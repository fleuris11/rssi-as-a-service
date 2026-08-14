"""Socle de la console d'administration : traçabilité, droits, réglages.

Principe : **les administrateurs plateforme ne sont pas au-dessus de l'audit.**
Ils disposent des droits les plus étendus de la plateforme (suspendre un
client, changer son offre, modifier le catalogue) ; ce sont précisément les
actions qu'il faut pouvoir reconstituer après coup.

Complémentaire de ``SecretRevealAudit`` (ADR-014) sans le remplacer : celui-ci
trace l'accès à une donnée d'un tenant, celui-là trace un acte de gestion. Le
journal consolidé du back-office affiche les deux.
"""

from django.conf import settings
from django.db import models

from apps.tenants.models import Tenant


class AdminAuditLog(models.Model):
    class Action(models.TextChoices):
        # Abonnements
        SUBSCRIPTION_ACTIVATED = "subscription_activated", "Abonnement activé"
        SUBSCRIPTION_SUSPENDED = "subscription_suspended", "Abonnement suspendu"
        SUBSCRIPTION_CANCELLED = "subscription_cancelled", "Abonnement résilié"
        SUBSCRIPTION_UPDATED = "subscription_updated", "Abonnement modifié"
        PLAN_CHANGED = "plan_changed", "Offre modifiée"
        TRIAL_STARTED = "trial_started", "Essai ouvert"
        TRIAL_EXTENDED = "trial_extended", "Essai prolongé"
        QUOTA_OVERRIDDEN = "quota_overridden", "Quota négocié appliqué"
        PAYMENT_RECORDED = "payment_recorded", "Paiement enregistré"
        # Catalogue
        PLAN_CREATED = "plan_created", "Offre créée"
        PLAN_UPDATED = "plan_updated", "Offre mise à jour"
        PLAN_PUBLISHED = "plan_published", "Offre publiée"
        PLAN_RETIRED = "plan_retired", "Offre retirée"
        PLAN_DUPLICATED = "plan_duplicated", "Offre dupliquée"
        # Clients et utilisateurs
        TENANT_CREATED = "tenant_created", "Entreprise créée"
        TENANT_UPDATED = "tenant_updated", "Entreprise modifiée"
        TENANT_ARCHIVED = "tenant_archived", "Entreprise archivée"
        TENANT_RESTORED = "tenant_restored", "Entreprise restaurée"
        TENANT_DELETED = "tenant_deleted", "Entreprise supprimée définitivement"
        USER_INVITED = "user_invited", "Utilisateur invité"
        USER_ROLE_CHANGED = "user_role_changed", "Rôle d'utilisateur modifié"
        USER_DEACTIVATED = "user_deactivated", "Utilisateur désactivé"
        USER_REACTIVATED = "user_reactivated", "Utilisateur réactivé"
        USER_REMOVED = "user_removed", "Utilisateur retiré d'une entreprise"
        PASSWORD_RESET_SENT = "password_reset_sent", "Réinitialisation de mot de passe émise"
        # Actifs et actions sur les données
        MONITORED_ASSET_ADDED = "monitored_asset_added", "Actif mis sous surveillance"
        MONITORED_ASSET_REMOVED = "monitored_asset_removed", "Actif retiré de la surveillance"
        SCAN_TRIGGERED = "scan_triggered", "Analyse déclenchée"
        SECRETS_PURGED = "secrets_purged", "Secrets purgés"
        # Prospects
        DEMO_REQUEST_UPDATED = "demo_request_updated", "Demande de démonstration traitée"
        PROSPECT_CREATED = "prospect_created", "Prospect créé"
        PROSPECT_UPDATED = "prospect_updated", "Prospect modifié"
        PROSPECT_NOTE_ADDED = "prospect_note_added", "Note ajoutée à un prospect"
        # Plateforme
        ADMIN_INVITED = "admin_invited", "Administrateur invité"
        ADMIN_LEVEL_CHANGED = "admin_level_changed", "Niveau d'administrateur modifié"
        ADMIN_REVOKED = "admin_revoked", "Administrateur retiré"
        SETTING_CHANGED = "setting_changed", "Réglage de plateforme modifié"
        EXPORT_GENERATED = "export_generated", "Export généré"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    action = models.CharField(max_length=40, choices=Action.choices)
    # Nullable : une action peut porter sur le catalogue et non sur un client.
    tenant = models.ForeignKey(
        Tenant, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # Ce sur quoi on a agi, en clair : un identifiant seul serait illisible
    # une fois l'objet supprimé.
    target = models.CharField(max_length=200, blank=True)
    detail = models.TextField(blank=True)
    # Valeurs avant/après pour les modifications : {"champ": [avant, après]}.
    # Sans elles, « Offre mise à jour » ne dit pas CE QUI a changé — or c'est
    # exactement la question qu'on se pose en relisant un journal.
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at"]), models.Index(fields=["action"])]

    def __str__(self):
        return f"{self.get_action_display()} — {self.target or '—'}"


class PlatformAdminProfile(models.Model):
    """Niveau de droits d'un administrateur plateforme.

    ``is_staff`` seul est binaire : il ouvre tout. Un collaborateur commercial
    doit pouvoir travailler ses prospects sans pouvoir suspendre un client ni
    toucher au catalogue. Le niveau est porté ici plutôt que par les
    permissions Django natives : il s'agit de deux ou trois rôles métier
    stables, pas d'une matrice de permissions à administrer.
    """

    class Level(models.TextChoices):
        FULL = "full", "Administrateur complet"
        COMMERCIAL = "commercial", "Commercial (lecture + prospects)"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="platform_admin"
    )
    level = models.CharField(max_length=12, choices=Level.choices, default=Level.COMMERCIAL)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__email"]

    def __str__(self):
        return f"{self.user_id} ({self.level})"

    @property
    def can_write(self) -> bool:
        return self.level == self.Level.FULL


class PlatformSetting(models.Model):
    """Réglage d'exploitation modifiable depuis la console.

    Sépare délibérément deux natures de configuration :

    - les **réglages d'exploitation** (plafonds de licence, durée d'essai,
      rétention, seuils d'alerte) vivent ici, en base : les changer ne doit
      pas demander un accès au serveur ni un redémarrage ;
    - les **secrets** (clés de chiffrement, jetons d'API) restent en variables
      d'environnement. Les stocker en base les exposerait à toute injection SQL
      et à toute sauvegarde de la base. La console montre leur présence et leur
      validité, jamais leur valeur, et n'offre aucun champ pour les saisir.

    La valeur est un JSON pour porter aussi bien un entier qu'un booléen ou un
    texte sans multiplier les colonnes.
    """

    key = models.CharField(max_length=60, unique=True)
    value = models.JSONField()
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return f"{self.key} = {self.value}"

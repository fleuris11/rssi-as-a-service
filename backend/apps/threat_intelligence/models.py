"""Data models for the threat_intelligence app (Phase 7, ADR-013/014).

Every model is tenant-scoped (``TenantScopedModel``) except the fact that
the *ceiling* they operate under (query quota, monitored-asset pool) is a
platform-wide, licence-level constraint, not a per-tenant one — see
``quota.py``/``pool.py`` in services.py for where that global bookkeeping
actually lives. Like apps.monitoring/apps.ai_assistant, FKs to another
app's model (``monitoring.Asset``) are imported directly — established
precedent in this codebase (apps.ai_assistant.models does the same for
FK/type-check purposes), cross-app *business logic* still goes through
that app's services.py.
"""

from django.conf import settings
from django.db import models

from apps.monitoring.models import Asset
from apps.tenants.models import TenantScopedModel


class BreachFinding(TenantScopedModel):
    """One normalized compromise finding. ADR-014 (updated): the secret a
    provider returns (password, token, cookie, card...) is never written in
    clear — it is Fernet-encrypted at ingestion (``secret_encrypted``, key
    ``BREACH_SECRET_ENCRYPTION_KEY``, dedicated and distinct from every
    other Fernet key in this codebase) and only ever decrypted in memory by
    the privileged, re-authenticated reveal endpoint
    (``BreachFindingRevealView``). ``secret_masked``/``has_secret`` remain
    the non-reversible default-display form."""

    class SourceEndpoint(models.TextChoices):
        STEALER = "stealer", "Logs de malware voleur d'identifiants"
        COMBO = "combo", "Liste combo (identifiant + mot de passe)"
        CREDS = "creds", "Identifiants exposés"
        SESSIONS = "sessions", "Sessions / cookies compromis"
        NHI = "nhi", "Identité non-humaine (clé de service, token API)"
        DARKWEB = "darkweb", "Mention dark web"
        DOCS = "docs", "Document fuité"
        ASM = "asm", "Surface d'attaque"
        RADAR = "radar", "Radar (mentions publiques)"
        WEBHOOK = "webhook", "Notification temps réel (webhook)"

    class Severity(models.TextChoices):
        # Mapping imposé par le prompt Phase 7 : stealer/sessions/nhi/darkweb
        # = critique ; creds/combo/docs = élevé ; radar/asm-phishing =
        # attention. Voir threat_intelligence.providers.breachsense.normalizer.
        CRITICAL = "critical", "Critique"
        HIGH = "high", "Élevée"
        ATTENTION = "attention", "Attention"

    class Status(models.TextChoices):
        OPEN = "open", "Ouvert"
        TREATED = "treated", "Traité"
        IGNORED = "ignored", "Ignoré"

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="breach_findings")
    source_endpoint = models.CharField(max_length=20, choices=SourceEndpoint.choices)
    finding_type = models.CharField(max_length=60)
    severity = models.CharField(max_length=10, choices=Severity.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)

    # ADR-014 §4 : en clair UNIQUEMENT si l'identifiant est l'email pro d'un
    # membre du tenant ; sinon la forme masquée est seule renseignée.
    identifier_plain = models.CharField(max_length=255, blank=True)
    identifier_masked = models.CharField(max_length=255, blank=True)

    # ADR-014 §1/§2 : jamais le secret en clair en base — uniquement sa
    # forme masquée non réversible pour l'affichage par défaut.
    secret_masked = models.CharField(max_length=32, blank=True)
    # ADR-014 (mise à jour) : chiffrement réversible à accès privilégié.
    # Blob Fernet (clé BREACH_SECRET_ENCRYPTION_KEY, dédiée) — vide (b"")
    # si aucun secret n'a été détecté, ou pour tout finding ingéré avant
    # l'introduction de ce champ (voir migration : has_secret=False dans ce
    # cas, jamais reconstruit rétroactivement à partir de secret_seen).
    secret_encrypted = models.BinaryField(blank=True, default=b"")
    # Vrai uniquement si secret_encrypted contient réellement un blob
    # déchiffrable — pas un simple report de l'ancien indicateur
    # "un secret a été vu à l'ingestion" (voir migration 0002).
    has_secret = models.BooleanField(default=False)
    # Phase 8C : horodatage de la purge du secret (rétention configurable).
    # On purge le SECRET, jamais la fuite : les métadonnées, le statut et
    # l'historique de traitement restent, seule la valeur récupérable
    # disparaît. Renseigné => l'interface affiche « secret purgé après X
    # jours » au lieu de laisser croire qu'il n'y en a jamais eu.
    secret_purged_at = models.DateTimeField(null=True, blank=True)

    breach_date = models.DateField(null=True, blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)
    # V2-1 : dernière fois que le fournisseur a REMONTÉ cette même fuite.
    # Distinct de ``detected_at``, qui ne bouge jamais : une fuite traitée que
    # trois scans successifs revoient reste détectée le premier jour, et c'est
    # ce que doit dire son historique de traitement. Ce que ``last_seen_at``
    # ajoute, c'est de quoi répondre honnêtement à « elle est toujours là ? »
    # sans rouvrir ce que le client a déjà traité.
    last_seen_at = models.DateTimeField(null=True, blank=True)

    # Payload déjà masqué au moment de la normalisation (ADR-014 §2) — champs
    # non-sensibles uniquement (endpoint d'origine, métadonnées).
    raw_data = models.JSONField(default=dict, blank=True)

    # Dédoublonnage (scan répété, webhook redélivré) — voir
    # providers/breachsense/normalizer.py pour le calcul, services.py pour
    # la façon dont il est consulté.
    #
    # ``dedup_hash`` reste la clé d'unicité (contrainte inchangée). Les deux
    # colonnes qui l'accompagnent ne sont pas redondantes : elles portent les
    # DEUX moitiés dont il est la combinaison, et c'est en les interrogeant
    # séparément qu'on peut répondre à « même compte, autre mot de passe ».
    dedup_hash = models.CharField(max_length=64)
    # Identité de la fuite, SECRET EXCLU. Vide pour les fuites ingérées avant
    # la V2-1 dont l'endpoint d'origine n'est plus reconstituable (endpoint
    # inconnu retombé sur "webhook") — voir la migration 0006.
    identity_hash = models.CharField(max_length=64, blank=True, db_index=True)
    # Empreinte à sens unique du secret ; "" quand la fuite n'en porte pas.
    # Préfixée de ``legacy:`` pour les fuites antérieures à la V2-1, dont le
    # secret en clair n'a jamais été empreint : elles se raccrochent alors sur
    # leur forme masquée, une fois, à leur première réobservation.
    #
    # N'est JAMAIS purgée avec le secret (Phase 8C) : une empreinte n'est pas
    # une valeur récupérable, et la purger casserait le dédoublonnage des
    # fuites les plus anciennes — exactement celles qu'un client a déjà
    # traitées et ne veut plus revoir.
    secret_fingerprint = models.CharField(max_length=71, blank=True)

    alert = models.ForeignKey(
        "monitoring.Alert", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    treated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    treated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-detected_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "dedup_hash"], name="unique_breach_finding_per_tenant_dedup"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "-detected_at"]),
            models.Index(fields=["asset", "-detected_at"]),
            # Sert le raccrochage des fuites antérieures à la V2-1 : à chaque
            # ingestion, une recherche par identité quand la clé complète ne
            # trouve rien.
            models.Index(fields=["tenant", "identity_hash"], name="ti_finding_tenant_identity_idx"),
        ]

    def __str__(self):
        return f"{self.asset_id} — {self.source_endpoint} — {self.severity} ({self.status})"


class MonitoredAsset(TenantScopedModel):
    """One occupied slot in the provider's real-time webhook monitoring
    pool (15 slots on the Essentials tier — a platform-wide, not
    per-tenant, ceiling; see threat_intelligence.services.pool). Distinct
    from — and always backed by — a ``monitoring.Asset``: only assets the
    tenant has already declared for passive checks may be registered for
    breach monitoring (extends ADR-010's "actif déclaré uniquement" to
    CTI)."""

    asset = models.OneToOneField(
        Asset, on_delete=models.CASCADE, related_name="threat_intel_monitored_asset"
    )
    provider = models.CharField(max_length=30, default="breachsense")
    provider_ref = models.CharField(max_length=255)
    # Vocabulaire du fournisseur externe (ex. "domain") — délibérément une
    # chaîne libre plutôt qu'un TextChoices : c'est Breachsense qui définit
    # ces valeurs, pas la plateforme (les deux types d'actifs monitoring
    # actuels, website et email_domain, sont tous deux des domaines côté
    # Breachsense — voir threat_intelligence.services.register_monitored_asset).
    provider_asset_type = models.CharField(max_length=20, default="domain")
    registered_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-registered_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_ref"], name="unique_provider_ref_per_provider"
            ),
        ]

    def __str__(self):
        return f"{self.provider} — {self.asset_id} ({'actif' if self.is_active else 'inactif'})"


class BreachIntelligenceUsage(TenantScopedModel):
    """Audit/attribution log: which tenant's scan consumed how much of the
    platform-wide "query" budget, and what the provider reported as
    remaining right after (QuotaManager's cache is seeded from this, not
    the other way round — see services.py)."""

    class TriggeredBy(models.TextChoices):
        INITIAL = "initial", "Scan initial (déclaration d'actif)"
        MANUAL = "manual", "Scan manuel"
        # Déclenché par l'exploitant depuis la fiche client, pas par le client
        # lui-même. La distinction compte pour l'attribution : c'est la même
        # licence qui paie, mais pas la même personne qui décide.
        PLATFORM_ADMIN = "platform_admin", "Analyse lancée par l'exploitant"

    endpoint = models.CharField(max_length=20, blank=True)
    requests_consumed = models.PositiveIntegerField(default=0)
    remaining_after = models.IntegerField(null=True, blank=True)
    triggered_by = models.CharField(max_length=20, choices=TriggeredBy.choices)
    findings_created = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tenant_id} — {self.triggered_by} — {self.requests_consumed} req"


class BreachScanJob(TenantScopedModel):
    """Async job pattern reused from ADR-011 (apps.ai_assistant.AIJob):
    POST creates the job, GET polls status/result. Always executed via
    Celery, queue "monitoring" (ADR-013: CTI is a monitoring sub-domain,
    not an AI one)."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        RUNNING = "running", "En cours"
        DONE = "done", "Terminé"
        FAILED = "failed", "Échec"

    asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, null=True, blank=True, related_name="breach_scan_jobs"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    triggered_by = models.CharField(
        max_length=20, choices=BreachIntelligenceUsage.TriggeredBy.choices
    )

    # V2-6 : le même job sert deux périmètres. Les analyses de comptes
    # désignés n'ont pas d'actif (``asset`` reste nul) et portent leurs
    # comptes dans ``result_ref``. Un second modèle de job aurait dupliqué le
    # statut, les reprises et la tâche Celery pour la seule différence de ce
    # qu'on interroge.
    class Scope(models.TextChoices):
        ASSETS = "assets", "Actifs déclarés"
        WATCHED_ACCOUNTS = "watched_accounts", "Comptes désignés"

    scope = models.CharField(max_length=20, choices=Scope.choices, default=Scope.ASSETS)
    result_ref = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.status} — {self.tenant_id} ({self.triggered_by})"


class ExposureSynthesis(TenantScopedModel):
    """Cached AI reading of the tenant's current exposure (Phase 8B, tâche 4).

    Cached rather than computed on read for two reasons: an AI call costs
    tokens against the tenant's monthly quota (cadrage §8), and the exposure
    page must render instantly and completely **without** it — the synthesis
    is a layer on top, never a prerequisite. ``is_stale`` is flipped when a
    finding is created or its status changes, so the banner can say "cette
    analyse date d'avant vos dernières actions" instead of silently showing
    a reading that no longer matches the page under it.

    One row per tenant (the latest reading replaces the previous one): this
    is a cache, not an audit trail — ``AIUsageLog`` already records every
    call for traceability.
    """

    content = models.TextField()
    generated_at = models.DateTimeField(auto_now=True)
    is_stale = models.BooleanField(default=False)
    # Empreinte de l'état des fuites au moment de la génération — permet de
    # ne pas régénérer si rien n'a bougé, même si le tenant clique.
    findings_fingerprint = models.CharField(max_length=64, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant"], name="unique_exposure_synthesis_per_tenant"),
        ]

    def __str__(self):
        state = "obsolète" if self.is_stale else "à jour"
        return f"Synthèse d'exposition — {self.tenant_id} ({state})"


class SecretPurgeRun(models.Model):
    """Trace d'une exécution de la purge des secrets (Phase 8C).

    Délibérément **non** tenant-scopé : la purge est une tâche plateforme qui
    balaie tous les tenants en une passe, et son journal sert au back-office
    plateforme (« la politique de rétention tourne-t-elle réellement ? »).
    Ne contient jamais de secret ni d'identifiant — seulement des compteurs,
    ce qui est précisément ce qu'on veut pouvoir montrer à un client ou à un
    auditeur.
    """

    started_at = models.DateTimeField(auto_now_add=True)
    retention_days = models.PositiveIntegerField()
    secrets_purged = models.PositiveIntegerField(default=0)
    reveal_audits_deleted = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return (
            f"Purge du {self.started_at:%Y-%m-%d %H:%M} — "
            f"{self.secrets_purged} secret(s), {self.reveal_audits_deleted} entrée(s) d'audit"
        )


class IdentifierAccessAudit(TenantScopedModel):
    """Trace des consultations d'adresses compromises en clair (V2-2, ADR-027).

    Afficher une adresse email est un traitement de données personnelles. La
    V2-2 démasque ces adresses parce que le RSSI ne peut pas agir sans savoir
    QUI est concerné — mais démasquer sans tracer reviendrait à échanger un
    problème d'utilité contre un problème de conformité.

    L'encadrement est **délibérément plus léger** que celui de la révélation
    d'un secret (ADR-014) : pas de ré-authentification, pas de limitation de
    débit, pas de refus par défaut. Une adresse n'est pas un mot de passe —
    elle ne donne accès à rien. Exiger les cinq conditions de la révélation
    pour la lire rendrait le produit inutilisable au quotidien, et une garde
    qu'on contourne parce qu'elle gêne ne protège personne.

    Ce qui est tracé, c'est **l'accès**, pas chaque adresse : une ligne par
    consultation ou par export, avec les actifs concernés et le nombre
    d'adresses servies. Une ligne par adresse ferait, sur un actif réel de
    production, 28 450 lignes d'audit pour un seul affichage de page.
    """

    class Context(models.TextChoices):
        CONSULTATION = "consultation", "Consultation à l'écran"
        EXPORT = "export", "Export de données"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    context = models.CharField(max_length=20, choices=Context.choices)
    # Actifs concernés par les adresses servies. Stockés en liste plutôt qu'en
    # relation : c'est une trace, pas un index — elle doit survivre à la
    # suppression d'un actif, ce qu'une clé étrangère ne ferait pas.
    asset_ids = models.JSONField(default=list, blank=True)
    identifier_count = models.PositiveIntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "-created_at"])]

    def __str__(self):
        return (
            f"{self.get_context_display()} — {self.identifier_count} adresse(s) — "
            f"{self.tenant_id} — {self.user_id}"
        )


class SecretRevealAudit(TenantScopedModel):
    """Audit trail for the privileged secret-reveal endpoint (ADR-014,
    update: reversible encryption + re-authenticated reveal). Every attempt
    — granted or denied, and for every denial reason — is recorded here,
    never the secret itself. ``finding`` is nullable/``SET_NULL`` so the
    audit trail outlives the finding it concerns (compliance record, not a
    cache of it)."""

    class DenialReason(models.TextChoices):
        ROLE = "role", "Rôle administrateur requis"
        STEP_UP = "step_up", "Ré-authentification invalide"
        NO_SECRET = "no_secret", "Aucun secret chiffré disponible"
        NOT_FOUND = "not_found", "Fuite introuvable ou hors périmètre du tenant"

    finding = models.ForeignKey(
        BreachFinding,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reveal_audits",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    success = models.BooleanField()
    denial_reason = models.CharField(max_length=20, choices=DenialReason.choices, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "-created_at"])]

    def __str__(self):
        outcome = "accordée" if self.success else f"refusée ({self.denial_reason})"
        return f"Révélation {outcome} — {self.tenant_id} — {self.user_id}"


# --- Comptes désignés (V2-6, ADR-033) ---------------------------------------


class WatchedAccount(TenantScopedModel):
    """Un compte que le client demande à faire surveiller, en dehors de ses
    domaines : l'adresse de son dirigeant, celle d'un client important, un
    compte technique sensible.

    **Le point qui n'est pas technique.** Faire surveiller l'adresse d'un
    tiers est un traitement de données personnelles de ce tiers. La base
    légale relève du client, pas de la plateforme — mais le produit ne peut
    pas se contenter de l'ignorer : il fait déclarer, il fige la déclaration,
    et il la garde. C'est le rôle des cinq champs ``legal_basis`` →
    ``declared_at``. Voir ADR-033.

    ``declaration_text`` conserve le **texte exact** accepté au moment de la
    déclaration, et non un renvoi à la version courante des conditions : le
    jour où l'on reformule cet engagement, ce qu'a réellement accepté ce
    client-là ne doit pas changer rétroactivement.

    Le retrait est **logique** (``removed_at``). Une ligne supprimée
    emporterait la déclaration avec elle, et avec elle la preuve de la date à
    laquelle la surveillance a cessé — exactement ce qu'on veut pouvoir
    montrer si la personne concernée le demande.
    """

    class Category(models.TextChoices):
        EXECUTIVE = "executive", "Dirigeant ou mandataire social"
        EMPLOYEE = "employee", "Collaborateur"
        CLIENT = "client", "Client ou partenaire"
        SERVICE = "service", "Compte technique ou de service"
        OTHER = "other", "Autre"

    class LegalBasis(models.TextChoices):
        """Ce que le client déclare comme fondement du traitement.

        Formulé dans les termes d'un dirigeant de PME, pas dans ceux du
        RGPD : « c'est mon compte », « c'est un compte professionnel de mon
        entreprise ». Le rapprochement avec l'article 6 est fait dans
        ADR-033, pas dans une liste déroulante que personne ne comprendrait.
        """

        OWN = "own", "C'est mon propre compte"
        COMPANY = "company", "Compte professionnel fourni par mon entreprise"
        CONSENT = "consent", "La personne concernée m'a donné son accord"
        CONTRACT = "contract", "Prévu au contrat qui me lie à cette personne"
        OTHER = "other", "Autre situation, que je précise ci-dessous"

    # Normalisé en minuscules par le service : deux déclarations qui ne
    # diffèrent que par la casse sont le même compte, et compteraient deux
    # fois dans le quota.
    value = models.CharField(max_length=255)
    label = models.CharField(max_length=120, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)

    # --- La déclaration, figée à la création --------------------------------
    legal_basis = models.CharField(max_length=20, choices=LegalBasis.choices)
    # Obligatoire, contrairement au « pourquoi » d'une demande d'accès
    # (V2-4) qui, lui, est facultatif. La différence est entière : là on
    # demandait une fonctionnalité, ici on déclare traiter les données d'un
    # tiers. Une finalité vide rendrait la déclaration ininterprétable le
    # jour où quelqu'un la relit.
    purpose = models.TextField()
    declaration_text = models.TextField()
    declaration_version = models.CharField(max_length=20)
    declared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    declared_at = models.DateTimeField(auto_now_add=True)

    # --- Cycle de vie -------------------------------------------------------
    is_active = models.BooleanField(default=True)
    last_scanned_at = models.DateTimeField(null=True, blank=True)
    #: Le PREMIER passage sur ce compte (lot A). Il remonte tout
    #: l'historique connu du fournisseur — des milliers d'entrees, c'est
    #: normal. Les passages suivants ne rapportent que du nouveau. Sans
    #: cette distinction, un client decouvre un volume enorme et croit a
    #: une catastrophe du jour.
    first_scanned_at = models.DateTimeField(null=True, blank=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    removal_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-declared_at"]
        constraints = [
            # Partielle : un compte retiré puis re-déclaré est une NOUVELLE
            # déclaration, avec sa propre date et sa propre finalité. La
            # contrainte ne doit donc porter que sur les comptes actifs.
            models.UniqueConstraint(
                fields=["tenant", "value"],
                condition=models.Q(is_active=True),
                name="unique_active_watched_account",
            ),
        ]
        indexes = [models.Index(fields=["tenant", "is_active"])]

    def __str__(self):
        etat = "surveillé" if self.is_active else "retiré"
        return f"{self.value} ({etat})"


class WatchedAccountFinding(TenantScopedModel):
    """Ce que le fournisseur remonte sur un compte désigné.

    Table distincte de ``BreachFinding``, et c'est la décision structurante
    d'ADR-033. Trois raisons, dans cet ordre :

    1. **ce ne sont pas les actifs du client.** La consigne V2-6 demande une
       présentation séparée ; une table séparée rend la séparation
       structurelle plutôt que dépendante d'un filtre que chaque requête
       devrait penser à poser. Le score d'exposition (ADR-016), le fil
       d'exposition, les indicateurs de comité et le registre des incidents
       interrogent ``BreachFinding`` : ils ignorent ces lignes sans qu'on ait
       eu à les modifier ;
    2. **aucune alerte de surveillance n'est ouverte.** Une alerte se pose sur
       un ``monitoring.Asset``, et il n'y en a pas ici ;
    3. **aucun secret n'est conservé, même chiffré.** ``BreachFinding`` chiffre
       le secret pour permettre sa révélation tracée (ADR-014). Révéler le mot
       de passe du compte d'un tiers à quelqu'un d'autre que lui est une tout
       autre affaire, et l'action utile est la même sans le secret : « ce
       compte est exposé, faites-le changer ». Il n'y a donc pas de colonne à
       révéler, et rien à purger.
    """

    class Status(models.TextChoices):
        OPEN = "open", "Ouvert"
        TREATED = "treated", "Traité"
        IGNORED = "ignored", "Ignoré"

    account = models.ForeignKey(WatchedAccount, on_delete=models.CASCADE, related_name="findings")
    source_endpoint = models.CharField(max_length=20, choices=BreachFinding.SourceEndpoint.choices)
    finding_type = models.CharField(max_length=60)
    severity = models.CharField(max_length=10, choices=BreachFinding.Severity.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)

    # Toujours masqué. Le compte lui-même est déjà connu du client — il l'a
    # déclaré — et reproduire l'adresse en clair sur chaque ligne la
    # multiplierait dans les exports et les captures d'écran sans rien
    # apprendre à personne.
    identifier_masked = models.CharField(max_length=255, blank=True)
    # Qu'un mot de passe ait fuité ou non change la gravité et l'urgence ; sa
    # valeur, elle, n'est ni stockée ni récupérable (voir la docstring).
    secret_masked = models.CharField(max_length=32, blank=True)
    has_secret = models.BooleanField(default=False)

    breach_date = models.DateField(null=True, blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    treated_at = models.DateTimeField(null=True, blank=True)
    #: Vrai si cette observation vient du PREMIER passage sur le compte,
    #: c'est-a-dire de la reprise d'historique. Faux si elle est apparue
    #: depuis. L'ecran doit le dire : « historique decouvert au premier
    #: scan » et « apparu depuis » ne demandent pas la meme reaction.
    from_first_scan = models.BooleanField(default=False)
    raw_data = models.JSONField(default=dict, blank=True)
    dedup_hash = models.CharField(max_length=64)

    class Meta:
        ordering = ["-detected_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "dedup_hash"], name="unique_watched_account_finding"
            ),
        ]
        indexes = [models.Index(fields=["tenant", "status", "-detected_at"])]

    def __str__(self):
        return f"{self.account_id} — {self.finding_type} ({self.severity})"

from django.conf import settings
from django.db import models

from apps.tenants.models import TenantScopedModel


class Asset(TenantScopedModel):
    """Something a tenant has declared and attested ownership of — checks
    only ever run against assets that exist here (CLAUDE.md: "un actif
    n'est vérifié que s'il est déclaré par le tenant").

    V2-1 (ADR-026) : **déclarer n'est pas posséder**. En production, un
    client a déclaré et fait surveiller le domaine d'une autre organisation.
    ``ownership_confirmed`` ne dit que « quelqu'un a coché une case » ; la
    preuve, elle, vit dans ``AssetOwnershipProof``, et la déclaration sur
    l'honneur — datée, nominative — dans ``AssetOwnershipAttestation``.
    """

    class Type(models.TextChoices):
        WEBSITE = "website", "Site web"
        EMAIL_DOMAIN = "email_domain", "Domaine email"

    type = models.CharField(max_length=20, choices=Type.choices)
    # WEBSITE: a full https:// URL. EMAIL_DOMAIN: a bare domain name.
    value = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    # Required True at creation (US-5.1: "preuve de légitimité") — enforced
    # in the serializer, not just defaulted here.
    ownership_confirmed = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "type", "value"], name="unique_asset_per_tenant"
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_type_display()} — {self.value}"


class AssetOwnershipAttestation(TenantScopedModel):
    """Déclaration sur l'honneur d'être habilité sur un actif — **tracée**.

    L'ancêtre de ce modèle est la case ``Asset.ownership_confirmed``, qui
    n'enregistrait rien : ni qui l'avait cochée, ni quand, ni sur quel actif.
    Le jour où un tiers demande des comptes sur la surveillance de son
    domaine, un booléen ne répond à aucune de ces trois questions.

    Le texte accepté est recopié dans ``statement`` plutôt que référencé :
    une déclaration doit pouvoir être relue telle qu'elle a été présentée,
    même après que le libellé du formulaire a changé.
    """

    asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, related_name="ownership_attestations"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    statement = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["asset", "-created_at"])]

    def __str__(self):
        return f"Déclaration sur l'honneur — actif {self.asset_id} — {self.created_at:%Y-%m-%d}"


class AssetOwnershipProof(TenantScopedModel):
    """Preuve de possession d'un domaine, exigée avant la surveillance continue.

    Trois méthodes au choix du client, parce qu'aucune n'est disponible pour
    tout le monde : une PME dont le site est chez un hébergeur mutualisé n'a
    pas toujours la main sur la zone DNS ; une autre ne peut pas déposer de
    fichier sur un site géré par un prestataire ; une troisième n'a plus
    accès aux adresses génériques de son domaine.

    Le jeton n'est pas un secret au sens de l'ADR-014 — il est justement fait
    pour être publié par le client. Il reste néanmoins imprévisible : sans
    cela, n'importe qui pourrait publier le jeton d'un domaine qu'il ne
    possède pas en le devinant.
    """

    class Method(models.TextChoices):
        DNS_TXT = "dns_txt", "Enregistrement DNS TXT"
        HTTP_FILE = "http_file", "Fichier à la racine du site"
        EMAIL = "email", "Email de validation"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente de vérification"
        VERIFIED = "verified", "Vérifiée"
        FAILED = "failed", "Dernière vérification en échec"

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="ownership_proofs")
    method = models.CharField(max_length=20, choices=Method.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    token = models.CharField(max_length=64)
    # Méthode email uniquement : l'adresse générique choisie par le client
    # parmi une liste fermée (voir services.OWNERSHIP_EMAIL_LOCAL_PARTS).
    # Laisser le client saisir l'adresse de son choix viderait la méthode de
    # son sens — il suffirait d'indiquer la sienne.
    email_recipient = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    # Ce qui manquait à la dernière tentative, en français, destiné au client.
    last_error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Une seule preuve VÉRIFIÉE par actif : au-delà, c'est du bruit,
            # et deux preuves vérifiées ne valent pas mieux qu'une.
            models.UniqueConstraint(
                fields=["asset"],
                condition=models.Q(status="verified"),
                name="unique_verified_ownership_proof_per_asset",
            ),
        ]
        indexes = [models.Index(fields=["asset", "status"])]

    def __str__(self):
        return f"{self.get_method_display()} — actif {self.asset_id} ({self.get_status_display()})"


class CheckResult(TenantScopedModel):
    """One timestamped observation. Status is a shared tri-state across
    every check type — deliberately: it's what the ☀️/⚠️/🔴 weather email
    (apps.notifications) reads directly, no per-check-type translation."""

    class CheckType(models.TextChoices):
        HTTP_UPTIME = "http_uptime", "Disponibilité HTTP"
        SSL_CERTIFICATE = "ssl_certificate", "Certificat SSL"
        SECURITY_HEADERS = "security_headers", "En-têtes de sécurité"
        EMAIL_DNS = "email_dns", "Configuration email (SPF/DMARC)"

    class Status(models.TextChoices):
        OK = "ok", "OK"
        WARNING = "warning", "Avertissement"
        CRITICAL = "critical", "Critique"

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="check_results")
    check_type = models.CharField(max_length=20, choices=CheckType.choices)
    status = models.CharField(max_length=10, choices=Status.choices)
    details = models.JSONField(default=dict, blank=True)
    latency_ms = models.FloatField(null=True, blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-checked_at"]
        indexes = [
            models.Index(fields=["asset", "check_type", "-checked_at"]),
        ]

    def __str__(self):
        return f"{self.asset_id} — {self.check_type} — {self.status}"


class Alert(TenantScopedModel):
    class AlertType(models.TextChoices):
        DOWN = "down", "Site indisponible"
        SSL_EXPIRING = "ssl_expiring", "Certificat SSL bientôt expiré"
        SECURITY_HEADERS = "security_headers", "En-têtes de sécurité manquants"
        EMAIL_MISCONFIGURED = "email_misconfigured", "Configuration email incomplète"
        # Phase 7 (ADR-013) : ouverte par apps.threat_intelligence via
        # services.open_or_update_alert, jamais par ce module lui-même —
        # apps.monitoring reste ignorant de threat_intelligence.
        BREACH_COMPROMISE = "breach_compromise", "Compromission détectée"

    class Severity(models.TextChoices):
        WARNING = "warning", "Avertissement"
        CRITICAL = "critical", "Critique"

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="alerts")
    alert_type = models.CharField(max_length=30, choices=AlertType.choices)
    severity = models.CharField(max_length=10, choices=Severity.choices)
    is_open = models.BooleanField(default=True)
    details = models.JSONField(default=dict, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]
        constraints = [
            # "pas de doublon d'alerte ouverte" enforced at the DB level
            # (partial unique index), not just in the service layer.
            models.UniqueConstraint(
                fields=["asset", "alert_type"],
                condition=models.Q(is_open=True),
                name="unique_open_alert_per_asset_type",
            ),
        ]

    def __str__(self):
        state = "ouverte" if self.is_open else "résolue"
        return f"{self.asset_id} — {self.alert_type} ({state})"

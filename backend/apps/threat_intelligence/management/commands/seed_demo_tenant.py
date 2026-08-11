"""Seeds (or resets) the client-demo tenant — Phase 8A.

Every finding is created by running realistic payloads through the **real**
ingestion pipeline (``services.ingest_raw_findings``): normalisation,
masquage, chiffrement du secret (ADR-014), dédoublonnage et ouverture
d'alerte sont donc exactement ceux de la production, pas une insertion
directe en base qui pourrait diverger silencieusement du vrai comportement.

Idempotence : rejouable à volonté. Les findings sont dédoublonnés par le
``dedup_hash`` calculé par le normaliseur (payloads identiques => mêmes
hashes => aucun doublon) ; ``--reset`` efface d'abord les données de démo
pour repartir d'un état propre avant une démo client.

Sécurité : le tenant de démo est identifié par un slug et un préfixe de nom
réservés (``DEMO_TENANT_SLUG`` / « Demo — »), jamais confondable avec un
tenant réel ; et la commande refuse de tourner avec ``DEBUG=False`` sans
``--allow-production`` explicite.
"""

from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.monitoring.models import Alert, Asset
from apps.tenants.models import Membership, Tenant
from apps.threat_intelligence import services
from apps.threat_intelligence.models import (
    BreachFinding,
    BreachIntelligenceUsage,
    BreachScanJob,
    ExposureSynthesis,
    MonitoredAsset,
    SecretRevealAudit,
)
from apps.threat_intelligence.providers.base import RawFinding

User = get_user_model()

DEMO_TENANT_SLUG = "demo-cabinet-durand"
DEMO_TENANT_NAME = "Demo — Cabinet Comptable Durand"
# Préfixe réservé : tout tenant dont le nom commence par ceci est une
# démonstration, jamais un client réel (convention vérifiée par les tests).
DEMO_TENANT_NAME_PREFIX = "Demo — "
DEMO_PASSWORD = "DemoDurand2026!"

DEMO_DOMAIN = "cabinet-durand-demo.fr"

DEMO_USERS = [
    # (email, prénom, nom, rôle) — le premier est l'admin qui fait la démo.
    (f"marie.durand@{DEMO_DOMAIN}", "Marie", "Durand", Membership.Role.ADMIN),
    (f"paul.leroy@{DEMO_DOMAIN}", "Paul", "Leroy", Membership.Role.CONTRIBUTOR),
    (f"sophie.marchand@{DEMO_DOMAIN}", "Sophie", "Marchand", Membership.Role.READER),
]

# Synthèse d'exposition pré-générée (Phase 8B) : texte FIXE, jamais un appel
# IA au moment du seed — la démo ne doit dépendre ni de l'API Anthropic ni du
# quota du tenant. Rédigée pour correspondre exactement aux fuites seedées
# ci-dessous (mêmes comptes, mêmes actifs) : une synthèse qui ne collerait pas
# aux données affichées se verrait immédiatement à l'écran.
DEMO_SYNTHESIS = (
    "Votre exposition est concentrée sur deux points : le compte de Marie Durand, "
    "qui apparaît dans trois fuites distinctes, et votre webmail, dont une session "
    "active a été compromise. "
    "Ces trois fuites autour du même compte suggèrent un poste infecté plutôt que "
    "trois incidents séparés — le mot de passe a probablement été recopié une fois, "
    "puis a circulé. "
    "La priorité de la semaine est le cookie de session du webmail : il permet "
    "d'entrer dans la messagerie sans mot de passe ni code de vérification, donc "
    "déconnecter toutes les sessions de ce compte est plus urgent que le changement "
    "de mot de passe lui-même. "
    "La clé de service AWS exposée vient juste après : elle reste utilisable tant "
    "qu'elle n'a pas été révoquée."
)

DEMO_ASSETS = [
    (Asset.Type.WEBSITE, f"https://www.{DEMO_DOMAIN}"),
    (Asset.Type.EMAIL_DOMAIN, DEMO_DOMAIN),
    (Asset.Type.WEBSITE, f"https://vpn.{DEMO_DOMAIN}"),
    (Asset.Type.WEBSITE, f"https://webmail.{DEMO_DOMAIN}"),
]


def _d(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


def demo_findings_payloads() -> list[tuple[str, dict, int]]:
    """(endpoint, payload, asset_index) — couvre TOUS les source_endpoint.

    Les "mots de passe" sont manifestement factices mais crédibles à
    l'écran : jamais un secret réel, jamais un mot de passe qu'un vrai
    utilisateur pourrait avoir (prompt Phase 8A point 3).
    """
    return [
        # --- stealer x2 (dont un révélable en démo) ------------------------
        (
            "stealer",
            {
                "usr": f"marie.durand@{DEMO_DOMAIN}",
                "pwd": "Hiver2024!durand",
                "src": "RedLine Stealer log",
                "fle": "passwords.txt",
                "inf": _d(41),
                "fnd": _d(38),
                "mal": "RedLine",
                "nme": "PC-COMPTA-01",
                "os": "Windows 11",
            },
            0,
        ),
        (
            "stealer",
            {
                "usr": f"paul.leroy@{DEMO_DOMAIN}",
                "pwd": "Cabinet2023*",
                "src": "Vidar Stealer log",
                "fle": "logins.txt",
                "inf": _d(96),
                "fnd": _d(92),
                "mal": "Vidar",
                "nme": "PORTABLE-PL",
                "os": "Windows 10",
            },
            0,
        ),
        # --- sessions (cookie M365 : contourne la MFA) ---------------------
        (
            "sessions",
            {
                "dom": "login.microsoftonline.com",
                "cookie_name": "ESTSAUTHPERSISTENT",
                "cookie_path": "/",
                "val": "DEMO.ey0000-cookie-de-session-factice-0000",
                "expires": _d(-20),
                "user_name": f"marie.durand@{DEMO_DOMAIN}",
                "inf": _d(12),
                "fnd": _d(9),
                "mal": "RedLine",
            },
            3,
        ),
        # --- nhi (clé API AWS) ---------------------------------------------
        (
            "nhi",
            {
                "token": "AKIADEMOFAKEKEY00000",
                "token_type": "aws_access_key",
                "platform": "AWS",
                "category": "service-account",
                "source_type": "stealer",
                "prefix": "AKIA",
                "src": "RedLine Stealer log",
                "pth": "C:/Users/paul/.aws/credentials",
                "usr": "svc-sauvegarde",
                "fnd": _d(27),
            },
            0,
        ),
        # --- creds x2 -------------------------------------------------------
        (
            "creds",
            {
                "eml": f"sophie.marchand@{DEMO_DOMAIN}",
                "pwd": "Printemps2022!",
                "src": "Fuite plateforme comptable 2023",
                "fnd": _d(128),
                "atr": "—",
                "hash": 0,
            },
            1,
        ),
        (
            "creds",
            {
                "eml": f"contact@{DEMO_DOMAIN}",
                "pwd": "Contact2021#",
                "src": "Fuite prestataire RH 2022",
                "fnd": _d(155),
                "atr": "—",
                "hash": 1,
            },
            1,
        ),
        # --- Le cas « réutilisation possible » de la démo (Phase 8C) ---------
        # L'adresse professionnelle de Marie Durand apparaît ici dans la fuite
        # d'un service EXTERNE, alors qu'elle apparaît déjà dans le log de
        # malware ci-dessus. Les deux signaux de corrélation se déclenchent
        # donc ensemble sur ce finding, qui porte en plus un mot de passe
        # récupérable : c'est l'enchaînement montré en démonstration
        # (corrélation -> hypothèse -> révélation pour la lever).
        (
            "creds",
            {
                "eml": f"marie.durand@{DEMO_DOMAIN}",
                "pwd": "Hiver2024!durand",
                "dom": "boutique-loisirs.example",
                "src": "Fuite boutique-loisirs.example 2025",
                "fnd": _d(58),
                "atr": "—",
                "hash": 0,
            },
            1,
        ),
        # --- Fuite ancienne dont le secret a dépassé la rétention -----------
        # Purgée par la commande après création (voir _simulate_purged_secret)
        # pour montrer à l'écran le second état du cycle de vie : la fuite
        # reste, son mot de passe non.
        (
            "combo",
            {
                "usr": f"sophie.marchand@{DEMO_DOMAIN}",
                "pwd": "Archive2019!",
                "src": "Liste combo 2019",
                "fle": "combo_ancien.txt",
                "fnd": _d(400),
                "cnt": 2,
            },
            1,
        ),
        # --- combo ----------------------------------------------------------
        (
            "combo",
            {
                "usr": f"paul.leroy@{DEMO_DOMAIN}",
                "pwd": "Bureau2020!",
                "src": "Liste combo 2025-Q4",
                "fle": "combo_fr.txt",
                "fnd": _d(64),
                "cnt": 4,
            },
            1,
        ),
        # --- docs -----------------------------------------------------------
        (
            "docs",
            {
                "doc_id": "demo-doc-4471",
                "file_name": "liasse_fiscale_client_2024.pdf",
                "file_hash": "9f2c4d7e1a8b6c3d5e0f7a9b2c4d6e8f",
                "file_size": 842000,
                "content_type": "application/pdf",
                "extraction_timestamp": _d(73),
                "leak_date": _d(75),
                "threat_actor": "LeakSite-Demo",
                "company_name": "Cabinet Comptable Durand",
                "domain_name": DEMO_DOMAIN,
                "url_main_post": "https://exemple-leaksite.invalid/post/demo",
            },
            1,
        ),
        # --- radar x2 (typosquat + mention forum) ----------------------------
        (
            "radar",
            {
                "data": "cabinet-durrand-demo.fr",
                "src": "Enregistrement de domaine similaire",
                "found": _d(4),
            },
            0,
        ),
        (
            "radar",
            {
                "data": DEMO_DOMAIN,
                "src": "Mention sur un forum spécialisé",
                "found": _d(16),
            },
            0,
        ),
        # --- asm (typosquatting/phishing => sévérité élevée) ------------------
        (
            "asm",
            {
                "dom": "cabinet-durand-demo.co",
                "type": "pphish",
                "cname": "",
                "ip": "203.0.113.42",
                "found": _d(6),
            },
            0,
        ),
        # --- darkweb ----------------------------------------------------------
        (
            "darkweb",
            {
                "data": DEMO_DOMAIN,
                "name": "Cabinet Comptable Durand",
                "desc": "Mention du cabinet dans une liste de cibles potentielles",
                "site": "ForumDemo",
                "tadesc": "Groupe opportuniste",
                "src": "veille-darkweb",
                "found": _d(21),
            },
            0,
        ),
    ]


class Command(BaseCommand):
    help = "Crée ou réinitialise le tenant de démonstration client (Phase 8A)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Supprime d'abord les données de démo existantes (findings, alertes, audits).",
        )
        parser.add_argument(
            "--allow-production",
            action="store_true",
            help="Obligatoire pour tourner avec DEBUG=False.",
        )

    def handle(self, *, reset, allow_production, **options):
        if not settings.DEBUG and not allow_production:
            raise CommandError(
                "DEBUG=False : refus de seeder des données de démonstration sur un environnement "
                "de type production. Relancez avec --allow-production si c'est bien l'intention."
            )

        with transaction.atomic():
            tenant = self._ensure_tenant()
            if reset:
                self._reset_demo_data(tenant)
            admin = self._ensure_users(tenant)
            assets = self._ensure_assets(tenant, admin)
            created = self._ensure_findings(tenant, assets)
            self._ensure_synthesis(tenant)

        total = BreachFinding.all_objects.filter(tenant=tenant).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Tenant de démo prêt : {tenant.name} (slug={tenant.slug}) — "
                f"{len(created)} fuite(s) créée(s) cette exécution, {total} au total.\n"
                f"Connexion démo : {DEMO_USERS[0][0]} / {DEMO_PASSWORD}"
            )
        )

    # --- Étapes ------------------------------------------------------------

    def _ensure_tenant(self) -> Tenant:
        tenant, created = Tenant.objects.get_or_create(
            slug=DEMO_TENANT_SLUG,
            defaults={
                "name": DEMO_TENANT_NAME,
                "sector": "Expertise comptable",
                "headcount": 12,
            },
        )
        if not created and tenant.name != DEMO_TENANT_NAME:
            tenant.name = DEMO_TENANT_NAME
            tenant.save(update_fields=["name"])
        return tenant

    def _reset_demo_data(self, tenant: Tenant) -> None:
        """Efface uniquement les données CTI/alertes du tenant de démo —
        jamais le tenant, ses utilisateurs ou ses actifs (rejouer la commande
        doit rester rapide et ne pas invalider une session ouverte pendant
        une démo)."""
        SecretRevealAudit.all_objects.filter(tenant=tenant).delete()
        BreachFinding.all_objects.filter(tenant=tenant).delete()
        BreachIntelligenceUsage.all_objects.filter(tenant=tenant).delete()
        BreachScanJob.all_objects.filter(tenant=tenant).delete()
        MonitoredAsset.all_objects.filter(tenant=tenant).delete()
        ExposureSynthesis.all_objects.filter(tenant=tenant).delete()
        Alert.all_objects.filter(tenant=tenant).delete()

    def _ensure_users(self, tenant: Tenant):
        admin = None
        for email, first_name, last_name, role in DEMO_USERS:
            user = User.objects.filter(email=email).first()
            if user is None:
                user = User.objects.create_user(
                    email=email,
                    password=DEMO_PASSWORD,
                    first_name=first_name,
                    last_name=last_name,
                )
            Membership.all_objects.get_or_create(tenant=tenant, user=user, defaults={"role": role})
            if role == Membership.Role.ADMIN and admin is None:
                admin = user
        return admin

    def _ensure_assets(self, tenant: Tenant, admin) -> list[Asset]:
        assets = []
        for asset_type, value in DEMO_ASSETS:
            asset, _created = Asset.all_objects.get_or_create(
                tenant=tenant,
                type=asset_type,
                value=value,
                defaults={"ownership_confirmed": True, "created_by": admin},
            )
            assets.append(asset)
        return assets

    def _ensure_findings(self, tenant: Tenant, assets: list[Asset]) -> list[BreachFinding]:
        tenant_emails = {email for email, _f, _l, _r in DEMO_USERS}
        created: list[BreachFinding] = []

        for endpoint, payload, asset_index in demo_findings_payloads():
            asset = assets[asset_index]
            raw = RawFinding(endpoint=endpoint, payload=payload)
            # Pipeline d'ingestion RÉEL (masquage, chiffrement du secret,
            # dédoublonnage, ouverture d'alerte) — c'est ce qui rend les
            # données de démo fidèles au comportement de production, et ce
            # qui rend cette commande naturellement idempotente.
            created.extend(
                services.ingest_raw_findings(
                    tenant=tenant, asset=asset, raw_findings=[raw], tenant_emails=tenant_emails
                )
            )

        self._spread_detection_dates(tenant)
        self._simulate_purged_secret(tenant)
        return created

    def _simulate_purged_secret(self, tenant: Tenant) -> None:
        """Applique la vraie purge (services.purge_expired_secrets) plutôt que
        de bricoler l'état à la main : la fuite « combo 2019 » est datée
        au-delà du délai de rétention, elle est donc effacée par le même code
        qui tourne en production. La démo montre ainsi un état réel, pas une
        mise en scène."""
        services.purge_expired_secrets()

    def _ensure_synthesis(self, tenant: Tenant) -> None:
        """Synthèse pré-générée (texte fixe) : la démo doit pouvoir montrer le
        bandeau « Analyse » sans dépendre de l'API Anthropic — même principe
        que les cassettes CTI (ADR-015). Écrite en base par le service normal,
        donc affichée exactement comme une vraie synthèse. Marquée non
        obsolète : les fuites viennent d'être (re)créées, l'analyse décrit
        bien l'état courant."""
        services.save_exposure_synthesis(tenant, DEMO_SYNTHESIS)

    def _spread_detection_dates(self, tenant: Tenant) -> None:
        """``detected_at`` est un ``auto_now_add`` : sans ce rattrapage, toutes
        les fuites de démo afficheraient la même seconde de détection, ce qui
        se voit immédiatement à l'écran. Aligné sur la date de fuite quand
        elle existe (détection quelques jours après la fuite, comme en vrai)."""
        now = timezone.now()
        for finding in BreachFinding.all_objects.filter(tenant=tenant):
            if finding.breach_date is None:
                continue
            detected = timezone.make_aware(
                timezone.datetime.combine(finding.breach_date, timezone.datetime.min.time())
            ) + timedelta(days=2, hours=9)
            if detected > now:
                detected = now
            BreachFinding.all_objects.filter(pk=finding.pk).update(detected_at=detected)

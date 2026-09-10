"""V2-1 — une fuite traitée ne réapparaît plus, et un secret changé compte
pour une nouvelle fuite.

**Migration purement additive.** Aucune colonne n'est supprimée, aucune
contrainte n'est retirée, et ``dedup_hash`` conserve ses valeurs
existantes : le code de la version précédente continue de tourner sur ce
schéma sans rien casser. C'est délibéré — la procédure de repli vers
``v1.0-production`` (docs/deploiement_production.md §6 bis) distingue le
retour du code seul du retour avec restauration de base, et une migration
qui casserait le code d'avant ferait basculer tout retour arrière dans le
second cas, le plus long et le plus risqué.

Ce que la migration ajoute :

- ``last_seen_at`` — dernière observation de la fuite par le fournisseur ;
- ``identity_hash`` — identité de la fuite, secret exclu ;
- ``secret_fingerprint`` — empreinte à sens unique du secret.

Le remplissage ne déchiffre RIEN. Il aurait fallu la clé Fernet pour
recalculer une vraie empreinte des secrets existants ; une migration qui
dépend d'un secret d'environnement échoue le jour où il manque, et elle
échouerait au pire moment — pendant un déploiement. Les fuites existantes
reçoivent donc une empreinte préfixée ``legacy:`` portant leur forme
masquée, et ``services._reconcile_legacy_finding`` les raccroche une par
une, à leur première réobservation, sur exactement le critère que
l'ancienne formule utilisait.
"""

import hashlib

from django.db import migrations, models

# Copie FIGÉE de ``normalizer.ENDPOINT_SCHEMAS[*].identity_fields`` au
# 09/09/2026. Volontairement recopiée et non importée : une migration décrit
# ce qui s'est passé à un instant donné, et importer le module vivant ferait
# silencieusement changer le sens de ce remplissage au premier ajout de champ
# d'identité.
IDENTITY_FIELDS_AU_09_09_2026 = {
    "stealer": ("usr", "src"),
    "combo": ("usr", "src"),
    "creds": ("eml", "src"),
    "sessions": ("user_name", "dom", "cookie_name"),
    "nhi": ("usr", "platform", "src"),
    "darkweb": ("data", "site"),
    "radar": ("data", "src"),
    "docs": ("doc_id", "file_hash"),
    "asm": ("dom", "type", "cname", "ip"),
}

LEGACY_FINGERPRINT_PREFIX = "legacy:"

# Assez grand pour que le remplissage tienne en quelques passes sur les
# volumes réels (un actif de production porte 28 450 fuites), assez petit
# pour ne pas charger toute la table en mémoire d'un coup.
TAILLE_LOT = 2000


def _identity_hash(source_endpoint, raw_data):
    """Rejoue le calcul d'identité sur les données déjà en base.

    ``raw_data`` est la charge du fournisseur DÉJÀ masquée — mais les champs
    de dédoublonnage sont, par construction, des champs non secrets : ils
    traversent le masquage intacts. L'identité est donc reconstituable.

    Sauf dans un cas : ``source_endpoint`` vaut « webhook » quand l'endpoint
    d'origine n'était pas reconnu, et cet endpoint d'origine n'a été stocké
    nulle part. Ces fuites-là gardent une identité vide et ne seront pas
    raccrochées — elles seront recréées une fois, puis porteront la clé
    actuelle. Elles sont rares (endpoint hors schéma connu), et les inventer
    une identité fausse serait pire que de l'admettre.

    Effet de bord assumé : deux fuites existantes qui ne différaient que par
    une date du fournisseur reçoivent désormais la MÊME identité. Elles ne
    sont pas fusionnées — la migration ne supprime rien — et le raccrochage
    n'en retiendra qu'une. L'autre restera telle quelle, doublon déjà présent
    en base. On cesse d'en créer de nouveaux ; on ne réécrit pas le passé.
    """
    identity_fields = IDENTITY_FIELDS_AU_09_09_2026.get(source_endpoint)
    if identity_fields is None:
        return ""
    raw_data = raw_data or {}
    presents = [
        f"{champ}={raw_data[champ]}"
        for champ in identity_fields
        if raw_data.get(champ) not in (None, "")
    ]
    return hashlib.sha256(f"{source_endpoint}|{'|'.join(presents)}".encode()).hexdigest()


def remplir(apps, schema_editor):
    BreachFinding = apps.get_model("threat_intelligence", "BreachFinding")

    lot = []
    for finding in BreachFinding.objects.all().iterator(chunk_size=TAILLE_LOT):
        finding.identity_hash = _identity_hash(finding.source_endpoint, finding.raw_data)
        finding.secret_fingerprint = f"{LEGACY_FINGERPRINT_PREFIX}{finding.secret_masked}"
        # Une fuite jamais revue depuis sa détection a bien été vue ce
        # jour-là : laisser le champ vide dirait « jamais observée », ce qui
        # est faux.
        finding.last_seen_at = finding.detected_at
        lot.append(finding)
        if len(lot) >= TAILLE_LOT:
            BreachFinding.objects.bulk_update(
                lot, ["identity_hash", "secret_fingerprint", "last_seen_at"]
            )
            lot = []
    if lot:
        BreachFinding.objects.bulk_update(
            lot, ["identity_hash", "secret_fingerprint", "last_seen_at"]
        )


def vider(apps, schema_editor):
    """Sens inverse : les trois colonnes disparaissent avec le schéma, il n'y
    a donc rien à défaire. Déclaré explicitement pour que la migration reste
    réversible (``migrate threat_intelligence 0005``) plutôt que de bloquer
    un retour arrière sur une opération irréversible par omission."""


class Migration(migrations.Migration):
    dependencies = [
        ("threat_intelligence", "0005_origine_analyse_exploitant"),
    ]

    operations = [
        migrations.AddField(
            model_name="breachfinding",
            name="last_seen_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="breachfinding",
            name="identity_hash",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="breachfinding",
            name="secret_fingerprint",
            field=models.CharField(blank=True, default="", max_length=71),
            preserve_default=False,
        ),
        migrations.RunPython(remplir, vider),
        migrations.AddIndex(
            model_name="breachfinding",
            index=models.Index(
                fields=["tenant", "identity_hash"],
                name="ti_finding_tenant_identity_idx",
            ),
        ),
    ]

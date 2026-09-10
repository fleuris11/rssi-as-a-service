"""V2-2 — remet en clair les adresses des fuites déjà en base (ADR-027).

Jusqu'ici, seule l'adresse d'un membre du tenant était conservée en clair
(ADR-014 §4) ; toute autre était réduite à une forme **non réversible**
(« j.••••@ex••••.com »). Le RSSI ne pouvait donc pas savoir qui prévenir —
précisément pour les adresses qui comptent le plus : un ancien salarié, une
adresse personnelle utilisée au bureau, un prestataire.

La forme masquée n'est pas réversible, mais **l'adresse n'a jamais été
perdue** : elle vit dans ``raw_data``, la charge du fournisseur déjà masquée.
Les champs d'identifiant (``usr``, ``eml``, ``user_name``) ne sont pas des
secrets, ils traversent donc le masquage intacts. Ce remplissage les y relit.

Aucune donnée n'est ajoutée ni devinée : ce que la migration écrit dans
``identifier_plain`` était déjà en base, dans la colonne d'à côté.

Migration purement additive au sens du schéma (aucune colonne touchée), et
sans effet pour le code de la version précédente : ``identifier_plain`` y
existe déjà et y est lu de la même façon.
"""

from django.db import migrations

# Copie FIGÉE de ``normalizer.ENDPOINT_SCHEMAS[*].identifier_fields`` et du
# repli générique, au 09/09/2026. Recopiée et non importée : une migration
# décrit ce qui s'est passé à un instant donné.
IDENTIFIER_FIELDS_AU_09_09_2026 = {
    "stealer": ("usr",),
    "combo": ("usr",),
    "creds": ("eml",),
    "sessions": ("user_name",),
    "nhi": ("usr",),
}

REPLI_GENERIQUE = (
    "email",
    "eml",
    "usr",
    "user_name",
    "login",
    "username",
    "user",
    "identifier",
)

MAX_IDENTIFIER = 255
TAILLE_LOT = 2000


def _identifiant(source_endpoint, raw_data):
    raw_data = raw_data or {}
    champs = IDENTIFIER_FIELDS_AU_09_09_2026.get(source_endpoint, ()) + REPLI_GENERIQUE
    for champ in champs:
        valeur = raw_data.get(champ)
        if valeur not in (None, ""):
            return str(valeur).strip()[:MAX_IDENTIFIER]
    return ""


def remplir(apps, schema_editor):
    BreachFinding = apps.get_model("threat_intelligence", "BreachFinding")

    lot = []
    # Seules les fuites SANS clair sont touchées : celles d'un membre du
    # tenant en avaient déjà un, et le réécrire ne servirait qu'à risquer de
    # l'abîmer.
    a_traiter = BreachFinding.objects.filter(identifier_plain="").exclude(raw_data={})
    for finding in a_traiter.iterator(chunk_size=TAILLE_LOT):
        identifiant = _identifiant(finding.source_endpoint, finding.raw_data)
        if not identifiant:
            # Les points d'entrée sans notion de compte (radar, dark web,
            # surface d'attaque, documents) n'ont pas d'identifiant à
            # retrouver. Ce n'est pas un échec du remplissage.
            continue
        finding.identifier_plain = identifiant
        lot.append(finding)
        if len(lot) >= TAILLE_LOT:
            BreachFinding.objects.bulk_update(lot, ["identifier_plain"])
            lot = []
    if lot:
        BreachFinding.objects.bulk_update(lot, ["identifier_plain"])


def vider(apps, schema_editor):
    """Sens inverse : on ne remasque pas.

    Revenir en arrière signifierait effacer ``identifier_plain`` — donc
    détruire une donnée que la migration n'a pas créée mais seulement
    recopiée, et que le code d'avant sait lire. Une réversibilité qui détruit
    n'en est pas une ; celle-ci ne fait donc rien, délibérément.
    """


class Migration(migrations.Migration):
    dependencies = [
        ("threat_intelligence", "0007_audit_consultation_adresses"),
    ]

    operations = [
        migrations.RunPython(remplir, vider),
    ]

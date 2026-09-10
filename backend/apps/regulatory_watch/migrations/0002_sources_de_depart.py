"""Installe la liste de sources de depart (V2-7, cadrage).

Les sources vivent en base et non en dur : l'exploitant doit pouvoir en
ajouter une, corriger une adresse ou en desactiver une sans redeploiement.
Cette migration ne fait que POSER le point de depart.

Idempotente et non destructrice : une source deja presente n'est pas
reecrite. Une adresse corrigee depuis la console ne doit pas etre defaite par
un redeploiement.

La liste est FIGEE ici (D5, revue V2-7). Elle importait auparavant
``apps.regulatory_watch.sources``, le module vivant : rejouee un jour sur une
base neuve, la migration aurait installe ce que ce fichier contiendrait
ALORS, et non ce qu'il contenait le 2026-09-10. Une migration doit produire
le meme etat quelle que soit la date a laquelle on la rejoue — c'est tout son
interet. Le module vivant reste la reference pour le code applicatif ; cette
copie ne bouge plus.
"""

from django.db import migrations

#: Etat de ``sources.SOURCES`` au 2026-09-10, adresses et formats verifies
#: contre le reseau ce jour-la. Ne pas modifier : pour changer les sources,
#: on passe par la console, ou par une NOUVELLE migration.
SOURCES_GELEES = [
    {
        "slug": "anssi-publications",
        "name": "Guides, recommandations et publications",
        "publisher": "ANSSI",
        "url": "https://cyber.gouv.fr/nous-connaitre/publications/",
        "feed_url": "",
        "format": "page",
        "expected_frequency": "quelques publications par mois",
        "scope_note": "Guides d'hygiène, recommandations techniques, référentiels. C'est la "
        "source de tête : le référentiel ANSSI embarqué dans le produit en "
        "vient. Ne couvre pas les avis de vulnérabilité, qui relèvent du "
        "CERT-FR et n'ont pas leur place dans une file de suggestions de "
        "référentiel.",
        "is_active": True,
    },
    {
        "slug": "cnil-actualites",
        "name": "Actualités, délibérations et recommandations",
        "publisher": "CNIL",
        "url": "https://www.cnil.fr/fr/actualites",
        "feed_url": "https://www.cnil.fr/fr/rss.xml",
        "format": "rss",
        "expected_frequency": "plusieurs publications par semaine",
        "scope_note": "Autorité de contrôle des données personnelles. Remonte les "
        "recommandations et référentiels sectoriels qui deviennent des "
        "exigences pour nos clients (registre, violations de données, "
        "sous-traitance). Le flux mêle sanctions et doctrine : la "
        "qualification est faite à la lecture, pas à la collecte.",
        "is_active": True,
    },
    {
        "slug": "nist-csrc-drafts",
        "name": "Publications ouvertes à commentaire (drafts)",
        "publisher": "NIST — Computer Security Resource Center",
        "url": "https://csrc.nist.gov/publications/drafts-open-for-comment",
        "feed_url": "https://csrc.nist.gov/CSRC/media/feeds/pubs/drafts-open-for-comment.xml",
        "format": "atom",
        "expected_frequency": "quelques publications par mois",
        "scope_note": "Prend les textes AVANT leur publication définitive : un projet ouvert "
        "à commentaire annonce l'exigence de demain, ce qui laisse le temps de "
        "préparer le référentiel plutôt que de le subir.",
        "is_active": True,
    },
    {
        "slug": "eurlex-cyber",
        "name": "Journal officiel — actes en matière de cybersécurité et de numérique",
        "publisher": "Union européenne — EUR-Lex",
        "url": "https://eur-lex.europa.eu/oj/direct-access.html",
        "feed_url": "",
        "format": "rss",
        "expected_frequency": "variable, plusieurs actes par mois sur ces thèmes",
        "scope_note": "À CONFIGURER : coller l'adresse d'un flux de recherche EUR-Lex "
        "restreint aux thèmes utiles. Le flux non filtré du JO L existe mais "
        "ne sert à rien ici — vérifié le 2026-09-10, 120 actes dont "
        "l'écrasante majorité sans rapport avec la sécurité.",
        "is_active": False,
    },
    {
        "slug": "enisa-publications",
        "name": "Rapports et lignes directrices",
        "publisher": "ENISA — Agence de l'Union européenne pour la cybersécurité",
        "url": "https://www.enisa.europa.eu/publications",
        "feed_url": "",
        "format": "page",
        "expected_frequency": "quelques publications par mois",
        "scope_note": "Lignes directrices européennes, notamment sur la mise en œuvre de NIS "
        "2 et sur les sujets émergents. Utile pour anticiper ce que les "
        "autorités nationales reprendront ensuite.",
        "is_active": True,
    },
]


def installer(apps, schema_editor):
    WatchSource = apps.get_model("regulatory_watch", "WatchSource")
    for spec in SOURCES_GELEES:
        spec = dict(spec)
        slug = spec.pop("slug")
        WatchSource.objects.get_or_create(slug=slug, defaults=spec)


def retirer(apps, schema_editor):
    WatchSource = apps.get_model("regulatory_watch", "WatchSource")
    # Seules les sources de depart, et seulement si elles n'ont rien collecte :
    # une source qui porte des suggestions deja triees par un humain ne se
    # supprime pas au retour arriere d'une migration.
    WatchSource.objects.filter(
        slug__in=[spec["slug"] for spec in SOURCES_GELEES], updates__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("regulatory_watch", "0001_veille_reglementaire"),
    ]

    operations = [migrations.RunPython(installer, retirer)]

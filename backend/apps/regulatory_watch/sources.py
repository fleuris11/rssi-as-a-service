"""Les sources suivies, et **pourquoi celles-là** (V2-7, cadrage, ADR-034 §1).

Une veille utile ne « scanne pas le net ». Elle suit des sources **primaires**
— l'organisme qui publie le texte, pas celui qui le commente. Les sources
secondaires (blogs, agrégateurs, presse spécialisée) sont exclues par
principe : un produit qui vend la rigueur ne peut pas remonter à un client une
exigence qui n'existe pas parce qu'un blog l'a mal comprise.

Chaque entrée porte ce qui a été VÉRIFIÉ, et à quelle date. Les flux annoncés
par un site ne sont pas des flux qui répondent : trois des sources envisagées
ont été écartées ou dégradées après vérification (voir ``EXCLUES`` et les
notes de format).

Cette liste est le point de départ, pas une clôture : la console permet
d'ajouter, de désactiver et de corriger une source sans redéploiement.
"""

from .models import WatchSource

#: Date de la vérification manuelle des adresses et des formats ci-dessous.
VERIFIED_ON = "2026-09-10"

#: Ce que le produit promet, mot pour mot (consigne V2-7 §8). Ni « veille
#: exhaustive », ni « temps réel » : nous suivons des publications officielles
#: et nous signalons ce qui change. C'est déjà beaucoup, et c'est vrai.
#: Un test épingle cette phrase et interdit les deux mots qu'on ne tiendrait
#: pas.
PROMESSE = (
    "Nous suivons les publications officielles des autorités et organismes de "
    "normalisation, et nous vous signalons ce qui change. Cette veille n'est ni "
    "exhaustive ni instantanée : elle couvre les sources listées ci-dessous, au "
    "rythme de leurs publications."
)

SOURCES = [
    {
        "slug": "anssi-publications",
        "name": "Guides, recommandations et publications",
        "publisher": "ANSSI",
        "url": "https://cyber.gouv.fr/nous-connaitre/publications/",
        "feed_url": "",
        # Vérifié le 2026-09-10 : la page ne publie AUCUN flux (ni
        # link rel=alternate, ni lien « flux »), et l'adresse
        # cyber.gouv.fr/publications/feed répond 404. On relève donc
        # l'empreinte de la page : on saura QUE quelque chose a changé, pas
        # QUOI — et la file le dit tel quel plutôt que de le laisser croire.
        "format": WatchSource.Format.PAGE,
        "expected_frequency": "quelques publications par mois",
        "scope_note": (
            "Guides d'hygiène, recommandations techniques, référentiels. C'est la source "
            "de tête : le référentiel ANSSI embarqué dans le produit en vient. Ne couvre "
            "pas les avis de vulnérabilité, qui relèvent du CERT-FR et n'ont pas leur "
            "place dans une file de suggestions de référentiel."
        ),
    },
    {
        "slug": "cnil-actualites",
        "name": "Actualités, délibérations et recommandations",
        "publisher": "CNIL",
        "url": "https://www.cnil.fr/fr/actualites",
        "feed_url": "https://www.cnil.fr/fr/rss.xml",
        # Vérifié le 2026-09-10 : RSS 2.0 valide, 10 éléments, dernier du
        # jour même.
        "format": WatchSource.Format.RSS,
        "expected_frequency": "plusieurs publications par semaine",
        "scope_note": (
            "Autorité de contrôle des données personnelles. Remonte les recommandations "
            "et référentiels sectoriels qui deviennent des exigences pour nos clients "
            "(registre, violations de données, sous-traitance). Le flux mêle sanctions "
            "et doctrine : la qualification est faite à la lecture, pas à la collecte."
        ),
    },
    {
        "slug": "nist-csrc-drafts",
        "name": "Publications ouvertes à commentaire (drafts)",
        "publisher": "NIST — Computer Security Resource Center",
        "url": "https://csrc.nist.gov/publications/drafts-open-for-comment",
        "feed_url": "https://csrc.nist.gov/CSRC/media/feeds/pubs/drafts-open-for-comment.xml",
        # Vérifié le 2026-09-10 : Atom valide, 7 entrées, dont un guide
        # d'application du CSF 2.0. Le NIST CSF est un référentiel importable
        # du produit depuis V2-4 : ses évolutions nous concernent directement.
        "format": WatchSource.Format.ATOM,
        "expected_frequency": "quelques publications par mois",
        "scope_note": (
            "Prend les textes AVANT leur publication définitive : un projet ouvert à "
            "commentaire annonce l'exigence de demain, ce qui laisse le temps de préparer "
            "le référentiel plutôt que de le subir."
        ),
    },
    {
        "slug": "eurlex-cyber",
        "name": "Journal officiel — actes en matière de cybersécurité et de numérique",
        "publisher": "Union européenne — EUR-Lex",
        "url": "https://eur-lex.europa.eu/oj/direct-access.html",
        # Volontairement VIDE à l'installation. Le flux « tous les actes du
        # JO L » a été vérifié le 2026-09-10 : il fonctionne, et il est
        # inutilisable — 120 entrées, essentiellement des décharges
        # budgétaires. Le suivre non filtré noierait la file et ferait
        # abandonner l'écran en une semaine. L'exploitant colle ici l'adresse
        # d'un flux de RECHERCHE ciblée (NIS 2, DORA, règlement sur
        # l'intelligence artificielle, cyber-résilience), construit depuis
        # EUR-Lex. La source est livrée inactive tant qu'elle n'a pas d'URL.
        "feed_url": "",
        "format": WatchSource.Format.RSS,
        "expected_frequency": "variable, plusieurs actes par mois sur ces thèmes",
        "scope_note": (
            "À CONFIGURER : coller l'adresse d'un flux de recherche EUR-Lex restreint aux "
            "thèmes utiles. Le flux non filtré du JO L existe mais ne sert à rien ici — "
            "vérifié le "
            + VERIFIED_ON
            + ", 120 actes dont l'écrasante majorité sans rapport avec la sécurité."
        ),
        "is_active": False,
    },
    {
        "slug": "enisa-publications",
        "name": "Rapports et lignes directrices",
        "publisher": "ENISA — Agence de l'Union européenne pour la cybersécurité",
        "url": "https://www.enisa.europa.eu/publications",
        # Vérifié le 2026-09-10 : les adresses de flux annoncées par le site
        # répondent 404, et la page qui les recense répond 403. On dégrade
        # honnêtement en détection de changement plutôt que d'inscrire une
        # adresse qui ne répond pas.
        "feed_url": "",
        "format": WatchSource.Format.PAGE,
        "expected_frequency": "quelques publications par mois",
        "scope_note": (
            "Lignes directrices européennes, notamment sur la mise en œuvre de NIS 2 et "
            "sur les sujets émergents. Utile pour anticiper ce que les autorités "
            "nationales reprendront ensuite."
        ),
    },
]

#: Écartées, et pourquoi. Une liste de sources sans ses exclusions se relit
#: mal : on ne sait pas si un manque est un oubli ou une décision.
EXCLUES = [
    (
        "CERT-FR (flux d'avis et d'alertes)",
        "Le flux fonctionne (vérifié le "
        + VERIFIED_ON
        + ", RSS 2.0, 40 éléments). Il publie des avis de vulnérabilité — « Multiples "
        "vulnérabilités dans les produits Ivanti » — qui sont opérationnels, pas "
        "normatifs. Aucun ne deviendra jamais une mesure de référentiel, et la file "
        "en serait noyée. La surveillance des vulnérabilités est un autre métier, que "
        "le produit traite ailleurs.",
    ),
    (
        "Blogs, agrégateurs et presse spécialisée",
        "Exclus par principe (consigne V2-7 §2). Le risque de remonter une information "
        "déformée est trop élevé pour un produit dont l'argument est la rigueur — et "
        "une exigence inventée coûte plus cher au client qu'une exigence manquée.",
    ),
    (
        "ISO / IEC (catalogue des normes)",
        "Les textes sont payants et non redistribuables (ADR-029 §5) : nous ne pourrions "
        "ni citer, ni conserver l'extrait source. Une veille qui ne peut pas montrer sa "
        "source ne respecte pas la règle du projet.",
    ),
]


def seed_sources(model=None) -> int:
    """Installe la liste de départ. Idempotent : une source déjà présente
    n'est pas réécrite — l'exploitant a pu corriger une adresse depuis la
    console, et une migration n'a pas à défaire son travail."""
    model = model or WatchSource
    crees = 0
    for spec in SOURCES:
        spec = dict(spec)
        slug = spec.pop("slug")
        _source, cree = model.objects.get_or_create(slug=slug, defaults=spec)
        crees += 1 if cree else 0
    return crees

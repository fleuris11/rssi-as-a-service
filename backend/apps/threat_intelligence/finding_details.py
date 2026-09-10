"""Ce que la source renvoie vraiment, restitué en français (V2-2, ADR-027).

Un inventaire des charges réelles a montré que **42 champs documentés
n'étaient jamais restitués** : le nom du logiciel malveillant, le service sur
lequel l'identifiant était enregistré, le système du poste infecté, le nom du
fichier de collecte, le nombre de listes où un couple circule, la date de
validité d'un cookie volé… Tous atterrissaient dans ``BreachFinding.raw_data``
— stockés, jamais montrés.

Ils ne manquaient pas en base : ils manquaient à l'écran. Ce module ne stocke
donc rien de nouveau, il **lit ``raw_data``** et en tire une liste de champs
présentables. Conséquence directe et voulue : les fuites déjà en base — dont
les 28 450 d'un actif de production — deviennent complètes sans migration ni
nouveau scan.

## Trois règles de construction

**1. Liste blanche, jamais liste noire.** Un champ n'est restitué que s'il
figure explicitement dans ``DETAILS_PAR_ENDPOINT``. Un champ que la source
ajouterait demain n'apparaît pas tout seul. C'est ce qui rend structurelle,
et non déclarative, l'interdiction de servir un lien de téléchargement vers un
document volé (ADR-027, partie C) : ``url_main_post`` et ``url_for_breach``
existent dans la charge, ne sont dans aucune liste, et ne peuvent donc pas
sortir.

**2. Un libellé français, jamais le nom technique.** ``mal`` ne veut rien dire
à un dirigeant ; « Logiciel malveillant identifié » si.

**3. Chaque champ porte ce qu'il implique.** « Raccoon » ne dit rien à qui
n'est pas du métier ; « un logiciel qui recopie les mots de passe enregistrés
dans le navigateur » lui dit quoi craindre et quoi faire. La valeur seule
informe ; la valeur plus l'implication permet de décider.

## Ce qui est délibérément laissé de côté

Certains champs présents dans la charge ne sont **pas** restitués, et c'est un
choix, pas un oubli :

- ``iip``, ``ip``, ``mac`` — l'adresse réseau et l'adresse matérielle du poste
  infecté. Ce sont des données personnelles (elles situent le domicile ou le
  poste d'une personne) pour une valeur d'action nulle : on ne fait rien d'une
  adresse IP domestique. Les afficher élargirait la surface de données
  personnelles au moment même où l'on démasque les adresses email ;
- ``pth``, ``malware_path`` — des chemins de fichiers sur la machine de
  l'attaquant ou de la victime. Techniques, non actionnables ;
- ``atr`` (endpoint ``creds``) — sémantique non confirmée par le fournisseur.
  Inventer un libellé pour un champ qu'on ne comprend pas serait pire que de
  le taire : le dirigeant croirait savoir quelque chose.
"""

from dataclasses import dataclass
from datetime import date, datetime

MOIS_FR = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def _formater_date(valeur) -> str:
    """« 2026-09-04 » -> « 4 septembre 2026 ». Une date ISO est lisible par un
    informaticien ; un dirigeant lit un mois écrit en toutes lettres."""
    if isinstance(valeur, (date, datetime)):
        d = valeur.date() if isinstance(valeur, datetime) else valeur
    else:
        try:
            d = date.fromisoformat(str(valeur)[:10])
        except (ValueError, TypeError):
            return str(valeur)
    return f"{d.day} {MOIS_FR[d.month - 1]} {d.year}"


def _formater_taille(valeur) -> str:
    """Octets -> unité lisible. « 2 411 724 » ne dit rien, « 2,3 Mo » si."""
    try:
        octets = int(valeur)
    except (ValueError, TypeError):
        return str(valeur)
    for seuil, unite in ((1024**3, "Go"), (1024**2, "Mo"), (1024, "ko")):
        if octets >= seuil:
            return f"{octets / seuil:.1f}".replace(".", ",") + f" {unite}"
    return f"{octets} octets"


def _formater_dechiffre(valeur) -> str:
    """``hash`` vaut 0 ou 1 chez la source. Le chiffre nu serait illisible, et
    le sens n'est pas devinable : 1 = le mot de passe circule déjà en clair."""
    return "oui, il circule en clair" if str(valeur) in ("1", "True", "true") else "non, chiffré"


def _formater_texte(valeur) -> str:
    return str(valeur).strip()


# Le fournisseur renvoie un type MIME (« application/pdf »). C'est un nom
# technique, et la règle est qu'aucun n'atteint le client. Les types inconnus
# ne sont donc PAS affichés tels quels : le nom du fichier porte déjà son
# extension, le client ne perd rien d'actionnable.
TYPES_DE_FICHIER = {
    "application/pdf": "Document PDF",
    "application/msword": "Document Word",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Document Word",
    "application/vnd.ms-excel": "Tableur Excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Tableur Excel",
    "application/vnd.ms-powerpoint": "Présentation PowerPoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": (
        "Présentation PowerPoint"
    ),
    "text/csv": "Fichier de données (CSV)",
    "text/plain": "Fichier texte",
    "application/zip": "Archive compressée",
    "application/x-rar-compressed": "Archive compressée",
    "application/json": "Fichier de données",
    "application/sql": "Export de base de données",
}

TYPE_DE_FICHIER_INCONNU = "Type de fichier non identifié"


def _formater_type_de_fichier(valeur) -> str:
    return TYPES_DE_FICHIER.get(str(valeur).strip().lower(), TYPE_DE_FICHIER_INCONNU)


# --- Glossaire des logiciels voleurs ----------------------------------------
#
# Le nom d'un logiciel malveillant est la donnée la plus parlante pour un
# technicien et la plus muette pour un dirigeant. Ce glossaire dit ce que
# chacun fait — donc ce qu'il faut craindre et changer en priorité.
#
# Les familles listées sont les plus répandues dans les journaux de vol
# d'identifiants. La formule de repli n'est pas un aveu d'ignorance : elle
# décrit ce que fait TOUTE cette catégorie de logiciels, ce qui suffit à
# décider de l'action.
GLOSSAIRE_MALVEILLANTS = {
    "raccoon": (
        "un logiciel qui recopie les mots de passe enregistrés dans le navigateur, "
        "ainsi que les cookies de connexion et les fichiers de portefeuilles de "
        "cryptomonnaie."
    ),
    "redline": (
        "un logiciel qui recopie les mots de passe enregistrés dans le navigateur, les "
        "cookies de connexion et les informations de carte bancaire mémorisées."
    ),
    "vidar": (
        "un logiciel qui recopie les mots de passe du navigateur et prend des captures "
        "de l'écran du poste infecté."
    ),
    "lumma": (
        "un logiciel qui recopie les mots de passe du navigateur et les jetons de "
        "connexion, y compris ceux qui permettent d'entrer sans mot de passe."
    ),
    "stealc": (
        "un logiciel qui recopie les mots de passe et les cookies de connexion "
        "enregistrés sur le poste."
    ),
    "meta": (
        "un logiciel qui recopie les mots de passe enregistrés dans le navigateur et "
        "les données de connexion des applications installées."
    ),
    "azorult": (
        "un logiciel qui recopie les mots de passe, l'historique de navigation et les "
        "fichiers de portefeuilles de cryptomonnaie."
    ),
    "rhadamanthys": (
        "un logiciel qui recopie les mots de passe, les cookies de connexion et les "
        "documents du poste infecté."
    ),
}

IMPLICATION_MALVEILLANT_INCONNUE = (
    "un logiciel installé à l'insu de l'utilisateur, qui recopie ce que le poste a "
    "mémorisé : mots de passe du navigateur, cookies de connexion, parfois documents."
)


def implication_malveillant(valeur) -> str:
    """Ce que fait ce logiciel, en français, à partir de son nom.

    La correspondance est faite sur une sous-chaîne : les noms réels arrivent
    sous des formes très variables (« RedLine Stealer », « redline_v2 »,
    « Raccoon v1.7 »), et exiger une égalité stricte ferait retomber sur le
    texte générique presque à chaque fois.
    """
    nom = str(valeur).lower()
    for famille, description in GLOSSAIRE_MALVEILLANTS.items():
        if famille in nom:
            return f"C'est {description}"
    return f"C'est {IMPLICATION_MALVEILLANT_INCONNUE}"


@dataclass(frozen=True)
class DetailField:
    """Un champ de la charge, tel qu'il sera lu par un dirigeant.

    ``implication`` est soit une phrase fixe, soit une fonction de la valeur
    (le seul cas à ce jour : le nom du logiciel malveillant, dont le sens
    dépend de la famille).
    """

    key: str
    label: str
    implication: str | object
    formatter: object = _formater_texte

    def implication_pour(self, valeur) -> str:
        if callable(self.implication):
            return self.implication(valeur)
        return self.implication


_SRC_IDENTIFIANT = DetailField(
    key="src",
    label="Identifiant enregistré sur",
    implication=(
        "C'est le service sur lequel cet identifiant était utilisé. Si le même mot de "
        "passe sert ailleurs, ces autres comptes sont exposés de la même façon."
    ),
)

_MALVEILLANT = DetailField(
    key="mal",
    label="Logiciel malveillant identifié",
    implication=implication_malveillant,
)

_SYSTEME = DetailField(
    key="os",
    label="Poste infecté",
    implication=(
        "Le système du poste depuis lequel les données ont été recopiées. Ce poste doit "
        "être nettoyé avant d'être réutilisé pour des accès sensibles : sinon les "
        "nouveaux mots de passe repartiront de la même façon."
    ),
)

_FICHIER_COLLECTE = DetailField(
    key="fle",
    label="Fichier de collecte",
    implication=(
        "Le fichier dans lequel l'attaquant a regroupé ce qu'il a volé. Deux fuites "
        "portant le même nom de fichier viennent du même vol : c'est ce qui permet de "
        "savoir si un seul poste est en cause, ou plusieurs."
    ),
)

_DATE_DECOUVERTE = DetailField(
    key="fnd",
    label="Détecté le",
    implication=(
        "La date à laquelle la donnée a été repérée en circulation. Elle est "
        "postérieure au vol lui-même, parfois de plusieurs mois."
    ),
    formatter=_formater_date,
)

_DATE_INFECTION = DetailField(
    key="inf",
    label="Poste infecté le",
    implication=(
        "La date de l'infection. Tout mot de passe saisi sur ce poste depuis cette date "
        "doit être considéré comme connu de l'attaquant."
    ),
    formatter=_formater_date,
)

_IDENTIFIANT_MACHINE = DetailField(
    key="hid",
    label="Identifiant du poste",
    implication=(
        "Un repère technique du poste infecté. Plusieurs fuites portant le même repère "
        "viennent d'une seule machine : une seule à traiter, et non plusieurs."
    ),
)


# Liste blanche, par point d'entrée. L'ordre est celui de l'affichage : ce qui
# fait décider en premier, en premier.
DETAILS_PAR_ENDPOINT: dict[str, tuple[DetailField, ...]] = {
    "stealer": (
        _SRC_IDENTIFIANT,
        _MALVEILLANT,
        _SYSTEME,
        DetailField(
            key="nme",
            label="Nom du poste",
            implication=(
                "Le nom que porte l'ordinateur sur le réseau. Il suffit souvent à "
                "retrouver de quelle machine il s'agit dans l'entreprise."
            ),
        ),
        _FICHIER_COLLECTE,
        _IDENTIFIANT_MACHINE,
        DetailField(
            key="bid",
            label="Identifiant de l'infection",
            implication=(
                "Un repère de la campagne d'infection. Utile à votre prestataire pour "
                "rapprocher plusieurs postes touchés en même temps."
            ),
        ),
        _DATE_INFECTION,
        _DATE_DECOUVERTE,
    ),
    "combo": (
        _SRC_IDENTIFIANT,
        _FICHIER_COLLECTE,
        DetailField(
            key="cnt",
            label="Nombre de listes où ce couple circule",
            implication=(
                "Plus ce nombre est élevé, plus le couple identifiant/mot de passe a été "
                "recopié et testé. Il ne s'agit plus d'un risque théorique."
            ),
        ),
        _DATE_DECOUVERTE,
    ),
    "creds": (
        _SRC_IDENTIFIANT,
        DetailField(
            key="hash",
            label="Mot de passe lisible par l'attaquant",
            implication=(
                "Un mot de passe qui circule en clair est utilisable immédiatement, sans "
                "aucun travail préalable. Chiffré, il demande un effort — souvent court."
            ),
            formatter=_formater_dechiffre,
        ),
        _DATE_DECOUVERTE,
    ),
    "sessions": (
        DetailField(
            key="dom",
            label="Service concerné",
            implication=(
                "Le site sur lequel ce jeton de connexion ouvre une session. C'est là "
                "qu'il faut déconnecter toutes les sessions actives."
            ),
        ),
        DetailField(
            key="cookie_name",
            label="Jeton concerné",
            implication=(
                "Le nom du jeton de connexion volé. Votre prestataire s'en sert pour "
                "confirmer de quel type d'accès il s'agit."
            ),
        ),
        DetailField(
            key="expires",
            label="Jeton valable jusqu'au",
            implication=(
                "Tant que cette date n'est pas passée, le jeton ouvre le compte sans mot "
                "de passe ni code de double authentification. Se déconnecter partout "
                "l'invalide immédiatement, sans attendre cette date."
            ),
            formatter=_formater_date,
        ),
        _MALVEILLANT,
        _DATE_INFECTION,
        _DATE_DECOUVERTE,
    ),
    "nhi": (
        DetailField(
            key="platform",
            label="Service concerné",
            implication=(
                "Le service auquel cette clé technique donne accès. C'est là qu'il faut "
                "la révoquer."
            ),
        ),
        DetailField(
            key="source_type",
            label="Trouvée dans",
            implication=(
                "L'endroit où la clé a été retrouvée. Une clé publiée par erreur dans du "
                "code partagé reste lisible même après correction, dans l'historique."
            ),
        ),
        DetailField(
            key="prefix",
            label="Début de la clé",
            implication=(
                "Les premiers caractères de la clé, sans le reste. Ils suffisent à "
                "l'identifier parmi vos clés actives, sans jamais l'exposer."
            ),
        ),
        DetailField(
            key="src",
            label="Origine de la fuite",
            implication=(
                "D'où provient cette clé. Une clé récupérée sur un poste infecté implique "
                "que ce poste soit nettoyé, en plus de la révocation de la clé."
            ),
        ),
        _DATE_DECOUVERTE,
    ),
    "darkweb": (
        DetailField(
            key="name",
            label="Organisation nommée",
            implication=(
                "L'entreprise citée dans la publication. Si c'est la vôtre, elle est "
                "explicitement désignée, et non simplement mentionnée au passage."
            ),
        ),
        DetailField(
            key="data",
            label="Élément cité",
            implication=(
                "La donnée de votre entreprise qui apparaît dans la publication. Elle "
                "indique ce que l'auteur prétend détenir — et donc par où vérifier."
            ),
        ),
        DetailField(
            key="site",
            label="Publié sur",
            implication=(
                "L'espace où la publication a été faite. Les sites de rançongiciel y "
                "annoncent leurs victimes avant de publier les fichiers."
            ),
        ),
        DetailField(
            key="tadesc",
            label="Auteur de la publication",
            implication=(
                "Ce que l'on sait du groupe à l'origine de la publication. Cela aide à "
                "estimer s'il s'agit d'une menace organisée ou d'un opportuniste."
            ),
        ),
        DetailField(
            key="desc",
            label="Description",
            implication=(
                "Le texte de la publication, tel qu'il a été relevé. Sa formulation "
                "dit souvent s'il s'agit d'une revente, d'une revendication ou d'une "
                "simple vantardise."
            ),
        ),
        DetailField(
            key="found",
            label="Repéré le",
            implication=(
                "La date à laquelle la publication a été relevée. Une mention récente "
                "appelle une vérification plus rapide qu'une mention ancienne restée "
                "sans suite."
            ),
            formatter=_formater_date,
        ),
    ),
    "radar": (
        DetailField(
            key="data",
            label="Élément mentionné",
            implication=(
                "L'élément de votre entreprise repéré publiquement. C'est ce qu'un "
                "attaquant peut lire sans rien forcer, et donc son point de départ."
            ),
        ),
        DetailField(
            key="src",
            label="Repéré sur",
            implication=(
                "L'espace public où la mention a été relevée. Un forum spécialisé et "
                "un réseau social grand public n'appellent pas la même attention."
            ),
        ),
        DetailField(
            key="found",
            label="Repéré le",
            implication=(
                "La date à laquelle la mention a été relevée. Plusieurs mentions "
                "rapprochées dans le temps valent mieux qu'une seule, isolée."
            ),
            formatter=_formater_date,
        ),
    ),
    # ADR-027 partie C : les métadonnées, jamais le document. `url_main_post`
    # et `url_for_breach` existent dans la charge et ne figurent volontairement
    # dans aucune liste — rediriger un client vers un fichier volé engagerait
    # sa responsabilité autant que la nôtre.
    "docs": (
        DetailField(
            key="file_name",
            label="Nom du document",
            implication=(
                "Le nom du fichier tel qu'il circule. Il suffit souvent à reconnaître de "
                "quel document interne il s'agit."
            ),
        ),
        DetailField(
            key="content_type",
            label="Type de document",
            implication=(
                "La nature du fichier. Un tableur ou une base exportée contient "
                "généralement bien plus de données personnelles qu'un document isolé."
            ),
            formatter=_formater_type_de_fichier,
        ),
        DetailField(
            key="file_size",
            label="Taille",
            implication=(
                "Un ordre de grandeur de ce qui a fuité. Plusieurs mégaoctets de tableur "
                "représentent des milliers de lignes."
            ),
            formatter=_formater_taille,
        ),
        DetailField(
            key="company_name",
            label="Organisation concernée",
            implication=(
                "L'entreprise à laquelle ce document a été rattaché. Si ce n'est pas "
                "la vôtre, le document peut vous concerner en tant que client ou "
                "fournisseur de celle qui est nommée."
            ),
        ),
        DetailField(
            key="domain_name",
            label="Domaine concerné",
            implication=(
                "Le domaine de votre entreprise retrouvé dans le document. C'est ce qui "
                "établit le lien avec vous."
            ),
        ),
        DetailField(
            key="threat_actor",
            label="Publié par",
            implication=(
                "Le groupe qui a mis le document en circulation. Un groupe de "
                "rançongiciel publie généralement par lots, après un refus de paiement."
            ),
        ),
        DetailField(
            key="leak_date",
            label="Publié le",
            implication=(
                "La date de mise en circulation. Au-delà de 72 heures après votre prise "
                "de connaissance, le délai de notification à la CNIL est dépassé."
            ),
            formatter=_formater_date,
        ),
        DetailField(
            key="extraction_timestamp",
            label="Relevé le",
            implication=(
                "La date à laquelle la surveillance a relevé ce document. C'est celle "
                "à partir de laquelle vous en avez connaissance — donc celle qui fait "
                "courir vos obligations."
            ),
            formatter=_formater_date,
        ),
    ),
    "asm": (
        DetailField(
            key="dom",
            label="Adresse concernée",
            implication=(
                "L'adresse internet inventoriée. Une adresse oubliée, qui ne sert plus "
                "mais reste accessible, est le service le moins susceptible d'être "
                "tenu à jour — donc le plus intéressant pour un attaquant."
            ),
        ),
        DetailField(
            key="cname",
            label="Pointe vers",
            implication=(
                "La destination réelle de cette adresse. Une adresse proche de la vôtre "
                "qui pointe ailleurs est un signe de préparation d'usurpation."
            ),
        ),
        DetailField(
            key="found",
            label="Repéré le",
            implication=(
                "La date à laquelle cet élément a été inventorié. Une apparition "
                "récente signale un changement de votre exposition, pas un état ancien."
            ),
            formatter=_formater_date,
        ),
    ),
}

# Champs de la charge qui ne doivent JAMAIS figurer dans une liste blanche.
# Vérifié par un test : la garde ne vaut que si elle échoue quand on la
# contourne, y compris par inadvertance en ajoutant un champ.
CHAMPS_INTERDITS = (
    "url_main_post",
    "url_for_breach",
    "img",
    "iip",
    "ip",
    "mac",
    "pth",
    "malware_path",
)


def details_for(finding) -> list[dict]:
    """Les champs présentables d'une fuite, dans l'ordre d'affichage.

    Lit ``raw_data`` — donc la charge DÉJÀ masquée (ADR-014) : un secret ne
    peut pas ressortir par ici même si un champ secret se glissait dans une
    liste blanche, puisqu'il n'y figure que sous sa forme masquée.

    Un champ absent ou vide est omis plutôt que rendu vide : « Poste
    infecté : — » n'apprend rien et donne l'impression d'une donnée perdue.
    """
    charge = finding.raw_data or {}
    champs = DETAILS_PAR_ENDPOINT.get(finding.source_endpoint, ())

    sortie = []
    for champ in champs:
        valeur = charge.get(champ.key)
        if valeur in (None, "", "—", []):
            continue
        sortie.append(
            {
                "label": champ.label,
                "value": champ.formatter(valeur),
                "implication": champ.implication_pour(valeur),
            }
        )
    return sortie


def all_detail_fields() -> dict[str, tuple[DetailField, ...]]:
    """Exposé pour les tests de couverture éditoriale."""
    return dict(DETAILS_PAR_ENDPOINT)

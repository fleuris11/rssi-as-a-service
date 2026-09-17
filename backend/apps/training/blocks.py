"""Le contenu d'un écran, en blocs typés — et validé À L'ÉCRITURE.

Pourquoi pas du Markdown, qui existait déjà pour les documents composés
(``ai_assistant/documents``) : parce que le contenu d'un document est *lu*,
alors que le contenu d'un écran de formation sera *découpé*. Dès F2, il faudra
le dire à voix haute phrase par phrase, et y injecter le nom de l'entreprise.
Les deux supposent de savoir où commence un paragraphe et où finit une
légende. Sur du texte libre, cela demande un analyseur ; sur des blocs typés,
c'est une boucle.

La validation est faite **au moment où on écrit** un écran, jamais au moment
où on le lit. Un écran mal formé doit être refusé par celui qui le crée, pas
découvert par un salarié dans le train. Conséquence pratique : une lecture ne
valide rien et ne peut donc pas échouer — le lecteur de cours n'a pas de
chemin d'erreur pour cause de contenu.

Le schéma est documenté dans ``docs/format_blocs_formation.md``. Le studio de
F2 s'y conformera au lieu de le réinventer ; ce module fait foi pour les
valeurs.
"""

PARAGRAPHE = "paragraphe"
TITRE = "titre"
LISTE = "liste"
ENCADRE = "encadre"
IMAGE = "image"
CITATION = "citation"

TYPES = (PARAGRAPHE, TITRE, LISTE, ENCADRE, IMAGE, CITATION)

#: Les tons d'un encadré. Volontairement peu nombreux, et sémantiques : un
#: encadré « attention » n'est pas une couleur, c'est une nature de propos.
#: Une palette libre aurait fait dériver le sens vers la décoration.
TONS_ENCADRE = ("info", "attention", "exemple")

#: Les niveaux de titre autorisés à l'intérieur d'un écran. Le titre de
#: l'écran est déjà un ``h2`` dans la page : un bloc titre ne peut donc être
#: que ``h3`` ou ``h4``, sous peine de casser la hiérarchie des en-têtes — ce
#: qui désoriente un lecteur d'écran, qui navigue par en-têtes (point 13).
NIVEAUX_TITRE = (3, 4)

#: Les images de F1 sont livrées avec l'application, pas téléversées : il n'y
#: a pas de studio, donc pas de dépôt de fichier, donc pas de question de
#: stockage ni d'analyse antivirale à trancher dans ce lot. Le préfixe est
#: vérifié pour que ce choix ne puisse pas être contourné en glissant une URL
#: externe dans un cours — ce qui ferait fuiter, à chaque ouverture d'écran,
#: l'adresse IP de chaque salarié vers un tiers.
PREFIXE_IMAGE = "/formation/"

LONGUEUR_MAX_TEXTE = 4000
LONGUEUR_MAX_COURTE = 300
MAX_ITEMS_LISTE = 20


class BlocInvalide(ValueError):
    """Le contenu proposé ne respecte pas le schéma. Porte la liste complète
    des problèmes : corriger un écran de huit blocs en découvrant les erreurs
    une par une est une perte de temps, et la première erreur n'est pas
    toujours la plus parlante."""

    def __init__(self, problemes):
        self.problemes = list(problemes)
        super().__init__(" ".join(self.problemes))


def _texte(valeur, *, champ, ou, maximum=LONGUEUR_MAX_TEXTE):
    """Une chaîne non vide, bornée. Renvoie la liste des problèmes."""
    if not isinstance(valeur, str):
        return [f"{ou} : « {champ} » doit être du texte."]
    if not valeur.strip():
        return [f"{ou} : « {champ} » ne peut pas être vide."]
    if len(valeur) > maximum:
        return [f"{ou} : « {champ} » dépasse {maximum} caractères."]
    return []


def _valider_bloc(bloc, position):
    ou = f"bloc {position}"
    if not isinstance(bloc, dict):
        return [f"{ou} : un bloc doit être un objet."]

    type_bloc = bloc.get("type")
    if type_bloc not in TYPES:
        connus = ", ".join(TYPES)
        return [f"{ou} : type « {type_bloc} » inconnu. Types acceptés : {connus}."]

    ou = f"bloc {position} ({type_bloc})"
    problemes = []

    if type_bloc in (PARAGRAPHE, ENCADRE, CITATION):
        problemes += _texte(bloc.get("texte"), champ="texte", ou=ou)

    if type_bloc == TITRE:
        problemes += _texte(bloc.get("texte"), champ="texte", ou=ou, maximum=LONGUEUR_MAX_COURTE)
        if bloc.get("niveau") not in NIVEAUX_TITRE:
            attendus = " ou ".join(str(n) for n in NIVEAUX_TITRE)
            problemes.append(
                f"{ou} : « niveau » doit valoir {attendus} — le titre de l'écran occupe "
                "déjà le niveau 2."
            )

    if type_bloc == ENCADRE and bloc.get("ton") not in TONS_ENCADRE:
        tons = ", ".join(TONS_ENCADRE)
        problemes.append(f"{ou} : « ton » doit valoir l'un de : {tons}.")

    if type_bloc == CITATION and "source" in bloc:
        problemes += _texte(bloc["source"], champ="source", ou=ou, maximum=LONGUEUR_MAX_COURTE)

    if type_bloc == LISTE:
        items = bloc.get("items")
        if not isinstance(items, list) or not items:
            problemes.append(f"{ou} : « items » doit être une liste non vide.")
        elif len(items) > MAX_ITEMS_LISTE:
            problemes.append(f"{ou} : une liste dépasse {MAX_ITEMS_LISTE} entrées.")
        else:
            for rang, item in enumerate(items, start=1):
                problemes += _texte(item, champ=f"items[{rang}]", ou=ou)
        if "ordonnee" in bloc and not isinstance(bloc["ordonnee"], bool):
            problemes.append(f"{ou} : « ordonnee » doit être vrai ou faux.")

    if type_bloc == IMAGE:
        source = bloc.get("source")
        if not isinstance(source, str) or not source.strip():
            problemes.append(f"{ou} : « source » est obligatoire.")
        elif not source.startswith(PREFIXE_IMAGE) or ".." in source:
            problemes.append(
                f"{ou} : « source » doit commencer par {PREFIXE_IMAGE} — les images sont "
                "livrées avec l'application, jamais chargées depuis un site tiers."
            )
        # Le texte alternatif est OBLIGATOIRE et vérifié ici, et non
        # recommandé dans une consigne de rédaction : un champ facultatif
        # reste vide. Une image sans alternative rend l'écran inutilisable
        # pour un salarié qui utilise un lecteur d'écran — et un module de
        # formation inaccessible exclut des salariés.
        problemes += _texte(
            bloc.get("alternative"), champ="alternative", ou=ou, maximum=LONGUEUR_MAX_COURTE
        )

    return problemes


def valider(blocs) -> list[dict]:
    """Renvoie les blocs tels qu'ils seront stockés, ou lève ``BlocInvalide``.

    Appelée par ``Screen.save`` : il n'existe aucun chemin d'écriture qui
    l'évite, sans quoi la garantie « ce qui est en base est valide » ne
    tiendrait que tant que tout le monde y pense.
    """
    if not isinstance(blocs, list) or not blocs:
        raise BlocInvalide(["Un écran doit contenir au moins un bloc."])

    problemes = []
    for position, bloc in enumerate(blocs, start=1):
        problemes += _valider_bloc(bloc, position)
    if problemes:
        raise BlocInvalide(problemes)
    return blocs


def texte_brut(blocs) -> str:
    """Le contenu d'un écran, à plat. Sert au décompte de mots de la durée
    indicative, et servira de source à la synthèse vocale de F2."""
    morceaux = []
    for bloc in blocs or []:
        type_bloc = bloc.get("type")
        if type_bloc in (PARAGRAPHE, TITRE, ENCADRE, CITATION):
            morceaux.append(bloc.get("texte", ""))
        elif type_bloc == LISTE:
            morceaux.extend(bloc.get("items", []))
        elif type_bloc == IMAGE:
            morceaux.append(bloc.get("alternative", ""))
    return "\n".join(m for m in morceaux if m)

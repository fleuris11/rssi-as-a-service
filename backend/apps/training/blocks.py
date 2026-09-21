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

import re

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

#: Une variable contextuelle : ``{score_maturite}``.
VARIABLE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

#: La SEULE marque en ligne autorisée (F2).
#:
#: Le format de F1 n'en avait aucune, et c'était délibéré : autoriser des
#: marques rouvre la porte à l'analyseur qu'on cherchait à éviter. Le studio
#: en demande une, et une seule — le gras. On la traite par un découpage en
#: segments, jamais par du HTML : rien de ce qu'écrit un auteur n'atteint le
#: navigateur sous forme de balise.
MARQUE_GRAS = "**"


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


def variables_du_texte(texte: str) -> list[str]:
    """Les variables citées par un texte, dans l'ordre d'apparition."""
    return VARIABLE.findall(texte or "")


def segments(texte: str) -> list[dict]:
    """Découpe un texte en segments ``{"texte": …, "gras": bool}``.

    C'est ce qui remplace le rendu d'une marque par du HTML : le navigateur
    reçoit une liste de morceaux et décide lui-même de mettre les uns en gras.
    Une marque non fermée ne peut pas arriver ici — la validation l'a refusée
    à l'écriture — mais la fonction reste tolérante : elle rend le texte brut
    plutôt que de lever, parce qu'elle sert aussi à la lecture.
    """
    morceaux = (texte or "").split(MARQUE_GRAS)
    if len(morceaux) % 2 == 0:  # marque non fermée : on n'interprète rien
        return [{"texte": texte, "gras": False}]
    return [
        {"texte": morceau, "gras": index % 2 == 1}
        for index, morceau in enumerate(morceaux)
        if morceau
    ]


def texte_sans_marques(texte: str) -> str:
    """Le texte débarrassé de ses marques — ce qu'on donne à lire à voix
    haute, et ce qu'on compte quand on mesure une longueur."""
    return "".join(segment["texte"] for segment in segments(texte))


def _valider_texte_riche(texte, *, champ, ou, cles_connues):
    problemes = []
    if not isinstance(texte, str):
        return problemes

    if texte.count(MARQUE_GRAS) % 2 != 0:
        problemes.append(
            f"{ou} : « {champ} » contient une marque de gras non fermée ({MARQUE_GRAS})."
        )

    for cle in variables_du_texte(texte):
        if cle not in cles_connues:
            connues = ", ".join(sorted(cles_connues)) or "aucune"
            problemes.append(
                f"{ou} : la variable {{{cle}}} n'existe pas. Variables disponibles : {connues}."
            )
    return problemes


def _textes_du_bloc(bloc):
    """Tous les textes d'un bloc, avec le nom de leur champ."""
    trouves = []
    for champ in ("texte", "source", "alternative"):
        if isinstance(bloc.get(champ), str):
            trouves.append((champ, bloc[champ]))
    for rang, item in enumerate(bloc.get("items") or [], start=1):
        if isinstance(item, str):
            trouves.append((f"items[{rang}]", item))
    return trouves


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

    # --- Marques et variables, sur tous les textes du bloc -----------------
    from . import variables as registre_variables

    cles = set(registre_variables.cles_connues())
    textes = _textes_du_bloc(bloc)
    for champ, texte in textes:
        problemes += _valider_texte_riche(texte, champ=champ, ou=ou, cles_connues=cles)

    # --- La formulation de repli, obligatoire dès qu'il y a une variable ---
    #
    # Sans elle, un client sans données verrait un trou, ou pire un « 0 »
    # annoncé sur le ton de l'alerte. Le repli n'est donc pas une option de
    # confort : c'est la seule version du bloc que verront les clients neufs,
    # ceux dont la donnée manque, et ceux dont le chiffre est trop petit pour
    # être dit sans désigner quelqu'un.
    utilisees = [cle for _champ, texte in textes for cle in variables_du_texte(texte)]
    if utilisees:
        repli = bloc.get("repli")
        problemes += _texte(repli, champ="repli", ou=ou)
        if isinstance(repli, str) and variables_du_texte(repli):
            problemes.append(
                f"{ou} : « repli » ne peut pas contenir de variable — c'est précisément le "
                "texte affiché quand les variables ne sont pas disponibles."
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

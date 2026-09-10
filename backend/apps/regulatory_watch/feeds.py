"""Lecture des flux, sans dépendance nouvelle.

RSS 2.0 et Atom sont deux formats XML simples dès qu'on se limite à ce dont on
a besoin : un identifiant stable, un titre, un lien, une date, un résumé.
``xml.etree`` de la bibliothèque standard suffit, et évite d'ajouter
``feedparser`` — cohérent avec la sobriété du projet et avec le fait que nos
sources sont des institutions dont les flux sont bien formés.

Le revers est assumé : un flux malformé lève une erreur au lieu d'être
réparé silencieusement. C'est le bon sens de la panne ici — une source dont le
flux se casse doit être signalée, pas devinée.

**Aucune de ces fonctions n'écrit en base.** Elles transforment des octets en
dictionnaires ; la décision de créer une ligne appartient à ``services.py``.
"""

import hashlib
import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from xml.etree import ElementTree

#: Espaces de noms rencontrés. Atom est toujours qualifié ; RSS ne l'est
#: presque jamais, sauf pour Dublin Core (``dc:date``).
ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/elements/1.1/}"

#: Bornes de sécurité. Un flux n'est pas censé faire dix mégaoctets ; s'il les
#: fait, quelque chose est cassé en amont et on ne veut pas le charger.
#: La borne s'applique aux OCTETS reçus, avant tout décodage.
MAX_FEED_BYTES = 5 * 1024 * 1024
MAX_ITEMS_PER_POLL = 50
MAX_EXCERPT_CHARS = 4000

_BALISES = re.compile(r"<[^>]+>")
_ESPACES = re.compile(r"\s+")


class FeedError(Exception):
    """Flux illisible. Remonte à la source, qui sera marquée en échec."""


@dataclass
class FeedEntry:
    external_id: str
    title: str
    url: str
    published_at: datetime | None
    excerpt: str


def _texte(element) -> str:
    """Le texte d'un élément, débarrassé de son balisage et de ses entités.

    Les résumés de flux contiennent du HTML échappé. On le retire plutôt que
    de le rendre : cet extrait est conservé comme RÉFÉRENCE (consigne V2-7
    §7), il doit rester lisible tel quel dans dix-huit mois, y compris en
    export texte.

    **Deux passes de déséchappement**, et c'est délibéré. Le flux de la CNIL
    publie des entités doublement échappées (« &amp;amp;nbsp; ») : une seule
    passe laissait « &amp;nbsp; » en clair dans l'extrait conservé. Deux
    passes suffisent à tous les flux observés, et on s'arrête là — en
    déséchapper indéfiniment finirait par transformer du texte légitime.
    """
    if element is None:
        return ""
    brut = "".join(element.itertext())
    sans_balises = _BALISES.sub(" ", brut)
    for _ in range(2):
        sans_balises = html.unescape(sans_balises)
    # L'espace insécable des entités déséchappées se lit mal en export texte.
    sans_balises = sans_balises.replace("\u00a0", " ")
    return _ESPACES.sub(" ", sans_balises).strip()[:MAX_EXCERPT_CHARS]


def _date(valeur: str) -> datetime | None:
    """Les deux formats de date des flux, plus les variantes courantes.

    Une date illisible ne fait pas échouer l'entrée : elle vaut ``None``, et
    la file affiche la date de détection. Perdre une publication parce que sa
    date est mal formée serait le pire des échanges.
    """
    valeur = (valeur or "").strip()
    if not valeur:
        return None

    # Atom : ISO 8601. Python n'accepte le « Z » qu'à partir de 3.11 selon
    # les formes, on le normalise.
    try:
        return datetime.fromisoformat(valeur.replace("Z", "+00:00"))
    except ValueError:
        pass

    # RSS : RFC 822/2822 (« Wed, 09 Sep 2026 14:00:00 +0200 »).
    from email.utils import parsedate_to_datetime

    try:
        date = parsedate_to_datetime(valeur)
    except (TypeError, ValueError):
        return None
    if date is not None and date.tzinfo is None:
        date = date.replace(tzinfo=UTC)
    return date


def fingerprint(contenu: str) -> str:
    return hashlib.sha256(contenu.encode("utf-8", errors="replace")).hexdigest()


def _identifiant(candidat: str, *, titre: str, lien: str) -> str:
    """L'identifiant stable d'une entrée.

    Le ``guid``/``id`` de la source quand elle en fournit un — c'est lui qui
    empêche de re-signaler la même publication à chaque passage. À défaut,
    l'empreinte du couple titre + lien : moins solide (un titre corrigé
    produit un doublon), mais préférable à un identifiant tiré de la date, qui
    en produirait un à chaque republication.
    """
    candidat = (candidat or "").strip()
    if candidat:
        return candidat[:200]
    return fingerprint(f"{titre}\n{lien}")


def parse_rss(payload: bytes) -> list[FeedEntry]:
    try:
        racine = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise FeedError(f"XML illisible : {exc}") from exc

    entrees = []
    for item in racine.iter("item"):
        titre = _texte(item.find("title"))
        lien = (item.findtext("link") or "").strip()
        if not titre and not lien:
            continue
        entrees.append(
            FeedEntry(
                external_id=_identifiant(item.findtext("guid"), titre=titre, lien=lien),
                title=titre[:500],
                url=lien[:1000],
                published_at=_date(item.findtext("pubDate") or item.findtext(f"{DC}date") or ""),
                excerpt=_texte(item.find("description")),
            )
        )
    return entrees[:MAX_ITEMS_PER_POLL]


def parse_atom(payload: bytes) -> list[FeedEntry]:
    try:
        racine = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise FeedError(f"XML illisible : {exc}") from exc

    entrees = []
    for entree in racine.iter(f"{ATOM}entry"):
        titre = _texte(entree.find(f"{ATOM}title"))
        lien = ""
        for balise in entree.findall(f"{ATOM}link"):
            relation = balise.get("rel", "alternate")
            if relation == "alternate" or not lien:
                lien = balise.get("href", "")
            if relation == "alternate":
                break
        if not titre and not lien:
            continue
        publie = entree.findtext(f"{ATOM}published") or entree.findtext(f"{ATOM}updated") or ""
        entrees.append(
            FeedEntry(
                external_id=_identifiant(entree.findtext(f"{ATOM}id"), titre=titre, lien=lien),
                title=titre[:500],
                url=lien[:1000],
                published_at=_date(publie),
                excerpt=_texte(entree.find(f"{ATOM}summary"))
                or _texte(entree.find(f"{ATOM}content")),
            )
        )
    return entrees[:MAX_ITEMS_PER_POLL]


def parse(payload: bytes, *, fmt: str) -> list[FeedEntry]:
    """Analyse les OCTETS du flux, jamais une chaîne déjà décodée.

    Le flux Atom du NIST porte une marque d'ordre des octets (BOM) et ne
    déclare pas son encodage dans l'en-tête HTTP : ``requests`` devine alors
    ISO-8859-1, et le texte décodé ne se parse plus (« not well-formed,
    line 1, column 1 »). En partant des octets, ElementTree honore la
    déclaration ``<?xml encoding="utf-8"?>`` et absorbe le BOM.

    Défaut trouvé en interrogeant le vrai flux, pas en écrivant un test.
    """
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    if fmt == "atom":
        return parse_atom(payload)
    return parse_rss(payload)


def page_signature(contenu_html: str) -> tuple[str, str]:
    """Empreinte d'une page sans flux, et l'extrait qu'on en conserve.

    On ignore le balisage et on normalise les espaces : sans cela, un
    identifiant de session, un compteur de visites ou un espace en trop
    feraient « changer » la page à chaque passage, et la file se remplirait de
    fausses nouveautés jusqu'à ce que plus personne ne la lise.

    Ce que cette méthode ne sait PAS faire : dire ce qui a changé. La file
    l'annonce telle quelle — « cette page a changé », avec le lien — plutôt
    que de laisser croire à une publication identifiée.
    """
    texte = _ESPACES.sub(" ", _BALISES.sub(" ", contenu_html)).strip()
    return fingerprint(texte), texte[:MAX_EXCERPT_CHARS]

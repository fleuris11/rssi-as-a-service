"""Interface publique de la veille réglementaire (V2-7, ADR-034).

La règle que ce module fait respecter, et qu'un test épingle : **la collecte
n'écrit jamais dans ``assessments``**. Elle crée des ``WatchUpdate``, c'est
tout. Le seul chemin qui ajoute une mesure à un référentiel est
``integrate_as_measure``, qui exige un relecteur nommé, un référentiel, un
domaine et un contenu saisi à la main — autrement dit une décision humaine,
pas une conséquence de la collecte.
"""

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.assessments import services as assessments_services
from apps.monitoring.checks.http_client import CheckNetworkError, safe_get  # noqa: F401
from apps.monitoring.checks.ssrf import SSRFError

from . import feeds
from .models import WatchSource, WatchUpdate
from .sources import PROMESSE, seed_sources  # noqa: F401 - ré-exports d'interface

logger = logging.getLogger(__name__)

#: Au-delà, la source est signalée comme cassée dans la console. Trois
#: passages hebdomadaires manqués, c'est trois semaines de silence : assez
#: pour qu'on veuille le savoir, pas assez pour crier au premier incident
#: réseau.
FAILURE_THRESHOLD = 3


class WatchError(Exception):
    """Refus métier de la veille."""


class ReviewRequiredError(WatchError):
    """Une suggestion ne devient une mesure que par une décision humaine."""


#: Sentinelle : distingue « le champ n'a pas été fourni » de « le champ a été
#: vidé explicitement ». ``None`` ne peut pas jouer ce rôle, puisque c'est
#: précisément la valeur qui signifie « plus de référentiel rattaché ».
#:
#: Sans cette distinction, re-trier une suggestion sans re-préciser son
#: référentiel effaçait le rattachement en silence (défaut D3, revue V2-7).
NON_FOURNI = object()


# --- Sources ----------------------------------------------------------------


def list_sources(*, include_inactive: bool = True):
    queryset = WatchSource.objects.all()
    if not include_inactive:
        queryset = queryset.filter(is_active=True)
    return queryset


def get_source(*, slug=None, source_id=None):
    if slug is not None:
        return WatchSource.objects.filter(slug=slug).first()
    return WatchSource.objects.filter(id=source_id).first()


def sources_health() -> dict:
    """Ce que la console doit savoir avant de faire confiance à la file.

    Une source qui échoue en silence est pire qu'une source absente : on croit
    surveiller. Le compteur d'échecs est donc remonté aussi visiblement que
    les suggestions elles-mêmes.
    """
    sources = list(WatchSource.objects.all())
    return {
        "total": len(sources),
        "active": sum(1 for source in sources if source.is_active),
        "failing": [
            {
                "slug": source.slug,
                "name": str(source),
                "consecutive_failures": source.consecutive_failures,
                "last_error": source.last_error,
                "last_success_at": source.last_success_at,
            }
            for source in sources
            if source.consecutive_failures >= FAILURE_THRESHOLD
        ],
        "unconfigured": [
            {"slug": source.slug, "name": str(source)}
            for source in sources
            # Une source à flux sans adresse de flux n'est pas cassée : elle
            # n'a jamais été configurée. La distinction évite de la compter
            # comme une panne pendant des mois.
            if source.format != WatchSource.Format.PAGE and not source.feed_url
        ],
    }


# --- Collecte ---------------------------------------------------------------


def _record_success(source: WatchSource, *, fingerprint: str = "") -> None:
    now = timezone.now()
    source.last_polled_at = now
    source.last_success_at = now
    source.last_error = ""
    source.consecutive_failures = 0
    champs = ["last_polled_at", "last_success_at", "last_error", "consecutive_failures"]
    if fingerprint:
        source.content_fingerprint = fingerprint
        champs.append("content_fingerprint")
    source.save(update_fields=champs)


def _record_failure(source: WatchSource, message: str) -> None:
    source.last_polled_at = timezone.now()
    # Message BORNÉ et sans pile : cette chaîne s'affiche dans la console.
    source.last_error = message[:300]
    source.consecutive_failures += 1
    source.save(update_fields=["last_polled_at", "last_error", "consecutive_failures"])


def _create_update(source: WatchSource, entry: feeds.FeedEntry) -> WatchUpdate | None:
    """Crée la suggestion si elle est nouvelle. Renvoie ``None`` si la
    publication était déjà connue — c'est le cas le plus fréquent, chaque
    passage revoyant l'essentiel du flux précédent."""
    try:
        with transaction.atomic():
            return WatchUpdate.objects.create(
                source=source,
                external_id=entry.external_id,
                title=entry.title,
                url=entry.url,
                published_at=entry.published_at,
                source_excerpt=entry.excerpt,
            )
    except IntegrityError:
        # La contrainte d'unicité a tranché : déjà signalée. On ne touche à
        # RIEN de la ligne existante — son statut appartient à l'exploitant
        # qui l'a peut-être déjà écartée, et une republication ne doit pas la
        # remettre dans la file.
        return None


def poll_source(source: WatchSource) -> dict:
    """Interroge une source et enregistre les nouveautés.

    Passe par ``safe_get`` : la même protection SSRF que les contrôles de
    surveillance (CLAUDE.md), validée à chaque saut de redirection. Les
    sources sont saisies en base par un administrateur plateforme — c'est
    exactement le genre de champ qui, sans garde, permettrait d'atteindre un
    service interne depuis notre propre serveur.
    """
    cible = source.feed_url or source.url
    if source.format != WatchSource.Format.PAGE and not source.feed_url:
        raise WatchError("Aucune adresse de flux configurée pour cette source.")

    try:
        response = safe_get(cible, timeout=15)
    except (SSRFError, CheckNetworkError) as exc:
        _record_failure(source, str(exc))
        raise WatchError(str(exc)) from exc

    if response.status_code >= 400:
        _record_failure(source, f"Réponse HTTP {response.status_code}")
        raise WatchError(f"Réponse HTTP {response.status_code}")

    # Les OCTETS, pas le texte décodé : l'en-tête HTTP d'une source peut
    # mentir sur l'encodage (le flux du NIST le fait), et le parseur XML sait
    # lire la déclaration du document.
    octets = response.content[: feeds.MAX_FEED_BYTES]

    if source.format == WatchSource.Format.PAGE:
        # Pour une page, il n'y a pas de déclaration XML à honorer : on
        # décode au mieux, en tolérant les octets invalides plutôt que
        # d'échouer sur une page par ailleurs lisible.
        empreinte, extrait = feeds.page_signature(
            octets.decode(response.encoding or "utf-8", errors="replace")
        )
        if source.content_fingerprint == empreinte:
            _record_success(source)
            return {"created": 0, "seen": 0, "changed": False}
        premiere = not source.content_fingerprint
        _record_success(source, fingerprint=empreinte)
        if premiere:
            # Premier passage : on relève l'empreinte SANS créer de
            # suggestion. Signaler « cette page a changé » alors qu'on ne l'a
            # jamais lue serait faux, et remplirait la file au déploiement.
            return {"created": 0, "seen": 0, "changed": False}
        cree = _create_update(
            source,
            feeds.FeedEntry(
                external_id=empreinte,
                title=f"Mise à jour de la page « {source.name} »",
                url=source.url,
                published_at=timezone.now(),
                excerpt=extrait,
            ),
        )
        return {"created": 1 if cree else 0, "seen": 1, "changed": True}

    try:
        entrees = feeds.parse(octets, fmt=source.format)
    except feeds.FeedError as exc:
        _record_failure(source, str(exc))
        raise WatchError(str(exc)) from exc

    crees = sum(1 for entree in entrees if _create_update(source, entree) is not None)
    _record_success(source)
    return {"created": crees, "seen": len(entrees), "changed": bool(crees)}


def poll_all_sources() -> dict:
    """Le passage périodique. Une source en échec ne fait pas tomber les
    autres — même règle que les analyses d'actifs (leçon du 06/09/2026)."""
    rapport = {"sources": 0, "created": 0, "failed": []}
    for source in list_sources(include_inactive=False):
        rapport["sources"] += 1
        try:
            resultat = poll_source(source)
            rapport["created"] += resultat["created"]
        except WatchError as exc:
            rapport["failed"].append(source.slug)
            logger.warning("Veille : source %s en échec (%s)", source.slug, exc)
        except Exception:  # noqa: BLE001 - une source ne fait pas tomber le lot
            rapport["failed"].append(source.slug)
            logger.exception("Veille : source %s en échec inattendu", source.slug)
    return rapport


# --- File de suggestions ----------------------------------------------------


def list_updates(*, status=None, source=None, limit=200):
    queryset = WatchUpdate.objects.select_related("source", "target_referential", "reviewed_by")
    if status:
        queryset = queryset.filter(status=status)
    if source is not None:
        queryset = queryset.filter(source=source)
    return queryset[:limit]


def get_update(update_id):
    return WatchUpdate.objects.filter(id=update_id).select_related("source").first()


def queue_summary() -> dict:
    return {
        "new": WatchUpdate.objects.filter(status=WatchUpdate.Status.NEW).count(),
        "kept": WatchUpdate.objects.filter(status=WatchUpdate.Status.KEPT).count(),
        "integrated": WatchUpdate.objects.filter(status=WatchUpdate.Status.INTEGRATED).count(),
        "promise": PROMESSE,
    }


def review_update(
    update: WatchUpdate,
    *,
    status: str,
    reviewer,
    kind: str = "",
    note: str = "",
    target_referential=NON_FOURNI,
) -> WatchUpdate:
    """Enregistre la décision d'un humain sur une suggestion.

    ``reviewer`` est obligatoire : une suggestion qui change d'état sans que
    l'on sache qui l'a lue n'est pas une décision, c'est un effet de bord.

    Ne crée aucune mesure. Retenir une publication dit « ceci nous concerne » ;
    en tirer une exigence est un second geste, volontairement séparé.

    ``target_referential`` est laissé tel quel s'il n'est pas fourni. Passer
    ``None`` explicitement détache la suggestion de son référentiel.
    """
    if reviewer is None:
        raise ReviewRequiredError("Une décision de veille doit être attribuée à quelqu'un.")
    if update.status == WatchUpdate.Status.INTEGRATED:
        # « Intégrée » est un état TERMINAL (D2, revue V2-7). La garde
        # existait dans un seul sens — on ne pouvait pas POSER ce statut,
        # mais rien n'empêchait de le RETIRER. Une suggestion repassée en
        # « écartée » laissait la mesure dans le référentiel et le lien
        # `integrated_measures` en place : la traçabilité se contredisait.
        #
        # Il n'y a volontairement PAS de mécanisme de dé-intégration ici. Si
        # l'exploitant s'est trompé, il retire la mesure du référentiel —
        # geste distinct, explicite et tracé, qui ne se déguise pas en
        # changement de statut d'une suggestion.
        raise WatchError(
            "Cette publication a déjà donné lieu à une mesure : son statut n'est plus "
            "modifiable. Pour revenir en arrière, retirez la mesure du référentiel."
        )
    if status not in WatchUpdate.Status.values or status == WatchUpdate.Status.INTEGRATED:
        # « Intégrée » n'est pas une décision qu'on pose : c'est la
        # conséquence d'une intégration réelle (integrate_as_measure).
        raise WatchError("Décision inconnue.")

    update.status = status
    update.reviewed_by = reviewer
    update.reviewed_at = timezone.now()
    if kind:
        update.kind = kind
    if note:
        update.review_note = note

    champs = ["status", "reviewed_by", "reviewed_at", "kind", "review_note"]
    if target_referential is not NON_FOURNI:
        # Fourni — y compris ``None``, qui détache volontairement.
        update.target_referential = target_referential
        champs.append("target_referential")

    update.save(update_fields=champs)
    return update


def integrate_as_measure(
    update: WatchUpdate,
    *,
    reviewer,
    referential,
    domain_code: str,
    code: str,
    official_title: str,
    plain_language: str,
    level: str = "",
    weight: float = 1.0,
    effort: str = "medium",
    impact: str = "medium",
):
    """Le SEUL chemin par lequel la veille ajoute une mesure à un référentiel.

    Quatre conditions, toutes explicites :

    1. un relecteur nommé — c'est lui qui engage, pas la collecte ;
    2. un référentiel cible, choisi ;
    3. un domaine existant de ce référentiel ;
    4. un contenu **saisi** : ni le titre ni l'énoncé ne sont repris
       automatiquement de la publication. Une exigence rédigée par copie d'un
       titre de communiqué serait illisible pour un dirigeant, et fausserait
       le score.

    La mesure créée porte sa source (``source_url``, ``source_reference``) :
    on ne livre pas ce qu'on ne peut pas sourcer.
    """
    if reviewer is None:
        raise ReviewRequiredError(
            "L'ajout d'une mesure depuis la veille doit être attribué à quelqu'un."
        )
    if referential is None:
        raise WatchError("Choisissez le référentiel auquel rattacher cette mesure.")
    if not (official_title or "").strip() or not (plain_language or "").strip():
        raise WatchError(
            "L'intitulé officiel et l'énoncé en langage clair sont obligatoires : une "
            "mesure recopiée d'un titre de publication ne veut rien dire pour un dirigeant."
        )

    if update.status == WatchUpdate.Status.INTEGRATED:
        # État terminal (D2) : une seconde intégration créerait une deuxième
        # mesure pour la même publication, sans que rien ne le signale.
        raise WatchError(
            "Cette publication a déjà donné lieu à une mesure. Pour en ajouter une "
            "autre, partez du référentiel plutôt que de la file de veille."
        )

    reference = f"{update.source.publisher} — {update.title}"
    if update.published_at:
        reference += f" ({update.published_at:%d/%m/%Y})"

    # Tout ou rien (D4, revue V2-7). C'est le SEUL chemin par lequel la veille
    # écrit dans le cœur métier : une erreur entre la création de la mesure et
    # le marquage de la suggestion laisserait une mesure orpheline dans un
    # référentiel — présente pour les clients qui répondent au questionnaire,
    # mais que plus aucune suggestion ne revendique.
    with transaction.atomic():
        mesure = assessments_services.add_measure(
            referential=referential,
            domain_code=domain_code,
            code=code,
            official_title=official_title,
            plain_language=plain_language,
            level=level,
            weight=weight,
            effort=effort,
            impact=impact,
            source_url=update.url,
            source_reference=reference[:300],
        )

        update.integrated_measures.add(mesure)
        update.status = WatchUpdate.Status.INTEGRATED
        update.target_referential = referential
        update.reviewed_by = reviewer
        update.reviewed_at = timezone.now()
        update.save(update_fields=["status", "target_referential", "reviewed_by", "reviewed_at"])
    return mesure


# --- Résumé par IA (facultatif) ---------------------------------------------


def summarize_update(update: WatchUpdate, *, reviewer) -> WatchUpdate:
    """Résume une publication avec l'IA. **Elle résume, elle ne conclut pas.**

    Déclenché à la main, jamais à la collecte : on ne paie pas un résumé pour
    une publication que personne n'ouvrira (sobriété). Le texte source reste
    la référence et n'est jamais remplacé — le résumé vient à côté, daté et
    identifié comme produit par une machine.
    """
    from apps.ai_assistant import services as ai_services

    if reviewer is None:
        raise ReviewRequiredError("Le résumé doit être demandé par quelqu'un.")
    if not update.source_excerpt.strip():
        raise WatchError("Aucun texte source à résumer pour cette publication.")

    texte, usage = ai_services.summarize_public_document(
        title=update.title,
        publisher=update.source.publisher,
        excerpt=update.source_excerpt,
    )
    update.ai_summary = texte
    update.ai_summary_model = usage["model"]
    update.ai_summary_at = timezone.now()
    update.ai_tokens_input = usage["tokens_input"]
    update.ai_tokens_output = usage["tokens_output"]
    update.save(
        update_fields=[
            "ai_summary",
            "ai_summary_model",
            "ai_summary_at",
            "ai_tokens_input",
            "ai_tokens_output",
        ]
    )
    return update


# --- Ce que le CLIENT voit (B5.18) ------------------------------------------

#: Ce qu'on montre au client : ce qui a ete JUGE pertinent, et rien d'autre.
#: Les suggestions encore a trier sont un travail en cours ; les montrer
#: reviendrait a lui faire porter nos doutes, et a annoncer des exigences qui
#: n'en sont peut-etre pas.
STATUTS_PUBLICS = (WatchUpdate.Status.KEPT, WatchUpdate.Status.INTEGRATED)


def public_feed(*, limit: int = 20) -> dict:
    """La veille telle qu'un client la lit.

    **Lecture seule, et volontairement partielle.** Le client voit ce qui a
    ete retenu ou integre — avec sa source officielle et sa date — jamais la
    file de tri, jamais l'etat des sources, jamais le fonctionnement interne.

    Ce n'est pas de la retenue d'information : une suggestion non triee n'est
    pas une information, c'est une hypothese. La promesse servie avec le flux
    dit d'ailleurs ce que cette veille n'est pas.
    """
    publications = (
        WatchUpdate.objects.filter(status__in=STATUTS_PUBLICS)
        .select_related("source", "target_referential")
        .order_by("-published_at", "-detected_at")[:limit]
    )
    return {
        "promise": PROMESSE,
        "results": [
            {
                "id": publication.id,
                "title": publication.title,
                "url": publication.url,
                "publisher": publication.source.publisher,
                "published_at": publication.published_at,
                "kind": publication.kind,
                "kind_label": publication.get_kind_display(),
                # Le referentiel concerne quand il y en a un : c'est ce qui
                # relie une publication a ce que le client evalue.
                "referential": (
                    publication.target_referential.name
                    if publication.target_referential_id
                    else None
                ),
                # « Integree » veut dire qu'une exigence en est sortie. Le
                # client a le droit de savoir laquelle le concerne.
                "integrated": publication.status == WatchUpdate.Status.INTEGRATED,
            }
            for publication in publications
        ],
    }

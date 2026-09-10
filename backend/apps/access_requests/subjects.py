"""Ce qu'un client peut demander — le registre, déclaré en code.

Même partage que ``billing/features.py`` et pour la même raison : le code seul
sait ce qui existe réellement. Un ``subject_type`` inventé côté client ne
correspondrait à aucune entrée ici, et la demande est refusée à la saisie
plutôt que de créer une ligne que personne ne saurait traiter.

Chaque sujet déclare trois choses :

- ``describe`` : le libellé du sujet demandé, figé dans la demande ;
- ``is_held`` : le client l'a-t-il déjà ? (on refuse de demander ce qu'on a) ;
- ``grant`` : ce qu'accorder veut dire. ``None`` = rien d'automatique, la
  console prévient l'exploitant qu'il reste un geste à faire. C'est le cas des
  offres : changer l'abonnement d'un client est un acte commercial, pas la
  conséquence silencieuse d'un clic sur « accorder ».

Les imports d'autres apps sont faits DANS les fonctions : ce module est chargé
au démarrage par les sérialiseurs, et un import de haut niveau vers
``assessments`` ou ``billing`` créerait une dépendance circulaire au premier
sujet qui viendra d'une app qui, elle, dépend des demandes.
"""

from collections.abc import Callable
from dataclasses import dataclass

REFERENTIAL = "referential"
FEATURE = "feature"


@dataclass(frozen=True)
class Subject:
    key: str
    label: str
    describe: Callable[[str], str | None]
    is_held: Callable[[object, str], bool]
    grant: Callable[[object, str, object], None] | None


def _describe_referential(subject_key: str) -> str | None:
    from apps.assessments import services as assessments_services

    referential = assessments_services.get_referential(slug=subject_key)
    return referential.name if referential else None


def _referential_is_held(tenant, subject_key: str) -> bool:
    from apps.assessments import services as assessments_services

    referential = assessments_services.get_referential(slug=subject_key)
    return referential is not None and assessments_services.is_granted(tenant, referential)


def _grant_referential(tenant, subject_key: str, actor) -> None:
    from apps.assessments import services as assessments_services

    referential = assessments_services.get_referential(slug=subject_key)
    if referential is None:
        return
    assessments_services.assign_referential(
        tenant=tenant,
        referential=referential,
        granted_by=actor,
        note="Attribué en réponse à une demande du client.",
    )


def _describe_feature(subject_key: str) -> str | None:
    from apps.billing import features

    feature = features.get(subject_key)
    return feature.label if feature else None


def _feature_is_held(tenant, subject_key: str) -> bool:
    from apps.billing import entitlements

    return entitlements.has_feature(tenant, subject_key)


REGISTRY: dict[str, Subject] = {
    subject.key: subject
    for subject in [
        Subject(
            key=REFERENTIAL,
            label="Référentiel",
            describe=_describe_referential,
            is_held=_referential_is_held,
            grant=_grant_referential,
        ),
        Subject(
            key=FEATURE,
            label="Fonctionnalité",
            describe=_describe_feature,
            is_held=_feature_is_held,
            # Volontairement None : accorder une fonctionnalité, c'est changer
            # l'offre du client. Cela se fait sur la fiche d'abonnement, avec
            # les conséquences de facturation qui vont avec.
            grant=None,
        ),
    ]
}


def get(subject_type: str) -> Subject | None:
    return REGISTRY.get(subject_type)


def all_keys() -> list[str]:
    return list(REGISTRY)

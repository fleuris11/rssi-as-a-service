"""Traduction HTTP des refus d'offre — point unique (phase 12).

La **règle métier** vit dans ``entitlements.ensure_feature`` et nulle part
ailleurs. Ce module ne décide rien : il traduit un ``EntitlementError`` en
réponse HTTP, une fois, pour tous les appelants.

Pourquoi un module plutôt que le ``try/except`` recopié dans chaque vue : les
cinq gardes posées en phase 12 s'ajoutent à trois gardes existantes, soit huit
endroits qui devraient répéter le même code de statut, la même forme de
charge utile et le même nom de champ. Une seule de ces copies qui dérive, et
le frontend affiche un refus qu'il ne sait pas interpréter.

**402 Payment Required, jamais 403.** Le distinguo est repris d'ADR-019 :
403 dit « vous n'avez pas le droit », ce qui est faux — l'appelant a
parfaitement le droit de demander, c'est son offre qui ne comprend pas la
fonctionnalité. La nuance porte tout le message commercial : un refus qui
nomme l'offre à prendre est un argument de vente, un 403 est une porte close.

La forme de la charge utile est **identique** à celle des trois gardes
existantes (``{"detail": ..., "required_plan": ...}``) : le frontend n'a rien
à apprendre de nouveau. Ces trois-là n'ont pas été réécrites pour passer par
ici — leurs tests épinglent leur forme actuelle, et une réécriture sans
nécessité pendant la pose de nouvelles gardes mélangerait deux changements.
"""

from rest_framework import status
from rest_framework.exceptions import APIException

from . import entitlements


class FeatureRequired(APIException):
    """Refus commercial, rendu par DRF en 402 avec l'offre qui débloque.

    Une exception plutôt qu'un ``Response`` retourné : elle traverse les
    sérialiseurs et les fonctions de service, qui ne peuvent pas retourner de
    réponse HTTP. Les gardes de phase 12 s'appliquent aussi bien dans une vue
    que dans un sérialiseur — il fallait un mécanisme qui fonctionne aux deux
    endroits.
    """

    status_code = status.HTTP_402_PAYMENT_REQUIRED

    def __init__(self, error: entitlements.EntitlementError):
        # `detail` sous forme de dict : DRF le rend tel quel en corps de
        # réponse, ce qui reproduit exactement la forme des gardes existantes.
        super().__init__(
            detail={
                "detail": error.message,
                "required_plan": error.required_plan,
                "feature": error.feature_key,
            }
        )


def ensure_feature(tenant, feature_key: str) -> None:
    """Refuse en 402 si l'offre du tenant n'inclut pas la fonctionnalité.

    À appeler sur les chemins qui **produisent** quelque chose, jamais sur un
    chemin de lecture : un client qui perd une fonctionnalité conserve l'accès
    en lecture à ce qu'il a déjà produit (ADR-019, ADR-026).
    """
    try:
        entitlements.ensure_feature(tenant, feature_key)
    except entitlements.EntitlementError as exc:
        raise FeatureRequired(exc) from exc


def has_feature(tenant, feature_key: str) -> bool:
    """Pour les chemins de lecture qui **omettent** une partie du contenu au
    lieu de refuser l'appel entier — la corrélation de réutilisation, par
    exemple, est une analyse ajoutée à un flux qui doit rester servi."""
    return entitlements.has_feature(tenant, feature_key)

"""La vitrine et la base doivent annoncer les mêmes offres.

Ce test existe à cause d'un écart réel, resté invisible plusieurs semaines : le
site vitrine annonçait « Essentiel 49 € / Standard 149 € / Étendu 349 € » quand
la base portait « Veille 89 € / Pilotage 249 € / Souverain sur devis ». Ni les
noms, ni les prix, ni les quotas ne correspondaient. Un prospect qui lisait la
page tarifs puis recevait son accès constatait l'écart lui-même.

Pourquoi l'écart a pu s'installer, et ce que ce test verrouille :

La grille affichée vient de l'API (``/api/v1/billing/plans/``), donc **elle**
était juste. C'est le REPLI statique de ``content.js`` — celui qui s'affiche
quand l'API ne répond pas — qui était périmé. Un repli ne se voit jamais en
conditions normales : rien ne signalait qu'il mentait, et il aurait menti
précisément le jour où l'API serait tombée, c'est-à-dire le pire.

On ne teste donc pas l'API (elle lit la base, elle ne peut pas diverger) : on
teste le **repli** contre la base. C'est le seul endroit où deux vérités
coexistent.

Ce test lit le fichier JavaScript. C'est inhabituel dans une suite Django, et
c'est assumé : l'alternative — publier les offres dans un JSON partagé par les
deux — ajouterait une étape de build au frontend pour une donnée qui change
deux fois par an. Le contrat de forme est étroit (une liste d'objets plats) et
le message d'échec dit quoi corriger.
"""

import re
from pathlib import Path

import pytest
from django.conf import settings

from apps.billing.models import Plan

CONTENT_JS = Path(settings.BASE_DIR).parent / "frontend" / "src" / "marketing" / "content.js"

# Champs recopiés dans le repli, et qui doivent correspondre à la base.
# `tagline` en est volontairement absent : c'est du texte éditorial, qu'un
# exploitant peut vouloir formuler autrement sur la vitrine que dans le
# back-office. Les codes, noms, prix et quotas, eux, sont des engagements.
QUOTA_FIELDS = ("monitored_assets", "monthly_scans", "max_users")


def _extract_fallback_plans() -> list[dict]:
    """Les offres du repli statique, extraites de ``content.js``.

    Volontairement strict : si la forme du fichier change (par exemple si
    quelqu'un remet des puces en texte libre à la place des champs), l'analyse
    échoue bruyamment plutôt que de retourner une liste vide — une liste vide
    ferait passer tous les tests sans rien vérifier.
    """
    assert CONTENT_JS.exists(), f"Fichier de contenu introuvable : {CONTENT_JS}"
    source = CONTENT_JS.read_text(encoding="utf-8")

    debut = source.find("export const PRICING")
    assert debut != -1, "Bloc PRICING absent de content.js"
    plans_debut = source.find("plans: [", debut)
    assert plans_debut != -1, "Liste `plans` absente du bloc PRICING"

    # Découpe par accolades équilibrées : les offres contiennent des objets
    # imbriqués (`features`), qu'une expression régulière naïve couperait au
    # premier « } ».
    curseur = source.index("[", plans_debut)
    profondeur = 0
    objets: list[str] = []
    depart = None
    for index in range(curseur, len(source)):
        caractere = source[index]
        if caractere == "{":
            if profondeur == 0:
                depart = index
            profondeur += 1
        elif caractere == "}":
            profondeur -= 1
            if profondeur == 0 and depart is not None:
                objets.append(source[depart : index + 1])
                depart = None
        elif caractere == "]" and profondeur == 0:
            break

    assert objets, "Aucune offre trouvée dans le repli statique de content.js"
    return [_parse_plan(bloc) for bloc in objets]


def _parse_plan(bloc: str) -> dict:
    def texte(champ: str) -> str | None:
        found = re.search(rf"\b{champ}:\s*'([^']*)'", bloc)
        return found.group(1) if found else None

    def nombre(champ: str) -> int | None:
        found = re.search(rf"\b{champ}:\s*(\d+)", bloc)
        return int(found.group(1)) if found else None

    def booleen(champ: str) -> bool | None:
        found = re.search(rf"\b{champ}:\s*(true|false)", bloc)
        return found.group(1) == "true" if found else None

    return {
        "code": texte("code"),
        "name": texte("name"),
        "price_monthly": nombre("price_monthly"),
        "is_quote_only": booleen("is_quote_only"),
        "monitored_assets": nombre("monitored_assets"),
        "monthly_scans": nombre("monthly_scans"),
        "max_users": nombre("max_users"),
    }


@pytest.fixture
def fallback_plans():
    return {plan["code"]: plan for plan in _extract_fallback_plans()}


@pytest.mark.django_db
class TestCoherenceVitrineBase:
    def test_toute_offre_publiee_figure_sur_la_vitrine(self, fallback_plans):
        """Publier une offre en base sans l'ajouter au repli la rendrait
        invisible aux visiteurs le jour où l'API ne répond pas."""
        publiees = set(
            Plan.objects.filter(status=Plan.Status.PUBLISHED).values_list("code", flat=True)
        )
        manquantes = publiees - set(fallback_plans)
        assert not manquantes, (
            f"Offres publiées en base et absentes du repli de content.js : {sorted(manquantes)}. "
            "Ajoutez-les à PRICING.plans, avec la forme de PublicPlanSerializer."
        )

    def test_la_vitrine_n_annonce_aucune_offre_non_publiee(self, fallback_plans):
        """Le miroir du test précédent, et il a un cas réel : l'offre « Essai »
        est `internal` (ADR-024). Elle est attribuée, jamais vendue — elle ne
        doit donc pas apparaître dans une grille tarifaire."""
        publiees = set(
            Plan.objects.filter(status=Plan.Status.PUBLISHED).values_list("code", flat=True)
        )
        en_trop = set(fallback_plans) - publiees
        assert not en_trop, (
            f"Offres annoncées sur la vitrine sans être publiées en base : {sorted(en_trop)}. "
            "Une offre retirée ou interne ne doit pas figurer dans PRICING.plans."
        )

    def test_les_noms_et_les_prix_ne_divergent_pas(self, fallback_plans):
        """Le cœur du sujet : c'est exactement l'écart qui a existé."""
        ecarts = []
        for plan in Plan.objects.filter(status=Plan.Status.PUBLISHED):
            attendu = fallback_plans.get(plan.code)
            if attendu is None:
                continue  # couvert par le premier test
            if attendu["name"] != plan.name:
                ecarts.append(f"{plan.code} : nom « {attendu['name']} » ≠ « {plan.name} »")
            if attendu["is_quote_only"] != plan.is_quote_only:
                ecarts.append(
                    f"{plan.code} : sur devis {attendu['is_quote_only']} ≠ {plan.is_quote_only}"
                )
            # Un plan sur devis n'affiche pas de montant : son prix n'engage
            # rien et n'a pas à être comparé.
            if not plan.is_quote_only and attendu["price_monthly"] != int(plan.price_monthly):
                ecarts.append(
                    f"{plan.code} : prix {attendu['price_monthly']} € ≠ {int(plan.price_monthly)} €"
                )
        assert not ecarts, "Divergences vitrine/base :\n- " + "\n- ".join(ecarts)

    def test_les_quotas_ne_divergent_pas(self, fallback_plans):
        """Les quotas sont affichés au visiteur (`quotaLines`) et engagent la
        plateforme : le nombre d'actifs en surveillance continue est pris sur
        un pool PARTAGÉ de 15 (ADR-013)."""
        ecarts = []
        for plan in Plan.objects.filter(status=Plan.Status.PUBLISHED):
            attendu = fallback_plans.get(plan.code)
            if attendu is None:
                continue
            for champ in QUOTA_FIELDS:
                if attendu[champ] != getattr(plan, champ):
                    ecarts.append(
                        f"{plan.code}.{champ} : {attendu[champ]} ≠ {getattr(plan, champ)}"
                    )
        assert not ecarts, "Quotas divergents entre la vitrine et la base :\n- " + "\n- ".join(
            ecarts
        )

    def test_aucune_offre_ne_promet_plus_que_le_pool_partage(self, fallback_plans):
        """La garde qui aurait arrêté « 30 actifs surveillés ».

        Le pool de surveillance continue est plafonné pour TOUTE la plateforme
        (ADR-013). Une seule offre qui annoncerait davantage serait invendable
        au premier client : ``billing.capacity`` refuserait son activation.
        On compare au plafond réel, pas à une constante recopiée ici.
        """
        pool = settings.BREACHSENSE_MONITORED_ASSET_POOL_SIZE
        fautives = [
            f"{code} annonce {plan['monitored_assets']} actifs pour un pool de {pool}"
            for code, plan in fallback_plans.items()
            if (plan["monitored_assets"] or 0) > pool
        ]
        assert not fautives, (
            "Offres promettant plus d'emplacements que la plateforme n'en possède :\n- "
            + "\n- ".join(fautives)
        )

    def test_le_repli_a_bien_la_forme_de_l_api(self, fallback_plans):
        """Le repli et l'API sont rendus par le même composant, sans
        traduction. Une forme divergente ré-ouvrirait la porte par laquelle
        l'écart initial est entré."""
        for code, plan in fallback_plans.items():
            for champ, valeur in plan.items():
                assert valeur is not None, (
                    f"L'offre « {code} » du repli n'a pas de champ `{champ}`. "
                    "Le repli doit porter les mêmes champs que PublicPlanSerializer."
                )

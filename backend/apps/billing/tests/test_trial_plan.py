"""Offre d'essai dédiée (ADR-024).

Ce qui est protégé ici est le tout début du parcours commercial : ce qu'un
prospect peut faire dans les minutes qui suivent son inscription. Le défaut
corrigé n'était pas une erreur de code — le code faisait exactement ce qu'on
lui demandait — mais un réglage commercial dont personne ne mesurait la
conséquence : l'essai démarrait sur une offre qui ne contient pas le
diagnostic ANSSI, c'est-à-dire l'entrée du produit.

Aucun test unitaire ne pouvait le voir : chacun déclarait son offre. Seul un
parcours de bout en bout, partant d'une inscription réelle, l'a révélé.
"""

import pytest
from django.conf import settings

from apps.billing import services as billing_services
from apps.billing.models import Plan

pytestmark = pytest.mark.django_db

CODE_ESSAI = "essai"


def test_l_essai_demarre_sur_l_offre_dediee():
    assert settings.BILLING_DEFAULT_TRIAL_PLAN_CODE == CODE_ESSAI
    plan = billing_services.get_default_trial_plan()
    assert plan is not None
    assert plan.code == CODE_ESSAI


def test_l_offre_d_essai_n_est_pas_au_catalogue_public():
    # Elle est attribuée, jamais vendue : la voir dans la grille tarifaire
    # laisserait croire qu'on peut y souscrire.
    codes = {plan.code for plan in billing_services.list_published_plans()}
    assert CODE_ESSAI not in codes
    assert {"veille", "pilotage", "souverain"} <= codes


def test_l_essai_donne_acces_a_l_entree_du_produit():
    # Le diagnostic et la génération documentaire sont ce pour quoi un
    # prospect s'inscrit. Un essai qui les refuse n'est pas un essai réduit,
    # c'est une promesse non tenue.
    plan = Plan.objects.get(code=CODE_ESSAI)
    assert "anssi_assessment" in plan.features
    assert "charter_generation" in plan.features
    assert "realtime_monitoring" in plan.features


def test_l_essai_ne_donne_pas_la_revelation_de_secret():
    # Seule fonctionnalité volontairement hors essai (ADR-014) : afficher en
    # clair un mot de passe réellement fuité.
    plan = Plan.objects.get(code=CODE_ESSAI)
    assert "secret_reveal" not in plan.features


def test_l_essai_ne_consomme_qu_un_emplacement_du_pool_partage():
    # C'est ce chiffre, et lui seul, qui détermine combien d'essais la
    # plateforme peut ouvrir : le pool de la licence en compte 15 (ADR-013).
    # À 3 emplacements — la valeur de « Pilotage » — on retomberait à cinq
    # essais au total.
    plan = Plan.objects.get(code=CODE_ESSAI)
    assert plan.monitored_assets == 1


def test_une_offre_interne_reste_attribuable():
    # `get_default_trial_plan` cherche par code sans filtrer sur le statut :
    # si un jour il filtrait sur « publiée », l'essai retomberait
    # silencieusement sur la première offre du catalogue — exactement le
    # défaut qu'on vient de corriger, revenu par une autre porte.
    plan = Plan.objects.get(code=CODE_ESSAI)
    assert plan.status == Plan.Status.INTERNAL
    assert billing_services.get_default_trial_plan().pk == plan.pk

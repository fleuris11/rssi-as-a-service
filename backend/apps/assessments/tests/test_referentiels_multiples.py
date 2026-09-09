"""V2-4 : plusieurs référentiels, attribués par client (ADR-029), consolidés
selon une règle écrite (ADR-030).

Quatre garanties tenues ici, dans cet ordre :

1. un référentiel s'attribue et se retire, et le retrait ne reprend RIEN ;
2. un questionnaire peut ne porter que sur une partie d'un référentiel ;
3. une reformulation pour un client n'atteint jamais le référentiel ;
4. deux clients ne se voient pas.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.assessments import services
from apps.assessments.models import Answer, Assessment, Measure, MeasureStatementOverride
from apps.tenants.models import Membership

pytestmark = pytest.mark.django_db


def _login(api_client, email, password="Str0ng!Passw0rd123"):
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": email, "password": password}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK
    return response.data["access"]


def _auth(api_client, user, tenant):
    return {
        "HTTP_AUTHORIZATION": f"Bearer {_login(api_client, user.email)}",
        "HTTP_X_TENANT_ID": str(tenant.id),
    }


def _terminer(tenant, user, referential, *, valeur="yes", subset=None):
    """Un diagnostic complet, du démarrage à la clôture."""
    assessment = services.start_or_resume_assessment(
        tenant=tenant, user=user, referential=referential, subset=subset
    )
    for mesure in services.get_assessment_measures(assessment):
        services.submit_answer(assessment=assessment, measure=mesure, value=valeur)
    return services.complete_assessment(assessment)


# --- Attribution ------------------------------------------------------------


class TestAttribution:
    def test_un_client_ne_voit_que_ce_qui_lui_est_attribue(
        self, tenant, referential, second_referential
    ):
        services.revoke_referential(tenant=tenant, referential=second_referential)

        attribues = [r.slug for r in services.granted_referentials(tenant)]
        assert attribues == [referential.slug]

    def test_attribution_multiple(self, tenant, referential, second_referential):
        attribues = {r.slug for r in services.granted_referentials(tenant)}
        assert attribues == {referential.slug, second_referential.slug}

    def test_produire_sans_attribution_est_refuse(
        self, tenant, tenant_owner, referential, second_referential
    ):
        services.revoke_referential(tenant=tenant, referential=second_referential)

        with pytest.raises(services.ReferentialNotAssignedError):
            services.start_or_resume_assessment(
                tenant=tenant, user=tenant_owner, referential=second_referential
            )

    def test_reattribuer_leve_le_retrait_sans_perdre_la_date_d_origine(self, tenant, referential):
        origine = services.list_assignments(tenant).get(referential=referential).granted_at
        services.revoke_referential(tenant=tenant, referential=referential)
        services.assign_referential(tenant=tenant, referential=referential)

        attribution = services.list_assignments(tenant).get(referential=referential)
        assert attribution.revoked_at is None
        assert attribution.granted_at == origine

    def test_un_referentiel_propre_a_un_client_n_est_pas_attribuable_a_un_autre(
        self, tenant, tenant_factory, user_factory, second_referential
    ):
        autre = tenant_factory(user_factory(email="autre@example.com"), name="Autre")
        second_referential.owner_tenant = autre
        second_referential.save(update_fields=["owner_tenant"])

        with pytest.raises(services.ReferentialNotAssignedError):
            services.assign_referential(tenant=tenant, referential=second_referential)

    def test_un_referentiel_propre_a_un_client_n_apparait_pas_au_catalogue_des_autres(
        self, tenant, tenant_factory, user_factory, second_referential
    ):
        autre = tenant_factory(user_factory(email="autre@example.com"), name="Autre")
        second_referential.owner_tenant = autre
        second_referential.save(update_fields=["owner_tenant"])

        attribuables = {r.slug for r in services.assignable_referentials(tenant)}
        assert second_referential.slug not in attribuables


class TestEntrepriseNouvellementCreee:
    """Ce qu'une entreprise reçoit à l'inscription.

    Ces tests appellent ``create_tenant_with_owner`` directement, sans passer
    par la fixture ``tenant_factory`` — celle-ci attribue tout le catalogue
    pour préserver le monde d'avant V2-4, et masquerait donc exactement ce
    qu'on vérifie ici.
    """

    def test_recoit_d_office_les_referentiels_libres_de_droits(self, referential, user_factory):
        from apps.tenants import services as tenants_services

        nouvelle = tenants_services.create_tenant_with_owner(
            name="Nouvelle entreprise", owner=user_factory(email="nouvelle@example.com")
        )

        assert services.is_granted(nouvelle, referential) is True

    def test_ne_recoit_pas_d_office_un_referentiel_sous_licence(
        self, second_referential, user_factory
    ):
        """Servir un contenu sous droits est une décision d'exploitant, pas la
        conséquence d'une inscription."""
        from apps.tenants import services as tenants_services

        nouvelle = tenants_services.create_tenant_with_owner(
            name="Nouvelle entreprise", owner=user_factory(email="nouvelle@example.com")
        )

        assert services.is_granted(nouvelle, second_referential) is False
        # Elle le VOIT quand même au catalogue : c'est ce qui lui permet d'en
        # faire la demande.
        assert second_referential in list(services.assignable_referentials(nouvelle))


class TestRetraitNeReprendRien:
    """Point 7 de V2-4 : « On ne prend jamais en otage des données déjà
    produites. »"""

    def test_les_evaluations_passees_restent_lisibles(self, tenant, tenant_owner, referential):
        termine = _terminer(tenant, tenant_owner, referential)
        services.revoke_referential(tenant=tenant, referential=referential)

        assert referential in list(services.readable_referentials(tenant))
        assert services.get_assessment(tenant=tenant, assessment_id=termine.id) is not None
        assert services.compute_scores(termine)["global"] == 100.0

    def test_le_score_consolide_compte_encore_un_referentiel_retire(
        self, tenant, tenant_owner, referential
    ):
        _terminer(tenant, tenant_owner, referential)
        services.revoke_referential(tenant=tenant, referential=referential)

        consolide = services.consolidated_scores(tenant)
        ligne = next(
            ligne
            for ligne in consolide["by_referential"]
            if ligne["referential_slug"] == referential.slug
        )
        assert ligne["score"] == 100.0
        assert ligne["granted"] is False

    def test_l_ecriture_est_fermee_apres_retrait(
        self, api_client, tenant, tenant_owner, referential
    ):
        assessment = services.start_or_resume_assessment(
            tenant=tenant, user=tenant_owner, referential=referential
        )
        mesure = services.get_assessment_measures(assessment)[0]
        services.revoke_referential(tenant=tenant, referential=referential)
        headers = _auth(api_client, tenant_owner, tenant)

        lecture = api_client.get(reverse("assessment-detail", args=[assessment.id]), **headers)
        ecriture = api_client.put(
            reverse("assessment-answer", args=[assessment.id, mesure.id]),
            {"value": "yes"},
            format="json",
            **headers,
        )

        assert lecture.status_code == status.HTTP_200_OK
        assert ecriture.status_code == status.HTTP_403_FORBIDDEN


# --- Sous-ensembles ---------------------------------------------------------


class TestSousEnsembles:
    def test_compose_un_questionnaire_plus_court(self, referential, subset_factory):
        subset = subset_factory(referential, ["1", "3"])
        assert services.subset_measure_ids(subset) == [
            Measure.objects.get(referential=referential, code="1").id,
            Measure.objects.get(referential=referential, code="3").id,
        ]

    def test_l_ordre_de_composition_est_l_ordre_de_passage(self, referential, subset_factory):
        subset = subset_factory(referential, ["3", "1"])
        codes = [Measure.objects.get(id=mid).code for mid in services.subset_measure_ids(subset)]
        assert codes == ["3", "1"]

    def test_une_mesure_inconnue_est_refusee(self, referential, subset_factory):
        with pytest.raises(services.SubsetError, match="Mesures inconnues"):
            subset_factory(referential, ["1", "999"])

    def test_la_progression_ne_compte_que_le_sous_ensemble(
        self, tenant, tenant_owner, referential, subset_factory
    ):
        subset = subset_factory(referential, ["1", "3"])
        assessment = services.start_or_resume_assessment(
            tenant=tenant, user=tenant_owner, referential=referential, subset=subset
        )
        assert services.get_progress(assessment)["total"] == 2

    def test_le_score_ne_porte_que_sur_le_sous_ensemble(
        self, tenant, tenant_owner, referential, subset_factory
    ):
        """Deux mesures standard de poids 1 : répondre « oui » à l'une et
        « non » à l'autre donne 50, et non le score des quatre mesures."""
        subset = subset_factory(referential, ["1", "3"])
        assessment = services.start_or_resume_assessment(
            tenant=tenant, user=tenant_owner, referential=referential, subset=subset
        )
        mesures = services.get_assessment_measures(assessment)
        services.submit_answer(assessment=assessment, measure=mesures[0], value="yes")
        services.submit_answer(assessment=assessment, measure=mesures[1], value="no")

        assert services.compute_scores(assessment)["global"] == 50.0

    def test_la_cloture_n_attend_que_les_mesures_du_sous_ensemble(
        self, tenant, tenant_owner, referential, subset_factory
    ):
        subset = subset_factory(referential, ["1", "3"])
        termine = _terminer(tenant, tenant_owner, referential, subset=subset)
        assert termine.status == Assessment.Status.COMPLETED

    def test_le_plan_d_action_ne_contient_que_le_sous_ensemble(
        self, tenant, tenant_owner, referential, subset_factory
    ):
        from apps.actions import services as actions_services

        subset = subset_factory(referential, ["1", "3"])
        termine = _terminer(tenant, tenant_owner, referential, valeur="no", subset=subset)
        actions_services.generate_action_plan(termine)

        items = actions_services.list_action_items(tenant)
        assert {item.measure.code for item in items} == {"1", "3"}

    def test_repondre_hors_du_sous_ensemble_est_refuse(
        self, tenant, tenant_owner, referential, subset_factory
    ):
        subset = subset_factory(referential, ["1"])
        assessment = services.start_or_resume_assessment(
            tenant=tenant, user=tenant_owner, referential=referential, subset=subset
        )
        hors_perimetre = Measure.objects.get(referential=referential, code="3")

        with pytest.raises(services.MeasureNotInScopeError):
            services.submit_answer(assessment=assessment, measure=hors_perimetre, value="yes")

    def test_un_sous_ensemble_est_reutilisable_par_un_autre_client(
        self, tenant, tenant_owner, tenant_factory, user_factory, referential, subset_factory
    ):
        """« Modèle réutilisable » : sans propriétaire, la composition sert à
        tous les clients à qui le référentiel est attribué."""
        modele = subset_factory(referential, ["1", "3"], owner_tenant=None)
        autre = tenant_factory(user_factory(email="autre@example.com"), name="Autre")

        assert modele in list(services.list_subsets(autre, referential=referential))


# --- Surcharge d'énoncé -----------------------------------------------------


class TestSurchargeDEnonce:
    def test_l_enonce_affiche_est_celui_du_client(self, tenant, referential):
        mesure = Measure.objects.get(referential=referential, code="1")
        services.set_measure_override(
            tenant=tenant, measure=mesure, plain_language="Notre formulation à nous ?"
        )

        structure = services.get_referential_structure(referential, tenant=tenant)
        affichee = structure[0]["measures"][0]
        assert affichee.statement == "Notre formulation à nous ?"
        assert affichee.is_overridden is True

    def test_le_referentiel_d_origine_n_est_pas_touche(self, tenant, referential):
        mesure = Measure.objects.get(referential=referential, code="1")
        origine = mesure.plain_language
        services.set_measure_override(
            tenant=tenant, measure=mesure, plain_language="Notre formulation à nous ?"
        )

        mesure.refresh_from_db()
        assert mesure.plain_language == origine

    def test_un_autre_client_lit_l_enonce_d_origine(
        self, tenant, tenant_factory, user_factory, referential
    ):
        mesure = Measure.objects.get(referential=referential, code="1")
        origine = mesure.plain_language
        services.set_measure_override(
            tenant=tenant, measure=mesure, plain_language="Notre formulation à nous ?"
        )
        autre = tenant_factory(user_factory(email="autre@example.com"), name="Autre")

        structure = services.get_referential_structure(referential, tenant=autre)
        assert structure[0]["measures"][0].statement == origine

    def test_retirer_la_surcharge_fait_revenir_l_enonce_d_origine(self, tenant, referential):
        mesure = Measure.objects.get(referential=referential, code="1")
        origine = mesure.plain_language
        services.set_measure_override(tenant=tenant, measure=mesure, plain_language="Autre ?")
        services.clear_measure_override(tenant=tenant, measure=mesure)

        structure = services.get_referential_structure(referential, tenant=tenant)
        assert structure[0]["measures"][0].statement == origine
        assert not MeasureStatementOverride.all_objects.filter(tenant=tenant).exists()

    def test_la_surcharge_ne_change_pas_le_score(self, tenant, tenant_owner, referential):
        """Elle porte sur les mots, pas sur la mesure : le poids, le niveau et
        le calcul sont les mêmes."""
        avant = _terminer(tenant, tenant_owner, referential).score_global
        mesure = Measure.objects.get(referential=referential, code="1")
        services.set_measure_override(tenant=tenant, measure=mesure, plain_language="Autre ?")

        apres = _terminer(tenant, tenant_owner, referential).score_global
        assert avant == apres


# --- Consolidation (ADR-030) ------------------------------------------------


class TestConsolidation:
    def test_le_detail_accompagne_toujours_le_consolide(
        self, tenant, tenant_owner, referential, second_referential
    ):
        _terminer(tenant, tenant_owner, referential, valeur="yes")
        _terminer(tenant, tenant_owner, second_referential, valeur="no")

        consolide = services.consolidated_scores(tenant)
        assert consolide["consolidated"] == 50.0
        assert consolide["method"] == "moyenne_par_referentiel"
        assert len(consolide["by_referential"]) == 2

    def test_chaque_referentiel_compte_pour_un_quelle_que_soit_sa_taille(
        self, tenant, tenant_owner, referential, second_referential
    ):
        """La règle rendue visible : 4 mesures d'un côté, 2 de l'autre, et
        pourtant 50 — une moyenne pondérée par les mesures aurait donné 66,7."""
        _terminer(tenant, tenant_owner, referential, valeur="yes")
        _terminer(tenant, tenant_owner, second_referential, valeur="no")

        assert services.consolidated_scores(tenant)["consolidated"] == 50.0

    def test_un_referentiel_non_evalue_est_nomme_et_non_compte(
        self, tenant, tenant_owner, referential, second_referential
    ):
        _terminer(tenant, tenant_owner, referential, valeur="yes")

        consolide = services.consolidated_scores(tenant)
        assert consolide["consolidated"] == 100.0
        assert consolide["scored_referentials"] == 1
        assert consolide["unscored_referentials"] == [second_referential.name]

    def test_sans_aucun_diagnostic_le_consolide_est_nul_et_non_zero(self, tenant, referential):
        assert services.consolidated_scores(tenant)["consolidated"] is None


class TestIndicateursDeComite:
    def test_un_seul_referentiel_donne_le_score_d_avant(
        self, tenant, tenant_owner, referential, second_referential
    ):
        from django.utils import timezone

        services.revoke_referential(tenant=tenant, referential=second_referential)
        _terminer(tenant, tenant_owner, referential, valeur="yes")

        maintenant = timezone.now()
        indicateurs = services.maturity_indicators(
            tenant, start=maintenant - timezone.timedelta(days=1), end=maintenant
        )
        assert indicateurs["score"] == 100.0
        assert indicateurs["referential_count"] == 1
        # Pas de méthode annoncée quand il n'y a rien à consolider.
        assert indicateurs["method"] is None

    def test_le_delta_n_est_pas_calcule_sur_des_ensembles_differents(
        self, tenant, tenant_owner, referential, second_referential
    ):
        """Le piège que la règle évite : un deuxième référentiel évalué pour la
        première fois ferait bouger une « progression » qui n'a eu lieu nulle
        part."""
        from django.utils import timezone

        _terminer(tenant, tenant_owner, referential, valeur="no")
        _terminer(tenant, tenant_owner, referential, valeur="yes")
        _terminer(tenant, tenant_owner, second_referential, valeur="yes")

        maintenant = timezone.now()
        indicateurs = services.maturity_indicators(
            tenant, start=maintenant - timezone.timedelta(days=1), end=maintenant
        )
        assert indicateurs["score"] == 100.0
        assert indicateurs["previous_score"] is None
        assert indicateurs["delta"] is None

    def test_le_delta_est_calcule_quand_les_deux_cotes_ont_un_antecedent(
        self, tenant, tenant_owner, referential, second_referential
    ):
        from django.utils import timezone

        _terminer(tenant, tenant_owner, referential, valeur="no")
        _terminer(tenant, tenant_owner, second_referential, valeur="no")
        _terminer(tenant, tenant_owner, referential, valeur="yes")
        _terminer(tenant, tenant_owner, second_referential, valeur="yes")

        maintenant = timezone.now()
        indicateurs = services.maturity_indicators(
            tenant, start=maintenant - timezone.timedelta(days=1), end=maintenant
        )
        assert indicateurs["score"] == 100.0
        assert indicateurs["previous_score"] == 0.0
        assert indicateurs["delta"] == 100.0


class TestPlanConsolide:
    def test_le_plan_consolide_reunit_les_deux_referentiels(
        self, tenant, tenant_owner, referential, second_referential
    ):
        from apps.actions import services as actions_services

        for cadre in (referential, second_referential):
            actions_services.generate_action_plan(
                _terminer(tenant, tenant_owner, cadre, valeur="no")
            )

        tous = actions_services.list_action_items(tenant)
        assert len(tous) == 6
        du_premier = actions_services.list_action_items(tenant, referential=referential)
        assert len(du_premier) == 4

    def test_le_detail_par_referentiel_accompagne_le_taux_global(
        self, tenant, tenant_owner, referential, second_referential
    ):
        from django.utils import timezone

        from apps.actions import services as actions_services

        for cadre in (referential, second_referential):
            actions_services.generate_action_plan(
                _terminer(tenant, tenant_owner, cadre, valeur="no")
            )

        maintenant = timezone.now()
        indicateurs = actions_services.action_plan_indicators(
            tenant, start=maintenant - timezone.timedelta(days=1), end=maintenant
        )
        noms = {ligne["referential_name"] for ligne in indicateurs["by_referential"]}
        assert noms == {referential.name, second_referential.name}


# --- Étanchéité -------------------------------------------------------------


class TestEtancheiteTenant:
    @pytest.fixture
    def voisin(self, tenant_factory, user_factory):
        proprietaire = user_factory(email="voisin@example.com")
        return tenant_factory(proprietaire, name="Voisin"), proprietaire

    def test_une_surcharge_n_est_pas_visible_du_voisin(self, tenant, voisin, referential):
        autre_tenant, _ = voisin
        mesure = Measure.objects.get(referential=referential, code="1")
        services.set_measure_override(tenant=tenant, measure=mesure, plain_language="À nous ?")

        assert list(services.list_overrides(autre_tenant)) == []

    def test_un_sous_ensemble_prive_n_est_pas_visible_du_voisin(
        self, tenant, voisin, referential, subset_factory
    ):
        autre_tenant, _ = voisin
        prive = subset_factory(referential, ["1"], owner_tenant=tenant, slug="prive")

        assert prive not in list(services.list_subsets(autre_tenant))

    def test_les_attributions_sont_par_client(self, tenant, voisin, referential):
        autre_tenant, _ = voisin
        services.revoke_referential(tenant=tenant, referential=referential)

        assert services.is_granted(tenant, referential) is False
        assert services.is_granted(autre_tenant, referential) is True

    def test_le_consolide_d_un_client_ignore_les_diagnostics_du_voisin(
        self, tenant, tenant_owner, voisin, referential
    ):
        autre_tenant, autre_owner = voisin
        _terminer(tenant, tenant_owner, referential, valeur="yes")
        _terminer(autre_tenant, autre_owner, referential, valeur="no")

        assert services.consolidated_scores(tenant)["consolidated"] == 100.0
        assert services.consolidated_scores(autre_tenant)["consolidated"] == 0.0

    def test_l_api_refuse_de_surcharger_une_mesure_d_un_referentiel_non_attribue(
        self, api_client, tenant, tenant_owner, referential, second_referential
    ):
        services.revoke_referential(tenant=tenant, referential=second_referential)
        mesure = Measure.objects.filter(referential=second_referential).first()
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.put(
            reverse("assessment-measure-override", args=[mesure.id]),
            {"plain_language": "Chez nous ?"},
            format="json",
            **headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# --- API --------------------------------------------------------------------


class TestApiReferentiels:
    def test_liste_le_catalogue_avec_l_etat_de_chaque_referentiel(
        self, api_client, tenant, tenant_owner, referential, second_referential
    ):
        services.revoke_referential(tenant=tenant, referential=second_referential)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("assessment-referential-list"), **headers)

        assert response.status_code == status.HTTP_200_OK
        par_slug = {r["slug"]: r for r in response.data}
        assert par_slug[referential.slug]["granted"] is True
        # Non attribué mais VISIBLE : le client doit savoir ce qu'il peut
        # demander, comme pour les fonctionnalités hors offre.
        assert par_slug[second_referential.slug]["granted"] is False

    def test_le_detail_d_un_referentiel_non_attribue_est_refuse(
        self, api_client, tenant, tenant_owner, referential, second_referential
    ):
        services.revoke_referential(tenant=tenant, referential=second_referential)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(
            reverse("assessment-referential-detail", args=[second_referential.slug]), **headers
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_demarrer_sur_un_referentiel_designe(
        self, api_client, tenant, tenant_owner, referential, second_referential
    ):
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(
            reverse("assessment-start"),
            {"referential": second_referential.slug},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["referential_slug"] == second_referential.slug

    def test_deux_diagnostics_de_front_un_par_referentiel(
        self, api_client, tenant, tenant_owner, referential, second_referential
    ):
        headers = _auth(api_client, tenant_owner, tenant)
        premier = api_client.post(
            reverse("assessment-start"), {"referential": referential.slug}, format="json", **headers
        )
        second = api_client.post(
            reverse("assessment-start"),
            {"referential": second_referential.slug},
            format="json",
            **headers,
        )

        assert premier.data["id"] != second.data["id"]
        assert Assessment.all_objects.filter(tenant=tenant).count() == 2

    def test_reprendre_renvoie_le_diagnostic_du_bon_referentiel(
        self, api_client, tenant, tenant_owner, referential, second_referential
    ):
        headers = _auth(api_client, tenant_owner, tenant)
        api_client.post(
            reverse("assessment-start"), {"referential": referential.slug}, format="json", **headers
        )
        attendu = api_client.post(
            reverse("assessment-start"),
            {"referential": second_referential.slug},
            format="json",
            **headers,
        )

        reprise = api_client.get(
            reverse("assessment-current"),
            {"referential": second_referential.slug},
            **headers,
        )
        assert reprise.data["id"] == attendu.data["id"]

    def test_le_score_consolide_est_expose(
        self, api_client, tenant, tenant_owner, referential, second_referential
    ):
        _terminer(tenant, tenant_owner, referential, valeur="yes")
        _terminer(tenant, tenant_owner, second_referential, valeur="no")
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("assessment-scores-consolidated"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["consolidated"] == 50.0
        assert response.data["method"] == "moyenne_par_referentiel"

    def test_l_ancien_endpoint_renvoie_le_referentiel_par_defaut(
        self, api_client, tenant, tenant_owner, referential
    ):
        """Compatibilité : les clients d'API écrits avant V2-4 continuent."""
        headers = _auth(api_client, tenant_owner, tenant)
        response = api_client.get(reverse("assessment-referential"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["slug"] == referential.slug
        assert len(response.data["domains"]) == 2

    def test_sans_aucun_referentiel_attribue_le_diagnostic_est_indisponible(
        self, api_client, tenant, tenant_owner, referential, second_referential
    ):
        for cadre in (referential, second_referential):
            services.revoke_referential(tenant=tenant, referential=cadre)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("assessment-referential"), **headers)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        # Le message parle au dirigeant, pas à l'exploitant : aucune commande,
        # aucun nom d'outil (config/tests/test_client_facing_messages_sweep.py).
        assert "demander" in response.data["detail"]

    def test_le_lecteur_ne_compose_pas_de_questionnaire(
        self, api_client, tenant, tenant_owner, user_factory, referential
    ):
        lecteur = user_factory(email="lecteur@example.com")
        Membership.all_objects.create(tenant=tenant, user=lecteur, role=Membership.Role.READER)
        headers = _auth(api_client, lecteur, tenant)

        response = api_client.post(
            reverse("assessment-subset-list"),
            {
                "referential": referential.slug,
                "slug": "court",
                "name": "Court",
                "measure_codes": ["1"],
            },
            format="json",
            **headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestApiSurcharge:
    def test_pose_puis_retire_une_surcharge(self, api_client, tenant, tenant_owner, referential):
        mesure = Measure.objects.get(referential=referential, code="1")
        origine = mesure.plain_language
        headers = _auth(api_client, tenant_owner, tenant)

        pose = api_client.put(
            reverse("assessment-measure-override", args=[mesure.id]),
            {"plain_language": "Chez nous ?", "context_note": "Périmètre : le siège."},
            format="json",
            **headers,
        )
        assert pose.status_code == status.HTTP_200_OK
        assert pose.data["original_plain_language"] == origine

        questionnaire = api_client.get(
            reverse("assessment-referential-detail", args=[referential.slug]), **headers
        )
        mesure_affichee = questionnaire.data["domains"][0]["measures"][0]
        assert mesure_affichee["statement"] == "Chez nous ?"
        assert mesure_affichee["plain_language"] == origine

        retrait = api_client.delete(
            reverse("assessment-measure-override", args=[mesure.id]), **headers
        )
        assert retrait.status_code == status.HTTP_204_NO_CONTENT


class TestApiSousEnsembles:
    def test_compose_et_demarre_sur_le_questionnaire_compose(
        self, api_client, tenant, tenant_owner, referential
    ):
        headers = _auth(api_client, tenant_owner, tenant)

        creation = api_client.post(
            reverse("assessment-subset-list"),
            {
                "referential": referential.slug,
                "slug": "essentiel",
                "name": "Les essentielles",
                "measure_codes": ["1", "3"],
            },
            format="json",
            **headers,
        )
        assert creation.status_code == status.HTTP_201_CREATED
        assert creation.data["measure_count"] == 2

        demarrage = api_client.post(
            reverse("assessment-start"),
            {"referential": referential.slug, "subset": "essentiel"},
            format="json",
            **headers,
        )
        assert demarrage.data["progress"]["total"] == 2
        assert demarrage.data["subset_name"] == "Les essentielles"

    def test_une_mesure_inconnue_est_refusee_en_400(
        self, api_client, tenant, tenant_owner, referential
    ):
        headers = _auth(api_client, tenant_owner, tenant)
        response = api_client.post(
            reverse("assessment-subset-list"),
            {
                "referential": referential.slug,
                "slug": "faux",
                "name": "Faux",
                "measure_codes": ["999"],
            },
            format="json",
            **headers,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestReponsesConservees:
    """La garantie que la migration doit tenir, vérifiée sur le code : rien de
    ce qui a été répondu ne se perd quand le catalogue bouge."""

    def test_un_import_qui_met_a_jour_le_referentiel_ne_touche_pas_les_reponses(
        self, tenant, tenant_owner, referential
    ):
        from apps.assessments import importers

        assessment = services.start_or_resume_assessment(
            tenant=tenant, user=tenant_owner, referential=referential
        )
        mesure = services.get_assessment_measures(assessment)[0]
        services.submit_answer(assessment=assessment, measure=mesure, value="partial")

        importers.import_referential(
            importers.parse_json(
                {
                    "slug": referential.slug,
                    "name": referential.name,
                    "version": "1.1",
                    "domains": [
                        {
                            "code": "domaine-a",
                            "name": "Domaine A",
                            "order": 1,
                            "measures": [
                                {
                                    "code": "1",
                                    "title": "Intitulé révisé",
                                    "statement": "Question révisée ?",
                                }
                            ],
                        }
                    ],
                }
            )
        )

        reponse = Answer.all_objects.get(assessment=assessment, measure=mesure)
        assert reponse.value == "partial"
        mesure.refresh_from_db()
        assert mesure.official_title == "Intitulé révisé"

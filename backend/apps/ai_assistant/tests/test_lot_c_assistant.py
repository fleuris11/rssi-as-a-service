"""Lot C, C4 — l'assistant : des questions de départ réelles, des renvois
vers les écrans, et aucun appel d'IA pour les produire."""

from datetime import timedelta
from unittest import mock

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.ai_assistant import assistant_guide, services
from apps.ai_assistant.models import Conversation, Message
from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Alert, Asset
from apps.threat_intelligence.models import BreachFinding

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


def _actif(tenant, user, valeur="https://acme.example"):
    return monitoring_services.create_asset(
        tenant=tenant, user=user, type=Asset.Type.WEBSITE, value=valeur, ownership_confirmed=True
    )


def _fuite_critique(tenant, asset, cle):
    return BreachFinding.all_objects.create(
        tenant=tenant,
        asset=asset,
        source_endpoint=BreachFinding.SourceEndpoint.CREDS,
        finding_type="creds",
        severity=BreachFinding.Severity.CRITICAL,
        status=BreachFinding.Status.OPEN,
        dedup_hash=f"d-{cle}",
        identity_hash=f"i-{cle}",
        secret_fingerprint=f"s-{cle}",
    )


def _questions(tenant):
    return [s["question"] for s in assistant_guide.suggestions(tenant)]


class TestSuggestionsTireesDeLaSituation:
    def test_les_compromissions_critiques_passent_en_premier_avec_leur_nombre(
        self, tenant, tenant_owner
    ):
        asset = _actif(tenant, tenant_owner)
        _fuite_critique(tenant, asset, "a")
        _fuite_critique(tenant, asset, "b")

        premiere = assistant_guide.suggestions(tenant)[0]

        assert premiere["question"] == "Que faire de mes 2 compromissions critiques ?"
        assert premiere["link"]["to"] == "/compromissions"

    def test_sans_diagnostic_on_propose_de_commencer_par_la(self, tenant):
        assert "Par où commencer pour évaluer la sécurité de mon entreprise ?" in _questions(tenant)

    def test_avec_un_plan_on_propose_par_quoi_commencer(self, tenant, tenant_owner, referential):
        from apps.actions import services as actions_services
        from apps.assessments import services as assessments_services

        evaluation = assessments_services.start_or_resume_assessment(
            tenant=tenant, user=tenant_owner, referential=referential
        )
        for mesure in assessments_services.get_assessment_measures(evaluation):
            assessments_services.submit_answer(assessment=evaluation, measure=mesure, value="no")
        assessments_services.complete_assessment(evaluation)
        actions_services.generate_action_plan(evaluation)

        questions = _questions(tenant)

        assert "Par quoi commencer dans mon plan d'action ?" in questions
        assert any(q.startswith("Que veut dire mon score de maturité de") for q in questions)
        assert "Par où commencer pour évaluer la sécurité de mon entreprise ?" not in questions

    def test_une_action_en_retard_est_signalee(self, tenant, tenant_owner, referential):
        from apps.actions import services as actions_services
        from apps.actions.models import ActionItem
        from apps.assessments import services as assessments_services

        evaluation = assessments_services.start_or_resume_assessment(
            tenant=tenant, user=tenant_owner, referential=referential
        )
        for mesure in assessments_services.get_assessment_measures(evaluation):
            assessments_services.submit_answer(assessment=evaluation, measure=mesure, value="no")
        assessments_services.complete_assessment(evaluation)
        actions_services.generate_action_plan(evaluation)
        ActionItem.all_objects.filter(tenant=tenant).update(
            due_date=timezone.localdate() - timedelta(days=3)
        )

        assert any("en retard : lesquelles prioriser ?" in q for q in _questions(tenant))

    def test_les_alertes_ouvertes_sont_citees(self, tenant, tenant_owner):
        asset = _actif(tenant, tenant_owner)
        Alert.all_objects.create(
            tenant=tenant, asset=asset, alert_type=Alert.AlertType.DOWN, severity="critical"
        )

        assert "J'ai 1 alerte ouverte sur mes sites : est-ce grave ?" in _questions(tenant)

    def test_jamais_plus_de_quatre(self, tenant, tenant_owner, referential):
        asset = _actif(tenant, tenant_owner)
        _fuite_critique(tenant, asset, "x")
        Alert.all_objects.create(
            tenant=tenant, asset=asset, alert_type=Alert.AlertType.DOWN, severity="critical"
        )
        assert len(assistant_guide.suggestions(tenant)) <= assistant_guide.LIMITE_SUGGESTIONS

    def test_aucune_suggestion_ne_cite_une_adresse_ou_un_actif(self, tenant, tenant_owner):
        asset = _actif(tenant, tenant_owner, valeur="https://confidentiel.example")
        _fuite_critique(tenant, asset, "p")

        texte = str(assistant_guide.suggestions(tenant))

        assert "confidentiel.example" not in texte
        assert tenant.name not in texte

    def test_les_suggestions_n_appellent_jamais_l_ia(self, tenant):
        with mock.patch.object(services, "call_claude") as appel:
            assistant_guide.suggestions(tenant)
        appel.assert_not_called()


class TestEtancheite:
    def test_les_compromissions_du_voisin_ne_sont_pas_suggerees(
        self, api_client, tenant, tenant_owner, user_factory, tenant_factory
    ):
        voisin_proprietaire = user_factory(email="voisin-assistant@example.com")
        voisin = tenant_factory(voisin_proprietaire, name="Voisin assistant")
        asset = _actif(voisin, voisin_proprietaire, valeur="https://voisin.example")
        _fuite_critique(voisin, asset, "v1")

        response = api_client.get(
            reverse("ai-assistant-suggestions"), **_auth(api_client, tenant_owner, tenant)
        )

        assert response.status_code == status.HTTP_200_OK
        assert not any("compromission" in s["question"] for s in response.data["results"])

    def test_refuse_quand_l_ia_est_coupee(self, api_client, tenant, tenant_owner):
        tenant.ai_enabled = False
        tenant.save(update_fields=["ai_enabled"])

        response = api_client.get(
            reverse("ai-assistant-suggestions"), **_auth(api_client, tenant_owner, tenant)
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestRenvoisVersLesEcrans:
    def test_une_reponse_renvoie_vers_les_ecrans_dont_elle_parle(self):
        texte = (
            "Commencez par changer le mot de passe exposé dans la fuite, puis complétez "
            "vos enregistrements SPF et DMARC. Ajoutez ensuite ces mesures à votre plan d'action."
        )

        liens = assistant_guide.related_links(texte)

        assert [lien["to"] for lien in liens] == [
            "/compromissions",
            "/surveillance",
            "/plan-action",
        ]

    def test_jamais_plus_de_trois_liens_ni_de_doublon(self):
        texte = (
            "fuite, fuite, compromission ; exposition ; plan d'action ; diagnostic ; "
            "certificat ; charte ; veille"
        )

        liens = assistant_guide.related_links(texte)

        routes = [lien["to"] for lien in liens]
        assert len(routes) == assistant_guide.LIMITE_LIENS
        assert len(set(routes)) == len(routes)

    def test_aucun_lien_n_est_invente(self):
        routes_connues = {route for route, _l, _m in assistant_guide.LIENS}
        texte = "Consultez https://exemple.org/piege et notre page /admin/plateforme."

        for lien in assistant_guide.related_links(texte):
            assert lien["to"] in routes_connues
        assert assistant_guide.related_links(texte) == []

    def test_l_api_sert_les_liens_sur_les_seules_reponses_de_l_assistant(
        self, api_client, tenant, tenant_owner
    ):
        conversation = Conversation.all_objects.create(tenant=tenant, created_by=tenant_owner)
        Message.all_objects.create(
            tenant=tenant,
            conversation=conversation,
            role=Message.Role.USER,
            content="Que faire de ma fuite de mot de passe ?",
        )
        Message.all_objects.create(
            tenant=tenant,
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content="Changez le mot de passe concerné, puis consultez votre plan d'action.",
        )

        response = api_client.get(
            reverse("ai-message-list", kwargs={"conversation_id": conversation.id}),
            **_auth(api_client, tenant_owner, tenant),
        )

        utilisateur, assistant = response.data["results"]
        assert utilisateur["links"] == []
        assert [lien["to"] for lien in assistant["links"]] == ["/compromissions", "/plan-action"]

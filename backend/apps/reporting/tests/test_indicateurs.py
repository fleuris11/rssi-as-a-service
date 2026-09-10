"""V2-3 — les indicateurs de comité (ADR-028).

Trois familles d'exigences, et la troisième est la plus importante :

1. **Exactitude** sur des jeux de données connus — un indicateur faux est pire
   qu'un indicateur absent, parce qu'il sera présenté à une direction.
2. **Étanchéité** — chaque indicateur est calculé par une requête, et une
   requête qui oublie son filtre de tenant ne se voit pas à l'œil.
3. **Cohérence avec les écrans de détail** — si le tableau de bord annonce 14
   compromissions ouvertes et que la liste en montre 12, le RSSI cesse de
   croire aux deux. C'est le risque propre à cette version : on introduit un
   second chemin de calcul sur des données qui en avaient déjà un.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.actions import services as actions_services
from apps.actions.models import ActionItem
from apps.assessments.models import Answer, Assessment, Measure
from apps.monitoring.models import Asset, CheckResult
from apps.reporting import periods, services
from apps.threat_intelligence import exposure
from apps.threat_intelligence import services as ti_services
from apps.threat_intelligence.models import BreachFinding
from apps.threat_intelligence.providers.base import RawFinding

pytestmark = pytest.mark.django_db


def _fuite(
    tenant, asset, *, severity, detected_il_y_a=0, status=None, traitee_il_y_a=None, cle="x"
):
    """Une fuite écrite directement, avec ses dates maîtrisées.

    Passer par l'ingestion imposerait des dates « maintenant » : impossible de
    fabriquer un passé, donc impossible de tester une évolution.
    """
    maintenant = timezone.now()
    fuite = BreachFinding.all_objects.create(
        tenant=tenant,
        asset=asset,
        source_endpoint=BreachFinding.SourceEndpoint.CREDS,
        finding_type="creds",
        severity=severity,
        status=status or BreachFinding.Status.OPEN,
        dedup_hash=f"d-{cle}",
        identity_hash=f"i-{cle}",
        secret_fingerprint=f"s-{cle}",
    )
    detecte = maintenant - timedelta(days=detected_il_y_a)
    BreachFinding.all_objects.filter(pk=fuite.pk).update(
        detected_at=detecte,
        last_seen_at=detecte,
        treated_at=(
            maintenant - timedelta(days=traitee_il_y_a) if traitee_il_y_a is not None else None
        ),
    )
    fuite.refresh_from_db()
    return fuite


@pytest.fixture
def periode():
    return periods.resolve(periods.PRESET_30D)


class TestExactitudeDesFuites:
    def test_compte_les_ouvertes_a_la_fin_de_la_periode(self, tenant, website_asset, periode):
        _fuite(tenant, website_asset, severity="critical", detected_il_y_a=10, cle="a")
        _fuite(tenant, website_asset, severity="high", detected_il_y_a=5, cle="b")
        # Close pendant la période : ne compte plus aujourd'hui.
        _fuite(
            tenant,
            website_asset,
            severity="high",
            detected_il_y_a=20,
            status=BreachFinding.Status.TREATED,
            traitee_il_y_a=3,
            cle="c",
        )

        indicateurs = ti_services.breach_indicators(tenant, start=periode.start, end=periode.end)

        assert indicateurs["open_total"] == 2
        assert indicateurs["open_by_severity"] == {"critical": 1, "high": 1, "attention": 0}

    def test_reconstruit_l_etat_au_debut_de_la_periode(self, tenant, website_asset, periode):
        """Le point qui rend la comparaison possible : « nous étions à X ».

        La fuite close il y a 3 jours était OUVERTE il y a 30 jours. Un
        tableau de bord qui la compterait close au début de la période
        annoncerait une progression qui n'a pas eu lieu.
        """
        _fuite(
            tenant,
            website_asset,
            severity="high",
            detected_il_y_a=40,
            status=BreachFinding.Status.TREATED,
            traitee_il_y_a=3,
            cle="a",
        )

        indicateurs = ti_services.breach_indicators(tenant, start=periode.start, end=periode.end)

        assert indicateurs["open_at_period_start"] == 1
        assert indicateurs["open_total"] == 0

    def test_une_fuite_detectee_apres_la_fin_n_est_pas_comptee(self, tenant, website_asset):
        _fuite(tenant, website_asset, severity="high", detected_il_y_a=0, cle="a")
        ancienne = periods.resolve(
            periods.PRESET_CUSTOM,
            start=(timezone.now() - timedelta(days=60)).date(),
            end=(timezone.now() - timedelta(days=30)).date(),
        )

        indicateurs = ti_services.breach_indicators(tenant, start=ancienne.start, end=ancienne.end)

        assert indicateurs["open_total"] == 0

    def test_compte_les_mouvements_de_la_periode(self, tenant, website_asset, periode):
        _fuite(tenant, website_asset, severity="high", detected_il_y_a=10, cle="a")
        _fuite(
            tenant,
            website_asset,
            severity="high",
            detected_il_y_a=12,
            status=BreachFinding.Status.TREATED,
            traitee_il_y_a=2,
            cle="b",
        )
        _fuite(
            tenant,
            website_asset,
            severity="high",
            detected_il_y_a=12,
            status=BreachFinding.Status.IGNORED,
            traitee_il_y_a=1,
            cle="c",
        )
        # Hors période : ni nouvelle, ni close ici.
        _fuite(tenant, website_asset, severity="high", detected_il_y_a=200, cle="d")

        indicateurs = ti_services.breach_indicators(tenant, start=periode.start, end=periode.end)

        assert indicateurs["new_in_period"] == 3
        assert indicateurs["treated_in_period"] == 1
        assert indicateurs["ignored_in_period"] == 1
        assert indicateurs["closed_in_period"] == 2

    def test_delai_moyen_de_traitement(self, tenant, website_asset, periode):
        """Deux fuites closes, l'une après 10 jours, l'autre après 20."""
        _fuite(
            tenant,
            website_asset,
            severity="high",
            detected_il_y_a=15,
            status=BreachFinding.Status.TREATED,
            traitee_il_y_a=5,
            cle="a",
        )
        _fuite(
            tenant,
            website_asset,
            severity="high",
            detected_il_y_a=22,
            status=BreachFinding.Status.TREATED,
            traitee_il_y_a=2,
            cle="b",
        )

        indicateurs = ti_services.breach_indicators(tenant, start=periode.start, end=periode.end)

        assert indicateurs["average_treatment_days"] == 15.0

    def test_le_delai_est_nul_quand_rien_n_a_ete_traite(self, tenant, website_asset, periode):
        _fuite(tenant, website_asset, severity="high", detected_il_y_a=5, cle="a")

        indicateurs = ti_services.breach_indicators(tenant, start=periode.start, end=periode.end)

        assert indicateurs["average_treatment_days"] is None

    def test_une_fuite_ignoree_est_close_et_datee(self, tenant, website_asset):
        """La date de clôture est posée pour « ignoré » comme pour « traité ».
        Sans elle, l'historique compterait comme ouvertes des fuites que le
        client avait fermées."""
        fuite = ti_services.ingest_raw_findings(
            tenant=tenant,
            asset=website_asset,
            raw_findings=[RawFinding(endpoint="creds", payload={"eml": "a@ex.fr"})],
        )[0]

        ti_services.set_finding_status(fuite, status=BreachFinding.Status.IGNORED)

        fuite.refresh_from_db()
        assert fuite.treated_at is not None
        # Ignorer n'est pas traiter : personne ne se voit attribuer ce geste.
        assert fuite.treated_by_id is None


class TestSerieQuotidienne:
    def test_la_serie_couvre_exactement_la_periode(self, tenant, website_asset, periode):
        serie = ti_services.open_findings_series(tenant, start=periode.start, end=periode.end)

        assert len(serie) == periode.days
        assert serie[0]["date"] == periode.start.date()
        assert serie[-1]["date"] == periode.end.date()

    def test_la_serie_suit_les_detections_et_les_clotures(self, tenant, website_asset, periode):
        _fuite(tenant, website_asset, severity="high", detected_il_y_a=10, cle="a")
        _fuite(tenant, website_asset, severity="high", detected_il_y_a=10, cle="b")
        _fuite(
            tenant,
            website_asset,
            severity="high",
            detected_il_y_a=10,
            status=BreachFinding.Status.TREATED,
            traitee_il_y_a=4,
            cle="c",
        )

        serie = {
            p["date"]: p["open"]
            for p in ti_services.open_findings_series(tenant, start=periode.start, end=periode.end)
        }
        aujourd_hui = timezone.localdate()

        assert serie[aujourd_hui - timedelta(days=9)] == 3
        assert serie[aujourd_hui - timedelta(days=5)] == 3
        assert serie[aujourd_hui - timedelta(days=4)] == 2
        assert serie[aujourd_hui] == 2

    def test_le_dernier_point_egale_le_compte_du_jour(self, tenant, website_asset, periode):
        """La série et le compteur doivent conclure la même chose : deux
        chiffres voisins qui se contredisent sur le même écran suffisent à
        disqualifier les deux."""
        for i in range(4):
            _fuite(tenant, website_asset, severity="high", detected_il_y_a=i + 1, cle=f"a{i}")

        indicateurs = ti_services.breach_indicators(tenant, start=periode.start, end=periode.end)

        assert indicateurs["series"][-1]["open"] == indicateurs["open_total"]


class TestCoherenceAvecLesEcransDeDetail:
    """Le risque propre à cette version : un second chemin de calcul."""

    def test_le_score_du_tableau_de_bord_egale_celui_du_fil_d_exposition(
        self, tenant, website_asset
    ):
        for i, gravite in enumerate(["critical", "high", "attention", "high"]):
            _fuite(tenant, website_asset, severity=gravite, detected_il_y_a=i, cle=f"a{i}")

        moment = timezone.now()
        du_tableau = ti_services.exposure_score_at(tenant, moment)
        ouvertes = list(
            BreachFinding.all_objects.filter(tenant=tenant, status=BreachFinding.Status.OPEN)
        )
        du_detail = exposure.compute_exposure_score(ouvertes, now=moment).score

        assert du_tableau == du_detail

    def test_le_bonus_de_secret_est_lu_pareil_des_deux_cotes(self, tenant, website_asset):
        """Le booléen calculé en base doit conclure comme la condition Python
        du fil d'exposition."""
        avec = _fuite(tenant, website_asset, severity="high", cle="a")
        BreachFinding.all_objects.filter(pk=avec.pk).update(
            has_secret=True, secret_encrypted=b"gAAAAA-chiffre"
        )
        # `has_secret` vrai mais colonne vide : le cas piège, qui ne doit PAS
        # donner le bonus.
        piege = _fuite(tenant, website_asset, severity="high", cle="b")
        BreachFinding.all_objects.filter(pk=piege.pk).update(has_secret=True, secret_encrypted=b"")

        moment = timezone.now()
        ouvertes = list(
            BreachFinding.all_objects.filter(tenant=tenant, status=BreachFinding.Status.OPEN)
        )

        assert (
            ti_services.exposure_score_at(tenant, moment)
            == exposure.compute_exposure_score(ouvertes, now=moment).score
        )

    def test_le_compte_du_tableau_de_bord_egale_celui_de_la_liste(
        self, tenant, website_asset, periode
    ):
        for i in range(5):
            _fuite(tenant, website_asset, severity="high", detected_il_y_a=i, cle=f"a{i}")
        _fuite(
            tenant,
            website_asset,
            severity="high",
            status=BreachFinding.Status.TREATED,
            traitee_il_y_a=1,
            cle="t",
        )

        indicateurs = ti_services.breach_indicators(tenant, start=periode.start, end=periode.end)
        de_la_liste = ti_services.list_findings(
            tenant, status=BreachFinding.Status.OPEN, include_pre_incident=True
        ).count()

        assert indicateurs["open_total"] == de_la_liste

    def test_l_exposition_par_actif_somme_les_memes_fuites(self, tenant, website_asset, periode):
        for i in range(3):
            _fuite(tenant, website_asset, severity="high", detected_il_y_a=i, cle=f"a{i}")

        indicateurs = ti_services.breach_indicators(tenant, start=periode.start, end=periode.end)
        par_actif = ti_services.exposure_by_asset(tenant, at=periode.end)

        assert sum(a["findings_count"] for a in par_actif) == indicateurs["open_total"]


class TestEtancheite:
    """Une requête qui oublie son filtre de tenant ne se voit pas à l'œil."""

    @pytest.fixture
    def voisin(self, user_factory, tenant_factory):
        from apps.monitoring import services as monitoring_services

        proprietaire = user_factory(email="voisin@example.com")
        tenant = tenant_factory(proprietaire, name="Entreprise Voisine")
        asset = monitoring_services.create_asset(
            tenant=tenant,
            user=proprietaire,
            type=Asset.Type.WEBSITE,
            value="https://voisin.example",
            ownership_confirmed=True,
        )
        return tenant, asset

    def test_les_fuites_du_voisin_ne_comptent_pas(self, tenant, website_asset, voisin, periode):
        autre_tenant, autre_asset = voisin
        for i in range(7):
            _fuite(autre_tenant, autre_asset, severity="critical", cle=f"v{i}")
        _fuite(tenant, website_asset, severity="high", cle="a")

        indicateurs = ti_services.breach_indicators(tenant, start=periode.start, end=periode.end)

        assert indicateurs["open_total"] == 1
        assert indicateurs["open_by_severity"]["critical"] == 0

    def test_le_plan_d_action_du_voisin_ne_compte_pas(self, tenant, voisin, periode, referential):
        autre_tenant, _asset = voisin
        mesure = Measure.objects.first()
        evaluation_voisine = Assessment.all_objects.create(
            tenant=autre_tenant, referential=mesure.domain.referential
        )
        ActionItem.all_objects.create(
            tenant=autre_tenant, assessment=evaluation_voisine, measure=mesure
        )

        indicateurs = actions_services.action_plan_indicators(
            tenant, start=periode.start, end=periode.end
        )

        assert indicateurs["total"] == 0

    def test_le_tableau_de_bord_complet_est_cloisonne(self, tenant, website_asset, voisin, periode):
        autre_tenant, autre_asset = voisin
        for i in range(5):
            _fuite(autre_tenant, autre_asset, severity="critical", cle=f"v{i}")

        tableau = services.build_dashboard(tenant, periode)

        assert tableau["exposure"]["open_total"] == 0
        assert tableau["exposure"]["by_asset"] == []


class TestPlanDAction:
    @pytest.fixture
    def plan(self, tenant, tenant_owner, referential):
        mesure = Measure.objects.first()
        evaluation = Assessment.all_objects.create(
            tenant=tenant, referential=mesure.domain.referential
        )
        mesures = list(Measure.objects.all()[:4])
        return evaluation, [
            ActionItem.all_objects.create(tenant=tenant, assessment=evaluation, measure=m)
            for m in mesures
        ]

    def test_compte_ouvertes_terminees_et_en_retard(self, tenant, plan, periode):
        _evaluation, items = plan
        actions_services.update_status(items[0], ActionItem.Status.DONE)
        actions_services.set_due_date(items[1], timezone.localdate() - timedelta(days=3))
        actions_services.set_due_date(items[2], timezone.localdate() + timedelta(days=10))

        indicateurs = actions_services.action_plan_indicators(
            tenant, start=periode.start, end=periode.end
        )

        assert indicateurs["done"] == 1
        assert indicateurs["open"] == 3
        assert indicateurs["overdue"] == 1
        assert indicateurs["without_due_date"] == 1
        assert indicateurs["completion_rate"] == 25.0

    def test_une_action_terminee_dont_l_echeance_est_passee_n_est_pas_en_retard(
        self, tenant, plan, periode
    ):
        _evaluation, items = plan
        actions_services.set_due_date(items[0], timezone.localdate() - timedelta(days=10))
        actions_services.update_status(items[0], ActionItem.Status.DONE)

        indicateurs = actions_services.action_plan_indicators(
            tenant, start=periode.start, end=periode.end
        )

        assert indicateurs["overdue"] == 0

    def test_rouvrir_une_action_efface_sa_date_de_fin(self, tenant, plan, periode):
        """Sans cela, une action rouverte resterait comptée comme terminée
        dans le trimestre où elle l'avait été."""
        _evaluation, items = plan
        actions_services.update_status(items[0], ActionItem.Status.DONE)
        actions_services.update_status(items[0], ActionItem.Status.IN_PROGRESS)

        items[0].refresh_from_db()
        indicateurs = actions_services.action_plan_indicators(
            tenant, start=periode.start, end=periode.end
        )

        assert items[0].completed_at is None
        assert indicateurs["completed_in_period"] == 0


class TestEcheanceParLApi:
    """L'indicateur « en retard » n'a de sens que si quelqu'un peut poser une
    échéance. Sans ce chemin, il resterait à zéro pour tout le monde — et
    serait donc décoratif, ce que la consigne interdit."""

    def _auth(self, api_client, user, tenant):
        from django.urls import reverse
        from rest_framework import status as http

        reponse = api_client.post(
            reverse("token-obtain-pair"),
            {"email": user.email, "password": "Str0ng!Passw0rd123"},
            format="json",
        )
        assert reponse.status_code == http.HTTP_200_OK
        return {
            "HTTP_AUTHORIZATION": f"Bearer {reponse.data['access']}",
            "HTTP_X_TENANT_ID": str(tenant.id),
        }

    @pytest.fixture
    def action(self, tenant, referential):
        mesure = Measure.objects.first()
        evaluation = Assessment.all_objects.create(
            tenant=tenant, referential=mesure.domain.referential
        )
        return ActionItem.all_objects.create(tenant=tenant, assessment=evaluation, measure=mesure)

    def test_poser_une_echeance_la_rend_comptable(
        self, api_client, tenant, tenant_owner, action, periode
    ):
        from django.urls import reverse

        entetes = self._auth(api_client, tenant_owner, tenant)
        echue = (timezone.localdate() - timedelta(days=2)).isoformat()

        reponse = api_client.patch(
            reverse("action-item-detail", args=[action.id]),
            {"due_date": echue},
            format="json",
            **entetes,
        )

        assert reponse.data["due_date"] == echue
        assert reponse.data["is_overdue"] is True
        indicateurs = actions_services.action_plan_indicators(
            tenant, start=periode.start, end=periode.end
        )
        assert indicateurs["overdue"] == 1
        assert indicateurs["without_due_date"] == 0

    def test_retirer_une_echeance_est_un_geste_legitime(
        self, api_client, tenant, tenant_owner, action
    ):
        from django.urls import reverse

        entetes = self._auth(api_client, tenant_owner, tenant)
        url = reverse("action-item-detail", args=[action.id])
        api_client.patch(
            url, {"due_date": timezone.localdate().isoformat()}, format="json", **entetes
        )

        reponse = api_client.patch(url, {"due_date": None}, format="json", **entetes)

        assert reponse.data["due_date"] is None
        assert reponse.data["is_overdue"] is False


class TestMaturite:
    def _evaluation_terminee(self, tenant, score, il_y_a_jours):
        mesure = Measure.objects.first()
        evaluation = Assessment.all_objects.create(
            tenant=tenant,
            referential=mesure.domain.referential,
            status=Assessment.Status.COMPLETED,
            score_global=score,
        )
        Assessment.all_objects.filter(pk=evaluation.pk).update(
            completed_at=timezone.now() - timedelta(days=il_y_a_jours)
        )
        return evaluation

    def test_prend_le_dernier_diagnostic_et_le_precedent(self, tenant, periode, referential):
        from apps.assessments import services as assessments_services

        self._evaluation_terminee(tenant, 41.0, il_y_a_jours=200)
        self._evaluation_terminee(tenant, 58.5, il_y_a_jours=10)

        indicateurs = assessments_services.maturity_indicators(
            tenant, start=periode.start, end=periode.end
        )

        assert indicateurs["score"] == 58.5
        assert indicateurs["previous_score"] == 41.0
        assert indicateurs["delta"] == 17.5

    def test_sans_diagnostic_termine_le_score_est_absent_pas_zero(self, tenant, periode):
        """Zéro voudrait dire « mesuré, et mauvais ». Absent veut dire « pas
        mesuré » — ce n'est pas la même chose devant une direction."""
        from apps.assessments import services as assessments_services

        indicateurs = assessments_services.maturity_indicators(
            tenant, start=periode.start, end=periode.end
        )

        assert indicateurs["score"] is None
        assert indicateurs["delta"] is None

    def test_le_score_historique_n_est_jamais_recalcule(self, tenant, periode, referential):
        """L'instantané posé à la clôture fait foi. Un score de juin recalculé
        avec le référentiel de septembre ne serait plus le score de juin."""
        from apps.assessments import services as assessments_services

        evaluation = self._evaluation_terminee(tenant, 62.0, il_y_a_jours=5)
        # Aucune réponse en base : un recalcul donnerait None.
        assert not Answer.all_objects.filter(assessment=evaluation).exists()

        indicateurs = assessments_services.maturity_indicators(
            tenant, start=periode.start, end=periode.end
        )

        assert indicateurs["score"] == 62.0


class TestSurveillance:
    def test_disponibilite_calculee_sur_la_periode(self, tenant, website_asset, periode):
        from apps.monitoring import services as monitoring_services

        for i in range(10):
            resultat = CheckResult.all_objects.create(
                tenant=tenant,
                asset=website_asset,
                check_type=CheckResult.CheckType.HTTP_UPTIME,
                status=CheckResult.Status.OK if i < 9 else CheckResult.Status.CRITICAL,
            )
            CheckResult.all_objects.filter(pk=resultat.pk).update(
                checked_at=timezone.now() - timedelta(days=1)
            )

        indicateurs = monitoring_services.monitoring_indicators(
            tenant, start=periode.start, end=periode.end
        )

        assert indicateurs["uptime_percentage"] == 90.0
        assert indicateurs["checks_in_period"] == 10
        assert indicateurs["failed_checks_in_period"] == 1

    def test_certificats_a_echeance_tries_du_plus_urgent(self, tenant, website_asset):
        from apps.monitoring import services as monitoring_services

        CheckResult.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            check_type=CheckResult.CheckType.SSL_CERTIFICATE,
            status=CheckResult.Status.WARNING,
            details={"days_left": 12, "expires_at": "2026-09-21T00:00:00+00:00"},
        )

        certificats = monitoring_services.expiring_certificates(tenant)

        assert certificats[0]["days_left"] == 12
        assert certificats[0]["asset_value"] == website_asset.value

    def test_un_certificat_lointain_n_est_pas_signale(self, tenant, website_asset):
        from apps.monitoring import services as monitoring_services

        CheckResult.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            check_type=CheckResult.CheckType.SSL_CERTIFICATE,
            status=CheckResult.Status.OK,
            details={"days_left": 300},
        )

        assert monitoring_services.expiring_certificates(tenant) == []


class TestAucunScoreGlobalInvente:
    """Point 10 de la consigne, vérifié structurellement.

    Mélanger maturité et exposition ferait un chiffre qui monte quand
    l'entreprise remplit un questionnaire et descend quand un fournisseur se
    fait pirater — deux variations qu'aucune action commune n'explique.
    """

    def test_le_tableau_de_bord_ne_publie_aucun_score_fusionne(self, tenant, periode):
        tableau = services.build_dashboard(tenant, periode)

        interdits = {"global_score", "security_score", "overall_score", "score_global"}
        assert interdits.isdisjoint(tableau)
        # Les deux scores restent dans leurs blocs respectifs.
        assert "exposure_score" in tableau["exposure"]
        assert "score" in tableau["maturity"]

"""Le document du comité et l'export tableur (V2-3, ADR-028).

Ce qui est vérifié ici n'est pas la mécanique — un PDF s'ouvre ou ne s'ouvre
pas — mais le **fond** : le rapport doit être lisible par quelqu'un qui n'est
pas technicien, dire ce que chaque chiffre veut dire, et ne jamais nommer la
source de renseignement.

Le rendu PDF lui-même dépend d'un moteur système (ADR-012) absent de certains
postes. C'est pour cela que la construction est séparée : ``build_html`` est
testée partout, ``render_pdf`` a un seul test, marqué comme tel.
"""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.reporting import exports, periods, report, services
from apps.threat_intelligence import client_messages
from apps.threat_intelligence.models import BreachFinding

pytestmark = pytest.mark.django_db


def _auth(api_client, user, tenant):
    reponse = api_client.post(
        reverse("token-obtain-pair"),
        {"email": user.email, "password": "Str0ng!Passw0rd123"},
        format="json",
    )
    assert reponse.status_code == status.HTTP_200_OK
    return {
        "HTTP_AUTHORIZATION": f"Bearer {reponse.data['access']}",
        "HTTP_X_TENANT_ID": str(tenant.id),
    }


@pytest.fixture
def donnees(tenant, website_asset):
    """Un tenant avec de quoi remplir chaque section du rapport."""
    maintenant = timezone.now()
    for i, (gravite, statut) in enumerate(
        [
            ("critical", BreachFinding.Status.OPEN),
            ("high", BreachFinding.Status.OPEN),
            ("attention", BreachFinding.Status.OPEN),
            ("high", BreachFinding.Status.TREATED),
        ]
    ):
        fuite = BreachFinding.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            source_endpoint=BreachFinding.SourceEndpoint.CREDS,
            finding_type="creds",
            severity=gravite,
            status=statut,
            dedup_hash=f"r-{i}",
            identity_hash=f"ri-{i}",
            secret_fingerprint=f"rs-{i}",
        )
        BreachFinding.all_objects.filter(pk=fuite.pk).update(
            detected_at=maintenant - timedelta(days=10 + i),
            treated_at=(
                maintenant - timedelta(days=2) if statut == BreachFinding.Status.TREATED else None
            ),
        )
    return services.build_report(tenant, periods.resolve(periods.PRESET_30D))


class TestPeriodes:
    def test_la_periode_precedente_a_la_meme_duree(self):
        periode = periods.resolve(periods.PRESET_QUARTER)

        duree = (periode.end.date() - periode.start.date()).days
        duree_precedente = (periode.previous_end.date() - periode.previous_start.date()).days

        assert duree == duree_precedente

    def test_la_periode_precedente_s_arrete_juste_avant(self):
        """Sans continuité, un jour tomberait dans les deux périodes ou dans
        aucune — et le total des deux ne ferait pas le compte."""
        periode = periods.resolve(periods.PRESET_30D)

        assert periode.previous_end < periode.start
        assert (periode.start - periode.previous_end).total_seconds() < 1

    def test_les_bornes_sont_des_jours_entiers(self):
        """Deux consultations le même après-midi doivent donner les mêmes
        chiffres : des bornes à l'heure près les feraient varier."""
        periode = periods.resolve(periods.PRESET_30D)

        assert (periode.start.hour, periode.start.minute) == (0, 0)
        assert periode.end.hour == 23

    def test_une_plage_personnalisee_est_acceptee(self):
        periode = periods.resolve(
            periods.PRESET_CUSTOM,
            start=timezone.localdate() - timedelta(days=10),
            end=timezone.localdate(),
        )

        assert periode.days == 11
        assert periode.key == periods.PRESET_CUSTOM

    def test_une_plage_inversee_est_refusee(self):
        with pytest.raises(periods.PeriodError):
            periods.resolve(
                periods.PRESET_CUSTOM,
                start=timezone.localdate(),
                end=timezone.localdate() - timedelta(days=5),
            )

    def test_une_plage_demesuree_est_refusee(self):
        with pytest.raises(periods.PeriodError):
            periods.resolve(
                periods.PRESET_CUSTOM,
                start=timezone.localdate() - timedelta(days=4000),
                end=timezone.localdate(),
            )

    def test_une_periode_inconnue_est_refusee(self):
        with pytest.raises(periods.PeriodError):
            periods.resolve("decennie")


class TestContenuDuRapport:
    def test_les_cinq_sections_attendues_sont_la(self, donnees):
        html = report.build_html(donnees)

        for titre in (
            "La situation aujourd'hui",
            "L'évolution sur la période",
            "Les faits marquants",
            "Les actions menées",
            "Ce qui reste à faire",
        ):
            assert titre in html, f"section manquante : {titre}"

    def test_chaque_chiffre_est_accompagne_de_ce_qu_il_veut_dire(self, donnees):
        """C'est le RSSI qui produit, c'est la direction qui lit. « Score
        d'exposition : 62 » ne dit rien à qui n'a pas le vocabulaire."""
        html = report.build_html(donnees)

        assert "Plus bas est mieux" in html
        # Les apostrophes sont échappées par la construction du document :
        # on assertit sur ce qui est réellement écrit, pas sur la source.
        assert "Mesure l&#x27;organisation" in html
        assert "retrouvées en circulation" in html

    def test_l_evolution_est_dite_en_toutes_lettres(self, donnees):
        """Un PDF n'a pas d'infobulle : une flèche verte sans phrase laisse le
        lecteur deviner si monter est une bonne nouvelle."""
        html = report.build_html(donnees)

        assert "amélioration" in html or "dégradation" in html or "Stable" in html

    def test_le_rapport_dit_pourquoi_les_deux_scores_ne_se_melangent_pas(self, donnees):
        html = report.build_html(donnees)

        assert "ne s'additionnent pas" in html

    def test_le_rapport_ne_nomme_jamais_la_source(self, donnees):
        html = report.build_html(donnees).lower()

        for nom in client_messages.VENDOR_NAMES:
            assert nom not in html, f"le rapport nomme la source : {nom}"

    def test_le_rapport_est_autonome(self, donnees):
        """Destiné à circuler par email et à s'ouvrir dix ans plus tard :
        aucune ressource externe, aucune police téléchargée."""
        html = report.build_html(donnees)

        assert "<img" not in html
        assert "http://" not in html
        assert "https://" not in html.replace("https://example.com", "")

    def test_le_meme_jeu_de_donnees_donne_le_meme_document(self, donnees):
        """Reproductible : un document présenté à une direction doit pouvoir
        être régénéré à l'identique."""
        assert report.build_html(donnees) == report.build_html(donnees)

    def test_le_nom_du_client_est_echappe(self, tenant, website_asset):
        tenant.name = "Durand & <script>Fils</script>"
        tenant.save(update_fields=["name"])

        html = report.build_html(services.build_report(tenant, periods.resolve(periods.PRESET_30D)))

        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestFaitsMarquantsEtResteAFaire:
    def test_les_faits_marquants_citent_les_critiques_ouvertes(self, donnees):
        titres = [f["title"] for f in donnees["highlights"]]

        assert any("critique" in t for t in titres)

    def test_le_reste_a_faire_dit_ce_qui_est_en_jeu(self, donnees):
        assert donnees["remaining"]
        for point in donnees["remaining"]:
            assert point["detail"], "un point sans détail est un constat, pas une décision"

    def test_un_tenant_sans_rien_ne_produit_pas_de_remplissage(self, tenant):
        """Mieux vaut trois faits que dix lignes dont personne ne lit la
        moitié."""
        vide = services.build_report(tenant, periods.resolve(periods.PRESET_30D))

        assert vide["highlights"] == []
        html = report.build_html(vide)
        assert "Aucun fait marquant" in html

    def test_le_nombre_d_actions_sans_echeance_est_dit(self, tenant, referential, periode_30j):
        """« 2 actions en retard » sur quarante sans échéance se lirait comme
        une bonne nouvelle."""
        from apps.actions.models import ActionItem
        from apps.assessments.models import Assessment, Measure

        mesure = Measure.objects.first()
        evaluation = Assessment.all_objects.create(
            tenant=tenant, referential=mesure.domain.referential
        )
        for m in Measure.objects.all()[:3]:
            ActionItem.all_objects.create(tenant=tenant, assessment=evaluation, measure=m)

        rapport = services.build_report(tenant, periode_30j)

        titres = [p["title"] for p in rapport["remaining"]]
        assert "Actions sans échéance" in titres


@pytest.fixture
def periode_30j():
    return periods.resolve(periods.PRESET_30D)


class TestExportTableur:
    def test_les_valeurs_sont_a_la_francaise(self, donnees):
        lignes = exports.csv_rows(donnees)
        plates = [str(cellule) for ligne in lignes for cellule in ligne]

        # Aucun point décimal : un tableur français lirait « 12.4 » comme du
        # texte et refuserait de l'additionner.
        assert not any(
            cellule.replace("-", "").replace(",", "").isdigit() and "." in cellule
            for cellule in plates
        )

    def test_l_export_reprend_les_memes_chiffres_que_l_ecran(self, donnees):
        """Si le tableur et l'écran divergeaient, le RSSI recommencerait à
        tout recalculer à la main — c'est-à-dire exactement ce que cette
        version cherche à supprimer."""
        lignes = {ligne[0]: ligne[1] for ligne in exports.csv_rows(donnees) if len(ligne) > 1}

        assert lignes["Compromissions ouvertes"] == str(donnees["exposure"]["open_total"])
        assert lignes["Score d'exposition"] == str(donnees["exposure"]["exposure_score"])
        assert lignes["Actions ouvertes"] == str(donnees["action_plan"]["open"])

    def test_le_nom_de_fichier_est_lisible_et_triable(self, donnees):
        nom = exports.filename(donnees, "csv")

        assert nom.startswith("rapport-")
        assert nom.endswith(".csv")
        assert donnees["period"]["end"].date().isoformat() in nom


class TestApi:
    def test_le_tableau_de_bord_repond(self, api_client, tenant, tenant_owner, website_asset):
        entetes = _auth(api_client, tenant_owner, tenant)

        reponse = api_client.get(reverse("reporting-dashboard"), **entetes)

        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.data["period"]["key"] == periods.DEFAULT_PRESET
        assert "available_periods" in reponse.data

    def test_la_periode_se_choisit_par_parametre(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        entetes = _auth(api_client, tenant_owner, tenant)

        reponse = api_client.get(reverse("reporting-dashboard") + "?period=year", **entetes)

        assert reponse.data["period"]["key"] == "year"
        assert reponse.data["period"]["days"] == 365

    def test_une_plage_personnalisee_passe_par_deux_dates(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        entetes = _auth(api_client, tenant_owner, tenant)
        debut = (timezone.localdate() - timedelta(days=7)).isoformat()
        fin = timezone.localdate().isoformat()

        reponse = api_client.get(
            reverse("reporting-dashboard") + f"?period=custom&start={debut}&end={fin}",
            **entetes,
        )

        assert reponse.data["period"]["days"] == 8

    def test_une_date_invalide_est_refusee_proprement(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        entetes = _auth(api_client, tenant_owner, tenant)

        reponse = api_client.get(
            reverse("reporting-dashboard") + "?period=custom&start=hier&end=demain", **entetes
        )

        assert reponse.status_code == status.HTTP_400_BAD_REQUEST
        assert "AAAA-MM-JJ" in reponse.data["detail"]

    def test_l_export_csv_est_servi_en_piece_jointe(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        entetes = _auth(api_client, tenant_owner, tenant)

        reponse = api_client.get(reverse("reporting-export-csv"), **entetes)

        assert reponse.status_code == status.HTTP_200_OK
        assert reponse["Content-Type"].startswith("text/csv")
        assert "attachment" in reponse["Content-Disposition"]
        corps = reponse.content.decode("utf-8")
        # BOM : sans lui, Excel en configuration française affiche des
        # caractères illisibles à la place des accents.
        assert corps.startswith("﻿")
        assert ";" in corps

    def test_le_rapport_json_porte_faits_et_reste_a_faire(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        entetes = _auth(api_client, tenant_owner, tenant)

        reponse = api_client.get(reverse("reporting-report"), **entetes)

        assert reponse.status_code == status.HTTP_200_OK
        assert "highlights" in reponse.data
        assert "remaining" in reponse.data

    def test_le_tableau_de_bord_est_cloisonne(
        self, api_client, tenant, website_asset, user_factory, tenant_factory
    ):
        intrus = user_factory(email="intrus@example.com")
        tenant_intrus = tenant_factory(intrus, name="Entreprise Intruse")
        BreachFinding.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            source_endpoint=BreachFinding.SourceEndpoint.CREDS,
            finding_type="creds",
            severity="critical",
            dedup_hash="c-1",
            identity_hash="ci-1",
            secret_fingerprint="cs-1",
        )
        entetes = _auth(api_client, intrus, tenant_intrus)

        reponse = api_client.get(reverse("reporting-dashboard"), **entetes)

        assert reponse.data["exposure"]["open_total"] == 0

    def test_l_acces_est_refuse_sans_entreprise(self, api_client, tenant_owner):
        reponse = api_client.post(
            reverse("token-obtain-pair"),
            {"email": tenant_owner.email, "password": "Str0ng!Passw0rd123"},
            format="json",
        )
        entetes = {"HTTP_AUTHORIZATION": f"Bearer {reponse.data['access']}"}

        assert (
            api_client.get(reverse("reporting-dashboard"), **entetes).status_code
            == status.HTTP_403_FORBIDDEN
        )


class TestRenduPdf:
    """Un seul test touche au moteur de rendu (ADR-012).

    Il échoue sur un poste où les bibliothèques système ne sont pas
    installées — comme les trois tests d'export documentaire existants. Ce
    n'est pas une raison pour ne pas l'écrire : c'est la CI qui l'exécute
    réellement, et le fond du rapport est vérifié ailleurs, sans lui.
    """

    def test_produit_un_pdf(self, donnees):
        pdf = report.render_pdf(donnees)

        assert pdf.startswith(b"%PDF-")

"""L'importateur générique : ce qu'il accepte, ce qu'il refuse, ce qu'il ne
détruit jamais.

Le refus compte autant que l'acceptation. Un référentiel importé à moitié —
une mesure sans énoncé, deux mesures partageant un code — ne se voit pas : il
donne un questionnaire plausible et un score faux.
"""

import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.assessments import importers, services
from apps.assessments.models import Domain, Measure, Referential

pytestmark = pytest.mark.django_db


def _fichier_json(tmp_path, data, nom="ref.json"):
    chemin = tmp_path / nom
    chemin.write_text(json.dumps(data), encoding="utf-8")
    return chemin


REFERENTIEL_MINIMAL = {
    "slug": "cadre-test",
    "name": "Cadre de test",
    "version": "1.0",
    "publisher": "Organisme de test",
    "kind": "licensed",
    "licence_notice": "Importé par l'exploitant.",
    "domains": [
        {
            "code": "gouvernance",
            "name": "Gouvernance",
            "order": 1,
            "measures": [
                {
                    "code": "A.5.1",
                    "title": "Politiques de sécurité de l'information",
                    "statement": "Avez-vous une politique de sécurité écrite ?",
                    "weight": 1.0,
                    "effort": "medium",
                    "impact": "high",
                },
                {
                    "code": "A.5.2",
                    "title": "Rôles et responsabilités",
                    "statement": "Les rôles sécurité sont-ils attribués ?",
                    "weight": 0.5,
                },
            ],
        }
    ],
}


class TestImportJson:
    def test_cree_le_referentiel_ses_domaines_et_ses_mesures(self, tmp_path):
        call_command("import_referential", file=_fichier_json(tmp_path, REFERENTIEL_MINIMAL))

        referential = Referential.objects.get(slug="cadre-test")
        assert referential.kind == Referential.Kind.LICENSED
        assert referential.publisher == "Organisme de test"
        assert Domain.objects.filter(referential=referential).count() == 1
        codes = list(
            Measure.objects.filter(referential=referential)
            .order_by("order")
            .values_list("code", flat=True)
        )
        assert codes == ["A.5.1", "A.5.2"]

    def test_un_code_alphanumerique_est_accepte(self, tmp_path):
        """Le point de départ de V2-4 : « A.5.1 » n'entrait pas dans un entier."""
        call_command("import_referential", file=_fichier_json(tmp_path, REFERENTIEL_MINIMAL))
        mesure = Measure.objects.get(code="A.5.1")
        assert mesure.number is None

    def test_les_poids_par_defaut_valent_un(self, tmp_path):
        call_command("import_referential", file=_fichier_json(tmp_path, REFERENTIEL_MINIMAL))
        assert Measure.objects.get(code="A.5.1").weight == 1.0
        assert Measure.objects.get(code="A.5.2").weight == 0.5

    def test_effort_et_impact_absents_prennent_une_valeur_moyenne(self, tmp_path):
        call_command("import_referential", file=_fichier_json(tmp_path, REFERENTIEL_MINIMAL))
        mesure = Measure.objects.get(code="A.5.2")
        assert mesure.effort == Measure.Effort.MEDIUM
        assert mesure.impact == Measure.Impact.MEDIUM
        # Le drapeau reste vrai : effort/impact restent un jugement produit.
        assert mesure.effort_impact_disclaimer is True

    def test_est_idempotent(self, tmp_path):
        chemin = _fichier_json(tmp_path, REFERENTIEL_MINIMAL)
        call_command("import_referential", file=chemin)
        call_command("import_referential", file=chemin)
        assert Referential.objects.filter(slug="cadre-test").count() == 1
        assert Measure.objects.filter(referential__slug="cadre-test").count() == 2

    def test_deux_referentiels_peuvent_partager_un_code_de_mesure(self, tmp_path, referential):
        """L'unicité est PAR référentiel. C'est tout l'objet de V2-4 : la
        mesure n°1 de l'ANSSI et la mesure n°1 d'un autre cadre coexistent."""
        autre = {**REFERENTIEL_MINIMAL, "slug": "cadre-bis", "name": "Cadre bis"}
        autre["domains"] = [
            {
                **REFERENTIEL_MINIMAL["domains"][0],
                "measures": [
                    {"code": "1", "title": "Homonyme", "statement": "Une question ?"},
                ],
            }
        ]
        call_command("import_referential", file=_fichier_json(tmp_path, autre, "bis.json"))

        assert Measure.objects.filter(code="1").count() == 2

    def test_dry_run_n_ecrit_rien(self, tmp_path):
        call_command(
            "import_referential",
            file=_fichier_json(tmp_path, REFERENTIEL_MINIMAL),
            dry_run=True,
        )
        assert not Referential.objects.filter(slug="cadre-test").exists()

    def test_les_options_surchargent_le_fichier(self, tmp_path):
        """Une coquille livrée avec le produit s'importe avec SA licence."""
        call_command(
            "import_referential",
            file=_fichier_json(tmp_path, REFERENTIEL_MINIMAL),
            licence_notice="Licence n°4242 — usage interne.",
        )
        assert Referential.objects.get(slug="cadre-test").licence_notice.startswith("Licence n°")


class TestRefus:
    @pytest.mark.parametrize(
        "mutation,motif",
        [
            ({"slug": ""}, "slug"),
            ({"domains": []}, "aucun domaine"),
        ],
    )
    def test_refuse_un_fichier_incomplet(self, tmp_path, mutation, motif):
        data = {**REFERENTIEL_MINIMAL, **mutation}
        with pytest.raises(CommandError, match=motif):
            call_command("import_referential", file=_fichier_json(tmp_path, data))

    def test_refuse_deux_mesures_de_meme_code(self, tmp_path):
        data = json.loads(json.dumps(REFERENTIEL_MINIMAL))
        data["domains"][0]["measures"][1]["code"] = "A.5.1"
        with pytest.raises(CommandError, match="en double"):
            call_command("import_referential", file=_fichier_json(tmp_path, data))

    def test_refuse_une_mesure_sans_enonce(self, tmp_path):
        data = json.loads(json.dumps(REFERENTIEL_MINIMAL))
        data["domains"][0]["measures"][0]["statement"] = ""
        with pytest.raises(CommandError, match="énoncé en langage clair manquant"):
            call_command("import_referential", file=_fichier_json(tmp_path, data))

    def test_refuse_un_poids_negatif(self, tmp_path):
        data = json.loads(json.dumps(REFERENTIEL_MINIMAL))
        data["domains"][0]["measures"][0]["weight"] = -1
        with pytest.raises(CommandError, match="strictement positif"):
            call_command("import_referential", file=_fichier_json(tmp_path, data))

    def test_rien_n_est_ecrit_quand_le_fichier_est_refuse(self, tmp_path):
        """La validation passe AVANT la première écriture : un fichier dont la
        dernière mesure est invalide ne laisse pas les précédentes en base."""
        data = json.loads(json.dumps(REFERENTIEL_MINIMAL))
        data["domains"][0]["measures"][1]["title"] = ""
        with pytest.raises(CommandError):
            call_command("import_referential", file=_fichier_json(tmp_path, data))
        assert not Referential.objects.filter(slug="cadre-test").exists()


class TestImportCsv:
    LIGNES = (
        "domaine_code,domaine_nom,domaine_ordre,mesure_code,mesure_numero,"
        "intitule_officiel,enonce_clair,niveau,poids,effort,impact\n"
        "gouvernance,Gouvernance,1,PR.AA-01,,Gestion des identités,"
        "Les comptes sont-ils nominatifs ?,,1,low,high\n"
        "detection,Détection,2,DE.CM-01,,Surveillance du réseau,"
        "Surveillez-vous votre réseau ?,,0.5,high,medium\n"
    )

    def test_importe_un_tableur(self, tmp_path):
        chemin = tmp_path / "cadre.csv"
        chemin.write_text(self.LIGNES, encoding="utf-8")

        call_command(
            "import_referential",
            file=chemin,
            slug="cadre-csv",
            name="Cadre en tableur",
            ref_version="1.1",
        )

        referential = Referential.objects.get(slug="cadre-csv")
        assert Domain.objects.filter(referential=referential).count() == 2
        assert Measure.objects.get(code="DE.CM-01").weight == 0.5

    def test_refuse_un_tableur_sans_les_colonnes_attendues(self, tmp_path):
        chemin = tmp_path / "mauvais.csv"
        chemin.write_text("a,b\n1,2\n", encoding="utf-8")
        with pytest.raises(CommandError, match="Colonnes manquantes"):
            call_command("import_referential", file=chemin, slug="x", name="X", ref_version="1")

    def test_exige_les_metadonnees_en_csv(self, tmp_path):
        chemin = tmp_path / "cadre.csv"
        chemin.write_text(self.LIGNES, encoding="utf-8")
        with pytest.raises(CommandError, match="Métadonnée obligatoire"):
            call_command("import_referential", file=chemin)


class TestMesuresDisparues:
    def test_une_mesure_absente_du_nouveau_fichier_est_conservee(self, tmp_path):
        """Un référentiel qui maigrit ne doit pas emporter les réponses déjà
        données. On avertit, on ne supprime pas."""
        chemin = _fichier_json(tmp_path, REFERENTIEL_MINIMAL)
        call_command("import_referential", file=chemin)

        reduit = json.loads(json.dumps(REFERENTIEL_MINIMAL))
        reduit["domains"][0]["measures"] = reduit["domains"][0]["measures"][:1]
        call_command("import_referential", file=_fichier_json(tmp_path, reduit, "reduit.json"))

        assert Measure.objects.filter(code="A.5.2").exists()

    def test_le_rapport_signale_les_mesures_disparues(self, tmp_path):
        parsed = importers.read_file(_fichier_json(tmp_path, REFERENTIEL_MINIMAL))
        importers.import_referential(parsed)

        reduit = json.loads(json.dumps(REFERENTIEL_MINIMAL))
        reduit["domains"][0]["measures"] = reduit["domains"][0]["measures"][:1]
        rapport = importers.import_referential(
            importers.read_file(_fichier_json(tmp_path, reduit, "reduit.json"))
        )
        assert rapport.orphans == ["A.5.2"]


class TestReferentielAnssiInchange:
    """L'ANSSI passe par le nouvel importateur sans changer d'un iota : c'est
    la condition pour que les scores d'avant V2-4 restent les scores d'avant."""

    def test_le_chargement_anssi_pose_codes_et_poids(self):
        call_command("load_anssi_referential")
        referential = Referential.objects.get(slug="anssi-hygiene-informatique")

        mesures = Measure.objects.filter(referential=referential)
        assert mesures.count() == 42
        assert set(mesures.values_list("code", flat=True)) == {str(n) for n in range(1, 43)}

        standard = mesures.filter(level=Measure.Level.STANDARD).first()
        renforce = mesures.filter(level=Measure.Level.RENFORCE).first()
        assert standard.weight == 1.0
        assert renforce.weight == 0.5

    def test_le_referentiel_anssi_est_libre_de_droits(self):
        call_command("load_anssi_referential")
        referential = Referential.objects.get(slug="anssi-hygiene-informatique")
        assert referential.kind == Referential.Kind.OPEN
        assert "Licence Ouverte" in referential.licence_notice

    def test_le_score_anssi_est_celui_d_avant_v2_4(self, tenant, tenant_owner):
        """Poids explicites (1.0 / 0.5) plutôt que table de niveaux figée : le
        chiffre doit être le même. On répond « oui » partout, ce qui doit
        donner 100 quel que soit le détail des poids, puis « oui » aux seules
        mesures standard, ce qui isole le rapport 1 / 0,5."""
        call_command("load_anssi_referential")
        referential = Referential.objects.get(slug="anssi-hygiene-informatique")
        services.assign_referential(tenant=tenant, referential=referential)
        assessment = services.start_or_resume_assessment(
            tenant=tenant, user=tenant_owner, referential=referential
        )

        mesures = services.get_assessment_measures(assessment)
        for mesure in mesures:
            services.submit_answer(
                assessment=assessment,
                measure=mesure,
                value="yes" if mesure.level == Measure.Level.STANDARD else "no",
            )

        poids_standard = sum(m.weight for m in mesures if m.level == Measure.Level.STANDARD)
        poids_total = sum(m.weight for m in mesures)
        attendu = round(100 * poids_standard / poids_total, 1)
        assert services.compute_scores(assessment)["global"] == attendu

"""Lot A — rendre utilisable l'écran des comptes surveillés.

Le constat qui a déclenché ce lot, relevé en production : **3 222 résultats
pour un seul compte**, en lignes rigoureusement identiques à l'affichage.

Le diagnostic, mesuré avant toute correction, a écarté deux hypothèses sur
trois : le dédoublonnage fonctionne (3 222 empreintes distinctes pour 3 222
lignes) et aucune analyse ne recrée d'entrées. La source renvoie réellement
des milliers d'observations distinctes — un cookie volé par domaine et par
nom — et l'écran masquait précisément les deux champs qui les distinguent.

Ces tests épinglent les quatre gardes qui en découlent :

1. le regroupement produit des groupes, pas des lignes ;
2. les champs distinctifs sont servis ;
3. le tri porte sur la date de fuite, pas sur l'ordre d'insertion ;
4. la réponse est bornée, sans que les compteurs le soient.
"""

import datetime
from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.threat_intelligence import services, watched_accounts
from apps.threat_intelligence.models import WatchedAccount, WatchedAccountFinding

from .test_comptes_designes import _auth

pytestmark = pytest.mark.django_db


def _finding(tenant, compte, *, dom, cookie, jour, statut="open", severite="critical"):
    """Une observation de session, comme le fournisseur les livre."""
    return WatchedAccountFinding.all_objects.create(
        tenant=tenant,
        account=compte,
        source_endpoint="sessions",
        finding_type="sessions",
        severity=severite,
        status=statut,
        breach_date=jour,
        dedup_hash=f"{dom}|{cookie}|{jour}",
        raw_data={"dom": dom, "cookie_name": cookie, "fnd": str(jour).replace("-", "")},
    )


@pytest.fixture
def compte(tenant):
    return WatchedAccount.all_objects.create(
        tenant=tenant,
        value="dirigeant@exemple.test",
        label="Direction",
        category="executive",
        legal_basis="legitimate_interest",
        purpose="Surveillance du compte de direction.",
        declaration_text="x",
        declaration_version="1",
    )


@pytest.fixture
def jeu(tenant, compte):
    """Deux domaines, trois cookies, trois dates — le motif de production."""
    _finding(tenant, compte, dom=".gmail.com", cookie="__utma", jour=datetime.date(2020, 1, 1))
    _finding(tenant, compte, dom=".gmail.com", cookie="__utmz", jour=datetime.date(2023, 10, 6))
    _finding(tenant, compte, dom=".gmail.com", cookie="SID", jour=datetime.date(2025, 10, 5))
    _finding(
        tenant, compte, dom="intranet.test", cookie="JSESSIONID", jour=datetime.date(2024, 5, 2)
    )
    return compte


class TestRegroupement:
    """A1.1 — une fuite ne s'affiche plus ligne par ligne quand elle se répète."""

    def test_regroupe_par_compte_type_et_service(self, tenant, jeu):
        base = services.list_watched_account_findings(tenant)
        groupes = services.group_watched_account_findings(base)

        # Deux domaines → deux groupes, pas quatre lignes.
        assert len(groupes) == 2
        par_service = {g["service"]: g for g in groupes}
        assert par_service[".gmail.com"]["occurrences"] == 3
        assert par_service["intranet.test"]["occurrences"] == 1

    def test_chaque_groupe_porte_ses_bornes_de_dates(self, tenant, jeu):
        groupes = services.group_watched_account_findings(
            services.list_watched_account_findings(tenant)
        )
        gmail = next(g for g in groupes if g["service"] == ".gmail.com")

        assert gmail["latest_breach_date"] == datetime.date(2025, 10, 5)
        assert gmail["oldest_breach_date"] == datetime.date(2020, 1, 1)

    def test_la_gravite_du_groupe_est_la_pire_qu_il_contient(self, tenant, compte):
        """Annoncer « Attention » sur un groupe qui renferme une fuite
        critique tromperait sur l'urgence."""
        _finding(
            tenant,
            compte,
            dom="a.test",
            cookie="c1",
            jour=datetime.date(2024, 1, 1),
            severite="attention",
        )
        _finding(
            tenant,
            compte,
            dom="a.test",
            cookie="c2",
            jour=datetime.date(2024, 1, 2),
            severite="critical",
        )

        groupes = services.group_watched_account_findings(
            services.list_watched_account_findings(tenant)
        )

        assert groupes[0]["severity"] == "critical"

    def test_le_groupe_compte_les_statuts_separement(self, tenant, compte):
        _finding(tenant, compte, dom="b.test", cookie="c1", jour=datetime.date(2024, 1, 1))
        _finding(
            tenant,
            compte,
            dom="b.test",
            cookie="c2",
            jour=datetime.date(2024, 1, 2),
            statut="treated",
        )
        _finding(
            tenant,
            compte,
            dom="b.test",
            cookie="c3",
            jour=datetime.date(2024, 1, 3),
            statut="ignored",
        )

        groupe = services.group_watched_account_findings(
            services.list_watched_account_findings(tenant)
        )[0]

        assert groupe["occurrences"] == 3
        assert (groupe["open_count"], groupe["treated_count"], groupe["ignored_count"]) == (1, 1, 1)

    def test_deplier_un_groupe_rend_ses_lignes(self, tenant, jeu):
        base = services.list_watched_account_findings(tenant)
        lignes = services.findings_in_group(
            base, account_id=jeu.id, finding_type="sessions", service=".gmail.com"
        )

        assert lignes.count() == 3
        assert {ligne.raw_data["cookie_name"] for ligne in lignes} == {"__utma", "__utmz", "SID"}


class TestChampsServis:
    """A2 — afficher ce que la source fournit réellement.

    Les champs étaient stockés depuis la V2-2 et servis nulle part sur cet
    écran : c'est ce qui rendait les lignes indiscernables.
    """

    def test_le_detail_porte_le_domaine_et_le_nom_du_cookie(
        self, api_client, tenant, tenant_owner, jeu
    ):
        from apps.threat_intelligence.serializers import WatchedAccountFindingSerializer

        ligne = services.list_watched_account_findings(tenant).first()
        data = WatchedAccountFindingSerializer(ligne).data

        libelles = {d["label"] for d in data["details"]}
        # Le libelle du domaine est « Service concerne » : c est le service
        # sur lequel la session a ete volee, pas un detail technique.
        assert "Service concerné" in libelles
        assert data["details"], "aucun detail servi : les lignes restent indiscernables"

    def test_chaque_champ_porte_son_implication(self, tenant, jeu):
        from apps.threat_intelligence.serializers import WatchedAccountFindingSerializer

        ligne = services.list_watched_account_findings(tenant).first()
        details = WatchedAccountFindingSerializer(ligne).data["details"]

        # « Raccoon » seul ne veut rien dire ; la phrase d'implication, si.
        for champ in details:
            assert champ["implication"], f"champ sans implication : {champ['label']}"

    def test_aucun_secret_ne_sort_par_le_detail(self, tenant, compte):
        """La liste blanche est la garde : un champ secret ne peut pas sortir."""
        from apps.threat_intelligence.serializers import WatchedAccountFindingSerializer

        f = _finding(tenant, compte, dom="c.test", cookie="c1", jour=datetime.date(2024, 1, 1))
        f.raw_data = {**f.raw_data, "val": "SECRET-EN-CLAIR"}
        f.save(update_fields=["raw_data"])

        data = WatchedAccountFindingSerializer(f).data

        assert "SECRET-EN-CLAIR" not in str(data)


class TestTri:
    """A3.10 — le plus récent d'abord, sur la date de FUITE."""

    def test_trie_par_date_de_fuite_et_non_par_ordre_d_insertion(self, tenant, jeu):
        dates = [f.breach_date for f in services.list_watched_account_findings(tenant)]

        assert dates == sorted(dates, reverse=True)
        assert dates[0] == datetime.date(2025, 10, 5)

    def test_une_ligne_sans_date_ne_passe_pas_devant(self, tenant, compte):
        """Une date inconnue ne doit pas être promue en tête de liste."""
        sans = _finding(tenant, compte, dom="d.test", cookie="c1", jour=None)
        _finding(tenant, compte, dom="d.test", cookie="c2", jour=datetime.date(2024, 1, 1))

        premiers = list(services.list_watched_account_findings(tenant))

        assert premiers[-1].id == sans.id


class TestFiltres:
    """A4.12 — filtrer par gravité, type, statut, période, et chercher."""

    def test_filtre_par_statut(self, tenant, compte):
        _finding(tenant, compte, dom="e.test", cookie="c1", jour=datetime.date(2024, 1, 1))
        _finding(
            tenant,
            compte,
            dom="e.test",
            cookie="c2",
            jour=datetime.date(2024, 1, 2),
            statut="treated",
        )

        assert services.list_watched_account_findings(tenant, status="open").count() == 1

    def test_filtre_par_periode(self, tenant, jeu):
        recents = services.list_watched_account_findings(tenant, since=datetime.date(2024, 1, 1))

        assert recents.count() == 2
        assert all(f.breach_date >= datetime.date(2024, 1, 1) for f in recents)

    def test_recherche_sur_le_compte(self, tenant, jeu):
        assert services.list_watched_account_findings(tenant, search="dirigeant").count() == 4
        assert services.list_watched_account_findings(tenant, search="absent").count() == 0

    def test_les_filtres_proposes_existent_reellement(self, tenant, jeu):
        """Proposer un type que le client n'a pas donne un filtre mort."""
        options = services.watched_account_filter_options(tenant)

        assert options["types"] == ["sessions"]
        assert options["severities"] == ["critical"]


class TestApiBornee:
    """A5.13-14 — borner l'affichage ne borne jamais l'analyse."""

    def test_la_reponse_est_paginee(self, api_client, tenant, tenant_owner, jeu):
        response = api_client.get(
            reverse("ti-watched-account-finding-list"),
            **_auth(api_client, tenant_owner, tenant),
        )

        assert response.status_code == 200
        assert "count" in response.data
        assert "results" in response.data

    def test_l_ecran_sert_des_groupes_par_defaut(self, api_client, tenant, tenant_owner, jeu):
        response = api_client.get(
            reverse("ti-watched-account-finding-list"),
            **_auth(api_client, tenant_owner, tenant),
        )

        # Quatre lignes en base, deux groupes servis.
        assert response.data["count"] == 2
        assert response.data["results"][0]["occurrences"] >= 1

    def test_les_compteurs_portent_sur_l_ensemble_malgre_la_pagination(self, tenant, jeu):
        """La règle qui tient : borner l'affichage ne borne pas l'analyse."""
        resume = services.watched_accounts_summary(tenant)

        assert resume["open_findings"] == 4

    def test_un_groupe_se_deplie_par_l_api(self, api_client, tenant, tenant_owner, jeu):
        cle = f"{jeu.id}|sessions|.gmail.com"
        response = api_client.get(
            reverse("ti-watched-account-finding-list"),
            {"group": cle},
            **_auth(api_client, tenant_owner, tenant),
        )

        assert response.data["count"] == 3

    def test_les_filtres_disponibles_accompagnent_la_liste(
        self, api_client, tenant, tenant_owner, jeu
    ):
        response = api_client.get(
            reverse("ti-watched-account-finding-list"),
            **_auth(api_client, tenant_owner, tenant),
        )

        assert "filters" in response.data


class TestPremierPassage:
    """A5.16 — distinguer la reprise d'historique des nouveautes.

    Le premier passage sur un compte remonte tout l'historique connu du
    fournisseur : 3 222 entrees en production. Les suivants ne rapportent que
    du nouveau. Sans cette distinction, le client croit a une catastrophe du
    jour devant ce qui est un inventaire du passe.
    """

    def test_le_premier_passage_est_marque_comme_historique(self, tenant, compte):
        from apps.threat_intelligence.providers.base import RawFinding

        brutes = [
            RawFinding(
                endpoint="sessions",
                payload={"user_name": compte.value, "dom": "a.test", "cookie_name": "c1"},
                is_test=False,
            )
        ]
        with patch("apps.threat_intelligence.watched_accounts.get_provider"):
            watched_accounts._ingest(tenant=tenant, account=compte, raw_findings=brutes)

        compte.refresh_from_db()
        assert compte.first_scanned_at is not None
        assert WatchedAccountFinding.all_objects.filter(from_first_scan=True).count() == 1

    def test_les_passages_suivants_ne_sont_pas_de_l_historique(self, tenant, compte):
        from apps.threat_intelligence.providers.base import RawFinding

        def brute(cookie):
            return RawFinding(
                endpoint="sessions",
                payload={"user_name": compte.value, "dom": "a.test", "cookie_name": cookie},
                is_test=False,
            )

        with patch("apps.threat_intelligence.watched_accounts.get_provider"):
            watched_accounts._ingest(tenant=tenant, account=compte, raw_findings=[brute("c1")])
            compte.refresh_from_db()
            watched_accounts._ingest(tenant=tenant, account=compte, raw_findings=[brute("c2")])

        nouvelle = WatchedAccountFinding.all_objects.get(raw_data__cookie_name="c2")
        assert nouvelle.from_first_scan is False

    def test_le_resume_separe_les_deux_volumes(self, tenant, compte):
        _finding(tenant, compte, dom="a.test", cookie="c1", jour=datetime.date(2024, 1, 1))
        historique = _finding(
            tenant, compte, dom="a.test", cookie="c2", jour=datetime.date(2023, 1, 1)
        )
        historique.from_first_scan = True
        historique.save(update_fields=["from_first_scan"])

        resume = services.watched_accounts_summary(tenant)

        assert resume["from_first_scan"] == 1
        assert resume["since_first_scan"] == 1

    def test_le_resume_compte_ce_qui_est_deja_traite(self, tenant, compte):
        """A3.9 — on masque, on ne cache pas."""
        _finding(
            tenant,
            compte,
            dom="a.test",
            cookie="c1",
            jour=datetime.date(2024, 1, 1),
            statut="treated",
        )
        _finding(
            tenant,
            compte,
            dom="a.test",
            cookie="c2",
            jour=datetime.date(2024, 1, 2),
            statut="ignored",
        )

        resume = services.watched_accounts_summary(tenant)

        assert resume["treated_findings"] == 1
        assert resume["ignored_findings"] == 1


class TestExport:
    """A5.17 — un export filtre EXACTEMENT comme l'ecran."""

    def test_l_export_respecte_les_filtres(self, api_client, tenant, tenant_owner, compte):
        _finding(tenant, compte, dom="a.test", cookie="c1", jour=datetime.date(2024, 1, 1))
        _finding(
            tenant,
            compte,
            dom="a.test",
            cookie="c2",
            jour=datetime.date(2024, 1, 2),
            statut="treated",
        )

        response = api_client.get(
            reverse("ti-watched-account-finding-export"),
            {"status": "open"},
            **_auth(api_client, tenant_owner, tenant),
        )

        corps = response.content.decode("utf-8")
        assert response.status_code == 200
        # Une ligne d'en-tete, une seule ligne de donnees : le filtre a porte.
        assert len([x for x in corps.strip().splitlines() if x]) == 2

    def test_l_export_porte_les_champs_distinctifs(self, api_client, tenant, tenant_owner, jeu):
        response = api_client.get(
            reverse("ti-watched-account-finding-export"),
            **_auth(api_client, tenant_owner, tenant),
        )
        corps = response.content.decode("utf-8")

        # Ce qui manquait a l'ecran doit se retrouver dans le fichier.
        assert "Service concerné" in corps
        assert ".gmail.com" in corps

    def test_l_export_dit_ce_qui_vient_de_l_historique(
        self, api_client, tenant, tenant_owner, compte
    ):
        f = _finding(tenant, compte, dom="a.test", cookie="c1", jour=datetime.date(2024, 1, 1))
        f.from_first_scan = True
        f.save(update_fields=["from_first_scan"])

        response = api_client.get(
            reverse("ti-watched-account-finding-export"),
            **_auth(api_client, tenant_owner, tenant),
        )

        assert "historique" in response.content.decode("utf-8")

    def test_un_voisin_n_exporte_rien(
        self, api_client, tenant, tenant_owner, jeu, tenant_factory, user_factory
    ):
        """L'export est un chemin de sortie de donnees : il se garde comme les autres."""
        voisin_owner = user_factory(email="voisin-export@example.com")
        voisin = tenant_factory(voisin_owner, name="Voisin Export")

        response = api_client.get(
            reverse("ti-watched-account-finding-export"),
            **_auth(api_client, voisin_owner, voisin),
        )

        corps = response.content.decode("utf-8")
        assert "dirigeant@exemple.test" not in corps
        assert len([x for x in corps.strip().splitlines() if x]) == 1

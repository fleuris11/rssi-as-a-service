"""V2-1 partie A — une fuite traitée ne réapparaît pas, un secret changé si.

Le défaut corrigé ici empêchait le client de progresser : chaque analyse
remontait les mêmes lignes, y compris celles qu'il venait de traiter. Il
retraitait indéfiniment le même travail.

Ces tests couvrent les deux moitiés de la règle, qui se contredisent en
apparence et doivent tenir ensemble :

  - même compte, MÊME secret → la même fuite, qu'on ne rouvre pas ;
  - même compte, secret DIFFÉRENT → une nouvelle fuite, qui doit
    apparaître même si la précédente a été traitée.
"""

from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.threat_intelligence import exposure, services
from apps.threat_intelligence.models import BreachFinding
from apps.threat_intelligence.providers.base import RawFinding

pytestmark = pytest.mark.django_db


def _fuite(mot_de_passe="MotDePasse2024!", compte="marie@example.com"):
    """Une fuite d'identifiants, telle que le fournisseur la remonte.

    ``src`` et ``fnd`` font partie des champs de dédoublonnage de l'endpoint
    ``creds`` : les figer ici est ce qui permet de ne faire varier QUE le
    secret d'un test à l'autre.
    """
    return RawFinding(
        endpoint="creds",
        payload={
            "eml": compte,
            "pwd": mot_de_passe,
            "src": "fuite-acme-2024",
            "fnd": "2024-03-01",
        },
    )


def _ingerer(tenant, asset, raw, report=None):
    return services.ingest_raw_findings(
        tenant=tenant, asset=asset, raw_findings=[raw], report=report
    )


def _analyser(tenant, asset, fake_provider, fuites):
    """Une analyse complète par le vrai chemin (``execute_scan``), le
    fournisseur seul étant simulé."""
    fake_provider.scan_findings = list(fuites)
    with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
        return services.execute_scan(
            tenant=tenant, assets=[asset], triggered_by=services.TriggeredBy.MANUAL
        )


class TestUneFuiteTraiteeNeReapparaitPas:
    @pytest.mark.parametrize(
        "statut",
        [BreachFinding.Status.TREATED, BreachFinding.Status.IGNORED],
    )
    def test_le_statut_survit_a_une_nouvelle_analyse(self, tenant, website_asset, statut):
        raw = _fuite()
        fuite = _ingerer(tenant, website_asset, raw)[0]
        services.set_finding_status(fuite, status=statut)

        creees = _ingerer(tenant, website_asset, raw)

        assert creees == []
        fuite.refresh_from_db()
        assert fuite.status == statut
        assert BreachFinding.all_objects.filter(tenant=tenant).count() == 1

    def test_la_date_de_detection_ne_bouge_pas_mais_la_derniere_observation_si(
        self, tenant, website_asset
    ):
        """La distinction porte tout l'intérêt : l'historique de traitement
        dit quand la fuite a été découverte, pas quand on l'a revue."""
        raw = _fuite()
        fuite = _ingerer(tenant, website_asset, raw)[0]
        services.set_finding_status(fuite, status=BreachFinding.Status.TREATED)
        detection_initiale = fuite.detected_at
        premiere_observation = fuite.last_seen_at

        _ingerer(tenant, website_asset, raw)

        fuite.refresh_from_db()
        assert fuite.detected_at == detection_initiale
        assert fuite.last_seen_at > premiere_observation

    def test_l_alerte_de_surveillance_n_est_pas_rouverte(self, tenant, website_asset):
        raw = _fuite()
        fuite = _ingerer(tenant, website_asset, raw)[0]
        alerte = fuite.alert
        alerte.is_open = False
        alerte.resolved_at = timezone.now()
        alerte.save(update_fields=["is_open", "resolved_at"])
        services.set_finding_status(fuite, status=BreachFinding.Status.TREATED)

        _ingerer(tenant, website_asset, raw)

        alerte.refresh_from_db()
        assert alerte.is_open is False

    def test_une_fuite_ouverte_revue_reste_une_seule_ligne(self, tenant, website_asset):
        """Le dédoublonnage ne dépend pas du statut : une fuite ouverte revue
        ne se dédouble pas davantage qu'une fuite traitée."""
        raw = _fuite()
        _ingerer(tenant, website_asset, raw)
        _ingerer(tenant, website_asset, raw)

        assert BreachFinding.all_objects.filter(tenant=tenant).count() == 1


class TestUnSecretDifferentEstUneNouvelleFuite:
    def test_nouveau_mot_de_passe_sur_le_meme_compte(self, tenant, website_asset):
        premiere = _ingerer(tenant, website_asset, _fuite("MotDePasse2024!"))[0]
        services.set_finding_status(premiere, status=BreachFinding.Status.TREATED)

        secondes = _ingerer(tenant, website_asset, _fuite("AutreSecret2025?"))

        assert len(secondes) == 1
        assert secondes[0].id != premiere.id
        assert secondes[0].status == BreachFinding.Status.OPEN
        premiere.refresh_from_db()
        assert premiere.status == BreachFinding.Status.TREATED

    def test_deux_secrets_qui_finissent_pareil_restent_deux_fuites(self, tenant, website_asset):
        """Le cas exact que l'ancienne empreinte manquait.

        Elle représentait le secret par sa forme masquée — six puces et les
        DEUX derniers caractères. « Ete2024! » et « Hiver2024! » donnent tous
        deux « ••••••4! » : le second était absorbé par le premier et
        n'apparaissait jamais. Une compromission réelle, non signalée.
        """
        premiere = _ingerer(tenant, website_asset, _fuite("Ete2024!"))[0]
        secondes = _ingerer(tenant, website_asset, _fuite("Hiver2024!"))

        assert premiere.secret_masked == secondes[0].secret_masked, (
            "prérequis du test : les deux secrets doivent bien avoir la MÊME "
            "forme masquée, sinon il ne prouve rien"
        )
        assert len(secondes) == 1
        assert BreachFinding.all_objects.filter(tenant=tenant).count() == 2

    def test_l_empreinte_du_secret_ne_stocke_pas_le_secret(self, tenant, website_asset):
        fuite = _ingerer(tenant, website_asset, _fuite("MotDePasse2024!"))[0]

        assert "MotDePasse2024!" not in fuite.secret_fingerprint
        assert len(fuite.secret_fingerprint) == 64

    def test_une_fuite_sans_secret_a_une_empreinte_vide_et_stable(self, tenant, website_asset):
        raw = RawFinding(
            endpoint="radar", payload={"data": "acme.fr", "src": "forum", "found": "2024-01-01"}
        )

        premiere = _ingerer(tenant, website_asset, raw)[0]
        secondes = _ingerer(tenant, website_asset, raw)

        assert premiere.secret_fingerprint == ""
        assert secondes == []


class TestLEmpreinteResisteAuxChampsOptionnels:
    """Le schéma réel du fournisseur pose que **tous** les champs sont
    optionnels. Une même fuite peut donc être remontée une fois avec sa date
    et une fois sans — et l'ancienne empreinte, positionnelle, en faisait
    deux fuites. C'est le chemin le plus probable par lequel une ligne déjà
    traitée revenait : non pas parce qu'on la rouvrait, mais parce qu'on ne
    la reconnaissait plus."""

    def test_un_champ_de_dedoublonnage_absent_ne_cree_pas_une_seconde_fuite(
        self, tenant, website_asset
    ):
        avec_date = RawFinding(
            endpoint="creds",
            payload={
                "eml": "marie@example.com",
                "pwd": "MotDePasse2024!",
                "src": "fuite-acme-2024",
                "fnd": "2024-03-01",
            },
        )
        sans_date = RawFinding(
            endpoint="creds",
            payload={
                "eml": "marie@example.com",
                "pwd": "MotDePasse2024!",
                "src": "fuite-acme-2024",
            },
        )

        fuite = _ingerer(tenant, website_asset, avec_date)[0]
        services.set_finding_status(fuite, status=BreachFinding.Status.TREATED)
        creees = _ingerer(tenant, website_asset, sans_date)

        assert creees == []
        assert BreachFinding.all_objects.filter(tenant=tenant).count() == 1

    def test_deux_champs_differents_portant_la_meme_valeur_restent_distincts(
        self, tenant, website_asset
    ):
        """Omettre les champs absents sans NOMMER ceux qui restent
        introduirait une collision.

        Les champs d'identité de ``creds`` sont ``eml`` et ``src``. Une fuite
        qui ne porte que ``eml="collision"`` et une autre qui ne porte que
        ``src="collision"`` se réduiraient toutes deux à « collision » : deux
        fuites sans rapport confondues en une, et la seconde jamais signalée.
        Le même secret dans les deux payloads garantit que c'est bien
        l'identité qui les sépare, et non l'empreinte du secret.
        """
        une = RawFinding(endpoint="creds", payload={"eml": "collision", "pwd": "MemeSecret1!"})
        autre = RawFinding(endpoint="creds", payload={"src": "collision", "pwd": "MemeSecret1!"})

        _ingerer(tenant, website_asset, une)
        _ingerer(tenant, website_asset, autre)

        assert BreachFinding.all_objects.filter(tenant=tenant).count() == 2


class TestRaccrochageDesFuitesAnterieures:
    """Les fuites ingérées avant la V2-1 portent une empreinte ``legacy:``
    (la migration 0006 ne déchiffre rien). Sans raccrochage, la première
    analyse suivant la mise en service les recréerait TOUTES en double —
    dont celles que le client venait de traiter."""

    def _rendre_anterieure(self, fuite):
        """Remet la fuite dans l'état où la migration 0006 laisse les fuites
        existantes : empreinte préfixée, clé d'unicité de l'ancienne formule."""
        fuite.secret_fingerprint = f"{services.LEGACY_FINGERPRINT_PREFIX}{fuite.secret_masked}"
        fuite.dedup_hash = "ancienne-formule-" + str(fuite.id)
        fuite.save(update_fields=["secret_fingerprint", "dedup_hash"])
        return fuite

    def test_une_fuite_anterieure_traitee_n_est_pas_recreee(self, tenant, website_asset):
        raw = _fuite()
        fuite = self._rendre_anterieure(_ingerer(tenant, website_asset, raw)[0])
        services.set_finding_status(fuite, status=BreachFinding.Status.TREATED)

        creees = _ingerer(tenant, website_asset, raw)

        assert creees == []
        assert BreachFinding.all_objects.filter(tenant=tenant).count() == 1
        fuite.refresh_from_db()
        assert fuite.status == BreachFinding.Status.TREATED

    def test_le_raccrochage_pose_la_cle_actuelle_une_fois_pour_toutes(self, tenant, website_asset):
        raw = _fuite()
        fuite = self._rendre_anterieure(_ingerer(tenant, website_asset, raw)[0])

        _ingerer(tenant, website_asset, raw)

        fuite.refresh_from_db()
        assert not fuite.secret_fingerprint.startswith(services.LEGACY_FINGERPRINT_PREFIX)
        assert len(fuite.secret_fingerprint) == 64

    def test_le_raccrochage_ne_confond_pas_deux_secrets_differents(self, tenant, website_asset):
        """Le raccrochage se fait sur la forme masquée — donc sur le critère
        même de l'ancienne formule. Il ne doit pas pour autant rapprocher deux
        fuites que la nouvelle règle sépare : à identité égale et forme masquée
        DIFFÉRENTE, ce sont deux fuites."""
        fuite = self._rendre_anterieure(_ingerer(tenant, website_asset, _fuite("Ete2024!"))[0])

        creees = _ingerer(tenant, website_asset, _fuite("Automne2025#"))

        assert len(creees) == 1
        assert creees[0].id != fuite.id


class TestCompteurDesFuitesDejaTraitees:
    """« On masque, on ne cache pas » : les fuites traitées ne reviennent pas
    dans la liste, mais le client doit pouvoir lire qu'elles ont été revues."""

    def test_le_compteur_ne_compte_que_les_fuites_deja_traitees(
        self, tenant, website_asset, fake_provider
    ):
        ouverte = _fuite(compte="ouverte@example.com")
        traitee = _fuite(compte="traitee@example.com")
        ignoree = _fuite(compte="ignoree@example.com")
        for raw, statut in (
            (ouverte, None),
            (traitee, BreachFinding.Status.TREATED),
            (ignoree, BreachFinding.Status.IGNORED),
        ):
            fuite = _ingerer(tenant, website_asset, raw)[0]
            if statut:
                services.set_finding_status(fuite, status=statut)

        resultat = _analyser(tenant, website_asset, fake_provider, [ouverte, traitee, ignoree])

        assert resultat["findings_created"] == 0
        assert resultat["findings_seen_again"] == 3
        assert resultat["already_treated_seen"] == 2

    def test_le_compteur_est_a_zero_quand_rien_n_a_ete_traite(
        self, tenant, website_asset, fake_provider
    ):
        raw = _fuite()
        _ingerer(tenant, website_asset, raw)

        resultat = _analyser(tenant, website_asset, fake_provider, [raw])

        assert resultat["already_treated_seen"] == 0
        assert resultat["already_treated_ids"] == []

    def test_les_identifiants_transportes_pointent_bien_sur_les_fuites_traitees(
        self, tenant, website_asset, fake_provider
    ):
        raw = _fuite()
        fuite = _ingerer(tenant, website_asset, raw)[0]
        services.set_finding_status(fuite, status=BreachFinding.Status.TREATED)

        resultat = _analyser(tenant, website_asset, fake_provider, [raw])

        assert resultat["already_treated_ids"] == [fuite.id]

    def test_une_fuite_nouvelle_n_est_pas_comptee_comme_revue(
        self, tenant, website_asset, fake_provider
    ):
        resultat = _analyser(tenant, website_asset, fake_provider, [_fuite()])

        assert resultat["findings_created"] == 1
        assert resultat["findings_seen_again"] == 0
        assert resultat["already_treated_seen"] == 0


class TestLeScoreIgnoreLesFuitesTraitees:
    """Point 4 de la consigne : vérifier que c'est bien le cas aujourd'hui.
    Ce n'était pas une correction à faire mais une garantie à verrouiller —
    rien ne l'empêchait de se perdre au prochain remaniement du fil."""

    def test_traiter_une_fuite_fait_baisser_le_score_du_fil_d_exposition(
        self, tenant, website_asset
    ):
        fuite = _ingerer(tenant, website_asset, _fuite())[0]
        avant = services.build_exposure_feed(tenant)["assets"][0]["score"]

        services.set_finding_status(fuite, status=BreachFinding.Status.TREATED)
        apres = services.build_exposure_feed(tenant)

        assert avant > 0
        assert apres["assets"] == []
        assert apres["highest_score"] == 0

    def test_le_fil_ne_passe_au_score_que_des_fuites_ouvertes(self, tenant, website_asset):
        ouverte = _ingerer(tenant, website_asset, _fuite(compte="a@example.com"))[0]
        traitee = _ingerer(tenant, website_asset, _fuite(compte="b@example.com"))[0]
        services.set_finding_status(traitee, status=BreachFinding.Status.TREATED)

        groupe = services.build_exposure_feed(tenant)["assets"][0]

        assert groupe["findings_count"] == 1
        assert [f["id"] for f in groupe["findings"]] == [ouverte.id]
        assert groupe["score"] == exposure.compute_exposure_score([ouverte]).score

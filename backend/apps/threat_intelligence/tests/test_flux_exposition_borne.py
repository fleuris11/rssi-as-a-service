"""Le flux d'exposition ne doit pas pouvoir figer le navigateur du client.

Panne de production du 06/09/2026. Sur le compte d'un client réel, la page
Exposition affichait « La page ne répond pas — Attendre / Quitter » à chaque
clic. Le client ne pouvait plus se servir de l'écran principal du produit.

Mesuré sur le serveur, la réponse contenait, pour un seul actif :

    ratp.fr : 28 450 fuites sérialisées + 28 450 composantes de score

soit 728 Ko compressés en 6 secondes, puis autant de nœuds à construire dans
le navigateur. Ce n'était pas une lenteur, c'était un blocage du fil
d'exécution principal.

Deux causes distinctes, et il faut les deux corrections :

1. **La liste des fuites.** Cent lignes triées par gravité puis fraîcheur
   disent ce qu'il y a à savoir ; les 28 350 suivantes ne s'ajoutent qu'au
   poids. Le COMPTE, lui, doit rester exact — c'est lui qui porte
   l'information « il y en a beaucoup ».

2. **Les composantes du score.** L'amortissement vaut 0,6 par rang : au-delà
   du 30e, chaque composante pèse 0 point. On transportait donc 28 420 lignes
   disant « cette fuite n'a rien ajouté au score ». Une justification qui ne
   justifie rien.

La règle que ces tests tiennent : **borner l'affichage ne doit jamais borner
l'analyse.** Le score, le compte total et les signaux de réutilisation se
calculent sur la totalité ; seule la liste transmise est plafonnée.
"""

import pytest

from apps.monitoring.models import Asset
from apps.threat_intelligence import exposure, services
from apps.threat_intelligence.models import BreachFinding

pytestmark = pytest.mark.django_db


NOMBREUSES = services.MAX_FINDINGS_PAR_ACTIF * 3


@pytest.fixture
def actif(tenant):
    return Asset.all_objects.create(
        tenant=tenant,
        type=Asset.Type.EMAIL_DOMAIN,
        value="volumineux.example",
        ownership_confirmed=True,
    )


def _fuites(tenant, actif, combien, severite=BreachFinding.Severity.ATTENTION):
    return BreachFinding.all_objects.bulk_create(
        [
            BreachFinding(
                tenant=tenant,
                asset=actif,
                source_endpoint=BreachFinding.SourceEndpoint.CREDS,
                finding_type="identifiants exposés",
                severity=severite,
                identifier_masked=f"u{i}***@volumineux.example",
                dedup_hash=f"volume-{i}",
            )
            for i in range(combien)
        ]
    )


class TestLaListeEstBornee:
    def test_un_actif_tres_expose_ne_serialise_pas_tout(self, tenant, actif):
        _fuites(tenant, actif, NOMBREUSES)

        feed = services.build_exposure_feed(tenant)
        groupe = feed["assets"][0]

        assert len(groupe["findings"]) == services.MAX_FINDINGS_PAR_ACTIF, (
            f"{len(groupe['findings'])} fuites sérialisées pour un seul actif. C'est la charge "
            "qui a figé le navigateur d'un client en production."
        )

    def test_le_compte_total_reste_exact(self, tenant, actif):
        """Le plafond ne doit pas se voir dans les chiffres. Un client qui a
        300 fuites doit lire 300, pas 100 — sinon la troncature devient un
        mensonge sur l'ampleur de sa compromission."""
        _fuites(tenant, actif, NOMBREUSES)

        groupe = services.build_exposure_feed(tenant)["assets"][0]

        assert groupe["findings_count"] == NOMBREUSES
        assert groupe["findings_shown"] == services.MAX_FINDINGS_PAR_ACTIF
        assert groupe["findings_hidden"] == NOMBREUSES - services.MAX_FINDINGS_PAR_ACTIF

    def test_un_actif_peu_expose_est_transmis_en_entier(self, tenant, actif):
        """Le cas normal, qui est aussi la quasi-totalité des cas : rien ne
        doit changer pour un client qui a douze fuites."""
        _fuites(tenant, actif, 12)

        groupe = services.build_exposure_feed(tenant)["assets"][0]

        assert len(groupe["findings"]) == 12
        assert groupe["findings_hidden"] == 0

    def test_les_fuites_transmises_sont_les_plus_graves(self, tenant, actif):
        """Tronquer n'a de sens que si ce qui reste est ce qui compte. Une
        troncature dans l'ordre d'insertion cacherait la fuite critique
        derrière deux cents fuites mineures."""
        _fuites(tenant, actif, NOMBREUSES)
        critique = BreachFinding.all_objects.create(
            tenant=tenant,
            asset=actif,
            source_endpoint=BreachFinding.SourceEndpoint.STEALER,
            finding_type="mot de passe administrateur",
            severity=BreachFinding.Severity.CRITICAL,
            identifier_masked="admin***@volumineux.example",
            dedup_hash="volume-critique",
        )

        groupe = services.build_exposure_feed(tenant)["assets"][0]

        assert critique.id in [f["id"] for f in groupe["findings"]], (
            "La fuite critique doit survivre à la troncature : c'est la seule que le "
            "dirigeant doit voir en premier."
        )


class TestLeScoreSeCalculeSurTout:
    def test_le_score_ignore_le_plafond_d_affichage(self, tenant, actif):
        """La garde centrale. Si le score se mettait à ne compter que les
        cent fuites transmises, un actif massivement compromis afficherait le
        score d'un actif ordinaire — et le produit dirait le contraire de la
        vérité, précisément sur son cas le plus grave."""
        _fuites(tenant, actif, NOMBREUSES, severite=BreachFinding.Severity.CRITICAL)
        toutes = list(BreachFinding.all_objects.filter(asset=actif))

        attendu = exposure.compute_exposure_score(toutes).score
        groupe = services.build_exposure_feed(tenant)["assets"][0]

        assert groupe["score"] == attendu

    def test_les_composantes_a_zero_point_ne_sont_pas_transmises(self, tenant, actif):
        """Une composante à 0 point dit « cette fuite n'a pas bougé le
        score ». La répéter 28 420 fois n'informe personne et double le poids
        de la réponse."""
        _fuites(tenant, actif, NOMBREUSES)

        groupe = services.build_exposure_feed(tenant)["assets"][0]

        assert groupe["components"], "Le « pourquoi ce score » ne doit pas disparaître non plus."
        assert all(c["points"] > 0 for c in groupe["components"])
        assert len(groupe["components"]) < NOMBREUSES

    def test_filtrer_les_composantes_ne_change_pas_le_score(self, tenant, actif):
        """Le total continue de sommer TOUTES les fuites. Le filtre porte sur
        la justification affichée, jamais sur le calcul."""
        _fuites(tenant, actif, NOMBREUSES)
        toutes = list(BreachFinding.all_objects.filter(asset=actif))

        score = exposure.compute_exposure_score(toutes)
        somme_affichee = sum(c.points for c in score.components)

        assert score.score >= somme_affichee - 1  # tolérance d'arrondi entier
        assert score.findings_count == NOMBREUSES, (
            "findings_count doit rester le nombre réel de fuites, pas le nombre de "
            "composantes retenues."
        )


class TestBornerLAffichageNeBornePasLAnalyse:
    def test_un_signal_de_reutilisation_lointain_remonte_quand_meme(self, tenant, actif):
        """Le piège de la première version du correctif : les signaux de
        réutilisation étaient recomposés à partir des seules fuites
        affichées. Une réutilisation de mot de passe enfouie au-delà du
        plafond aurait disparu de la carte de l'actif — or c'est exactement
        le signal rare et grave que le produit existe pour trouver.

        Mise en scène : les fuites de remplissage sont critiques et récentes,
        donc en tête ; la paire porteuse du signal est en gravité « attention »
        et se retrouve donc largement au-delà de la centième place.
        """
        email_membre = next(iter(services.tenant_member_emails(tenant)))
        _fuites(tenant, actif, NOMBREUSES, severite=BreachFinding.Severity.CRITICAL)

        paire = [
            BreachFinding.all_objects.create(
                tenant=tenant,
                asset=actif,
                source_endpoint=endpoint,
                finding_type="identifiants exposés",
                severity=BreachFinding.Severity.ATTENTION,
                identifier_plain=email_membre,
                identifier_masked="m***@example.com",
                dedup_hash=f"reutilisation-{endpoint}",
            )
            for endpoint in (
                BreachFinding.SourceEndpoint.CREDS,
                BreachFinding.SourceEndpoint.COMBO,
            )
        ]

        groupe = services.build_exposure_feed(tenant)["assets"][0]
        affichees = {f["id"] for f in groupe["findings"]}

        assert not any(f.id in affichees for f in paire), (
            "Prérequis : la paire doit bien être hors de la partie affichée."
        )
        assert groupe["reuse_signals"], (
            "Le signal de réutilisation a disparu avec la troncature. Borner l'affichage "
            "ne doit jamais borner l'analyse : la carte de l'actif doit continuer de "
            "signaler un identifiant exposé deux fois, où qu'il se trouve dans la liste."
        )
        signale = {
            fid
            for signal in groupe["reuse_signals"]
            for fid in signal.get("related_finding_ids", [])
        }
        assert signale & {f.id for f in paire}

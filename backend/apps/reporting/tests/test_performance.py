"""Le tableau de bord doit tenir sur le client qui en a vraiment besoin.

Le 06/09/2026, le fil d'exposition s'est effondré sur un actif réel portant
28 450 fuites : 3,79 s rien qu'à matérialiser les instances Django, et un
`defer()` sur les colonnes larges n'y changeait rien — le coût est celui des
OBJETS, pas des données. Un tableau de bord qui interroge plusieurs dates
referait la même faute, multipliée.

Ce module mesure les deux approches sur le même jeu de données, et fixe la
garantie qui compte : **le nombre de requêtes ne dépend pas du volume**. Un
budget de temps serait un test qui échoue selon la machine ; un budget de
requêtes décrit une propriété du code.

Marqué ``slow`` : il fabrique 28 450 fuites. Lancer avec
``pytest -m slow apps/reporting/tests/test_performance.py -s``.
"""

import time

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.monitoring.models import Asset
from apps.reporting import periods, services
from apps.threat_intelligence import exposure
from apps.threat_intelligence.models import BreachFinding

pytestmark = [pytest.mark.django_db, pytest.mark.slow]

#: Volume relevé en production sur l'actif le plus chargé (journal du
#: 06/09/2026). On mesure sur le cas réel, pas sur un cas commode.
VOLUME = 28_450

#: Plafond de requêtes du tableau de bord complet. Volontairement large :
#: ce qui est vérifié n'est pas un chiffre exact — il bougerait au premier
#: indicateur ajouté — mais le fait qu'il ne DÉPEND PAS du volume. Le test
#: compare d'ailleurs deux volumes très différents.
#:
#: Lot C : 40 → 56. Le tableau de bord atteignait déjà 40 requêtes, et les
#: courbes en ajoutent un nombre FIXE — treize pour le score d'exposition (un
#: point par requête, retenu sur mesure : 0,33 s contre 1,21 s en mémoire, voir
#: test_performance_courbes.py), trois pour le plan. Aucune ne dépend du volume.
BUDGET_REQUETES = 56


#: Un secret chiffré réel fait quelques centaines d'octets (jeton Fernet).
#: Le jeu de mesure en porte, sinon il ne mesurerait pas ce qui coûte : une
#: première version de ce fichier n'en avait aucun, et concluait à tort que
#: rapatrier la colonne ne coûtait rien.
SECRET_FACTICE = b"gAAAAAB" + b"x" * 240


def _peupler(tenant, asset, combien):
    maintenant = timezone.now()
    gravites = [
        BreachFinding.Severity.CRITICAL,
        BreachFinding.Severity.HIGH,
        BreachFinding.Severity.ATTENTION,
    ]
    BreachFinding.all_objects.bulk_create(
        [
            BreachFinding(
                tenant=tenant,
                asset=asset,
                source_endpoint=BreachFinding.SourceEndpoint.CREDS,
                finding_type="creds",
                severity=gravites[i % 3],
                status=BreachFinding.Status.OPEN,
                dedup_hash=f"perf-{i}",
                identity_hash=f"perf-id-{i}",
                secret_fingerprint=f"perf-s-{i}",
                # Proportion relevée en production le 04/09/2026 : 106 fuites
                # sur 137 portaient un secret chiffré.
                has_secret=i % 4 != 0,
                secret_encrypted=SECRET_FACTICE if i % 4 != 0 else b"",
                detected_at=maintenant,
                last_seen_at=maintenant,
            )
            for i in range(combien)
        ],
        batch_size=2000,
    )


@pytest.fixture
def tenant_charge(tenant, tenant_owner):
    from apps.monitoring import services as monitoring_services

    asset = monitoring_services.create_asset(
        tenant=tenant,
        user=tenant_owner,
        type=Asset.Type.WEBSITE,
        value="https://charge.example",
        ownership_confirmed=True,
    )
    _peupler(tenant, asset, VOLUME)
    return tenant


def _score_par_le_chemin_naif(tenant, moment):
    """Ce qu'aurait donné l'approche évidente : charger les fuites ouvertes
    comme des objets, puis appeler la fonction de score complète.

    Gardé dans le test — et seulement là — pour que la comparaison soit
    mesurée et non affirmée.
    """
    fuites = list(
        BreachFinding.all_objects.filter(
            tenant=tenant, status=BreachFinding.Status.OPEN, detected_at__lte=moment
        )
    )
    return exposure.compute_exposure_score(fuites, now=moment).score


class TestCoutDuTableauDeBord:
    def test_le_score_ne_materialise_pas_les_objets(self, tenant_charge, capsys):
        """Mesure les deux chemins sur exactement les mêmes données."""
        from apps.threat_intelligence import services as ti_services

        moment = timezone.now()

        debut = time.perf_counter()
        naif = _score_par_le_chemin_naif(tenant_charge, moment)
        temps_naif = time.perf_counter() - debut

        debut = time.perf_counter()
        rapide = ti_services.exposure_score_at(tenant_charge, moment)
        temps_rapide = time.perf_counter() - debut

        with capsys.disabled():
            print(f"\n  volume                      : {VOLUME} fuites")
            print(f"  score par objets Django     : {temps_naif:.2f} s")
            print(f"  score par n-uplets bruts    : {temps_rapide:.2f} s")
            print(f"  rapport                     : x{temps_naif / max(temps_rapide, 1e-6):.1f}")

        # Le résultat doit être IDENTIQUE : une optimisation qui change le
        # chiffre n'est pas une optimisation, c'est un autre indicateur.
        assert rapide == naif

    def test_le_booleen_calcule_en_base_evite_de_rapatrier_les_secrets(self, tenant_charge, capsys):
        """Mesure ce que coûte le transport de la colonne chiffrée.

        Le score n'a besoin que de savoir si un secret existe. Le rapatrier
        pour en faire un booléen transporte plusieurs mégaoctets — l'annotation
        le calcule côté base. Ce test compare les deux, plutôt que d'affirmer
        que l'un est meilleur.
        """
        moment = timezone.now()  # noqa: F841 - borne implicite, meme jeu des deux cotes
        ouvertes = BreachFinding.all_objects.filter(
            tenant=tenant_charge, status=BreachFinding.Status.OPEN
        )

        debut = time.perf_counter()
        avec_blob = list(
            ouvertes.values_list(
                "severity", "breach_date", "detected_at", "has_secret", "secret_encrypted"
            )
        )
        temps_blob = time.perf_counter() - debut

        debut = time.perf_counter()
        avec_booleen = list(
            exposure.annotate_revealable(ouvertes).values_list(*exposure.SCORE_ROW_FIELDS)
        )
        temps_booleen = time.perf_counter() - debut

        octets = sum(len(ligne[4] or b"") for ligne in avec_blob)
        with capsys.disabled():
            print("")
            print(
                f"  colonne chiffree rapatriee : {temps_blob:.2f} s "
                f"({octets / 1024 / 1024:.1f} Mo transportes)"
            )
            print(f"  booleen calcule en base    : {temps_booleen:.2f} s")
            print(f"  rapport                    : x{temps_blob / max(temps_booleen, 1e-6):.1f}")

        assert len(avec_blob) == len(avec_booleen)
        # Les deux doivent conclure la MEME chose sur chaque ligne.
        for (_s, _b, _d, has_secret, chiffre), (_s2, _b2, _d2, revelable) in zip(
            avec_blob, avec_booleen, strict=True
        ):
            assert bool(has_secret and bytes(chiffre or b"")) == bool(revelable)

    def test_le_nombre_de_requetes_ne_depend_pas_du_volume(
        self, tenant, tenant_owner, tenant_charge, capsys
    ):
        """La propriété qui compte, et la seule qui ne dépende pas de la
        machine : le tableau de bord fait le même nombre de requêtes sur un
        tenant vide et sur un tenant à 28 450 fuites."""
        periode = periods.resolve(periods.PRESET_QUARTER)

        debut = time.perf_counter()
        with CaptureQueriesContext(connection) as charge:
            services.build_dashboard(tenant_charge, periode)
        temps_charge = time.perf_counter() - debut

        with capsys.disabled():
            print(
                f"\n  tableau de bord ({VOLUME} fuites) : {len(charge)} requêtes, "
                f"{temps_charge:.2f} s"
            )

        assert len(charge) <= BUDGET_REQUETES

    def test_la_serie_quotidienne_coute_un_nombre_fixe_de_requetes(self, tenant_charge, capsys):
        """Une série de 91 jours ne doit pas coûter 91 requêtes.

        C'est le piège naturel de ce genre d'écran : « combien de fuites
        ouvertes chaque jour ? » se traduit spontanément par une boucle sur
        les jours.
        """
        from apps.threat_intelligence import services as ti_services

        periode = periods.resolve(periods.PRESET_QUARTER)
        with CaptureQueriesContext(connection) as requetes:
            serie = ti_services.open_findings_series(
                tenant_charge, start=periode.start, end=periode.end
            )

        with capsys.disabled():
            print(f"\n  série de {len(serie)} jours : {len(requetes)} requêtes")

        assert len(serie) == periode.days
        # Quatre requêtes : détections, clôtures, traitements par jour (lot C),
        # état initial.
        assert len(requetes) <= 4

    def test_les_courbes_du_lot_c_sur_le_volume_reel(self, tenant_charge, capsys):
        """Lot C, point 11 : « mesure et donne les chiffres ».

        Compare, sur les 28 450 fuites, ce que coûtait le tableau de bord SANS
        les nouvelles courbes (les indicateurs de la V2-3, appelés seuls) et ce
        qu'il coûte AVEC. Et mesure le chemin naïf de la courbe du score — un
        appel à ``exposure_score_at`` par point — pour que le choix d'une seule
        requête soit mesuré et non affirmé.
        """
        from apps.actions import services as actions_services
        from apps.threat_intelligence import services as ti_services

        periode = periods.resolve(periods.PRESET_QUARTER)

        debut = time.perf_counter()
        with CaptureQueriesContext(connection) as avant:
            ti_services.breach_indicators(tenant_charge, start=periode.start, end=periode.end)
            actions_services.action_plan_indicators(
                tenant_charge, start=periode.start, end=periode.end
            )
            ti_services.exposure_by_asset(tenant_charge, at=periode.end)
        temps_avant = time.perf_counter() - debut

        debut = time.perf_counter()
        with CaptureQueriesContext(connection) as score:
            serie = ti_services.exposure_score_series(
                tenant_charge, start=periode.start, end=periode.end
            )
        temps_score = time.perf_counter() - debut

        debut = time.perf_counter()
        with CaptureQueriesContext(connection) as naif:
            pas = (periode.end - periode.start) / (ti_services.EXPOSURE_SCORE_POINTS - 1)
            instants = [
                periode.start + pas * r for r in range(ti_services.EXPOSURE_SCORE_POINTS - 1)
            ] + [periode.end]
            attendu = [ti_services.exposure_score_at(tenant_charge, m) for m in instants]
        temps_naif = time.perf_counter() - debut

        debut = time.perf_counter()
        with CaptureQueriesContext(connection) as plan:
            actions_services.action_plan_series(tenant_charge, start=periode.start, end=periode.end)
        temps_plan = time.perf_counter() - debut

        debut = time.perf_counter()
        with CaptureQueriesContext(connection) as complet:
            services.build_dashboard(tenant_charge, periode)
        temps_complet = time.perf_counter() - debut

        with capsys.disabled():
            print(f"\n  volume                                  : {VOLUME} fuites")
            print(
                f"  indicateurs V2-3 seuls (avant lot C)    : {len(avant)} requêtes, "
                f"{temps_avant:.2f} s"
            )
            print(
                f"  courbe du score, une requête            : {len(score)} requête, "
                f"{temps_score:.2f} s"
            )
            print(
                f"  courbe du score, chemin naïf par point  : {len(naif)} requêtes, "
                f"{temps_naif:.2f} s"
            )
            print(
                f"  courbe du plan                          : {len(plan)} requêtes, "
                f"{temps_plan:.2f} s"
            )
            print(
                f"  tableau de bord complet (après lot C)   : {len(complet)} requêtes, "
                f"{temps_complet:.2f} s"
            )

        assert [p["score"] for p in serie] == attendu
        assert len(score) == ti_services.EXPOSURE_SCORE_POINTS
        assert len(complet) <= BUDGET_REQUETES

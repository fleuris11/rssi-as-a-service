"""Lot C, point 11 — la courbe du score d'exposition, mesurée honnêtement.

Une première mesure concluait en faveur d'une requête par point (0,45 s)
contre une requête unique reconstruite en mémoire (2,04 s). Elle était
biaisée, deux fois :

- toutes les fuites du jeu de mesure étaient détectées « maintenant » : aux
  douze premiers points, aucune n'était encore ouverte, et douze requêtes sur
  treize ne ramenaient rien ;
- le chemin par point passait en second, sur un cache de base déjà chaud.

Ici, les détections et les traitements sont répartis sur six mois, les deux
chemins sont alternés, et on garde le meilleur de trois essais. Le choix
d'implémentation suit ce que mesure CE fichier.

Marqué ``slow``. Lancer avec
``pytest -m slow -s apps/reporting/tests/test_performance_courbes.py``.
"""

import random
import time
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.monitoring.models import Asset
from apps.reporting import periods
from apps.threat_intelligence import exposure
from apps.threat_intelligence import services as ti_services
from apps.threat_intelligence.models import BreachFinding

pytestmark = [pytest.mark.django_db, pytest.mark.slow]

VOLUME = 28_450
ESSAIS = 3


@pytest.fixture
def tenant_realiste(tenant, tenant_owner):
    from apps.monitoring import services as monitoring_services

    asset = monitoring_services.create_asset(
        tenant=tenant,
        user=tenant_owner,
        type=Asset.Type.WEBSITE,
        value="https://realiste.example",
        ownership_confirmed=True,
    )
    hasard = random.Random(28450)
    maintenant = timezone.now()
    gravites = [
        BreachFinding.Severity.CRITICAL,
        BreachFinding.Severity.HIGH,
        BreachFinding.Severity.ATTENTION,
    ]
    fuites = []
    for i in range(VOLUME):
        detectee = maintenant - timedelta(days=hasard.uniform(0, 180))
        traitee = hasard.random() < 0.6
        fuites.append(
            BreachFinding(
                tenant=tenant,
                asset=asset,
                source_endpoint=BreachFinding.SourceEndpoint.CREDS,
                finding_type="creds",
                severity=gravites[i % 3],
                status=BreachFinding.Status.TREATED if traitee else BreachFinding.Status.OPEN,
                dedup_hash=f"real-{i}",
                identity_hash=f"real-id-{i}",
                secret_fingerprint=f"real-s-{i}",
                has_secret=i % 4 != 0,
                secret_encrypted=b"gAAAAAB" + b"x" * 240 if i % 4 != 0 else b"",
                detected_at=detectee,
                last_seen_at=detectee,
                treated_at=(detectee + timedelta(days=hasard.uniform(0, 60)) if traitee else None),
            )
        )
    BreachFinding.all_objects.bulk_create(fuites, batch_size=2000)
    return tenant


def _par_point(tenant, periode):
    pas = (periode.end - periode.start) / (ti_services.EXPOSURE_SCORE_POINTS - 1)
    instants = [periode.start + pas * r for r in range(ti_services.EXPOSURE_SCORE_POINTS - 1)]
    instants.append(periode.end)
    return [ti_services.exposure_score_at(tenant, m) for m in instants]


def _en_memoire(tenant, periode):
    """La reconstruction en mémoire, gardée ici pour la comparaison : une
    requête, puis l'état à chaque point recalculé sur les intervalles."""
    pas = (periode.end - periode.start) / (ti_services.EXPOSURE_SCORE_POINTS - 1)
    instants = [periode.start + pas * r for r in range(ti_services.EXPOSURE_SCORE_POINTS - 1)]
    instants.append(periode.end)
    from django.db.models import Q

    lignes = exposure.annotate_revealable(
        BreachFinding.all_objects.filter(tenant=tenant, detected_at__lte=periode.end).filter(
            Q(status=BreachFinding.Status.OPEN) | Q(treated_at__gt=periode.start)
        )
    ).values_list("status", "treated_at", *exposure.SCORE_ROW_FIELDS)
    intervalles = []
    for statut, traitee_le, *reste in lignes:
        if statut != BreachFinding.Status.OPEN and traitee_le is None:
            continue
        fin = None if statut == BreachFinding.Status.OPEN else traitee_le
        intervalles.append((reste[2], fin, tuple(reste)))
    return [
        exposure.score_from_rows(
            [r for d, f, r in intervalles if d <= m and (f is None or f > m)], now=m
        )
        for m in instants
    ]


def test_mesure_equitable_des_deux_chemins(tenant_realiste, capsys):
    periode = periods.resolve(periods.PRESET_QUARTER)
    temps = {"par point": [], "en mémoire": []}
    requetes = {}
    resultats = {}

    for essai in range(ESSAIS):
        ordre = [("par point", _par_point), ("en mémoire", _en_memoire)]
        if essai % 2:
            ordre.reverse()
        for nom, chemin in ordre:
            debut = time.perf_counter()
            with CaptureQueriesContext(connection) as capture:
                resultats[nom] = chemin(tenant_realiste, periode)
            temps[nom].append(time.perf_counter() - debut)
            requetes[nom] = len(capture)

    with capsys.disabled():
        print(f"\n  volume réparti sur 6 mois       : {VOLUME} fuites, 60 % traitées")
        for nom in temps:
            print(
                f"  {nom:<31} : {requetes[nom]} requête(s), meilleur de {ESSAIS} : "
                f"{min(temps[nom]):.2f} s (essais : "
                + ", ".join(f"{t:.2f}" for t in temps[nom])
                + ")"
            )
    # Les deux chemins donnent le même chiffre : on ne compare que des coûts.
    assert resultats["par point"] == resultats["en mémoire"]
    # Et la fonction de service, quel que soit le chemin retenu, aussi.
    serie = ti_services.exposure_score_series(tenant_realiste, start=periode.start, end=periode.end)
    assert [p["score"] for p in serie] == resultats["par point"]

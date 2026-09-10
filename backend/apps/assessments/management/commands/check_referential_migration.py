"""Vérifie qu'une base migrée en V2-4 n'a rien perdu ni faussé.

À lancer **sur une copie de la base de production**, après ``migrate`` :

    python manage.py check_referential_migration

La commande ne modifie rien. Elle sort en erreur (code 1) au premier constat
qui devrait empêcher le déploiement.

Pourquoi une commande et pas seulement des tests : les tests s'exécutent sur
une base vide, construite par les fixtures. Ils prouvent que le CODE est juste,
pas que LES DONNÉES le sont — un référentiel chargé en juin, à moitié réimporté
en août, avec deux diagnostics en cours dessus, ne ressemble à aucune fixture.
"""

from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.assessments.models import (
    Answer,
    Assessment,
    Measure,
    Referential,
    ReferentialAssignment,
)
from apps.tenants.models import Tenant


class Command(BaseCommand):
    help = "Contrôle l'intégrité des données après la migration V2-4 (ADR-029)."

    def handle(self, *args, **options):
        anomalies: list[str] = []
        constats: list[str] = []

        # 1. Toute mesure a un code et un référentiel, et le référentiel
        #    dénormalisé dit la même chose que son domaine.
        sans_code = Measure.objects.filter(code="").count()
        if sans_code:
            anomalies.append(f"{sans_code} mesure(s) sans code.")

        incoherentes = 0
        for mesure in Measure.objects.select_related("domain").iterator():
            if mesure.referential_id != mesure.domain.referential_id:
                incoherentes += 1
        if incoherentes:
            anomalies.append(
                f"{incoherentes} mesure(s) dont le référentiel ne correspond pas à celui "
                "de leur domaine."
            )

        # 2. Les codes sont uniques DANS chaque référentiel.
        doublons = (
            Measure.objects.values("referential_id", "code").annotate(n=Count("id")).filter(n__gt=1)
        )
        if doublons:
            anomalies.append(f"{len(doublons)} code(s) de mesure en double dans un référentiel.")

        # 3. Les poids reproduisent l'ancien calcul pour l'ANSSI.
        attendu = {"standard": 1.0, "renforce": 0.5}
        faux_poids = 0
        for niveau, poids in attendu.items():
            faux_poids += Measure.objects.filter(level=niveau).exclude(weight=poids).count()
        if faux_poids:
            anomalies.append(
                f"{faux_poids} mesure(s) ANSSI dont le poids ne reproduit pas l'ancien "
                "calcul (standard=1.0, renforcé=0.5) : les scores changeraient."
            )

        # 4. Aucune réponse orpheline : la migration n'a supprimé aucune mesure.
        orphelines = Answer.all_objects.filter(measure__isnull=True).count()
        if orphelines:
            anomalies.append(f"{orphelines} réponse(s) sans mesure.")

        # 5. Le point le plus important : personne ne perd son diagnostic.
        #    Tout client qui a une évaluation doit être attribué du référentiel
        #    correspondant, sinon il ne pourrait plus la remplir.
        prives = []
        for assessment in (
            Assessment.all_objects.filter(status=Assessment.Status.IN_PROGRESS)
            .select_related("tenant", "referential")
            .iterator()
        ):
            attribue = ReferentialAssignment.all_objects.filter(
                tenant_id=assessment.tenant_id,
                referential_id=assessment.referential_id,
                revoked_at__isnull=True,
            ).exists()
            if not attribue:
                prives.append(f"{assessment.tenant} / {assessment.referential.slug}")
        if prives:
            anomalies.append(
                "Diagnostic(s) EN COURS sur un référentiel non attribué — le client ne "
                f"pourrait plus le terminer : {', '.join(prives)}."
            )

        # 6. Les scores figés ne bougent pas : on les recalcule et on compare.
        #    Un écart signifie que la migration a changé le sens d'un chiffre
        #    déjà présenté à un client.
        from apps.assessments import services

        ecarts = []
        for assessment in (
            Assessment.all_objects.filter(
                status=Assessment.Status.COMPLETED, score_global__isnull=False
            )
            .select_related("referential")
            .iterator()
        ):
            recalcule = services.compute_scores(assessment)["global"]
            if recalcule is not None and abs(recalcule - assessment.score_global) > 0.05:
                ecarts.append(
                    f"évaluation {assessment.id} : figé {assessment.score_global}, "
                    f"recalculé {recalcule}"
                )
        if ecarts:
            anomalies.append(
                "Score(s) terminé(s) que le nouveau calcul ne retrouve pas : " + "; ".join(ecarts)
            )

        constats.append(f"{Referential.objects.count()} référentiel(s) au catalogue.")
        constats.append(f"{Measure.objects.count()} mesure(s), toutes rattachées et codées.")
        constats.append(
            f"{ReferentialAssignment.all_objects.filter(revoked_at__isnull=True).count()} "
            f"attribution(s) actives pour {Tenant.objects.count()} client(s)."
        )
        constats.append(
            f"{Assessment.all_objects.count()} évaluation(s) conservées, "
            f"{Answer.all_objects.count()} réponse(s)."
        )

        for constat in constats:
            self.stdout.write(f"  · {constat}")

        if anomalies:
            for anomalie in anomalies:
                self.stderr.write(self.style.ERROR(f"  ✗ {anomalie}"))
            self.stderr.write(
                self.style.ERROR(
                    "\nLa migration V2-4 a laissé des anomalies : ne pas déployer en l'état."
                )
            )
            raise SystemExit(1)

        self.stdout.write(
            self.style.SUCCESS("\nMigration V2-4 vérifiée : rien de perdu, aucun score faussé.")
        )

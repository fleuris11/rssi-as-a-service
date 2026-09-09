"""API de restitution (V2-3, ADR-028).

Trois points d'entrée, un par usage : consulter à l'écran, produire le
document du comité, reprendre les chiffres dans un tableur.

La période est résolue **côté serveur** à partir d'une clé (`?period=quarter`)
ou de deux dates. Le frontend n'en calcule aucune : deux implémentations du
même trimestre finiraient par diverger, et l'écart se verrait le jour où le
PDF ne dirait pas la même chose que la page.
"""

import csv
from datetime import date

from django.http import HttpResponse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenants.permissions import IsTenantMember

from . import exports, periods, report, services


def _resolve_period(request) -> periods.Period:
    cle = request.query_params.get("period")
    debut = request.query_params.get("start")
    fin = request.query_params.get("end")

    def _date(valeur, nom):
        if not valeur:
            return None
        try:
            return date.fromisoformat(valeur)
        except ValueError as exc:
            raise periods.PeriodError(
                f"Date {nom} invalide (format attendu : AAAA-MM-JJ)."
            ) from exc

    return periods.resolve(cle, start=_date(debut, "de début"), end=_date(fin, "de fin"))


class PeriodAwareView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request):
        try:
            periode = _resolve_period(request)
        except periods.PeriodError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self.render(request, periode)


class DashboardView(PeriodAwareView):
    """GET /api/v1/reporting/dashboard/ — les indicateurs de la période."""

    def render(self, request, periode):
        return Response(
            {
                **services.build_dashboard(request.tenant, periode),
                # Servi avec la réponse pour que l'écran n'ait pas à recopier
                # la liste des périodes : une liste recopiée finit par diverger.
                "available_periods": periods.available(),
            }
        )


class ReportView(PeriodAwareView):
    """GET /api/v1/reporting/report/ — le rapport de comité, en JSON.

    Le même contenu que le PDF, servi en données : c'est ce qui permet de
    tester le fond du document sans dépendre du moteur de rendu, et de
    prévisualiser le rapport à l'écran avant de l'imprimer.
    """

    def render(self, request, periode):
        return Response(services.build_report(request.tenant, periode))


class ReportPdfView(PeriodAwareView):
    """GET /api/v1/reporting/report.pdf — le document du comité."""

    def render(self, request, periode):
        donnees = services.build_report(request.tenant, periode)
        try:
            pdf = report.render_pdf(donnees)
        except report.PdfUnavailableError as exc:
            # Le moteur de rendu est une dépendance système (ADR-012). S'il
            # manque, on le dit sans exposer l'erreur d'installation : c'est
            # notre configuration, pas l'affaire du client.
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        reponse = HttpResponse(pdf, content_type="application/pdf")
        reponse["Content-Disposition"] = (
            f'attachment; filename="{exports.filename(donnees, "pdf")}"'
        )
        return reponse


class ExportCsvView(PeriodAwareView):
    """GET /api/v1/reporting/export.csv — les chiffres, pour retravail.

    Point-virgule et BOM UTF-8 : c'est ce qu'attend Excel en configuration
    française. Sans eux, le fichier s'ouvre en une seule colonne et les
    accents sont illisibles — et le RSSI retourne à son tableur à la main,
    c'est-à-dire exactement ce que cette version cherche à supprimer.
    """

    def render(self, request, periode):
        donnees = services.build_report(request.tenant, periode)
        reponse = HttpResponse(content_type="text/csv; charset=utf-8")
        reponse["Content-Disposition"] = (
            f'attachment; filename="{exports.filename(donnees, "csv")}"'
        )
        reponse.write("﻿")
        writer = csv.writer(reponse, delimiter=";")
        for ligne in exports.csv_rows(donnees):
            writer.writerow(ligne)
        return reponse

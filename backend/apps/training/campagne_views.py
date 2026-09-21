"""Piloter une campagne : import, relances, rapports, preuves (F3).

Les permissions ne sont pas uniformes, et la différence est le sujet :

- les **agrégats** sont lisibles par tout membre de l'entreprise ;
- le **suivi nominatif** est réservé aux administrateurs, et sa consultation
  est tracée. C'est la contrepartie que le RGPD attend quand un employeur
  traite les données de ses salariés (ADR-041) ;
- l'**écriture** (import, réglage des relances, confirmation d'une preuve) est
  réservée aux administrateurs et soumise à l'offre.
"""

import csv
import io

from django.http import HttpResponse
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing import api_guards, features
from apps.tenants.permissions import IsTenantAdmin

from . import campagnes, exports, preuves, rapport_pdf, rapports
from .models import Course, MeasureSuggestion
from .permissions import IsTenantAdminForWrites
from .serializers import ImportSerializer, ReminderPolicySerializer


def _cours(request):
    """Le cours visé par un rapport, ou None pour « tous »."""
    slug = request.query_params.get("course")
    if not slug:
        return None
    cours = Course.objects.filter(slug=slug).first()
    if cours is None:
        raise NotFound("Ce cours n'existe pas.")
    return cours


class RelancesView(APIView):
    """Le rythme des relances — et le bouton pour tout couper."""

    permission_classes = [permissions.IsAuthenticated, IsTenantAdminForWrites]

    def get(self, request):
        return Response(ReminderPolicySerializer(campagnes.politique(request.tenant)).data)

    def put(self, request):
        api_guards.ensure_feature(request.tenant, features.TRAINING)
        serializer = ReminderPolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reglage = campagnes.regler_la_politique(
            tenant=request.tenant, actor=request.user, **serializer.validated_data
        )
        return Response(ReminderPolicySerializer(reglage).data)


class ImportView(APIView):
    """Déclarer des salariés depuis une liste."""

    permission_classes = [permissions.IsAuthenticated, IsTenantAdminForWrites]

    def post(self, request):
        api_guards.ensure_feature(request.tenant, features.TRAINING)
        serializer = ImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            resultat = campagnes.importer_des_salaries(
                tenant=request.tenant,
                contenu=serializer.validated_data["content"],
                actor=request.user,
            )
        except campagnes.ImportRefuse as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        return Response(resultat)


class RapportView(APIView):
    """Les agrégats. Rien de nominatif, donc lisible par tout membre."""

    permission_classes = [permissions.IsAuthenticated, IsTenantAdminForWrites]

    def get(self, request):
        return Response(rapports.rapport(request.tenant, course=_cours(request)))


class ExportRapportView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantAdminForWrites]

    def get(self, request, extension):
        rapport = rapports.rapport(request.tenant, course=_cours(request))

        if extension == "csv":
            tampon = io.StringIO()
            # Point-virgule et BOM : c'est ce qu'attend un tableur français,
            # et sans le BOM les accents sortent en mojibake.
            graveur = csv.writer(tampon, delimiter=";")
            graveur.writerows(exports.csv_rows(rapport))
            reponse = HttpResponse("﻿" + tampon.getvalue(), content_type="text/csv; charset=utf-8")
            reponse["Content-Disposition"] = (
                f'attachment; filename="{exports.filename(rapport, "csv")}"'
            )
            return reponse

        try:
            pdf = rapport_pdf.render_pdf(rapport)
        except rapport_pdf.PdfUnavailableError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        reponse = HttpResponse(pdf, content_type="application/pdf")
        reponse["Content-Disposition"] = (
            f'attachment; filename="{exports.filename(rapport, "pdf")}"'
        )
        return reponse


class SuiviNominatifView(APIView):
    """Qui relancer. Administrateurs seulement, et tracé.

    Sans score : il n'est d'aucune utilité pour relancer, et sa présence
    transformerait cette liste en classement dès qu'un tableur s'en emparerait.
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]

    def get(self, request):
        lignes = rapports.suivi_nominatif(
            request.tenant, actor=request.user, course=_cours(request)
        )
        return Response(
            {
                "results": lignes,
                "notice": (
                    "Cette liste sert à relancer. Sa consultation est enregistrée, et elle "
                    "ne comporte aucun résultat individuel."
                ),
            }
        )


def _preuve_en_clair(suggestion: MeasureSuggestion) -> dict:
    return {
        "id": str(suggestion.id),
        "course_title": suggestion.course.title,
        "measure_code": suggestion.measure_code,
        "measure_title": suggestion.measure_title,
        "learners_total": suggestion.learners_total,
        "learners_done": suggestion.learners_done,
        "participation_rate": suggestion.participation_rate,
        "success_rate": suggestion.success_rate,
        "period_start": suggestion.period_start,
        "period_end": suggestion.period_end,
        "status": suggestion.status,
        "evidence": preuves.texte_de_preuve(suggestion),
    }


class PreuvesView(APIView):
    """Les propositions de renseignement du diagnostic."""

    permission_classes = [permissions.IsAuthenticated, IsTenantAdminForWrites]

    def get(self, request):
        return Response([_preuve_en_clair(s) for s in preuves.en_attente(request.tenant)])


class PreuveDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]

    def _proposition(self, suggestion_id) -> MeasureSuggestion:
        suggestion = MeasureSuggestion.objects.filter(id=suggestion_id).first()
        if suggestion is None:
            raise NotFound("Cette proposition n'existe pas.")
        return suggestion

    def post(self, request, suggestion_id):
        """Confirmer : reporte la preuve dans le diagnostic en cours."""
        api_guards.ensure_feature(request.tenant, features.TRAINING)
        suggestion = self._proposition(suggestion_id)
        try:
            preuves.confirmer(suggestion=suggestion, actor=request.user)
        except preuves.PreuveError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(_preuve_en_clair(suggestion))

    def delete(self, request, suggestion_id):
        """Écarter : on ne la reproposera pas."""
        suggestion = self._proposition(suggestion_id)
        try:
            preuves.ecarter(suggestion=suggestion, actor=request.user)
        except preuves.PreuveError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(_preuve_en_clair(suggestion))

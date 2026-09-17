"""Deux surfaces, deux publics, aucune permission commune.

``session/`` — l'apprenant. Aucune authentification : c'est le jeton du lien
qui porte l'autorisation. ``authentication_classes = []`` n'est pas une
omission mais une consigne : sans cela, un jeton JWT périmé traînant dans le
navigateur d'un salarié qui a par ailleurs un compte ferait échouer la requête
avant d'atteindre la vue.

``pilotage/`` — celui qui organise la campagne. Membre de l'entreprise,
administrateur pour tout ce qui écrit.
"""

from django.http import HttpResponse
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing import api_guards, features

from . import certificates, services
from .models import Certificate, Course, Enrollment, Learner
from .permissions import IsTenantAdminForWrites
from .serializers import (
    EnrollmentSerializer,
    GrantAttemptsSerializer,
    LearnerSerializer,
    QuizSubmissionSerializer,
    ScreenDoneSerializer,
)
from .throttling import SessionFormationThrottle

#: Le jeton voyage en en-tête, jamais dans l'adresse de l'API : une URL finit
#: dans les journaux du serveur, dans l'historique du navigateur et dans le
#: référent envoyé aux sites tiers. L'adresse de la PAGE le contient — c'est
#: inévitable pour un lien qu'on envoie par courriel — mais les appels d'API
#: qu'elle déclenche, non.
ENTETE_JETON = "HTTP_X_FORMATION_TOKEN"


class VueApprenant(APIView):
    """Socle des vues de l'apprenant : résolution du jeton, et cloisonnement."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [SessionFormationThrottle]

    def session(self, request):
        try:
            return services.resoudre_session(request.META.get(ENTETE_JETON, ""))
        except services.SessionIntrouvable as exc:
            # 404 et non 403 : « ce lien n'existe pas » et « ce lien a expiré »
            # doivent être indiscernables de l'extérieur. Le champ ``reason``
            # sert à l'interface pour afficher une page d'explication plutôt
            # qu'une erreur technique — un salarié qui lit « 403 Forbidden »
            # abandonne.
            raise NotFound({"detail": str(exc), "reason": "link"}) from exc


class SessionView(VueApprenant):
    """L'état complet du parcours : le cours, la progression, le quiz."""

    def get(self, request):
        inscription = self.session(request)
        with services.contexte_du_client(inscription.tenant):
            return Response(services.etat_de_session(inscription))


class ScreenDoneView(VueApprenant):
    def post(self, request):
        inscription = self.session(request)
        serializer = ScreenDoneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with services.contexte_du_client(inscription.tenant):
            try:
                etat = services.marquer_ecran_vu(
                    enrollment=inscription, screen_id=serializer.validated_data["screen_id"]
                )
            except services.TrainingError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            return Response(etat)


class QuizView(VueApprenant):
    def post(self, request):
        inscription = self.session(request)
        serializer = QuizSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with services.contexte_du_client(inscription.tenant):
            try:
                resultat = services.soumettre_le_quiz(
                    enrollment=inscription,
                    reponses={
                        str(question): [str(choix) for choix in choisis]
                        for question, choisis in serializer.validated_data["answers"].items()
                    },
                )
            except services.QuizRefuse as exc:
                # 409 : la demande est bien formée, c'est l'état qui s'y oppose
                # (essais épuisés, cours non parcouru, déjà réussi).
                return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
            return Response(resultat)


class CertificateView(VueApprenant):
    """L'attestation, en PDF. Servie à qui détient le lien de CETTE
    inscription, et à personne d'autre."""

    def get(self, request):
        inscription = self.session(request)
        with services.contexte_du_client(inscription.tenant):
            attestation = Certificate.objects.filter(enrollment=inscription).first()
            if attestation is None:
                raise NotFound({"detail": "Aucune attestation pour ce parcours.", "reason": "none"})
            try:
                pdf = certificates.render_pdf(attestation)
            except certificates.PdfUnavailableError as exc:
                return Response(
                    {"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            reponse = HttpResponse(pdf, content_type="application/pdf")
            reponse["Content-Disposition"] = (
                f'attachment; filename="{certificates.filename(attestation)}"'
            )
            return reponse


class AccessRequestView(VueApprenant):
    """« Mon lien ne marche plus » — depuis la page d'expiration.

    Répond toujours la même chose, que la demande ait été transmise ou qu'elle
    l'ait déjà été aujourd'hui : le salarié n'a pas à connaître le rythme
    d'envoi, et l'uniformité évite d'en faire un moyen de sonder l'état d'une
    inscription.
    """

    def post(self, request):
        try:
            services.demander_un_acces(request.META.get(ENTETE_JETON, ""))
        except services.SessionIntrouvable as exc:
            raise NotFound({"detail": str(exc), "reason": "link"}) from exc
        return Response(
            {
                "detail": "Votre demande a été transmise aux responsables de votre "
                "entreprise. Ils vous renverront un accès."
            },
            status=status.HTTP_202_ACCEPTED,
        )


# --- Pilotage : composer et suivre une campagne -----------------------------


class VuePilotage(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantAdminForWrites]


def _inscription_en_clair(inscription, lien=None) -> dict:
    """Ce que la console de l'entreprise voit d'une inscription.

    ``lien`` n'est présent qu'au moment de l'émission : le jeton n'est stocké
    que haché, il n'existe en clair que dans la réponse qui suit sa création.
    Le relire plus tard est impossible — par construction, et c'est voulu.
    """
    attestation = getattr(inscription, "certificate", None)
    return {
        "id": str(inscription.id),
        "learner": {
            "id": str(inscription.learner_id),
            "full_name": inscription.learner.full_name,
            "email": inscription.learner.email,
        },
        "course_title": inscription.version.course.title,
        "course_version": inscription.version.number,
        "due_date": inscription.due_date,
        "expires_at": inscription.expires_at,
        "first_opened_at": inscription.first_opened_at,
        "revoked_at": inscription.revoked_at,
        "attempts_allowed": inscription.attempts_allowed,
        "certificate_serial": attestation.serial if attestation else "",
        "passed": attestation is not None,
        **({"link": lien} if lien else {}),
    }


class CatalogueView(VuePilotage):
    """Les cours proposés à cette entreprise."""

    def get(self, request):
        cours = services.cours_attribues(request.tenant)
        return Response(
            [
                {
                    "slug": c.slug,
                    "title": c.title,
                    "summary": c.summary,
                    "estimated_minutes": c.published_version.estimated_minutes,
                    "pass_threshold": c.published_version.pass_threshold,
                    "max_attempts": c.published_version.max_attempts,
                    "screens": c.published_version.screens.count(),
                    "questions": c.published_version.questions.count(),
                }
                for c in cours
            ]
        )


class LearnersView(VuePilotage):
    def get(self, request):
        return Response(
            [
                {
                    "id": str(salarie.id),
                    "full_name": salarie.full_name,
                    "email": salarie.email,
                    "is_active": salarie.is_active,
                    "has_account": salarie.user_id is not None,
                }
                for salarie in Learner.objects.all()
            ]
        )

    def post(self, request):
        api_guards.ensure_feature(request.tenant, features.TRAINING)
        serializer = LearnerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            salarie = services.creer_apprenant(
                tenant=request.tenant,
                full_name=serializer.validated_data["full_name"],
                email=serializer.validated_data["email"],
                actor=request.user,
            )
        except services.InscriptionRefusee as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(
            {"id": str(salarie.id), "full_name": salarie.full_name, "email": salarie.email},
            status=status.HTTP_201_CREATED,
        )


class EnrollmentsView(VuePilotage):
    def get(self, request):
        inscriptions = (
            Enrollment.objects.select_related("learner", "version", "version__course")
            .prefetch_related("certificate")
            .all()
        )
        return Response([_inscription_en_clair(i) for i in inscriptions])

    def post(self, request):
        api_guards.ensure_feature(request.tenant, features.TRAINING)
        serializer = EnrollmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        salarie = Learner.objects.filter(id=serializer.validated_data["learner_id"]).first()
        if salarie is None:
            raise NotFound("Ce salarié ne figure pas dans votre entreprise.")
        cours = Course.objects.filter(slug=serializer.validated_data["course_slug"]).first()
        if cours is None:
            raise NotFound("Ce cours n'existe pas.")

        try:
            inscription, jeton = services.inscrire(
                tenant=request.tenant,
                learner=salarie,
                course=cours,
                due_date=serializer.validated_data["due_date"],
                actor=request.user,
            )
        except services.InscriptionRefusee as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(
            _inscription_en_clair(inscription, lien=services.lien_de_session(jeton)),
            status=status.HTTP_201_CREATED,
        )


class EnrollmentDetailView(VuePilotage):
    def _inscription(self, enrollment_id):
        inscription = (
            Enrollment.objects.select_related("learner", "version", "version__course")
            .filter(id=enrollment_id)
            .first()
        )
        if inscription is None:
            raise NotFound("Cette inscription n'existe pas.")
        return inscription

    def delete(self, request, enrollment_id):
        """Retire l'accès. Immédiat, et non à l'échéance."""
        inscription = self._inscription(enrollment_id)
        services.revoquer(enrollment=inscription, actor=request.user)
        return Response(_inscription_en_clair(inscription))


class EnrollmentLinkView(VuePilotage):
    """Réémettre le lien. L'ancien meurt à cet instant."""

    def post(self, request, enrollment_id):
        api_guards.ensure_feature(request.tenant, features.TRAINING)
        inscription = EnrollmentDetailView()._inscription(enrollment_id)
        try:
            jeton = services.renouveler_le_lien(enrollment=inscription, actor=request.user)
        except services.InscriptionRefusee as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(_inscription_en_clair(inscription, lien=services.lien_de_session(jeton)))


class EnrollmentAttemptsView(VuePilotage):
    """Réarmer le quiz pour un salarié donné."""

    def post(self, request, enrollment_id):
        api_guards.ensure_feature(request.tenant, features.TRAINING)
        inscription = EnrollmentDetailView()._inscription(enrollment_id)
        serializer = GrantAttemptsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.accorder_des_essais(
                enrollment=inscription,
                nombre=serializer.validated_data["count"],
                actor=request.user,
            )
        except services.InscriptionRefusee as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_inscription_en_clair(inscription))

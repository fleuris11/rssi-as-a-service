"""L'API du studio (F2).

Qui peut écrire quoi, et c'est la seule question difficile de ce module :

- **l'exploitant** écrit les cours de la BIBLIOTHÈQUE (``owner_tenant`` nul) ;
- **un client** écrit les siens, et seulement les siens.

Un administrateur plateforme ne peut donc PAS modifier le cours d'un client,
bien qu'il en ait techniquement le pouvoir : il n'entre pas dans les espaces
clients (ADR-014). Il peut lire un cours de sa bibliothèque, pas celui qu'un
client en a dérivé — la copie appartient au client, y compris ses phrases.
"""

from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing import api_guards, features

from . import studio, variables
from .models import Course, CourseVersion
from .serializers import (
    CourseSerializer,
    DuplicationSerializer,
    NouvelleVersionSerializer,
    OrdreEcransSerializer,
    QuestionSerializer,
    ScreenSerializer,
)


class PeutComposer(permissions.BasePermission):
    """Administrateur plateforme, ou administrateur d'un client dont l'offre
    comprend le studio."""

    message = "L'écriture de cours n'est pas ouverte à votre compte."

    def has_permission(self, request, view):
        if getattr(request.user, "is_staff", False):
            return True
        adhesion = getattr(request, "membership", None)
        # Le RÔLE se juge ici ; l'OFFRE se juge dans la vue, à l'écriture
        # seulement. Refuser ici pour cause d'offre rendrait 403 — « vous
        # n'avez pas le droit » — là où le bon refus est 402, qui nomme
        # l'offre à prendre (ADR-019). La nuance porte tout le message
        # commercial, et la lecture reste servie.
        return adhesion is not None and adhesion.role == adhesion.Role.ADMIN


class VueStudio(APIView):
    permission_classes = [permissions.IsAuthenticated, PeutComposer]

    @property
    def est_exploitant(self):
        return getattr(self.request.user, "is_staff", False)

    def client(self):
        return None if self.est_exploitant else self.request.tenant

    def garde_de_production(self):
        """Le refus commercial, posé sur ce qui PRODUIT — jamais sur la
        lecture (ADR-019). Sans objet pour l'exploitant, qui n'a pas d'offre."""
        if not self.est_exploitant:
            api_guards.ensure_feature(self.request.tenant, features.TRAINING_STUDIO)

    def cours_modifiable(self, course_id) -> Course:
        cours = Course.objects.filter(id=course_id).first()
        if cours is None:
            raise NotFound("Ce cours n'existe pas.")
        if self.est_exploitant:
            if not cours.est_de_la_bibliotheque:
                # Le cours d'un client ne s'ouvre pas depuis la console.
                raise PermissionDenied("Ce cours appartient à un client.")
        elif cours.owner_tenant_id != self.request.tenant.id:
            raise NotFound("Ce cours n'existe pas.")
        return cours

    def version_modifiable(self, version_id) -> CourseVersion:
        version = CourseVersion.objects.select_related("course").filter(id=version_id).first()
        if version is None:
            raise NotFound("Cette version n'existe pas.")
        self.cours_modifiable(version.course_id)
        return version


def _cours_en_clair(cours: Course) -> dict:
    publiee = cours.published_version
    brouillon = cours.draft_version
    return {
        "id": str(cours.id),
        "slug": cours.slug,
        "title": cours.title,
        "summary": cours.summary,
        "is_library": cours.est_de_la_bibliotheque,
        "derived_from": str(cours.derived_from_id) if cours.derived_from_id else "",
        "published_version": publiee.number if publiee else None,
        "draft_version": brouillon.number if brouillon else None,
        "draft_version_id": str(brouillon.id) if brouillon else "",
        "published_version_id": str(publiee.id) if publiee else "",
        "screens": (brouillon or publiee).screens.count() if (brouillon or publiee) else 0,
    }


class CoursListView(VueStudio):
    """Les cours que je peux écrire, et ceux que je peux dériver."""

    def get(self, request):
        if self.est_exploitant:
            miens = Course.objects.filter(owner_tenant__isnull=True)
            bibliotheque = Course.objects.none()
        else:
            miens = Course.objects.filter(owner_tenant=request.tenant)
            # La bibliothèque est lisible par tout client qui a le studio :
            # c'est elle qui lui évite de partir d'une page blanche.
            bibliotheque = Course.objects.filter(owner_tenant__isnull=True, is_active=True)

        return Response(
            {
                "mine": [_cours_en_clair(c) for c in miens],
                "library": [_cours_en_clair(c) for c in bibliotheque],
                # Le studio propose les variables ; on n'écrit pas une
                # variable qui n'existe pas.
                "variables": variables.catalogue(),
            }
        )

    def post(self, request):
        self.garde_de_production()
        serializer = CourseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cours = studio.creer_cours(
            title=serializer.validated_data["title"],
            summary=serializer.validated_data.get("summary", ""),
            owner_tenant=self.client(),
            actor=request.user,
        )
        return Response(_cours_en_clair(cours), status=status.HTTP_201_CREATED)


class CoursDetailView(VueStudio):
    def get(self, request, course_id):
        cours = self.cours_modifiable(course_id)
        return Response(_cours_en_clair(cours))

    def post(self, request, course_id):
        """Ouvrir une nouvelle version à l'écriture."""
        self.garde_de_production()
        cours = self.cours_modifiable(course_id)
        serializer = NouvelleVersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            version = studio.nouvelle_version(
                cours, change_note=serializer.validated_data.get("change_note", "")
            )
        except studio.StudioError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(studio.apercu(version), status=status.HTTP_201_CREATED)


class DuplicationView(VueStudio):
    """Dériver un cours — le sien, ou un cours de la bibliothèque."""

    def post(self, request, course_id):
        self.garde_de_production()
        source = Course.objects.filter(id=course_id).first()
        if source is None:
            raise NotFound("Ce cours n'existe pas.")

        # On peut dupliquer un cours de la bibliothèque, ou l'un des siens.
        # Jamais celui d'un autre client.
        lisible = source.est_de_la_bibliotheque or (
            not self.est_exploitant and source.owner_tenant_id == request.tenant.id
        )
        if not lisible:
            raise NotFound("Ce cours n'existe pas.")

        serializer = DuplicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            copie = studio.dupliquer(
                cours=source,
                owner_tenant=self.client(),
                actor=request.user,
                titre=serializer.validated_data.get("title") or None,
            )
        except studio.StudioError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(_cours_en_clair(copie), status=status.HTTP_201_CREATED)


class VersionView(VueStudio):
    """L'aperçu : le cours tel que l'apprenant le verra."""

    def get(self, request, version_id):
        version = self.version_modifiable(version_id)
        refus, avertissements = studio.controles_avant_publication(version)
        return Response(
            {
                **studio.apercu(version, tenant=self.client()),
                "blocking": refus,
                "warnings": avertissements,
            }
        )


class PublicationView(VueStudio):
    def post(self, request, version_id):
        self.garde_de_production()
        version = self.version_modifiable(version_id)
        try:
            studio.publier(version)
        except studio.StudioError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(_cours_en_clair(version.course))


class EcransView(VueStudio):
    def post(self, request, version_id):
        self.garde_de_production()
        version = self.version_modifiable(version_id)
        serializer = ScreenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        donnees = serializer.validated_data
        try:
            ecran = studio.ecrire_ecran(
                version=version,
                screen_id=donnees.get("screen_id"),
                title=donnees["title"],
                content=donnees["content"],
                estimated_seconds=donnees.get("estimated_seconds", 60),
            )
        except studio.VersionVerrouillee as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except studio.StudioError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # blocs invalides
            from .blocks import BlocInvalide

            if isinstance(exc, BlocInvalide):
                # Les problèmes sont rendus TOUS ENSEMBLE : corriger huit blocs
                # en découvrant les erreurs une par une est une perte de temps.
                return Response(
                    {"detail": "Le contenu n'est pas valide.", "problemes": exc.problemes},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            raise
        return Response({"id": str(ecran.id), "order": ecran.order}, status=status.HTTP_200_OK)

    def delete(self, request, version_id, screen_id):
        self.garde_de_production()
        version = self.version_modifiable(version_id)
        try:
            studio.supprimer_ecran(version=version, screen_id=screen_id)
        except studio.VersionVerrouillee as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except studio.StudioError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrdreEcransView(VueStudio):
    def post(self, request, version_id):
        self.garde_de_production()
        version = self.version_modifiable(version_id)
        serializer = OrdreEcransSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            studio.reordonner_ecrans(version=version, ordre_ids=serializer.validated_data["order"])
        except studio.VersionVerrouillee as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except studio.StudioError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(studio.apercu(version))


class QuestionsView(VueStudio):
    def post(self, request, version_id):
        self.garde_de_production()
        version = self.version_modifiable(version_id)
        serializer = QuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        donnees = serializer.validated_data
        try:
            question = studio.ecrire_question(
                version=version,
                question_id=donnees.get("question_id"),
                text=donnees["text"],
                kind=donnees["kind"],
                explanation=donnees["explanation"],
                screen_id=donnees["screen_id"],
                choix=donnees["choices"],
            )
        except studio.VersionVerrouillee as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except studio.StudioError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"id": str(question.id), "order": question.order})

    def delete(self, request, version_id, question_id):
        self.garde_de_production()
        version = self.version_modifiable(version_id)
        try:
            studio.supprimer_question(version=version, question_id=question_id)
        except studio.VersionVerrouillee as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except studio.StudioError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

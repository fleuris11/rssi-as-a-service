"""Console — proposer la bibliothèque de cours à un client, et la retirer.

Le chemin n'existait pas : `attribuer_cours` n'était appelé que par des
commandes et des tests. Ce fichier tient les quatre propriétés qui comptent :
seul un compte d'exploitation peut le faire, un cours écrit par un client ne se
propose pas à un autre, le retrait ne casse aucun parcours en cours, et tout
passe au journal d'audit.
"""

import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework import status

from apps.platform_admin.models import AdminAuditLog, PlatformAdminProfile
from apps.training import services as training_services
from apps.training.models import Course, CourseAssignment, CourseVersion, Enrollment, Screen

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng!Passw0rd123"


@pytest.fixture
def staff_headers(api_client, user_factory):
    staff = user_factory(email="exploitant-formation@example.com", is_staff=True)
    PlatformAdminProfile.objects.create(user=staff, level=PlatformAdminProfile.Level.FULL)
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": staff.email, "password": PASSWORD}, format="json"
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {response.data['access']}"}


@pytest.fixture
def bibliotheque():
    call_command("seed_catalogue_formation", verbosity=0)
    return Course.objects.filter(owner_tenant__isnull=True).order_by("slug")


def url(tenant):
    return reverse("platform-client-courses", args=[tenant.id])


# --- Les droits -------------------------------------------------------------


def test_un_compte_de_client_n_y_accede_pas(api_client, tenant, tenant_owner, bibliotheque):
    response = api_client.post(
        reverse("token-obtain-pair"),
        {"email": tenant_owner.email, "password": PASSWORD},
        format="json",
    )
    entetes = {"HTTP_AUTHORIZATION": f"Bearer {response.data['access']}"}

    assert api_client.get(url(tenant), **entetes).status_code in (
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    )


def test_sans_jeton_c_est_refuse(api_client, tenant):
    assert api_client.get(url(tenant)).status_code == status.HTTP_401_UNAUTHORIZED


# --- Voir -------------------------------------------------------------------


def test_la_bibliotheque_est_listee_avec_ses_chiffres(
    api_client, tenant, staff_headers, bibliotheque
):
    reponse = api_client.get(url(tenant), **staff_headers)

    assert reponse.status_code == status.HTTP_200_OK
    assert reponse.data["assigned"] == []
    assert len(reponse.data["available"]) == bibliotheque.count()
    premier = reponse.data["available"][0]
    # La durée est CALCULÉE depuis les écrans : c'est le chiffre sur lequel un
    # salarié décide de commencer maintenant ou plus tard.
    assert premier["minutes"] > 0
    assert premier["screens"] > 0
    assert premier["questions"] >= 5


def test_un_cours_ecrit_par_un_client_n_est_pas_proposable(
    api_client, tenant, tenant_factory, user_factory, staff_headers
):
    autre = tenant_factory(user_factory(email="proprio@exemple.test"), name="Autre")
    cours = Course.objects.create(
        slug="cours-maison", title="Notre procédure interne", owner_tenant=autre
    )
    version = CourseVersion.objects.create(course=cours, number=1, published_at="2026-09-01T08:00Z")
    Screen.objects.create(
        version=version,
        order=1,
        title="Un écran",
        content=[{"type": "paragraphe", "texte": "Du contenu."}],
    )

    reponse = api_client.get(url(tenant), **staff_headers)
    assert "cours-maison" not in [c["slug"] for c in reponse.data["available"]]

    # Et il n'est pas non plus attribuable de force.
    refus = api_client.post(url(tenant), {"course": "cours-maison"}, format="json", **staff_headers)
    assert refus.status_code == status.HTTP_404_NOT_FOUND


# --- Proposer et retirer ----------------------------------------------------


def test_proposer_un_cours(api_client, tenant, staff_headers, bibliotheque):
    slug = bibliotheque.first().slug

    reponse = api_client.post(url(tenant), {"course": slug}, format="json", **staff_headers)

    assert reponse.status_code == status.HTTP_200_OK
    assert slug in [c["slug"] for c in reponse.data["assigned"]]
    assert slug not in [c["slug"] for c in reponse.data["available"]]
    assert CourseAssignment.all_objects.filter(tenant=tenant, course__slug=slug).exists()

    trace = AdminAuditLog.objects.get(action=AdminAuditLog.Action.COURSE_ASSIGNED)
    assert trace.tenant_id == tenant.id


def test_proposer_deux_fois_ne_double_rien(api_client, tenant, staff_headers, bibliotheque):
    slug = bibliotheque.first().slug
    api_client.post(url(tenant), {"course": slug}, format="json", **staff_headers)
    api_client.post(url(tenant), {"course": slug}, format="json", **staff_headers)

    assert CourseAssignment.all_objects.filter(tenant=tenant, course__slug=slug).count() == 1


def test_un_cours_inconnu_donne_404(api_client, tenant, staff_headers):
    reponse = api_client.post(url(tenant), {"course": "inexistant"}, format="json", **staff_headers)
    assert reponse.status_code == status.HTTP_404_NOT_FOUND


def test_retirer_un_cours_ne_casse_aucun_parcours(
    api_client, tenant, tenant_owner, staff_headers, bibliotheque
):
    """Une inscription pointe vers une VERSION, pas vers une attribution : le
    salarié en cours de route termine, et son attestation reste."""
    cours = bibliotheque.first()
    api_client.post(url(tenant), {"course": cours.slug}, format="json", **staff_headers)

    with training_services.contexte_du_client(tenant):
        salarie = training_services.creer_apprenant(
            tenant=tenant, full_name="Claude Martin", email="claude@exemple.test"
        )
        inscription, jeton = training_services.inscrire(
            tenant=tenant, learner=salarie, course=cours, due_date="2026-12-31"
        )

    reponse = api_client.delete(url(tenant), {"course": cours.slug}, format="json", **staff_headers)

    assert reponse.status_code == status.HTTP_200_OK
    assert reponse.data["kept_enrollments"] is True
    assert not CourseAssignment.all_objects.filter(tenant=tenant, course=cours).exists()
    # L'inscription vit toujours, et le lien du salarié fonctionne encore.
    assert Enrollment.all_objects.filter(id=inscription.id, revoked_at__isnull=True).exists()
    assert training_services.resoudre_session(jeton).id == inscription.id


def test_le_nombre_de_salaries_en_cours_est_annonce(
    api_client, tenant, staff_headers, bibliotheque
):
    """C'est ce chiffre qui fait hésiter avant un retrait."""
    cours = bibliotheque.first()
    api_client.post(url(tenant), {"course": cours.slug}, format="json", **staff_headers)
    with training_services.contexte_du_client(tenant):
        salarie = training_services.creer_apprenant(
            tenant=tenant, full_name="Claude Martin", email="claude@exemple.test"
        )
        training_services.inscrire(
            tenant=tenant, learner=salarie, course=cours, due_date="2026-12-31"
        )

    reponse = api_client.get(url(tenant), **staff_headers)

    ligne = next(c for c in reponse.data["assigned"] if c["slug"] == cours.slug)
    assert ligne["ongoing"] == 1


# --- Cloisonnement ----------------------------------------------------------


def test_proposer_a_un_client_ne_propose_rien_a_un_autre(
    api_client, tenant, tenant_factory, user_factory, staff_headers, bibliotheque
):
    autre = tenant_factory(user_factory(email="voisin@exemple.test"), name="Voisin")
    slug = bibliotheque.first().slug

    api_client.post(url(tenant), {"course": slug}, format="json", **staff_headers)

    assert not CourseAssignment.all_objects.filter(tenant=autre).exists()
    chez_le_voisin = api_client.get(url(autre), **staff_headers)
    assert chez_le_voisin.data["assigned"] == []
    assert slug in [c["slug"] for c in chez_le_voisin.data["available"]]

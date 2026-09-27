"""La commande de préparation d'un espace client.

Ce qui est vérifié ici n'est pas qu'elle « marche » : c'est qu'elle ne fasse
PAS ce qu'elle ne doit pas faire. Elle écrit dans l'espace d'un vrai client, et
les garde-fous comptent plus que le résultat — rejouable sans rien doubler, pas
de compte créé au passage, pas de document rédigé par l'IA déclenché, et une
trace dans le journal d'audit.
"""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.ai_assistant.models import GeneratedDocument
from apps.platform_admin.models import AdminAuditLog
from apps.tenants.models import Membership
from apps.training.models import CourseAssignment, Enrollment, Learner

pytestmark = pytest.mark.django_db


@pytest.fixture
def exploitant(user_factory):
    """Le compte qu'on rattache : il existe déjà, comme en production."""
    return user_factory(email="exploitant@exemple.test", first_name="Alex", last_name="Roy")


@pytest.fixture
def bibliotheque():
    call_command("seed_catalogue_formation", verbosity=0)


def _lancer(client, compte, **extra):
    call_command(
        "preparer_client", "--tenant", client.slug, "--admin", compte.email, verbosity=0, **extra
    )


# --- Les refus --------------------------------------------------------------


def test_refuse_une_entreprise_inconnue(exploitant):
    with pytest.raises(CommandError, match="introuvable"):
        call_command(
            "preparer_client", "--tenant", "nexiste-pas", "--admin", exploitant.email, verbosity=0
        )


def test_ne_cree_jamais_le_compte_administrateur(tenant):
    """Une commande qui créerait le compte sur simple passage d'une adresse
    serait une porte, pas un outil."""
    from apps.accounts.models import User

    with pytest.raises(CommandError, match="Aucun compte"):
        call_command(
            "preparer_client",
            "--tenant",
            tenant.slug,
            "--admin",
            "inconnu@exemple.test",
            verbosity=0,
        )
    assert not User.objects.filter(email="inconnu@exemple.test").exists()


def test_refuse_une_etape_inconnue(tenant, exploitant):
    with pytest.raises(CommandError, match="Étape"):
        _lancer(tenant, exploitant, etapes="acces,exposition")


def test_la_simulation_n_ecrit_rien(tenant, exploitant, bibliotheque):
    _lancer(tenant, exploitant, dry_run=True)

    assert not Membership.all_objects.filter(tenant=tenant, user=exploitant).exists()
    assert not CourseAssignment.all_objects.filter(tenant=tenant).exists()
    assert not GeneratedDocument.all_objects.filter(tenant=tenant).exists()
    assert not AdminAuditLog.objects.filter(action="tenant.prepare").exists()


# --- Les étapes -------------------------------------------------------------


def test_le_compte_devient_administrateur_sans_invitation(tenant, exploitant):
    from apps.accounts.models import AccessInvitation

    _lancer(tenant, exploitant, etapes="acces")

    adhesion = Membership.all_objects.get(tenant=tenant, user=exploitant)
    assert adhesion.role == Membership.Role.ADMIN
    # Aucun lien d'invitation émis : le compte a déjà un mot de passe, et un
    # jeton non utilisé est un secret de plus qui traîne.
    assert not AccessInvitation.objects.filter(user=exploitant).exists()


def test_un_membre_lecteur_est_promu(tenant, exploitant):
    Membership.all_objects.create(tenant=tenant, user=exploitant, role=Membership.Role.READER)

    _lancer(tenant, exploitant, etapes="acces")

    adhesion = Membership.all_objects.get(tenant=tenant, user=exploitant)
    assert adhesion.role == Membership.Role.ADMIN


def test_la_bibliotheque_est_proposee_et_l_administrateur_inscrit(tenant, exploitant, bibliotheque):
    _lancer(tenant, exploitant, etapes="acces,formations")

    attribues = CourseAssignment.all_objects.filter(tenant=tenant).count()
    assert attribues >= 6

    apprenant = Learner.all_objects.get(tenant=tenant, email=exploitant.email)
    # ``user`` renseigné : il suit les cours depuis son espace, sans lien
    # nominatif envoyé par courriel (ADR-039).
    assert apprenant.user_id == exploitant.id
    assert Enrollment.all_objects.filter(tenant=tenant, learner=apprenant).count() == attribues


def test_aucun_apprenant_n_est_invente(tenant, exploitant, bibliotheque):
    _lancer(tenant, exploitant, etapes="acces,formations")

    # Un seul apprenant : celui qu'on a passé en option. Les salariés d'un
    # client réel sont des personnes réelles, pas des données de confort.
    assert Learner.all_objects.filter(tenant=tenant).count() == 1


def test_les_documents_composes_sont_produits_en_brouillon(tenant, exploitant):
    from apps.ai_assistant.documents import registry

    _lancer(tenant, exploitant, etapes="documents")

    produits = set(
        GeneratedDocument.all_objects.filter(tenant=tenant).values_list("type", flat=True)
    )
    composes = {
        spec.type for spec in registry.all_specs() if spec.source == registry.SOURCE_COMPOSED
    }
    assert produits == composes

    statuts = set(
        GeneratedDocument.all_objects.filter(tenant=tenant).values_list("status", flat=True)
    )
    # Valider un document, c'est dire qu'un responsable l'a lu. Personne ne l'a
    # lu : ils restent en brouillon.
    assert GeneratedDocument.Status.VALIDATED not in statuts


def test_aucun_document_redige_par_l_ia_n_est_declenche(tenant, exploitant):
    from apps.ai_assistant.documents import registry
    from apps.ai_assistant.models import AIUsageLog

    _lancer(tenant, exploitant, etapes="documents")

    rediges = {spec.type for spec in registry.all_specs() if spec.source == registry.SOURCE_AI}
    produits = set(
        GeneratedDocument.all_objects.filter(tenant=tenant).values_list("type", flat=True)
    )
    assert not (produits & rediges), "la charte est rédigée par l'IA : coût, quota, et job"
    assert not AIUsageLog.all_objects.filter(tenant=tenant).exists()


def test_rien_n_est_touche_du_cote_exposition(tenant, exploitant, bibliotheque):
    """La consigne d'exploitation : les scans restent déclenchés à la main."""
    from apps.threat_intelligence.models import BreachFinding, BreachScanJob

    _lancer(tenant, exploitant)

    assert not BreachScanJob.all_objects.filter(tenant=tenant).exists()
    assert not BreachFinding.all_objects.filter(tenant=tenant).exists()


# --- Rejouabilité et trace --------------------------------------------------


def test_rejouee_elle_ne_double_rien(tenant, exploitant, bibliotheque):
    _lancer(tenant, exploitant)
    avant = (
        CourseAssignment.all_objects.filter(tenant=tenant).count(),
        Enrollment.all_objects.filter(tenant=tenant).count(),
        Learner.all_objects.filter(tenant=tenant).count(),
        GeneratedDocument.all_objects.filter(tenant=tenant).count(),
    )

    _lancer(tenant, exploitant)

    assert (
        CourseAssignment.all_objects.filter(tenant=tenant).count(),
        Enrollment.all_objects.filter(tenant=tenant).count(),
        Learner.all_objects.filter(tenant=tenant).count(),
        GeneratedDocument.all_objects.filter(tenant=tenant).count(),
    ) == avant


def test_l_action_laisse_une_trace_dans_le_journal_d_audit(tenant, exploitant):
    _lancer(tenant, exploitant, etapes="acces")

    trace = AdminAuditLog.objects.get(action="tenant.prepare")
    assert trace.tenant_id == tenant.id
    assert trace.actor_id == exploitant.id
    assert "acces" in trace.detail


def test_le_cloisonnement_tient(tenant, tenant_factory, user_factory, exploitant, bibliotheque):
    """Préparer un client n'ouvre rien chez un autre."""
    autre = tenant_factory(user_factory(email="autre-proprietaire@exemple.test"), name="Autre")

    _lancer(tenant, exploitant)

    assert not CourseAssignment.all_objects.filter(tenant=autre).exists()
    assert not Learner.all_objects.filter(tenant=autre).exists()
    assert not GeneratedDocument.all_objects.filter(tenant=autre).exists()
    assert not Membership.all_objects.filter(tenant=autre, user=exploitant).exists()

"""L'API du studio : qui peut écrire quoi.

Trois refus sont vérifiés ici, et ils ne se confondent pas :

- **403** : ce compte n'a pas le rôle (un contributeur n'écrit pas de cours) ;
- **402** : le rôle est bon, c'est l'offre qui ne comprend pas le studio ;
- **404** : le cours existe, mais pas pour vous — on ne confirme jamais
  l'existence du cours d'un autre client.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.billing import features
from apps.billing.models import Subscription
from apps.tenants.models import Membership
from apps.training import studio

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "Str0ng!Passw0rd123"
ECRAN = [{"type": "paragraphe", "texte": "Un contenu."}]


def _auth(api_client, user, tenant=None):
    reponse = api_client.post(
        reverse("token-obtain-pair"),
        {"email": user.email, "password": MOT_DE_PASSE},
        format="json",
    )
    entetes = {"HTTP_AUTHORIZATION": f"Bearer {reponse.data['access']}"}
    if tenant is not None:
        entetes["HTTP_X_TENANT_ID"] = str(tenant.id)
    return entetes


def _accorder(tenant, cles):
    abonnement = Subscription.objects.get(tenant=tenant)
    abonnement.override_features = list(cles)
    abonnement.save(update_fields=["override_features"])


@pytest.fixture(autouse=True)
def _studio_inclus(tenant):
    _accorder(tenant, [features.TRAINING, features.TRAINING_STUDIO])


@pytest.fixture
def exploitant(user_factory):
    return user_factory(email="exploitant@example.com", is_staff=True)


class TestDroits:
    def test_un_contributeur_ne_peut_pas_ecrire_de_cours(self, api_client, tenant, user_factory):
        contributeur = user_factory(email="contrib@example.com")
        Membership.all_objects.create(
            tenant=tenant, user=contributeur, role=Membership.Role.CONTRIBUTOR
        )
        entetes = _auth(api_client, contributeur, tenant)

        reponse = api_client.post(
            reverse("formation-studio-cours"), {"title": "Le mien"}, format="json", **entetes
        )

        assert reponse.status_code == status.HTTP_403_FORBIDDEN

    def test_hors_offre_l_ecriture_est_refusee_en_402_et_non_en_403(
        self, api_client, tenant, tenant_owner
    ):
        _accorder(tenant, [features.TRAINING])
        entetes = _auth(api_client, tenant_owner, tenant)

        reponse = api_client.post(
            reverse("formation-studio-cours"), {"title": "Le mien"}, format="json", **entetes
        )

        # 403 dirait « vous n'avez pas le droit », ce qui est faux : le client
        # a parfaitement le droit de demander, c'est son offre qui ne comprend
        # pas le studio. Le 402 nomme l'offre à prendre.
        assert reponse.status_code == status.HTTP_402_PAYMENT_REQUIRED

    def test_hors_offre_la_lecture_de_la_bibliotheque_reste_servie(
        self, api_client, tenant, tenant_owner
    ):
        _accorder(tenant, [features.TRAINING])
        entetes = _auth(api_client, tenant_owner, tenant)

        reponse = api_client.get(reverse("formation-studio-cours"), **entetes)

        assert reponse.status_code == status.HTTP_200_OK

    def test_un_anonyme_n_atteint_pas_le_studio(self, api_client):
        assert (
            api_client.get(reverse("formation-studio-cours")).status_code
            == status.HTTP_401_UNAUTHORIZED
        )


class TestEtancheite:
    @pytest.fixture
    def cours_d_un_autre(self, user_factory, tenant_factory):
        proprietaire = user_factory(email="ailleurs@example.com")
        autre = tenant_factory(proprietaire, name="Autre Entreprise")
        _accorder(autre, [features.TRAINING, features.TRAINING_STUDIO])
        return studio.creer_cours(title="Secret maison", owner_tenant=autre, actor=proprietaire)

    def test_le_cours_d_un_autre_client_n_existe_pas_pour_moi(
        self, api_client, tenant, tenant_owner, cours_d_un_autre
    ):
        entetes = _auth(api_client, tenant_owner, tenant)

        reponse = api_client.get(
            reverse("formation-studio-cours-detail", args=[cours_d_un_autre.id]), **entetes
        )

        # 404 et non 403 : un 403 confirmerait que ce cours existe.
        assert reponse.status_code == status.HTTP_404_NOT_FOUND

    def test_ma_liste_ne_montre_que_mes_cours_et_la_bibliotheque(
        self, api_client, tenant, tenant_owner, cours_d_un_autre
    ):
        studio.creer_cours(title="Le mien", owner_tenant=tenant, actor=tenant_owner)
        studio.creer_cours(title="De la bibliothèque")
        entetes = _auth(api_client, tenant_owner, tenant)

        reponse = api_client.get(reverse("formation-studio-cours"), **entetes)

        assert [c["title"] for c in reponse.data["mine"]] == ["Le mien"]
        assert [c["title"] for c in reponse.data["library"]] == ["De la bibliothèque"]

    def test_l_exploitant_n_entre_pas_dans_le_cours_d_un_client(
        self, api_client, exploitant, cours_d_un_autre
    ):
        """ADR-014 : un administrateur plateforme n'entre pas dans un espace
        client. La copie qu'un client a dérivée lui appartient, ses phrases
        comprises."""
        entetes = _auth(api_client, exploitant)

        reponse = api_client.get(
            reverse("formation-studio-cours-detail", args=[cours_d_un_autre.id]), **entetes
        )

        assert reponse.status_code == status.HTTP_403_FORBIDDEN

    def test_l_exploitant_ecrit_dans_la_bibliotheque(self, api_client, exploitant):
        entetes = _auth(api_client, exploitant)

        reponse = api_client.post(
            reverse("formation-studio-cours"),
            {"title": "Cours de la maison"},
            format="json",
            **entetes,
        )

        assert reponse.status_code == status.HTTP_201_CREATED
        assert reponse.data["is_library"] is True


class TestParcoursDeRedaction:
    @pytest.fixture
    def entetes(self, api_client, tenant, tenant_owner):
        return _auth(api_client, tenant_owner, tenant)

    def test_ecrire_publier_puis_reouvrir_une_version(self, api_client, entetes):
        creation = api_client.post(
            reverse("formation-studio-cours"), {"title": "Mon cours"}, format="json", **entetes
        )
        version_id = creation.data["draft_version_id"]

        ecran = api_client.post(
            reverse("formation-studio-ecrans", args=[version_id]),
            {"title": "Premier écran", "content": ECRAN},
            format="json",
            **entetes,
        )
        assert ecran.status_code == status.HTTP_200_OK

        question = api_client.post(
            reverse("formation-studio-questions", args=[version_id]),
            {
                "text": "Une question ?",
                "kind": "single",
                "explanation": "Parce que.",
                "screen_id": ecran.data["id"],
                "choices": [
                    {"text": "Bonne", "is_correct": True},
                    {"text": "Mauvaise", "is_correct": False},
                ],
            },
            format="json",
            **entetes,
        )
        assert question.status_code == status.HTTP_200_OK

        apercu = api_client.get(reverse("formation-studio-version", args=[version_id]), **entetes)
        assert apercu.data["blocking"] == []
        assert apercu.data["warnings"]  # un quiz d'une question est bancal

        publication = api_client.post(
            reverse("formation-studio-publier", args=[version_id]), **entetes
        )
        assert publication.status_code == status.HTTP_200_OK
        assert publication.data["published_version"] == 1

        # Version publiée : l'écriture est fermée.
        refus = api_client.post(
            reverse("formation-studio-ecrans", args=[version_id]),
            {"title": "Ajout tardif", "content": ECRAN},
            format="json",
            **entetes,
        )
        assert refus.status_code == status.HTTP_409_CONFLICT

    def test_un_contenu_invalide_rend_tous_les_problemes_d_un_coup(self, api_client, entetes):
        creation = api_client.post(
            reverse("formation-studio-cours"), {"title": "Mon cours"}, format="json", **entetes
        )

        reponse = api_client.post(
            reverse("formation-studio-ecrans", args=[creation.data["draft_version_id"]]),
            {
                "title": "Écran",
                "content": [
                    {"type": "image", "source": "https://ailleurs.test/x.png"},
                    {"type": "paragraphe", "texte": "Un **gras oublié"},
                ],
            },
            format="json",
            **entetes,
        )

        assert reponse.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        # Corriger huit blocs en découvrant les erreurs une par une est une
        # perte de temps : on les rend toutes.
        assert len(reponse.data["problemes"]) >= 3

    def test_dupliquer_un_cours_de_la_bibliotheque(self, api_client, entetes, tenant):
        bibliotheque = studio.creer_cours(title="Cours de la maison")
        ecran = studio.ecrire_ecran(
            version=bibliotheque.draft_version, title="Écran", content=ECRAN
        )
        studio.ecrire_question(
            version=bibliotheque.draft_version,
            text="Q ?",
            kind="single",
            explanation="Parce que.",
            screen_id=ecran.id,
            choix=[{"text": "A", "is_correct": True}, {"text": "B", "is_correct": False}],
        )
        studio.publier(bibliotheque.draft_version)

        reponse = api_client.post(
            reverse("formation-studio-dupliquer", args=[bibliotheque.id]),
            {"title": "Notre version"},
            format="json",
            **entetes,
        )

        assert reponse.status_code == status.HTTP_201_CREATED
        assert reponse.data["is_library"] is False
        assert reponse.data["title"] == "Notre version"

    def test_le_studio_propose_les_variables_disponibles(self, api_client, entetes):
        reponse = api_client.get(reverse("formation-studio-cours"), **entetes)

        # On n'écrit pas une variable qui n'existe pas : la liste vient du
        # serveur, jamais de la mémoire de l'auteur.
        cles = {v["cle"] for v in reponse.data["variables"]}
        assert "score_maturite" in cles

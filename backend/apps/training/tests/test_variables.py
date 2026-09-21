"""Les variables contextuelles : ce qu'elles disent, et surtout ce qu'elles
ne peuvent pas dire.

Les trois tests qui comptent vraiment sont ceux du bas : une variable ne rend
jamais du texte, un petit décompte ne s'affiche pas, et une donnée absente
bascule le bloc entier sur sa formulation de repli.
"""

import pytest

from apps.training import blocks, services, variables
from apps.training.variables import SEUIL_DISCRETION, Variable

pytestmark = pytest.mark.django_db


def _variable(monkeypatch, cle, valeur, *, est_un_decompte=True, feature=""):
    monkeypatch.setitem(
        variables.REGISTRE,
        cle,
        Variable(
            cle,
            "Témoin",
            "Variable de test.",
            lambda _tenant: valeur,
            est_un_decompte=est_un_decompte,
            feature=feature,
        ),
    )


BLOC = {
    "type": "paragraphe",
    "texte": "Votre entreprise a {fuites_ouvertes} comptes compromis.",
    "repli": "Des comptes de votre entreprise pourraient déjà circuler dans des fuites.",
}


class TestSubstitution:
    def test_remplace_la_variable_par_le_chiffre_reel(self, tenant, monkeypatch):
        _variable(monkeypatch, "fuites_ouvertes", 7)

        rendu = services.contextualiser([BLOC], tenant)

        assert rendu[0]["texte"] == "Votre entreprise a 7 comptes compromis."

    def test_laisse_intact_un_bloc_sans_variable(self, tenant):
        bloc = {"type": "paragraphe", "texte": "Un texte ordinaire."}
        assert services.contextualiser([bloc], tenant) == [bloc]

    def test_substitue_aussi_dans_les_entrees_d_une_liste(self, tenant, monkeypatch):
        _variable(monkeypatch, "fuites_ouvertes", 4)
        bloc = {
            "type": "liste",
            "items": ["Premier", "Vous avez {fuites_ouvertes} comptes touchés"],
            "repli": "Certains de vos comptes sont peut-être touchés.",
        }

        rendu = services.contextualiser([bloc], tenant)

        assert rendu[0]["items"] == ["Premier", "Vous avez 4 comptes touchés"]


class TestRepli:
    def test_une_donnee_absente_fait_basculer_le_bloc_entier(self, tenant, monkeypatch):
        _variable(monkeypatch, "fuites_ouvertes", None)

        rendu = services.contextualiser([BLOC], tenant)

        # Le bloc entier, et non la seule variable : sinon on produirait
        # « Votre entreprise a — comptes compromis. »
        assert rendu[0]["texte"] == BLOC["repli"]

    def test_zero_n_est_jamais_affiche(self, tenant, monkeypatch):
        _variable(monkeypatch, "fuites_ouvertes", 0)

        rendu = services.contextualiser([BLOC], tenant)

        # « Vous avez eu 0 incident » sur le ton de l'alerte est au mieux
        # ridicule. L'absence de problème se dit avec des mots.
        assert rendu[0]["texte"] == BLOC["repli"]
        assert "0" not in rendu[0]["texte"]

    def test_un_decompte_trop_petit_ne_designe_personne(self, tenant, monkeypatch):
        # Dans une entreprise de six salariés, « 1 compte compromis » dit à
        # tout le monde de qui il s'agit.
        _variable(monkeypatch, "fuites_ouvertes", SEUIL_DISCRETION - 1)

        rendu = services.contextualiser([BLOC], tenant)

        assert rendu[0]["texte"] == BLOC["repli"]

    def test_le_seuil_ne_s_applique_pas_a_un_score(self, tenant, monkeypatch):
        # Un score sur 100 ne désigne personne : 2 sur 100 s'affiche.
        _variable(monkeypatch, "score_maturite", 2, est_un_decompte=False)
        bloc = {
            "type": "paragraphe",
            "texte": "Votre score de maturité est de {score_maturite} sur 100.",
            "repli": "Votre maturité n'a pas encore été évaluée.",
        }

        assert "2 sur 100" in services.contextualiser([bloc], tenant)[0]["texte"]

    def test_hors_offre_le_client_recoit_le_repli_et_non_une_erreur(self, tenant, monkeypatch):
        from apps.billing import features

        _variable(monkeypatch, "fuites_ouvertes", 12, feature=features.SECRET_REVEAL)

        rendu = services.contextualiser([BLOC], tenant)

        assert rendu[0]["texte"] == BLOC["repli"]

    def test_une_panne_de_calcul_ne_casse_pas_le_cours(self, tenant, monkeypatch):
        def tombe(_tenant):
            raise RuntimeError("base indisponible")

        monkeypatch.setitem(
            variables.REGISTRE,
            "fuites_ouvertes",
            Variable("fuites_ouvertes", "Témoin", "", tombe),
        )

        # Un salarié dans le train ne doit pas voir une page d'erreur parce
        # qu'un calcul d'indicateur a échoué.
        assert services.contextualiser([BLOC], tenant)[0]["texte"] == BLOC["repli"]


class TestGardesDeFond:
    def test_aucune_variable_ne_rend_du_texte(self, tenant):
        """LE test du lot.

        Tant que toute variable rend un entier, aucun nom, aucune adresse et
        aucun mot de passe ne peut se retrouver dans un cours — pas même par
        l'erreur d'un auteur. Ajouter une variable de texte ferait rougir ce
        test, et c'est exactement ce qu'on veut.
        """
        for cle in variables.cles_connues():
            try:
                valeur = variables.valeur(cle, tenant)
            except variables.ValeurIndisponible:
                continue
            assert isinstance(valeur, int), f"{cle} rend autre chose qu'un entier"

    def test_le_catalogue_du_studio_ne_propose_que_des_cles_connues(self):
        propose = {entree["cle"] for entree in variables.catalogue()}
        assert propose == set(variables.cles_connues())

    def test_une_variable_inconnue_est_refusee_a_l_ecriture(self):
        with pytest.raises(blocks.BlocInvalide) as refus:
            blocks.valider([{"type": "paragraphe", "texte": "Bonjour {inventee}.", "repli": "x"}])

        assert "n'existe pas" in " ".join(refus.value.problemes)

    def test_un_bloc_a_variable_exige_sa_formulation_de_repli(self):
        with pytest.raises(blocks.BlocInvalide) as refus:
            blocks.valider([{"type": "paragraphe", "texte": "Vous avez {fuites_ouvertes}."}])

        assert "repli" in " ".join(refus.value.problemes)

    def test_le_repli_ne_peut_pas_lui_meme_contenir_une_variable(self):
        with pytest.raises(blocks.BlocInvalide) as refus:
            blocks.valider(
                [
                    {
                        "type": "paragraphe",
                        "texte": "Vous avez {fuites_ouvertes} comptes.",
                        "repli": "Vous avez {fuites_ouvertes} comptes.",
                    }
                ]
            )

        assert "repli" in " ".join(refus.value.problemes)


class TestGras:
    def test_decoupe_le_texte_en_segments(self):
        assert blocks.segments("Un **mot** important") == [
            {"texte": "Un ", "gras": False},
            {"texte": "mot", "gras": True},
            {"texte": " important", "gras": False},
        ]

    def test_refuse_une_marque_non_fermee(self):
        with pytest.raises(blocks.BlocInvalide) as refus:
            blocks.valider([{"type": "paragraphe", "texte": "Un **mot oublié"}])

        assert "non fermée" in " ".join(refus.value.problemes)

    def test_le_texte_lu_a_voix_haute_est_debarrasse_des_marques(self):
        assert blocks.texte_sans_marques("Un **mot** important") == "Un mot important"

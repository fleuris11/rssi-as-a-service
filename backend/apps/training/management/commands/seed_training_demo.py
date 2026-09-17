"""Le cours de démonstration de F1 : reconnaître un courriel d'hameçonnage.

Écrit en dur, et c'est le choix du lot : le studio arrive en F2, et un cours
figé suffit à valider le parcours — invitation, écrans, reprise, quiz,
attestation. Le sujet n'est pas indifférent : l'hameçonnage est le seul dont
le contenu soit incontestable, court, et illustrable sans produire de schéma.

Aucune image : les blocs ``image`` existent et sont validés, mais les livrer
ici supposerait d'ajouter des fichiers au dépôt pour un cours de
démonstration. Le format les accepte, le cours de F1 s'en passe.

Rejouable : ``--reset`` reprend le contenu à zéro sans toucher aux
inscriptions des salariés, qui pointent vers une version et non vers un cours.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.tenants.models import Tenant
from apps.training import services
from apps.training.models import Choice, Course, CourseVersion, Question, Screen

SLUG = "hameconnage"

ECRANS = [
    {
        "title": "Pourquoi ce cours",
        "seconds": 60,
        "content": [
            {
                "type": "paragraphe",
                "texte": "La très grande majorité des attaques contre une entreprise commence "
                "par un courriel. Pas par une prouesse technique : par un message qui "
                "ressemble à un message ordinaire, et auquel quelqu'un répond.",
            },
            {
                "type": "paragraphe",
                "texte": "Ce cours dure une dizaine de minutes. À la fin, vous saurez "
                "reconnaître les trois signes qui doivent vous arrêter, et ce qu'il faut "
                "faire si vous avez déjà cliqué.",
            },
            {
                "type": "encadre",
                "ton": "info",
                "texte": "Il n'y a pas de piège dans ce cours : on ne vous reprochera jamais "
                "d'avoir signalé un message qui se révélait légitime.",
            },
        ],
    },
    {
        "title": "Ce qu'est l'hameçonnage",
        "seconds": 90,
        "content": [
            {
                "type": "paragraphe",
                "texte": "L'hameçonnage est un message qui se fait passer pour quelqu'un que "
                "vous connaissez — votre banque, un fournisseur, votre direction — pour vous "
                "faire donner quelque chose : un mot de passe, un virement, ou simplement un "
                "clic.",
            },
            {
                "type": "titre",
                "niveau": 3,
                "texte": "Ce qu'il cherche à obtenir",
            },
            {
                "type": "liste",
                "items": [
                    "vos identifiants, saisis sur une page qui imite celle que vous connaissez",
                    "un paiement, présenté comme urgent et confidentiel",
                    "l'ouverture d'une pièce jointe qui installe un programme",
                ],
            },
            {
                "type": "encadre",
                "ton": "attention",
                "texte": "Un message d'hameçonnage bien fait ne comporte aucune faute "
                "d'orthographe. Se fier aux fautes ne protège plus de rien.",
            },
        ],
    },
    {
        "title": "Signe n° 1 — l'urgence",
        "seconds": 90,
        "content": [
            {
                "type": "paragraphe",
                "texte": "C'est le signe le plus constant. Le message vous presse : il faut "
                "répondre aujourd'hui, avant ce soir, avant la fermeture du compte.",
            },
            {
                "type": "paragraphe",
                "texte": "L'urgence n'est pas là par hasard. Elle sert à vous empêcher de "
                "faire ce qui suffirait à déjouer l'attaque : prendre trente secondes, et "
                "vérifier.",
            },
            {
                "type": "citation",
                "texte": "Votre compte sera suspendu sous 24 heures si vous ne confirmez pas "
                "vos informations.",
                "source": "Formulation type d'un courriel d'hameçonnage",
            },
            {
                "type": "encadre",
                "ton": "exemple",
                "texte": "Une organisation légitime qui doit vraiment vous joindre en urgence "
                "vous appellera. Elle ne vous demandera pas votre mot de passe par écrit.",
            },
        ],
    },
    {
        "title": "Signe n° 2 — l'adresse d'expéditeur",
        "seconds": 90,
        "content": [
            {
                "type": "paragraphe",
                "texte": "Le nom affiché par votre logiciel de messagerie est choisi par "
                "l'expéditeur. N'importe qui peut s'appeler « Service comptabilité ». Ce qui "
                "compte est l'adresse complète, qu'il faut afficher en entier.",
            },
            {
                "type": "titre",
                "niveau": 3,
                "texte": "Ce qu'on cherche dans une adresse",
            },
            {
                "type": "liste",
                "ordonnee": True,
                "items": [
                    "le nom de domaine, c'est-à-dire ce qui suit l'arobase",
                    "une lettre remplacée ou ajoutée, qui imite un domaine connu",
                    "un domaine public là où vous attendez celui d'une entreprise",
                ],
            },
            {
                "type": "encadre",
                "ton": "attention",
                "texte": "Répondre à un message suspect envoie votre réponse à l'attaquant. "
                "Pour vérifier, écrivez un NOUVEAU message à l'adresse que vous connaissez "
                "déjà.",
            },
        ],
    },
    {
        "title": "Signe n° 3 — le lien qui ne mène pas où il dit",
        "seconds": 90,
        "content": [
            {
                "type": "paragraphe",
                "texte": "Le texte d'un lien et sa destination sont deux choses différentes. "
                "Un lien peut afficher l'adresse de votre banque et conduire ailleurs.",
            },
            {
                "type": "paragraphe",
                "texte": "Sur un ordinateur, survolez le lien sans cliquer : la vraie adresse "
                "apparaît en bas de la fenêtre. Sur un téléphone, appuyez longuement — elle "
                "s'affiche sans ouvrir la page.",
            },
            {
                "type": "encadre",
                "ton": "info",
                "texte": "Le plus sûr reste de ne pas utiliser le lien du tout : ouvrez "
                "vous-même le site par vos favoris ou en tapant l'adresse.",
            },
        ],
    },
    {
        "title": "Les pièces jointes",
        "seconds": 60,
        "content": [
            {
                "type": "paragraphe",
                "texte": "Une pièce jointe inattendue est un risque, même venant d'une adresse "
                "connue : la boîte de votre correspondant a pu être compromise avant la vôtre.",
            },
            {
                "type": "liste",
                "items": [
                    "une facture que vous n'attendiez pas",
                    "un document qui demande d'« activer les macros » pour s'afficher",
                    "une archive compressée contenant un seul fichier exécutable",
                ],
            },
        ],
    },
    {
        "title": "Si vous avez cliqué",
        "seconds": 90,
        "content": [
            {
                "type": "paragraphe",
                "texte": "Cela arrive, y compris à des personnes très attentives. Ce qui "
                "détermine les conséquences, ce n'est pas le clic : c'est le temps qu'on met "
                "à le dire.",
            },
            {
                "type": "titre",
                "niveau": 3,
                "texte": "Dans l'ordre",
            },
            {
                "type": "liste",
                "ordonnee": True,
                "items": [
                    "signalez-le immédiatement à votre responsable informatique",
                    "si vous avez saisi un mot de passe, changez-le partout où il servait",
                    "ne supprimez pas le message : il sert à comprendre l'attaque",
                ],
            },
            {
                "type": "encadre",
                "ton": "attention",
                "texte": "Signaler tôt, c'est ce qui transforme un incident majeur en "
                "incident mineur. Personne n'est sanctionné pour avoir signalé.",
            },
        ],
    },
]

# (rang, écran visé, énoncé, type, explication, [(texte, correct), ...])
QUESTIONS = [
    (
        1,
        2,
        "Un courriel vous presse de répondre avant ce soir, sans quoi votre compte sera "
        "suspendu. Que fait ce sentiment d'urgence ?",
        "single",
        "L'urgence est le ressort principal de l'hameçonnage : elle sert à vous empêcher de "
        "prendre les trente secondes de vérification qui suffiraient à déjouer l'attaque. "
        "Une organisation légitime qui doit vraiment vous joindre en urgence vous appelle.",
        [
            ("Elle indique que le message est prioritaire et doit être traité en premier", False),
            ("Elle cherche à vous empêcher de prendre le temps de vérifier", True),
            ("Elle prouve que l'expéditeur est bien votre banque", False),
        ],
    ),
    (
        2,
        3,
        "Le nom affiché de l'expéditeur est « Service comptabilité ». Que pouvez-vous en "
        "conclure ?",
        "single",
        "Rien : le nom affiché est choisi librement par l'expéditeur. Seule l'adresse "
        "complète — et surtout le nom de domaine qui suit l'arobase — porte une information.",
        [
            ("Que le message vient du service comptabilité", False),
            ("Rien : ce nom est choisi par l'expéditeur, il faut regarder l'adresse", True),
            ("Que le message a été vérifié par la messagerie", False),
        ],
    ),
    (
        3,
        4,
        "Vous voulez savoir où mène vraiment un lien. Que faites-vous ?",
        "multiple",
        "Survoler sur ordinateur, appuyer longuement sur téléphone : les deux affichent la "
        "destination réelle sans l'ouvrir. Cliquer « pour voir » est précisément ce que le "
        "message cherche à obtenir.",
        [
            ("Je survole le lien sans cliquer, sur ordinateur", True),
            ("J'appuie longuement dessus, sur téléphone", True),
            ("Je clique pour voir où cela mène, puis je ferme la page", False),
        ],
    ),
    (
        4,
        3,
        "Un message vous semble suspect. Comment vérifiez-vous auprès de l'expéditeur ?",
        "single",
        "Répondre envoie votre message à l'attaquant, qui vous confirmera bien volontiers "
        "que le message est authentique. La vérification n'a de valeur que si elle emprunte "
        "un chemin que l'attaquant ne contrôle pas.",
        [
            ("Je réponds au message pour demander confirmation", False),
            ("J'écris un nouveau message à l'adresse que je connais déjà", True),
            ("Je transfère le message à toute mon équipe pour avoir leur avis", False),
        ],
    ),
    (
        5,
        5,
        "Vous recevez une facture en pièce jointe, d'une adresse que vous connaissez, mais "
        "vous n'attendiez rien. Que faut-il en penser ?",
        "single",
        "Une adresse connue ne garantit rien : la boîte de votre correspondant a pu être "
        "compromise avant la vôtre. C'est le caractère inattendu de la pièce jointe qui "
        "compte, pas l'identité affichée.",
        [
            ("C'est sans risque, puisque je connais l'expéditeur", False),
            ("C'est à traiter avec prudence : sa boîte a pu être compromise", True),
            ("C'est forcément une attaque, il faut supprimer le message", False),
        ],
    ),
    (
        6,
        6,
        "Vous vous apercevez que vous avez cliqué et saisi votre mot de passe. Que faites-vous "
        "en premier ?",
        "single",
        "Signaler immédiatement est ce qui transforme un incident majeur en incident mineur : "
        "c'est le délai, et non le clic, qui détermine les conséquences. Supprimer le message "
        "priverait au contraire de ce qui sert à comprendre l'attaque.",
        [
            ("Je supprime le message pour effacer toute trace", False),
            ("J'attends de voir si quelque chose d'anormal se produit", False),
            ("Je le signale immédiatement à mon responsable informatique", True),
        ],
    ),
]


class Command(BaseCommand):
    help = "Charge le cours de démonstration « hameçonnage » (F1)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Reprend le contenu à zéro. Les inscriptions existantes ne sont pas "
            "touchées : elles pointent vers une version, qui est conservée.",
        )
        parser.add_argument(
            "--tenant",
            default="",
            help="Attribue le cours à ce client (slug). Sans cela, le cours est chargé "
            "au catalogue sans être proposé à personne.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        cours, cree = Course.objects.get_or_create(
            slug=SLUG,
            defaults={
                "title": "Reconnaître un courriel d'hameçonnage",
                "summary": "Les trois signes qui doivent vous arrêter, et ce qu'il faut faire "
                "si vous avez déjà cliqué. Dix minutes.",
            },
        )

        version = cours.versions.order_by("-number").first()
        if version is None:
            version = CourseVersion.objects.create(
                course=cours, number=1, change_note="Version initiale (F1)."
            )
        elif options["reset"]:
            # On vide le CONTENU de la version, pas la version : une
            # inscription pointe dessus, et la supprimer casserait le parcours
            # d'un salarié en cours de route.
            version.screens.all().delete()
            version.questions.all().delete()

        if version.screens.exists():
            self.stdout.write("Le cours est déjà chargé. Utilisez --reset pour le reprendre.")
        else:
            self._charger(version)

        version.published_at = version.published_at or timezone.now()
        version.save(update_fields=["published_at"])

        for avertissement in services.avertissements_de_quiz(version):
            self.stdout.write(self.style.WARNING(f"Attention : {avertissement}"))

        if options["tenant"]:
            client = Tenant.objects.filter(slug=options["tenant"]).first()
            if client is None:
                self.stderr.write(f"Client « {options['tenant']} » introuvable.")
            else:
                services.attribuer_cours(tenant=client, course=cours)
                self.stdout.write(f"Cours proposé à {client.name}.")

        etat = "créé" if cree else "mis à jour"
        self.stdout.write(
            self.style.SUCCESS(
                f"Cours « {cours.title} » {etat} — version {version.number}, "
                f"{version.screens.count()} écrans, {version.questions.count()} questions, "
                f"{version.estimated_minutes} minutes annoncées."
            )
        )

    def _charger(self, version):
        ecrans = []
        for rang, donnees in enumerate(ECRANS, start=1):
            ecrans.append(
                Screen.objects.create(
                    version=version,
                    order=rang,
                    title=donnees["title"],
                    content=donnees["content"],
                    estimated_seconds=donnees["seconds"],
                )
            )

        for rang, ecran_vise, enonce, genre, explication, choix in QUESTIONS:
            question = Question.objects.create(
                version=version,
                order=rang,
                text=enonce,
                kind=genre,
                explanation=explication,
                screen=ecrans[ecran_vise - 1],
            )
            for position, (texte, correct) in enumerate(choix, start=1):
                Choice.objects.create(
                    question=question, order=position, text=texte, is_correct=correct
                )

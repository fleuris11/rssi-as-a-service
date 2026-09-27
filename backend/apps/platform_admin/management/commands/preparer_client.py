"""Prépare l'espace d'un client réel : accès, formations, documents.

Pourquoi une commande et non des ordres tapés en production : ce qu'elle fait
touche les données d'un vrai client. Une commande versionnée se relit avant
d'être lancée, se teste, laisse une trace dans le journal d'audit de la
plateforme, et se rejoue sans rien doubler. Un script tapé dans un conteneur ne
fait aucune de ces quatre choses.

Elle est **générique**. Aucun nom de client, aucune adresse, aucun identifiant
n'est écrit ici : tout arrive par les options. Un fichier de seed qui nommerait
un client réel finirait par le nommer dans le dépôt, puis dans les captures.

**Ce qu'elle ne fait jamais**, et c'est délibéré :

- aucune analyse d'exposition, aucun scan, aucune recherche de compromission.
  Ces gestes ont un coût, engagent une licence et désignent des personnes : ils
  restent déclenchés à la main par l'exploitant ;
- aucun envoi de courriel. Les inscriptions créées ici n'émettent pas de lien
  nominatif : l'exploitant les enverra depuis l'interface quand il le décidera ;
- aucun diagnostic répondu à la place du client. Les réponses au référentiel
  sont un engagement de l'entreprise, pas une donnée de confort — les inventer
  produirait un score faux et un plan d'action faux ;
- aucun apprenant inventé. Les salariés d'un vrai client sont des personnes
  réelles ; seul le compte passé en ``--admin`` est inscrit, pour qu'il puisse
  parcourir les cours depuis son propre espace.

Étapes, toutes idempotentes et sélectionnables par ``--etapes`` :

``acces``      le compte devient membre administrateur de l'entreprise ;
``formations`` la bibliothèque est proposée au client, et l'administrateur y est
               inscrit ;
``documents``  les documents COMPOSÉS manquants sont produits.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

ETAPES = ("acces", "formations", "documents")

#: Le délai laissé aux inscriptions créées ici. Un mois : assez pour ne pas
#: afficher une échéance dépassée le jour de la livraison, assez court pour que
#: la date ait un sens.
ECHEANCE_JOURS = 30


class Command(BaseCommand):
    help = "Prépare l'espace d'un client : accès administrateur, formations, documents."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="Slug de l'entreprise.")
        parser.add_argument(
            "--admin",
            required=True,
            help="Adresse du compte à rendre membre administrateur. Le compte doit exister.",
        )
        parser.add_argument(
            "--etapes",
            default=",".join(ETAPES),
            help=f"Étapes à exécuter, séparées par des virgules. Connues : {', '.join(ETAPES)}.",
        )
        parser.add_argument(
            "--echeance-jours",
            type=int,
            default=ECHEANCE_JOURS,
            help="Échéance des inscriptions créées, en jours.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Annonce ce qui serait fait, sans rien écrire.",
        )

    def handle(self, *args, **options):
        from apps.tenants.models import Tenant

        self.simulation = options["dry_run"]

        etapes = [e.strip() for e in options["etapes"].split(",") if e.strip()]
        inconnues = [e for e in etapes if e not in ETAPES]
        if inconnues:
            raise CommandError(f"Étape(s) inconnue(s) : {', '.join(inconnues)}.")

        client = Tenant.objects.filter(slug=options["tenant"]).first()
        if client is None:
            raise CommandError(f"Entreprise « {options['tenant']} » introuvable.")

        User = get_user_model()
        compte = User.objects.filter(email__iexact=options["admin"].strip()).first()
        if compte is None:
            # On ne crée PAS le compte : une commande qui crée un compte
            # administrateur sur simple passage d'une adresse en ligne de
            # commande est une porte, pas un outil.
            raise CommandError(
                f"Aucun compte « {options['admin']} ». Créez-le d'abord, puis relancez."
            )

        self.stdout.write(f"Entreprise : {client.name} ({client.slug})")
        self.stdout.write(f"Compte     : {compte.email}")
        if self.simulation:
            self.stdout.write(self.style.WARNING("Simulation : aucune écriture."))

        if "acces" in etapes:
            self._acces(client, compte)
        if "formations" in etapes:
            self._formations(client, compte, options["echeance_jours"])
        if "documents" in etapes:
            self._documents(client, compte)

        self._tracer(client, compte, etapes)

    # --- Journalisation -----------------------------------------------------

    def _fait(self, message):
        self.stdout.write(self.style.SUCCESS(f"  + {message}"))

    def _deja(self, message):
        self.stdout.write(f"  = {message}")

    def _tracer(self, client, compte, etapes):
        """Une trace dans le journal d'audit de la plateforme.

        Sans elle, l'apparition de données dans l'espace d'un client serait
        inexplicable six mois plus tard — y compris pour celui qui a lancé la
        commande.
        """
        if self.simulation:
            return
        from apps.platform_admin import services as admin_services

        admin_services.record_admin_action(
            actor=compte,
            action="tenant.prepare",
            tenant=client,
            target=client.slug,
            detail=f"Préparation de l'espace client — étapes : {', '.join(etapes)}.",
        )

    # --- Étape « acces » ----------------------------------------------------

    def _acces(self, client, compte):
        self.stdout.write("Accès")
        from apps.tenants.models import Membership

        existant = Membership.all_objects.filter(tenant=client, user=compte).first()
        if existant is not None:
            if existant.role != Membership.Role.ADMIN and not self.simulation:
                from apps.tenants import services as tenants_services

                tenants_services.change_member_role(membership=existant, role=Membership.Role.ADMIN)
                self._fait(f"rôle porté à administrateur (était {existant.role}).")
            else:
                self._deja(f"déjà membre ({existant.role}).")
            return

        if self.simulation:
            self._fait("serait ajouté comme administrateur.")
            return

        # Le quota d'utilisateurs de l'offre est vérifié comme pour n'importe
        # quelle invitation : une commande d'exploitation n'a pas le droit de
        # passer devant une garde d'offre.
        from apps.billing import entitlements

        entitlements.ensure_user_quota(client, additional=1)
        Membership.all_objects.create(tenant=client, user=compte, role=Membership.Role.ADMIN)
        # Aucune invitation n'est émise : le compte a déjà un mot de passe. Un
        # lien d'invitation non utilisé est un secret de plus qui traîne.
        self._fait("ajouté comme administrateur (aucun courriel envoyé).")

    # --- Étape « formations » -----------------------------------------------

    def _formations(self, client, compte, echeance_jours):
        self.stdout.write("Formations")
        from apps.training import services as training_services
        from apps.training.models import Course, CourseAssignment, Enrollment, Learner

        bibliotheque = [
            cours
            for cours in Course.objects.filter(owner_tenant__isnull=True, is_active=True)
            if cours.published_version is not None
        ]
        if not bibliotheque:
            self.stdout.write(
                self.style.WARNING(
                    "  aucun cours publié en bibliothèque : lancez d'abord "
                    "seed_catalogue_formation."
                )
            )
            return

        with training_services.contexte_du_client(client):
            deja = set(CourseAssignment.objects.values_list("course_id", flat=True))
            for cours in bibliotheque:
                if cours.id in deja:
                    self._deja(f"« {cours.title} » déjà proposé.")
                elif self.simulation:
                    self._fait(f"« {cours.title} » serait proposé.")
                else:
                    training_services.attribuer_cours(tenant=client, course=cours, actor=compte)
                    self._fait(f"« {cours.title} » proposé.")

            if self.simulation:
                self._fait(f"{compte.email} serait inscrit à {len(bibliotheque)} cours.")
                return

            apprenant = Learner.objects.filter(email__iexact=compte.email).first()
            if apprenant is None:
                apprenant = training_services.creer_apprenant(
                    tenant=client,
                    full_name=compte.get_full_name() or compte.email,
                    email=compte.email,
                    actor=compte,
                    # ``user`` renseigné : l'administrateur suit les cours
                    # depuis son propre espace, sans lien nominatif envoyé par
                    # courriel (ADR-039).
                    user=compte,
                )
                self._fait(f"apprenant créé pour {compte.email}.")
            elif apprenant.user_id is None:
                apprenant.user = compte
                apprenant.save(update_fields=["user"])
                self._fait("apprenant existant rattaché au compte.")

            echeance = (timezone.now() + timedelta(days=echeance_jours)).date()
            for cours in bibliotheque:
                version = cours.published_version
                if Enrollment.objects.filter(
                    learner=apprenant, version=version, revoked_at__isnull=True
                ).exists():
                    self._deja(f"déjà inscrit à « {cours.title} ».")
                    continue
                # Le jeton en clair rendu ici n'est PAS affiché : il ouvrirait
                # le parcours sans authentification, et il n'a pas à sortir
                # dans la sortie d'une commande ni dans un journal.
                training_services.inscrire(
                    tenant=client,
                    learner=apprenant,
                    course=cours,
                    due_date=echeance,
                    actor=compte,
                )
                self._fait(f"inscrit à « {cours.title} » (échéance {echeance:%d/%m/%Y}).")

    # --- Étape « documents » ------------------------------------------------

    def _documents(self, client, compte):
        self.stdout.write("Documents")
        from apps.ai_assistant import services as ai_services
        from apps.ai_assistant.documents import registry
        from apps.ai_assistant.models import GeneratedDocument

        presents = set(
            GeneratedDocument.all_objects.filter(tenant=client).values_list("type", flat=True)
        )

        for spec in registry.all_specs():
            if spec.source != registry.SOURCE_COMPOSED:
                # La charte informatique est le seul document RÉDIGÉ par l'IA
                # (ADR-032) : elle passe par un job, un quota de jetons et un
                # coût. Une commande de préparation ne la déclenche pas.
                self._deja(f"« {spec.label} » : rédigé par l'IA, non déclenché ici.")
                continue
            if spec.type in presents:
                self._deja(f"« {spec.label} » déjà présent.")
                continue

            etat = registry.readiness(client, spec)
            for manque in etat["missing"]:
                self.stdout.write(self.style.WARNING(f"    {spec.label} : {manque}"))

            if self.simulation:
                self._fait(f"« {spec.label} » serait composé.")
                continue

            document = ai_services.compose_document(
                tenant=client, user=compte, document_type=spec.type
            )
            # Laissés en BROUILLON, volontairement : valider un document, c'est
            # dire qu'un responsable l'a lu. Personne ne l'a lu.
            self._fait(f"« {spec.label} » composé (brouillon, v{document.version}).")

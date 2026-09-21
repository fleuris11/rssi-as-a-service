"""Inscrire, inviter, relancer (F3, ADR-041).

**La relance est le sujet sensible de ce module.** Un outil qui écrit à des
salariés au nom de leur employeur peut très vite devenir une machine à
harceler : c'est pourquoi tout ici est fait pour qu'elle en envoie le MOINS
possible.

- chaque nature de relance part **une fois** par inscription, jamais plus —
  garanti par une contrainte d'unicité en base, pas par une condition ;
- un salarié qui a **terminé** ne reçoit plus rien ;
- l'entreprise peut couper chaque moment séparément, ou tout couper.

**Pourquoi une relance porte un lien NEUF.** Le jeton n'est stocké que haché
(ADR-039) : on ne peut pas rappeler le lien déjà envoyé, on ne peut qu'en
émettre un autre. Conséquence assumée et à dire au salarié : le lien précédent
cesse de fonctionner. Elle a un effet secondaire utile — un lien qui dort dans
une vieille boîte aux lettres s'éteint à chaque relance.
"""

import csv
import io
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import emails, services
from .models import Certificate, Enrollment, Learner, ReminderLog, ReminderPolicy

#: Séparateurs acceptés à l'import. Le point-virgule d'abord : c'est ce que
#: produit Excel en français, et c'est le fichier que le client aura sous la
#: main.
SEPARATEURS = (";", ",", "\t")


class ImportRefuse(services.TrainingError):
    """Le fichier n'est pas exploitable du tout."""


# --- La politique de relance ------------------------------------------------


def politique(tenant) -> ReminderPolicy:
    existante = ReminderPolicy.objects.filter(tenant=tenant).first()
    if existante is not None:
        return existante
    return ReminderPolicy.objects.create(tenant=tenant)


def regler_la_politique(*, tenant, actor=None, **champs) -> ReminderPolicy:
    reglage = politique(tenant)
    for nom in ("enabled", "mid_course", "before_due_days", "after_due_days"):
        if nom in champs and champs[nom] is not None:
            setattr(reglage, nom, champs[nom])
    reglage.updated_by = actor
    reglage.save()
    return reglage


# --- L'import d'une liste ---------------------------------------------------


def _lignes(contenu: str):
    """Découpe le fichier, quel que soit son séparateur.

    On sniffe plutôt que d'imposer : demander à un client de reformater son
    export de paie avant de pouvoir inscrire ses salariés, c'est lui demander
    de renoncer.
    """
    texte = contenu.replace("\r\n", "\n").strip()
    if not texte:
        raise ImportRefuse("Le fichier est vide.")

    premiere = texte.split("\n", 1)[0]
    separateur = max(SEPARATEURS, key=premiere.count)
    if premiere.count(separateur) == 0:
        raise ImportRefuse(
            "Aucune colonne détectée. Attendu : un nom et une adresse par ligne, "
            "séparés par un point-virgule."
        )
    return list(csv.reader(io.StringIO(texte), delimiter=separateur))


def importer_des_salaries(*, tenant, contenu: str, actor=None) -> dict:
    """Crée les salariés d'un fichier. Ne s'arrête JAMAIS à la première erreur.

    Un import qui échoue sur la ligne 12 d'un fichier de 80 et n'en dit pas
    plus oblige à recommencer douze fois. On traite tout, et on rend le détail
    ligne par ligne.
    """
    resultat = {"crees": [], "deja_presents": [], "invalides": []}

    for numero, colonnes in enumerate(_lignes(contenu), start=1):
        cellules = [c.strip() for c in colonnes if c is not None]
        if not any(cellules):
            continue

        # En-tête : on la reconnaît et on la saute, plutôt que de créer un
        # salarié nommé « Nom ».
        if numero == 1 and any(
            c.lower() in {"nom", "name", "email", "adresse", "courriel"} for c in cellules
        ):
            continue

        if len(cellules) < 2:
            resultat["invalides"].append({"ligne": numero, "raison": "Il manque une colonne."})
            continue

        nom, email = cellules[0], cellules[1].lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            resultat["invalides"].append(
                {"ligne": numero, "raison": f"« {email} » n'est pas une adresse."}
            )
            continue
        if not nom:
            resultat["invalides"].append({"ligne": numero, "raison": "Le nom est vide."})
            continue

        try:
            salarie = services.creer_apprenant(
                tenant=tenant, full_name=nom, email=email, actor=actor
            )
        except services.InscriptionRefusee:
            resultat["deja_presents"].append(email)
            continue
        resultat["crees"].append({"id": str(salarie.id), "full_name": salarie.full_name})

    return resultat


# --- Inviter ----------------------------------------------------------------


@transaction.atomic
def inscrire_et_inviter(*, tenant, learner, course, due_date, actor=None) -> tuple[Enrollment, str]:
    """Inscrit, puis envoie le lien au salarié.

    L'envoi est dans la même transaction que l'inscription : si le courriel ne
    part pas, l'inscription n'existe pas non plus. Une inscription muette
    serait pire qu'aucune — le salarié ne saurait rien, et l'administrateur
    croirait l'avoir prévenu.
    """
    inscription, jeton = services.inscrire(
        tenant=tenant, learner=learner, course=course, due_date=due_date, actor=actor
    )
    emails.envoyer_invitation(inscription, services.lien_de_session(jeton))
    # Le jeton est rendu aussi à l'appelant : la console l'affiche une fois,
    # pour le cas où le courriel n'arriverait pas.
    return inscription, jeton


# --- Relancer ---------------------------------------------------------------


def _a_termine(inscription) -> bool:
    return Certificate.all_objects.filter(enrollment=inscription).exists()


def relances_du_jour(*, maintenant=None) -> list[tuple[Enrollment, str]]:
    """Ce qu'il y a à envoyer aujourd'hui, et rien de plus.

    Rend des couples ``(inscription, nature)``. Fonction pure de lecture :
    c'est elle qu'on teste, l'envoi n'étant qu'une boucle par-dessus.
    """
    maintenant = maintenant or timezone.now()
    aujourdhui = maintenant.date()
    a_faire = []

    politiques = {p.tenant_id: p for p in ReminderPolicy.all_objects.all()}

    inscriptions = Enrollment.all_objects.filter(
        revoked_at__isnull=True, learner__is_active=True
    ).select_related("learner", "version", "version__course", "tenant")

    # ``all_objects`` et non l'accès par relation : cette fonction balaie TOUS
    # les clients, donc hors contexte de cloisonnement. Le manager par défaut
    # échoue fermé — ``inscription.reminders.all()`` y rendrait toujours zéro,
    # et chaque relance repartirait tous les jours. C'est la contrainte
    # d'unicité en base qui a révélé le défaut.
    deja_envoyees = {}
    for enrollment_id, nature in ReminderLog.all_objects.values_list("enrollment_id", "kind"):
        deja_envoyees.setdefault(enrollment_id, set()).add(nature)

    for inscription in inscriptions:
        reglage = politiques.get(inscription.tenant_id)
        # Pas de politique enregistrée = les valeurs par défaut du modèle.
        if reglage is not None and not reglage.enabled:
            continue
        if not inscription.is_usable:
            # Lien mort : relancer avec un lien neuf serait possible, mais
            # rallonger une campagne close est une décision de gestion.
            continue
        if _a_termine(inscription):
            # L'erreur classique du genre : continuer d'écrire à quelqu'un qui
            # a fini. Elle est vérifiée par un test dédié.
            continue

        deja = deja_envoyees.get(inscription.id, set())
        debut = inscription.created_at.date()
        echeance = inscription.due_date

        mi_parcours = debut + timedelta(days=max(1, (echeance - debut).days // 2))
        avant = echeance - timedelta(days=(reglage.before_due_days if reglage else 3))
        apres = echeance + timedelta(days=(reglage.after_due_days if reglage else 2))

        actif = {
            ReminderLog.Kind.MID: (reglage.mid_course if reglage else True),
            ReminderLog.Kind.BEFORE: (reglage.before_due_days if reglage else 3) > 0,
            ReminderLog.Kind.AFTER: (reglage.after_due_days if reglage else 2) > 0,
        }
        # Une seule relance par jour et par salarié : si deux moments tombent
        # le même jour — campagne courte —, on n'en envoie qu'une.
        for nature, jour in (
            (ReminderLog.Kind.AFTER, apres),
            (ReminderLog.Kind.BEFORE, avant),
            (ReminderLog.Kind.MID, mi_parcours),
        ):
            if nature in deja or not actif[nature]:
                continue
            if aujourdhui >= jour:
                a_faire.append((inscription, nature))
                break

    return a_faire


def envoyer_les_relances(*, maintenant=None) -> int:
    """Envoie ce que ``relances_du_jour`` a désigné. Rend le nombre envoyé."""
    envoyees = 0
    for inscription, nature in relances_du_jour(maintenant=maintenant):
        with services.contexte_du_client(inscription.tenant):
            # Le lien précédent meurt ici : on ne peut pas le rappeler, il
            # n'est stocké que haché. Le message le dit au salarié.
            jeton = services.renouveler_le_lien(enrollment=inscription)
            emails.envoyer_relance(inscription, services.lien_de_session(jeton), nature)
            ReminderLog.objects.create(
                tenant=inscription.tenant, enrollment=inscription, kind=nature
            )
            envoyees += 1
    return envoyees


def salaries_sans_inscription(tenant):
    """Les salariés déclarés que personne n'a encore inscrits — l'oubli le
    plus courant après un import."""
    inscrits = Enrollment.objects.filter(revoked_at__isnull=True).values_list(
        "learner_id", flat=True
    )
    return Learner.objects.filter(is_active=True).exclude(id__in=inscrits)

"""Les faits de la plateforme, rassemblés une fois pour tous les documents.

Un seul endroit qui interroge les autres apps, et il le fait **par leur
``services.py``** (règle d'architecture n°1) : la politique de sécurité, le
plan de continuité et le rapport de comité doivent dire la même chose du même
client le même jour. Deux collectes parallèles finiraient par diverger, et
c'est exactement le genre d'écart qu'un lecteur repère et qui lui fait perdre
confiance dans les deux documents à la fois.

Aucune donnée personnelle n'entre ici au-delà de ce que le client a lui-même
saisi sur sa fiche (raison sociale, adresse, contact). Les identifiants
retrouvés dans des fuites sont **comptés**, jamais nommés : un registre des
incidents qui listerait « jean.dupont@… » circulerait ensuite en pièce jointe.
"""

from apps.actions import services as actions_services
from apps.assessments import services as assessments_services
from apps.monitoring import services as monitoring_services
from apps.threat_intelligence import services as ti_services

# Ce qu'on écrit quand la plateforme ne sait pas. Uniforme dans tous les
# documents : un lecteur doit reconnaître d'un coup d'œil ce qui reste à sa
# charge, et pouvoir chercher la chaîne dans son traitement de texte.
A_COMPLETER = "*[à compléter]*"


def company(tenant) -> dict:
    """La fiche de l'entreprise, telle qu'elle a été saisie."""
    return {
        "raison_sociale": tenant.name,
        "secteur": tenant.sector or "",
        "effectif": tenant.headcount,
        "adresse": tenant.address or "",
        "contact_email": tenant.contact_email or "",
        "contact_phone": tenant.contact_phone or "",
        "site_web": tenant.website or "",
    }


def assets(tenant) -> list[dict]:
    """Les actifs déclarés — ce que l'entreprise a dit posséder et fait
    surveiller. C'est le seul inventaire dont la plateforme dispose ; les
    documents le présentent comme tel, jamais comme un inventaire complet du
    système d'information."""
    return [
        {
            "type": asset.get_type_display(),
            "valeur": asset.value,
            "actif": asset.is_active,
            "possession": monitoring_services.ownership_state(asset),
        }
        for asset in monitoring_services.list_assets(tenant)
    ]


def maturity(tenant) -> dict:
    """Le dernier diagnostic terminé : score global, score par domaine, et
    les mesures en écart. ``None`` si aucun diagnostic n'a été terminé — les
    composeurs le disent au lieu d'écrire un zéro."""
    assessment = assessments_services.get_latest_completed_assessment(tenant)
    if assessment is None:
        return {
            "evalue": False,
            "referentiel": None,
            "date": None,
            "score_global": None,
            "par_domaine": [],
            "ecarts": [],
        }

    scores = assessments_services.compute_scores(assessment)
    valeurs = assessments_services.get_answer_values(assessment)
    # Le périmètre de CETTE évaluation (V2-4) : un diagnostic mené sur un
    # sous-ensemble ne doit pas faire dire au document que 42 mesures ont été
    # examinées.
    mesures = assessments_services.get_assessment_measures(assessment)

    ecarts = []
    for mesure in mesures:
        if valeurs.get(mesure.id) not in assessments_services.GAP_VALUES:
            continue
        ecarts.append(
            {
                "domaine": mesure.domain.name,
                "code": mesure.code,
                "intitule": mesure.official_title,
                "enonce": mesure.plain_language,
                "partiel": valeurs.get(mesure.id) == "partial",
                "impact": mesure.impact,
                "effort": mesure.effort,
            }
        )

    return {
        "evalue": True,
        "referentiel": assessment.referential.name,
        "date": assessment.completed_at,
        "score_global": scores["global"],
        "par_domaine": scores["by_domain"],
        "mesures_examinees": len(mesures),
        "ecarts": ecarts,
    }


def action_plan(tenant) -> list[dict]:
    """Le plan d'action ouvert, priorité décroissante — ce qui reste à faire
    et pour quand."""
    lignes = []
    for item in actions_services.list_action_items(tenant):
        if item.status not in actions_services.OPEN_STATUSES:
            continue
        lignes.append(
            {
                "mesure": item.measure.official_title,
                "enonce": item.measure.statement,
                "domaine": item.measure.domain.name,
                "referentiel": item.measure.referential.name,
                "statut": item.get_status_display(),
                "echeance": item.due_date,
                "responsable": item.assignee.get_full_name() if item.assignee_id else "",
            }
        )
    return lignes


def detected_events(tenant) -> list[dict]:
    """Ce que la plateforme a DÉTECTÉE elle-même et qui mérite une ligne au
    registre des incidents : les alertes de surveillance ouvertes et les
    fuites de données.

    Les identifiants ne sortent jamais d'ici. Une fuite devient « un compte
    lié à exemple.fr » et non l'adresse elle-même : le registre est un
    document qui s'imprime, se transmet et finit en pièce jointe d'un courriel.
    """
    evenements = []

    for alerte in monitoring_services.list_open_alerts(tenant):
        evenements.append(
            {
                "detecte_le": alerte.opened_at,
                "source": "Surveillance",
                "nature": alerte.get_alert_type_display(),
                "actif": alerte.asset.value,
                "gravite": alerte.get_severity_display(),
                "statut": "En cours",
                "clos_le": None,
                "donnees_personnelles": False,
            }
        )

    for fuite in ti_services.list_findings(tenant):
        evenements.append(
            {
                "detecte_le": fuite.detected_at,
                "source": "Renseignement sur la menace",
                "nature": f"Compte exposé dans une fuite ({fuite.finding_type})",
                "actif": fuite.asset.value if fuite.asset_id else "",
                "gravite": fuite.get_severity_display(),
                "statut": fuite.get_status_display(),
                "clos_le": fuite.treated_at,
                # Une adresse professionnelle retrouvée dans une fuite EST une
                # donnée personnelle : le registre doit le signaler, c'est ce
                # qui déclenche l'analyse au titre de l'article 33 du RGPD.
                "donnees_personnelles": True,
            }
        )

    evenements.sort(key=lambda ligne: ligne["detecte_le"], reverse=True)
    return evenements


def full(tenant) -> dict:
    """Tout, en une passe. Les composeurs prennent ce dictionnaire : cela
    évite qu'un document interroge la base trois fois pour le même chiffre."""
    return {
        "entreprise": company(tenant),
        "actifs": assets(tenant),
        "maturite": maturity(tenant),
        "plan_action": action_plan(tenant),
        "evenements": detected_events(tenant),
    }

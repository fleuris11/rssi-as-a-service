"""Public interface of the notifications app — other apps must go through
here instead of importing apps.notifications.models directly. Like
apps.monitoring, every function uses ``all_objects`` with an explicit
tenant filter, since Celery tasks have no ambient request context.
"""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from apps.ai_assistant import services as ai_assistant_services
from apps.monitoring import plain_language as monitoring_plain_language
from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Alert, CheckResult
from apps.tenants import services as tenants_services
from apps.tenants.models import Membership
from apps.threat_intelligence import plain_language as breach_plain_language
from apps.threat_intelligence import services as threat_intelligence_services
from apps.threat_intelligence.models import BreachFinding

from .models import EmailLog, NotificationPreferences

WEATHER_TIME_BUCKET_MINUTES = 15

# Types de compromission détaillés dans la météo. Un email quotidien est un
# résumé, pas un inventaire : au-delà, on renvoie vers le tableau de bord.
WEATHER_MAX_BREACH_TYPES = 3

_STATUS_RANK = {
    CheckResult.Status.OK: 0,
    CheckResult.Status.WARNING: 1,
    CheckResult.Status.CRITICAL: 2,
}
# La métaphore météo, tenue jusqu'au bout. Elle n'est pas décorative : un
# dirigeant qui ouvre son téléphone le matin doit connaître son état en une
# seconde, avant même de lire une phrase. D'où un symbole VRAIMENT
# météorologique (le ⚠️ et le 🔴 précédents étaient des pictogrammes
# d'alerte, qui ne racontaient aucun temps qu'il fait), un verdict en une
# phrase, et une légende en bas de l'email pour que le symbole s'interprète
# sans avoir à le deviner.
_MOOD_EMOJI = {
    CheckResult.Status.OK: "☀️",
    CheckResult.Status.WARNING: "⛅",
    CheckResult.Status.CRITICAL: "⛈️",
}
_MOOD_LABEL = {
    CheckResult.Status.OK: "Beau temps",
    CheckResult.Status.WARNING: "Quelques nuages",
    CheckResult.Status.CRITICAL: "Orage",
}
# Le verdict : ce qu'un dirigeant doit comprendre avant tout le reste.
_MOOD_VERDICT = {
    CheckResult.Status.OK: (
        "Rien ne demande votre attention aujourd'hui. Vos actifs répondent, "
        "et aucune compromission n'est en attente de traitement."
    ),
    CheckResult.Status.WARNING: (
        "Rien d'urgent, mais des points méritent d'être traités cette semaine. "
        "Le détail est ci-dessous."
    ),
    CheckResult.Status.CRITICAL: (
        "Quelque chose demande une action de votre part aujourd'hui. "
        "Commencez par le premier point ci-dessous."
    ),
}
_MOOD_LEGENDE = (
    ("☀️", "Beau temps", "tout répond, rien à traiter."),
    ("⛅", "Quelques nuages", "rien d'urgent, des points à regarder cette semaine."),
    ("⛈️", "Orage", "une action est attendue de votre part aujourd'hui."),
)


# --- Preferences -----------------------------------------------------------


def get_or_create_preferences(tenant) -> NotificationPreferences:
    prefs, _created = NotificationPreferences.all_objects.get_or_create(tenant=tenant)
    return prefs


def update_preferences(tenant, **fields) -> NotificationPreferences:
    prefs = get_or_create_preferences(tenant)
    for key, value in fields.items():
        setattr(prefs, key, value)
    prefs.save()
    return prefs


def list_preferences_due_for_weather(now):
    """Preferences whose chosen weather_time falls in the current
    ~15-minute dispatch window — a once-a-day digest doesn't need
    to-the-minute precision."""
    due = []
    for prefs in NotificationPreferences.all_objects.filter(weather_enabled=True).select_related(
        "tenant"
    ):
        same_hour = prefs.weather_time.hour == now.hour
        same_bucket = (
            prefs.weather_time.minute // WEATHER_TIME_BUCKET_MINUTES
            == now.minute // WEATHER_TIME_BUCKET_MINUTES
        )
        if same_hour and same_bucket:
            due.append(prefs)
    return due


def list_recipient_emails(tenant) -> list[str]:
    """Weather/alert emails go to the tenant's admins — the account
    owner(s) — not every contributor/reader, to avoid flooding inboxes."""
    return list(
        tenants_services.list_members(tenant)
        .filter(role=Membership.Role.ADMIN)
        .values_list("user__email", flat=True)
    )


# --- Sending -----------------------------------------------------------------


def _already_sent_today(tenant, kind: str) -> bool:
    return EmailLog.all_objects.filter(
        tenant=tenant, kind=kind, sent_at__date=timezone.localdate()
    ).exists()


def _send_email(*, tenant, kind: str, recipients, subject, text_body, html_body, details=None):
    if not recipients:
        return None
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        to=recipients,
        from_email=settings.DEFAULT_FROM_EMAIL,
    )
    message.attach_alternative(html_body, "text/html")
    message.send()
    for recipient in recipients:
        EmailLog.all_objects.create(
            tenant=tenant, kind=kind, recipient=recipient, subject=subject, details=details or {}
        )
    return message


# --- Météo cyber quotidienne -------------------------------------------------


def build_weather_context(tenant) -> dict:
    dashboard = monitoring_services.get_tenant_dashboard(tenant)
    open_alerts = list(monitoring_services.list_open_alerts(tenant))

    asset_rows = []
    worst = CheckResult.Status.OK
    for row in dashboard:
        checks_summary = []
        for result in row["latest_checks"].values():
            if result is None:
                continue
            checks_summary.append(
                {
                    "label": CheckResult.CheckType(result.check_type).label,
                    "status_label": CheckResult.Status(result.status).label,
                    "status": result.status,
                }
            )
            if _STATUS_RANK[result.status] > _STATUS_RANK[worst]:
                worst = result.status
        # Le pire contrôle de CET actif — pour lui donner son propre temps,
        # au lieu de laisser le lecteur recomposer un état à partir d'une
        # liste de lignes « OK / OK / Avertissement ».
        pire_actif = CheckResult.Status.OK
        for controle in checks_summary:
            if _STATUS_RANK[controle["status"]] > _STATUS_RANK[pire_actif]:
                pire_actif = controle["status"]
        asset_rows.append(
            {
                "value": row["asset"].value,
                "type_label": row["asset"].get_type_display(),
                "uptime_24h": row["uptime_24h"],
                "checks": checks_summary,
                "mood_emoji": _MOOD_EMOJI[pire_actif],
                "mood_label": _MOOD_LABEL[pire_actif],
                "is_ok": pire_actif == CheckResult.Status.OK,
            }
        )

    if open_alerts:
        if any(a.severity == Alert.Severity.CRITICAL for a in open_alerts):
            worst = CheckResult.Status.CRITICAL
        elif _STATUS_RANK[worst] < _STATUS_RANK[CheckResult.Status.WARNING]:
            worst = CheckResult.Status.WARNING

    # Chaque alerte porte son sens et son action, comme les fuites. Sans
    # cela, la météo annonçait « Certificat SSL bientôt expiré » et laissait
    # le dirigeant deviner si c'était grave et qui devait s'en occuper.
    # Alertes de surveillance, regroupées PAR TYPE — même principe que les
    # compromissions, et pour la même raison : trois actifs injoignables
    # produisaient trois blocs « Site indisponible » rigoureusement
    # identiques, explication et action comprises. Le dirigeant a besoin de
    # savoir qu'il y a une panne et quels actifs elle touche, pas de lire
    # trois fois la même consigne.
    #
    # Les alertes de type « compromission » sont exclues : les fuites sont
    # déjà détaillées plus haut, par type, avec leur sens et leur action. Les
    # garder ici répétait « ouvrez la page Compromissions » juste sous la
    # section qui venait de tout expliquer. Elles continuent de compter dans
    # le temps du jour (`worst`), elles ne sont simplement plus redites.
    groupes_alertes: dict[str, dict] = {}
    for alert in open_alerts:
        if alert.alert_type == Alert.AlertType.BREACH_COMPROMISE:
            continue
        groupe = groupes_alertes.get(alert.alert_type)
        if groupe is None:
            explication = monitoring_plain_language.explain(alert.alert_type)
            groupes_alertes[alert.alert_type] = {
                "type_label": alert.get_alert_type_display(),
                "severity_label": alert.get_severity_display(),
                "meaning": explication["meaning"],
                "action": explication["action"],
                "assets": [alert.asset.value],
            }
            continue
        if alert.asset.value not in groupe["assets"]:
            groupe["assets"].append(alert.asset.value)

    for groupe in groupes_alertes.values():
        groupe["count"] = len(groupe["assets"])
        groupe["assets_label"] = ", ".join(groupe["assets"][:3])
        groupe["assets_extra"] = max(0, len(groupe["assets"]) - 3)

    alert_rows = list(groupes_alertes.values())

    # Phase 7 (ADR-013) : les BREACH_COMPROMISE ouvertes sont déjà comptées
    # dans `open_alerts`/`worst` ci-dessus (même moteur d'alertes que le
    # reste de la surveillance — rien à dupliquer pour la météo ☀️/⚠️/🔴).
    # Cette liste distincte apporte le détail (endpoint d'origine,
    # identifiant) que l'Alert générique n'a pas, pour que la reformulation
    # IA (_maybe_enrich_weather_summary) puisse être concrète ("un compte a
    # été trouvé dans une fuite de type X") plutôt que générique.
    # Regroupement par TYPE DE FUITE, pas par ligne.
    #
    # L'email listait les fuites une à une — vingt lignes « crrhuemoa.org —
    # Surface d'attaque (Attention) » à la file. Un dirigeant n'a ni le temps
    # ni la raison de lire un inventaire : ce qu'il doit savoir, c'est de
    # QUOI il s'agit, ce que ça risque de produire, et ce qu'il faut faire.
    # Le détail ligne à ligne existe déjà, dans son espace.
    #
    # Les phrases viennent de `threat_intelligence.plain_language`, qui les
    # sert déjà à l'écran : une seule voix, un seul endroit à relire.
    _RANG = {
        BreachFinding.Severity.CRITICAL: 0,
        BreachFinding.Severity.HIGH: 1,
        BreachFinding.Severity.ATTENTION: 2,
    }
    findings_ouvertes = list(
        threat_intelligence_services.list_findings(
            tenant, status=BreachFinding.Status.OPEN, include_pre_incident=True
        ).select_related("asset")
    )
    findings_ouvertes.sort(key=lambda f: (_RANG.get(f.severity, 9), f.asset.value))

    groupes: dict[tuple, dict] = {}
    for finding in findings_ouvertes:
        explication = breach_plain_language.explain(finding)
        cle = (finding.source_endpoint, finding.finding_type, finding.severity)
        groupe = groupes.get(cle)
        if groupe is None:
            groupes[cle] = {
                "type_label": finding.get_source_endpoint_display(),
                "severity": finding.severity,
                "severity_label": finding.get_severity_display(),
                "meaning": explication["meaning"],
                "action": explication["action"],
                "count": 1,
                "assets": [finding.asset.value],
            }
            continue
        groupe["count"] += 1
        if finding.asset.value not in groupe["assets"]:
            groupe["assets"].append(finding.asset.value)

    for groupe in groupes.values():
        groupe["assets_label"] = ", ".join(groupe["assets"][:3])
        groupe["assets_extra"] = max(0, len(groupe["assets"]) - 3)

    breach_rows = list(groupes.values())[:WEATHER_MAX_BREACH_TYPES]
    breach_total = len(findings_ouvertes)
    breach_types_hidden = max(0, len(groupes) - len(breach_rows))

    # Le temps du jour tient compte des FUITES, pas seulement des alertes.
    #
    # Défaut relevé le 04/09/2026 sur un vrai client : le bulletin titrait
    # « ⛅ Quelques nuages — rien d'urgent » quelques lignes au-dessus d'un
    # bloc « Sessions / cookies compromis — Critique ». Le titre contredisait
    # le contenu du même email, ce qui est pire que l'un ou l'autre pris
    # séparément : le lecteur pressé s'arrête au titre.
    #
    # La cause : l'humeur ne se calculait que sur les contrôles de
    # surveillance et sur la sévérité des ALERTES. Or l'alerte ouverte pour
    # une compromission porte sa propre sévérité, qui n'est pas celle de la
    # fuite la plus grave qu'elle recouvre — deux fuites critiques vivaient
    # donc sous une alerte « avertissement ».
    if any(f.severity == BreachFinding.Severity.CRITICAL for f in findings_ouvertes):
        worst = CheckResult.Status.CRITICAL
    elif findings_ouvertes and _STATUS_RANK[worst] < _STATUS_RANK[CheckResult.Status.WARNING]:
        # Une fuite ouverte, même « élevée » ou « attention », n'est pas un
        # beau temps : il reste quelque chose à traiter.
        worst = CheckResult.Status.WARNING

    context = {
        "tenant_name": tenant.name,
        "date": timezone.localdate(),
        "mood_emoji": _MOOD_EMOJI[worst],
        "mood_label": _MOOD_LABEL[worst],
        "mood_verdict": _MOOD_VERDICT[worst],
        "legende": _MOOD_LEGENDE,
        "tout_va_bien": worst == CheckResult.Status.OK,
        "assets": asset_rows,
        "open_alerts": alert_rows,
        "open_breach_findings": breach_rows,
        "breach_total": breach_total,
        "breach_types_hidden": breach_types_hidden,
        "dashboard_url": f"{settings.FRONTEND_BASE_URL}/surveillance",
    }
    context["enriched_summary"] = _maybe_enrich_weather_summary(tenant, context)
    return context


def _maybe_enrich_weather_summary(tenant, context: dict) -> str | None:
    """Cas d'usage 3 (optionnel par tenant) : reformulation Haiku du résumé
    déterministe via le pipeline de pseudonymisation d'ai_assistant. Renvoie
    toujours ``None`` proprement (jamais d'exception) si désactivé, si le
    tenant n'a pas activé l'IA, si le quota est dépassé ou si l'appel
    échoue — apps.notifications.services.enrich_weather_summary garantit
    déjà ce comportement, mais le template déterministe (déjà construit
    dans ``context``) reste dans tous les cas le contenu envoyé si ce champ
    est vide : la météo part toujours (CLAUDE.md)."""
    prefs = get_or_create_preferences(tenant)
    if not prefs.weather_enrichment_enabled:
        return None
    deterministic_context = {
        "synthese": context["mood_label"],
        "actifs": [
            {
                "type": asset["type_label"],
                "valeur": asset["value"],
                "disponibilite_24h": asset["uptime_24h"],
                "checks": asset["checks"],
            }
            for asset in context["assets"]
        ],
        "alertes_ouvertes": context["open_alerts"],
        "compromissions_ouvertes": context["open_breach_findings"],
    }
    return ai_assistant_services.enrich_weather_summary(
        tenant=tenant, deterministic_context=deterministic_context
    )


def send_weather_email(tenant):
    # La préférence est vérifiée ICI, et pas seulement par l'ordonnanceur.
    #
    # `list_preferences_due_for_weather` filtre déjà sur `weather_enabled`,
    # mais c'était le SEUL endroit : cette fonction, appelée directement,
    # envoyait à un client qui avait justement demandé à ne plus recevoir.
    # Un réglage qui n'est honoré que par un seul de ses appelants n'est pas
    # un réglage, c'est une coïncidence — d'autant qu'ici il porte un refus
    # explicite du client.
    #
    # `send_realtime_alert_email` faisait déjà cette vérification ; la météo
    # ne la faisait pas. Découvert en coupant les emails du tenant de
    # démonstration : la coupure était sans effet sur cet appel.
    prefs = get_or_create_preferences(tenant)
    if not prefs.weather_enabled:
        return None
    if _already_sent_today(tenant, EmailLog.Kind.WEATHER):
        return None
    recipients = list_recipient_emails(tenant)
    if not recipients:
        return None

    context = build_weather_context(tenant)
    # Le symbole météo EST l'information : il dit l'état avant l'ouverture.
    subject = (
        f"{context['mood_emoji']} Bulletin du {context['date']:%d/%m} — "
        f"{context['mood_label']} — {tenant.name}"
    )
    text_body = render_to_string("notifications/weather_email.txt", context)
    html_body = render_to_string("notifications/weather_email.html", context)

    return _send_email(
        tenant=tenant,
        kind=EmailLog.Kind.WEATHER,
        recipients=recipients,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        details={"mood": context["mood_label"], "ai_enriched": bool(context["enriched_summary"])},
    )


# --- Alertes temps réel (US-5.6) ---------------------------------------------


def send_realtime_alert_email(alert: Alert):
    tenant = alert.tenant
    prefs = get_or_create_preferences(tenant)
    if not prefs.realtime_alerts_enabled:
        return None
    recipients = list_recipient_emails(tenant)
    if not recipients:
        return None

    explication = monitoring_plain_language.explain(alert.alert_type)
    context = {
        "tenant_name": tenant.name,
        "asset_value": alert.asset.value,
        "alert_type_label": alert.get_alert_type_display(),
        "severity_label": alert.get_severity_display(),
        "meaning": explication["meaning"],
        "action": explication["action"],
        "details": alert.details,
        "dashboard_url": f"{settings.FRONTEND_BASE_URL}/surveillance",
    }
    # Objet volontairement SANS symbole météo : dans une boîte de réception,
    # « Alerte » et « Météo » doivent se distinguer avant ouverture. Le nom du
    # type d'alerte passe devant l'actif — c'est ce qui dit s'il faut ouvrir
    # tout de suite.
    subject = f"Alerte — {alert.get_alert_type_display()} — {alert.asset.value}"
    text_body = render_to_string("notifications/realtime_alert_email.txt", context)
    html_body = render_to_string("notifications/realtime_alert_email.html", context)

    return _send_email(
        tenant=tenant,
        kind=EmailLog.Kind.REALTIME_ALERT,
        recipients=recipients,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        details={"alert_id": alert.id, "alert_type": alert.alert_type},
    )


# --- Signaux avant-coureurs (Phase 8A) ---------------------------------------


def send_pre_incident_signal_email(finding: BreachFinding):
    """Deliberately a different message from ``send_realtime_alert_email``:
    a pre-incident signal means "we're watching, nothing has leaked yet",
    and telling a business owner "🔴 Alerte" for a look-alike domain
    registration would train them to ignore the alerts that DO mean a real
    leak. Gated by the same ``realtime_alerts_enabled`` preference — it's
    still a real-time push, just a calmer one."""
    tenant = finding.tenant
    prefs = get_or_create_preferences(tenant)
    if not prefs.realtime_alerts_enabled:
        return None
    recipients = list_recipient_emails(tenant)
    if not recipients:
        return None

    signal_type = threat_intelligence_services.classify_pre_incident_signal(finding)
    definition = threat_intelligence_services.pre_incident_definition(signal_type)

    context = {
        "tenant_name": tenant.name,
        "signal_label": definition["label"],
        "plain_language": definition["plain_language"],
        "detail": threat_intelligence_services.pre_incident_detail(finding),
        "asset_value": finding.asset.value,
        "compromissions_url": f"{settings.FRONTEND_BASE_URL}/compromissions",
    }
    subject = f"👁️ Signal avant-coureur — {tenant.name} — {definition['label']}"
    text_body = render_to_string("notifications/pre_incident_signal_email.txt", context)
    html_body = render_to_string("notifications/pre_incident_signal_email.html", context)

    return _send_email(
        tenant=tenant,
        kind=EmailLog.Kind.PRE_INCIDENT_SIGNAL,
        recipients=recipients,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        details={"finding_id": finding.id, "signal_type": signal_type},
    )

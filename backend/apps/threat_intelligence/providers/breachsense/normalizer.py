"""Turns a raw Breachsense payload (any endpoint — query or webhook) into
the fields ``threat_intelligence.services`` needs to create a
``BreachFinding`` — the ONLY place in the codebase that masks secrets
(ADR-014 §2), so every ingestion path (scan or webhook) is held to the
same non-storage discipline instead of each caller reimplementing it.

Deliberately model-agnostic (returns a plain dict, string severity values
matching ``BreachFinding.Severity``) so the provider layer never imports
Django models (ADR-013: "le reste du code ne dépend QUE de l'interface").
"""

import hashlib
from datetime import date

# Détection récursive, par sous-chaîne de nom de clé — délibérément large
# (ADR-014 §2 : "robuste face à des schémas hétérogènes selon l'endpoint")
# plutôt qu'une liste exacte de noms de champs par endpoint, qui casserait
# silencieusement dès qu'un endpoint utilise un nom légèrement différent.
SECRET_KEY_MARKERS = (
    "password",
    "pass",
    "pwd",
    "secret",
    "token",
    "cookie",
    "session",
    "hash",
    "credential",
    "api_key",
    "apikey",
    "auth",
)

# Mapping de sévérité imposé par le prompt Phase 7 : stealer/sessions/nhi/
# darkweb = critique ; creds/combo/docs = élevé ; radar/asm(-phishing) =
# attention.
SEVERITY_BY_ENDPOINT = {
    "stealer": "critical",
    "sessions": "critical",
    "nhi": "critical",
    "darkweb": "critical",
    "creds": "high",
    "combo": "high",
    "docs": "high",
    "radar": "attention",
    "asm": "attention",
}

_IDENTIFIER_KEYS = ("email", "login", "username", "user", "identifier")
_DATE_KEYS = ("breach_date", "date", "leaked_at", "discovered_at", "found_at")


def _is_secret_key(key: str) -> bool:
    key_lower = key.lower()
    return any(marker in key_lower for marker in SECRET_KEY_MARKERS)


def _mask_secret_value(value) -> str:
    text = str(value)
    tail = text[-2:] if len(text) >= 2 else text
    return f"{'•' * 6}{tail}"


def mask_payload(payload: dict) -> tuple[dict, bool, str]:
    """Recursively masks every secret-like value found anywhere in
    ``payload`` (ADR-014 §2: applied on the whole tree, not just top-level
    keys). Returns ``(masked_payload, secret_seen, first_secret_masked)``
    — ``first_secret_masked`` feeds ``BreachFinding.secret_masked`` (one
    representative masked value; the full — already masked — payload is
    what's kept in ``raw_data``)."""
    state = {"secret_seen": False, "first_masked": ""}

    def _walk(node):
        if isinstance(node, dict):
            result = {}
            for key, value in node.items():
                if isinstance(value, (dict, list)):
                    result[key] = _walk(value)
                elif _is_secret_key(key) and value not in (None, ""):
                    masked = _mask_secret_value(value)
                    state["secret_seen"] = True
                    if not state["first_masked"]:
                        state["first_masked"] = masked
                    result[key] = masked
                else:
                    result[key] = value
            return result
        if isinstance(node, list):
            return [_walk(item) for item in node]
        return node

    masked = _walk(payload)
    return masked, state["secret_seen"], state["first_masked"]


def _extract_identifier(payload: dict) -> str | None:
    for key in _IDENTIFIER_KEYS:
        value = payload.get(key)
        if value:
            return str(value)
    return None


def mask_identifier(identifier: str) -> str:
    """Non-reversible minimisation for identifiers that don't belong to
    the tenant (ADR-014 §4) — keeps enough shape to be recognisable
    (email vs. username) without exposing the value."""
    if "@" in identifier:
        local, _, domain = identifier.partition("@")
        local_mask = f"{local[:2]}••••" if len(local) > 2 else "••••"
        domain_parts = domain.split(".")
        head = domain_parts[0] if domain_parts else ""
        domain_mask = f"{head[:2]}••••" if len(head) > 2 else "••••"
        tld = "." + ".".join(domain_parts[1:]) if len(domain_parts) > 1 else ""
        return f"{local_mask}@{domain_mask}{tld}"
    return f"{identifier[:2]}••••" if len(identifier) > 2 else "••••"


def _extract_breach_date(payload: dict) -> date | None:
    for key in _DATE_KEYS:
        value = payload.get(key)
        if not value:
            continue
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            continue
    return None


def _compute_dedup_hash(
    *, endpoint: str, identifier: str | None, breach_date, secret_masked: str, raw_id
) -> str:
    source = "|".join(
        str(part)
        for part in (endpoint, identifier or "", breach_date or "", secret_masked, raw_id or "")
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def normalize_finding(endpoint: str, raw: dict, *, tenant_emails: set[str] | None = None) -> dict:
    """Returns a dict of kwargs ready for ``BreachFinding.all_objects.create``
    (minus ``tenant``/``asset``, which the caller already knows)."""
    tenant_emails = {email.lower() for email in (tenant_emails or set())}
    masked_payload, secret_seen, secret_masked = mask_payload(raw)

    identifier = _extract_identifier(raw)
    identifier_plain = ""
    identifier_masked = ""
    if identifier:
        if identifier.lower() in tenant_emails:
            identifier_plain = identifier
        else:
            identifier_masked = mask_identifier(identifier)

    breach_date = _extract_breach_date(raw)
    severity = SEVERITY_BY_ENDPOINT.get(endpoint, "attention")
    finding_type = str(raw.get("type") or raw.get("category") or endpoint)
    raw_id = raw.get("id") or raw.get("uuid")

    return {
        "source_endpoint": endpoint if endpoint in SEVERITY_BY_ENDPOINT else "webhook",
        "finding_type": finding_type,
        "severity": severity,
        "identifier_plain": identifier_plain,
        "identifier_masked": identifier_masked,
        "secret_masked": secret_masked,
        "secret_seen": secret_seen,
        "breach_date": breach_date,
        "raw_data": masked_payload,
        "dedup_hash": _compute_dedup_hash(
            endpoint=endpoint,
            identifier=identifier,
            breach_date=breach_date,
            secret_masked=secret_masked,
            raw_id=raw_id,
        ),
    }

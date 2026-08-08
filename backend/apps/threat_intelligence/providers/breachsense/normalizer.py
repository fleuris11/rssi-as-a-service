"""Turns a raw Breachsense payload (any endpoint — query or webhook) into
the fields ``threat_intelligence.services`` needs to create a
``BreachFinding`` — the ONLY place in the codebase that masks secrets
(ADR-014 §2), so every ingestion path (scan or webhook) is held to the
same non-storage discipline instead of each caller reimplementing it.

Field mapping is driven by the REAL Breachsense response schema per
endpoint (palier Essentials — supplied directly, not guessed), via
``ENDPOINT_SCHEMAS`` below. Each endpoint uses its own abbreviated JSON
vocabulary (``usr``/``pwd``, ``eml``, ``val``, ``token``...) that a
generic "email"/"date" field-name guess would never match — precision
here matters because a missed secret field is a real data leak (ADR-014),
not just a display bug. The old generic-keys heuristic is kept as a
**fallback layer only**, for endpoints/fields not in the known schema
(schema drift, a future new endpoint) — never the primary mechanism for
known endpoints.

Deliberately model-agnostic (returns a plain dict, string severity values
matching ``BreachFinding.Severity``) so the provider layer never imports
Django models (ADR-013: "le reste du code ne dépend QUE de l'interface").
"""

import hashlib
from dataclasses import dataclass, field
from datetime import date

# Secrets détectés par nom de clé EXACT — pour les champs dont le nom réel
# est trop abrégé/cryptique pour être fiable via une sous-chaîne générique
# (ex. "val" est le nom réel du cookie de session ; le détecter par
# sous-chaîne générique serait soit trop large - "val" apparaît dans
# beaucoup de noms de champs innocents en général -, soit ne servirait à
# rien vu qu'il n'y a pas de sous-chaîne "sûre" plus courte à en tirer).
EXACT_SECRET_FIELDS = {
    "val",  # sessions : valeur du cookie de session
    "ccn",  # stealer : numéro de carte bancaire
    "ccx",  # stealer : donnée de carte bancaire additionnelle (cryptogramme/expiration)
    "cwa",  # stealer : wallet crypto
}

# Sous-chaînes génériques — volontairement restreintes par rapport à une
# version précédente qui incluait aussi "cookie" et "hash" : sur le schéma
# réel, "cookie" aurait masqué à tort cookie_name/cookie_path (métadonnées,
# pas des secrets - seul "val" l'est), et "hash" aurait masqué à tort
# creds.hash (indicateur 0/1 "haché ou déchiffré", pas un secret) et
# docs.file_hash (empreinte du fichier fuité, pas un secret). Cette liste
# reste une ceinture de sécurité pour des champs non prévus (ADR-014 §2),
# pas le mécanisme principal pour les endpoints connus.
SECRET_KEY_MARKERS = (
    "password",
    "pass",
    "pwd",
    "secret",
    "token",
    "credential",
    "api_key",
    "apikey",
    "auth",
)

# Mapping de sévérité (imposé par le prompt Phase 7) : stealer/sessions/
# nhi/darkweb = critique ; creds/combo/docs = élevé ; radar/asm = attention
# — sauf asm.type == "pphish" (domaine de typosquatting/phishing usurpant
# la marque), plus grave que le reste de la surface d'attaque (ns/mx/ast,
# simple inventaire), remonté à "élevé".
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
ASM_PHISHING_TYPE = "pphish"
ASM_PHISHING_SEVERITY = "high"


@dataclass(frozen=True)
class EndpointSchema:
    """Réel vocabulaire de champs d'un endpoint Breachsense (palier
    Essentials). Tous les champs sont optionnels dans le payload réel
    (``fnd``, dates, etc. peuvent être absents) — l'extraction reste
    tolérante à leur absence."""

    identifier_fields: tuple[str, ...] = ()
    date_fields: tuple[str, ...] = ()
    type_field: str | None = None
    # Champs (non-secrets) utilisés pour construire le dédoublonnage —
    # en plus du secret masqué, jamais la valeur brute.
    dedup_fields: tuple[str, ...] = field(default_factory=tuple)


ENDPOINT_SCHEMAS: dict[str, EndpointSchema] = {
    # usr, pwd(SECRET), src, fle, fnd + optionnels nme/iip/inf/mal/os/hid/
    # bid/mac/pth/ccn(SECRET)/ccx(SECRET)/cwa(SECRET)
    "stealer": EndpointSchema(
        identifier_fields=("usr",),
        date_fields=("inf", "fnd"),
        type_field="mal",
        dedup_fields=("usr", "src", "inf", "fnd"),
    ),
    # usr, pwd(SECRET), src, fle, fnd, cnt
    "combo": EndpointSchema(
        identifier_fields=("usr",),
        date_fields=("fnd",),
        dedup_fields=("usr", "src", "fnd"),
    ),
    # eml, pwd(SECRET), src, fnd, atr, hash (0/1 — indicateur, pas un secret)
    "creds": EndpointSchema(
        identifier_fields=("eml",),
        date_fields=("fnd",),
        dedup_fields=("eml", "src", "fnd"),
    ),
    # dom, cookie_name, cookie_path, val(SECRET), expires, user_name, iip,
    # inf, mal, malware_path, bid, fnd — "expires" est la validité du
    # cookie, pas la date de la fuite : on utilise fnd, pas expires.
    "sessions": EndpointSchema(
        identifier_fields=("user_name",),
        date_fields=("fnd",),
        dedup_fields=("user_name", "dom", "cookie_name", "fnd"),
    ),
    # token(SECRET), token_type, platform, category, source_type, prefix,
    # src, pth, ip, usr, fnd + champs stealer optionnels (bid, hid, mal, os, av)
    "nhi": EndpointSchema(
        identifier_fields=("usr",),
        date_fields=("fnd",),
        type_field="category",
        dedup_fields=("usr", "platform", "src", "fnd"),
    ),
    # data (domaine victime), name (entreprise), desc, site (threat actor),
    # tadesc, src, found, img (absent en Essentials — palier Business+ uniquement)
    "darkweb": EndpointSchema(
        date_fields=("found",),
        dedup_fields=("data", "site", "found"),
    ),
    # data, src, found, img (absent en Essentials)
    "radar": EndpointSchema(
        date_fields=("found",),
        dedup_fields=("data", "src", "found"),
    ),
    # doc_id, file_name, file_hash, file_size, content_type,
    # extraction_timestamp, leak_date, threat_actor, company_name,
    # domain_name, url_main_post, url_for_breach, password(SECRET)
    "docs": EndpointSchema(
        date_fields=("leak_date",),
        type_field="content_type",
        dedup_fields=("doc_id", "file_hash"),
    ),
    # dom, type (ns/mx/ast/pphish), cname, ip, found
    "asm": EndpointSchema(
        date_fields=("found",),
        type_field="type",
        dedup_fields=("dom", "type", "cname", "ip"),
    ),
}

# Repli générique (schémas inconnus, endpoints futurs, dérive du schéma
# réel) — jamais consulté pour un champ déjà couvert par ENDPOINT_SCHEMAS
# ci-dessus, seulement quand celui-ci ne trouve rien.
_FALLBACK_IDENTIFIER_KEYS = (
    "email",
    "eml",
    "usr",
    "user_name",
    "login",
    "username",
    "user",
    "identifier",
)
_FALLBACK_DATE_KEYS = (
    "breach_date",
    "date",
    "leaked_at",
    "discovered_at",
    "found_at",
    "found",
    "fnd",
    "inf",
    "leak_date",
)
_FALLBACK_TYPE_KEYS = ("type", "category", "mal")


def _is_secret_key(key: str) -> bool:
    key_lower = key.lower()
    if key_lower in EXACT_SECRET_FIELDS:
        return True
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


def _first_present(payload: dict, fields: tuple[str, ...]) -> str | None:
    for key in fields:
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _extract_identifier(endpoint: str, payload: dict) -> str | None:
    schema = ENDPOINT_SCHEMAS.get(endpoint)
    value = _first_present(payload, schema.identifier_fields) if schema else None
    return value or _first_present(payload, _FALLBACK_IDENTIFIER_KEYS)


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


def _extract_breach_date(endpoint: str, payload: dict) -> date | None:
    schema = ENDPOINT_SCHEMAS.get(endpoint)
    raw_value = _first_present(payload, schema.date_fields) if schema else None
    raw_value = raw_value or _first_present(payload, _FALLBACK_DATE_KEYS)
    if not raw_value:
        return None
    try:
        return date.fromisoformat(str(raw_value)[:10])
    except ValueError:
        return None


def _extract_finding_type(endpoint: str, payload: dict) -> str:
    schema = ENDPOINT_SCHEMAS.get(endpoint)
    fields = (schema.type_field,) if schema and schema.type_field else ()
    return (
        _first_present(payload, fields) or _first_present(payload, _FALLBACK_TYPE_KEYS) or endpoint
    )


def _compute_severity(endpoint: str, payload: dict) -> str:
    if endpoint == "asm" and payload.get("type") == ASM_PHISHING_TYPE:
        return ASM_PHISHING_SEVERITY
    return SEVERITY_BY_ENDPOINT.get(endpoint, "attention")


def _compute_dedup_hash(*, endpoint: str, payload: dict, secret_masked: str) -> str:
    schema = ENDPOINT_SCHEMAS.get(endpoint)
    dedup_fields = schema.dedup_fields if schema else ()
    # Le champ secret (s'il y en a un pour cet endpoint) est représenté par
    # sa forme déjà masquée, jamais la valeur brute (ADR-014).
    values = [payload.get(f) for f in dedup_fields]
    values.append(secret_masked)
    source = "|".join(str(v) if v is not None else "" for v in values)
    return hashlib.sha256(f"{endpoint}|{source}".encode()).hexdigest()


def normalize_finding(endpoint: str, raw: dict, *, tenant_emails: set[str] | None = None) -> dict:
    """Returns a dict of kwargs ready for ``BreachFinding.all_objects.create``
    (minus ``tenant``/``asset``, which the caller already knows)."""
    tenant_emails = {email.lower() for email in (tenant_emails or set())}
    masked_payload, secret_seen, secret_masked = mask_payload(raw)

    identifier = _extract_identifier(endpoint, raw)
    identifier_plain = ""
    identifier_masked = ""
    if identifier:
        if identifier.lower() in tenant_emails:
            identifier_plain = identifier
        else:
            identifier_masked = mask_identifier(identifier)

    breach_date = _extract_breach_date(endpoint, raw)
    severity = _compute_severity(endpoint, raw)
    finding_type = _extract_finding_type(endpoint, raw)

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
            endpoint=endpoint, payload=raw, secret_masked=secret_masked
        ),
    }

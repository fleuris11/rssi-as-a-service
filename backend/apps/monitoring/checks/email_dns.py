"""Check (d): email DNS hygiene — SPF and DMARC (policy) presence and
consistency. DKIM is out of scope (its selector isn't discoverable from
the domain alone). No SSRF concern here: this only queries public DNS TXT
records through the resolver, it never opens a connection to the target
domain's own infrastructure."""

import dns.exception
import dns.resolver

from apps.monitoring.models import CheckResult

LOOKUP_TIMEOUT_SECONDS = 10


def _txt_strings(domain: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(domain, "TXT", lifetime=LOOKUP_TIMEOUT_SECONDS)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return []
    except dns.exception.DNSException as exc:
        raise RuntimeError(f"Requête DNS TXT impossible pour {domain!r} : {exc}") from exc

    records = []
    for answer in answers:
        # dnspython splits long TXT strings into chunks; join them back.
        records.append(b"".join(answer.strings).decode(errors="replace"))
    return records


def check_email_dns(domain: str) -> dict:
    issues = []
    details = {}

    try:
        spf_records = [t for t in _txt_strings(domain) if t.startswith("v=spf1")]
    except RuntimeError as exc:
        return {"status": CheckResult.Status.CRITICAL, "details": {"error": str(exc)}}

    if not spf_records:
        issues.append({"type": "spf_missing", "message": "Aucun enregistrement SPF trouvé."})
    else:
        if len(spf_records) > 1:
            issues.append(
                {
                    "type": "spf_multiple",
                    "message": "Plusieurs enregistrements SPF trouvés (un seul est autorisé).",
                }
            )
        details["spf"] = spf_records[0]

    try:
        dmarc_records = [t for t in _txt_strings(f"_dmarc.{domain}") if t.startswith("v=DMARC1")]
    except RuntimeError as exc:
        return {"status": CheckResult.Status.CRITICAL, "details": {"error": str(exc)}}

    if not dmarc_records:
        issues.append({"type": "dmarc_missing", "message": "Aucun enregistrement DMARC trouvé."})
    else:
        record = dmarc_records[0]
        details["dmarc"] = record
        policy = None
        for part in record.split(";"):
            part = part.strip()
            if part.startswith("p="):
                policy = part[2:].strip()
                break
        details["dmarc_policy"] = policy
        if policy == "none":
            issues.append(
                {
                    "type": "dmarc_policy_none",
                    "message": (
                        "La politique DMARC est « none » (surveillance uniquement, "
                        "aucun email frauduleux n'est bloqué ou mis en quarantaine)."
                    ),
                }
            )

    spf_or_dmarc_missing = any(i["type"] in {"spf_missing", "dmarc_missing"} for i in issues)
    both_missing = {"spf_missing", "dmarc_missing"} <= {i["type"] for i in issues}

    if both_missing:
        status = CheckResult.Status.CRITICAL
    elif issues:
        status = CheckResult.Status.WARNING
    else:
        status = CheckResult.Status.OK

    # spf_or_dmarc_missing kept in details for callers/tests that want the
    # coarse signal without re-deriving it from `issues`.
    details["spf_or_dmarc_missing"] = spf_or_dmarc_missing

    return {"status": status, "details": {"issues": issues, **details}}

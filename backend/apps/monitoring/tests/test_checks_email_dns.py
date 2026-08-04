from unittest.mock import patch

import dns.resolver

from apps.monitoring.checks.email_dns import check_email_dns
from apps.monitoring.models import CheckResult


class FakeAnswer:
    def __init__(self, text):
        self.strings = [text.encode()]


def _resolver(*, spf=None, dmarc=None):
    def fake_resolve(qname, rdtype, lifetime=None):
        if qname == "_dmarc.example.com":
            if dmarc is None:
                raise dns.resolver.NXDOMAIN()
            return [FakeAnswer(dmarc)]
        if qname == "example.com":
            if spf is None:
                raise dns.resolver.NoAnswer()
            return [FakeAnswer(spf)]
        raise dns.resolver.NXDOMAIN()

    return fake_resolve


class TestCheckEmailDns:
    def test_ok_with_spf_and_enforcing_dmarc(self):
        resolve = _resolver(spf="v=spf1 include:_spf.example.com -all", dmarc="v=DMARC1; p=reject;")
        with patch("dns.resolver.resolve", side_effect=resolve):
            result = check_email_dns("example.com")

        assert result["status"] == CheckResult.Status.OK
        assert result["details"]["issues"] == []
        assert result["details"]["dmarc_policy"] == "reject"

    def test_critical_when_both_spf_and_dmarc_missing(self):
        resolve = _resolver(spf=None, dmarc=None)
        with patch("dns.resolver.resolve", side_effect=resolve):
            result = check_email_dns("example.com")

        assert result["status"] == CheckResult.Status.CRITICAL
        issue_types = {i["type"] for i in result["details"]["issues"]}
        assert issue_types == {"spf_missing", "dmarc_missing"}

    def test_warning_when_only_dmarc_missing(self):
        resolve = _resolver(spf="v=spf1 -all", dmarc=None)
        with patch("dns.resolver.resolve", side_effect=resolve):
            result = check_email_dns("example.com")

        assert result["status"] == CheckResult.Status.WARNING
        issue_types = {i["type"] for i in result["details"]["issues"]}
        assert issue_types == {"dmarc_missing"}

    def test_warning_when_dmarc_policy_is_none(self):
        resolve = _resolver(spf="v=spf1 -all", dmarc="v=DMARC1; p=none;")
        with patch("dns.resolver.resolve", side_effect=resolve):
            result = check_email_dns("example.com")

        assert result["status"] == CheckResult.Status.WARNING
        issue_types = {i["type"] for i in result["details"]["issues"]}
        assert "dmarc_policy_none" in issue_types

    def test_flags_multiple_spf_records(self):
        def fake_resolve(qname, rdtype, lifetime=None):
            if qname == "example.com":
                return [FakeAnswer("v=spf1 -all"), FakeAnswer("v=spf1 include:other.com -all")]
            raise dns.resolver.NXDOMAIN()

        with patch("dns.resolver.resolve", side_effect=fake_resolve):
            result = check_email_dns("example.com")

        issue_types = {i["type"] for i in result["details"]["issues"]}
        assert "spf_multiple" in issue_types

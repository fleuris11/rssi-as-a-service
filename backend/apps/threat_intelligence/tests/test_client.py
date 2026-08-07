from unittest.mock import Mock, patch

import pytest
import requests

from apps.threat_intelligence.providers.breachsense.client import (
    MAX_PAGINATION_PAGES,
    BreachsenseAuthError,
    BreachsenseBadRequestError,
    BreachsenseClient,
    BreachsenseForbiddenError,
    BreachsenseNetworkError,
    BreachsenseServerError,
    BreachsenseValidationError,
)


class _NoopThrottle:
    """Client tests exercise pagination/error-handling logic, not the
    Redis-backed throttle (covered by test_throttle.py) — a no-op keeps
    them fast and independent of real Redis timing."""

    def acquire(self, *, timeout=30):
        return None


def _client(session=None):
    return BreachsenseClient(
        license_key="test-lic-key",
        base_url="https://api.breachsense.test",
        throttle=_NoopThrottle(),
        session=session or Mock(),
    )


def _response(status_code, body=None, text=""):
    response = Mock(status_code=status_code, text=text or "")
    response.content = b"1" if body is not None else b""
    response.json.return_value = body
    return response


class TestAuthHeader:
    def test_sends_license_key_in_lic_header(self):
        session = Mock()
        session.request.return_value = _response(200, [])
        client = _client(session)

        client.stealer(domain="example.com")

        _args, kwargs = session.request.call_args
        assert kwargs["headers"]["lic"] == "test-lic-key"


class TestPagination:
    def test_single_200_page_stops_immediately(self):
        session = Mock()
        session.request.return_value = _response(200, [{"a": 1}])
        client = _client(session)

        items, requests_consumed = client.stealer(domain="example.com")

        assert items == [{"a": 1}]
        assert requests_consumed == 1
        assert session.request.call_count == 1

    def test_206_pages_are_followed_until_200(self):
        session = Mock()
        session.request.side_effect = [
            _response(206, [{"a": 1}]),
            _response(206, [{"a": 2}]),
            _response(200, [{"a": 3}]),
        ]
        client = _client(session)

        items, requests_consumed = client.stealer(domain="example.com")

        assert items == [{"a": 1}, {"a": 2}, {"a": 3}]
        assert requests_consumed == 3

    def test_pagination_follows_p_query_param(self):
        session = Mock()
        session.request.side_effect = [
            _response(206, [{"a": 1}]),
            _response(200, [{"a": 2}]),
        ]
        client = _client(session)

        client.stealer(domain="example.com")

        pages_requested = [call.kwargs["params"]["p"] for call in session.request.call_args_list]
        assert pages_requested == [1, 2]

    def test_pagination_stops_at_safety_cap(self):
        session = Mock()
        session.request.return_value = _response(206, [{"a": 1}])
        client = _client(session)

        _items, requests_consumed = client.stealer(domain="example.com")

        assert requests_consumed == MAX_PAGINATION_PAGES

    def test_dict_envelope_with_results_key_is_supported(self):
        session = Mock()
        session.request.return_value = _response(200, {"results": [{"a": 1}, {"a": 2}]})
        client = _client(session)

        items, _consumed = client.stealer(domain="example.com")

        assert items == [{"a": 1}, {"a": 2}]


class TestErrorHandling:
    @pytest.mark.parametrize(
        "status_code,error_cls",
        [
            (400, BreachsenseBadRequestError),
            (401, BreachsenseAuthError),
            (403, BreachsenseForbiddenError),
            (422, BreachsenseValidationError),
        ],
    )
    def test_non_retryable_status_raises_immediately(self, status_code, error_cls):
        session = Mock()
        session.request.return_value = _response(status_code, text="erreur")
        client = _client(session)

        with pytest.raises(error_cls):
            client.stealer(domain="example.com")

        assert session.request.call_count == 1

    def test_500_is_retried_then_raises_after_max_retries(self):
        session = Mock()
        session.request.return_value = _response(500, text="boom")
        client = _client(session)

        with (
            patch("apps.threat_intelligence.providers.breachsense.client.time.sleep"),
            pytest.raises(BreachsenseServerError),
        ):
            client.stealer(domain="example.com")

        assert session.request.call_count == 1 + 3  # MAX_RETRIES

    def test_500_then_200_succeeds_after_retry(self):
        session = Mock()
        session.request.side_effect = [_response(500, text="boom"), _response(200, [{"a": 1}])]
        client = _client(session)

        with patch("apps.threat_intelligence.providers.breachsense.client.time.sleep"):
            items, _consumed = client.stealer(domain="example.com")

        assert items == [{"a": 1}]

    def test_429_is_retried_like_500(self):
        session = Mock()
        session.request.side_effect = [_response(429, text="slow down"), _response(200, [])]
        client = _client(session)

        with patch("apps.threat_intelligence.providers.breachsense.client.time.sleep"):
            client.stealer(domain="example.com")

        assert session.request.call_count == 2

    def test_network_error_is_retried_then_raises(self):
        session = Mock()
        session.request.side_effect = requests.ConnectionError("refused")
        client = _client(session)

        with (
            patch("apps.threat_intelligence.providers.breachsense.client.time.sleep"),
            pytest.raises(BreachsenseNetworkError),
        ):
            client.stealer(domain="example.com")

        assert session.request.call_count == 1 + 3


class TestAccountEndpoints:
    def test_account_remaining_parses_response(self):
        session = Mock()
        session.request.return_value = _response(200, {"remaining": 42})
        client = _client(session)

        result = client.account_remaining()

        assert result["remaining"] == 42
        params = session.request.call_args.kwargs["params"]
        assert params["action"] == "remaining"

    def test_account_add_sends_asset_and_type(self):
        session = Mock()
        session.request.return_value = _response(200, {"ref": "abc"})
        client = _client(session)

        client.account_add(
            asset="example.com", asset_type="domain", webhook_url="https://x/webhook"
        )

        params = session.request.call_args.kwargs["params"]
        assert params == {
            "action": "add",
            "asset": "example.com",
            "type": "domain",
            "webhook": "https://x/webhook",
        }

    def test_account_creds_formats_username_password(self):
        session = Mock()
        session.request.return_value = _response(200, {})
        client = _client(session)

        client.account_creds(username="wh_user", password="wh_pass")

        params = session.request.call_args.kwargs["params"]
        assert params["creds"] == "wh_user:wh_pass"

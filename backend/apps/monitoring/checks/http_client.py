"""SSRF-safe GET: validates every hop of a redirect chain, not just the
first URL — ``requests``' own ``allow_redirects=True`` would otherwise
happily follow a 302 straight to an internal address."""

from urllib.parse import urljoin

import requests

from .ssrf import SSRFError, validate_url

DEFAULT_TIMEOUT_SECONDS = 10
MAX_REDIRECTS = 5


class CheckNetworkError(Exception):
    """A check couldn't complete because of a network-level failure
    (timeout, connection refused, DNS...) — distinct from SSRFError, which
    means the request was refused on purpose."""


def safe_get(url: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> requests.Response:
    """GETs ``url``, validating SSRF safety on every redirect hop, and
    returns the final response. Raises SSRFError or CheckNetworkError."""
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        validate_url(current_url)
        try:
            response = requests.get(current_url, timeout=timeout, allow_redirects=False)
        except requests.RequestException as exc:
            raise CheckNetworkError(str(exc)) from exc

        if response.is_redirect:
            location = response.headers.get("Location")
            if not location:
                return response
            current_url = urljoin(current_url, location)
            continue

        return response

    raise CheckNetworkError(f"Trop de redirections (> {MAX_REDIRECTS}) depuis {url!r}.")


__all__ = ["CheckNetworkError", "SSRFError", "safe_get"]

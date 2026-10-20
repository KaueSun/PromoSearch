"""Bounded API requests; credentials never follow redirects and errors contain no URLs."""

import json
import math
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .domain import clean_url


class ApiError(RuntimeError):
    def __init__(self, code="network", *, ambiguous=False):
        super().__init__(f"Falha API ({code})")
        self.code, self.ambiguous = code, ambiguous


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, opener=None, sleep=time.sleep):
        self.opener = opener or build_opener(NoRedirect())
        self.sleep = sleep

    def request(self, url, *, method="GET", headers=None, body=None):
        clean_url(url, {"api.mercadolibre.com", "discord.com"})
        h = {"Accept": "application/json", "User-Agent": "PromoSearch/0.2"}
        h.update(headers or {})
        for attempt in range(3):
            req = Request(url, data=body, headers=h, method=method)
            try:
                with self.opener.open(req, timeout=20) as response:
                    payload = response.read(2_000_001)
                    if len(payload) > 2_000_000:
                        raise ApiError("response_size", ambiguous=method == "POST")
                    try:
                        return json.loads(payload) if payload else {}
                    except (ValueError, UnicodeError):
                        raise ApiError("invalid_json", ambiguous=method == "POST") from None
            except HTTPError as exc:
                # POST is only retried on explicit 429 rejection, never on 5xx/timeouts.
                retryable = exc.code == 429 or (method == "GET" and exc.code >= 500)
                try:
                    delay = float(exc.headers.get("Retry-After", 2**attempt))
                except (ValueError, TypeError):
                    delay = 2**attempt
                if retryable and attempt < 2 and math.isfinite(delay) and 0 <= delay <= 60:
                    self.sleep(max(1, delay))
                    continue
                raise ApiError(str(exc.code), ambiguous=method == "POST" and exc.code >= 500) from None
            except (URLError, TimeoutError, OSError):
                if method == "GET" and attempt < 2:
                    self.sleep(2**attempt)
                    continue
                raise ApiError(ambiguous=method == "POST") from None
        raise ApiError("retry_exhausted")

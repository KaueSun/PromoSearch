import json
from dataclasses import replace
from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest
import sqlalchemy as sa
from conftest import NOW
from cryptography.fernet import Fernet

from radar_gamer.analysis import assess
from radar_gamer.discord import embed, send, webhook_url
from radar_gamer.domain import digest
from radar_gamer.http import ApiError, Client
from radar_gamer.meli import Meli, approved_metadata
from radar_gamer.oauth import OAuth
from radar_gamer.service import monitor
from radar_gamer.storage import alerts, runs, tokens


class FakeClient:
    """Synthetic official-API-shaped responses. Never queries retail or sends Discord messages."""

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        result = self.replies.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def details():
    return {
        "id": "MLB1234567",
        "site_id": "MLB",
        "title": "Notebook TESTE",
        "seller_id": 123,
        "condition": "new",
        "status": "active",
        "variations": [],
        "attributes": [
            {"id": key, "value_name": value}
            for key, value in [
                ("BRAND", "Acer"),
                ("MODEL", "TEST-ONLY-ANV15"),
                ("CPU", "Intel Core i5-13420H"),
                ("GPU", "RTX 4050"),
                ("RAM", "16 GB"),
                ("SSD", "512 GB"),
            ]
        ],
        "permalink": "https://produto.mercadolivre.com.br/MLB-1234567-teste",
        "secure_thumbnail": "https://http2.mlstatic.com/test.jpg",
    }


def test_meli_real_contract_fixture(details, product):
    client = FakeClient(
        [
            details,
            {"currency_id": "BRL", "amount": 3999.99, "regular_amount": 9999},
            {"seller_reputation": {"level_id": "5_green"}},
        ]
    )
    api = Meli(client, "TEST_TOKEN", {"123"})
    offer = api.fetch({"listing": "MLB1234567", "signature": digest(approved_metadata(details))}, product)
    assert offer.price == 399999 and offer.shipping is None
    assert offer.verified and offer.trusted and offer.product_id == product.identity
    assert "regular_price" not in offer.__dict__
    assert client.calls[1][0].endswith("sale_price?context=channel_marketplace")


def test_changed_attributes_block(details, product):
    original = digest(approved_metadata(details))
    details["attributes"][-1]["value_name"] = "256 GB"
    with pytest.raises(ValueError, match="Metadados alterados"):
        Meli(FakeClient([details]), "TEST", {"123"}).fetch(
            {"listing": "MLB1234567", "signature": original}, product
        )


def test_variations_block(details):
    details["variations"] = [{"id": 1}]
    with pytest.raises(ValueError):
        approved_metadata(details)


def test_wrong_currency_block(details, product):
    api = Meli(FakeClient([details, {"currency_id": "USD", "amount": 1000}]), "TEST", {"123"})
    with pytest.raises(ValueError, match="BRL"):
        api.fetch({"listing": "MLB1234567", "signature": digest(approved_metadata(details))}, product)


def test_oauth_rotation_is_encrypted_and_reused(store, monkeypatch):
    key = Fernet.generate_key()
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", key.decode())
    monkeypatch.setenv("MELI_CLIENT_ID", "test-client")
    monkeypatch.setenv("MELI_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("MELI_REFRESH_TOKEN", "old-test-refresh")
    client = FakeClient(
        [{"access_token": "test-access", "refresh_token": "rotated-test-refresh", "expires_in": 21600}]
    )
    oauth = OAuth(store, client)
    assert oauth.access_token() == "test-access"
    assert oauth.access_token() == "test-access" and len(client.calls) == 1
    encrypted = store.rows(sa.select(tokens))[0]["ciphertext"]
    assert "test-access" not in encrypted and "refresh" not in encrypted
    decoded = json.loads(Fernet(key).decrypt(encrypted))
    assert decoded["refresh_token"] == "rotated-test-refresh"


def test_failed_rotation_never_reuses_single_use_token(store, monkeypatch):
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    for key in ("MELI_CLIENT_ID", "MELI_CLIENT_SECRET", "MELI_REFRESH_TOKEN"):
        monkeypatch.setenv(key, "test-value")
    client = FakeClient([ApiError(ambiguous=True)])
    oauth = OAuth(store, client)
    with pytest.raises(ApiError):
        oauth.access_token()
    with pytest.raises(ValueError, match="interrompida"):
        oauth.access_token()
    assert len(client.calls) == 1


def test_embeds_and_mentions(store, offer, product, rules):
    for days in (1, 2, 3, 4, 5, 6, 7):
        store.observe(replace(offer, price=500000), product, NOW - days * 86400, True)
    review = assess(store, offer, rules, NOW)
    payload = embed(offer, product, review, NOW)
    assert payload["allowed_mentions"] == {"parse": []}
    assert payload["embeds"][0]["color"] == 0x22C55E
    assert "2026-10-20" in payload["embeds"][0]["timestamp"]
    fields = payload["embeds"][0]["fields"]
    assert all(len(f["value"]) <= 1024 for f in fields)
    assert "RTX 4050" in fields[0]["value"]
    assert (
        send(FakeClient([{"id": "12345"}]), "https://discord.com/api/webhooks/123/test", payload) == "12345"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://discord.com.evil.test/api/webhooks/123/x",
        "https://u:p@discord.com/api/webhooks/123/x",
        "https://discord.com/api/webhooks/123/x?wait=false",
    ],
)
def test_webhook_validation(url):
    with pytest.raises(ValueError):
        webhook_url(url)


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, limit):
        return self.payload


class Opener:
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    def open(self, *args, **kwargs):
        self.calls += 1
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def http_error(status, retry="1"):
    return HTTPError(
        "https://discord.com/secret-not-for-logs", status, "test", {"Retry-After": retry}, BytesIO()
    )


def test_get_transient_retry():
    op = Opener([http_error(503), URLError("secret"), Response(b'{"ok":true}')])
    waits = []
    assert Client(op, waits.append).request("https://api.mercadolibre.com/items/MLB1234567") == {"ok": True}
    assert op.calls == 3 and waits == [1, 2]


def test_post_timeout_not_retried_or_leaked():
    op = Opener([URLError("SECRET_URL")])
    with pytest.raises(ApiError) as error:
        Client(op, lambda _: None).request(
            "https://discord.com/api/webhooks/123/test", method="POST", body=b"{}"
        )
    assert error.value.ambiguous and "SECRET" not in str(error.value) and op.calls == 1


def test_429_honors_retry_after():
    op = Opener([http_error(429, "3"), Response(b'{"id":"123"}')])
    waits = []
    Client(op, waits.append).request("https://discord.com/api/webhooks/123/test", method="POST", body=b"{}")
    assert waits == [3] and op.calls == 2


def test_large_retry_after_stops():
    with pytest.raises(ApiError):
        Client(Opener([http_error(429, "300")]), lambda _: pytest.fail("No waiting")).request(
            "https://api.mercadolibre.com/items/MLB1234567"
        )


class OffersAPI:
    def __init__(self, offer):
        self.offer = offer

    def fetch(self, watch, product):
        if watch["listing"] == "MLB9999999":
            raise ApiError("403")
        return self.offer


def test_full_job_partial_failure_persists_and_deduplicates(store, offer, product, rules, monkeypatch):
    from radar_gamer import service

    monkeypatch.setattr(service, "timestamp", lambda: NOW)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/123/test")
    for days in range(1, 8):
        store.observe(replace(offer, price=500000), product, NOW - days * 86400, True)
    store.watch("MLB1234567", "sku", "a" * 64)
    store.watch("MLB9999999", "sku", "a" * 64)
    client = FakeClient([{"id": "111111"}])
    assert monitor(store, client, {"sku": product}, {"123"}, rules, sending=True, api=OffersAPI(offer)) == 1
    assert monitor(store, client, {"sku": product}, {"123"}, rules, sending=True, api=OffersAPI(offer)) == 1
    assert len(client.calls) == 1
    assert store.rows(sa.select(alerts))[0]["state"] == "sent"
    assert all(r["state"] == "partial" for r in store.rows(sa.select(runs)))


def test_uncertain_delivery_blocks_retries(store, offer, product, rules, monkeypatch):
    from radar_gamer import service

    monkeypatch.setattr(service, "timestamp", lambda: NOW)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/123/test")
    for days in range(1, 8):
        store.observe(replace(offer, price=500000), product, NOW - days * 86400, True)
    store.watch("MLB1234567", "sku", "a" * 64)
    client = FakeClient([ApiError(ambiguous=True)])
    assert monitor(store, client, {"sku": product}, {"123"}, rules, sending=True, api=OffersAPI(offer)) == 1
    monitor(store, client, {"sku": product}, {"123"}, rules, sending=True, api=OffersAPI(offer))
    assert len(client.calls) == 1
    assert store.rows(sa.select(alerts))[0]["state"] == "uncertain"

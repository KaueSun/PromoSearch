from dataclasses import replace

import pytest
import sqlalchemy as sa
from conftest import NOW

from radar_gamer.storage import alerts, observations, tokens, watches


def storage_contract(store, offer, product, rules):
    store.observe(offer, product, NOW - 86400, True)
    store.observe(offer, product, NOW - 86400, True)
    assert len(store.rows(sa.select(observations))) == 1
    assert store.history(offer, NOW)[0]["price"] == 400000
    with store.lease(NOW):
        with pytest.raises(ValueError):
            with store.lease(NOW + 1):
                pass
        ident = store.reserve(offer, NOW, rules)
        assert ident
        assert store.reserve(replace(offer, price=300000), NOW + 7200, rules) is None
        store.finish_alert(ident, "sent", "123456")
        assert store.reserve(offer, NOW + 86400, rules) is None
        assert store.reserve(replace(offer, price=390000), NOW + 86400, rules) is None
        second = store.reserve(replace(offer, price=375000), NOW + 86400, rules)
        assert second
        store.finish_alert(second, "uncertain")
    store.cleanup(100, NOW + 200 * 86400)
    assert len(store.rows(sa.select(observations))) == 0
    assert len(store.rows(sa.select(alerts))) == 2
    store.watch("MLB1234567", "exact", "a" * 64)
    assert len(store.rows(sa.select(watches))) == 1
    store.upsert(tokens, tokens.c.provider == "meli", {"provider": "meli", "ciphertext": "encrypted"})
    assert store.rows(sa.select(tokens))[0]["ciphertext"] == "encrypted"


def test_sqlite_storage_contract(store, offer, product, rules):
    storage_contract(store, offer, product, rules)


@pytest.mark.postgres
def test_real_postgresql_contract(pg_store, offer, product, rules):
    storage_contract(pg_store, offer, product, rules)


def test_old_history_does_not_delete_alert_dedup(store, offer, rules):
    ident = store.reserve(offer, NOW, rules)
    store.finish_alert(ident, "sent")
    store.cleanup(100, NOW + 1000 * 86400)
    assert store.reserve(offer, NOW + 1000 * 86400, rules) is None


def test_changed_shipping_basis_does_not_realert(store, offer, rules):
    ident = store.reserve(offer, NOW, rules)
    store.finish_alert(ident, "sent")
    assert store.reserve(replace(offer, price=300000, shipping=None), NOW + 86400, rules) is None


@pytest.mark.postgres
def test_postgres_competitors_json_and_condition(pg_store, offer, product, rules):
    from radar_gamer.analysis import assess

    for key in ("B", "C"):
        pg_store.observe(replace(offer, listing=key, seller=key, price=500000), product, NOW - 1, True)
    assert assess(pg_store, offer, rules, NOW).worthy
    assert not assess(pg_store, replace(offer, condition="used"), rules, NOW).worthy


def test_production_rejects_sqlite_and_insecure_tls():
    from radar_gamer.storage import Store

    with pytest.raises(ValueError):
        Store("sqlite:///:memory:")
    with pytest.raises(ValueError):
        Store("postgresql://example:example@localhost/postgres?sslmode=disable")

from dataclasses import replace

import pytest
from conftest import NOW

from radar_gamer.analysis import assess, drop
from radar_gamer.config import Rules
from radar_gamer.domain import clean_url, item_id, money


def history(store, offer, product, days=7, price=500000):
    for day in range(1, days + 1):
        store.observe(replace(offer, price=price), product, NOW - day * 86400, True)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "-1", "0", "1000.001", True, None])
def test_invalid_money(value):
    with pytest.raises(ValueError):
        money(value)


def test_centavos():
    assert money("3999.99") == 399999
    assert money(0, zero=True) == 0
    assert drop(500000, 400000) == 20


@pytest.mark.parametrize(
    "url",
    [
        "http://amazon.com.br/p",
        "https://localhost/x",
        "https://127.0.0.1/x",
        "https://user:pass@discord.com/x",
        "https://amazon.com.br:444/x",
        "https://amazon.com.br/x\n",
        "https://[::1]/x",
        "file:///tmp/a",
    ],
)
def test_unsafe_links(url):
    with pytest.raises(ValueError):
        clean_url(url)


def test_meli_link_extract():
    assert item_id("https://produto.mercadolivre.com.br/MLB-1234567-notebook") == "MLB1234567"
    with pytest.raises(ValueError):
        item_id("https://mercadolivre.com.br.evil.test/MLB-1234567-x")


def test_exact_configuration(product):
    for replacement in [
        dict(cpu="Intel Core i5-12450H"),
        dict(gpu="RTX 2050"),
        dict(ram_gb=8),
        dict(ssd_gb=1024),
        dict(manufacturer_code="OTHER-SKU"),
        dict(display="FHD 60 Hz"),
    ]:
        assert replace(product, **replacement).identity != product.identity
    with pytest.raises(ValueError):
        replace(product, cpu="Core i5")


def test_no_history_no_discount(store, offer, rules):
    r = assess(store, offer, rules, NOW)
    assert not r.worthy and r.best_reference is None
    assert all(v["median"] is None for v in r.references.values())


def test_7_30_90_day_history(store, offer, product, rules):
    history(store, offer, product, days=90)
    result = assess(store, offer, rules, NOW)
    assert result.worthy and result.best_pct == 20 and result.tier == "Excelente"
    assert result.references["7"]["days"] == 7
    assert result.references["30"]["days"] == 30
    assert result.references["90"]["days"] == 90
    assert result.historical_low == 500000


def test_recent_three_days(store, offer, product, rules):
    history(store, offer, product, days=3, price=450000)
    r = assess(store, offer, rules, NOW)
    assert r.worthy and r.tier == "Queda moderada"
    assert r.references["7"]["median"] is None


def test_many_same_day_samples_not_mature(store, offer, product, rules):
    for interval in range(1, 25):
        store.observe(replace(offer, price=500000), product, NOW - interval * 1800, True)
    assert not assess(store, offer, rules, NOW).worthy


def test_history_different_configuration_excluded(store, offer, product, rules):
    history(store, offer, product)
    other = replace(product, gpu="RTX 2050")
    assert not assess(store, replace(offer, product_id=other.identity), rules, NOW).worthy


def test_two_distinct_sellers(store, offer, product, rules):
    for key in ("B", "C"):
        store.observe(replace(offer, listing=key, seller=key, price=500000), product, NOW - 1, True)
    assert assess(store, offer, rules, NOW).worthy
    assert not assess(store, replace(offer, shipping=None), rules, NOW).worthy


def test_one_seller_many_listings_not_enough(store, offer, product, rules):
    for key in ("B", "C", "D"):
        store.observe(replace(offer, listing=key, seller="one", price=500000), product, NOW - 1, True)
    assert not assess(store, offer, rules, NOW).worthy


@pytest.mark.parametrize(
    "change",
    [
        dict(condition="used"),
        dict(available=False),
        dict(trusted=False),
        dict(verified=False),
        dict(source="manual_unverified"),
        dict(price=10000),
    ],
)
def test_quality_gate(store, offer, product, rules, change):
    history(store, offer, product)
    review = assess(store, replace(offer, **change), rules, NOW)
    assert not review.worthy and not review.usable


def test_suspicious_crash(store, offer, product, rules):
    history(store, offer, product, price=1000000)
    assert not assess(store, replace(offer, price=300000), rules, NOW).usable


def test_unknown_shipping_history_only(store, offer, product, rules):
    offer = replace(offer, shipping=None)
    history(store, offer, product)
    result = assess(store, offer, rules, NOW)
    assert result.worthy and "Frete desconhecido" in result.limitations[0]
    assert not assess(store, replace(offer, shipping=0), rules, NOW).worthy


def test_stale_and_unavailable_competitor_not_resurrected(store, offer, product, rules):
    for key in ("B", "C"):
        other = replace(offer, listing=key, seller=key, price=500000)
        store.observe(other, product, NOW - 3600, True)
        store.observe(replace(other, available=False), product, NOW - 1, False)
    assert not assess(store, offer, rules, NOW).worthy


def test_invalid_rules():
    with pytest.raises(ValueError):
        Rules(recent_drop_pct=float("nan"))
    with pytest.raises(ValueError):
        Rules(retention_days=30)

import json
from dataclasses import asdict, replace

import pytest
import sqlalchemy as sa
from conftest import NOW

from radar_gamer import cli
from radar_gamer.analysis import compare_manual
from radar_gamer.config import load
from radar_gamer.storage import alerts, manual, observations


def test_manual_comparison_never_contaminates_or_sends(store, offer, product, rules):
    for day in range(1, 8):
        store.observe(replace(offer, price=500000), product, NOW - day * 86400, True)
    report = compare_manual(store, product, {"price": 400000, "shipping": 0}, NOW, rules)
    assert report["source"] == "manual_unverified"
    assert report["references"]["7"]["provisional_drop_pct"] == 20
    assert report["alert_sent"] is False
    assert len(store.rows(sa.select(observations))) == 7
    assert store.rows(sa.select(alerts)) == []


def test_manual_insufficient_history_returns_null(store, product, rules):
    result = compare_manual(store, product, {"price": 400000, "shipping": None}, NOW, rules)
    assert result["references"]["7"]["provisional_drop_pct"] is None


def setup_cli(monkeypatch, tmp_path, product, store):
    config = tmp_path / "catalog.json"
    config.write_text(
        json.dumps({"products": {"sku": asdict(product)}, "trusted_meli_sellers": ["123"]}), encoding="utf-8"
    )

    class SharedStore:
        def __getattr__(self, name):
            return getattr(store, name)

        def close(self):
            pass

    monkeypatch.setattr(cli, "Store", lambda _: SharedStore())
    monkeypatch.setattr(cli, "timestamp", lambda: NOW)
    return config


def test_cli_manual_end_to_end(monkeypatch, tmp_path, product, store, capsys):
    config = setup_cli(monkeypatch, tmp_path, product, store)
    file = tmp_path / "manual.json"
    file.write_text(
        json.dumps(
            [{"sku": "sku", "url": "https://www.amazon.com.br/dp/TEST", "price": 3999.99, "shipping": None}]
        ),
        encoding="utf-8",
    )
    assert cli.execute(cli.parser().parse_args(["--config", str(config), "manual", str(file)])) == 0
    assert store.rows(sa.select(manual))[0]["data"]["source"] == "manual_unverified"
    assert not store.rows(sa.select(observations)) and not store.rows(sa.select(alerts))
    assert "manual_unverified" in capsys.readouterr().out


def test_schedule_with_empty_inputs(monkeypatch, tmp_path, product, store):
    config = setup_cli(monkeypatch, tmp_path, product, store)
    monkeypatch.setenv("INPUT_ACTION", "")
    assert cli.execute(cli.parser().parse_args(["--config", str(config), "cloud-input"])) == 0


def test_cli_errors_do_not_print_database_credentials(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["radar", "check"])

    def failing(_):
        raise sa.exc.OperationalError("SECRET_STATEMENT", {}, Exception("SECRET_PASSWORD"))

    monkeypatch.setattr(cli, "execute", failing)
    assert cli.main() == 1
    output = capsys.readouterr()
    assert "SECRET" not in output.out + output.err


def test_load_rejects_generic_cpu(tmp_path, product):
    data = {"products": {"sku": dict(asdict(product), cpu="Core i5")}, "trusted_meli_sellers": []}
    file = tmp_path / "catalog.json"
    file.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load(file)

import argparse
import json
import os
import re
import sys
from dataclasses import asdict
from pathlib import Path

import sqlalchemy as sa
from cryptography.fernet import Fernet

from .analysis import compare_manual
from .config import load
from .domain import clean_url, digest, item_id, money
from .http import ApiError, Client
from .meli import Meli, approved_metadata, valid_signature
from .oauth import OAuth
from .service import event, monitor
from .storage import Store, alerts, manual, runs, timestamp, tokens, watches


def parser():
    p = argparse.ArgumentParser(description="PromoSearch / Radar Gamer — APIs oficiais e PostgreSQL")
    p.add_argument("--config", default="config/catalog.json")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    sub.add_parser("keygen")
    sub.add_parser("status")
    sub.add_parser("cleanup")
    sub.add_parser("oauth-reset")
    sub.add_parser("check").add_argument("--send", action="store_true")
    sub.add_parser("inspect").add_argument("url")
    watch = sub.add_parser("watch")
    watch.add_argument("url")
    watch.add_argument("--sku", required=True)
    watch.add_argument("--signature", required=True)
    sub.add_parser("unwatch").add_argument("url")
    sub.add_parser("manual").add_argument("file")
    resolve = sub.add_parser("resolve-alert")
    resolve.add_argument("id")
    resolve.add_argument("--state", choices=["sent", "failed"], required=True)
    sub.add_parser("cloud-input")
    return p


def execute(args):
    if args.command == "keygen":
        print(Fernet.generate_key().decode())
        return 0
    products, sellers, rules = load(args.config)
    store = Store(os.getenv("DATABASE_URL", ""))
    client = Client()
    try:
        if args.command == "init-db":
            store.init()
            event("schema_ready", version=1)
            return 0
        if args.command == "check":
            return monitor(store, client, products, sellers, rules, sending=args.send)
        with store.lease():
            if args.command == "cloud-input":
                value = os.getenv("INPUT_URL", "")
                action = os.getenv("INPUT_ACTION") or "check"
                if action == "watch":
                    args.command, args.url = "watch", value
                    args.sku, args.signature = os.getenv("INPUT_SKU", ""), os.getenv("INPUT_SIGNATURE", "")
                elif action == "unwatch":
                    args.command, args.url = "unwatch", value
                elif action != "check":
                    raise ValueError("Ação inválida")
                else:
                    return 0
            if args.command in {"watch", "inspect"}:
                api = Meli(client, OAuth(store, client).access_token(), sellers)
                ident, data, signature = api.inspect(args.url)
                if args.command == "inspect":
                    # An explicit operator command; never invoked automatically in public Actions logs.
                    print(
                        json.dumps(
                            {"item_id": ident, "signature": signature, "review": approved_metadata(data)},
                            ensure_ascii=False,
                            indent=2,
                        )
                    )
                else:
                    if args.sku not in products or valid_signature(args.signature) != signature:
                        raise ValueError("SKU desconhecido ou assinatura diferente da revisão")
                    if str(data["seller_id"]) not in sellers:
                        raise ValueError("Inclua o vendedor revisado em trusted_meli_sellers")
                    existing = store.rows(sa.select(watches).where(watches.c.enabled.is_(True)))
                    if len(existing) >= rules.max_watches and ident not in {r["listing"] for r in existing}:
                        raise ValueError("Limite de anúncios atingido")
                    store.watch(ident, args.sku, signature)
                    event("watch_saved")
            elif args.command == "unwatch":
                with store.engine.begin() as c:
                    c.execute(
                        watches.update().where(watches.c.listing == item_id(args.url)).values(enabled=False)
                    )
                event("watch_disabled")
            elif args.command == "manual":
                data = json.loads(Path(args.file).read_text(encoding="utf-8"))
                if not isinstance(data, list) or len(data) > 50:
                    raise ValueError("Importe uma lista de até 50 ofertas manuais")
                for entry in data:
                    if entry["sku"] not in products:
                        raise ValueError("SKU desconhecido")
                    url = clean_url(entry["url"])
                    # No URL is fetched and no manually typed price is trusted as an API observation.
                    sanitized = dict(
                        sku=entry["sku"],
                        url=url,
                        price=money(entry["price"]),
                        shipping=None
                        if entry.get("shipping") is None
                        else money(entry["shipping"], zero=True),
                        source="manual_unverified",
                        condition=entry.get("condition", "new"),
                        product=asdict(products[entry["sku"]]),
                    )
                    report = compare_manual(store, products[entry["sku"]], sanitized, timestamp(), rules)
                    store.upsert(
                        manual,
                        manual.c.id == digest(sanitized),
                        dict(id=digest(sanitized), at=timestamp(), data=sanitized),
                    )
                    print(json.dumps(report, ensure_ascii=False))
                event("manual_saved_unverified", count=len(data))
            elif args.command == "resolve-alert":
                if not re.fullmatch(r"[0-9a-f]{32}", args.id):
                    raise ValueError("ID inválido")
                records = store.rows(sa.select(alerts).where(alerts.c.id == args.id))
                if not records or records[0]["state"] not in {"uncertain", "dispatching"}:
                    raise ValueError("Alerta não está pendente de reconciliação")
                store.finish_alert(args.id, args.state)
                event("alert_reconciled")
            elif args.command == "oauth-reset":
                if not os.getenv("MELI_REFRESH_TOKEN"):
                    raise ValueError("Configure o novo refresh token autorizado antes de resetar")
                with store.engine.begin() as c:
                    c.execute(tokens.delete().where(tokens.c.provider == "meli"))
                OAuth(store, client).access_token()
                event("oauth_reauthorized")
            elif args.command == "cleanup":
                store.cleanup(rules.retention_days, timestamp())
                event("cleanup_complete")
            elif args.command == "status":
                latest = store.rows(sa.select(runs).order_by(runs.c.at.desc()).limit(1))
                unresolved = store.rows(
                    sa.select(alerts.c.id, alerts.c.state).where(
                        alerts.c.state.in_(["uncertain", "dispatching"])
                    )
                )
                count = len(store.rows(sa.select(watches.c.listing).where(watches.c.enabled.is_(True))))
                size = store.rows(
                    sa.select(sa.func.pg_database_size(sa.func.current_database()).label("bytes"))
                )
                print(
                    json.dumps(
                        {
                            "active_watches": count,
                            "latest_run": latest,
                            "unresolved_alerts": unresolved,
                            "database_bytes": size[0]["bytes"],
                        }
                    )
                )
                if size[0]["bytes"] >= 350_000_000:
                    event("database_near_free_limit")
        return 0
    finally:
        store.close()


def main():
    args = parser().parse_args()
    try:
        return execute(args)
    except (ValueError, KeyError, TypeError, ApiError, OSError, sa.exc.SQLAlchemyError) as error:
        # Exceptions may embed a secret URL or a DB password. Emit only a stable error category.
        event("command_failed", category=type(error).__name__)
        if type(error) is ValueError:
            print(str(error), file=sys.stderr)
        print(
            "Falha: confira configuração, autorização das APIs e conectividade. Consulte docs/OPERACAO.md.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""Bounded scheduled job, durable delivery states and sanitized operational events."""

import json
import os
import time
import uuid

import sqlalchemy as sa

from .analysis import assess
from .discord import embed, send, webhook_url
from .http import ApiError
from .meli import Meli
from .oauth import OAuth
from .storage import listings, runs, timestamp, watches


def event(name, **counts):
    # Never log offer titles, URLs, API bodies, SQL errors, tokens or user-provided text.
    print(json.dumps({"event": name, **counts}, sort_keys=True))


def monitor(store, client, products, sellers, rules, *, sending=False, api=None):
    with store.lease():
        ident, started = uuid.uuid4().hex, timestamp()
        counts = dict(checked=0, errors=0, candidates=0, sent=0, uncertain=0)
        store.upsert(runs, runs.c.id == ident, dict(id=ident, at=started, state="running", counts=counts))
        state = "failed"
        try:
            tracked = store.rows(
                sa.select(watches).where(watches.c.enabled.is_(True)).order_by(watches.c.listing)
            )
            if not tracked:
                raise ValueError("Nenhum anúncio revisado cadastrado; monitoramento ainda não ativado")
            if len(tracked) > rules.max_watches:
                raise ValueError("Quantidade de anúncios excede o limite configurado")
            if sending:
                webhook_url(os.getenv("DISCORD_WEBHOOK_URL", ""))
            api = api or Meli(client, OAuth(store, client).access_token(), sellers)
            deadline = time.monotonic() + 780
            for watch in tracked:
                if time.monotonic() > deadline:
                    counts["errors"] += 1
                    break
                try:
                    product = products[watch["sku"]]
                    offer = api.fetch(watch, product)
                    now = timestamp()
                    review = assess(store, offer, rules, now)
                    store.observe(offer, product, now, review.usable)
                    counts["checked"] += 1
                    if not review.worthy:
                        continue
                    counts["candidates"] += 1
                    if not sending or counts["sent"] >= rules.max_alerts_per_run:
                        continue
                    reservation = store.reserve(offer, now, rules)
                    if not reservation:
                        continue
                    try:
                        message_id = send(
                            client, os.environ["DISCORD_WEBHOOK_URL"], embed(offer, product, review, now)
                        )
                    except ApiError as error:
                        store.finish_alert(reservation, "uncertain" if error.ambiguous else "failed")
                        counts["uncertain"] += int(error.ambiguous)
                        counts["errors"] += 1
                        # An invalid webhook must not be retried once per product.
                        if error.code in {"401", "403", "404", "429"}:
                            break
                    else:
                        store.finish_alert(reservation, "sent", message_id)
                        counts["sent"] += 1
                except (ApiError, ValueError, KeyError, TypeError):
                    counts["errors"] += 1
                    event("source_item_failed")
                    # An unavailable API must not leave a listing claiming fresh stock availability.
                    key = "meli:" + watch["listing"]
                    rows = store.rows(sa.select(listings).where(listings.c.id == key))
                    if rows:
                        data = rows[0]["data"]
                        data["available"] = False
                        store.upsert(
                            listings,
                            listings.c.id == key,
                            dict(
                                id=key,
                                product_id=rows[0]["product_id"],
                                seller=rows[0]["seller"],
                                data=data,
                                seen=rows[0]["seen"],
                            ),
                        )
            store.cleanup(rules.retention_days, timestamp())
            state = "partial" if counts["errors"] else "success"
            return 1 if counts["errors"] else 0
        finally:
            store.upsert(runs, runs.c.id == ident, dict(id=ident, at=started, state=state, counts=counts))
            event("monitor_finished", state=state, **counts)
            summary = os.getenv("GITHUB_STEP_SUMMARY")
            if summary:
                with open(summary, "a", encoding="utf-8") as handle:
                    handle.write(
                        f"### PromoSearch: {state}\n\n"
                        + " | ".join(f"{k}: {v}" for k, v in counts.items())
                        + "\n"
                    )

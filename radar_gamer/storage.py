"""Portable SQLAlchemy Core schema; PostgreSQL in production, SQLite only in tests."""

import uuid
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.pool import NullPool

meta = sa.MetaData()
version = sa.Table("schema_version", meta, sa.Column("version", sa.Integer, primary_key=True))
products = sa.Table(
    "products",
    meta,
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column("spec", sa.JSON, nullable=False),
)
watches = sa.Table(
    "watches",
    meta,
    sa.Column("listing", sa.String(60), primary_key=True),
    sa.Column("sku", sa.String(150), nullable=False),
    sa.Column("signature", sa.String(64), nullable=False),
    sa.Column("enabled", sa.Boolean, nullable=False, default=True),
)
listings = sa.Table(
    "listings",
    meta,
    sa.Column("id", sa.String(200), primary_key=True),
    sa.Column("product_id", sa.ForeignKey("products.id"), nullable=False),
    sa.Column("seller", sa.String(150), nullable=False),
    sa.Column("data", sa.JSON, nullable=False),
    sa.Column("seen", sa.BigInteger, nullable=False),
)
observations = sa.Table(
    "observations",
    meta,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("listing", sa.ForeignKey("listings.id"), nullable=False),
    sa.Column("product_id", sa.String(64), nullable=False),
    sa.Column("seller", sa.String(150), nullable=False),
    sa.Column("at", sa.BigInteger, nullable=False),
    sa.Column("bucket", sa.BigInteger, nullable=False),
    sa.Column("price", sa.Integer, nullable=False),
    sa.Column("shipping", sa.Integer),
    sa.Column("basis", sa.String(30), nullable=False),
    sa.Column("condition", sa.String(20), nullable=False),
    sa.Column("usable", sa.Boolean, nullable=False),
    sa.UniqueConstraint("listing", "bucket"),
)
sa.Index("ix_history", observations.c.listing, observations.c.at)
sa.Index("ix_equivalent", observations.c.product_id, observations.c.at)
alerts = sa.Table(
    "alerts",
    meta,
    sa.Column("id", sa.String(32), primary_key=True),
    sa.Column("listing", sa.String(200), nullable=False),
    sa.Column("product_id", sa.String(64), nullable=False),
    sa.Column("condition", sa.String(20), nullable=False),
    sa.Column("basis", sa.String(30), nullable=False),
    sa.Column("price", sa.Integer, nullable=False),
    sa.Column("at", sa.BigInteger, nullable=False),
    sa.Column("state", sa.String(30), nullable=False),
    sa.Column("message_id", sa.String(100)),
)
sa.Index("ix_alert_listing", alerts.c.listing, alerts.c.at)
leases = sa.Table(
    "leases",
    meta,
    sa.Column("name", sa.String(30), primary_key=True),
    sa.Column("owner", sa.String(32), nullable=False),
    sa.Column("until", sa.BigInteger, nullable=False),
)
tokens = sa.Table(
    "oauth_tokens",
    meta,
    sa.Column("provider", sa.String(30), primary_key=True),
    sa.Column("ciphertext", sa.Text, nullable=False),
)
runs = sa.Table(
    "runs",
    meta,
    sa.Column("id", sa.String(32), primary_key=True),
    sa.Column("at", sa.BigInteger, nullable=False),
    sa.Column("state", sa.String(30), nullable=False),
    sa.Column("counts", sa.JSON, nullable=False),
)
manual = sa.Table(
    "manual_submissions",
    meta,
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column("at", sa.BigInteger, nullable=False),
    sa.Column("data", sa.JSON, nullable=False),
)


def timestamp():
    return int(datetime.now(timezone.utc).timestamp())


class Store:
    def __init__(self, url: str, *, testing=False):
        if not testing and not url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("Produção exige DATABASE_URL PostgreSQL")
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        options = {}
        if url.startswith("postgresql+"):
            requested_tls = sa.engine.make_url(url).query.get("sslmode", "require")
            if not testing and requested_tls not in {"require", "verify-ca", "verify-full"}:
                raise ValueError("Produção exige TLS require, verify-ca ou verify-full")
            # Works with transaction poolers. Never print connection exceptions/DSNs.
            options = dict(
                connect_args={
                    "connect_timeout": 15,
                    "sslmode": "prefer" if testing else requested_tls,
                    "prepare_threshold": None,
                    "options": "-c statement_timeout=20000 -c lock_timeout=5000",
                },
                poolclass=NullPool,
            )
        self.engine = sa.create_engine(url, hide_parameters=True, **options)

    def init(self):
        meta.create_all(self.engine)
        with self.engine.begin() as c:
            versions = list(c.execute(sa.select(version.c.version)).scalars())
            if not versions:
                c.execute(version.insert().values(version=1))
            elif versions != [1]:
                raise ValueError("Versão de schema incompatível; faça backup e migre")
            if c.execute(sa.select(leases).where(leases.c.name == "monitor")).first() is None:
                c.execute(leases.insert().values(name="monitor", owner="", until=0))

    def rows(self, query):
        with self.engine.connect() as c:
            return [dict(r) for r in c.execute(query).mappings()]

    @contextmanager
    def lease(self, now=None):
        now = timestamp() if now is None else now
        owner = uuid.uuid4().hex
        with self.engine.begin() as c:
            result = c.execute(
                leases.update()
                .where(leases.c.name == "monitor", leases.c.until < now)
                .values(owner=owner, until=now + 1200)
            )
            if result.rowcount != 1:
                raise ValueError("Outra execução possui o bloqueio; tente mais tarde")
        try:
            yield
        finally:
            with self.engine.begin() as c:
                c.execute(
                    leases.update()
                    .where(leases.c.name == "monitor", leases.c.owner == owner)
                    .values(owner="", until=0)
                )

    def upsert(self, table, key, values):
        with self.engine.begin() as c:
            existing = c.execute(sa.select(table).where(key)).first()
            if existing:
                c.execute(table.update().where(key).values(**values))
            else:
                c.execute(table.insert().values(**values))

    def watch(self, listing, sku, signature):
        self.upsert(
            watches,
            watches.c.listing == listing,
            dict(listing=listing, sku=sku, signature=signature, enabled=True),
        )

    def observe(self, offer, product, now, usable):
        self.upsert(
            products, products.c.id == product.identity, dict(id=product.identity, spec=asdict(product))
        )
        self.upsert(
            listings,
            listings.c.id == offer.listing,
            dict(
                id=offer.listing,
                product_id=product.identity,
                seller=offer.seller,
                data=asdict(offer),
                seen=now,
            ),
        )
        values = dict(
            listing=offer.listing,
            product_id=offer.product_id,
            seller=offer.seller,
            at=now,
            bucket=now // 1800,
            price=offer.price,
            shipping=offer.shipping,
            basis=offer.basis,
            condition=offer.condition,
            usable=usable,
        )
        # One observation per listing per half-hour; repeat manual runs cannot overweight history.
        self.upsert(
            observations,
            sa.and_(observations.c.listing == offer.listing, observations.c.bucket == now // 1800),
            values,
        )

    def history(self, offer, now):
        return self.rows(
            sa.select(observations)
            .where(
                observations.c.listing == offer.listing,
                observations.c.product_id == offer.product_id,
                observations.c.condition == offer.condition,
                observations.c.basis == offer.basis,
                observations.c.usable.is_(True),
                observations.c.at >= now - 90 * 86400,
                observations.c.at < now,
            )
            .order_by(observations.c.at)
        )

    def equivalent_history(self, product_id, condition, basis, now):
        return self.rows(
            sa.select(observations).where(
                observations.c.product_id == product_id,
                observations.c.condition == condition,
                observations.c.basis == basis,
                observations.c.usable.is_(True),
                observations.c.at >= now - 90 * 86400,
                observations.c.at < now,
            )
        )

    def competitors(self, offer, now, hours):
        # Latest row per listing FIRST; never resurrect older in-stock/trusted observations.
        latest = (
            sa.select(observations.c.listing, sa.func.max(observations.c.at).label("last"))
            .where(observations.c.at <= now, observations.c.at >= now - hours * 3600)
            .group_by(observations.c.listing)
            .subquery()
        )
        return self.rows(
            sa.select(observations)
            .join(
                latest,
                sa.and_(observations.c.listing == latest.c.listing, observations.c.at == latest.c.last),
            )
            .join(listings, listings.c.id == observations.c.listing)
            .where(
                observations.c.product_id == offer.product_id,
                observations.c.condition == offer.condition,
                observations.c.basis == "total",
                observations.c.usable.is_(True),
                observations.c.listing != offer.listing,
                observations.c.seller != offer.seller,
                listings.c.data["available"].as_boolean().is_(True),
            )
        )

    def reserve(self, offer, now, rules):
        previous = self.rows(
            sa.select(alerts).where(
                alerts.c.listing == offer.listing,
                alerts.c.product_id == offer.product_id,
                alerts.c.condition == offer.condition,
            )
        )
        if any(r["state"] in {"dispatching", "uncertain"} for r in previous):
            return None
        sent = [r for r in previous if r["state"] == "sent"]
        if sent:
            last = max(sent, key=lambda r: r["at"])
            if last["basis"] != offer.basis or now - last["at"] < rules.cooldown_hours * 3600:
                return None
            if offer.total > last["price"] * (1 - rules.realert_drop_pct / 100):
                return None
        ident = uuid.uuid4().hex
        with self.engine.begin() as c:
            c.execute(
                alerts.insert().values(
                    id=ident,
                    listing=offer.listing,
                    product_id=offer.product_id,
                    condition=offer.condition,
                    basis=offer.basis,
                    price=offer.total,
                    at=now,
                    state="dispatching",
                )
            )
        return ident

    def finish_alert(self, ident, state, message_id=None):
        with self.engine.begin() as c:
            c.execute(alerts.update().where(alerts.c.id == ident).values(state=state, message_id=message_id))

    def cleanup(self, days, now):
        cutoff = now - int(timedelta(days=days).total_seconds())
        with self.engine.begin() as c:
            c.execute(observations.delete().where(observations.c.at < cutoff))
            c.execute(runs.delete().where(runs.c.at < cutoff))
            c.execute(manual.delete().where(manual.c.at < cutoff))
            # Preserve sent/uncertain dedup records even if the price history expires.
            c.execute(alerts.delete().where(alerts.c.state == "failed", alerts.c.at < cutoff))

    def close(self):
        self.engine.dispose()

import os
import uuid
from datetime import datetime, timezone

import pytest

from radar_gamer.config import Rules
from radar_gamer.domain import Offer, Product
from radar_gamer.storage import Store, meta

NOW = int(datetime(2026, 10, 20, 12, tzinfo=timezone.utc).timestamp())


@pytest.fixture
def product():
    # Synthetic fixture: no claim that this code/configuration exists in retail.
    return Product(
        "Acer",
        "Nitro V15",
        "Intel Core i5-13420H",
        "RTX 4050",
        16,
        512,
        "TEST-ONLY-ANV15",
        "15.6 FHD 144 Hz",
        "6 GB; TGP não informado",
    )


@pytest.fixture
def offer(product):
    return Offer(
        "meli:MLB1234567",
        product.identity,
        "meli:123",
        "Notebook fictício TESTE",
        "https://produto.mercadolivre.com.br/MLB-1234567-teste",
        400000,
        0,
        "new",
        True,
        True,
        True,
    )


@pytest.fixture
def rules():
    return Rules()


@pytest.fixture
def store():
    db = Store("sqlite:///:memory:", testing=True)
    db.init()
    yield db
    db.close()


@pytest.fixture
def pg_store():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL ausente; teste real PostgreSQL não executado")
    # A unique schema protects other databases; no DROP DATABASE or shared table cleanup.
    db = Store(url, testing=True)
    schema = "test_" + uuid.uuid4().hex
    import sqlalchemy as sa

    with db.engine.begin() as c:
        c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    db.engine = db.engine.execution_options(schema_translate_map={None: schema})
    db.init()
    yield db
    with db.engine.begin() as c:
        meta.drop_all(c)
        c.execute(sa.text(f'DROP SCHEMA "{schema}"'))
    db.close()

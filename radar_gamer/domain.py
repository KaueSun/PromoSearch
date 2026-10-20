"""Validated domain values. Money is always stored as integer centavos."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, urlunsplit


def money(value, *, zero=False) -> int:
    if isinstance(value, bool):
        raise ValueError("Valor monetário inválido")
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < (0 if zero else Decimal("0.01")) or number > 200000:
            raise ValueError("Valor monetário fora do limite")
        if number != number.quantize(Decimal("0.01")):
            raise ValueError("Use no máximo duas casas decimais")
        return int(number * 100)
    except (InvalidOperation, TypeError):
        raise ValueError("Valor monetário inválido") from None


def clean_url(value: str, hosts: set[str] | None = None) -> str:
    try:
        p = urlsplit(value)
        host = (p.hostname or "").lower()
        if p.scheme != "https" or not host or p.username or p.password or p.port not in (None, 443):
            raise ValueError
        if any(ord(c) < 33 for c in value) or len(value) > 2000 or p.fragment:
            raise ValueError
        if host == "localhost" or "." not in host or host.endswith((".local", ".internal")):
            raise ValueError
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError
        if hosts is not None and host not in hosts:
            raise ValueError
        return urlunsplit((p.scheme, p.netloc, p.path, p.query, ""))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Link HTTPS/domínio inválido") from None


def item_id(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"MLB\d{6,15}", value.upper()):
        return value.upper()
    clean_url(value, {"produto.mercadolivre.com.br", "www.mercadolivre.com.br", "mercadolivre.com.br"})
    path = urlsplit(value).path
    match = re.search(r"(?:^|/)MLB-?(\d{6,15})(?:-|/|$)", path, re.I)
    if not match:
        raise ValueError("Use o link completo de um anúncio MLB; links curtos/catálogos não são aceitos")
    return "MLB" + match[1]


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


@dataclass(frozen=True)
class Product:
    brand: str
    model: str
    cpu: str
    gpu: str
    ram_gb: int
    ssd_gb: int
    manufacturer_code: str
    display: str = "Não informado"
    gpu_variant: str = "Não informado"

    def __post_init__(self):
        for field in (self.brand, self.model, self.cpu, self.gpu, self.manufacturer_code):
            if not isinstance(field, str) or not field.strip() or len(field) > 150:
                raise ValueError("Preencha marca, modelo, CPU, GPU e código exato do fabricante")
        if not re.search(r"\d{4,5}", self.cpu) or not re.search(r"\d{3,4}", self.gpu):
            raise ValueError("CPU/GPU genérica: informe o modelo completo")
        if type(self.ram_gb) is not int or type(self.ssd_gb) is not int:
            raise ValueError("RAM/SSD devem ser inteiros em GB")
        if not 4 <= self.ram_gb <= 256 or not 64 <= self.ssd_gb <= 16384:
            raise ValueError("RAM/SSD inválidos")

    @property
    def identity(self):
        return digest({k: v.casefold().strip() if isinstance(v, str) else v for k, v in asdict(self).items()})


@dataclass(frozen=True)
class Offer:
    listing: str
    product_id: str
    seller: str
    title: str
    url: str
    price: int
    shipping: int | None
    condition: str
    available: bool
    trusted: bool
    verified: bool
    source: str = "meli_api"
    image: str | None = None
    payment: str = "Preço API channel_marketplace; confira condições no checkout"

    def __post_init__(self):
        clean_url(self.url)
        if self.condition not in {"new", "used", "refurbished", "unknown"}:
            raise ValueError("Condição inválida")
        if type(self.price) is not int or not 0 < self.price <= 20000000:
            raise ValueError("Preço inválido")
        if self.shipping is not None and (
            type(self.shipping) is not int or not 0 <= self.shipping <= 1000000
        ):
            raise ValueError("Frete inválido")
        if not self.listing or not self.seller or not self.title or not self.product_id:
            raise ValueError("Oferta incompleta")

    @property
    def total(self):
        return self.price + (self.shipping or 0)

    @property
    def basis(self):
        return "total" if self.shipping is not None else "produto_sem_frete"


def brl(cents: int | None) -> str:
    if cents is None:
        return "Não informado"
    return f"R$ {cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

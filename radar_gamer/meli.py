"""Official item/price API only. Curated hardware mapping and metadata approval are mandatory."""

import re
from dataclasses import dataclass

from .domain import Offer, clean_url, digest, item_id, money


def approved_metadata(data):
    if not isinstance(data, dict) or not isinstance(data.get("attributes"), list):
        raise ValueError("Metadados incompletos")
    if data.get("variations"):
        raise ValueError("Anúncio com variações: selecione uma publicação sem ambiguidade")
    seller = str(data.get("seller_id", ""))
    if not seller.isdigit():
        raise ValueError("Vendedor ausente")
    attributes = []
    for a in data["attributes"]:
        if not isinstance(a, dict):
            raise ValueError("Atributo malformado")
        attributes.append({k: a.get(k) for k in ("id", "value_id", "value_name", "values")})
    if len(attributes) < 4:
        raise ValueError("Atributos insuficientes para revisar configuração")
    return {
        "title": data.get("title"),
        "seller_id": seller,
        "condition": data.get("condition"),
        "attributes": sorted(attributes, key=lambda a: str(a["id"])),
    }


@dataclass
class Meli:
    client: object
    token: str
    sellers: set[str]

    def get(self, path):
        response = self.client.request(
            "https://api.mercadolibre.com" + path, headers={"Authorization": "Bearer " + self.token}
        )
        if not isinstance(response, dict):
            raise ValueError("Resposta de API inválida")
        return response

    def inspect(self, value):
        ident = item_id(value)
        details = self.get("/items/" + ident)
        if details.get("id") != ident or details.get("site_id") != "MLB":
            raise ValueError("Identidade/moeda/localidade inconsistente")
        approved = approved_metadata(details)
        return ident, details, digest(approved)

    def fetch(self, watch, product):
        ident, data, signature = self.inspect(watch["listing"])
        if signature != watch["signature"]:
            raise ValueError("Metadados alterados: revisar CPU/GPU/RAM/SSD e aprovar nova assinatura")
        price = self.get(f"/items/{ident}/sale_price?context=channel_marketplace")
        if price.get("currency_id") != "BRL":
            raise ValueError("A API não retornou preço em BRL")
        link = clean_url(
            data.get("permalink"),
            {"produto.mercadolivre.com.br", "www.mercadolivre.com.br", "mercadolivre.com.br"},
        )
        if item_id(link) != ident:
            raise ValueError("Link não corresponde ao anúncio consultado")
        # Ignore free_shipping: it is not a delivery quote for the user's CEP.
        image = data.get("secure_thumbnail")
        if image:
            image = clean_url(image, {"http2.mlstatic.com"})
        seller = str(data["seller_id"])
        reputation = self.get("/users/" + seller).get("seller_reputation", {})
        trusted = seller in self.sellers and reputation.get("level_id") in {"4_light_green", "5_green"}
        condition = {
            "new": "new",
            "used": "used",
            "not_specified": "unknown",
            "refurbished": "refurbished",
        }.get(data.get("condition"), "unknown")
        return Offer(
            listing="meli:" + ident,
            product_id=product.identity,
            seller="meli:" + seller,
            title=str(data.get("title") or "Notebook")[:250],
            url=link,
            price=money(price["amount"]),
            shipping=None,
            condition=condition,
            available=data.get("status") == "active",
            trusted=trusted,
            verified=True,
            image=image,
        )


def valid_signature(value):
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Assinatura deve vir de inspect e ter 64 caracteres hexadecimais")
    return value

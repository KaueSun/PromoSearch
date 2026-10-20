import json
import re
from datetime import datetime, timezone

from .domain import brl, clean_url
from .http import ApiError


def embed(offer, product, review, now):
    condition = {"new": "Novo", "used": "USADO", "refurbished": "RECONDICIONADO"}[offer.condition]
    colors = {"Excelente": 0x22C55E, "Boa oferta": 0x3B82F6, "Queda moderada": 0xF59E0B}
    fields = [
        {
            "name": "Configuração revisada",
            "value": f"{product.cpu} • {product.gpu}\n{product.ram_gb} GB RAM • SSD {product.ssd_gb} GB\n"
            f"Tela: {product.display}\nVariante GPU: {product.gpu_variant}",
        },
        {"name": "Preço do produto", "value": brl(offer.price), "inline": True},
        {"name": "Frete", "value": brl(offer.shipping), "inline": True},
        {"name": "Referência calculada", "value": brl(review.best_reference), "inline": True},
        {"name": "Queda calculada", "value": f"{review.best_pct:.1f}% ({offer.basis})", "inline": True},
        {"name": "Menor preço anterior observado (90d)", "value": brl(review.historical_low), "inline": True},
        {"name": "Loja / vendedor", "value": f"Mercado Livre / {offer.seller}"},
        {"name": "Por que foi selecionado", "value": "\n".join(review.reasons)[:1000]},
        {
            "name": "Histórico disponível",
            "value": "\n".join(
                f"{key}d: {brl(value['median'])} • {value['days']} dias observados"
                for key, value in review.references.items()
            )
            or "Sem histórico",
        },
        {"name": "Condições e limites", "value": "\n".join([offer.payment] + review.limitations)[:1000]},
    ]
    result = {
        "title": f"{review.tier} • {condition}",
        "description": offer.title[:250],
        "url": offer.url,
        "color": colors.get(review.tier, 0x808080),
        "fields": fields,
        "timestamp": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        "footer": {"text": "Radar Gamer • PromoSearch • Confirme frete e preço final no checkout"},
    }
    if offer.image:
        result["thumbnail"] = {"url": offer.image}
    return {"username": "Radar Gamer", "allowed_mentions": {"parse": []}, "embeds": [result]}


def webhook_url(value):
    clean_url(value, {"discord.com"})
    if not re.fullmatch(r"https://discord\.com/api/webhooks/\d+/[A-Za-z0-9_.-]+", value):
        raise ValueError("Configure um webhook Discord HTTPS válido, sem parâmetros extras")
    return value + "?wait=true"


def send(client, url, payload):
    response = client.request(
        webhook_url(url),
        method="POST",
        headers={"Content-Type": "application/json"},
        body=json.dumps(payload, ensure_ascii=False).encode(),
    )
    if not isinstance(response, dict) or not str(response.get("id", "")).isdigit():
        raise ApiError("discord_confirmation", ambiguous=True)
    return str(response["id"])

import json
from dataclasses import dataclass, fields
from pathlib import Path

from .domain import Product


@dataclass(frozen=True)
class Rules:
    historical_discount_pct: float = 20
    competitor_discount_pct: float = 12
    recent_drop_pct: float = 10
    realert_drop_pct: float = 5
    cooldown_hours: int = 1
    min_reference_days: int = 7
    min_recent_days: int = 3
    min_competitors: int = 2
    freshness_hours: int = 2
    suspicious_drop_pct: float = 60
    minimum_price_brl: int = 1200
    retention_days: int = 100
    max_watches: int = 50
    max_alerts_per_run: int = 5
    allow_non_new: bool = False

    def __post_init__(self):
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name == "allow_non_new":
                if type(value) is not bool:
                    raise ValueError("allow_non_new deve ser booleano")
            elif f.name.endswith("_pct"):
                if isinstance(value, bool) or not isinstance(value, (float, int)) or not 0 < value < 100:
                    raise ValueError("Percentual inválido")
            elif type(value) is not int or not 1 <= value <= 10000:
                raise ValueError("Limite inválido")
        if self.retention_days < 91 or self.max_watches > 100 or self.max_alerts_per_run > 20:
            raise ValueError("Retenção mínima 91 dias; máximo 100 anúncios e 20 alertas/execução")


def load(path="config/catalog.json"):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    products = {key: Product(**spec) for key, spec in data["products"].items()}
    sellers = data["trusted_meli_sellers"]
    if not all(isinstance(s, str) and s.isdigit() for s in sellers):
        raise ValueError("Vendedores devem ser IDs numéricos em texto")
    return products, set(sellers), Rules(**data.get("rules", {}))

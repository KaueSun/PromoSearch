"""Signals based on daily medians, independent sellers and comparable price bases."""

from dataclasses import dataclass, field
from statistics import median

from .config import Rules


def drop(reference, current):
    return max(0.0, 100 * (reference - current) / reference) if reference else 0.0


def daily_prices(rows, cutoff):
    days = {}
    for r in rows:
        if r["at"] >= cutoff:
            days.setdefault(r["at"] // 86400, []).append(r["price"] + (r["shipping"] or 0))
    return [median(values) for values in days.values()]


@dataclass
class Review:
    worthy: bool = False
    usable: bool = False
    tier: str = "Sem alerta"
    reasons: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    references: dict = field(default_factory=dict)
    best_reference: int | None = None
    best_pct: float = 0
    historical_low: int | None = None


def assess(store, offer, rules: Rules, now: int) -> Review:
    result = Review()
    if not offer.available or not offer.trusted or not offer.verified or offer.source != "meli_api":
        result.limitations.append("Indisponível, vendedor não aprovado ou dados sem verificação por API")
        return result
    if offer.condition == "unknown" or (offer.condition != "new" and not rules.allow_non_new):
        result.limitations.append("Condição fora do filtro de produtos novos")
        return result
    if offer.price < rules.minimum_price_brl * 100:
        result.limitations.append("Preço suspeito abaixo do piso configurado; revisão manual necessária")
        return result
    history = store.history(offer, now)
    daily = daily_prices(history, now - 7 * 86400)
    baselines = []
    for days in (7, 30, 90):
        values = daily_prices(history, now - days * 86400)
        mature = len(values) >= rules.min_reference_days
        reference = int(median(values)) if mature else None
        result.references[str(days)] = {"median": reference, "days": len(values), "window": days}
        if reference:
            baselines.append(
                (
                    f"mediana diária de {days} dias ({len(values)} dias observados)",
                    reference,
                    rules.historical_discount_pct,
                )
            )
    if len(daily) >= rules.min_recent_days:
        baselines.append(
            (
                f"histórico recente de 7 dias ({len(daily)} dias observados)",
                int(median(daily)),
                rules.recent_drop_pct,
            )
        )
    if offer.shipping is not None:
        rows = store.competitors(offer, now, rules.freshness_hours)
        sellers = {}
        for row in rows:
            # One cheapest offer per distinct seller; a seller with 20 listings is still one seller.
            total = row["price"] + row["shipping"]
            sellers[row["seller"]] = min(sellers.get(row["seller"], total), total)
        if len(sellers) >= rules.min_competitors:
            baselines.append(
                (
                    f"mediana de {len(sellers)} vendedores equivalentes com frete conhecido",
                    int(median(sellers.values())),
                    rules.competitor_discount_pct,
                )
            )
    else:
        result.limitations.append(
            "Frete desconhecido: histórico compara apenas produto; sem comparação de totais"
        )
    if history:
        result.historical_low = min(r["price"] + (r["shipping"] or 0) for r in history)
    if any(drop(reference, offer.total) >= rules.suspicious_drop_pct for _, reference, _ in baselines):
        result.limitations.append("Queda extrema suspeita: confirmar anúncio antes de alertar")
        return result
    result.usable = True
    for label, reference, threshold in baselines:
        pct = drop(reference, offer.total)
        if pct >= threshold:
            result.reasons.append(f"{pct:.1f}% abaixo de {label}")
            if pct > result.best_pct:
                result.best_reference, result.best_pct = reference, pct
    result.worthy = bool(result.reasons)
    if result.worthy:
        result.tier = (
            "Excelente"
            if result.best_pct >= 20
            else "Boa oferta"
            if result.best_pct >= 12
            else "Queda moderada"
        )
    else:
        result.limitations.append(
            "Sem evidência suficiente de desconto real; preço original da loja não é referência"
        )
    return result


def compare_manual(store, product, entry, now, rules):
    """Provisional comparison only; typed prices never become verified history or alerts."""
    basis = "total" if entry["shipping"] is not None else "produto_sem_frete"
    condition = entry.get("condition", "new")
    if condition not in {"new", "used", "refurbished"}:
        raise ValueError("Condição manual inválida")
    history = store.equivalent_history(product.identity, condition, basis, now)
    total = entry["price"] + (entry["shipping"] or 0)
    report = {
        "source": "manual_unverified",
        "basis": basis,
        "condition": condition,
        "current": total,
        "references": {},
        "alert_sent": False,
        "limitation": "Preço digitado e especificações precisam de confirmação; sem alerta automático",
    }
    for window in (7, 30, 90):
        daily = daily_prices(history, now - window * 86400)
        reference = int(median(daily)) if len(daily) >= rules.min_reference_days else None
        report["references"][str(window)] = {
            "median": reference,
            "days": len(daily),
            "provisional_drop_pct": drop(reference, total) if reference else None,
        }
    return report

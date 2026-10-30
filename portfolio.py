import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "portfolio_config.json"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def compute_portfolio(config: dict, prices: dict) -> dict:
    cash = config["cash"]
    total_mkt = 0.0
    total_cost = 0.0
    total_day_pl = 0.0
    allocation: dict[str, float] = {}
    positions = []

    for h in config["holdings"]:
        ticker = h["ticker"]
        shares = h["shares"]
        avg_cost = h["avg_cost"]
        asset_class = h["asset_class"]
        name = h.get("name", ticker)

        p = prices.get(ticker, {})
        price = p.get("price", 0.0)
        day_change = p.get("day_change", 0.0)
        day_change_pct = p.get("day_change_pct", 0.0)

        mkt_val = shares * price
        cost_basis = shares * avg_cost
        gain_loss = mkt_val - cost_basis
        gain_loss_pct = gain_loss / cost_basis * 100 if cost_basis else 0.0
        day_pl = shares * day_change

        total_mkt += mkt_val
        total_cost += cost_basis
        total_day_pl += day_pl
        allocation[asset_class] = allocation.get(asset_class, 0.0) + mkt_val

        positions.append({
            "ticker": ticker,
            "name": name,
            "shares": shares,
            "avg_cost": avg_cost,
            "price": price,
            "mkt_val": mkt_val,
            "cost_basis": cost_basis,
            "gain_loss": gain_loss,
            "gain_loss_pct": gain_loss_pct,
            "day_change": day_change,
            "day_change_pct": day_change_pct,
            "day_pl": day_pl,
            "asset_class": asset_class,
        })

    allocation["Cash"] = cash
    total_val = total_mkt + cash
    alloc_pct = {k: round(v / total_val * 100, 1) for k, v in allocation.items()}

    positions.sort(key=lambda x: x["mkt_val"], reverse=True)

    total_gain = total_mkt - total_cost
    total_gain_pct = total_gain / total_cost * 100 if total_cost else 0.0
    day_pct = total_day_pl / (total_val - total_day_pl) * 100 if (total_val - total_day_pl) else 0.0

    return {
        "total_val": total_val,
        "total_mkt": total_mkt,
        "total_gain": total_gain,
        "total_gain_pct": total_gain_pct,
        "day_pl": total_day_pl,
        "day_pct": day_pct,
        "cash": cash,
        "positions": positions,
        "allocation": allocation,
        "alloc_pct": alloc_pct,
    }

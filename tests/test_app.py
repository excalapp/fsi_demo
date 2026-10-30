"""Pre-deploy smoke tests. No network calls — market functions are mocked."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from portfolio import compute_portfolio, load_config

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PRICES = {
    "AAPL": {"price": 200.0, "prev_close": 190.0, "day_change": 10.0, "day_change_pct": 5.26},
}
_HISTORY = [{"date": "2024-01-01", "value": 10000.0}]
_WATCHLIST_RAW = [
    {
        "ticker": "NVDA",
        "price": 500.0,
        "day_change": 5.0,
        "day_change_pct": 1.0,
        "week52_high": 600.0,
        "week52_low": 300.0,
        "volume": 1_000_000,
    }
]


@pytest.fixture(autouse=True)
def mock_market():
    with (
        patch("main.get_current_prices", return_value=_PRICES),
        patch("main.get_portfolio_history", return_value=_HISTORY),
        patch("main.get_watchlist_data", return_value=_WATCHLIST_RAW),
    ):
        yield


# ---------------------------------------------------------------------------
# Unit tests — compute_portfolio (pure function, no mocking needed)
# ---------------------------------------------------------------------------

_CONFIG = {
    "cash": 10_000.0,
    "holdings": [
        {"ticker": "AAPL", "name": "Apple Inc.", "shares": 10, "avg_cost": 150.0, "asset_class": "US Equities"}
    ],
    "watchlist": [],
}


def test_compute_portfolio_totals():
    port = compute_portfolio(_CONFIG, _PRICES)
    assert port["total_mkt"] == pytest.approx(2_000.0)   # 10 * 200
    assert port["total_val"] == pytest.approx(12_000.0)  # 2000 + 10000 cash
    assert port["total_gain"] == pytest.approx(500.0)    # 2000 - 1500
    assert port["day_pl"] == pytest.approx(100.0)        # 10 * 10


def test_compute_portfolio_position_fields():
    port = compute_portfolio(_CONFIG, _PRICES)
    assert len(port["positions"]) == 1
    pos = port["positions"][0]
    for key in ("ticker", "name", "shares", "price", "mkt_val", "cost_basis",
                "gain_loss", "gain_loss_pct", "day_change", "day_change_pct",
                "day_pl", "asset_class"):
        assert key in pos, f"Missing key '{key}' in position"


def test_compute_portfolio_zero_prices():
    """Falls back to zeros when prices dict is empty."""
    port = compute_portfolio(_CONFIG, {})
    assert port["total_mkt"] == pytest.approx(0.0)
    assert port["total_val"] == pytest.approx(10_000.0)  # cash only


def test_compute_portfolio_alloc_pct_sums_to_100():
    port = compute_portfolio(_CONFIG, _PRICES)
    total = sum(port["alloc_pct"].values())
    assert total == pytest.approx(100.0, abs=0.1)


def test_compute_portfolio_empty_holdings():
    config = {"cash": 5_000.0, "holdings": [], "watchlist": []}
    port = compute_portfolio(config, {})
    assert port["positions"] == []
    assert port["total_val"] == pytest.approx(5_000.0)


# ---------------------------------------------------------------------------
# Config validation — ensures portfolio_config.json stays well-formed
# ---------------------------------------------------------------------------

def test_config_required_keys():
    config = load_config()
    for key in ("cash", "holdings", "watchlist"):
        assert key in config, f"portfolio_config.json missing '{key}'"


def test_config_holdings_schema():
    config = load_config()
    for h in config["holdings"]:
        for key in ("ticker", "shares", "avg_cost", "asset_class"):
            assert key in h, f"Holding {h.get('ticker', '?')} missing '{key}'"
        assert isinstance(h["shares"], (int, float)) and h["shares"] > 0
        assert isinstance(h["avg_cost"], (int, float)) and h["avg_cost"] > 0


def test_config_watchlist_schema():
    config = load_config()
    for w in config["watchlist"]:
        assert "ticker" in w, f"Watchlist entry missing 'ticker': {w}"


# ---------------------------------------------------------------------------
# Route smoke tests — all pages must return 200
# ---------------------------------------------------------------------------

def test_root_redirects_to_overview():
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"].endswith("/overview")


@pytest.mark.parametrize("path", ["/overview", "/holdings", "/watchlist"])
def test_implemented_pages_200(path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", [
    "/performance", "/transactions", "/markets",
    "/accounts", "/research", "/reports",
])
def test_placeholder_pages_200(path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("period", ["1M", "3M", "6M", "1Y", "All"])
def test_chart_data_api(period):
    r = client.get(f"/api/chart-data?period={period}")
    assert r.status_code == 200
    data = r.json()
    assert "labels" in data and "values" in data
    assert len(data["labels"]) == len(data["values"])

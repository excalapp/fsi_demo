import json
from datetime import date

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from market import PERIOD_MAP, get_current_prices, get_portfolio_history, get_watchlist_data
from portfolio import compute_portfolio, load_config

app = FastAPI(title="FinTechCo")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def _fmt_usd(v: float) -> str:
    return f"${v:,.2f}"


def _fmt_pct(v: float) -> str:
    return f"{'+' if v >= 0 else ''}{v:.2f}%"


def _fmt_chg(v: float) -> str:
    return f"+${v:,.2f}" if v >= 0 else f"-${abs(v):,.2f}"


templates.env.globals.update(
    fmt_usd=_fmt_usd,
    fmt_pct=_fmt_pct,
    fmt_chg=_fmt_chg,
    now_year=date.today().year,
)


@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/overview")


@app.get("/overview", response_class=HTMLResponse)
async def overview(request: Request, period: str = "1M"):
    config = load_config()
    tickers = [h["ticker"] for h in config["holdings"]]
    prices = get_current_prices(tickers)
    port = compute_portfolio(config, prices)

    shares_map = {h["ticker"]: h["shares"] for h in config["holdings"]}
    history = get_portfolio_history(tickers, shares_map, period)

    return templates.TemplateResponse(request, "overview.html", {
        "port": port,
        "chart_labels": json.dumps([d["date"] for d in history]),
        "chart_values": json.dumps([d["value"] for d in history]),
        "active_period": period,
        "active_page": "overview",
        "periods": list(PERIOD_MAP.keys()),
    })


@app.get("/holdings", response_class=HTMLResponse)
async def holdings(request: Request):
    config = load_config()
    tickers = [h["ticker"] for h in config["holdings"]]
    prices = get_current_prices(tickers)
    port = compute_portfolio(config, prices)

    return templates.TemplateResponse(request, "holdings.html", {
        "port": port,
        "active_page": "holdings",
    })


@app.get("/watchlist", response_class=HTMLResponse)
async def watchlist(request: Request):
    config = load_config()
    wl_tickers = [w["ticker"] for w in config["watchlist"]]
    name_map = {w["ticker"]: w.get("name", w["ticker"]) for w in config["watchlist"]}
    data = get_watchlist_data(wl_tickers)
    for item in data:
        item["name"] = name_map.get(item["ticker"], item["ticker"])

    return templates.TemplateResponse(request, "watchlist.html", {
        "watchlist": data,
        "active_page": "watchlist",
    })


def _placeholder(page: str):
    async def handler(request: Request):
        return templates.TemplateResponse(request, f"{page}.html", {
            "active_page": page,
        })
    return handler


app.get("/performance", response_class=HTMLResponse)(_placeholder("performance"))
app.get("/transactions", response_class=HTMLResponse)(_placeholder("transactions"))
app.get("/markets", response_class=HTMLResponse)(_placeholder("markets"))
app.get("/accounts", response_class=HTMLResponse)(_placeholder("accounts"))
app.get("/research", response_class=HTMLResponse)(_placeholder("research"))
app.get("/reports", response_class=HTMLResponse)(_placeholder("reports"))


@app.get("/api/chart-data")
async def chart_data(period: str = "1M"):
    config = load_config()
    tickers = [h["ticker"] for h in config["holdings"]]
    shares_map = {h["ticker"]: h["shares"] for h in config["holdings"]}
    history = get_portfolio_history(tickers, shares_map, period)
    return {"labels": [d["date"] for d in history], "values": [d["value"] for d in history]}

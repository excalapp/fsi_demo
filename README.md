# FinTechCo Portfolio Dashboard

A web-based portfolio management dashboard built with FastAPI and Python. Live market data is pulled from Yahoo Finance.

## Requirements

- Python 3.10 or later

## Setup

**1. Clone the repository and navigate to the project folder:**

```bash
cd fsi_demo
```

**2. (Recommended) Create and activate a virtual environment:**

```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

**3. Install dependencies:**

```bash
pip install -r requirements.txt
```

## Running the app

```bash
uvicorn main:app --reload
```

Then open your browser at **http://localhost:8000**

The `--reload` flag restarts the server automatically when you edit source files. For production, omit it and optionally specify a host/port:

```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

## Customising your portfolio

Edit `portfolio_config.json` to change holdings, share counts, average costs, and the watchlist. No code changes needed — the app reads this file on every request.

```json
{
  "cash": 24580.00,
  "holdings": [
    { "ticker": "AAPL", "name": "Apple Inc.", "shares": 50, "avg_cost": 150.00, "asset_class": "US Equities" }
  ],
  "watchlist": [
    { "ticker": "NVDA", "name": "NVIDIA Corp." }
  ]
}
```

## Pages

| URL | Description |
|-----|-------------|
| `/overview` | Portfolio summary, performance chart, asset allocation |
| `/holdings` | Full positions table with live P&L |
| `/watchlist` | Tracked securities with 52-week range |
| `/performance` | Placeholder |
| `/transactions` | Placeholder |
| `/markets` | Placeholder |
| `/accounts` | Placeholder |
| `/research` | Placeholder |
| `/reports` | Placeholder |

## Notes

- Market data is cached for 5 minutes to avoid hammering Yahoo Finance on every page load.
- Prices reflect the previous close when markets are closed.
- This app is for informational and demonstration purposes only. It is not financial advice.

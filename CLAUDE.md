# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```bash
source venv/bin/activate
uvicorn main:app --reload
```

App runs at http://localhost:8000. The `--reload` flag restarts on source changes.

## Architecture

This is a FastAPI + Jinja2 web app with no database. Data flows in a single direction on every request:

1. `portfolio_config.json` — source of truth for holdings, share counts, avg cost, and watchlist. Read on every request by `portfolio.py:load_config()`.
2. `market.py` — fetches live prices from Yahoo Finance via `yfinance`. An in-process dict cache (`_cache`) keyed by a 5-minute time bucket prevents redundant API calls. All market functions silently return zeros on fetch failure.
3. `portfolio.py:compute_portfolio()` — pure function that combines config + prices into a `port` dict (positions, totals, allocation breakdown) passed to templates.
4. `main.py` — FastAPI routes; each handler composes the above and calls `templates.TemplateResponse`. Three Jinja2 global formatters (`fmt_usd`, `fmt_pct`, `fmt_chg`) are available in every template.

**Implemented pages:** `/overview` (summary + portfolio history chart), `/holdings` (positions table), `/watchlist` (52-week range).

**Placeholder pages** (render empty shell): `/performance`, `/transactions`, `/markets`, `/accounts`, `/research`, `/reports`.

**JSON API:** `GET /api/chart-data?period=<1M|3M|6M|1Y|All>` returns `{labels, values}` for the portfolio history chart; called client-side by `static/js/charts.js` when the user switches periods.

## Portfolio configuration

Edit `portfolio_config.json` directly — no code changes needed:

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

## Deploying to AWS

Deployment is done interactively via Claude Code — no AWS CLI required.

**Prerequisites on any machine:**
- Docker Desktop running
- AWS credentials set as environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION=us-east-1`)
- Claude Code with the AWS MCP plugin (already configured in this project)

**To deploy**, just tell Claude Code: *"deploy this app to AWS"*. Claude Code will:
1. Create an ECR repository and get login credentials via `ecr:GetAuthorizationToken` (no AWS CLI needed)
2. Run `docker build` and `docker push` via Bash
3. Create ECS Fargate cluster, task definition (ARM64/Graviton), security group, IAM roles, and CloudWatch log group
4. Launch the task and return a public URL (`http://<public-ip>:8080`)

**To clean up**, tell Claude Code: *"clean up the AWS stack"*. It will delete all resources in the correct order (task → cluster → ECR → security group → IAM roles → log group).

**Key deployment details:**
- Platform: ECS Fargate ARM64 (Graviton) — matches Apple Silicon Docker builds; ~20% cheaper than x86
- Port: 8080 (Fargate default)
- Cost: ~$0.01/hr (0.25 vCPU + 0.5 GB memory)
- The public IP changes if the task is restarted; for a stable URL add an ALB
- `deploy.sh` and `cleanup.sh` are standalone scripts if you ever want to deploy without Claude Code (require AWS CLI)

## Key constraints

- Market data is cached in-process for 5 minutes (`market.py:CACHE_TTL`). Restart the server to bust the cache during development.
- The cache is lost on each restart — there is no persistent store.
- `yfinance` returns previous-close prices when markets are closed; "day change" reflects the last two available closing prices.

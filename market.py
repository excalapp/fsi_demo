import time

import pandas as pd
import yfinance as yf

CACHE_TTL = 300
_cache: dict = {}

PERIOD_MAP = {
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "1Y": "1y",
    "All": "5y",
}


def _bucket() -> int:
    return int(time.time() / CACHE_TTL)


def _download_closes(tickers: list[str], **kwargs) -> pd.DataFrame:
    single = len(tickers) == 1
    raw = yf.download(
        tickers[0] if single else tickers,
        progress=False,
        auto_adjust=True,
        threads=False,
        **kwargs,
    )

    if raw.empty:
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):
        lvl0 = raw.columns.get_level_values(0)
        if "Close" not in lvl0:
            return pd.DataFrame()
        df = raw["Close"]
        if isinstance(df, pd.Series):
            df = df.to_frame(name=tickers[0])
        return df

    if "Close" not in raw.columns:
        return pd.DataFrame()

    close = raw["Close"]
    if isinstance(close, pd.Series):
        return close.to_frame(name=tickers[0])
    return close


def get_current_prices(tickers: list[str]) -> dict:
    key = f"prices:{_bucket()}"
    if key in _cache:
        return _cache[key]

    result = {}
    try:
        closes = _download_closes(tickers, period="5d").dropna(how="all")
        for ticker in tickers:
            if ticker not in closes.columns:
                result[ticker] = {"price": 0.0, "prev_close": 0.0, "day_change": 0.0, "day_change_pct": 0.0}
                continue
            col = closes[ticker].dropna()
            if col.empty:
                result[ticker] = {"price": 0.0, "prev_close": 0.0, "day_change": 0.0, "day_change_pct": 0.0}
                continue
            current = float(col.iloc[-1])
            prev = float(col.iloc[-2]) if len(col) >= 2 else current
            change = current - prev
            pct = change / prev * 100 if prev else 0.0
            result[ticker] = {
                "price": current,
                "prev_close": prev,
                "day_change": change,
                "day_change_pct": pct,
            }
    except Exception:
        for t in tickers:
            result.setdefault(t, {"price": 0.0, "prev_close": 0.0, "day_change": 0.0, "day_change_pct": 0.0})

    _cache[key] = result
    return result


def get_portfolio_history(tickers: list[str], shares: dict, period: str = "1M") -> list[dict]:
    key = f"history:{_bucket()}:{period}"
    if key in _cache:
        return _cache[key]

    yf_period = PERIOD_MAP.get(period, "1mo")
    result = []
    try:
        closes = _download_closes(tickers, period=yf_period)
        if closes.empty:
            return result
        closes = closes.ffill().dropna(how="all")
        available = [t for t in tickers if t in closes.columns]
        portfolio_val = sum(closes[t] * shares.get(t, 0) for t in available)
        result = [
            {"date": str(idx.date()), "value": round(float(v), 2)}
            for idx, v in portfolio_val.items()
            if pd.notna(v)
        ]
    except Exception:
        pass

    _cache[key] = result
    return result


def get_watchlist_data(tickers: list[str]) -> list[dict]:
    key = f"watchlist:{_bucket()}"
    if key in _cache:
        return _cache[key]

    prices = get_current_prices(tickers)
    result = []

    for ticker in tickers:
        p = prices.get(ticker, {})
        week52_high = week52_low = 0.0
        volume = 0
        try:
            hist = yf.Ticker(ticker).history(period="1y")
            if not hist.empty:
                week52_high = float(hist["Close"].max())
                week52_low = float(hist["Close"].min())
                volume = int(hist["Volume"].iloc[-1]) if "Volume" in hist.columns else 0
        except Exception:
            pass

        result.append({
            "ticker": ticker,
            "price": p.get("price", 0.0),
            "day_change": p.get("day_change", 0.0),
            "day_change_pct": p.get("day_change_pct", 0.0),
            "week52_high": week52_high,
            "week52_low": week52_low,
            "volume": volume,
        })

    _cache[key] = result
    return result

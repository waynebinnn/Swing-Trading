from __future__ import annotations

from dataclasses import dataclass

import akshare as ak
import pandas as pd
import requests
import yfinance as yf


@dataclass(frozen=True)
class FetchConfig:
    symbol: str
    period: str = "2y"
    interval: str = "1d"


def fetch_ohlcv(config: FetchConfig) -> pd.DataFrame:
    """Fetch OHLCV data and normalize columns for downstream analysis."""
    df = _fetch_with_yfinance(config)
    if df.empty:
        # Fall back to akshare for A-share symbols when Yahoo is rate-limited.
        df = _fetch_with_akshare(config)
    if df.empty:
        # Final fallback: Eastmoney public kline API.
        df = _fetch_with_eastmoney(config)
    if df.empty:
        # Tencent day kline fallback is usually more reachable for A-shares.
        df = _fetch_with_tencent(config)

    if df.empty:
        raise ValueError(
            f"No data fetched for symbol={config.symbol} from yfinance, akshare, eastmoney, and tencent"
        )

    needed = ["open", "high", "low", "close", "volume"]
    missing = [name for name in needed if name not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    out = df[needed].copy()
    out = out.dropna()
    out.index = pd.to_datetime(out.index)
    out = out.sort_index()
    return out


def _fetch_with_yfinance(config: FetchConfig) -> pd.DataFrame:
    yf_symbol = _normalize_yf_symbol(config.symbol)
    raw = yf.download(
        tickers=yf_symbol,
        period=config.period,
        interval=config.interval,
        auto_adjust=False,
        progress=False,
    )
    if raw.empty:
        return raw

    df = raw.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )
    return df


def _normalize_yf_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if s.endswith(".SS") or s.endswith(".SZ"):
        return s
    if s.isdigit() and len(s) == 6:
        if s.startswith(("0", "3")):
            return f"{s}.SZ"
        return f"{s}.SS"
    return s


def _fetch_with_akshare(config: FetchConfig) -> pd.DataFrame:
    code = _to_akshare_code(config.symbol)
    if not code:
        return pd.DataFrame()

    if config.interval == "1d":
        return _fetch_with_akshare_daily(code, config.period)

    return _fetch_with_akshare_minute(code, config.period, config.interval)


def _fetch_with_akshare_daily(code: str, period: str) -> pd.DataFrame:
    start_date, end_date = _period_to_date_range(period)
    try:
        raw = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
    except Exception:
        return pd.DataFrame()

    if raw.empty:
        return raw

    out = raw.rename(
        columns={
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
        }
    )
    if "date" not in out.columns:
        return pd.DataFrame()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"])
    out = out.set_index("date")

    return out


def _fetch_with_akshare_minute(code: str, period: str, interval: str) -> pd.DataFrame:
    period_map = {
        "1m": "1",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "60m": "60",
    }
    ak_period = period_map.get(interval)
    if not ak_period:
        return pd.DataFrame()

    start_dt, end_dt = _period_to_datetime_range(period)
    try:
        raw = ak.stock_zh_a_hist_min_em(
            symbol=code,
            period=ak_period,
            start_date=start_dt,
            end_date=end_dt,
            adjust="qfq",
        )
    except Exception:
        return pd.DataFrame()

    if raw.empty:
        return raw

    out = raw.rename(
        columns={
            "时间": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
        }
    )
    if "date" not in out.columns:
        return pd.DataFrame()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"])
    out = out.set_index("date")

    return out


def _to_akshare_code(symbol: str) -> str | None:
    s = symbol.strip().upper()
    if s.endswith(".SS") or s.endswith(".SZ"):
        return s.split(".")[0]
    if s.isdigit() and len(s) == 6:
        return s
    return None


def _period_to_date_range(period: str) -> tuple[str, str]:
    now = pd.Timestamp.now().normalize()
    mapping = {
        "1mo": pd.DateOffset(months=1),
        "3mo": pd.DateOffset(months=3),
        "6mo": pd.DateOffset(months=6),
        "1y": pd.DateOffset(years=1),
        "2y": pd.DateOffset(years=2),
        "5y": pd.DateOffset(years=5),
    }
    delta = mapping.get(period, pd.DateOffset(years=2))
    start = now - delta
    return start.strftime("%Y%m%d"), now.strftime("%Y%m%d")


def _period_to_datetime_range(period: str) -> tuple[str, str]:
    now = pd.Timestamp.now().floor("min")
    mapping = {
        "5d": pd.DateOffset(days=5),
        "1mo": pd.DateOffset(months=1),
        "3mo": pd.DateOffset(months=3),
        "6mo": pd.DateOffset(months=6),
        "1y": pd.DateOffset(years=1),
    }
    delta = mapping.get(period, pd.DateOffset(months=3))
    start = now - delta
    return start.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S")


def _fetch_with_eastmoney(config: FetchConfig) -> pd.DataFrame:
    secid = _to_eastmoney_secid(config.symbol)
    if not secid:
        return pd.DataFrame()

    klt_map = {
        "1m": "1",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "60m": "60",
        "1d": "101",
    }
    klt = klt_map.get(config.interval)
    if not klt:
        return pd.DataFrame()

    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
        "klt": klt,
        "fqt": "1",
        "secid": secid,
        "beg": "19900101",
        "end": "20991231",
    }
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    try:
        response = requests.get(url, params=params, timeout=12)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return pd.DataFrame()

    data = payload.get("data") or {}
    klines = data.get("klines") or []
    if not klines:
        return pd.DataFrame()

    rows = []
    for item in klines:
        parts = item.split(",")
        if len(parts) < 6:
            continue
        rows.append(
            {
                "date": parts[0],
                "open": parts[1],
                "close": parts[2],
                "high": parts[3],
                "low": parts[4],
                "volume": parts[5],
            }
        )

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for col in ["open", "close", "high", "low", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["date", "open", "high", "low", "close"])
    out = out.set_index("date")

    return out


def _to_eastmoney_secid(symbol: str) -> str | None:
    s = symbol.strip().upper()
    if s.endswith(".SZ"):
        return f"0.{s.split('.')[0]}"
    if s.endswith(".SS"):
        return f"1.{s.split('.')[0]}"
    if s.isdigit() and len(s) == 6:
        if s.startswith(("0", "3")):
            return f"0.{s}"
        return f"1.{s}"
    return None


def _fetch_with_tencent(config: FetchConfig) -> pd.DataFrame:
    # Current Tencent endpoint is stable for daily K-lines.
    if config.interval != "1d":
        return pd.DataFrame()

    ts_code = _to_tencent_symbol(config.symbol)
    if not ts_code:
        return pd.DataFrame()

    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {
        "param": f"{ts_code},day,,,1200,qfq",
    }
    try:
        response = requests.get(url, params=params, timeout=12)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return pd.DataFrame()

    data = payload.get("data") or {}
    symbol_data = data.get(ts_code) or {}
    qfqday = symbol_data.get("qfqday") or symbol_data.get("day") or []
    if not qfqday:
        return pd.DataFrame()

    rows = []
    for item in qfqday:
        if len(item) < 6:
            continue
        rows.append(
            {
                "date": item[0],
                "open": item[1],
                "close": item[2],
                "high": item[3],
                "low": item[4],
                "volume": item[5],
            }
        )

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for col in ["open", "close", "high", "low", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["date", "open", "high", "low", "close"])
    out = out.set_index("date")
    return out


def _to_tencent_symbol(symbol: str) -> str | None:
    s = symbol.strip().upper()
    if s.endswith(".SZ"):
        return f"sz{s.split('.')[0]}"
    if s.endswith(".SS"):
        return f"sh{s.split('.')[0]}"
    if s.isdigit() and len(s) == 6:
        if s.startswith(("0", "3")):
            return f"sz{s}"
        return f"sh{s}"
    return None

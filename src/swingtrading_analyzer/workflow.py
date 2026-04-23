from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

import pandas as pd

from .analysis import ChanAnalysisResult, analyze_chan_structure
from .data_source import FetchConfig, fetch_ohlcv
from .interactive_plot import build_interactive_figure, save_interactive_html
from .planner import build_trading_plan, plan_to_dict


@dataclass(frozen=True)
class TimeframeConfig:
    name: str
    period: str
    interval: str


DEFAULT_TIMEFRAMES = [
    TimeframeConfig(name="main", period="6mo", interval="1d"),
]


def _analysis_to_summary(analysis: ChanAnalysisResult) -> dict:
    return {
        "trend": analysis.trend,
        "fractals": len(analysis.fractals),
        "strokes": len(analysis.strokes),
        "pivots": len(analysis.pivots),
        "signals": [
            {
                "signal": s.signal,
                "type": s.signal_type,
                "timestamp": s.timestamp.isoformat(),
                "price": s.price,
                "reason": s.reason,
            }
            for s in analysis.signals
        ],
    }


def _latest_ma_values(df) -> dict[str, float]:
    close = df["close"]
    ma5 = close.rolling(5).mean().iloc[-1]
    ma10 = close.rolling(10).mean().iloc[-1]
    ma20 = close.rolling(20).mean().iloc[-1]
    ma60 = close.rolling(60).mean().iloc[-1]
    return {
        "ma5": round(float(ma5), 3) if not pd.isna(ma5) else 0.0,
        "ma10": round(float(ma10), 3) if not pd.isna(ma10) else 0.0,
        "ma20": round(float(ma20), 3) if not pd.isna(ma20) else 0.0,
        "ma60": round(float(ma60), 3) if not pd.isna(ma60) else 0.0,
    }


def _build_confluence(timeframe_results: dict[str, dict]) -> dict:
    main_trend = timeframe_results["main"]["analysis"]["trend"]
    main_signals = timeframe_results["main"]["analysis"]["signals"]
    buy_types = sorted({s["type"] for s in main_signals if s["signal"] == "buy"})
    sell_types = sorted({s["type"] for s in main_signals if s["signal"] == "sell"})

    if main_trend == "up" and buy_types:
        view = "偏多执行"
        note = "当前结构向上且出现买点信号，可分批执行。"
    elif main_trend == "down" and sell_types:
        view = "偏空防守"
        note = "当前结构走弱且有卖点，优先防守或等待结构重建。"
    else:
        view = "等待确认"
        note = "当前级别暂未形成高确定性信号，建议继续观察。"

    main_plan = timeframe_results["main"]["plan"]

    return {
        "trend": main_trend,
        "buy_types": buy_types,
        "sell_types": sell_types,
        "view": view,
        "note": note,
        "suggested_levels": main_plan.get("key_levels", {}),
        "operation_plan": main_plan.get("operation_plan", []),
    }


def run_multi_timeframe(symbol: str, outdir: str) -> dict:
    # Keep all artifacts grouped by symbol for cleaner project outputs.
    safe_symbol = symbol.strip().replace("/", "_").replace("\\", "_")
    output_dir = Path(outdir) / safe_symbol
    output_dir.mkdir(parents=True, exist_ok=True)

    timeframe_results: dict[str, dict] = {}
    for tf in DEFAULT_TIMEFRAMES:
        fallback_note = ""
        df = fetch_ohlcv(FetchConfig(symbol=symbol, period=tf.period, interval=tf.interval))

        analysis = analyze_chan_structure(df)
        plan = build_trading_plan(
            symbol,
            analysis,
            current_price=float(df["close"].iloc[-1]),
        )

        html_path = output_dir / f"{symbol}_{tf.name}_interactive.html"
        data_path = output_dir / f"{symbol}_{tf.name}_data.csv"
        df.to_csv(data_path, encoding="utf-8")

        interactive_fig = build_interactive_figure(
            df=df,
            symbol=f"{symbol} [{tf.name}]",
            signals=plan.latest_signals,
            pivot_reference=plan.pivot_reference,
            support_levels=plan.support_levels,
            resistance_levels=plan.resistance_levels,
        )
        save_interactive_html(interactive_fig, str(html_path))

        timeframe_results[tf.name] = {
            "config": asdict(tf),
            "bars": int(len(df)),
            "interactive_chart": str(html_path),
            "data_csv": str(data_path),
            "fallback_note": fallback_note,
            "moving_averages": _latest_ma_values(df),
            "analysis": _analysis_to_summary(analysis),
            "plan": plan_to_dict(plan),
        }

    confluence = _build_confluence(timeframe_results)
    report = {
        "symbol": symbol,
        "timeframes": timeframe_results,
        "confluence": confluence,
    }

    report_path = output_dir / f"{symbol}_multi_plan.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    report["report_path"] = str(report_path)
    return report

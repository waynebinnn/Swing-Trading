from __future__ import annotations

from dataclasses import asdict, dataclass

from .analysis import ChanAnalysisResult


@dataclass(frozen=True)
class TradingPlan:
    symbol: str
    trend: str
    bias: str
    action: str
    risk_note: str
    current_price: float | None
    pivot_reference: dict[str, float] | None
    latest_signals: list[dict]
    key_levels: dict[str, float]
    support_levels: list[float]
    resistance_levels: list[float]
    operation_plan: list[str]


def build_trading_plan(
    symbol: str,
    analysis: ChanAnalysisResult,
    current_price: float | None = None,
) -> TradingPlan:
    latest_pivot = analysis.pivots[-1] if analysis.pivots else None

    if analysis.trend == "up":
        bias = "波段偏多"
        action = "优先等待回踩中枢下沿后的企稳信号，再分批介入"
        risk_note = "若跌破最近中枢下沿并放量，降低仓位"
    elif analysis.trend == "down":
        bias = "波段偏空/观望"
        action = "不抢反弹，等待下跌结构完成或出现更高一级别买点"
        risk_note = "逆势交易只允许轻仓并设置硬止损"
    else:
        bias = "震荡"
        action = "围绕中枢高抛低吸，减少追涨杀跌"
        risk_note = "突破前尽量控制仓位，防止假突破"

    pivot_reference = None
    if latest_pivot:
        pivot_reference = {"low": latest_pivot.low, "high": latest_pivot.high}

    key_levels = _build_key_levels(analysis.trend, latest_pivot, current_price)
    support_levels, resistance_levels = _build_support_resistance(
        key_levels, latest_pivot
    )
    operation_plan = _build_operation_plan(analysis.trend, key_levels)

    latest_signals = [
        {
            "signal": s.signal,
            "type": s.signal_type,
            "timestamp": s.timestamp.isoformat(),
            "price": s.price,
            "reason": s.reason,
        }
        for s in analysis.signals
    ]

    return TradingPlan(
        symbol=symbol,
        trend=analysis.trend,
        bias=bias,
        action=action,
        risk_note=risk_note,
        current_price=current_price,
        pivot_reference=pivot_reference,
        latest_signals=latest_signals,
        key_levels=key_levels,
        support_levels=support_levels,
        resistance_levels=resistance_levels,
        operation_plan=operation_plan,
    )


def plan_to_dict(plan: TradingPlan) -> dict:
    return asdict(plan)


def _build_key_levels(
    trend: str,
    latest_pivot,
    current_price: float | None,
) -> dict[str, float]:
    cp = float(current_price) if current_price is not None else 0.0
    has_price = cp > 0

    if latest_pivot:
        pivot_low = float(latest_pivot.low)
        pivot_high = float(latest_pivot.high)
    elif has_price:
        pivot_low = cp * 0.97
        pivot_high = cp * 1.03
    else:
        pivot_low = 0.0
        pivot_high = 0.0

    if trend == "up":
        entry_low = pivot_low
        entry_high = pivot_high
        stop_loss = pivot_low * 0.985
        target_1 = max(pivot_high * 1.03, cp * 1.03 if has_price else 0.0)
        target_2 = max(target_1 * 1.04, cp * 1.06 if has_price else 0.0)
    elif trend == "down":
        entry_low = pivot_high * 0.99
        entry_high = pivot_high * 1.01
        stop_loss = pivot_high * 1.015
        target_1 = min(pivot_low * 0.97, cp * 0.97 if has_price else pivot_low * 0.97)
        target_2 = min(target_1 * 0.96, cp * 0.94 if has_price else target_1 * 0.96)
    else:
        entry_low = pivot_low
        entry_high = pivot_high
        stop_loss = pivot_low * 0.98
        target_1 = pivot_high
        target_2 = pivot_high * 1.02

    return {
        "entry_low": round(entry_low, 3),
        "entry_high": round(entry_high, 3),
        "stop_loss": round(stop_loss, 3),
        "target_1": round(target_1, 3),
        "target_2": round(target_2, 3),
    }


def _build_operation_plan(trend: str, key_levels: dict[str, float]) -> list[str]:
    if trend == "up":
        return [
            f"回踩 {key_levels['entry_low']} - {key_levels['entry_high']} 区间分批试仓。",
            f"跌破 {key_levels['stop_loss']} 执行止损，不做主观扛单。",
            f"上行先看 {key_levels['target_1']}，突破后看 {key_levels['target_2']} 并分批止盈。",
        ]
    if trend == "down":
        return [
            f"反弹到 {key_levels['entry_low']} - {key_levels['entry_high']} 区间以防守为主。",
            f"若向上突破 {key_levels['stop_loss']}，停止逆势思路。",
            f"下行目标先看 {key_levels['target_1']}，再看 {key_levels['target_2']}。",
        ]
    return [
        f"震荡区间参考 {key_levels['entry_low']} - {key_levels['entry_high']}，靠近下沿低吸。",
        f"跌破 {key_levels['stop_loss']} 先减仓，等待结构重建。",
        f"反弹至 {key_levels['target_1']} / {key_levels['target_2']} 分批止盈。",
    ]


def _build_support_resistance(
    key_levels: dict[str, float],
    latest_pivot,
) -> tuple[list[float], list[float]]:
    supports = {key_levels["stop_loss"], key_levels["entry_low"]}
    resistances = {
        key_levels["entry_high"],
        key_levels["target_1"],
        key_levels["target_2"],
    }
    if latest_pivot:
        supports.add(round(float(latest_pivot.low), 3))
        resistances.add(round(float(latest_pivot.high), 3))

    support_levels = sorted(supports)
    resistance_levels = sorted(resistances)
    return support_levels, resistance_levels

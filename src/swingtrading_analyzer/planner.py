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
    strategy_parameters: dict[str, float]
    operation_plan: list[str]


@dataclass(frozen=True)
class StrategyParams:
    entry_band_pct: float = 0.01
    stop_loss_pct: float = 0.015
    target_1_pct: float = 0.03
    target_2_pct: float = 0.06
    range_stop_loss_pct: float = 0.02
    range_target_2_pct: float = 0.02

    def to_dict(self) -> dict[str, float]:
        return {
            "entry_band_pct": round(self.entry_band_pct, 4),
            "stop_loss_pct": round(self.stop_loss_pct, 4),
            "target_1_pct": round(self.target_1_pct, 4),
            "target_2_pct": round(self.target_2_pct, 4),
            "range_stop_loss_pct": round(self.range_stop_loss_pct, 4),
            "range_target_2_pct": round(self.range_target_2_pct, 4),
        }


def build_trading_plan(
    symbol: str,
    analysis: ChanAnalysisResult,
    current_price: float | None = None,
    strategy_params: StrategyParams | None = None,
) -> TradingPlan:
    params = strategy_params or StrategyParams()
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

    key_levels = _build_key_levels(
        analysis.trend,
        latest_pivot,
        current_price,
        params,
    )
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
        strategy_parameters=params.to_dict(),
        operation_plan=operation_plan,
    )


def plan_to_dict(plan: TradingPlan) -> dict:
    return asdict(plan)


def _build_key_levels(
    trend: str,
    latest_pivot,
    current_price: float | None,
    params: StrategyParams,
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
        stop_loss = pivot_low * (1.0 - params.stop_loss_pct)
        target_1 = max(
            pivot_high * (1.0 + params.target_1_pct),
            cp * (1.0 + params.target_1_pct) if has_price else 0.0,
        )
        target_2 = max(
            pivot_high * (1.0 + params.target_2_pct),
            cp * (1.0 + params.target_2_pct) if has_price else 0.0,
        )
    elif trend == "down":
        entry_low = pivot_high * (1.0 - params.entry_band_pct)
        entry_high = pivot_high * (1.0 + params.entry_band_pct)
        stop_loss = pivot_high * (1.0 + params.stop_loss_pct)
        target_1 = min(
            pivot_low * (1.0 - params.target_1_pct),
            cp * (1.0 - params.target_1_pct) if has_price else pivot_low * (1.0 - params.target_1_pct),
        )
        target_2 = min(
            pivot_low * (1.0 - params.target_2_pct),
            cp * (1.0 - params.target_2_pct) if has_price else pivot_low * (1.0 - params.target_2_pct),
        )
    else:
        entry_low = pivot_low
        entry_high = pivot_high
        stop_loss = pivot_low * (1.0 - params.range_stop_loss_pct)
        target_1 = pivot_high
        target_2 = pivot_high * (1.0 + params.range_target_2_pct)

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

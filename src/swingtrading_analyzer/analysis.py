from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class FractalPoint:
    kind: str
    idx: int
    timestamp: pd.Timestamp
    price: float


@dataclass(frozen=True)
class Stroke:
    start: FractalPoint
    end: FractalPoint
    direction: str


@dataclass(frozen=True)
class PivotZone:
    low: float
    high: float
    start_ts: pd.Timestamp
    end_ts: pd.Timestamp


@dataclass(frozen=True)
class BuySellSignal:
    signal: str
    signal_type: int
    timestamp: pd.Timestamp
    price: float
    reason: str


@dataclass(frozen=True)
class ChanAnalysisResult:
    fractals: list[FractalPoint]
    strokes: list[Stroke]
    pivots: list[PivotZone]
    signals: list[BuySellSignal]
    trend: str


def _detect_fractals(df: pd.DataFrame) -> list[FractalPoint]:
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    timestamps = df.index

    points: list[FractalPoint] = []
    for i in range(1, len(df) - 1):
        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
            points.append(
                FractalPoint("top", i, pd.Timestamp(timestamps[i]), float(highs[i]))
            )
        if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
            points.append(
                FractalPoint("bottom", i, pd.Timestamp(timestamps[i]), float(lows[i]))
            )

    points.sort(key=lambda x: x.idx)
    return points


def _build_strokes(fractals: list[FractalPoint]) -> list[Stroke]:
    if len(fractals) < 2:
        return []

    strokes: list[Stroke] = []
    prev = fractals[0]
    for now in fractals[1:]:
        if now.kind == prev.kind:
            if now.kind == "top" and now.price >= prev.price:
                prev = now
            elif now.kind == "bottom" and now.price <= prev.price:
                prev = now
            continue

        direction = "up" if now.price > prev.price else "down"
        strokes.append(Stroke(start=prev, end=now, direction=direction))
        prev = now

    return strokes


def _build_pivots(strokes: list[Stroke]) -> list[PivotZone]:
    pivots: list[PivotZone] = []
    if len(strokes) < 3:
        return pivots

    for i in range(2, len(strokes)):
        s1, s2, s3 = strokes[i - 2], strokes[i - 1], strokes[i]
        high_overlap = min(s1.start.price, s1.end.price, s2.start.price, s2.end.price, s3.start.price, s3.end.price)
        low_overlap = max(s1.start.price, s1.end.price, s2.start.price, s2.end.price, s3.start.price, s3.end.price)

        if low_overlap < high_overlap:
            pivots.append(
                PivotZone(
                    low=low_overlap,
                    high=high_overlap,
                    start_ts=min(s1.start.timestamp, s1.end.timestamp),
                    end_ts=max(s3.start.timestamp, s3.end.timestamp),
                )
            )

    return pivots


def _infer_trend(strokes: list[Stroke]) -> str:
    if len(strokes) < 3:
        return "sideways"

    tail = strokes[-3:]
    up_count = sum(1 for s in tail if s.direction == "up")
    down_count = 3 - up_count
    if up_count >= 2:
        return "up"
    if down_count >= 2:
        return "down"
    return "sideways"


def _detect_signals(df: pd.DataFrame, strokes: list[Stroke], pivots: list[PivotZone]) -> list[BuySellSignal]:
    signals: list[BuySellSignal] = []
    if len(strokes) < 3:
        return signals

    last = strokes[-1]
    prev = strokes[-2]

    # Type-2: reversal confirmation after opposite stroke appears.
    if prev.direction == "down" and last.direction == "up" and last.end.price > prev.start.price:
        signals.append(
            BuySellSignal(
                signal="buy",
                signal_type=2,
                timestamp=last.end.timestamp,
                price=last.end.price,
                reason="下跌笔后出现向上确认笔并突破前一笔起点",
            )
        )
    if prev.direction == "up" and last.direction == "down" and last.end.price < prev.start.price:
        signals.append(
            BuySellSignal(
                signal="sell",
                signal_type=2,
                timestamp=last.end.timestamp,
                price=last.end.price,
                reason="上涨笔后出现向下确认笔并跌破前一笔起点",
            )
        )

    down_strokes = [s for s in strokes if s.direction == "down"]
    up_strokes = [s for s in strokes if s.direction == "up"]

    # Type-1: divergence-like exhaustion proxy.
    if len(down_strokes) >= 2:
        d1, d2 = down_strokes[-2], down_strokes[-1]
        amp1 = abs(d1.end.price - d1.start.price)
        amp2 = abs(d2.end.price - d2.start.price)
        if d2.end.price < d1.end.price and amp2 < amp1:
            signals.append(
                BuySellSignal(
                    signal="buy",
                    signal_type=1,
                    timestamp=d2.end.timestamp,
                    price=d2.end.price,
                    reason="创新低但下跌力度收敛，出现背驰近似特征",
                )
            )
    if len(up_strokes) >= 2:
        u1, u2 = up_strokes[-2], up_strokes[-1]
        amp1 = abs(u1.end.price - u1.start.price)
        amp2 = abs(u2.end.price - u2.start.price)
        if u2.end.price > u1.end.price and amp2 < amp1:
            signals.append(
                BuySellSignal(
                    signal="sell",
                    signal_type=1,
                    timestamp=u2.end.timestamp,
                    price=u2.end.price,
                    reason="创新高但上涨力度收敛，出现背驰近似特征",
                )
            )

    # Type-3: pivot breakout and pullback hold.
    if pivots:
        pivot = pivots[-1]
        closes = df["close"]
        if len(closes) >= 3:
            c1, c2, c3 = closes.iloc[-3], closes.iloc[-2], closes.iloc[-1]
            if c1 > pivot.high and c2 >= pivot.high and c3 > pivot.high:
                signals.append(
                    BuySellSignal(
                        signal="buy",
                        signal_type=3,
                        timestamp=pd.Timestamp(closes.index[-1]),
                        price=float(c3),
                        reason="向上离开中枢后回踩不破中枢上沿",
                    )
                )
            if c1 < pivot.low and c2 <= pivot.low and c3 < pivot.low:
                signals.append(
                    BuySellSignal(
                        signal="sell",
                        signal_type=3,
                        timestamp=pd.Timestamp(closes.index[-1]),
                        price=float(c3),
                        reason="向下离开中枢后反抽不过中枢下沿",
                    )
                )

    # Keep latest unique signals by (signal, type).
    dedup: dict[tuple[str, int], BuySellSignal] = {}
    for s in signals:
        dedup[(s.signal, s.signal_type)] = s
    return list(dedup.values())


def analyze_chan_structure(df: pd.DataFrame) -> ChanAnalysisResult:
    """A practical and simplified Chan-structure extraction pipeline."""
    fractals = _detect_fractals(df)
    strokes = _build_strokes(fractals)
    pivots = _build_pivots(strokes)
    signals = _detect_signals(df, strokes, pivots)
    trend = _infer_trend(strokes)
    return ChanAnalysisResult(
        fractals=fractals,
        strokes=strokes,
        pivots=pivots,
        signals=signals,
        trend=trend,
    )

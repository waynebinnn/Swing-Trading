from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go


def build_interactive_figure(
    df: pd.DataFrame,
    symbol: str,
    signals: list[dict] | None = None,
    pivot_reference: dict[str, float] | None = None,
    support_levels: list[float] | None = None,
    resistance_levels: list[float] | None = None,
) -> go.Figure:
    data = df.copy()
    data = data.sort_index()
    data = data[~data.index.duplicated(keep="last")]
    data = data.dropna(subset=["open", "high", "low", "close"])
    if len(data) > 600:
        data = data.tail(600).copy()

    data["ma5"] = data["close"].rolling(5).mean()
    data["ma10"] = data["close"].rolling(10).mean()
    data["ma20"] = data["close"].rolling(20).mean()
    data["ma60"] = data["close"].rolling(60).mean()

    latest = data.iloc[-1]

    def _fmt_ma(v: float) -> str:
        return f"{v:.3f}" if pd.notna(v) else "--"

    x_vals = pd.to_datetime(data.index)
    if len(x_vals) >= 2:
        step = x_vals.to_series().diff().median()
        if pd.isna(step) or step <= pd.Timedelta(0):
            x_pad = pd.Timedelta(days=1)
        else:
            x_pad = step / 2
    else:
        x_pad = pd.Timedelta(days=1)

    xaxis_range = [x_vals.min() - x_pad, x_vals.max() + x_pad]

    volume_vals = data["volume"].fillna(0.0).to_numpy()
    customdata = pd.DataFrame(
        {
            "vol": volume_vals,
            "ma5": data["ma5"],
            "ma10": data["ma10"],
            "ma20": data["ma20"],
            "ma60": data["ma60"],
        }
    ).to_numpy()

    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=x_vals,
            open=data["open"],
            high=data["high"],
            low=data["low"],
            close=data["close"],
            name="K线",
            showlegend=True,
            increasing={"line": {"color": "red"}, "fillcolor": "red"},
            decreasing={"line": {"color": "green"}, "fillcolor": "green"},
            customdata=customdata,
            hovertemplate=(
                "日期: %{x|%Y-%m-%d}<br>"
                "开盘: %{open:.3f}<br>"
                "最高: %{high:.3f}<br>"
                "最低: %{low:.3f}<br>"
                "收盘: %{close:.3f}<br>"
                "成交量: %{customdata[0]:,.0f}<extra>%{fullData.name}</extra>"
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=data["ma5"],
            mode="lines",
            line={"width": 1.0, "color": "#1f77b4"},
            name=f"MA5 {_fmt_ma(float(latest['ma5']))}",
            showlegend=True,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=data["ma10"],
            mode="lines",
            line={"width": 1.0, "color": "#ff7f0e"},
            name=f"MA10 {_fmt_ma(float(latest['ma10']))}",
            showlegend=True,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=data["ma20"],
            mode="lines",
            line={"width": 1.1, "color": "#2ca02c"},
            name=f"MA20 {_fmt_ma(float(latest['ma20']))}",
            showlegend=True,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=data["ma60"],
            mode="lines",
            line={"width": 1.2, "color": "#9467bd"},
            name=f"MA60 {_fmt_ma(float(latest['ma60']))}",
            showlegend=True,
            hoverinfo="skip",
        )
    )

    if pivot_reference:
        pivot_low = float(pivot_reference.get("low", 0.0))
        pivot_high = float(pivot_reference.get("high", 0.0))
        if pivot_low > 0:
            fig.add_hline(
                y=pivot_low,
                line_width=1,
                line_dash="dash",
                line_color="seagreen",
                annotation_text=f"中枢下沿 {pivot_low:.3f}",
                annotation_position="bottom right",
            )
        if pivot_high > 0:
            fig.add_hline(
                y=pivot_high,
                line_width=1,
                line_dash="dash",
                line_color="firebrick",
                annotation_text=f"中枢上沿 {pivot_high:.3f}",
                annotation_position="top right",
            )

    for idx, lv in enumerate(support_levels or []):
        y_val = float(lv)
        fig.add_hline(
            y=y_val,
            line_width=1,
            line_dash="dot",
            line_color="#2E8B57",
            annotation_text=f"支撑{idx + 1}: {y_val:.3f}",
            annotation_position="bottom left",
        )

    for idx, lv in enumerate(resistance_levels or []):
        y_val = float(lv)
        fig.add_hline(
            y=y_val,
            line_width=1,
            line_dash="dot",
            line_color="#B22222",
            annotation_text=f"压力{idx + 1}: {y_val:.3f}",
            annotation_position="top left",
        )

    buy_x = []
    buy_y = []
    sell_x = []
    sell_y = []
    for sig in signals or []:
        ts = pd.to_datetime(sig.get("timestamp"), errors="coerce")
        if pd.isna(ts):
            continue
        ts = _align_to_nearest_bar(pd.Timestamp(ts), x_vals)
        if ts is None:
            continue
        px = float(sig.get("price", 0.0))
        if px <= 0:
            continue
        if sig.get("signal") == "buy":
            buy_x.append(ts)
            buy_y.append(px)
        elif sig.get("signal") == "sell":
            sell_x.append(ts)
            sell_y.append(px)

    rangebreaks = _build_date_rangebreaks(x_vals)

    if buy_x:
        fig.add_trace(
            go.Scatter(
                x=buy_x,
                y=buy_y,
                mode="markers",
                marker={"symbol": "triangle-up", "size": 10, "color": "green"},
                name="买点",
            )
        )
    if sell_x:
        fig.add_trace(
            go.Scatter(
                x=sell_x,
                y=sell_y,
                mode="markers",
                marker={"symbol": "triangle-down", "size": 10, "color": "red"},
                name="卖点",
            )
        )

    fig.update_layout(
        title={"text": f"{symbol} 交互K线图（可缩放）", "x": 0.01, "xanchor": "left", "y": 0.98},
        xaxis_title="时间",
        yaxis_title="价格",
        xaxis_rangeslider_visible=True,
        xaxis={"type": "date", "rangebreaks": rangebreaks, "range": xaxis_range},
        dragmode="zoom",
        hovermode="x unified",
        template="plotly_white",
        legend={
            "orientation": "h",
            "y": 1.2,
            "x": 0,
            "yanchor": "bottom",
            "xanchor": "left",
            "bgcolor": "rgba(255,255,255,0.85)",
            "bordercolor": "rgba(0,0,0,0.2)",
            "borderwidth": 1,
            "font": {"size": 12},
            "entrywidth": 76,        # 每个图例固定宽度
            # "entrywidthmode": "fraction",  # 自适应分行

        },
        bargap=0.02,
        margin={"l": 40, "r": 40, "t": 165, "b": 40},
    )
    return fig


def _align_to_nearest_bar(ts: pd.Timestamp, index: pd.DatetimeIndex) -> pd.Timestamp | None:
    if len(index) == 0:
        return None

    if ts in index:
        return ts

    pos = index.get_indexer([ts], method="nearest")
    if len(pos) == 0 or pos[0] < 0:
        return None

    nearest = index[pos[0]]
    # Keep alignment strict enough to avoid crossing to unrelated periods.
    max_delta = pd.Timedelta(days=2)
    if abs(nearest - ts) > max_delta:
        return None
    return pd.Timestamp(nearest)


def _build_date_rangebreaks(index: pd.DatetimeIndex) -> list[dict]:
    if len(index) < 2:
        return []

    idx = pd.DatetimeIndex(index).sort_values()
    median_delta = (idx.to_series().diff().median())

    # Daily/longer series: hide weekends + missing calendar dates (holidays/suspensions).
    if pd.notna(median_delta) and median_delta >= pd.Timedelta(hours=12):
        start = idx.min().normalize()
        end = idx.max().normalize()
        full = pd.date_range(start=start, end=end, freq="D")
        existing = pd.DatetimeIndex(idx.normalize().unique())
        missing = full.difference(existing)

        breaks = [{"bounds": ["sat", "mon"]}]
        if len(missing) > 0:
            breaks.append({"values": [d.strftime("%Y-%m-%d") for d in missing]})
        return breaks

    # Intraday fallback: hide non-trading hours and weekends.
    return [{"bounds": ["sat", "mon"]}, {"bounds": [15.01, 9.29], "pattern": "hour"}]


def save_interactive_html(fig: go.Figure, output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(
        str(path),
        include_plotlyjs="cdn",
        post_script=_build_dynamic_yaxis_script(),
    )


def _build_dynamic_yaxis_script() -> str:
    # Auto-fit y-axis to visible candlesticks whenever the x-range changes.
    return """
var gd = document.getElementsByClassName('plotly-graph-div')[0];
if (!gd) {
    return;
}

var updatingY = false;
var updatingX = false;
var MIN_VISIBLE_BARS = 60;
var yFramePending = false;
var latestYEvent = null;
var lastXRange = [NaN, NaN];

function toMillis(v) {
    if (v === undefined || v === null) {
        return NaN;
    }
    var t = new Date(v).getTime();
    return Number.isNaN(t) ? NaN : t;
}

function cacheXRange(left, right) {
    if (Number.isNaN(left) || Number.isNaN(right)) {
        return;
    }
    if (right < left) {
        var t = left;
        left = right;
        right = t;
    }
    lastXRange = [left, right];
}

function getVisibleRange(evt) {
    var left = NaN;
    var right = NaN;

    if (evt && Array.isArray(evt['xaxis.range']) && evt['xaxis.range'].length === 2) {
        left = toMillis(evt['xaxis.range'][0]);
        right = toMillis(evt['xaxis.range'][1]);
        if (!Number.isNaN(left) && !Number.isNaN(right)) {
            cacheXRange(left, right);
            return [left, right];
        }
    }
    if (evt && evt['xaxis.range[0]'] !== undefined && evt['xaxis.range[1]'] !== undefined) {
        left = toMillis(evt['xaxis.range[0]']);
        right = toMillis(evt['xaxis.range[1]']);
        if (!Number.isNaN(left) && !Number.isNaN(right)) {
            cacheXRange(left, right);
            return [left, right];
        }
    }
    if (gd._fullLayout && gd._fullLayout.xaxis && Array.isArray(gd._fullLayout.xaxis.range) && gd._fullLayout.xaxis.range.length === 2) {
        left = toMillis(gd._fullLayout.xaxis.range[0]);
        right = toMillis(gd._fullLayout.xaxis.range[1]);
        if (!Number.isNaN(left) && !Number.isNaN(right)) {
            cacheXRange(left, right);
            return [left, right];
        }
    }
    if (gd.layout && gd.layout.xaxis && Array.isArray(gd.layout.xaxis.range) && gd.layout.xaxis.range.length === 2) {
        left = toMillis(gd.layout.xaxis.range[0]);
        right = toMillis(gd.layout.xaxis.range[1]);
        if (!Number.isNaN(left) && !Number.isNaN(right)) {
            cacheXRange(left, right);
            return [left, right];
        }
    }
    if (!Number.isNaN(lastXRange[0]) && !Number.isNaN(lastXRange[1])) {
        return [lastXRange[0], lastXRange[1]];
    }
    return [NaN, NaN];
}

function hasXRangeChange(evt) {
    if (!evt) {
        return false;
    }
    return (
        evt['xaxis.range[0]'] !== undefined ||
        evt['xaxis.range[1]'] !== undefined ||
        evt['xaxis.range'] !== undefined ||
        evt['xaxis.autorange'] !== undefined
    );
}

function getCandlestickTrace() {
    for (var i = 0; i < gd.data.length; i += 1) {
        var trace = gd.data[i];
        if (trace.type === 'candlestick') {
            return trace;
        }
    }
    return null;
}

function lowerBound(arr, target) {
    var lo = 0;
    var hi = arr.length;
    while (lo < hi) {
        var mid = (lo + hi) >> 1;
        if (arr[mid] < target) {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    return lo;
}

function upperBound(arr, target) {
    var lo = 0;
    var hi = arr.length;
    while (lo < hi) {
        var mid = (lo + hi) >> 1;
        if (arr[mid] <= target) {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    return lo;
}

function estimateHalfBarMs(xMs) {
    if (!xMs || xMs.length < 2) {
        return 12 * 60 * 60 * 1000;
    }

    var diffs = [];
    for (var i = 1; i < xMs.length; i += 1) {
        var d = xMs[i] - xMs[i - 1];
        if (d > 0 && Number.isFinite(d)) {
            diffs.push(d);
        }
    }
    if (diffs.length === 0) {
        return 12 * 60 * 60 * 1000;
    }

    diffs.sort(function(a, b) { return a - b; });
    var mid = Math.floor(diffs.length / 2);
    var median = diffs.length % 2 === 0 ? (diffs[mid - 1] + diffs[mid]) / 2 : diffs[mid];
    return Math.max(1, median / 2);
}

function enforceMinXSpan(evt) {
    if (updatingX) {
        return false;
    }

    var vr = getVisibleRange(evt);
    var left = vr[0];
    var right = vr[1];
    if (Number.isNaN(left) || Number.isNaN(right)) {
        return false;
    }
    if (right < left) {
        var tmp = left;
        left = right;
        right = tmp;
    }

    var trace = getCandlestickTrace();
    if (!trace || !trace.x || trace.x.length === 0) {
        return false;
    }

    var xMs = [];
    for (var i = 0; i < trace.x.length; i += 1) {
        var v = toMillis(trace.x[i]);
        if (!Number.isNaN(v)) {
            xMs.push(v);
        }
    }
    if (xMs.length === 0) {
        return false;
    }
    if (xMs.length <= MIN_VISIBLE_BARS) {
        return false;
    }

    var visibleCount = upperBound(xMs, right) - lowerBound(xMs, left);
    if (visibleCount >= MIN_VISIBLE_BARS) {
        return false;
    }

    var center = (left + right) / 2;
    var centerIdx = lowerBound(xMs, center);
    if (centerIdx >= xMs.length) {
        centerIdx = xMs.length - 1;
    } else if (centerIdx > 0 && Math.abs(xMs[centerIdx - 1] - center) <= Math.abs(xMs[centerIdx] - center)) {
        centerIdx = centerIdx - 1;
    }

    var half = Math.floor((MIN_VISIBLE_BARS - 1) / 2);
    var leftIdx = centerIdx - half;
    var rightIdx = leftIdx + MIN_VISIBLE_BARS - 1;

    if (leftIdx < 0) {
        leftIdx = 0;
        rightIdx = MIN_VISIBLE_BARS - 1;
    }
    if (rightIdx >= xMs.length) {
        rightIdx = xMs.length - 1;
        leftIdx = rightIdx - (MIN_VISIBLE_BARS - 1);
    }

    left = xMs[leftIdx];
    right = xMs[rightIdx];
    var halfBar = estimateHalfBarMs(xMs);
    var paddedLeft = left - halfBar;
    var paddedRight = right + halfBar;
    cacheXRange(paddedLeft, paddedRight);

    updatingX = true;
    var relayoutResult = Plotly.relayout(gd, {'xaxis.range': [new Date(paddedLeft), new Date(paddedRight)]});
    if (relayoutResult && typeof relayoutResult.then === 'function') {
        relayoutResult.then(function() {
            updatingX = false;
            recalcY(null);
        }).catch(function() {
            updatingX = false;
        });
    } else {
        updatingX = false;
        recalcY(null);
    }
    return true;
}

function recalcY(evt) {
    if (updatingY) {
        return;
    }

    var trace = getCandlestickTrace();
    if (!trace || !trace.x) {
        return;
    }

    // Plotly stores high/low as TypedArray wrappers: {_inputArray: Float64Array, ...}
    var high = trace.high && trace.high._inputArray ? trace.high._inputArray : trace.high;
    var low = trace.low && trace.low._inputArray ? trace.low._inputArray : trace.low;

    if (!high || !low) {
        return;
    }

    var vr = getVisibleRange(evt);
    var left = vr[0];
    var right = vr[1];
    var hasRange = !Number.isNaN(left) && !Number.isNaN(right);

    if (!hasRange) {
        return;
    }

    var minY = Infinity;
    var maxY = -Infinity;
    for (var j = 0; j < trace.x.length; j += 1) {
        var xMs = toMillis(trace.x[j]);
        if (hasRange && !Number.isNaN(xMs) && (xMs < left || xMs > right)) {
            continue;
        }
        var lo = Number(low[j]);
        var hi = Number(high[j]);
        if (!Number.isFinite(lo) || !Number.isFinite(hi)) {
            continue;
        }
        if (lo < minY) {
            minY = lo;
        }
        if (hi > maxY) {
            maxY = hi;
        }
    }

    if (!Number.isFinite(minY) || !Number.isFinite(maxY)) {
        return;
    }

    var span = maxY - minY;
    var pad = span > 0 ? span * 0.06 : Math.max(Math.abs(maxY) * 0.02, 0.01);
    var nextRange = [minY - pad, maxY + pad];

    var current = gd.layout && gd.layout.yaxis ? gd.layout.yaxis.range : null;
    if (Array.isArray(current) && current.length === 2) {
        var c0 = Number(current[0]);
        var c1 = Number(current[1]);
        if (Math.abs(c0 - nextRange[0]) < 1e-9 && Math.abs(c1 - nextRange[1]) < 1e-9) {
            return;
        }
    }

    updatingY = true;
    var relayoutResult = Plotly.relayout(gd, {'yaxis.range': nextRange});
    if (relayoutResult && typeof relayoutResult.then === 'function') {
        relayoutResult.then(function() {
            updatingY = false;
        }).catch(function() {
            updatingY = false;
        });
    } else {
        updatingY = false;
    }
}

function scheduleRecalcY(evt) {
    latestYEvent = evt || null;
    if (yFramePending) {
        return;
    }
    yFramePending = true;
    requestAnimationFrame(function() {
        yFramePending = false;
        recalcY(latestYEvent);
    });
}

gd.on('plotly_relayout', function(evt) {
    if (hasXRangeChange(evt)) {
        if (enforceMinXSpan(evt)) {
            return;
        }
        scheduleRecalcY(evt);
    }
});

gd.on('plotly_relayouting', function(evt) {
    if (hasXRangeChange(evt)) {
        if (enforceMinXSpan(evt)) {
            return;
        }
        scheduleRecalcY(evt);
    }
});

setTimeout(function() {
    recalcY(null);
}, 0);
"""
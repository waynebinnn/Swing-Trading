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

    x_vals = pd.to_datetime(data.index)
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
            increasing={"line": {"color": "red"}, "fillcolor": "red"},
            decreasing={"line": {"color": "green"}, "fillcolor": "green"},
            customdata=customdata,
            hovertemplate=(
                "日期: %{x|%Y-%m-%d}<br>"
                "开盘: %{open:.3f}<br>"
                "最高: %{high:.3f}<br>"
                "最低: %{low:.3f}<br>"
                "收盘: %{close:.3f}<br>"
                "成交量: %{customdata[0]:,.0f}<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=data["ma5"],
            mode="lines",
            line={"width": 1.0, "color": "#1f77b4"},
            name="MA5",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=data["ma10"],
            mode="lines",
            line={"width": 1.0, "color": "#ff7f0e"},
            name="MA10",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=data["ma20"],
            mode="lines",
            line={"width": 1.1, "color": "#2ca02c"},
            name="MA20",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=data["ma60"],
            mode="lines",
            line={"width": 1.2, "color": "#9467bd"},
            name="MA60",
            hoverinfo="skip",
        )
    )

    latest = data.iloc[-1]
    ma_label = (
        f"MA5 {latest['ma5']:.3f}  "
        f"MA10 {latest['ma10']:.3f}  "
        f"MA20 {latest['ma20']:.3f}  "
        f"MA60 {latest['ma60']:.3f}"
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
        fig.add_hline(
            y=float(lv),
            line_width=1,
            line_dash="dot",
            line_color="#2E8B57",
            annotation_text=f"支撑{idx + 1}: {float(lv):.3f}",
            annotation_position="bottom left",
        )

    for idx, lv in enumerate(resistance_levels or []):
        fig.add_hline(
            y=float(lv),
            line_width=1,
            line_dash="dot",
            line_color="#B22222",
            annotation_text=f"压力{idx + 1}: {float(lv):.3f}",
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
        title=f"{symbol} 交互K线图（可缩放）",
        xaxis_title="时间",
        yaxis_title="价格",
        xaxis_rangeslider_visible=True,
        xaxis={"type": "date", "rangebreaks": rangebreaks},
        dragmode="zoom",
        hovermode="x unified",
        template="plotly_white",
        legend={"orientation": "h", "y": 1.02, "x": 0},
        bargap=0.02,
        margin={"l": 40, "r": 30, "t": 70, "b": 40},
        annotations=[
            {
                "x": 0.01,
                "y": 0.99,
                "xref": "paper",
                "yref": "paper",
                "xanchor": "left",
                "yanchor": "top",
                "showarrow": False,
                "text": ma_label,
                "bgcolor": "rgba(255,255,255,0.75)",
                "bordercolor": "rgba(0,0,0,0.2)",
                "font": {"size": 11},
            }
        ],
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
    fig.write_html(str(path), include_plotlyjs="cdn")

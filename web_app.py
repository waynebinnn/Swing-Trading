from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from swingtrading_analyzer.planner import StrategyParams
from swingtrading_analyzer.workflow import run_multi_timeframe


st.set_page_config(page_title="Swing Trading 分析", page_icon="📈", layout="wide")

st.title("Swing Trading 自动分析")
st.caption("单版本输出：6个月日线，支持策略参数配置与可读报告导出")

with st.sidebar:
    st.header("参数设置")
    symbol = st.text_input("股票代码", value="002241", help="A股可用 002241 / 002241.SZ / 600519.SS")
    st.caption("策略参数")
    entry_band_pct = st.slider("入场带宽(%)", min_value=0.2, max_value=5.0, value=1.0, step=0.1) / 100.0
    stop_loss_pct = st.slider("止损比例(%)", min_value=0.2, max_value=8.0, value=1.5, step=0.1) / 100.0
    target_1_pct = st.slider("目标1比例(%)", min_value=0.5, max_value=12.0, value=3.0, step=0.1) / 100.0
    target_2_pct = st.slider("目标2比例(%)", min_value=1.0, max_value=20.0, value=6.0, step=0.1) / 100.0
    range_stop_loss_pct = st.slider("震荡止损(%)", min_value=0.5, max_value=10.0, value=2.0, step=0.1) / 100.0
    range_target_2_pct = st.slider("震荡目标2(%)", min_value=0.5, max_value=10.0, value=2.0, step=0.1) / 100.0

run = st.button("开始分析", type="primary")

if run:
    with st.spinner("正在拉取数据并进行分析..."):
        try:
            strategy_params = StrategyParams(
                entry_band_pct=entry_band_pct,
                stop_loss_pct=stop_loss_pct,
                target_1_pct=target_1_pct,
                target_2_pct=target_2_pct,
                range_stop_loss_pct=range_stop_loss_pct,
                range_target_2_pct=range_target_2_pct,
            )
            report = run_multi_timeframe(
                symbol=symbol.strip(),
                outdir="output",
                strategy_params=strategy_params,
            )
        except Exception as exc:
            st.error(f"分析失败: {exc}")
        else:
            st.success("分析完成")

            confluence = report["confluence"]
            main_plan = report["timeframes"]["main"]["plan"]
            levels = main_plan.get("key_levels", {})

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("观点", confluence["view"])
            c2.metric("趋势", report["timeframes"]["main"]["analysis"]["trend"])
            c3.metric("买点数", str(len(confluence.get("buy_types") or [])))
            c4.metric("卖点数", str(len(confluence.get("sell_types") or [])))

            tab_overview, tab_chart, tab_signals, tab_reports = st.tabs(["概览", "图表", "信号", "报告"])

            with tab_overview:
                st.subheader("综合结论")
                st.write(f"说明: {confluence['note']}")
                st.write(
                    f"买点类型: {confluence['buy_types'] or '无'} | "
                    f"卖点类型: {confluence['sell_types'] or '无'}"
                )
                if levels:
                    st.write("建议点位")
                    st.json(levels)

                op_plan = confluence.get("operation_plan", [])
                if op_plan:
                    st.write("未来操作建议")
                    for idx, item in enumerate(op_plan, start=1):
                        st.write(f"{idx}. {item}")

                st.write("策略参数")
                st.json(main_plan.get("strategy_parameters", {}))

            with tab_chart:
                for name, data in report["timeframes"].items():
                    st.markdown(f"### {name}")
                    st.write(f"趋势: {data['analysis']['trend']} | K线数量: {data['bars']}")
                    if data.get("fallback_note"):
                        st.warning(f"数据降级提示: {data['fallback_note']}")

                    html_path = Path(data["interactive_chart"])
                    if html_path.exists():
                        html_content = html_path.read_text(encoding="utf-8")
                        components.html(html_content, height=760, scrolling=True)
                    else:
                        st.warning("交互图文件不存在，请重新运行分析。")

            with tab_signals:
                for name, data in report["timeframes"].items():
                    st.markdown(f"### {name}")
                    st.write(
                        f"分型/笔/中枢: "
                        f"{data['analysis']['fractals']} / "
                        f"{data['analysis']['strokes']} / "
                        f"{data['analysis']['pivots']}"
                    )
                    signals = data["analysis"]["signals"]
                    if signals:
                        st.dataframe(signals, use_container_width=True)
                    else:
                        st.write("最新买卖点: 无")
                    plan = data.get("plan", {})
                    st.write(f"支撑位: {plan.get('support_levels', []) or '无'}")
                    st.write(f"压力位: {plan.get('resistance_levels', []) or '无'}")

            with tab_reports:
                report_path = Path(report["report_path"])
                readable_report_path = Path(report.get("readable_report_path", ""))
                st.write("JSON 报告")
                st.write(str(report_path))
                if report_path.exists():
                    st.download_button(
                        "下载 JSON 报告",
                        data=report_path.read_text(encoding="utf-8"),
                        file_name=report_path.name,
                        mime="application/json",
                    )

                st.write("可读摘要报告")
                st.write(str(readable_report_path))
                if readable_report_path.exists():
                    st.download_button(
                        "下载摘要报告(MD)",
                        data=readable_report_path.read_text(encoding="utf-8"),
                        file_name=readable_report_path.name,
                        mime="text/markdown",
                    )
                    with st.expander("预览摘要"):
                        st.markdown(readable_report_path.read_text(encoding="utf-8"))

                with st.expander("查看完整 JSON"):
                    st.code(json.dumps(report, ensure_ascii=False, indent=2), language="json")

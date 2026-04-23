from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from swingtrading_analyzer.workflow import run_multi_timeframe


st.set_page_config(page_title="多级别分析", page_icon="📈", layout="wide")

st.title("自动分析")
st.caption("单版本输出：6个月日线")

symbol = st.text_input("股票代码", value="002241", help="A股可用 002241 / 002241.SZ / 600519.SS")

run = st.button("开始分析", type="primary")

if run:
    with st.spinner("正在拉取数据并进行分析..."):
        try:
            report = run_multi_timeframe(symbol=symbol.strip(), outdir="output")
        except Exception as exc:
            st.error(f"分析失败: {exc}")
        else:
            st.success("分析完成")

            confluence = report["confluence"]
            st.subheader("综合结论")
            st.write(f"观点: {confluence['view']}")
            st.write(f"说明: {confluence['note']}")
            st.write(
                f"买点类型: {confluence['buy_types'] or '无'} | "
                f"卖点类型: {confluence['sell_types'] or '无'}"
            )
            levels = confluence.get("suggested_levels", {})
            if levels:
                st.write("建议点位:")
                st.json(levels)
            op_plan = confluence.get("operation_plan", [])
            if op_plan:
                st.write("未来操作建议:")
                for idx, item in enumerate(op_plan, start=1):
                    st.write(f"{idx}. {item}")


            st.subheader("分析结果")
            for name, data in report["timeframes"].items():
                st.markdown(f"### {name}")
                st.write(f"趋势: {data['analysis']['trend']}")
                st.write(f"K线数量: {data['bars']}")
                st.write(f"分型/笔/中枢: {data['analysis']['fractals']} / {data['analysis']['strokes']} / {data['analysis']['pivots']}")
                if data.get("fallback_note"):
                    st.warning(f"数据降级提示: {data['fallback_note']}")

                signals = data["analysis"]["signals"]
                if signals:
                    st.write("最新买卖点:")
                    st.dataframe(signals, use_container_width=True)
                else:
                    st.write("最新买卖点: 无")

                html_path = Path(data["interactive_chart"])
                if html_path.exists():
                    html_content = html_path.read_text(encoding="utf-8")
                    components.html(html_content, height=720, scrolling=True)
                else:
                    st.warning("交互图文件不存在，请重新运行分析。")

                plan = data.get("plan", {})
                st.write(f"支撑位: {plan.get('support_levels', []) or '无'}")
                st.write(f"压力位: {plan.get('resistance_levels', []) or '无'}")

            st.subheader("报告文件")
            report_path = Path(report["report_path"])
            st.write(str(report_path))
            if report_path.exists():
                st.download_button(
                    "下载 JSON 报告",
                    data=report_path.read_text(encoding="utf-8"),
                    file_name=report_path.name,
                    mime="application/json",
                )

            with st.expander("查看完整 JSON"):
                st.code(json.dumps(report, ensure_ascii=False, indent=2), language="json")

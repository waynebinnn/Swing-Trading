# 自动分析（波段场景）

本项目用于自动获取股票K线数据，进行简化结构识别并输出：

- 单版本分析：6个月日线
- 图表：交互K线图（HTML）
- 报告：当前趋势、买卖点（1/2/3类）和交易规划建议（JSON）

## 1. 环境准备

已创建 conda 环境：`swingtrading`（Python 3.12）

激活环境：

```bash
conda activate swingtrading
```

安装依赖：

```bash
pip install -r requirements.txt
```

## 2. 运行分析

在项目根目录执行：

```bash
PYTHONPATH=src python -m swingtrading_analyzer.cli --symbol 002241
```

示例（美股）：

```bash
PYTHONPATH=src python -m swingtrading_analyzer.cli --symbol AAPL
```

提示：A 股建议用 `600519.SS`、`000001.SZ` 或纯数字 `600519`，便于触发 akshare 回退。

以 `002241` 为例：

```bash
PYTHONPATH=src python -m swingtrading_analyzer.cli --symbol 002241
```

说明：已移除 `mode` 参数，默认执行当前唯一分析流程（6个月日线）。

## 3. Web界面

启动 Streamlit：

```bash
PYTHONPATH=src streamlit run web_app.py
```

## 4. 输出结果

输出在 `output/{symbol}/`：

- `{symbol}_main_data.csv`：原始数据（6个月日线）
- `{symbol}_main_interactive.html`：交互图（可缩放）
- `{symbol}_multi_plan.json`：分析报告（含点位与操作建议）

Web 页面直接加载 `*_main_interactive.html` 文件，因此与输出 HTML 图完全一致。

图中元素说明：

- K线颜色：红色上涨，绿色下跌（A股习惯）
- MA5/MA10/MA20/MA60：5/10/20/60日均线
- 绿色/红色虚线：最近中枢下沿/上沿
- 绿色上箭头：买点信号
- 红色下箭头：卖点信号

命令行和 JSON 会给出未来操作建议与点位：

- `entry_low` / `entry_high`：观察或分批介入区间
- `stop_loss`：失效止损位
- `target_1` / `target_2`：分批止盈目标位
- `support_levels`：支撑位水平线
- `resistance_levels`：压力位水平线

## 5. 说明

- 数据源默认使用 Yahoo Finance，若遇到限流会自动回退到 akshare（A股代码）。
- 已包含一二三类买卖点的简化识别规则，适合自动化初版。
- 若用于实盘，建议继续加强严格笔定义与背驰判定细则。

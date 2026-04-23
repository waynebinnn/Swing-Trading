from __future__ import annotations

import argparse
from .planner import StrategyParams
from .workflow import run_multi_timeframe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chan theory auto analysis")
    parser.add_argument("--symbol", required=True, help="Stock symbol, e.g. 600519.SS")
    parser.add_argument("--outdir", default="output", help="Base output directory")
    parser.add_argument("--entry-band-pct", type=float, default=0.01, help="Entry band percent")
    parser.add_argument("--stop-loss-pct", type=float, default=0.015, help="Stop loss percent")
    parser.add_argument("--target-1-pct", type=float, default=0.03, help="Target 1 percent")
    parser.add_argument("--target-2-pct", type=float, default=0.06, help="Target 2 percent")
    parser.add_argument("--range-stop-loss-pct", type=float, default=0.02, help="Sideways stop loss percent")
    parser.add_argument("--range-target-2-pct", type=float, default=0.02, help="Sideways second target percent")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    strategy_params = StrategyParams(
        entry_band_pct=args.entry_band_pct,
        stop_loss_pct=args.stop_loss_pct,
        target_1_pct=args.target_1_pct,
        target_2_pct=args.target_2_pct,
        range_stop_loss_pct=args.range_stop_loss_pct,
        range_target_2_pct=args.range_target_2_pct,
    )

    report = run_multi_timeframe(
        symbol=args.symbol,
        outdir=args.outdir,
        strategy_params=strategy_params,
    )
    print("Multi-timeframe analysis finished")
    print(f"Report: {report['report_path']}")
    print(f"Readable Report: {report.get('readable_report_path', '')}")
    for tf_name, tf_result in report["timeframes"].items():
        print(f"Interactive ({tf_name}): {tf_result['interactive_chart']}")
        print(f"MAs ({tf_name}): {tf_result.get('moving_averages', {})}")
    print(f"Confluence: {report['confluence']['view']}")
    levels = report["confluence"].get("suggested_levels", {})
    if levels:
        print(f"Levels: {levels}")
    main_plan = report["timeframes"]["main"]["plan"]
    print(f"Supports: {main_plan.get('support_levels', [])}")
    print(f"Resistances: {main_plan.get('resistance_levels', [])}")
    op_plan = report["confluence"].get("operation_plan", [])
    for idx, line in enumerate(op_plan, start=1):
        print(f"Step {idx}: {line}")


if __name__ == "__main__":
    main()

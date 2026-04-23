from __future__ import annotations

import argparse
from .workflow import run_multi_timeframe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chan theory auto analysis")
    parser.add_argument("--symbol", required=True, help="Stock symbol, e.g. 600519.SS")
    parser.add_argument("--outdir", default="output", help="Base output directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    report = run_multi_timeframe(symbol=args.symbol, outdir=args.outdir)
    print("Multi-timeframe analysis finished")
    print(f"Report: {report['report_path']}")
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

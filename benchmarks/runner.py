"""Benchmark runner: measures token reduction and filter timing per fixture scenario.

Usage:
    python -m benchmarks.runner [--fixture-only] [--category git] [--iterations 10]
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from pytk_ai.filters import filter_output
from pytk_ai.filters.base import (
    combine_command_streams,
    output_metrics,
)
from pytk_ai.plan import plan_command

from .scenarios import Scenario, discover_scenarios

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def benchmark_scenario(scenario: Scenario, *, iterations: int = 10) -> dict:
    data = scenario.load()
    stdout, stderr = data["stdout"], data["stderr"]
    plan = plan_command(scenario.command)

    # Warm-up
    filter_output(
        stdout=stdout,
        stderr=stderr,
        command=scenario.command,
        exit_code=scenario.exit_code,
        plan=plan,
    )

    timings_ms: list[float] = []
    result = None
    for _ in range(iterations):
        t0 = time.perf_counter()
        result = filter_output(
            command=scenario.command,
            stdout=stdout,
            stderr=stderr,
            exit_code=scenario.exit_code,
            plan=plan,
        )
        t1 = time.perf_counter()
        timings_ms.append((t1 - t0) * 1000)

    assert result is not None
    raw_text = combine_command_streams(stdout, stderr, scenario.exit_code)
    raw = output_metrics(raw_text)
    filtered = output_metrics(result.output)
    saved_tokens = raw.tokens - filtered.tokens
    saved_pct = ((saved_tokens / raw.tokens) * 100.0) if raw.tokens else 0.0

    return {
        "category": scenario.category,
        "name": scenario.name,
        "command": scenario.command,
        "filter_name": result.filter_name,
        "token_estimator": result.metrics.estimator if result.metrics else None,
        "raw_bytes": raw.chars,
        "filtered_bytes": filtered.chars,
        "raw_tokens": raw.tokens,
        "filtered_tokens": filtered.tokens,
        "saved_tokens": saved_tokens,
        "reduction_pct": round(saved_pct, 1),
        "mean_filter_ms": round(statistics.fmean(timings_ms), 3),
        "median_filter_ms": round(statistics.median(timings_ms), 3),
        "min_filter_ms": round(min(timings_ms), 3),
        "max_filter_ms": round(max(timings_ms), 3),
        "iterations": iterations,
    }


def run_benchmarks(
    *,
    category: str | None = None,
    iterations: int = 10,
) -> list[dict]:
    scenarios = discover_scenarios(category=category)
    results = []
    for scenario in scenarios:
        entry = benchmark_scenario(scenario, iterations=iterations)
        results.append(entry)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ptk-ai filter benchmarks")
    parser.add_argument(
        "--fixture-only",
        action="store_true",
        help="only run fixture-based benchmarks (no live commands)",
    )
    parser.add_argument("--category", type=str, default=None, help="filter by category")
    parser.add_argument(
        "--iterations", type=int, default=10, help="timing iterations per scenario"
    )
    parser.add_argument(
        "--output", type=str, default=None, help="output JSON file path"
    )
    args = parser.parse_args()

    results = run_benchmarks(category=args.category, iterations=args.iterations)

    output_path = Path(args.output) if args.output else RESULTS_DIR / "latest.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2) + "\n")

    # Print summary
    total_raw = sum(r["raw_tokens"] for r in results)
    total_filtered = sum(r["filtered_tokens"] for r in results)
    total_saved = total_raw - total_filtered
    overall_pct = ((total_saved / total_raw) * 100.0) if total_raw else 0.0

    print(f"Benchmarked {len(results)} scenarios")
    print(f"Total raw tokens: {total_raw:,}")
    print(f"Total filtered tokens: {total_filtered:,}")
    print(f"Total saved: {total_saved:,} ({overall_pct:.1f}%)")
    print(f"Results written to {output_path}")


if __name__ == "__main__":
    main()

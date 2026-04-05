"""Patch README.md with benchmark results between sentinel markers.

Usage:
    python -m benchmarks.update_readme [--dry-run] [--results path/to/latest.json]
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent / "results"
README_PATH = Path(__file__).resolve().parents[1] / "README.md"
START_MARKER = "<!-- BENCHMARK-START -->"
END_MARKER = "<!-- BENCHMARK-END -->"


def format_benchmark_tables(results: list[dict]) -> str:
    """Format benchmark results as markdown tables."""
    lines: list[str] = []
    lines.append("### Filter Benchmark Results\n")

    # Category summary table
    by_category: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_category[r["category"]].append(r)

    lines.append("#### By Category\n")
    lines.append(
        "| Category | Scenarios | Avg Raw Tokens | Avg Filtered | Avg Reduction |"
    )
    lines.append(
        "|----------|-----------|---------------|-------------|---------------|"
    )

    for cat in sorted(by_category):
        entries = by_category[cat]
        n = len(entries)
        avg_raw = sum(e["raw_tokens"] for e in entries) / n
        avg_filtered = sum(e["filtered_tokens"] for e in entries) / n
        avg_pct = sum(e["reduction_pct"] for e in entries) / n
        lines.append(
            f"| {cat} | {n} | {avg_raw:,.0f} | {avg_filtered:,.0f} | {avg_pct:.1f}% |"
        )

    total_raw = sum(r["raw_tokens"] for r in results)
    total_filtered = sum(r["filtered_tokens"] for r in results)
    total_saved = total_raw - total_filtered
    overall_pct = ((total_saved / total_raw) * 100.0) if total_raw else 0.0
    lines.append(f"| **Total** | **{len(results)}** | | | **{overall_pct:.1f}%** |")

    # Top individual filters by reduction
    lines.append("\n#### Top Filters by Token Reduction\n")
    lines.append("| Filter | Command | Raw | Filtered | Saved | Reduction |")
    lines.append("|--------|---------|-----|----------|-------|-----------|")

    sorted_results = sorted(results, key=lambda r: r["reduction_pct"], reverse=True)
    for r in sorted_results[:15]:
        cmd = r["command"]
        if len(cmd) > 40:
            cmd = cmd[:37] + "..."
        lines.append(
            f"| {r['filter_name']} | `{cmd}` | {r['raw_tokens']:,} | {r['filtered_tokens']:,} "
            f"| {r['saved_tokens']:,} | {r['reduction_pct']}% |"
        )

    lines.append("")
    return "\n".join(lines)


def patch_readme(
    tables: str,
    *,
    readme_path: Path = README_PATH,
    dry_run: bool = False,
) -> str:
    content = readme_path.read_text()

    start_idx = content.find(START_MARKER)
    end_idx = content.find(END_MARKER)
    if start_idx == -1 or end_idx == -1:
        raise ValueError(
            f"README.md missing sentinel markers ({START_MARKER} / {END_MARKER})"
        )

    new_content = (
        content[: start_idx + len(START_MARKER)]
        + "\n\n"
        + tables
        + "\n"
        + content[end_idx:]
    )

    if dry_run:
        return new_content

    readme_path.write_text(new_content)
    return new_content


def main() -> None:
    parser = argparse.ArgumentParser(description="Update README with benchmark results")
    parser.add_argument(
        "--dry-run", action="store_true", help="print output without writing"
    )
    parser.add_argument(
        "--results", type=str, default=None, help="path to results JSON"
    )
    args = parser.parse_args()

    results_path = Path(args.results) if args.results else RESULTS_DIR / "latest.json"
    if not results_path.exists():
        print(f"No results file found at {results_path}. Run benchmarks first.")
        return

    results = json.loads(results_path.read_text())
    tables = format_benchmark_tables(results)

    if args.dry_run:
        print(tables)
    else:
        patch_readme(tables)
        print(f"README.md updated with {len(results)} benchmark results.")


if __name__ == "__main__":
    main()

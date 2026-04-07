"""Patch README.md with v2 benchmark results between sentinel markers.

Usage:
    python -m benchmarks.update_readme [--dry-run] [--results path/to/latest.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent / "results"
README_PATH = Path(__file__).resolve().parents[1] / "README.md"
START_MARKER = "<!-- BENCHMARK-START -->"
END_MARKER = "<!-- BENCHMARK-END -->"
SCENARIO_COMPARISON_LIMIT = 25


def load_results_document(results_path: Path) -> dict:
    document = json.loads(results_path.read_text())
    if not isinstance(document, dict):
        raise ValueError("benchmark results must be a JSON object")
    if document.get("schema_version") != 2:
        raise ValueError("benchmark results must use schema_version 2")
    results = document.get("results")
    if not isinstance(results, list):
        raise ValueError("benchmark results must include a results array")
    return document


def _truncate_command(command: str, limit: int = 40) -> str:
    if len(command) <= limit:
        return command
    return command[: limit - 3] + "..."


def _comparable_rows(document: dict, *, engine: str | None = None) -> list[dict]:
    results = [row for row in document["results"] if row["status"] == "ok"]
    if engine is not None:
        results = [row for row in results if row["engine"] == engine]
    return results


def _rows_by_key(document: dict) -> dict[tuple[str, str, str], dict[str, dict]]:
    grouped: dict[tuple[str, str, str], dict[str, dict]] = {}
    for row in document["results"]:
        key = (row["category"], row["name"], row["command"])
        grouped.setdefault(key, {})[row["engine"]] = row
    return grouped


def _category_rows(document: dict) -> list[str]:
    grouped = _rows_by_key(document)
    categories = sorted({key[0] for key in grouped})

    lines = ["#### By Category\n"]
    lines.append(
        "| Category | Scenarios | Avg Raw Tokens | PYTK Avg Filtered | PYTK Avg Reduction | RTK Coverage | RTK Avg Filtered | RTK Avg Reduction |"
    )
    lines.append(
        "|----------|-----------|----------------|-------------------|--------------------|--------------|------------------|-------------------|"
    )

    for category in categories:
        entries = [
            engines for (cat, _, _), engines in grouped.items() if cat == category
        ]
        scenario_count = len(entries)
        pytk_rows = [
            entry["pytk"]
            for entry in entries
            if entry.get("pytk", {}).get("status") == "ok"
        ]
        rtk_rows = [
            entry["rtk"]
            for entry in entries
            if entry.get("rtk", {}).get("status") == "ok"
        ]

        avg_raw = (
            sum(row["raw_tokens"] for row in pytk_rows) / len(pytk_rows)
            if pytk_rows
            else 0.0
        )
        pytk_filtered = (
            sum(row["filtered_tokens"] for row in pytk_rows) / len(pytk_rows)
            if pytk_rows
            else 0.0
        )
        pytk_raw_total = sum(row["raw_tokens"] for row in pytk_rows)
        pytk_filtered_total = sum(row["filtered_tokens"] for row in pytk_rows)
        pytk_pct = (
            ((pytk_raw_total - pytk_filtered_total) / pytk_raw_total) * 100.0
            if pytk_raw_total
            else 0.0
        )
        rtk_filtered = (
            sum(row["filtered_tokens"] for row in rtk_rows) / len(rtk_rows)
            if rtk_rows
            else 0.0
        )
        rtk_raw_total = sum(row["raw_tokens"] for row in rtk_rows)
        rtk_filtered_total = sum(row["filtered_tokens"] for row in rtk_rows)
        rtk_pct = (
            ((rtk_raw_total - rtk_filtered_total) / rtk_raw_total) * 100.0
            if rtk_raw_total
            else 0.0
        )
        lines.append(
            f"| {category} | {scenario_count} | {avg_raw:,.0f} | {pytk_filtered:,.0f} | "
            f"{pytk_pct:.1f}% | {len(rtk_rows)}/{scenario_count} | {rtk_filtered:,.0f} | {rtk_pct:.1f}% |"
        )

    pytk_total = _comparable_rows(document, engine="pytk")
    rtk_total = _comparable_rows(document, engine="rtk")
    total_scenarios = len(grouped)
    total_raw = (
        sum(row["raw_tokens"] for row in pytk_total) / len(pytk_total)
        if pytk_total
        else 0.0
    )
    pytk_total_filtered = (
        sum(row["filtered_tokens"] for row in pytk_total) / len(pytk_total)
        if pytk_total
        else 0.0
    )
    pytk_total_raw = sum(row["raw_tokens"] for row in pytk_total)
    pytk_total_filtered_sum = sum(row["filtered_tokens"] for row in pytk_total)
    pytk_total_pct = (
        ((pytk_total_raw - pytk_total_filtered_sum) / pytk_total_raw) * 100.0
        if pytk_total_raw
        else 0.0
    )
    rtk_total_filtered = (
        sum(row["filtered_tokens"] for row in rtk_total) / len(rtk_total)
        if rtk_total
        else 0.0
    )
    rtk_total_raw = sum(row["raw_tokens"] for row in rtk_total)
    rtk_total_filtered_sum = sum(row["filtered_tokens"] for row in rtk_total)
    rtk_total_pct = (
        ((rtk_total_raw - rtk_total_filtered_sum) / rtk_total_raw) * 100.0
        if rtk_total_raw
        else 0.0
    )
    lines.append(
        f"| **Total** | **{total_scenarios}** | **{total_raw:,.0f}** | **{pytk_total_filtered:,.0f}** | "
        f"**{pytk_total_pct:.1f}%** | **{len(rtk_total)}/{total_scenarios}** | "
        f"**{rtk_total_filtered:,.0f}** | **{rtk_total_pct:.1f}%** |"
    )
    return lines


def _scenario_rows(document: dict) -> list[str]:
    lines = [f"\n#### Scenario Comparison (Top {SCENARIO_COMPARISON_LIMIT})\n"]
    lines.append(
        "| Scenario | Command | Raw | PYTK | PYTK Red. | RTK | RTK Red. | Winner |"
    )
    lines.append(
        "|----------|---------|-----|------|-----------|-----|----------|--------|"
    )

    comparable: list[tuple[float, dict, dict]] = []
    for _, engines in _rows_by_key(document).items():
        pytk = engines.get("pytk")
        rtk = engines.get("rtk")
        if not pytk or not rtk:
            continue
        if pytk["status"] != "ok" or rtk["status"] != "ok":
            continue
        delta = abs((pytk["reduction_pct"] or 0.0) - (rtk["reduction_pct"] or 0.0))
        comparable.append((delta, pytk, rtk))

    comparable.sort(
        key=lambda item: (
            item[0],
            item[1]["raw_tokens"],
            item[1]["saved_tokens"],
        ),
        reverse=True,
    )

    for _, pytk, rtk in comparable[:SCENARIO_COMPARISON_LIMIT]:
        delta = (pytk["reduction_pct"] or 0.0) - (rtk["reduction_pct"] or 0.0)
        if abs(delta) < 0.05:
            winner = "Tie"
        elif delta > 0:
            winner = f"PYTK +{delta:.1f}pp"
        else:
            winner = f"RTK +{abs(delta):.1f}pp"
        lines.append(
            f"| {pytk['category']}/{pytk['name']} | `{_truncate_command(pytk['command'])}` | "
            f"{pytk['raw_tokens']:,} | {pytk['filtered_tokens']:,} | {pytk['reduction_pct']:.1f}% | "
            f"{rtk['filtered_tokens']:,} | {rtk['reduction_pct']:.1f}% | {winner} |"
        )

    return lines


def format_benchmark_tables(document: dict) -> str:
    lines: list[str] = []
    lines.append("### Filter Benchmark Results\n")
    lines.append(f"Token estimator: `{document['token_estimator']}`\n")
    if document.get("rtk_version"):
        lines.append(f"Compared against `{document['rtk_version']}`\n")
    lines.extend(_category_rows(document))
    lines.extend(_scenario_rows(document))
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

    document = load_results_document(results_path)
    tables = format_benchmark_tables(document)

    if args.dry_run:
        print(tables)
    else:
        patch_readme(tables)
        print(f"README.md updated with {len(document['results'])} benchmark rows.")


if __name__ == "__main__":
    main()

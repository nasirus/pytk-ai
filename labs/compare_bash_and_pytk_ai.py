from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pytk_ai.filters import filter_output  # noqa: E402
from pytk_ai.plan import plan_command  # noqa: E402
from pytk_ai.runner import run_command  # noqa: E402


class Scenario(NamedTuple):
    title: str
    command: str
    cwd: Path = PROJECT_ROOT


class TimingStats(NamedTuple):
    mean_ms: float
    median_ms: float
    min_ms: float
    max_ms: float
    stdev_ms: float


class OutputStats(NamedTuple):
    chars: int
    lines: int
    tokens: int


class BenchmarkResult(NamedTuple):
    title: str
    command: str
    cwd: Path
    bash_timing: TimingStats
    pytk_ai_timing: TimingStats
    bash_output: OutputStats
    pytk_ai_output: OutputStats


class FilterSampleScenario(NamedTuple):
    family: str
    title: str
    command: str
    stdout: str
    stderr: str = ""
    exit_code: int = 0


class FilterSampleResult(NamedTuple):
    family: str
    title: str
    command: str
    filter_name: str
    policy: str
    raw_output: OutputStats
    filtered_output: OutputStats
    saved_tokens: int
    saved_pct: float


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(title="List repository root", command="ls"),
    Scenario(title="List PYTK-AI package files", command="ls src/pytk_ai"),
    Scenario(
        title="Grep PYTK-AI mentions in README", command="grep -n 'pytk-ai' README.md"
    ),
    Scenario(title="Show tracked git status", command="git status --short"),
    Scenario(title="Show latest git commit", command="git log -1 --oneline"),
    Scenario(
        title="Print a simple file-manipulation pipeline",
        command="ls src/pytk_ai | grep '\\.py$'",
    ),
    Scenario(
        title="Collapse highly repetitive output",
        command="yes 'same line' | head -n 10",
    ),
)

FILTER_SAMPLE_SCENARIOS: tuple[FilterSampleScenario, ...] = (
    FilterSampleScenario(
        family="git",
        title="git diff patch trimming",
        command="git diff -- src/app.py",
        stdout=(
            "diff --git a/src/app.py b/src/app.py\n"
            "index 1234567..89abcde 100644\n"
            "--- a/src/app.py\n"
            "+++ b/src/app.py\n"
            "@@ -1,8 +1,10 @@\n"
            "-old line\n"
            "+new line\n"
            " context 1\n"
            " context 2\n"
            " context 3\n"
            " context 4\n"
            " context 5\n"
            " context 6\n"
            " context 7\n"
            " context 8\n"
        ),
    ),
    FilterSampleScenario(
        family="tests",
        title="cargo test failure grouping",
        command="cargo test",
        stdout=(
            "running 3 tests\n"
            "test parser::ok_case ... ok\n"
            "test parser::bad_case ... FAILED\n"
            "test parser::other_case ... ok\n\n"
            "failures:\n\n"
            "---- parser::bad_case stdout ----\n"
            "thread 'parser::bad_case' panicked at src/lib.rs:42:9:\n"
            "assertion `left == right` failed\n"
            "left: 1\n"
            "right: 2\n\n"
            "failures:\n"
            "    parser::bad_case\n\n"
            "test result: FAILED. 2 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out\n"
        ),
        exit_code=101,
    ),
    FilterSampleScenario(
        family="build",
        title="next build route summary",
        command="next build",
        stdout=(
            "Route (app)                              Size     First Load JS\n"
            "┌ ○ /                                    180 B           102 kB\n"
            "├ ○ /_not-found                          902 B           103 kB\n"
            "├ ƒ /api/health                          150 B           101 kB\n"
            "├ ƒ /dashboard                           3.25 kB         120 kB\n"
            "├ ƒ /dashboard/settings                  2.98 kB         119 kB\n"
            "├ ƒ /projects/[id]                       4.10 kB         124 kB\n"
            "└ ○ /signin                              1.85 kB         110 kB\n"
            "+ First Load JS shared by all            101 kB\n"
        ),
    ),
    FilterSampleScenario(
        family="files",
        title="tail repeated log spam",
        command="tail -n 20 app.log",
        stdout=(
            "INFO worker started\n"
            "INFO worker started\n"
            "INFO worker started\n"
            "INFO worker started\n"
            "INFO worker started\n"
            "INFO worker started\n"
            "INFO worker started\n"
            "INFO worker started\n"
            "WARN retrying request\n"
            "WARN retrying request\n"
            "WARN retrying request\n"
            "ERROR failed to reach upstream\n"
            "ERROR failed to reach upstream\n"
            "ERROR failed to reach upstream\n"
            "ERROR failed to reach upstream\n"
        ),
    ),
    FilterSampleScenario(
        family="packages",
        title="pip outdated package table",
        command="pip list --outdated",
        stdout=(
            "Package    Version Latest Type\n"
            "---------- ------- ------ -----\n"
            "httpx      0.27.0  0.28.1 wheel\n"
            "pydantic   2.8.0   2.9.2  wheel\n"
        ),
    ),
    FilterSampleScenario(
        family="infra",
        title="docker ps compact listing",
        command="docker ps",
        stdout=(
            "CONTAINER ID   IMAGE               COMMAND                  CREATED         STATUS         PORTS                    NAMES\n"
            'abc123def456   postgres:16         "docker-entrypoint.s…"   2 hours ago     Up 2 hours     0.0.0.0:5432->5432/tcp   db\n'
            'fedcba654321   redis:7             "docker-entrypoint.s…"   90 minutes ago  Up 90 minutes  0.0.0.0:6379->6379/tcp   cache\n'
        ),
    ),
    FilterSampleScenario(
        family="github-api",
        title="gh pr list default table",
        command="gh pr list",
        stdout=(
            "Showing 2 of 2 open pull requests in org/repo\n\n"
            "#14  fix parser edge cases     main <- fix/parser   OPEN   2026-04-05\n"
            "#12  add benchmark reporting   main <- feat/bench   OPEN   2026-04-04\n"
        ),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare bash subprocess output against PYTK-AI output."
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="run repeated timing and token-savings benchmarks",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="number of timed runs per benchmark scenario",
    )
    parser.add_argument(
        "--filter-benchmarks",
        action="store_true",
        help="run deterministic sample-based filter benchmarks across filter families",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format for benchmark reports",
    )
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be >= 1")
    return args


def run_bash(
    command: str, *, cwd: Path = PROJECT_ROOT
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-lc", command],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
    )


def show_section(title: str, content: str) -> None:
    print(title)
    if content:
        print(content, end="" if content.endswith("\n") else "\n")
    else:
        print("<empty>")


def combine_streams(stdout: str, stderr: str, exit_code: int) -> str:
    stdout = stdout.rstrip()
    stderr = stderr.rstrip()
    if exit_code == 0:
        parts = [part for part in (stdout, stderr) if part]
    else:
        parts = [part for part in (stderr, stdout) if part]
    return "\n".join(parts)


@lru_cache(maxsize=1)
def _load_token_encoder():
    try:
        import tiktoken  # type: ignore
    except ImportError:
        return None
    return tiktoken.get_encoding("cl100k_base")


def token_estimator_label() -> str:
    return "cl100k_base" if _load_token_encoder() is not None else "chars/4 estimate"


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    encoder = _load_token_encoder()
    if encoder is not None:
        return len(encoder.encode(text))
    return max(1, math.ceil(len(text) / 4))


def measure_timing(samples_ms: list[float]) -> TimingStats:
    return TimingStats(
        mean_ms=statistics.fmean(samples_ms),
        median_ms=statistics.median(samples_ms),
        min_ms=min(samples_ms),
        max_ms=max(samples_ms),
        stdev_ms=statistics.pstdev(samples_ms) if len(samples_ms) > 1 else 0.0,
    )


def output_stats(text: str) -> OutputStats:
    return OutputStats(
        chars=len(text),
        lines=0 if not text else len(text.splitlines()),
        tokens=estimate_tokens(text),
    )


def compare_outputs() -> None:
    for index, scenario in enumerate(SCENARIOS, start=1):
        bash_result = run_bash(scenario.command, cwd=scenario.cwd)
        pytk_ai_result = run_command(scenario.command, cwd=str(scenario.cwd))
        bash_combined = combine_streams(
            bash_result.stdout,
            bash_result.stderr,
            bash_result.returncode,
        )
        bash_stats = output_stats(bash_combined)
        pytk_ai_stats = output_stats(pytk_ai_result.filtered_output)
        saved_tokens = bash_stats.tokens - pytk_ai_stats.tokens
        saved_pct = (
            (saved_tokens / bash_stats.tokens) * 100 if bash_stats.tokens else 0.0
        )

        print(f"Scenario {index}: {scenario.title}")
        print(f"Command: {scenario.command}")
        print(
            "Estimated token savings:"
            f" {bash_stats.tokens} -> {pytk_ai_stats.tokens}"
            f" ({saved_tokens} saved, {format_percent(saved_pct)})"
        )
        print()
        print("=== bash subprocess ===")
        print(f"exit_code: {bash_result.returncode}")
        show_section("stdout:", bash_result.stdout)
        show_section("stderr:", bash_result.stderr)
        print(
            "combined_output_stats:"
            f" {bash_stats.lines} line(s), {bash_stats.chars} char(s),"
            f" {bash_stats.tokens} token(s)"
        )
        print()
        print("=== pytk-ai ===")
        print(f"exit_code: {pytk_ai_result.exit_code}")
        print(f"executed_command: {pytk_ai_result.executed_command}")
        print(f"planned_command: {pytk_ai_result.planned_command}")
        print(f"managed: {pytk_ai_result.managed}")
        show_section("filtered_output:", pytk_ai_result.filtered_output)
        show_section("stdout:", pytk_ai_result.stdout)
        show_section("stderr:", pytk_ai_result.stderr)
        print(
            "filtered_output_stats:"
            f" {pytk_ai_stats.lines} line(s), {pytk_ai_stats.chars} char(s),"
            f" {pytk_ai_stats.tokens} token(s)"
        )
        if index != len(SCENARIOS):
            print("\n" + "=" * 72 + "\n")


def create_benchmark_workspace() -> tuple[
    tempfile.TemporaryDirectory[str], tuple[Scenario, ...]
]:
    temp_dir = tempfile.TemporaryDirectory(prefix="pytk-ai-bench-")
    root = Path(temp_dir.name)

    ls_dir = root / "ls_bench"
    ls_dir.mkdir()
    for index in range(500):
        (ls_dir / f"file_{index:04d}.txt").write_text(f"payload {index}\n")

    find_dir = root / "find_bench"
    for group in range(12):
        subdir = find_dir / f"group_{group:02d}"
        subdir.mkdir(parents=True, exist_ok=True)
        for index in range(55):
            file_index = group * 55 + index
            (subdir / f"item_{file_index:04d}.txt").write_text(
                f"find payload {file_index}\n"
            )

    repo_dir = root / "git_bench"
    repo_dir.mkdir()
    run_bash("git init -q", cwd=repo_dir)
    run_bash('git config user.email "pytk-ai-bench@example.com"', cwd=repo_dir)
    run_bash('git config user.name "PYTK-AI Bench"', cwd=repo_dir)
    tracked_file = repo_dir / "tracked.txt"
    tracked_file.write_text("original\n")
    run_bash("git add tracked.txt", cwd=repo_dir)
    run_bash('git commit -qm "bench init"', cwd=repo_dir)
    tracked_file.write_text("modified\n")
    for index in range(260):
        (repo_dir / f"scratch_{index:04d}.txt").write_text(f"untracked {index}\n")

    scenarios = (
        Scenario(
            title="Large ls -l listing",
            command="ls -l ls_bench",
            cwd=root,
        ),
        Scenario(
            title="Large find listing",
            command="find find_bench -type f",
            cwd=root,
        ),
        Scenario(
            title="Verbose git status",
            command="git status",
            cwd=repo_dir,
        ),
    )
    return temp_dir, scenarios


def time_bash(
    command: str, *, cwd: Path, iterations: int
) -> tuple[TimingStats, OutputStats]:
    durations_ms: list[float] = []
    latest_output = ""
    run_bash(command, cwd=cwd)
    for _ in range(iterations):
        started = time.perf_counter_ns()
        result = run_bash(command, cwd=cwd)
        durations_ms.append((time.perf_counter_ns() - started) / 1_000_000)
        latest_output = combine_streams(result.stdout, result.stderr, result.returncode)
    return measure_timing(durations_ms), output_stats(latest_output)


def time_pytk_ai(
    command: str, *, cwd: Path, iterations: int
) -> tuple[TimingStats, OutputStats]:
    durations_ms: list[float] = []
    latest_output = ""
    run_command(command, cwd=str(cwd))
    for _ in range(iterations):
        started = time.perf_counter_ns()
        result = run_command(command, cwd=str(cwd))
        durations_ms.append((time.perf_counter_ns() - started) / 1_000_000)
        latest_output = result.filtered_output
    return measure_timing(durations_ms), output_stats(latest_output)


def benchmark_scenarios(iterations: int) -> list[BenchmarkResult]:
    workspace, scenarios = create_benchmark_workspace()
    try:
        results: list[BenchmarkResult] = []
        for scenario in scenarios:
            bash_timing, bash_output = time_bash(
                scenario.command,
                cwd=scenario.cwd,
                iterations=iterations,
            )
            pytk_ai_timing, pytk_ai_output = time_pytk_ai(
                scenario.command,
                cwd=scenario.cwd,
                iterations=iterations,
            )
            results.append(
                BenchmarkResult(
                    title=scenario.title,
                    command=scenario.command,
                    cwd=scenario.cwd,
                    bash_timing=bash_timing,
                    pytk_ai_timing=pytk_ai_timing,
                    bash_output=bash_output,
                    pytk_ai_output=pytk_ai_output,
                )
            )
        return results
    finally:
        workspace.cleanup()


def benchmark_filter_samples() -> list[FilterSampleResult]:
    results: list[FilterSampleResult] = []
    for scenario in FILTER_SAMPLE_SCENARIOS:
        result = filter_output(
            scenario.command,
            scenario.stdout,
            scenario.stderr,
            scenario.exit_code,
            plan=plan_command(scenario.command),
        )
        metrics = result.metrics
        if metrics is None:
            continue
        results.append(
            FilterSampleResult(
                family=scenario.family,
                title=scenario.title,
                command=scenario.command,
                filter_name=result.filter_name or "unknown",
                policy=(result.policy.summary_scope if result.policy else "unknown"),
                raw_output=OutputStats(
                    chars=metrics.raw.chars,
                    lines=metrics.raw.lines,
                    tokens=metrics.raw.tokens,
                ),
                filtered_output=OutputStats(
                    chars=metrics.filtered.chars,
                    lines=metrics.filtered.lines,
                    tokens=metrics.filtered.tokens,
                ),
                saved_tokens=metrics.saved_tokens,
                saved_pct=metrics.saved_pct,
            )
        )
    return results


def format_percent(value: float) -> str:
    return f"{value:.1f}%"


def format_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def render_row(row: tuple[str, ...]) -> str:
        return " | ".join(value.ljust(widths[index]) for index, value in enumerate(row))

    divider = "-+-".join("-" * width for width in widths)
    return "\n".join([render_row(headers), divider, *(render_row(row) for row in rows)])


def print_benchmark_report(results: list[BenchmarkResult], *, iterations: int) -> None:
    rows: list[tuple[str, ...]] = []
    total_bash_tokens = 0
    total_pytk_ai_tokens = 0
    total_bash_mean = 0.0
    total_pytk_ai_mean = 0.0

    for result in results:
        saved_tokens = result.bash_output.tokens - result.pytk_ai_output.tokens
        saved_pct = (
            (saved_tokens / result.bash_output.tokens) * 100
            if result.bash_output.tokens
            else 0.0
        )
        perf_delta_ms = result.pytk_ai_timing.mean_ms - result.bash_timing.mean_ms
        perf_delta_pct = (
            (perf_delta_ms / result.bash_timing.mean_ms) * 100
            if result.bash_timing.mean_ms
            else 0.0
        )
        rows.append(
            (
                result.title,
                f"{result.bash_timing.mean_ms:.2f}",
                f"{result.pytk_ai_timing.mean_ms:.2f}",
                f"{perf_delta_ms:+.2f}",
                format_percent(perf_delta_pct),
                str(result.bash_output.tokens),
                str(result.pytk_ai_output.tokens),
                str(saved_tokens),
                format_percent(saved_pct),
            )
        )
        total_bash_tokens += result.bash_output.tokens
        total_pytk_ai_tokens += result.pytk_ai_output.tokens
        total_bash_mean += result.bash_timing.mean_ms
        total_pytk_ai_mean += result.pytk_ai_timing.mean_ms

    total_saved_tokens = total_bash_tokens - total_pytk_ai_tokens
    total_saved_pct = (
        (total_saved_tokens / total_bash_tokens) * 100 if total_bash_tokens else 0.0
    )
    total_perf_delta_ms = total_pytk_ai_mean - total_bash_mean
    total_perf_delta_pct = (
        (total_perf_delta_ms / total_bash_mean) * 100 if total_bash_mean else 0.0
    )
    rows.append(
        (
            "TOTAL",
            f"{total_bash_mean:.2f}",
            f"{total_pytk_ai_mean:.2f}",
            f"{total_perf_delta_ms:+.2f}",
            format_percent(total_perf_delta_pct),
            str(total_bash_tokens),
            str(total_pytk_ai_tokens),
            str(total_saved_tokens),
            format_percent(total_saved_pct),
        )
    )

    print(f"Benchmark iterations per scenario: {iterations}")
    print(f"Token estimator: {token_estimator_label()}")
    print(
        "Runtime note: bash timings use `bash -lc`; PYTK-AI timings use `run_command`,"
        " so this measures end-to-end wrapper cost rather than isolated filter overhead."
    )
    print()
    print(
        format_table(
            (
                "scenario",
                "bash ms",
                "pytk-ai ms",
                "delta ms",
                "delta %",
                "bash tok",
                "pytk-ai tok",
                "saved",
                "saved %",
            ),
            rows,
        )
    )
    print()
    for result in results:
        print(f"{result.title}: {result.command}")
        print(f"  cwd: {result.cwd}")
        print(
            "  bash output:"
            f" {result.bash_output.lines} line(s),"
            f" {result.bash_output.chars} char(s),"
            f" {result.bash_output.tokens} token(s)"
        )
        print(
            "  pytk-ai output:"
            f" {result.pytk_ai_output.lines} line(s),"
            f" {result.pytk_ai_output.chars} char(s),"
            f" {result.pytk_ai_output.tokens} token(s)"
        )
        print(
            "  timing spread:"
            f" bash median {result.bash_timing.median_ms:.2f} ms"
            f" (min {result.bash_timing.min_ms:.2f}, max {result.bash_timing.max_ms:.2f},"
            f" stdev {result.bash_timing.stdev_ms:.2f})"
        )
        print(
            "                 "
            f"pytk-ai median {result.pytk_ai_timing.median_ms:.2f} ms"
            f" (min {result.pytk_ai_timing.min_ms:.2f}, max {result.pytk_ai_timing.max_ms:.2f},"
            f" stdev {result.pytk_ai_timing.stdev_ms:.2f})"
        )


def print_filter_benchmark_report(
    results: list[FilterSampleResult], *, output_format: str
) -> None:
    if output_format == "json":
        payload = [
            {
                "family": result.family,
                "title": result.title,
                "command": result.command,
                "filter_name": result.filter_name,
                "policy": result.policy,
                "raw_output": result.raw_output._asdict(),
                "filtered_output": result.filtered_output._asdict(),
                "saved_tokens": result.saved_tokens,
                "saved_pct": result.saved_pct,
            }
            for result in results
        ]
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    rows = [
        (
            result.family,
            result.filter_name,
            result.policy,
            str(result.raw_output.tokens),
            str(result.filtered_output.tokens),
            str(result.saved_tokens),
            format_percent(result.saved_pct),
        )
        for result in results
    ]
    print("Token estimator: chars/4 estimate")
    print(
        "Usage mode decision: interactive and hook currently share the same filter output."
    )
    print()
    print(
        format_table(
            (
                "family",
                "filter",
                "policy",
                "raw tok",
                "filtered tok",
                "saved",
                "saved %",
            ),
            rows,
        )
    )
    print()
    for result in results:
        print(f"{result.family}: {result.title}")
        print(f"  command: {result.command}")
        print(f"  filter: {result.filter_name}")
        print(
            "  tokens:"
            f" {result.raw_output.tokens} -> {result.filtered_output.tokens}"
            f" ({result.saved_tokens} saved, {format_percent(result.saved_pct)})"
        )


def main() -> None:
    args = parse_args()
    if args.filter_benchmarks:
        print_filter_benchmark_report(
            benchmark_filter_samples(), output_format=args.format
        )
        return
    if args.benchmark:
        print_benchmark_report(
            benchmark_scenarios(args.iterations), iterations=args.iterations
        )
        return
    compare_outputs()


if __name__ == "__main__":
    main()

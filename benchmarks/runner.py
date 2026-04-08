"""Benchmark runner: measures token reduction per fixture scenario for PYTK-AI and RTK.

Usage:
    python -m benchmarks.runner [--category git] [--iterations 10]
    python -m benchmarks.runner --fixture-only
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import shutil
import statistics
import subprocess
import tempfile
import time

from pytk_ai.filters import filter_output
from pytk_ai.filters.base import combine_command_streams, output_metrics
from pytk_ai.plan import plan_command

from .scenarios import Scenario, discover_scenarios

RESULTS_DIR = Path(__file__).resolve().parent / "results"
DEFAULT_ENGINES = ("pytk", "rtk")
SUPPORTED_ENGINES = frozenset(DEFAULT_ENGINES)
UNSUPPORTED_RTK_SCENARIOS = {
    ("git", "diff_multifile"),
    ("go", "golangci_lint"),
    ("infra", "docker_compose_ps"),
}


@dataclass
class ReplayPlan:
    argv: list[str]
    rewritten_command: str
    benchmark_mode: str
    workdir: Path
    env: dict[str, str]
    status: str = "ok"
    error: str | None = None
    _tempdirs: list[tempfile.TemporaryDirectory[str]] = field(default_factory=list)

    def cleanup(self) -> None:
        for tempdir in self._tempdirs:
            tempdir.cleanup()


def _summarize_metrics(
    *,
    raw_text: str,
    filtered_text: str | None,
) -> tuple[dict[str, int | float | None], str | None]:
    raw = output_metrics(raw_text)
    if filtered_text is None:
        return (
            {
                "raw_bytes": raw.chars,
                "filtered_bytes": None,
                "raw_tokens": raw.tokens,
                "filtered_tokens": None,
                "saved_tokens": None,
                "reduction_pct": None,
            },
            None,
        )

    filtered = output_metrics(filtered_text)
    saved_tokens = raw.tokens - filtered.tokens
    saved_pct = ((saved_tokens / raw.tokens) * 100.0) if raw.tokens else 0.0
    return (
        {
            "raw_bytes": raw.chars,
            "filtered_bytes": filtered.chars,
            "raw_tokens": raw.tokens,
            "filtered_tokens": filtered.tokens,
            "saved_tokens": saved_tokens,
            "reduction_pct": round(saved_pct, 1),
        },
        None,
    )


def _timing_summary(timings_ms: list[float]) -> dict[str, float | int | None]:
    if not timings_ms:
        return {
            "mean_filter_ms": None,
            "median_filter_ms": None,
            "min_filter_ms": None,
            "max_filter_ms": None,
        }
    return {
        "mean_filter_ms": round(statistics.fmean(timings_ms), 3),
        "median_filter_ms": round(statistics.median(timings_ms), 3),
        "min_filter_ms": round(min(timings_ms), 3),
        "max_filter_ms": round(max(timings_ms), 3),
    }


def benchmark_pytk_scenario(scenario: Scenario, *, iterations: int = 10) -> dict:
    data = scenario.load()
    stdout, stderr = data["stdout"], data["stderr"]
    plan = plan_command(scenario.command)

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
    metrics, _ = _summarize_metrics(raw_text=raw_text, filtered_text=result.output)

    return {
        "engine": "pytk",
        "status": "ok",
        "benchmark_mode": "fixture",
        "category": scenario.category,
        "name": scenario.name,
        "command": scenario.command,
        "rewritten_command": plan.planned_command,
        "filter_name": result.filter_name,
        "error": result.error,
        **metrics,
        **_timing_summary(timings_ms),
        "iterations": iterations,
    }


def detect_rtk_version(rtk_bin: str) -> str:
    output = subprocess.run(
        [rtk_bin, "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    if output.returncode != 0:
        raise RuntimeError(
            f"failed to read RTK version from {rtk_bin}: {output.stderr.strip()}"
        )
    return output.stdout.strip()


def resolve_rtk_command(command: str, *, rtk_bin: str) -> str:
    output = subprocess.run(
        [rtk_bin, "rewrite", command],
        capture_output=True,
        text=True,
        check=False,
    )
    rewritten = output.stdout.strip()
    return rewritten or f"rtk {command}"


def parse_rewritten_command(rewritten: str, *, rtk_bin: str) -> list[str]:
    argv = shlex.split(rewritten)
    if not argv:
        raise ValueError("rewritten RTK command is empty")
    if argv[0] == "rtk":
        argv[0] = rtk_bin
    return argv


def make_fixture_stub(
    directory: Path,
    command_name: str,
    *,
    stdout: str,
    stderr: str,
    exit_code: int,
) -> None:
    script_path = directory / command_name
    body = (
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"sys.stdout.write({stdout!r})\n"
        f"sys.stderr.write({stderr!r})\n"
        f"raise SystemExit({exit_code})\n"
    )
    script_path.write_text(body)
    script_path.chmod(0o755)


def _tokens_for_command(command: str) -> list[str]:
    tokens = shlex.split(command)
    if not tokens:
        raise ValueError("scenario command is empty")
    return tokens


def _prepare_read_inputs(base_dir: Path, command_tokens: list[str], data: dict) -> str:
    file_path = Path(command_tokens[1])
    target = base_dir / file_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if data["stdout"]:
        target.write_text(data["stdout"])
    return str(file_path)


def _prepare_find_tree(base_dir: Path, data: dict) -> None:
    for raw_line in data["stdout"].splitlines():
        line = raw_line.strip()
        if not line or line.endswith("/"):
            continue
        relative = line[2:] if line.startswith("./") else line
        target = base_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text("")


def build_rtk_replay_plan(scenario: Scenario, *, rtk_bin: str) -> ReplayPlan:
    rewritten_command = resolve_rtk_command(scenario.command, rtk_bin=rtk_bin)
    argv = parse_rewritten_command(rewritten_command, rtk_bin=rtk_bin)
    command_tokens = _tokens_for_command(scenario.command)
    data = scenario.load()

    if (scenario.category, scenario.name) in UNSUPPORTED_RTK_SCENARIOS:
        return ReplayPlan(
            argv=argv,
            rewritten_command=rewritten_command,
            benchmark_mode="unsupported",
            workdir=Path.cwd(),
            env=os.environ.copy(),
            status="unsupported",
            error="fixture requires multi-step RTK replay that is not benchmarked yet",
        )

    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

    original_root = command_tokens[0]
    benchmark_mode = "rewrite-stub"

    if original_root in {"cat", "head", "tail"} and len(command_tokens) >= 2:
        _prepare_read_inputs(root, command_tokens, data)
        benchmark_mode = "rewrite-file"
    elif original_root == "find":
        _prepare_find_tree(root, data)
        benchmark_mode = "rewrite-tree"
    else:
        make_fixture_stub(
            bin_dir,
            original_root,
            stdout=data["stdout"],
            stderr=data["stderr"],
            exit_code=scenario.exit_code,
        )
        if rewritten_command == f"rtk {scenario.command}":
            benchmark_mode = "fallback-stub"

    return ReplayPlan(
        argv=argv,
        rewritten_command=rewritten_command,
        benchmark_mode=benchmark_mode,
        workdir=root,
        env=env,
        _tempdirs=[tmp],
    )


def _run_replay(plan: ReplayPlan) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        plan.argv,
        cwd=plan.workdir,
        env=plan.env,
        capture_output=True,
        text=True,
        check=False,
    )


def benchmark_rtk_scenario(
    scenario: Scenario,
    *,
    iterations: int = 10,
    rtk_bin: str,
) -> dict:
    data = scenario.load()
    raw_text = combine_command_streams(
        data["stdout"], data["stderr"], scenario.exit_code
    )
    replay = build_rtk_replay_plan(scenario, rtk_bin=rtk_bin)

    if replay.status != "ok":
        metrics, _ = _summarize_metrics(raw_text=raw_text, filtered_text=None)
        return {
            "engine": "rtk",
            "status": replay.status,
            "benchmark_mode": replay.benchmark_mode,
            "category": scenario.category,
            "name": scenario.name,
            "command": scenario.command,
            "rewritten_command": replay.rewritten_command,
            "filter_name": "rtk",
            "error": replay.error,
            **metrics,
            **_timing_summary([]),
            "iterations": iterations,
        }

    try:
        _run_replay(replay)

        timings_ms: list[float] = []
        run = None
        for _ in range(iterations):
            t0 = time.perf_counter()
            run = _run_replay(replay)
            t1 = time.perf_counter()
            timings_ms.append((t1 - t0) * 1000)

        assert run is not None
        filtered_text = combine_command_streams(run.stdout, run.stderr, run.returncode)
        metrics, _ = _summarize_metrics(raw_text=raw_text, filtered_text=filtered_text)
        status = "ok" if run.returncode == scenario.exit_code else "error"
        error = None
        if status == "error":
            error = (
                f"RTK replay exit code mismatch: expected {scenario.exit_code}, "
                f"got {run.returncode}"
            )

        return {
            "engine": "rtk",
            "status": status,
            "benchmark_mode": replay.benchmark_mode,
            "category": scenario.category,
            "name": scenario.name,
            "command": scenario.command,
            "rewritten_command": replay.rewritten_command,
            "filter_name": "rtk",
            "error": error,
            **metrics,
            **_timing_summary(timings_ms),
            "iterations": iterations,
        }
    finally:
        replay.cleanup()


def run_benchmarks(
    *,
    category: str | None = None,
    iterations: int = 10,
    engines: tuple[str, ...] = DEFAULT_ENGINES,
    rtk_bin: str | None = None,
) -> dict:
    scenarios = discover_scenarios(category=category)
    results: list[dict] = []
    normalized_engines = tuple(dict.fromkeys(engines))
    invalid = [
        engine for engine in normalized_engines if engine not in SUPPORTED_ENGINES
    ]
    if invalid:
        raise ValueError(f"unsupported benchmark engine(s): {', '.join(invalid)}")

    rtk_version = None
    resolved_rtk_bin = None
    if "rtk" in normalized_engines:
        resolved_rtk_bin = rtk_bin or os.environ.get("RTK_BIN") or shutil.which("rtk")
        if not resolved_rtk_bin:
            raise FileNotFoundError(
                "RTK benchmark requested but `rtk` was not found. Set RTK_BIN or install rtk."
            )
        rtk_version = detect_rtk_version(resolved_rtk_bin)

    for scenario in scenarios:
        if "pytk" in normalized_engines:
            results.append(benchmark_pytk_scenario(scenario, iterations=iterations))
        if "rtk" in normalized_engines and resolved_rtk_bin is not None:
            results.append(
                benchmark_rtk_scenario(
                    scenario,
                    iterations=iterations,
                    rtk_bin=resolved_rtk_bin,
                )
            )

    sample_estimator = next(
        (
            result.get("token_estimator")
            for result in results
            if result.get("token_estimator")
        ),
        None,
    )
    if sample_estimator is None:
        sample_estimator = "cl100k_base"

    return {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "token_estimator": sample_estimator,
        "iterations": iterations,
        "engines": list(normalized_engines),
        "category_filter": category,
        "rtk_version": rtk_version,
        "results": results,
    }


def _print_summary(document: dict) -> None:
    print(f"Benchmarked {len(document['results'])} engine/scenario rows")
    for engine in document["engines"]:
        engine_results = [
            row
            for row in document["results"]
            if row["engine"] == engine and row["status"] == "ok"
        ]
        coverage = sum(1 for row in document["results"] if row["engine"] == engine)
        total_filtered = sum(row["filtered_tokens"] or 0 for row in engine_results)
        total_raw = sum(row["raw_tokens"] or 0 for row in engine_results)
        total_saved = total_raw - total_filtered
        reduction = ((total_saved / total_raw) * 100.0) if total_raw else 0.0
        print(
            f"{engine}: {len(engine_results)}/{coverage} comparable, "
            f"{total_saved:,} tokens saved ({reduction:.1f}%)"
        )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run PTK/RTK fixture benchmarks")
    parser.add_argument("--category", type=str, default=None, help="filter by category")
    parser.add_argument(
        "--iterations", type=int, default=10, help="timing iterations per scenario"
    )
    parser.add_argument(
        "--engines",
        type=str,
        default=",".join(DEFAULT_ENGINES),
        help="comma-separated engine list (pytk,rtk)",
    )
    parser.add_argument(
        "--fixture-only",
        action="store_true",
        help="benchmark fixture filtering only (equivalent to --engines pytk)",
    )
    parser.add_argument(
        "--rtk-bin",
        type=str,
        default=None,
        help="path to RTK binary (default: RTK_BIN or PATH lookup)",
    )
    parser.add_argument(
        "--output", type=str, default=None, help="output JSON file path"
    )
    return parser


def parse_engines(*, engines_arg: str, fixture_only: bool) -> tuple[str, ...]:
    if fixture_only:
        return ("pytk",)
    return (
        tuple(engine.strip() for engine in engines_arg.split(",") if engine.strip())
        or DEFAULT_ENGINES
    )


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    engines = parse_engines(engines_arg=args.engines, fixture_only=args.fixture_only)
    document = run_benchmarks(
        category=args.category,
        iterations=args.iterations,
        engines=engines,
        rtk_bin=args.rtk_bin,
    )

    output_path = Path(args.output) if args.output else RESULTS_DIR / "latest.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(document, indent=2) + "\n")

    _print_summary(document)
    print(f"Results written to {output_path}")


if __name__ == "__main__":
    main()

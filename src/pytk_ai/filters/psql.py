from __future__ import annotations

import re

from ..models import FilterResult
from .base import make_filter_result
from .generic import filter_generic_output

_EXPANDED_RECORD_RE = re.compile(r"-\[ RECORD \d+ \]-")
_SEPARATOR_RE = re.compile(r"^[-+]+$")
_ROW_COUNT_RE = re.compile(r"^\(\d+ rows?\)$")
_RECORD_HEADER_RE = re.compile(r"^-\[ RECORD (\d+) \]-")

_MAX_TABLE_ROWS = 30
_MAX_EXPANDED_RECORDS = 20


def _is_table_format(output: str) -> bool:
    return any(
        "-+-" in line.strip() or "---+---" in line.strip()
        for line in output.splitlines()
    )


def _is_expanded_format(output: str) -> bool:
    return bool(_EXPANDED_RECORD_RE.search(output))


def _filter_table(output: str) -> str:
    result: list[str] = []
    data_rows = 0
    total_rows = 0

    for line in output.splitlines():
        trimmed = line.strip()
        if not trimmed or _SEPARATOR_RE.match(trimmed) or _ROW_COUNT_RE.match(trimmed):
            continue

        if "|" in trimmed:
            total_rows += 1
            if total_rows > 1:
                data_rows += 1
            if data_rows <= _MAX_TABLE_ROWS or total_rows == 1:
                cols = [col.strip() for col in trimmed.split("|")]
                result.append("\t".join(cols))
        else:
            result.append(trimmed)

    if data_rows > _MAX_TABLE_ROWS:
        result.append(f"... +{data_rows - _MAX_TABLE_ROWS} more rows")

    return "\n".join(result)


def _filter_expanded(output: str) -> str:
    result: list[str] = []
    current_pairs: list[str] = []
    current_record: str | None = None
    record_count = 0

    for line in output.splitlines():
        trimmed = line.strip()
        if _ROW_COUNT_RE.match(trimmed):
            continue

        record_match = _RECORD_HEADER_RE.match(trimmed)
        if record_match:
            if current_record is not None and record_count <= _MAX_EXPANDED_RECORDS:
                result.append(f"{current_record} {' '.join(current_pairs)}".rstrip())
            current_pairs = []
            record_count += 1
            current_record = f"[{record_match.group(1)}]"
            continue

        if current_record is not None and "|" in trimmed:
            key, value = [part.strip() for part in trimmed.split("|", 1)]
            current_pairs.append(f"{key}={value}")
            continue

        if trimmed and current_record is None:
            result.append(trimmed)

    if current_record is not None and record_count <= _MAX_EXPANDED_RECORDS:
        result.append(f"{current_record} {' '.join(current_pairs)}".rstrip())

    if record_count > _MAX_EXPANDED_RECORDS:
        result.append(f"... +{record_count - _MAX_EXPANDED_RECORDS} more records")

    return "\n".join(result)


def _filter_psql_output(output: str) -> str:
    if not output.strip():
        return ""
    if _is_expanded_format(output):
        return _filter_expanded(output)
    if _is_table_format(output):
        return _filter_table(output)
    return output


def filter_psql_output(
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    max_output_lines: int = 200,
) -> FilterResult:
    del command
    if exit_code != 0:
        return filter_generic_output(
            "psql",
            stdout,
            stderr,
            exit_code,
            max_output_lines=max_output_lines,
        )

    return make_filter_result(
        _filter_psql_output(stdout),
        filter_name="psql",
        max_output_lines=max_output_lines,
    )

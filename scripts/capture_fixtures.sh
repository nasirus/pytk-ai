#!/usr/bin/env bash
# Capture real command output into fixture files.
# Usage: ./scripts/capture_fixtures.sh <category> <command> <name>
# Example: ./scripts/capture_fixtures.sh git "git status" status_dirty

set -euo pipefail

if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <category> <command> <name>"
    echo "Example: $0 git 'git status' status_dirty"
    exit 1
fi

CATEGORY="$1"
COMMAND="$2"
NAME="$3"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIXTURES_DIR="$SCRIPT_DIR/../tests/fixtures/$CATEGORY"

mkdir -p "$FIXTURES_DIR"

STDOUT_FILE="$FIXTURES_DIR/$NAME.stdout"
STDERR_FILE="$FIXTURES_DIR/$NAME.stderr"
META_FILE="$FIXTURES_DIR/$NAME.meta"

EXIT_CODE=0
bash -lc "$COMMAND" >"$STDOUT_FILE" 2>"$STDERR_FILE" || EXIT_CODE=$?

# Remove empty stderr file
if [ ! -s "$STDERR_FILE" ]; then
    rm -f "$STDERR_FILE"
fi

# Derive filter_name by running the actual filter pipeline (not just plan_command)
FILTER_NAME=$(PYTK_CMD="$COMMAND" PYTK_EXIT="$EXIT_CODE" PYTK_STDOUT="$STDOUT_FILE" PYTK_STDERR="$STDERR_FILE" python3 -c "
import os
from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command
cmd = os.environ['PYTK_CMD']
exit_code = int(os.environ['PYTK_EXIT'])
stdout_path = os.environ['PYTK_STDOUT']
stderr_path = os.environ.get('PYTK_STDERR', '')
stdout = open(stdout_path).read()
stderr = open(stderr_path).read() if stderr_path and os.path.exists(stderr_path) else ''
result = filter_output(cmd, stdout, stderr, exit_code, plan=plan_command(cmd))
print(result.filter_name)
")

# Write .meta as proper JSON using python to handle escaping
PYTK_CMD="$COMMAND" PYTK_EXIT="$EXIT_CODE" PYTK_FILTER="$FILTER_NAME" python3 -c "
import json, os
meta = {
    'command': os.environ['PYTK_CMD'],
    'exit_code': int(os.environ['PYTK_EXIT']),
    'filter_name': os.environ['PYTK_FILTER'],
}
print(json.dumps(meta))
" > "$META_FILE"

echo "Captured fixture: $FIXTURES_DIR/$NAME"
echo "  stdout: $(wc -l < "$STDOUT_FILE") lines"
[ -f "$STDERR_FILE" ] && echo "  stderr: $(wc -l < "$STDERR_FILE") lines"
echo "  meta: $META_FILE"

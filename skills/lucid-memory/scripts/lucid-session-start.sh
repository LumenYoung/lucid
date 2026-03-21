#!/usr/bin/env bash
set -euo pipefail

SESSION_NAME="${1:-lucid}"
if [ "$#" -gt 0 ]; then
  shift
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec bash "${SCRIPT_DIR}/lucid-mcp2cli.sh" --session-start "${SESSION_NAME}" "$@"

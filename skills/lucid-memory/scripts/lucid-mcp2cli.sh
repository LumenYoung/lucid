#!/usr/bin/env bash
set -euo pipefail

: "${LUCID_API_TOKEN:?Set LUCID_API_TOKEN before using the lucid memory wrapper.}"
: "${LUCID_MCP_URL:?Set LUCID_MCP_URL before using the lucid memory wrapper.}"

MCP2CLI_BIN="${MCP2CLI_BIN:-mcp2cli}"
LUCID_TRANSPORT="${LUCID_TRANSPORT:-streamable}"

exec "${MCP2CLI_BIN}" \
  --mcp "${LUCID_MCP_URL}" \
  --transport "${LUCID_TRANSPORT}" \
  --auth-header "X-Lucid-Token:env:LUCID_API_TOKEN" \
  "$@"

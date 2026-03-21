# Lucid

`lucid` is a control repo for a shared Graphiti and FalkorDB memory platform and the agent skill that consumes it through `mcp2cli`.

The repo is intentionally split into two separate surfaces:

- `deploy/` and `docs/` are operator-facing reference artifacts for running the shared memory service.
- `skills/` is agent-facing material for consuming that service without loading raw MCP schemas into every session.
- `openspec/` tracks the design and rollout work as OpenSpec changes.

`lucid` does not vendor Graphiti. The deployment examples assume Graphiti is checked out separately and referenced through `GRAPHITI_MCP_SERVER_PATH`.

Start here:

- Server deployment: `docs/deployment.md`
- Agent skill: `skills/lucid-memory/SKILL.md`

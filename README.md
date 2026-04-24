# Lucid

`lucid` is the home for a shared Graphiti and FalkorDB memory platform and the Lucid-owned MCP
runtime that wraps `graphiti-core`.

The repo now has three main surfaces:

- `src/lucid_mcp/` and `config/` contain the Lucid-owned MCP runtime
- `docs/` contains operator and integration documentation
- `deploy/` contains deployment and maintenance artifacts used by operators
- `openspec/` tracks the design and rollout work as OpenSpec changes.

`lucid` does not vendor `graphiti-core`, but it owns its own MCP server implementation and depends
on `graphiti-core` as a library.

## Current Runtime Shape

Lucid exposes a Graphiti-compatible MCP tool surface and adds Lucid-specific policy controls:

- server-level MCP instruction
- subgroup-level instruction groups declared in `instructions.groups`
- profile-based default write groups
- profile-based allowed read groups
- profile-to-subgroup instruction mapping via `profiles.<name>.instruction_group`
- disallowed write-group fallback to the profile default
- optional route-based profile selection from one HTTP service
- FalkorDB logical-group handling that keeps all groups inside one configured database

The current deployment model uses one HTTP service with internal route-based profile selection:

- `/work/mcp`
- `/internal/mcp`
- `/mcp` as a compatibility alias to the work profile

## Agent Integration Direction

Lucid's preferred integration model is now:

- MCP for the actual memory tools
- agent instruction for retrieval and write policy
- agent-native automation where available, such as OpenCode hooks

This repo no longer treats a Codex/OpenCode skill as the primary integration surface.

Start here:

- Server deployment: `docs/deployment.md`
- Maintenance: `docs/maintenance.md`
- Agent setup: `docs/agents/README.md`
- Shared agent instruction: `docs/agents/shared-instruction.md`
- Runtime notes and gotchas: `docs/runtime-notes.md`

For local runtime development:

```bash
uv lock
uv run python main.py --config config/config.yaml
```

## Validation

Useful local checks:

```bash
uv run python -m py_compile main.py src/lucid_mcp/*.py
uv run pytest
```

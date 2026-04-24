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

## Design Principles

Lucid treats memory as a graph because useful context is rarely isolated. Code, decisions,
preferences, assumptions, procedures, and facts become valuable when an agent can see how they
relate, how those relationships changed, and how far it should expand around a topic before acting.
Graph memory gives the agent a higher-resolution retrieval surface than a flat log: it can start
from a node, inspect nearby facts, follow only relevant relationships, and decide when it needs the
raw episode behind a claim.

For coding projects, Lucid's goal is memory from first principles. A repository should not be
remembered only as scattered session summaries. Lucid should help build a durable model of the
codebase from:

- decisions: what was chosen and why
- assumptions: what the code or design depends on being true
- principles: architectural rules, coding style, and project conventions
- facts: stable observations about files, modules, behavior, tests, deployment, and dependencies
- relationships: how files, modules, use cases, assumptions, principles, and tests affect one
  another

For general agent memory, Lucid has the same first-principles goal at a broader scope. Memory should
give an agent enough clean context to deliver the task: user preferences, durable rules, prior
decisions, project constraints, task prerequisites, handoff state, and known gotchas. The point is
not to store every event. The point is to preserve the context a future agent would otherwise have
to rediscover, while filtering out noise.

Lucid should preserve raw episodes alongside curated graph memory. The graph is an interpretation of
the source material, not a perfect source of truth. Keeping the original episode content and
provenance lets a future librarian or memory-management agent revisit the raw evidence, correct
misunderstandings, update stale interpretations, and rebuild better graph memory when the ontology or
extraction behavior improves.

Lucid runs memory on a server so agents can share context across devices and sessions. The server is
the centralized place to manage, retrieve, clean, and evolve memory. In the long run, it should act
as a second brain for agents: not a transcript archive, but a managed context system that gives the
agent real working context instead of a pile of unrelated notes.

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

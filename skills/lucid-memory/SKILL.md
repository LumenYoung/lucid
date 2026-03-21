---
name: lucid-memory
description: Use a shared Graphiti memory service through mcp2cli. Use this skill when you need to search or write shared memory that should be visible across Codex, OpenCode, and Nanobot without loading raw MCP schemas directly into the model context.
---

# Lucid Memory Via mcp2cli

Use the configured public MCP endpoint through the bundled `mcp2cli` wrapper scripts.

## Rules

- Prefer a persistent `lucid` session if one already exists.
- Keep `LUCID_MCP_URL` in the environment and point it at your deployed MCP endpoint.
- Keep `LUCID_API_TOKEN` in the environment and rely on `env:` header resolution instead of literal tokens in commands.
- Use discovery first: `--list`, then `<command> --help`, then the actual invocation.
- Search before writing when the task might already be covered by existing memory.
- Use `add-memory` for new memory, `search-nodes` for entity summaries, `search-memory-facts` for relationships, and `get-episodes` for recent writes.

## Setup

Set the required endpoint and token once in the shell where the skill will run:

```bash
export LUCID_MCP_URL=https://memory.example.com/mcp
export LUCID_API_TOKEN=...
```

## Direct one-off usage

List available tools:

```bash
bash scripts/lucid-mcp2cli.sh --list
```

Inspect a tool:

```bash
bash scripts/lucid-mcp2cli.sh search-nodes --help
```

Call a tool:

```bash
bash scripts/lucid-mcp2cli.sh search-nodes --query "shared memory" --max-nodes 5
```

## Persistent session workflow

Start a reusable session:

```bash
bash scripts/lucid-session-start.sh lucid
```

Then use the session directly:

```bash
mcp2cli --session lucid --list
mcp2cli --session lucid search-nodes --help
mcp2cli --session lucid search-nodes --query "shared memory" --max-nodes 5
```

If you need more examples or bootstrap guidance, read:

- `references/bootstrap.md`
- `references/validation.md`

# Codex and OpenCode Setup

This directory documents the practical Lucid integration pattern we use for Codex and OpenCode.

The setup has three layers:

1. Shared instruction: tell the model when Lucid memory is worth reading or writing.
2. MCP connection: expose the Lucid MCP endpoint with `LUCID_API_TOKEN`.
3. Agent-specific automation: OpenCode can add hooks through a plugin; Codex currently cannot.

## Shared environment contract

Set these in the shell or agent service environment:

```bash
export LUCID_API_TOKEN=...
export LUCID_MCP_URL=https://memory.example.com/mcp
export LUCID_MEMORY_WRITE_GROUP=work
export LUCID_MEMORY_READ_GROUPS=work
```

Notes:

- `LUCID_MEMORY_WRITE_GROUP` defaults to `work` in our setup.
- `LUCID_MEMORY_READ_GROUPS` can be a comma-separated list such as `work,research`.
- If you do not need read/write separation yet, keep both set to `work`.

## Shared instruction

Use the text in [shared-instruction.md](shared-instruction.md) as the common Lucid memory policy for both agents.

The point of this instruction is to keep both sides aligned on:

- when to retrieve
- what counts as a durable episode
- what should be skipped
- when to write a checkpoint or final handoff

## Codex

Codex currently relies on instruction plus direct MCP access.

Recommended setup:

1. Put the shared instruction in Codex's global `AGENTS.md`.
2. Add a `lucid_memory` MCP entry in Codex `config.toml`.
3. Export `LUCID_API_TOKEN` in the environment where Codex runs.

Example MCP block:

```toml
[mcp_servers.lucid_memory]
url = "https://memory.example.com/mcp"
env_http_headers = { "X-Lucid-Token" = "LUCID_API_TOKEN" }
startup_timeout_sec = 20.0
tool_timeout_sec = 120.0

[mcp_servers.lucid_memory.tools.add_memory]
approval_mode = "approve"

[mcp_servers.lucid_memory.tools.search_nodes]
approval_mode = "approve"

[mcp_servers.lucid_memory.tools.search_memory_facts]
approval_mode = "approve"

[mcp_servers.lucid_memory.tools.get_episodes]
approval_mode = "approve"
```

Operationally:

- Codex should retrieve narrowly, usually by repo or task terms.
- Codex should write only durable, high-value summaries another session would need.
- Codex should write a checkpoint before compaction and a final handoff at the end of meaningful work.

## OpenCode

OpenCode should use the same shared instruction, the same Lucid MCP server, and an additional plugin for automatic hooks.

Recommended setup:

1. Put the shared instruction in OpenCode's global `AGENTS.md`.
2. Add a remote `lucid-memory` MCP server in `opencode.json`.
3. Load a Lucid plugin through the OpenCode `plugin` array.
4. Export `LUCID_API_TOKEN` and the optional Lucid group variables in the OpenCode environment.

Example MCP block:

```json
{
  "mcp": {
    "lucid-memory": {
      "type": "remote",
      "url": "https://memory.example.com/mcp",
      "enabled": true,
      "headers": {
        "X-Lucid-Token": "{env:LUCID_API_TOKEN}"
      },
      "oauth": false,
      "timeout": 120000
    }
  }
}
```

The plugin should automate the hook layer, especially:

- session-start retrieval
- narrow retrieval after the first real user prompt
- post-tool capture for meaningful tool results
- post-command capture for stateful commands
- pre-compact checkpoint writes
- session-end handoff writes

The shared instruction still matters in OpenCode. It tells the model what good memory looks like, even when some retrieval and write moments are already automated by hooks.

## Recommended policy boundary

Keep the policy simple:

- default write group: `work`
- optional read groups: one or more groups, if you need broader retrieval
- separate `personal` only when you truly need privacy or a different retention posture

For most engineering work, `work` as the default write target and optional multi-group reads is the cleanest starting point.

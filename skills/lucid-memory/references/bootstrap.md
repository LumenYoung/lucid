# Session bootstrap

## Default flow

For Codex or OpenCode on a machine that can reach your deployed memory endpoint:

```bash
export LUCID_MCP_URL=https://memory.example.com/mcp
export LUCID_API_TOKEN=...
bash scripts/lucid-session-start.sh lucid
mcp2cli --session lucid --list
```

That gives the agent a reusable named session without repeating the full MCP URL and auth header on every command.

## Recovery

List active sessions:

```bash
mcp2cli --session-list
```

Stop a stale session:

```bash
mcp2cli --session-stop lucid
```

Start it again:

```bash
bash scripts/lucid-session-start.sh lucid
```

## Nanobot-style prestart

If you want Nanobot to mirror the existing `searxng` pattern, prestart the `lucid` session during its bootstrap process with a shell command equivalent to:

```bash
export LUCID_MCP_URL=https://memory.example.com/mcp
export LUCID_API_TOKEN=...
bash /path/to/lucid/skills/lucid-memory/scripts/lucid-session-start.sh lucid
```

After that, the runtime can use:

```bash
mcp2cli --session lucid --list
```

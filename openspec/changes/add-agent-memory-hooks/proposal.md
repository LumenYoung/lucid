## Why

Lucid already exposes shared memory through Graphiti and FalkorDB, but agents still have to remember to search and write memory manually. We need an agent-side hook workflow so OpenCode and Codex can load relevant shared memory at session start and capture important edits, commands, and session outcomes with minimal operator effort.

## What Changes

- Add a normalized Lucid hook workflow that turns agent-specific events into a shared set of memory actions such as session-start retrieval, post-edit capture, and session-end summarization.
- Add an OpenCode hook bridge that uses a generated plugin to translate OpenCode lifecycle, file, command, and tool events into the normalized Lucid hook workflow.
- Add a Codex-compatible hook workflow that uses a launcher, optional file watcher, and AGENTS guidance to provide the closest practical equivalent to native hooks where Codex does not expose the same hook surface as OpenCode.
- Add agent-side filtering rules so Lucid avoids writing noisy or duplicate memory for trivial edits and repeated events.
- Add operator and skill documentation for hook installation, supported event coverage, and known differences between OpenCode and Codex.

## Capabilities

### New Capabilities
- `agent-memory-hooks`: Normalize agent events into Lucid memory retrieval and write behaviors with shared filtering, deduplication, and `mcp2cli`-based execution.
- `opencode-hook-bridge`: Install and run an OpenCode plugin bridge that forwards supported OpenCode events into the normalized Lucid hook workflow.
- `codex-hook-workflow`: Provide a Codex-compatible workflow for session-start retrieval and post-edit or session-end capture without requiring native Codex hooks that do not exist today.

### Modified Capabilities

None.

## Impact

- Affected systems: `skills/lucid-memory`, future hook scripts and installers, operator docs, and agent bootstrap workflows.
- Dependencies: `mcp2cli`, the live Lucid MCP endpoint, and local agent-specific config surfaces such as OpenCode plugins and Codex repo guidance.
- Runtime behavior: adds agent-side automatic retrieval and write paths that will call Lucid during session start, selected edits, selected commands, and session end.
- Operational constraint: OpenCode can support a true hook bridge, while Codex will use a wrapper or sidecar workflow with explicitly documented event-coverage limits.

## Context

Lucid already provides a shared memory backend through Graphiti, FalkorDB, and a public MCP endpoint. The missing piece is agent-side automation: when a session starts, agents should fetch relevant memory automatically, and when they perform meaningful edits or finish a session, Lucid should capture memory without depending entirely on manual discipline.

The `memorix` repo provides a useful reference model. It normalizes agent-specific payloads into a single hook vocabulary, then applies event-specific behavior such as searching memory on `session_start` and storing summaries on `session_end`. It also makes an important distinction between agents that expose native hooks and agents that do not. OpenCode falls into the first category because it supports plugin events. Codex currently falls into the second category in practice, so parity must be achieved through a launcher and sidecar workflow rather than a native hook file.

Latency measurements from the live Lucid runtime set the performance envelope for this design:

- Public MCP via persistent `mcp2cli` session:
  - `get-status`: median about 457 ms
  - `get-episodes`: median about 571 ms
  - `search-nodes`: median about 762 ms on warm runs
  - `search-memory-facts`: median about 934 ms on warm runs
- Direct backend access against a known-hit group:
  - `get_episodes`: median about 1.9 ms
  - `search_nodes`: median about 250 ms on warm runs
  - `search_facts`: median about 210 ms on warm runs

This means hook-driven retrieval is feasible for session start as long as Lucid reuses a persistent `mcp2cli` session, keeps the number of retrieval calls small, and treats first-hit outliers as acceptable startup cost rather than per-turn cost.

## Goals / Non-Goals

**Goals:**
- Define a normalized hook interface for Lucid that can support multiple agents without duplicating memory logic.
- Support true automatic hook handling for OpenCode through a generated plugin bridge.
- Provide the closest practical equivalent for Codex through a launcher, optional watcher, and AGENTS-guided workflow.
- Keep hook logic on the agent side and separate it from server-side deployment artifacts.
- Minimize noisy writes through cooldowns, deduplication, and significance thresholds.
- Reuse the existing public Lucid MCP endpoint through `mcp2cli` instead of inventing a second memory transport.

**Non-Goals:**
- Adding native request-side hooks to the Lucid server.
- Claiming full hook parity between OpenCode and Codex when the host agents expose different capability surfaces.
- Sending secrets in generated plugin files or committed examples.
- Replacing the existing manual `lucid-memory` skill workflow; hooks should build on it.

## Decisions

### 1. Use a normalized Lucid hook entrypoint

Lucid will define one agent-side hook runner, conceptually `lucid hook <normalized-event>`, that accepts agent metadata and optional payload details through stdin JSON or flags.

Supported normalized events will be:

- `session_start`
- `post_edit`
- `post_command`
- `post_tool`
- `pre_compact`
- `session_end`

Rationale:
- This follows the proven shape in Memorix and keeps agent-specific adapters thin.
- It lets OpenCode and Codex share the same memory logic even if they differ in how events are captured.
- It localizes noise filtering, retrieval policy, and write policy in one place.

Alternatives considered:
- Writing separate memory logic per agent: rejected because it duplicates behavior and drifts quickly.
- Calling Graphiti MCP directly from each hook adapter: rejected because it hardcodes transport details into adapters instead of keeping them in one runner.

### 2. Use `mcp2cli` as the hook runner transport

The hook runner will use the existing Lucid `mcp2cli` integration rather than talking to raw MCP schemas or FalkorDB directly.

Rationale:
- Lucid already standardizes on `mcp2cli` as the agent-facing transport.
- Persistent `mcp2cli` sessions keep retrieval latency acceptable for `session_start` and repeated lookup flows.
- This keeps agent-side memory workflows aligned with the existing skill assets.

Alternatives considered:
- Direct HTTP calls from hook adapters: workable but duplicates auth and transport details.
- Direct Graphiti Python client usage on agent machines: rejected because the shared memory contract should stay at the public MCP boundary.

### 3. Split hook behavior into retrieval and write phases

The normalized hook workflow will use event-specific policies:

- `session_start`: run a small number of retrieval calls and emit a concise memory summary for the agent.
- `post_edit`: inspect changed files or diffs, then write memory only when the change passes significance filters.
- `post_command`: write memory only for meaningful command outcomes such as failures, fixes, migrations, or environment changes.
- `post_tool`: record tool results only when they encode knowledge another agent would need.
- `pre_compact`: write a short handoff summary when the host agent supports compaction events.
- `session_end`: write a final session summary and pending-next-step note.

Rationale:
- Different events need different memory behavior.
- Most post-edit and post-command events should be filtered rather than stored blindly.
- Session-start latency stays manageable if the retrieval phase is intentionally narrow.

Alternatives considered:
- Store everything automatically: rejected because it creates noisy memory and increases costs.
- Retrieve memory before every prompt: rejected because the current latency envelope is good for session start but too expensive for indiscriminate per-turn retrieval.

### 4. Use a real OpenCode plugin bridge

Lucid will support OpenCode with a generated plugin file that forwards supported events into the normalized hook runner.

OpenCode event mapping will cover:

- `session.created` -> `session_start`
- `session.idle` -> `session_end`
- `session.compacted` -> `pre_compact`
- `file.edited` -> `post_edit`
- `command.executed` -> `post_command`
- `tool.execute.after` -> `post_tool`

Rationale:
- OpenCode already exposes the required event surface through plugins.
- A plugin bridge gives near-native hook behavior without modifying Lucid server components.
- This is the cleanest path to parity with Memorix on OpenCode.

Alternatives considered:
- Polling the filesystem for OpenCode too: rejected because OpenCode already has a better native integration point.

### 5. Use a wrapper and optional watcher for Codex

Lucid will support Codex through a launcher workflow rather than claiming native hooks. The launcher will bootstrap a persistent Lucid session, retrieve memory at session start, and optionally run a filesystem watcher that emits `post_edit` events based on real file changes. Session-end summarization will run when the launcher exits or on explicit shutdown.

The Codex workflow will explicitly document that:

- `session_start` is supported through the launcher.
- `post_edit` is supportable through a watcher or diff-based polling sidecar.
- `session_end` is supportable through wrapper shutdown or explicit finalize command.
- `post_command`, `post_tool`, and `pre_compact` are not guaranteed automatically unless Codex exposes additional native surfaces later.

Rationale:
- This is the closest practical equivalent to hooks for Codex today.
- It avoids pretending that AGENTS.md alone is a hook system.
- It still improves memory automation materially for Codex sessions.

Alternatives considered:
- AGENTS.md only: rejected because it relies entirely on the model following instructions and offers no automatic post-edit capture.
- Claim full Codex hook parity: rejected because the native integration surface is not there.

### 6. Keep hook tooling under agent-facing Lucid assets

The hook runner, OpenCode plugin template, Codex launcher, and installation docs will live with the agent-side assets under `skills/` or an adjacent agent-facing subtree, not under `deploy/`.

Rationale:
- This keeps the server-side and agent-side responsibilities separate, matching the repo structure the user requested.
- It makes Lucid the host of the agent skill and hook workflow without mixing it with Docker artifacts.

Alternatives considered:
- Putting hook scripts under `deploy/`: rejected because they are agent-facing behavior, not server deployment mechanics.

## Risks / Trade-offs

- [Codex does not expose native hooks] -> Provide wrapper and watcher coverage, document unsupported events clearly, and avoid promising identical behavior to OpenCode.
- [Automatic hooks can write noisy memory] -> Add significance thresholds, cooldowns, and deduplication before storing memory.
- [Session-start retrieval can feel slow] -> Reuse persistent `mcp2cli` sessions, cap retrieval fan-out, and emit concise context instead of large dumps.
- [Hook adapters might leak local secrets or paths] -> Keep tokens in environment variables and ensure generated examples avoid checked-in local data.
- [Sidecar watchers may miss intent behind an edit] -> Use session-end summarization as a second pass to capture higher-level rationale that raw file watching cannot infer.

## Migration Plan

1. Add OpenSpec requirements for the normalized hook runner, OpenCode bridge, and Codex workflow.
2. Implement agent-side hook tooling in Lucid alongside the existing `lucid-memory` skill assets.
3. Add OpenCode plugin templates or installers that point at the Lucid hook runner.
4. Add a Codex launcher and optional watcher workflow, plus AGENTS guidance that explains automatic and manual event coverage.
5. Validate end-to-end behavior against the live Lucid MCP endpoint using persistent `mcp2cli` sessions.
6. Benchmark session-start retrieval and post-edit capture paths before promoting the hook workflow as the default.

Rollback strategy:
- Remove generated OpenCode plugin files or disable them.
- Stop using the Codex launcher and fall back to the existing manual skill workflow.
- Keep the Lucid server runtime unchanged; this change is agent-side only.

## Open Questions

- What exact context format should `session_start` emit for Codex and OpenCode: stdout snippet, temp file, or a tool-readable JSON summary?
- Should the Codex watcher default to file-based triggers only, or should Lucid also inspect git diffs when available to reduce noise?
- Should Lucid hook installation generate agent-local config files automatically, or should v1 ship only reference templates and wrapper scripts?

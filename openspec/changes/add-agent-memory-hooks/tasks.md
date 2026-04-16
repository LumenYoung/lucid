## 1. OpenSpec Proposal and Design

- [ ] 1.1 Finalize the proposal for Lucid agent-side memory hooks
- [ ] 1.2 Finalize the technical design for normalized events, OpenCode integration, and Codex workflow limits

## 2. Hook Specifications

- [ ] 2.1 Define the `agent-memory-hooks` capability for normalized retrieval and write behavior
- [ ] 2.2 Define the `opencode-hook-bridge` capability for plugin-based OpenCode integration
- [ ] 2.3 Define the `codex-hook-workflow` capability for launcher or sidecar-based Codex integration

## 3. Agent-Facing Hook Tooling

- [ ] 3.1 Add a Lucid hook runner that reuses the existing `mcp2cli` session pattern
- [ ] 3.2 Add filtering and deduplication rules for post-edit, post-command, and post-tool capture
- [ ] 3.3 Add session-start retrieval formatting that can be consumed by supported agents

## 4. Agent Integrations

- [ ] 4.1 Add an OpenCode plugin template or installer that forwards supported events into the Lucid hook runner
- [ ] 4.2 Add a Codex launcher workflow for session-start retrieval and session-end summarization
- [ ] 4.3 Add an optional Codex file watcher or diff-based post-edit capture path with explicit event-coverage documentation

## 5. Documentation and Validation

- [ ] 5.1 Document supported hook events, unsupported events, and installation steps for OpenCode and Codex
- [ ] 5.2 Benchmark hook-triggered retrieval against the live Lucid endpoint and record expected latency envelopes
- [ ] 5.3 Validate the OpenSpec change with the local `openspec` CLI

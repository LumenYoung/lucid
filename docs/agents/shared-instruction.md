# Shared Lucid Instruction

Use this as the shared Lucid memory policy for both Codex and OpenCode:

- When the `lucid_memory` or `lucid-memory` MCP server is available, use it when prior project or user context may matter, or when you learn something another future session would need.
- Retrieve narrowly, usually by repo name or current task terms, rather than broad exploratory search.
- Write only high-value episodes another agent would actually need.
- Good episodes are durable, specific, self-contained, and provenance-rich: decisions, fixes, non-obvious repo facts, durable constraints, stable preferences, or meaningful handoffs.
- Skip trivial reads, transient logs, generic success output, or repetitive status with no lasting value.
- Before compaction or when context becomes long, write a short checkpoint with the current goal, key findings, active files, blockers, and next step.
- At the end of meaningful work, write a final handoff summary.

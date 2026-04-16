## ADDED Requirements

### Requirement: Lucid normalizes agent hook events into shared memory actions
The system SHALL provide an agent-side hook workflow that maps agent-specific events into a shared Lucid hook vocabulary for retrieval and memory writes.

#### Scenario: Supported hook event is normalized
- **WHEN** an agent integration sends a supported event to Lucid hook tooling
- **THEN** Lucid interprets it as one of the normalized events `session_start`, `post_edit`, `post_command`, `post_tool`, `pre_compact`, or `session_end`

### Requirement: Session-start hooks retrieve shared memory through the public Lucid interface
The system SHALL use the existing Lucid MCP interface through `mcp2cli` for session-start memory retrieval rather than accessing FalkorDB directly from the agent machine.

#### Scenario: Session start loads relevant memory
- **WHEN** a supported agent session begins
- **THEN** the hook workflow reuses or creates an `mcp2cli` session for Lucid
- **AND** it performs a bounded retrieval flow against the public Lucid MCP endpoint
- **AND** it emits a concise memory summary for the agent session

### Requirement: Hook writes are filtered for significance and duplication
The system SHALL filter hook-driven writes so Lucid does not store trivial or duplicate memory entries for every event.

#### Scenario: Trivial edit is skipped
- **WHEN** a post-edit or related event does not meet the configured significance policy
- **THEN** Lucid does not write a new memory record for that event

#### Scenario: Significant event is stored
- **WHEN** a post-edit, post-command, post-tool, pre-compact, or session-end event contains knowledge another agent would need
- **THEN** Lucid writes a memory record through the shared MCP workflow

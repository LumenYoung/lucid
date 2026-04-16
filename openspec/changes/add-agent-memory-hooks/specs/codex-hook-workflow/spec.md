## ADDED Requirements

### Requirement: Codex integration uses a launcher-based Lucid workflow
The system SHALL provide a Codex-compatible Lucid workflow that does not depend on native Codex hooks.

#### Scenario: Codex session starts through Lucid launcher
- **WHEN** a Codex session is started through the supported Lucid workflow
- **THEN** Lucid performs session-start retrieval before or during session bootstrap
- **AND** the workflow makes the retrieved memory available to the Codex session

### Requirement: Codex workflow documents partial automatic event coverage
The system SHALL explicitly document which normalized Lucid hook events can and cannot be automated for Codex with the supported workflow.

#### Scenario: Codex automation boundary is visible
- **WHEN** an operator or agent user installs the Codex Lucid workflow
- **THEN** the documentation states which of `session_start`, `post_edit`, `post_command`, `post_tool`, `pre_compact`, and `session_end` are automated, optional, or unsupported

### Requirement: Codex supports post-edit capture through watcher or diff-based workflow
The system SHALL support an optional Codex post-edit capture path that observes real file changes without requiring native Codex edit hooks.

#### Scenario: File change triggers Codex post-edit handling
- **WHEN** the optional Codex watcher or diff-based capture path is enabled and a significant file change is detected
- **THEN** Lucid emits a `post_edit` action through the normalized hook workflow
- **AND** it applies the same significance and deduplication policies used by other agents

### Requirement: Codex session end can persist a handoff summary
The system SHALL support a Codex workflow that records a final Lucid memory summary when the session wrapper exits or when the user explicitly finalizes the session.

#### Scenario: Codex session finalizes
- **WHEN** the supported Codex Lucid workflow is terminated normally or finalized explicitly
- **THEN** Lucid stores a session-end handoff summary through the shared memory workflow

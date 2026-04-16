## ADDED Requirements

### Requirement: OpenCode uses a plugin bridge for Lucid memory hooks
The system SHALL support OpenCode integration through a plugin bridge that forwards supported OpenCode events into the normalized Lucid hook workflow.

#### Scenario: Plugin forwards session and edit events
- **WHEN** the OpenCode plugin receives a supported event
- **THEN** it forwards the event payload to the Lucid hook runner without embedding secrets directly in the plugin file

### Requirement: OpenCode event coverage includes session, edit, command, and tool events
The system SHALL document and support a concrete mapping from OpenCode events into Lucid normalized events.

#### Scenario: Supported OpenCode event maps to normalized event
- **WHEN** OpenCode emits one of `session.created`, `session.idle`, `session.compacted`, `file.edited`, `command.executed`, or `tool.execute.after`
- **THEN** the plugin bridge maps it to the corresponding Lucid normalized event before invoking Lucid hook logic

### Requirement: OpenCode hook bridge reuses the Lucid agent skill workflow
The system SHALL keep OpenCode hook behavior aligned with the same public MCP auth and `mcp2cli` workflow used by the Lucid agent skill.

#### Scenario: OpenCode plugin invokes Lucid without bespoke transport logic
- **WHEN** OpenCode triggers a Lucid hook action
- **THEN** the hook runner uses the standard Lucid endpoint and token environment contract instead of a separate transport or database credential

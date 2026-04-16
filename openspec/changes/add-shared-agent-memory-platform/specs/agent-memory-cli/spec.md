## ADDED Requirements

### Requirement: Agents can use the shared memory service through mcp2cli
The system SHALL support agent access to the shared memory service through `mcp2cli` as a CLI mediation layer.

#### Scenario: Agent discovers available commands
- **WHEN** an agent initializes the `mcp2cli` integration for the shared memory service
- **THEN** it can list available MCP tools and inspect tool help before execution

### Requirement: Agents can reuse persistent mcp2cli sessions
The system SHALL support persistent `mcp2cli` sessions for agents that repeatedly access the shared memory service.

#### Scenario: Agent reuses named session
- **WHEN** an agent starts a named `mcp2cli` session for the shared memory service
- **THEN** subsequent commands can use that named session instead of reconnecting manually each time

### Requirement: CLI integration uses the same public auth contract as direct MCP access
The system SHALL require the same public API-key header contract for `mcp2cli` usage as for direct MCP HTTP clients.

#### Scenario: mcp2cli request includes configured token header
- **WHEN** an agent invokes the shared memory service through `mcp2cli`
- **THEN** the request includes the configured API-key header expected by the public MCP endpoint

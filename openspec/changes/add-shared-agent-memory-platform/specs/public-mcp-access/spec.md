## ADDED Requirements

### Requirement: Public MCP endpoint is exposed on a configured hostname
The system SHALL expose the shared memory service through an MCP HTTP endpoint on a configured public hostname.

#### Scenario: MCP client reaches public endpoint
- **WHEN** an MCP-capable client connects to the shared memory service
- **THEN** it uses the configured public hostname rather than the raw FalkorDB database port

### Requirement: Public MCP traffic requires API-key header authentication
The system SHALL require a configured API-key header before public MCP requests are forwarded to Graphiti.

#### Scenario: Missing token is rejected
- **WHEN** a request reaches the public MCP endpoint without the required API-key header
- **THEN** the request is rejected with an unauthorized response

#### Scenario: Invalid token is rejected
- **WHEN** a request reaches the public MCP endpoint with the wrong API-key header value
- **THEN** the request is rejected with an unauthorized response

#### Scenario: Valid token is forwarded
- **WHEN** a request reaches the public MCP endpoint with the expected API-key header value
- **THEN** the request is forwarded to Graphiti's MCP endpoint

### Requirement: Raw FalkorDB is not the public access surface
The system SHALL keep the public access surface at the MCP layer rather than exposing raw FalkorDB to remote agents.

#### Scenario: Remote agent access uses MCP instead of database port
- **WHEN** a remote agent needs shared memory access
- **THEN** it interacts with the public MCP endpoint
- **AND** it does not require direct public connectivity to FalkorDB

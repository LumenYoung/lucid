## ADDED Requirements

### Requirement: Shared memory runtime uses private FalkorDB-backed Graphiti
The system SHALL provide a shared memory runtime in which Graphiti uses FalkorDB on this machine as the durable persistence layer, with FalkorDB remaining on the internal runtime network.

#### Scenario: Runtime starts with private database connectivity
- **WHEN** the shared memory stack starts
- **THEN** Graphiti connects to FalkorDB over the internal service network
- **AND** FalkorDB is not required to be exposed as a public endpoint for agent access

### Requirement: Shared memory persists across service restarts
The system SHALL retain stored memory when the Graphiti service or FalkorDB service is restarted.

#### Scenario: Stored memory survives restart
- **WHEN** a memory is written successfully and the runtime services restart
- **THEN** the memory remains queryable after the services become healthy again

### Requirement: Graphiti uses an internal FalkorDB service credential in v1
The system SHALL use an internal FalkorDB service credential for Graphiti connectivity in the first implementation phase.

#### Scenario: Graphiti authenticates without per-agent FalkorDB identities
- **WHEN** Graphiti initializes its FalkorDB connection
- **THEN** it uses a private service credential managed by deployment configuration
- **AND** the runtime does not require distinct FalkorDB users per agent in v1

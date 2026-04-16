## ADDED Requirements

### Requirement: Lucid defines an agent-facing memory usage policy above the Graphiti MCP tool surface
The system SHALL provide a Lucid skill interface that tells agents how to use Graphiti memory tools well, rather than relying on Graphiti tool descriptions alone.

#### Scenario: Agent decides whether to use memory tools
- **WHEN** an agent considers interacting with Lucid memory
- **THEN** the Lucid skill interface guides the agent to choose among searching first, skipping the write, or preparing a write

### Requirement: Lucid skill interface teaches search-before-write behavior
The system SHALL instruct agents to search memory before writing when the candidate knowledge may already exist in Lucid.

#### Scenario: Candidate memory might already exist
- **WHEN** an agent is about to store knowledge that could already be represented in Lucid
- **THEN** the skill guidance directs the agent to search relevant nodes or facts before writing a new memory

### Requirement: Lucid skill interface includes a skip-write path
The system SHALL make it explicit that some candidate content should not be written to Lucid at all.

#### Scenario: Candidate content is low-value
- **WHEN** an event contains only transient, trivial, or reconstructible information
- **THEN** the Lucid skill guidance directs the agent to skip writing it to graph memory

### Requirement: Lucid skill interface documents the current extraction-control boundary
The system SHALL document that the current Lucid skill layer cannot control Graphiti's internal extraction prompts through `custom_extraction_instructions`.

#### Scenario: Agent wants to influence Graphiti extraction behavior
- **WHEN** an operator or agent author reviews the Lucid skill interface
- **THEN** the documentation states that the current MCP write path does not expose `custom_extraction_instructions`
- **AND** the skill guidance focuses on shaping the episode content instead

## ADDED Requirements

### Requirement: Lucid writes use the current Graphiti MCP contract
The system SHALL prepare Lucid writes using the current Graphiti MCP write fields rather than requiring graph-native node or edge payloads.

#### Scenario: Agent prepares a Lucid write
- **WHEN** an agent writes memory to Lucid through Graphiti MCP
- **THEN** the write is organized around `name`, `source`, `source_description`, and `episode_body`

### Requirement: Lucid selects Graphiti source type deliberately
The system SHALL define guidance for choosing `json`, `text`, or `message` based on the nature of the source content.

#### Scenario: Agent writes curated machine memory
- **WHEN** an agent prepares a curated memory summary for Lucid
- **THEN** the guidance prefers `source="json"` unless the content is better preserved as prose

#### Scenario: Agent writes prose source material
- **WHEN** the source content is primarily prose such as a cleaned note or paper synthesis
- **THEN** the guidance prefers `source="text"`

#### Scenario: Agent writes actual dialogue
- **WHEN** the source content is a real dialogue or transcript-like exchange
- **THEN** the guidance may use `source="message"`

### Requirement: Lucid envelope preserves provenance and retrieval cues
The system SHALL encourage writes to preserve provenance and retrieval-relevant context inside the Graphiti write envelope.

#### Scenario: Agent writes high-value memory
- **WHEN** an agent prepares a high-value Lucid write
- **THEN** the guidance includes provenance and source context in `source_description` and or `episode_body`
- **AND** the resulting content remains suitable for Graphiti's own extraction pipeline

### Requirement: Lucid envelope optimizes for Graphiti extraction rather than precomputed graph structure
The system SHALL shape content for Graphiti ingestion without requiring the agent to emit graph-native entities or edges directly.

#### Scenario: Agent prepares episode body
- **WHEN** an agent creates `episode_body` for Lucid
- **THEN** the guidance optimizes for clear entities, stable facts, and low-noise context
- **AND** it does not require the agent to generate the final graph structure itself

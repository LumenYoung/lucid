## Why

Lucid currently exposes Graphiti's MCP tools, but that only tells an agent what it can call, not how it should use memory well. We need a Lucid-specific ingestion skill interface that teaches agents when to search, when to skip writing, how to choose `text` versus `json` versus `message`, and how to shape episodes so Graphiti can extract useful graph structure without excessive noise.

## What Changes

- Add a Lucid agent-facing ingestion skill interface that defines the decision policy for searching, skipping writes, and writing memory.
- Add a standardized Graphiti write envelope for Lucid that organizes `name`, `source`, `source_description`, and `episode_body` around provenance, importance, and retrieval quality.
- Document the responsibility boundary between Graphiti MCP tool contracts and Lucid skill prompts.
- Document the current control-surface limitation that Lucid cannot pass `custom_extraction_instructions` through the existing Graphiti MCP write path.

## Capabilities

### New Capabilities
- `ingestion-skill-interface`: Define how agents should decide when to search memory, when to skip writes, and when to write to Lucid through the Graphiti MCP tools.
- `graphiti-write-envelope`: Define the Lucid-side content contract for Graphiti ingestion, including source selection and episode shaping for high-signal writes.

### Modified Capabilities

None.

## Impact

- Affected systems: `skills/lucid-memory`, future hook behavior, Lucid design notes, and any tooling that prepares writes for Graphiti.
- Dependencies: Graphiti MCP `add-memory`, `search-nodes`, `search-memory-facts`, and `get-episodes`.
- Agent behavior impact: agents will follow a Lucid-specific memory usage policy rather than relying on raw Graphiti tool descriptions alone.
- Known limitation: Lucid skill prompts can shape writes, but cannot currently alter Graphiti's internal extraction prompts through `custom_extraction_instructions` because that parameter is not exposed in the current MCP interface.

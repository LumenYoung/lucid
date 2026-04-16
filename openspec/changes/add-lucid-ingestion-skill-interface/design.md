## Context

Graphiti MCP currently gives agents a tool surface, not a strategy surface. The exposed write path is `add_memory(name, episode_body, group_id, source, source_description, uuid)`, and the exposed retrieval path is mainly `search_nodes`, `search_memory_facts`, and `get_episodes`. After a write, Graphiti runs its own ingestion pipeline: entity extraction, edge extraction, deduplication, and summarization.

This means Lucid should not try to make agents generate graph nodes and edges directly. Instead, Lucid should define how agents prepare good episodes for Graphiti. That agent-side guidance belongs in a Lucid skill prompt, not in Graphiti's internal extraction prompts.

There is an important control-surface limit: Graphiti core supports `custom_extraction_instructions`, but the current MCP `add_memory` tool does not expose it. So Lucid's practical levers today are:

- whether to search before writing
- whether to skip writing
- what `source` type to choose
- how to shape `name`, `source_description`, and `episode_body`

## Goals / Non-Goals

**Goals:**
- Define a Lucid-specific skill interface for memory usage decisions.
- Standardize the write envelope that agents prepare before calling Graphiti MCP.
- Keep the agent-facing guidance compatible with Graphiti's current MCP surface.
- Reduce graph pollution by making write decisions explicit and disciplined.
- Preserve the option to evolve toward richer metadata or extraction controls later.

**Non-Goals:**
- Replacing Graphiti's internal extraction pipeline.
- Requiring agents to generate graph-native node/edge payloads.
- Adding `custom_extraction_instructions` support through MCP in this change.
- Finalizing Lucid's long-term ontology or full metadata schema.

## Decisions

### 1. Lucid skill prompts define memory strategy; Graphiti MCP defines tool contracts

Lucid will treat the Graphiti MCP layer as a transport and tool contract layer. The higher-level memory strategy belongs in the Lucid skill prompt.

Rationale:
- Graphiti MCP documents what can be called, not when or why.
- Lucid needs a consistent memory discipline across Codex, OpenCode, and other future agents.
- This preserves a clean boundary between application policy and Graphiti internals.

### 2. Agents decide search / skip / write before preparing a write envelope

The first step in the Lucid skill workflow will be a decision phase:

- search first
- skip write
- prepare write

Rationale:
- Not every event should become graph memory.
- Search-before-write reduces duplicates and encourages reuse of existing memory.
- A deliberate skip path is necessary to avoid graph pollution.

### 3. The write envelope uses Graphiti-native fields, not graph-native schema

Lucid should standardize on the current Graphiti MCP write contract:

- `name`
- `source`
- `source_description`
- `episode_body`

The skill prompt may encourage internal structure inside `episode_body`, but it should not require the agent to emit nodes and edges.

Rationale:
- This matches the current MCP surface exactly.
- Graphiti already expects to do the extraction work itself.
- It avoids over-fitting Lucid to Graphiti internals in a brittle way.

### 4. `json` is preferred for curated agent memory; `text` is preferred for prose sources

Lucid should instruct agents to choose source types deliberately:

- `json`: curated agent memory and machine-shaped summaries
- `text`: cleaned prose, note content, paper synthesis, and human-authored summaries
- `message`: actual dialogue or transcript-like content only

Rationale:
- Graphiti uses different extraction prompts for `text`, `json`, and `message`.
- `json` provides better structure for curated agent-side memory without requiring graph-native payloads.
- `message` should remain narrow to genuine conversational content.

### 5. Provenance belongs in the envelope content even before Lucid exposes first-class metadata filters

Lucid should encourage agents to preserve provenance and source context inside the write envelope, especially in `source_description` and `episode_body`.

Rationale:
- Provenance helps future consolidation, cleanup, and cross-source reasoning.
- The current Graphiti MCP interface does not provide a first-class Lucid metadata filter model.
- Writing provenance now keeps future migration options open.

### 6. Lucid should explicitly document unavailable controls

The skill interface should explicitly state that `custom_extraction_instructions` is not currently available through the MCP write path.

Rationale:
- Avoids designing prompts around a control surface that does not exist today.
- Keeps expectations realistic for agent writers and future implementers.

## Risks / Trade-offs

- [Skill guidance too vague] -> Agents will still write noisy memory. The interface should define concrete search/skip/write rules.
- [Skill guidance too rigid] -> Agents may miss useful memory opportunities. The policy should emphasize intent and examples rather than only hard rules.
- [Overuse of `json`] -> Agents may generate brittle machine-shaped content that reads poorly. Keep the envelope minimal and semantically clear.
- [Overuse of `text`] -> Graphiti may receive noisy prose and extract weak entities. Prefer `json` for curated machine memory.
- [No `custom_extraction_instructions`] -> Fine-grained extraction tuning is deferred. Improve write quality first and treat MCP extension as a later step.

## Migration Plan

1. Add OpenSpec requirements for the Lucid ingestion skill interface and Graphiti write envelope.
2. Update Lucid skill assets to reflect the new decision policy and envelope guidance.
3. Validate the guidance against live Lucid writes and retrieval results.
4. Revisit whether MCP should later expose `custom_extraction_instructions` after real usage data exists.

Rollback strategy:
- Revert to the simpler Lucid skill guidance that only explains direct tool invocation.
- Keep Graphiti MCP usage unchanged, because this change is agent-policy only.

## Open Questions

- Should Lucid standardize a minimal JSON envelope shape in the skill, or only describe content principles?
- How strongly should the skill distinguish between `json` and `text` for mixed sources like cleaned notes?
- Should provenance be required in every curated write, or only recommended?

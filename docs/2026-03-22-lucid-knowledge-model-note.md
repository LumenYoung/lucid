# 2026-03-22
# Topic: Lucid Knowledge Model, Partitioning, and Ingestion Planning

## Status

Working note. High-level design only. This document records current thinking and open questions; it is not a finalized implementation plan.

## Why this note exists

Lucid is moving beyond code-agent memory. It is expected to ingest:

- code-related experience and architecture knowledge
- paper reading and research synthesis
- personal knowledge and preferences
- note systems such as SilverBullet or Obsidian-derived content

These sources need partial separation, but they should still be able to produce meaningful links over time. The core design question is how to separate without destroying future graph value.

## Current Graphiti constraints

The current Graphiti backend imposes several constraints that matter for Lucid design.

### 1. `group_id` is a hard partition

`group_id` is validated as a simple identifier and is used throughout storage and search as a graph partition key. It is not a lightweight tag.

Relevant code:

- `validate_group_id()` only accepts ASCII alphanumeric, `_`, and `-`:
  - `/home/yang/git/graphiti/graphiti_core/helpers.py`
- `add_episode()` uses `group_id` to select or clone the backing database:
  - `/home/yang/git/graphiti/graphiti_core/graphiti.py`
- search paths filter explicitly on `group_ids`:
  - `/home/yang/git/graphiti/graphiti_core/search/search_utils.py`

Implication:

- using many fine-grained groups will create isolated memory islands
- cross-group querying is possible
- cross-group graph structure is not the same as having one connected graph

### 2. Graphiti has labels and attributes, but not a first-class Lucid tag system

Graphiti nodes and edges can carry:

- `labels`
- `attributes`

Relevant code:

- `EntityNode.labels` and `EntityNode.attributes`
  - `/home/yang/git/graphiti/graphiti_core/nodes.py`
- `EntityEdge.attributes`
  - `/home/yang/git/graphiti/graphiti_core/edges.py`

However, the current Lucid MCP surface does not expose a generic tag or metadata filtering model. Today, Lucid mainly exposes:

- `add-memory`
- `search-nodes`
- `search-memory-facts`
- `get-episodes`

Implication:

- a "single unified group + tags" model is attractive conceptually
- but it is not yet backed by a clean, first-class retrieval and filtering interface in the current MCP layer

### 3. Graphiti MCP exposes tool contracts, not agent-facing strategy prompts

Graphiti has many internal LLM prompts for extraction, deduplication, and summarization, but these are internal implementation prompts. They are not exposed as MCP prompts for the agent to consume directly.

Today, the Lucid-facing MCP surface is primarily a tool surface:

- `add-memory`
- `search-nodes`
- `search-memory-facts`
- `get-episodes`
- `get-status`

Implication:

- Graphiti MCP currently tells the agent what tools exist and how to call them
- Graphiti MCP does not provide the higher-level agent strategy for when to search, when to skip writing, or how to prepare the best ingestion content
- Lucid therefore needs its own skill prompt layer that teaches agents how to use the Graphiti tools well

### 4. `custom_extraction_instructions` exists in Graphiti core but is not exposed through the current MCP write path

Graphiti core supports `custom_extraction_instructions` during episode ingestion. This can influence the internal extraction prompts used for entities and edges.

However, the current MCP `add_memory` tool does not expose a parameter for passing `custom_extraction_instructions`. The current MCP write contract is effectively:

- `name`
- `episode_body`
- `group_id`
- `source`
- `source_description`
- `uuid`

Implication:

- Lucid cannot currently control Graphiti extraction behavior from the skill side by passing custom extraction instructions
- the main lever Lucid has today is the quality and structure of the `episode_body`, along with correct choice of `source` and `source_description`
- any future desire to tune extraction behavior per write would require an MCP-layer extension or upstream patch

### 5. Ingestion quality is strongly model-dependent

Graphiti ingestion is built around entity extraction, edge extraction, resolution, and summarization. The upstream docs explicitly note that it works best with providers that support strong structured output.

Implication:

- Lucid should avoid raw, noisy free-form ingestion as the dominant write pattern
- structured envelopes and explicit write criteria will matter a lot

## High-level design direction

## A. Keep partitioning coarse, not fine

Do not use one `group_id` per note, paper, session, or agent. That will over-partition the graph.

If Lucid uses multiple groups, they should represent coarse trust or lifecycle boundaries only. Examples of possible coarse domains:

- code
- research
- personal
- ops
- bridge or synthesis

The final set is still open and should be kept intentionally small in v1.

## B. Separate hard partitioning from logical structure

Lucid should treat these as different layers:

- hard partitioning: `group_id`
- logical structure: domain, source type, confidence, importance, cross-domain linkage, provenance

The logical structure should not be encoded entirely into `group_id`.

This suggests using a structured ingestion envelope even before Lucid exposes a formal metadata filter API.

## C. Prefer explicit cross-group references over blind duplication

Open question raised in discussion:

- instead of a dedicated bridge group, should Lucid use cross-group references such as `origin_group_id` and `origin_object_id`?

Current view:

- this is a good idea and should be preserved even if a bridge group exists
- if knowledge is ported or synthesized into another group, Lucid should preserve where it came from

Recommended provenance fields for future ingestion envelopes:

- `origin_group_id`
- `origin_object_type`
- `origin_object_id`
- `source_ref`
- `derived_from`

This provenance model is cleaner than silent duplication.

## D. A bridge group is still useful, but only for synthesis

The purpose of a bridge group should not be "copy everything important from other groups." Its purpose should be:

- store synthesized cross-domain knowledge
- preserve deliberate connections between otherwise separate domains
- avoid expecting Graphiti to infer reliable cross-boundary meaning from isolated partitions

If a bridge group is used, every bridge entry should carry explicit provenance back to its source group and source object.

## E. A single unified group remains attractive, but is not yet obviously the right v1 choice

A single unified group plus tags would maximize flexibility and future cross-domain linking.

However, given the current Graphiti and Lucid surface, this approach has risks:

- no first-class tag governance model on the Lucid MCP surface
- no explicit tag-filtered retrieval interface yet
- higher risk of graph pollution from mixed low-value content
- harder long-term cleanup if ingestion discipline is weak

So the idea should remain open, but not assumed.

Current recommendation:

- do not commit to unified-group-only until Lucid has a stronger ingestion envelope and review policy

## Important-vs-noisy ingestion criteria

Lucid should not be the default sink for every edit or note. Entering the graph should be treated as a promotion step.

### Likely good Lucid candidates

- stable architecture decisions
- recurring gotchas
- durable preferences that influence future behavior
- research takeaways that were already synthesized
- cross-project or cross-domain concepts
- curated summaries of important sessions
- canonical entity and relation knowledge

### Likely poor Lucid candidates

- raw command output
- temporary debugging attempts without conclusion
- trivial file edits
- unsynthesized paper highlights
- session noise and status chatter
- local details that can be reconstructed cheaply from the source of truth

## Prompt and write-shape direction

Lucid should eventually prefer structured writes over raw prose-heavy ingestion.

The division of responsibility should be explicit:

- Graphiti MCP tool descriptions define what tools exist and how to call them
- Lucid skill prompts define how an agent should use those tools well

In particular, the Lucid skill layer should decide:

- when to search before writing
- when to skip writing entirely
- whether a write should use `text`, `json`, or `message`
- how to shape a high-signal episode for Graphiti ingestion

The Lucid skill layer should not pretend it can directly tune Graphiti's internal extraction prompts, because the current MCP surface does not expose that control.

Future ingestion should aim to capture at least:

- domain
- source type
- provenance
- short summary
- stable facts
- importance
- confidence
- suggested related entities or concepts

This could be supplied as structured JSON episodes or a disciplined text template before being passed into Graphiti.

## Long-term management goals

These are not immediate implementation tasks, but they should inform future scaffolding.

- visibility into what entered the knowledge base and why
- reviewable staging before graph promotion
- provenance-preserving cross-group or cross-source synthesis
- periodic consolidation and cleanup
- explicit retention and archive policies
- operator-facing visualization behind interactive auth

## Open questions

1. Should Lucid start with multiple coarse groups plus provenance, or one unified group plus soft structure?
2. If a bridge group exists, what should qualify as "synthesis" rather than duplication?
3. Should Lucid expose a first-class metadata or tag filter before converging on a unified-group design?
4. How much ingestion should be automatic, and how much should go through a review or staging layer?
5. Should the write-time model for Lucid be stronger than the default day-to-day agent model in order to preserve graph quality?

## Current recommendation for next discussion

The next discussion should focus on one narrow question:

- define the ingestion envelope and provenance model first

That decision will make the `group_id` choice easier, because it determines how much structure Lucid can safely keep outside the hard partition key.

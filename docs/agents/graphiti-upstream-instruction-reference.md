# Graphiti Upstream Instruction Reference

This document extracts the agent-facing instruction text from the upstream Graphiti project so it
can be compared against Lucid's current MCP instruction design.

Source repos and files:

- Server-level MCP instruction:
  [graphiti_mcp_server.py](</home/yang/git/graphiti/mcp_server/src/graphiti_mcp_server.py:165>)
- Tool descriptions:
  [graphiti_mcp_server.py](</home/yang/git/graphiti/mcp_server/src/graphiti_mcp_server.py:371>)
- Additional agent rule document in the upstream repo:
  [cursor_rules.md](/home/yang/git/graphiti/mcp_server/docs/cursor_rules.md:1)

## What Upstream Actually Exposes

There are three different layers in the upstream project:

1. `FastMCP(..., instructions=...)`
   This is the server-level instruction that MCP clients can receive from the server.
2. Tool docstrings and argument descriptions
   These are exposed through the MCP tool schema and are often what the model sees when selecting
   or calling a tool.
3. `docs/cursor_rules.md`
   This is not part of the MCP server runtime. It is an extra client-side guidance document.

If you only want the instruction that is truly built into upstream Graphiti MCP, the critical parts
are section 1 and section 2 below.

## 1. Upstream Server-Level MCP Instruction

Source:
[graphiti_mcp_server.py:166-194](</home/yang/git/graphiti/mcp_server/src/graphiti_mcp_server.py:166>)

> Graphiti is a memory service for AI agents built on a knowledge graph. Graphiti performs well
> with dynamic data such as user interactions, changing enterprise data, and external information.
>
> Graphiti transforms information into a richly connected knowledge network, allowing you to
> capture relationships between concepts, entities, and information. The system organizes data as episodes
> (content snippets), nodes (entities), and facts (relationships between entities), creating a dynamic,
> queryable memory store that evolves with new information. Graphiti supports multiple data formats, including
> structured JSON data, enabling seamless integration with existing data pipelines and systems.
>
> Facts contain temporal metadata, allowing you to track the time of creation and whether a fact is invalid
> (superseded by new information).
>
> Key capabilities:
> 1. Add episodes (text, messages, or JSON) to the knowledge graph with the add_memory tool
> 2. Search for nodes (entities) in the graph using natural language queries with search_nodes
> 3. Find relevant facts (relationships between entities) with search_facts
> 4. Retrieve specific entity edges or episodes by UUID
> 5. Manage the knowledge graph with tools like delete_episode, delete_entity_edge, and clear_graph
>
> The server connects to a database for persistent storage and uses language models for certain operations.
> Each piece of information is organized by group_id, allowing you to maintain separate knowledge domains.
>
> When adding information, provide descriptive names and detailed content to improve search quality.
> When searching, use specific queries and consider filtering by group_id for more relevant results.
>
> For optimal performance, ensure the database is properly configured and accessible, and valid
> API keys are provided for any language model operations.

### Observations

- This instruction is high-level and product-oriented.
- It teaches the concepts `episodes`, `nodes`, `facts`, and `group_id`.
- It gives very little operational guidance on what makes a good episode.
- It does not define concrete writing heuristics such as when to skip writing.
- It mentions `search_facts`, but the actual tool name in the source is `search_memory_facts`.

## 2. Upstream Tool-Level Instruction Surface

These are the tool docstrings and argument descriptions that matter in practice.

### `add_memory`

Source:
[graphiti_mcp_server.py:372-419](</home/yang/git/graphiti/mcp_server/src/graphiti_mcp_server.py:372>)

What upstream tells the model:

- `add_memory` is the primary way to add information to the graph.
- The call returns immediately and processing happens in the background.
- Episodes for the same `group_id` are processed sequentially.
- `name` should be the episode name.
- `episode_body` should be the actual content.
- If `source='json'`, `episode_body` must be an escaped JSON string, not a raw dict.
- `group_id` is optional and falls back to the server default.
- For normal shared-agent usage, the docstring already recommends omitting `group_id` unless a hard partition is intended.
- `source` supports `text`, `json`, and `message`.
- `source_description` is optional.
- `uuid` is optional.

Notable example content in upstream:

> Add an episode to memory. This is the primary way to add information to the graph.
>
> This function returns immediately and processes the episode addition in the background.
> Episodes for the same group_id are processed sequentially to avoid race conditions.

And for `group_id`:

> If omitted, the server default group_id is used.
> For normal shared-agent usage, prefer omitting this and letting the service
> default route the write. Do not invent repo-specific or session-specific
> group ids unless you intentionally need a separate hard partition.

### `search_nodes`

Source:
[graphiti_mcp_server.py:460-473](</home/yang/git/graphiti/mcp_server/src/graphiti_mcp_server.py:460>)

What upstream tells the model:

- Use `query` for the natural-language search.
- `group_ids` is optional.
- `max_nodes` defaults to `10`.
- `entity_types` can filter node labels.

This is a thin tool description. It does not teach a retrieval strategy beyond parameter usage.

### `search_memory_facts`

Source:
[graphiti_mcp_server.py:540-553](</home/yang/git/graphiti/mcp_server/src/graphiti_mcp_server.py:540>)

What upstream tells the model:

- Use it to search for relevant facts.
- `group_ids` is optional.
- `max_facts` defaults to `10`.
- `center_node_uuid` can center search around a node.

Again, this explains parameters, not behavior policy.

### `delete_entity_edge`

Source:
[graphiti_mcp_server.py:594-599](</home/yang/git/graphiti/mcp_server/src/graphiti_mcp_server.py:594>)

What upstream tells the model:

- It deletes an entity edge by `uuid`.

### `delete_episode`

Source:
[graphiti_mcp_server.py:620-625](</home/yang/git/graphiti/mcp_server/src/graphiti_mcp_server.py:620>)

What upstream tells the model:

- It deletes an episode by `uuid`.

Important operational note:

- The docstring does not mention that deleting an episode does not necessarily remove all derived
  entity nodes and relationships that ingestion created later.

### `get_entity_edge`

Source:
[graphiti_mcp_server.py:646-651](</home/yang/git/graphiti/mcp_server/src/graphiti_mcp_server.py:646>)

What upstream tells the model:

- It retrieves a fact edge by `uuid`.

### `get_episodes`

Source:
[graphiti_mcp_server.py:673-682](</home/yang/git/graphiti/mcp_server/src/graphiti_mcp_server.py:673>)

What upstream tells the model:

- It returns episodes.
- `group_ids` is optional.
- `max_episodes` defaults to `10`.

### `clear_graph`

Source:
[graphiti_mcp_server.py:741-746](</home/yang/git/graphiti/mcp_server/src/graphiti_mcp_server.py:741>)

What upstream tells the model:

- It clears graph data for specified `group_ids`.
- If `group_ids` is omitted, it clears the default group.

This is powerful but upstream gives no extra caution text beyond the parameter description.

### `get_status`

Source:
[graphiti_mcp_server.py:776-777](</home/yang/git/graphiti/mcp_server/src/graphiti_mcp_server.py:776>)

What upstream tells the model:

- It reports server and database status.

## 3. Upstream Extra Client-Side Rule Document

Source:
[cursor_rules.md](</home/yang/git/graphiti/mcp_server/docs/cursor_rules.md:1>)

This is not the MCP server instruction itself, but it is the closest thing upstream has to a
practical memory workflow policy.

### Before Starting Any Task

Source:
[cursor_rules.md:3-8](</home/yang/git/graphiti/mcp_server/docs/cursor_rules.md:3>)

> - Always search first
> - Search for facts too
> - Filter by entity type
> - Review all matches

### Always Save New Or Updated Information

Source:
[cursor_rules.md:10-17](</home/yang/git/graphiti/mcp_server/docs/cursor_rules.md:10>)

> - Capture requirements and preferences immediately
> - Split very long requirements into shorter chunks
> - Be explicit if something is an update
> - Document procedures clearly
> - Record factual relationships
> - Be specific with categories

### During Your Work

Source:
[cursor_rules.md:19-24](</home/yang/git/graphiti/mcp_server/docs/cursor_rules.md:19>)

> - Respect discovered preferences
> - Follow procedures exactly
> - Apply relevant facts
> - Stay consistent

### Best Practices

Source:
[cursor_rules.md:26-34](</home/yang/git/graphiti/mcp_server/docs/cursor_rules.md:26>)

> - Search before suggesting
> - Combine node and fact searches
> - Use `center_node_uuid`
> - Prioritize specific matches
> - Be proactive about storing patterns

## 4. Practical Summary

If you compare upstream Graphiti against Lucid, the upstream project is strong on:

- explaining what the system is
- naming the major entry points
- explaining basic parameters for each tool
- pushing a generic "search first, then write" workflow in the extra Cursor rule doc

Upstream Graphiti is weak on:

- defining what makes a high-value episode
- defining required fields for a durable episode
- telling the model when not to write
- teaching compact, normalized episode structure
- warning about ingestion side effects such as derived entities surviving episode deletion

## 5. Bottom Line

There is no especially rich hidden server instruction in upstream Graphiti.

The upstream instruction surface is mostly:

1. one short general-purpose MCP server instruction string
2. tool docstrings with parameter guidance
3. one extra client-side `cursor_rules.md` file with a more practical workflow

If you want Lucid to teach:

- how to use entry points well
- how to compose good episodes
- what fields are required
- what should be skipped

then Lucid needs to go meaningfully beyond upstream Graphiti's built-in instruction layer.

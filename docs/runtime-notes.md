# Lucid Runtime Notes

This document records runtime-specific behavior and non-obvious Graphiti/FalkorDB constraints that
matter when operating or extending Lucid.

## FalkorDB Group Handling

Lucid uses one configured FalkorDB database and treats `group_id` as a logical partition inside that
database.

This is intentionally different from upstream Graphiti's default FalkorDB behavior.

Upstream behavior:

- `graphiti_core.add_episode()` treats a provided `group_id` as a FalkorDB database switch
- for FalkorDB, that means `group_id=work` can cause writes to move from `default_db` into a
  different physical graph database

Lucid behavior:

- Lucid pins FalkorDB access to the configured database, typically `default_db`
- `group_id` remains a logical field used for filtering and policy
- Lucid's custom Falkor driver overrides Graphiti's `clone(database=...)` path so group writes do
  not silently switch databases

Relevant files:

- `src/lucid_mcp/falkordb_driver.py`
- `src/lucid_mcp/server.py`

## Streamable HTTP Behind Caddy

When Caddy proxies the Lucid MCP HTTP endpoint, it must send:

```text
Host: localhost:8000
```

Without that upstream host override, FastMCP returns:

- `421 Invalid Host header`

This applies to all routed Lucid endpoints, including `/mcp`, `/work/mcp`, and `/internal/mcp`.

## Route-Based Profile Selection

Lucid currently supports:

- `/work/mcp`
- `/internal/mcp`
- `/mcp` as a compatibility alias to the work profile

Lucid can now expose all three endpoints from a single HTTP service. Caddy only needs to handle
authentication and reverse proxying. The route table, profiles, and subgroup instruction groups live in
`config/config.yaml`.

When route-based profile selection is disabled, Lucid falls back to direct `/mcp` behavior and
lets clients provide explicit `group_id` values.

## `add_memory` And Explicit UUIDs

Normal Lucid agent traffic should not send an explicit episode UUID.

Why:

- upstream Graphiti interprets a provided UUID as "load an existing episode with this UUID"
- if that UUID does not already exist, Graphiti errors instead of creating a fresh episode

Implication:

- hooks and instructions should let Lucid create episode UUIDs automatically
- maintenance and replay flows should assume UUIDs are runtime-owned unless a dedicated import path
  is added later

## Queue Semantics

Lucid's `add_memory` tool queues background processing and returns once the episode has been accepted
for processing. It does not guarantee that extraction and graph mutation are fully complete at the
moment the MCP response is returned.

Operationally:

- validation should poll reads after writes instead of assuming immediate visibility
- restarting the runtime during active queue processing can interrupt work in flight

For the current agent integrations, this is acceptable, but it is important to remember during
deployment validation and operational debugging.

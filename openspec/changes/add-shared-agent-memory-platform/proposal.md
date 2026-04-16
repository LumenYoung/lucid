## Why

The current agent memory setup is fragmented across individual agent-local memory stores and ad hoc integrations, which prevents Codex, OpenCode, and Nanobot from sharing durable memory across machines. We need a self-hosted memory platform that centralizes persistence on one machine, exposes a stable public MCP interface, and fits the existing Docker and Caddy deployment model.

## What Changes

- Add a shared memory runtime built on Graphiti and FalkorDB, with FalkorDB kept on the internal network and used as the persistent store for agent memory.
- Add a public MCP endpoint that is protected by API-key header authentication at the reverse-proxy layer.
- Add an agent integration capability based on `mcp2cli`, including a reusable skill and session bootstrap pattern for agents that prefer CLI-mediated MCP access.
- Separate `lucid` into operator-facing deployment references under `deploy/` and `docs/`, and agent-facing skill assets under `skills/`.
- Standardize the v1 authentication model on edge API-key auth for MCP traffic and an internal FalkorDB service credential for Graphiti.
- Keep `lucid` as a thin control repo for specs, deployment templates, skill assets, scripts, and minimal upstream patch overlays instead of vendoring Graphiti.

## Capabilities

### New Capabilities
- `shared-memory-runtime`: Deploy and operate the internal Graphiti and FalkorDB runtime that stores shared agent memory durably on this machine.
- `public-mcp-access`: Expose the Graphiti MCP interface on a configured public hostname with API-key enforcement before requests reach Graphiti.
- `agent-memory-cli`: Let agents consume the shared memory service through `mcp2cli` discovery, invocation, and persistent session workflows.

### Modified Capabilities

None.

## Impact

- Affected systems: future `lucid` deployment artifacts, `docker-com` compose integration, Caddy labels, agent skill/bootstrap documentation, and Graphiti runtime configuration.
- New runtime dependencies: Graphiti MCP server, FalkorDB, and `mcp2cli`-based client workflows.
- Public interface impact: introduces a shared HTTPS MCP endpoint at `/mcp` and an API-key header contract for machine-to-machine access.
- Authentication posture: MCP traffic is protected at the HTTP edge; FalkorDB remains private and is not exposed as a public API.

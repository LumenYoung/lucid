## Why

Lucid currently exposes only the MCP surface, which is appropriate for agents but leaves no authenticated browser interface for operators to inspect or explore the memory graph. We need a separate proposal for browser-facing access so visualization can be exposed safely behind interactive auth without weakening the current API-key-only MCP posture.

## What Changes

- Add a browser-facing Lucid memory UI access capability for graph inspection and operator workflows.
- Add an auth-routing capability that keeps MCP traffic on API-key header auth while routing browser-facing paths through tinyauth.
- Prefer a single-domain deployment on `lucid.lumeny.io` when the upstream UI can tolerate path-based reverse proxying.
- Keep a fallback deployment option that splits API and UI onto separate hostnames if the UI or auth flow proves incompatible with same-domain path routing.
- Document the routing and trust-boundary distinction between machine-to-machine MCP access and human browser access.

## Capabilities

### New Capabilities
- `memory-ui-access`: Expose a browser-facing Lucid memory visualization or operator UI without making it part of the public unauthenticated MCP surface.
- `mixed-auth-routing`: Route MCP requests and browser UI requests through different auth mechanisms on the edge, with API-key auth for MCP and tinyauth for browser access.

### Modified Capabilities

None.

## Impact

- Affected systems: Lucid deployment docs, Caddy label patterns, browser-facing visualization choice, and auth boundary documentation.
- Dependencies: tinyauth, Caddy path or host routing, and either FalkorDB browser or a future Lucid-specific UI surface.
- Public interface impact: introduces a browser access surface in addition to `/mcp`, while preserving MCP's header-auth contract.
- Deployment risk: same-domain mixed routing is feasible in principle, but UI path assumptions, websocket behavior, or auth callback requirements may force a two-domain fallback.

## Context

`lucid` is a control repo for a self-hosted shared memory platform for Codex, OpenCode, and Nanobot that uses Graphiti as the MCP memory service and FalkorDB as the durable backing store on one machine. The public entrypoint should be a configured hostname behind Caddy, and the preferred external auth model is an API-key header.

The repo investigation established several important constraints. Graphiti MCP already supports FalkorDB and HTTP transport at `/mcp/`, so it is a viable foundation. FalkorDB itself exposes Redis-style password and ACL authentication rather than an API-key model. Graphiti's FalkorDB driver supports a username, but the current MCP config/factory path does not pass a FalkorDB username through, so per-user FalkorDB ACL identities are not wired end-to-end in the current upstream path. The existing deployment environment already has working patterns for `mcp2cli` agent sessions and Caddy header-gated APIs, so the new design should reuse those patterns instead of inventing a new auth or client model.

## Goals / Non-Goals

**Goals:**
- Provide a self-hosted shared memory runtime that stores Graphiti data durably in FalkorDB on one machine.
- Expose a public MCP endpoint on a configured hostname that remote agents can consume safely with a simple API-key header.
- Keep FalkorDB private to the internal runtime network and avoid publishing the raw database as a public surface.
- Define a reusable `mcp2cli` integration pattern so agents can use the memory service either as direct HTTP MCP or as a CLI-mediated skill.
- Keep operator-facing deployment material and agent-facing skill material separate inside `lucid`.
- Keep `lucid` focused on deployment control, specs, and minimal overlays instead of forking or vendoring Graphiti wholesale.

**Non-Goals:**
- Building a new memory engine instead of using Graphiti.
- Exposing raw FalkorDB directly to remote agents.
- Requiring tinyauth or interactive user auth for machine-to-machine MCP access in v1.
- Implementing true per-agent FalkorDB ACL identities in v1.
- Rewriting Graphiti MCP request handling to add native API-key auth in v1.

## Decisions

### 1. Use separate Graphiti and FalkorDB services, not Graphiti's combined FalkorDB image

The deployed runtime will use separate Graphiti MCP and FalkorDB services.

Rationale:
- Keeps FalkorDB private and independently operable on the internal network.
- Makes it easier to control public exposure so only Graphiti is reachable through Caddy.
- Avoids coupling browser/UI ports and database ports into the public service by default.
- Fits the user's request to treat the database as the central shared persistence layer on this machine.

Alternatives considered:
- Combined Graphiti+FalkorDB container: simpler for demos, but less precise for networking, security, and operations.

### 2. Use API-key auth at the HTTP edge, not at FalkorDB

The public authentication boundary will be Caddy, using an API-key header such as `X-Lucid-Token`.

Rationale:
- Matches the user's preference for API-key auth where possible.
- FalkorDB source shows password and ACL support, not API-key semantics.
- Graphiti MCP does not currently expose native request auth for `/mcp/`.
- The existing repo already uses this exact Caddy pattern for header-protected APIs.

Alternatives considered:
- Native Graphiti MCP auth: not present in the current Graphiti MCP server code.
- tinyauth/Pocket ID for this endpoint: better suited to human/browser access than machine-to-machine MCP clients.
- Public raw FalkorDB with Redis auth only: rejected because the public surface should be MCP, not the database.

### 3. Keep FalkorDB private and use a single internal service credential in v1

Graphiti will connect to FalkorDB with a single service credential on the private network.

Rationale:
- Graphiti's current config path only forwards FalkorDB password and database, not username.
- This avoids requiring an upstream patch for the first release.
- It keeps the runtime simple while still letting the public interface use API-key auth.

Alternatives considered:
- Per-agent FalkorDB ACL users: desirable later, but requires patching Graphiti MCP config/factory flow to pass username through.
- No FalkorDB password: rejected for production use.

### 4. Reuse `mcp2cli` as the agent-side integration layer

`lucid` will define a skill and bootstrap pattern that uses `mcp2cli` for discovery-first access and persistent sessions.

Rationale:
- This matches the pattern already deployed for Nanobot in `docker-com`.
- It gives a uniform CLI interface to agents that do not want to load the MCP server directly.
- It supports a discovery-first workflow with `--list`, `--help`, and `--session-start`.

Alternatives considered:
- Custom bespoke CLI wrapper for Graphiti only: unnecessary duplication when `mcp2cli` already solves the general problem.
- Direct MCP only: too narrow because some agents will benefit from a CLI mediation layer.

### 5. Keep `lucid` as a thin wrapper repo around upstream Graphiti

`lucid` will own specs, deployment templates, docs, scripts, and any minimal patch overlays, but not a full Graphiti fork.

Rationale:
- This keeps upgrade and maintenance cost low.
- It makes the relationship to upstream explicit.
- It matches the user's choice to keep `lucid` as a thin wrapper.

Alternatives considered:
- Fork Graphiti into `lucid`: rejected because it creates unnecessary long-term maintenance burden.
- Keep deployment outside `lucid`: rejected because the user explicitly wants `lucid` to be the control repo for this system.

### 6. Separate deployment references from agent skill assets

`lucid` will keep server-side reference artifacts and agent-consumable skill assets in separate top-level areas.

Rationale:
- The operator workflow and the agent workflow are different and should not be mixed together.
- Deployment material belongs under `deploy/` and `docs/`, while reusable agent material belongs under `skills/`.
- This makes it easier to evolve the skill independently of the compose examples and deployment notes.

Alternatives considered:
- Mixing deployment docs and skill instructions in a single folder: rejected because it blurs the two audiences.

## Risks / Trade-offs

- [Graphiti upstream lacks FalkorDB username wiring] -> Use a shared internal service credential in v1 and document a follow-up patch if per-user ACL support becomes necessary.
- [Public MCP endpoint could be probed or abused] -> Require explicit API-key header matching at Caddy and do not expose FalkorDB publicly.
- [Header rule ordering in Caddy can misroute requests] -> Use explicit `handle` ordering consistent with existing repo guidance.
- [Remote agents may vary in MCP support] -> Support both direct MCP HTTP and `mcp2cli`-mediated workflows.
- [Keeping `lucid` thin means deployment still spans repos] -> Make `lucid` the source of truth for design/specs and deployment templates while explicitly referencing the runtime repos it coordinates.

## Migration Plan

1. Create OpenSpec artifacts in `lucid` that define the runtime, edge auth, and agent integration capabilities.
2. Add deployment templates and docs in `lucid` that describe the target Graphiti, FalkorDB, and Caddy setup for a configured public hostname.
3. Add the actual runtime services to the compose environment using separate FalkorDB and Graphiti services.
4. Add Caddy label rules for the configured public hostname with API-key-gated forwarding to Graphiti's `/mcp` endpoint.
5. Add the `mcp2cli` skill/bootstrap pattern for agents, starting with the same persistent-session approach already used for Nanobot.
6. Validate add/search memory flows through both direct MCP and `mcp2cli`.

Rollback strategy:
- Remove or disable the public Caddy route for the shared memory endpoint.
- Stop the Graphiti service while keeping FalkorDB data intact.
- Leave `lucid` specs and templates in place even if deployment is postponed.

## Open Questions

- Which exact header name should be standardized for v1: `X-Lucid-Token` or another project-wide naming convention?
- Should the first implementation include a local Graphiti patch for FalkorDB username support, or should that remain explicitly deferred?
- Should `lucid` include deployment templates only, or also a checked-in compose fragment intended to be imported from `docker-com`?

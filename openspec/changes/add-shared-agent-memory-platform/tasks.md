## 1. OpenSpec Proposal and Design

- [x] 1.1 Finalize the proposal for the shared Graphiti and FalkorDB memory platform
- [x] 1.2 Finalize the technical design for internal runtime separation, edge auth, and agent integration

## 2. Runtime Specifications

- [x] 2.1 Define the `shared-memory-runtime` capability for private FalkorDB-backed Graphiti persistence
- [x] 2.2 Define the `public-mcp-access` capability for API-key-gated MCP exposure on a configured public hostname
- [x] 2.3 Define the `agent-memory-cli` capability for `mcp2cli`-based discovery, invocation, and persistent sessions

## 3. Deployment Artifacts

- [x] 3.1 Add `deploy/` templates for separate FalkorDB and Graphiti services
- [x] 3.2 Add Caddy label templates or deployment notes for API-key-gated public exposure
- [x] 3.3 Add env template documentation for internal FalkorDB credentials and public MCP token configuration

## 4. Agent Integration Artifacts

- [x] 4.1 Add a `skills/lucid-memory` skill document that teaches agents to use the service through `mcp2cli`
- [x] 4.2 Add a bootstrap pattern for persistent `mcp2cli` sessions that remote agents can reuse
- [x] 4.3 Document direct MCP and CLI-mediated validation commands for add/search memory flows

## 5. Validation

- [x] 5.1 Validate the OpenSpec change with the local `openspec` CLI
- [x] 5.2 Review the change for consistency between proposal capabilities and spec folder names

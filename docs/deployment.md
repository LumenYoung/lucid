# Deploy Lucid Memory

## Repo split

This repo has two audiences and keeps them separate:

- `deploy/` contains operator-facing reference artifacts for Graphiti, FalkorDB, and Caddy.
- `skills/` contains agent-facing skill assets that consume the public MCP endpoint.

The files here are sanitized examples. They are meant to be copied or merged into your actual compose environment.

## Runtime shape

V1 uses three layers:

- `lucid-falkordb`: private persistence on the internal runtime network only
- `lucid-graphiti`: Graphiti MCP service connected to FalkorDB
- `${LUCID_PUBLIC_HOSTNAME}`: public hostname routed through Caddy with header-based API-key auth

The public surface is Graphiti's MCP HTTP endpoint at `/mcp`. Raw FalkorDB is not exposed publicly.

## Files to use

- `deploy/docker-compose.lucid-memory.example.yml`
- `deploy/caddy/lucid-graphiti.labels.example.yml`
- `deploy/env/lucid-falkordb.env.example`
- `deploy/env/lucid-graphiti.env.example`
- `deploy/graphiti/config-docker-falkordb.yaml`

## Required configuration

Put these values in the compose project `.env` that owns the Caddy labels:

- `LUCID_PUBLIC_HOSTNAME=memory.example.com`
- `LUCID_API_TOKEN=<generated-random-token>`
- `GRAPHITI_MCP_SERVER_PATH=/path/to/graphiti/mcp_server`

Put these values in `deploy/env/lucid-falkordb.env` and `deploy/env/lucid-graphiti.env`:

- `FALKORDB_PASSWORD=<shared-internal-password>`
- `OPENAI_API_KEY=<provider-key>` in the Graphiti env file

## Authentication model

- Public MCP auth uses `X-Lucid-Token` at the Caddy edge.
- The public hostname and token must live in the compose project `.env`, because compose label interpolation does not read service `env_file` values.
- Graphiti connects to FalkorDB with an internal service credential from `deploy/env/lucid-graphiti.env`.
- FalkorDB does not provide API-key auth in this design. Its v1 role is a private database behind Graphiti.

## Deployment notes

- Keep `lucid-falkordb` on a private network only and do not publish `6379`.
- The raw `falkordb/falkordb` image does not enforce `FALKORDB_PASSWORD` by itself. The compose example exports `REDIS_ARGS="--requirepass ..."` in the container entrypoint, which is required if you want password auth.
- When Caddy proxies Graphiti's streamable MCP endpoint, it must send `Host localhost:8000` upstream. Without that header override, Graphiti returns `421 Invalid Host header`.
- Use `https://${LUCID_PUBLIC_HOSTNAME}/mcp` for MCP clients. The endpoint works without a trailing slash.

## Deployment steps

1. Create real env files from the checked-in examples:

```bash
cp deploy/env/lucid-falkordb.env.example deploy/env/lucid-falkordb.env
cp deploy/env/lucid-graphiti.env.example deploy/env/lucid-graphiti.env
```

2. Fill in secrets and project-level variables.

3. Copy or merge `deploy/docker-compose.lucid-memory.example.yml` into your compose repo.

4. Keep the Graphiti service on both the `caddy` network and a private runtime network.

5. Bring the services up from the compose project that contains the merged service definitions:

```bash
docker compose up -d lucid-falkordb lucid-graphiti
```

## Validation

Check auth behavior:

```bash
curl -i "https://${LUCID_PUBLIC_HOSTNAME}/health"
curl -i -H "X-Lucid-Token: wrong" "https://${LUCID_PUBLIC_HOSTNAME}/health"
curl -i -H "X-Lucid-Token: ${LUCID_API_TOKEN}" "https://${LUCID_PUBLIC_HOSTNAME}/health"
```

Check the MCP surface with `mcp2cli`:

```bash
mcp2cli --mcp "https://${LUCID_PUBLIC_HOSTNAME}/mcp" \
  --transport streamable \
  --auth-header "X-Lucid-Token:env:LUCID_API_TOKEN" \
  --list

mcp2cli --mcp "https://${LUCID_PUBLIC_HOSTNAME}/mcp" \
  --transport streamable \
  --auth-header "X-Lucid-Token:env:LUCID_API_TOKEN" \
  get-status
```

If you want the agent-friendly flow instead of raw `mcp2cli`, use the skill under `skills/lucid-memory/`.

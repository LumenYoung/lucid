# Validation commands

These commands assume:

- `LUCID_MCP_URL` is already exported
- `LUCID_API_TOKEN` is already exported
- You are running from the skill directory, or using the correct script path

## Discovery

```bash
bash scripts/lucid-mcp2cli.sh --list
bash scripts/lucid-mcp2cli.sh get-status
bash scripts/lucid-mcp2cli.sh add-memory --help
bash scripts/lucid-mcp2cli.sh search-nodes --help
bash scripts/lucid-mcp2cli.sh search-memory-facts --help
```

## Optional write smoke test

```bash
bash scripts/lucid-mcp2cli.sh add-memory \
  --name "Lucid smoke test" \
  --episode-body "Lucid shared memory smoke test from mcp2cli." \
  --source text \
  --source-description "manual smoke test"
```

## Read it back

```bash
bash scripts/lucid-mcp2cli.sh search-nodes \
  --query "Lucid shared memory smoke test" \
  --max-nodes 5

bash scripts/lucid-mcp2cli.sh search-memory-facts \
  --query "Lucid shared memory smoke test" \
  --max-facts 5

bash scripts/lucid-mcp2cli.sh get-episodes \
  --max-episodes 5
```

## Session mode

```bash
bash scripts/lucid-session-start.sh lucid
mcp2cli --session lucid --list
mcp2cli --session lucid get-status
mcp2cli --session lucid search-nodes --query "Lucid shared memory smoke test" --max-nodes 5
```

If a list-typed argument becomes relevant later, inspect `--help` first and pass comma-separated values where `mcp2cli` expects an array.

# Lucid Memory

Lucid is a shared memory service for AI agents built on `graphiti-core`.

Use Lucid when prior project or user context may matter, or when you learn something durable that another future session would need. Prefer narrow retrieval over broad exploratory search.

For normal usage, do not invent repo-specific, session-specific, or task-specific `group_id` values.

Lucid applies policy at the server boundary:

- if a write group is omitted, the endpoint default is used
- if a disallowed write group is requested, the write is routed to the endpoint default
- reads are filtered through the endpoint's allowed read groups

Good writes are durable, specific, self-contained, and provenance-rich. Skip transient logs, generic success output, repetitive status, and low-value noise.

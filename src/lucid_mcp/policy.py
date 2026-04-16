"""Policy helpers for Lucid MCP group routing."""

from lucid_mcp.config import LucidPolicyConfig


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def resolve_write_group(requested_group_id: str | None, policy: LucidPolicyConfig) -> str:
    """Resolve the write group according to Lucid policy."""
    if requested_group_id and requested_group_id in policy.allowed_write_groups:
        return requested_group_id
    return policy.default_write_group


def resolve_read_groups(
    requested_group_ids: list[str] | None,
    policy: LucidPolicyConfig,
) -> list[str]:
    """Resolve read groups by intersecting with the allowed read set."""
    if requested_group_ids is None:
        return _unique(policy.default_read_groups)

    allowed = [group_id for group_id in requested_group_ids if group_id in policy.allowed_read_groups]
    if allowed:
        return _unique(allowed)
    if policy.fallback_to_default_read_groups:
        return _unique(policy.default_read_groups)
    return []


def can_read_group(group_id: str, policy: LucidPolicyConfig) -> bool:
    return group_id in policy.allowed_read_groups


def can_write_group(group_id: str, policy: LucidPolicyConfig) -> bool:
    return group_id in policy.allowed_write_groups

from lucid_mcp.config import LucidPolicyConfig
from lucid_mcp.policy import resolve_read_groups, resolve_write_group


def test_write_group_defaults_to_profile_default():
    policy = LucidPolicyConfig(
        default_write_group='work',
        allowed_write_groups=['work'],
    )

    assert resolve_write_group(None, policy) == 'work'
    assert resolve_write_group('unknown', policy) == 'work'


def test_write_group_preserves_allowed_override():
    policy = LucidPolicyConfig(
        default_write_group='work',
        allowed_write_groups=['work', 'research'],
    )

    assert resolve_write_group('research', policy) == 'research'


def test_read_groups_default_when_none_requested():
    policy = LucidPolicyConfig(
        default_read_groups=['personal'],
        allowed_read_groups=['personal', 'work'],
    )

    assert resolve_read_groups(None, policy) == ['personal']


def test_read_groups_filter_to_allowed_values():
    policy = LucidPolicyConfig(
        default_read_groups=['personal'],
        allowed_read_groups=['personal', 'work'],
    )

    assert resolve_read_groups(['work', 'research'], policy) == ['work']


def test_read_groups_fall_back_when_request_is_fully_disallowed():
    policy = LucidPolicyConfig(
        default_read_groups=['personal'],
        allowed_read_groups=['personal', 'work'],
        fallback_to_default_read_groups=True,
    )

    assert resolve_read_groups(['research'], policy) == ['personal']


def test_write_group_allows_explicit_group_in_direct_mode():
    policy = LucidPolicyConfig(
        default_write_group='work',
        allowed_write_groups=['work'],
    )

    assert (
        resolve_write_group('research', policy, enforce_group_policy=False) == 'research'
    )


def test_read_groups_preserve_requested_groups_in_direct_mode():
    policy = LucidPolicyConfig(
        default_read_groups=['work'],
        allowed_read_groups=['work'],
    )

    assert resolve_read_groups(
        ['personal', 'research'],
        policy,
        enforce_group_policy=False,
    ) == ['personal', 'research']

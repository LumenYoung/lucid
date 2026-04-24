from pathlib import Path

from lucid_mcp.config import LucidConfig


def test_unified_config_resolves_profiles_and_instruction_groups():
    config = LucidConfig.load_from_path(Path('config/config.yaml').resolve())

    assert sorted(config.profiles) == ['internal', 'work']
    assert config.routing.default_profile == 'work'
    assert config.routing.compatibility_profile == 'work'

    work_config = config.resolve_profile('work')
    internal_config = config.resolve_profile('internal')

    assert work_config.lucid.profile_name == 'work'
    assert work_config.lucid.default_write_group == 'work'
    assert work_config.lucid.instruction_group == 'work'

    assert internal_config.lucid.profile_name == 'internal'
    assert internal_config.lucid.default_write_group == 'personal'
    assert internal_config.lucid.instruction_group == 'personal'


def test_instruction_group_inheritance_uses_default_tool_descriptions():
    config = LucidConfig.load_from_path(Path('config/config.yaml').resolve())

    work_instruction_group = config.resolve_instruction_group('work')
    personal_instruction_group = config.resolve_instruction_group('personal')

    assert 'knowledge graph' in (work_instruction_group.high_level_policy or '')
    assert 'add_memory tool' in (work_instruction_group.direct_policy or '')
    assert 'Add an episode to memory' in (
        work_instruction_group.tool_descriptions.add_memory or ''
    )

    assert personal_instruction_group.tool_descriptions.get_status == (
        work_instruction_group.tool_descriptions.get_status
    )


def test_subgroup_instruction_text_is_explicitly_present():
    config = LucidConfig.load_from_path(Path('config/config.yaml').resolve())

    work_instruction_group = config.resolve_instruction_group('work')
    personal_instruction_group = config.resolve_instruction_group('personal')

    assert work_instruction_group.high_level_policy
    assert work_instruction_group.direct_policy
    assert work_instruction_group.routed_policy
    assert work_instruction_group.tool_descriptions.add_memory

    assert personal_instruction_group.high_level_policy
    assert personal_instruction_group.direct_policy
    assert personal_instruction_group.routed_policy
    assert personal_instruction_group.tool_descriptions.add_memory

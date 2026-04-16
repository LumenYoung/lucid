from lucid_mcp.falkordb_driver import LucidFalkorDriver


def test_clone_ignores_group_database_switch():
    driver = LucidFalkorDriver(falkor_db=object(), database='default_db')

    cloned = driver.clone('work')

    assert isinstance(cloned, LucidFalkorDriver)
    assert cloned is not driver
    assert cloned.client is driver.client
    assert cloned._database == 'default_db'


def test_clone_returns_self_for_same_database():
    driver = LucidFalkorDriver(falkor_db=object(), database='default_db')

    cloned = driver.clone('default_db')

    assert cloned is driver

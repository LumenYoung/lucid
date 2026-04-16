"""Lucid-specific FalkorDB driver behavior."""

from graphiti_core.driver.falkordb_driver import FalkorDriver


class LucidFalkorDriver(FalkorDriver):
    """Keep logical group IDs inside one configured FalkorDB database.

    Upstream graphiti-core treats FalkorDB `group_id` as a database switch during
    writes by cloning the driver to `database=group_id`. Lucid uses `group_id`
    as a logical partition within one shared database, so clone requests must
    stay pinned to the configured database.
    """

    def clone(self, database: str) -> 'LucidFalkorDriver':
        if database == self._database:
            return self

        return LucidFalkorDriver(
            falkor_db=self.client,
            database=self._database,
        )

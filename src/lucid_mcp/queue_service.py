"""Queue service for managing episode processing."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class QueueService:
    """Manage sequential episode processing queues by group_id."""

    def __init__(self):
        self._episode_queues: dict[str, asyncio.Queue] = {}
        self._queue_workers: dict[str, bool] = {}
        self._graphiti_client: Any = None

    async def add_episode_task(
        self, group_id: str, process_func: Callable[[], Awaitable[None]]
    ) -> int:
        if group_id not in self._episode_queues:
            self._episode_queues[group_id] = asyncio.Queue()

        await self._episode_queues[group_id].put(process_func)

        if not self._queue_workers.get(group_id, False):
            asyncio.create_task(self._process_episode_queue(group_id))

        return self._episode_queues[group_id].qsize()

    async def _process_episode_queue(self, group_id: str) -> None:
        logger.info(f'Starting episode queue worker for group_id: {group_id}')
        self._queue_workers[group_id] = True

        try:
            while True:
                process_func = await self._episode_queues[group_id].get()
                try:
                    await process_func()
                except Exception as exc:
                    logger.error(
                        f'Error processing queued episode for group_id {group_id}: {exc}'
                    )
                finally:
                    self._episode_queues[group_id].task_done()
        except asyncio.CancelledError:
            logger.info(f'Episode queue worker for group_id {group_id} was cancelled')
        except Exception as exc:
            logger.error(f'Unexpected error in queue worker for group_id {group_id}: {exc}')
        finally:
            self._queue_workers[group_id] = False
            logger.info(f'Stopped episode queue worker for group_id: {group_id}')

    async def initialize(self, graphiti_client: Any) -> None:
        self._graphiti_client = graphiti_client
        logger.info('Queue service initialized with graphiti client')

    async def add_episode(
        self,
        group_id: str,
        name: str,
        content: str,
        source_description: str,
        episode_type: Any,
        entity_types: Any,
        uuid: str | None,
    ) -> int:
        if self._graphiti_client is None:
            raise RuntimeError('Queue service not initialized. Call initialize() first.')

        async def process_episode():
            logger.info(f'Processing episode {uuid} for group {group_id}')
            await self._graphiti_client.add_episode(
                name=name,
                episode_body=content,
                source_description=source_description,
                source=episode_type,
                group_id=group_id,
                reference_time=datetime.now(timezone.utc),
                entity_types=entity_types,
                uuid=uuid,
            )
            logger.info(f'Successfully processed episode {uuid} for group {group_id}')

        return await self.add_episode_task(group_id, process_episode)

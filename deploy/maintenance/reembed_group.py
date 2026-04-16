#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from common import build_runtime, clone_client_for_group, configure_logging, generate_embeddings_for_communities


LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Refresh stored Graphiti embeddings in place for one or more groups.',
    )
    parser.add_argument(
        '--group-id',
        action='append',
        dest='group_ids',
        required=True,
        help='Graphiti group/database to refresh. Pass multiple times for multiple groups.',
    )
    parser.add_argument(
        '--config',
        type=Path,
        default=None,
        help='Path to the Graphiti YAML config. Defaults to deploy/graphiti/config-docker-falkordb.yaml.',
    )
    parser.add_argument(
        '--env-file',
        action='append',
        default=[],
        type=Path,
        help='Env file to load before reading the config. Pass multiple times if needed.',
    )
    parser.add_argument(
        '--graphiti-mcp-server-path',
        default=None,
        help='Path to the upstream graphiti/mcp_server checkout.',
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Batch size for Graphiti reads and writes.',
    )
    parser.add_argument(
        '--skip-entity-nodes',
        action='store_true',
        help='Do not refresh entity node name embeddings.',
    )
    parser.add_argument(
        '--skip-community-nodes',
        action='store_true',
        help='Do not refresh community node name embeddings.',
    )
    parser.add_argument(
        '--skip-entity-edges',
        action='store_true',
        help='Do not refresh fact edge embeddings.',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Count the work without writing updated embeddings back to the database.',
    )
    parser.add_argument(
        '--semaphore-limit',
        type=int,
        default=None,
        help='Override Graphiti internal concurrency for this maintenance run.',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable debug logging.',
    )
    return parser.parse_args()


async def refresh_entity_nodes(group_client, group_id: str, batch_size: int, dry_run: bool) -> int:
    from graphiti_core.nodes import create_entity_node_embeddings

    total = 0
    cursor = None

    while True:
        batch = await group_client.nodes.entity.get_by_group_ids(
            [group_id],
            limit=batch_size,
            uuid_cursor=cursor,
        )
        if not batch:
            break

        if not dry_run:
            await create_entity_node_embeddings(group_client.embedder, batch)
            await group_client.nodes.entity.save_bulk(batch, batch_size=batch_size)

        total += len(batch)
        cursor = batch[-1].uuid
        LOGGER.info('Group %s: refreshed %s entity nodes so far', group_id, total)

    return total


async def refresh_community_nodes(group_client, group_id: str, batch_size: int, dry_run: bool) -> int:
    total = 0
    cursor = None

    while True:
        batch = await group_client.nodes.community.get_by_group_ids(
            [group_id],
            limit=batch_size,
            uuid_cursor=cursor,
        )
        if not batch:
            break

        if not dry_run:
            await generate_embeddings_for_communities(batch, group_client.embedder)
            await group_client.nodes.community.save_bulk(batch, batch_size=batch_size)

        total += len(batch)
        cursor = batch[-1].uuid
        LOGGER.info('Group %s: refreshed %s community nodes so far', group_id, total)

    return total


async def refresh_entity_edges(group_client, group_id: str, batch_size: int, dry_run: bool) -> int:
    from graphiti_core.edges import create_entity_edge_embeddings
    from graphiti_core.errors import GroupsEdgesNotFoundError

    total = 0
    cursor = None

    while True:
        try:
            batch = await group_client.edges.entity.get_by_group_ids(
                [group_id],
                limit=batch_size,
                uuid_cursor=cursor,
            )
        except GroupsEdgesNotFoundError:
            break

        if not batch:
            break

        if not dry_run:
            await create_entity_edge_embeddings(group_client.embedder, batch)
            await group_client.edges.entity.save_bulk(batch, batch_size=batch_size)

        total += len(batch)
        cursor = batch[-1].uuid
        LOGGER.info('Group %s: refreshed %s entity edges so far', group_id, total)

    return total


async def main() -> int:
    args = parse_args()
    configure_logging(args.verbose)

    runtime = await build_runtime(
        config_path=args.config,
        env_files=args.env_file,
        graphiti_mcp_server_path=args.graphiti_mcp_server_path,
        semaphore_limit=args.semaphore_limit,
        require_embedder=True,
        require_llm=False,
    )

    try:
        for group_id in args.group_ids:
            LOGGER.info('Refreshing group %s', group_id)
            group_client = clone_client_for_group(runtime.client, group_id)
            entity_node_count = 0
            community_node_count = 0
            entity_edge_count = 0

            if not args.skip_entity_nodes:
                entity_node_count = await refresh_entity_nodes(
                    group_client,
                    group_id,
                    args.batch_size,
                    args.dry_run,
                )

            if not args.skip_community_nodes:
                community_node_count = await refresh_community_nodes(
                    group_client,
                    group_id,
                    args.batch_size,
                    args.dry_run,
                )

            if not args.skip_entity_edges:
                entity_edge_count = await refresh_entity_edges(
                    group_client,
                    group_id,
                    args.batch_size,
                    args.dry_run,
                )

            LOGGER.info(
                'Finished group %s: entity_nodes=%s community_nodes=%s entity_edges=%s dry_run=%s',
                group_id,
                entity_node_count,
                community_node_count,
                entity_edge_count,
                args.dry_run,
            )
    finally:
        await runtime.close()

    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))

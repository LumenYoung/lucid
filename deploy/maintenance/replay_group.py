#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from common import build_runtime, clone_client_for_group, configure_logging


LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        '--config',
        type=Path,
        default=None,
        help='Path to the Graphiti YAML config. Defaults to deploy/graphiti/config-docker-falkordb.yaml.',
    )
    shared.add_argument(
        '--env-file',
        action='append',
        default=[],
        type=Path,
        help='Env file to load before reading the config. Pass multiple times if needed.',
    )
    shared.add_argument(
        '--graphiti-mcp-server-path',
        default=None,
        help='Path to the upstream graphiti/mcp_server checkout.',
    )
    shared.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Batch size for episode export.',
    )
    shared.add_argument(
        '--semaphore-limit',
        type=int,
        default=None,
        help='Override Graphiti internal concurrency for this maintenance run.',
    )
    shared.add_argument(
        '--verbose',
        action='store_true',
        help='Enable debug logging.',
    )

    parser = argparse.ArgumentParser(
        description='Export Graphiti episodes and rebuild a group by replaying them through add_episode().',
        parents=[shared],
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    export_parser = subparsers.add_parser(
        'export',
        help='Export all episodes for one group into a JSON snapshot.',
        parents=[shared],
    )
    export_parser.add_argument('--group-id', required=True, help='Source group/database to export.')
    export_parser.add_argument(
        '--snapshot-file',
        type=Path,
        required=True,
        help='JSON snapshot file to write.',
    )
    export_parser.add_argument(
        '--max-episodes',
        type=int,
        default=None,
        help='Optional export cap for smoke tests.',
    )

    replay_parser = subparsers.add_parser(
        'replay',
        help='Replay a previously exported JSON snapshot into a target group.',
        parents=[shared],
    )
    replay_parser.add_argument(
        '--snapshot-file',
        type=Path,
        required=True,
        help='JSON snapshot file produced by the export command.',
    )
    replay_parser.add_argument(
        '--target-group-id',
        required=True,
        help='Target group/database to rebuild.',
    )
    replay_parser.add_argument(
        '--clear-target',
        action='store_true',
        help='Clear the target group before replay.',
    )
    replay_parser.add_argument(
        '--update-communities',
        action='store_true',
        help='Request Graphiti community updates during replay.',
    )

    roundtrip_parser = subparsers.add_parser(
        'roundtrip',
        help='Export a live group to a snapshot and then replay it into a target group.',
        parents=[shared],
    )
    roundtrip_parser.add_argument(
        '--source-group-id',
        required=True,
        help='Source group/database to export.',
    )
    roundtrip_parser.add_argument(
        '--target-group-id',
        required=True,
        help='Target group/database to rebuild.',
    )
    roundtrip_parser.add_argument(
        '--snapshot-file',
        type=Path,
        required=True,
        help='JSON snapshot file to write before replay.',
    )
    roundtrip_parser.add_argument(
        '--clear-target',
        action='store_true',
        help='Clear the target group before replay.',
    )
    roundtrip_parser.add_argument(
        '--update-communities',
        action='store_true',
        help='Request Graphiti community updates during replay.',
    )
    roundtrip_parser.add_argument(
        '--max-episodes',
        type=int,
        default=None,
        help='Optional export cap for smoke tests.',
    )

    return parser.parse_args()


def iso_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def serialize_episode(episode) -> dict[str, Any]:
    return {
        'uuid': episode.uuid,
        'name': episode.name,
        'group_id': episode.group_id,
        'source': episode.source.value,
        'source_description': episode.source_description,
        'content': episode.content,
        'created_at': episode.created_at.isoformat(),
        'valid_at': episode.valid_at.isoformat(),
        'entity_edges': list(episode.entity_edges),
    }


def normalize_episodes(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        episodes,
        key=lambda episode: (
            episode['valid_at'],
            episode['created_at'],
            episode['uuid'],
        ),
    )


def write_snapshot(
    snapshot_path: Path,
    *,
    source_group_id: str,
    episodes: list[dict[str, Any]],
) -> None:
    payload = {
        'format_version': 1,
        'source_group_id': source_group_id,
        'exported_at': iso_now(),
        'episode_count': len(episodes),
        'episodes': normalize_episodes(episodes),
    }
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')


def load_snapshot(snapshot_path: Path) -> dict[str, Any]:
    payload = json.loads(snapshot_path.read_text(encoding='utf-8'))
    if 'episodes' not in payload or not isinstance(payload['episodes'], list):
        raise ValueError(f'Invalid snapshot format in {snapshot_path}')
    payload['episodes'] = normalize_episodes(payload['episodes'])
    return payload


async def export_episodes(group_client, group_id: str, batch_size: int, max_episodes: int | None) -> list[dict[str, Any]]:
    exported: list[dict[str, Any]] = []
    cursor = None

    while True:
        remaining = None if max_episodes is None else max(max_episodes - len(exported), 0)
        if remaining == 0:
            break

        limit = batch_size if remaining is None else min(batch_size, remaining)
        batch = await group_client.nodes.episode.get_by_group_ids(
            [group_id],
            limit=limit,
            uuid_cursor=cursor,
        )
        if not batch:
            break

        exported.extend(serialize_episode(episode) for episode in batch)
        cursor = batch[-1].uuid
        LOGGER.info('Exported %s episodes from group %s so far', len(exported), group_id)

    return normalize_episodes(exported)


async def replay_episodes(
    target_client,
    target_group_id: str,
    episodes: list[dict[str, Any]],
    *,
    update_communities: bool,
) -> int:
    from graphiti_core.nodes import EpisodeType

    replayed = 0

    for episode in episodes:
        await target_client.add_episode(
            name=episode['name'],
            episode_body=episode['content'],
            source_description=episode.get('source_description', ''),
            reference_time=datetime.fromisoformat(episode['valid_at']),
            source=EpisodeType.from_str(episode['source']),
            group_id=target_group_id,
            update_communities=update_communities,
        )
        replayed += 1
        LOGGER.info('Replayed %s/%s episodes into group %s', replayed, len(episodes), target_group_id)

    return replayed


async def clear_target_group(target_client, target_group_id: str) -> None:
    from graphiti_core.utils.maintenance.graph_data_operations import clear_data

    await clear_data(target_client.driver, [target_group_id])


def validate_replay_request(
    *,
    source_group_id: str | None,
    target_group_id: str,
    clear_target: bool,
) -> None:
    if source_group_id and source_group_id == target_group_id and not clear_target:
        raise ValueError(
            'Replay to the same group requires --clear-target. Replaying in place without clearing '
            'can duplicate or corrupt the graph state.'
        )


async def main() -> int:
    args = parse_args()
    configure_logging(args.verbose)

    require_llm = args.command in {'replay', 'roundtrip'}
    require_embedder = args.command in {'replay', 'roundtrip'}

    runtime = await build_runtime(
        config_path=args.config,
        env_files=args.env_file,
        graphiti_mcp_server_path=args.graphiti_mcp_server_path,
        semaphore_limit=args.semaphore_limit,
        require_llm=require_llm,
        require_embedder=require_embedder,
    )

    try:
        if args.command == 'export':
            source_client = clone_client_for_group(runtime.client, args.group_id)
            episodes = await export_episodes(
                source_client,
                args.group_id,
                args.batch_size,
                args.max_episodes,
            )

            write_snapshot(args.snapshot_file, source_group_id=args.group_id, episodes=episodes)
            LOGGER.info(
                'Wrote %s episodes from group %s to %s',
                len(episodes),
                args.group_id,
                args.snapshot_file,
            )
            return 0

        if args.command == 'replay':
            snapshot = load_snapshot(args.snapshot_file)
            source_group_id = snapshot.get('source_group_id')
            validate_replay_request(
                source_group_id=source_group_id,
                target_group_id=args.target_group_id,
                clear_target=args.clear_target,
            )

            target_client = clone_client_for_group(runtime.client, args.target_group_id)
            if args.clear_target:
                LOGGER.info('Clearing target group %s', args.target_group_id)
                await clear_target_group(target_client, args.target_group_id)

            replayed = await replay_episodes(
                target_client,
                args.target_group_id,
                snapshot['episodes'],
                update_communities=args.update_communities,
            )

            LOGGER.info('Replayed %s episodes into group %s', replayed, args.target_group_id)
            return 0

        if args.command == 'roundtrip':
            validate_replay_request(
                source_group_id=args.source_group_id,
                target_group_id=args.target_group_id,
                clear_target=args.clear_target,
            )

            source_client = clone_client_for_group(runtime.client, args.source_group_id)
            episodes = await export_episodes(
                source_client,
                args.source_group_id,
                args.batch_size,
                args.max_episodes,
            )

            write_snapshot(
                args.snapshot_file,
                source_group_id=args.source_group_id,
                episodes=episodes,
            )

            target_client = clone_client_for_group(runtime.client, args.target_group_id)
            if args.clear_target:
                LOGGER.info('Clearing target group %s', args.target_group_id)
                await clear_target_group(target_client, args.target_group_id)

            replayed = await replay_episodes(
                target_client,
                args.target_group_id,
                episodes,
                update_communities=args.update_communities,
            )

            LOGGER.info(
                'Roundtrip complete: exported and replayed %s episodes from %s to %s',
                replayed,
                args.source_group_id,
                args.target_group_id,
            )
            return 0

        raise ValueError(f'Unsupported command: {args.command}')
    finally:
        await runtime.close()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))

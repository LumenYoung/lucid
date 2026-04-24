#!/usr/bin/env python3
"""Lucid MCP server built on graphiti-core."""

import argparse
import asyncio
import logging
import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb import STOPWORDS as FALKOR_STOPWORDS
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.driver.falkordb.operations import search_ops as falkor_search_ops
from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EpisodeType, EpisodicNode
from graphiti_core.search.search_filters import SearchFilters
from graphiti_core.utils.maintenance.graph_data_operations import clear_data
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from lucid_mcp.config import LucidConfig, LucidInstructionGroupConfig, LucidRouteConfig, ServerConfig
from lucid_mcp.falkordb_driver import LucidFalkorDriver
from lucid_mcp.factories import DatabaseDriverFactory, EmbedderFactory, LLMClientFactory
from lucid_mcp.formatting import format_fact_result
from lucid_mcp.policy import can_read_group, can_write_group, resolve_read_groups, resolve_write_group
from lucid_mcp.queue_service import QueueService
from lucid_mcp.response_types import (
    EpisodeSearchResponse,
    ErrorResponse,
    FactSearchResponse,
    NodeResult,
    NodeSearchResponse,
    StatusResponse,
    SuccessResponse,
)

mcp_server_dir = Path(__file__).parent.parent.parent
env_file = mcp_server_dir / '.env'
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv()

SEMAPHORE_LIMIT = int(os.getenv('SEMAPHORE_LIMIT', 10))
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    stream=sys.stderr,
)

logging.getLogger('uvicorn').setLevel(logging.INFO)
logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
logging.getLogger('mcp.server.streamable_http_manager').setLevel(logging.WARNING)


def configure_uvicorn_logging() -> None:
    for logger_name in ['uvicorn', 'uvicorn.error', 'uvicorn.access']:
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        uvicorn_logger.addHandler(handler)
        uvicorn_logger.propagate = False


logger = logging.getLogger(__name__)


def _default_instruction_group() -> LucidInstructionGroupConfig:
    return LucidInstructionGroupConfig(
        high_level_policy="""
Graphiti is a memory service for AI agents built on a knowledge graph. Graphiti performs well
with dynamic data such as user interactions, changing enterprise data, and external information.

Graphiti transforms information into a richly connected knowledge network, allowing you to
capture relationships between concepts, entities, and information. The system organizes data as episodes
(content snippets), nodes (entities), and facts (relationships between entities), creating a dynamic,
queryable memory store that evolves with new information. Graphiti supports multiple data formats, including
structured JSON data, enabling seamless integration with existing data pipelines and systems.

Facts contain temporal metadata, allowing you to track the time of creation and whether a fact is invalid
(superseded by new information).
""".strip(),
        direct_policy="""
Key capabilities:
1. Add episodes (text, messages, or JSON) to the knowledge graph with the add_memory tool
2. Search for nodes (entities) in the graph using natural language queries with search_nodes
3. Find relevant facts (relationships between entities) with search_memory_facts
4. Retrieve specific entity edges or episodes by UUID
5. Manage the knowledge graph with tools like delete_episode, delete_entity_edge, and clear_graph

The server connects to a database for persistent storage and uses language models for certain operations.
Each piece of information is organized by group_id, allowing you to maintain separate knowledge domains.

When adding information, provide descriptive names and detailed content to improve search quality.
When searching, use specific queries and consider filtering by group_id for more relevant results.

For optimal performance, ensure the database is properly configured and accessible, and valid
API keys are provided for any language model operations.
""".strip(),
        routed_policy="""
Key capabilities:
1. Add episodes (text, messages, or JSON) to the knowledge graph with the add_memory tool
2. Search for nodes (entities) in the graph using natural language queries with search_nodes
3. Find relevant facts (relationships between entities) with search_memory_facts
4. Retrieve specific entity edges or episodes by UUID
5. Manage the knowledge graph with tools like delete_episode, delete_entity_edge, and clear_graph

The server connects to a database for persistent storage and uses language models for certain operations.
This endpoint already applies the route's write and read policy.

When adding information, provide descriptive names and detailed content to improve search quality.
When searching, use specific queries for more relevant results.

For optimal performance, ensure the database is properly configured and accessible, and valid
API keys are provided for any language model operations.
""".strip(),
        tool_descriptions=LucidInstructionGroupConfig().tool_descriptions.model_copy(
            update={
                'add_memory': """
Add an episode to memory. This is the primary way to add information to the graph.

This function returns immediately and processes the episode addition in the background.
Episodes for the same group are processed sequentially to avoid race conditions.

Arguments:
- name: descriptive episode name
- episode_body: full episode content; when source='json', provide a properly escaped JSON string
- group_id: optional write group override; omit it for normal shared-agent usage unless you intentionally need a separate hard partition
- source: one of text, json, or message
- source_description: optional provenance description
- uuid: optional episode UUID
""".strip(),
                'search_nodes': """
Search for nodes in the graph memory.

Arguments:
- query: natural-language search query
- group_ids: optional list of groups to search
- max_nodes: maximum number of nodes to return
- entity_types: optional entity labels to filter by
""".strip(),
                'search_memory_facts': """
Search the graph memory for relevant facts.

Arguments:
- query: natural-language search query
- group_ids: optional list of groups to search
- max_facts: maximum number of facts to return
- center_node_uuid: optional node UUID to center the search around
""".strip(),
                'delete_entity_edge': 'Delete an entity edge from the graph memory by UUID.',
                'delete_episode': 'Delete an episode from the graph memory by UUID.',
                'get_entity_edge': 'Get an entity edge from the graph memory by UUID.',
                'get_episodes': """
Get episodes from the graph memory.

Arguments:
- group_ids: optional list of groups to filter by
- max_episodes: maximum number of episodes to return
""".strip(),
                'clear_graph': """
Clear graph data for the specified groups.

Arguments:
- group_ids: optional list of groups to clear; if omitted in direct mode, the default group is used
""".strip(),
                'get_status': 'Get the status of the Lucid MCP server and database connection.',
            }
        ),
    )


def resolve_instruction_group(config: LucidConfig, instruction_group_name: str | None) -> LucidInstructionGroupConfig:
    resolved = _default_instruction_group()
    configured = config.resolve_instruction_group(instruction_group_name)
    return configured.merge(resolved)


def build_server_instructions(
    instruction_group: LucidInstructionGroupConfig,
    *,
    routed: bool,
) -> str:
    parts = [instruction_group.high_level_policy or '']
    mode_policy = instruction_group.routed_policy if routed else instruction_group.direct_policy
    if mode_policy:
        parts.append(mode_policy)
    return '\n\n'.join(part.strip() for part in parts if part and part.strip())


def patch_falkordb_fulltext_group_filter() -> None:
    """Avoid injecting group_id into Falkor fulltext query syntax."""

    def _build_fulltext_query_without_group_filter(
        query: str,
        group_ids: list[str] | None = None,
        max_query_length: int = falkor_search_ops.MAX_QUERY_LENGTH,
    ) -> str:
        sanitized_query = falkor_search_ops._sanitize(query)
        query_words = sanitized_query.split()
        filtered_words = [
            word for word in query_words if word and word.lower() not in FALKOR_STOPWORDS
        ]
        sanitized_query = ' | '.join(filtered_words)

        if len(sanitized_query.split(' ')) + len(group_ids or '') >= max_query_length:
            return ''

        return '(' + sanitized_query + ')'

    def _patched_build_falkor_fulltext_query(
        query: str,
        group_ids: list[str] | None = None,
        max_query_length: int = falkor_search_ops.MAX_QUERY_LENGTH,
    ) -> str:
        return _build_fulltext_query_without_group_filter(query, group_ids, max_query_length)

    def _patched_driver_build_fulltext_query(
        self,
        query: str,
        group_ids: list[str] | None = None,
        max_query_length: int = 128,
    ) -> str:
        return _build_fulltext_query_without_group_filter(query, group_ids, max_query_length)

    falkor_search_ops._build_falkor_fulltext_query = _patched_build_falkor_fulltext_query
    FalkorDriver.build_fulltext_query = _patched_driver_build_fulltext_query


patch_falkordb_fulltext_group_filter()


class LucidService:
    """Lucid service using graphiti-core and Lucid policy configuration."""

    def __init__(self, config: LucidConfig, semaphore_limit: int = 10):
        self.config = config
        self.semaphore_limit = semaphore_limit
        self.semaphore = asyncio.Semaphore(semaphore_limit)
        self.client: Graphiti | None = None
        self.entity_types = None

    async def initialize(self) -> None:
        try:
            llm_client = None
            embedder_client = None

            try:
                llm_client = LLMClientFactory.create(self.config.llm)
            except Exception as exc:
                logger.warning(f'Failed to create LLM client: {exc}')

            try:
                embedder_client = EmbedderFactory.create(self.config.embedder)
            except Exception as exc:
                logger.warning(f'Failed to create embedder client: {exc}')

            db_config = DatabaseDriverFactory.create_config(self.config.database)

            custom_types = None
            if self.config.graphiti.entity_types:
                custom_types = {}
                for entity_type in self.config.graphiti.entity_types:
                    entity_model = type(
                        entity_type.name,
                        (BaseModel,),
                        {
                            '__doc__': entity_type.description,
                        },
                    )
                    custom_types[entity_type.name] = entity_model

            self.entity_types = custom_types

            if self.config.database.provider.lower() == 'falkordb':
                falkor_driver = LucidFalkorDriver(
                    host=db_config['host'],
                    port=db_config['port'],
                    password=db_config['password'],
                    database=db_config['database'],
                )
                self.client = Graphiti(
                    graph_driver=falkor_driver,
                    llm_client=llm_client,
                    embedder=embedder_client,
                    max_coroutines=self.semaphore_limit,
                )
            else:
                self.client = Graphiti(
                    uri=db_config['uri'],
                    user=db_config['user'],
                    password=db_config['password'],
                    llm_client=llm_client,
                    embedder=embedder_client,
                    max_coroutines=self.semaphore_limit,
                )

            await self.client.build_indices_and_constraints()
            logger.info('Successfully initialized Lucid graphiti client')
            logger.info(
                f'Using Lucid profile: {self.config.lucid.profile_name} '
                f'(default_write={self.config.lucid.default_write_group}, '
                f'default_read={",".join(self.config.lucid.default_read_groups)})'
            )
        except Exception as exc:
            logger.error(f'Failed to initialize Lucid client: {exc}')
            raise

    async def get_client(self) -> Graphiti:
        if self.client is None:
            await self.initialize()
        if self.client is None:
            raise RuntimeError('Failed to initialize Lucid client')
        return self.client


class LucidRuntime:
    """One runtime instance with its own policy and queue service."""

    def __init__(self, config: LucidConfig, *, enforce_group_policy: bool):
        self.config = config
        self.enforce_group_policy = enforce_group_policy
        self.lucid_service: LucidService | None = None
        self.queue_service: QueueService | None = None
        self.graphiti_client: Graphiti | None = None

    async def initialize(self) -> None:
        self.config.graphiti.group_id = self.config.lucid.default_write_group
        self.lucid_service = LucidService(self.config, SEMAPHORE_LIMIT)
        self.queue_service = QueueService()
        await self.lucid_service.initialize()
        self.graphiti_client = await self.lucid_service.get_client()
        await self.queue_service.initialize(self.graphiti_client)

    def effective_read_groups(self, group_ids: list[str] | None) -> list[str]:
        return resolve_read_groups(
            group_ids,
            self.config.lucid,
            enforce_group_policy=self.enforce_group_policy,
        )

    def effective_write_group(self, group_id: str | None) -> str:
        return resolve_write_group(
            group_id,
            self.config.lucid,
            enforce_group_policy=self.enforce_group_policy,
        )

    def can_read_group(self, group_id: str) -> bool:
        return can_read_group(
            group_id,
            self.config.lucid,
            enforce_group_policy=self.enforce_group_policy,
        )

    def can_write_group(self, group_id: str) -> bool:
        return can_write_group(
            group_id,
            self.config.lucid,
            enforce_group_policy=self.enforce_group_policy,
        )


@dataclass
class MountedProfileApp:
    profile_name: str
    path_prefix: str
    runtime: LucidRuntime
    mcp: FastMCP
    app: Starlette


def _normalize_mount_path(path_prefix: str) -> str:
    if not path_prefix.startswith('/'):
        raise ValueError(f'Route prefix must start with "/": {path_prefix}')
    normalized = path_prefix.rstrip('/')
    return normalized or '/'


def _log_config(config: LucidConfig, *, routed: bool) -> None:
    logger.info('Using configuration:')
    logger.info(f'  - LLM: {config.llm.provider} / {config.llm.model}')
    logger.info(f'  - Embedder: {config.embedder.provider} / {config.embedder.model}')
    logger.info(f'  - Database: {config.database.provider}')
    logger.info(f'  - Lucid profile: {config.lucid.profile_name}')
    logger.info(f'  - Default write group: {config.lucid.default_write_group}')
    logger.info(f'  - Default read groups: {",".join(config.lucid.default_read_groups)}')
    logger.info(f'  - Allowed write groups: {",".join(config.lucid.allowed_write_groups)}')
    logger.info(f'  - Allowed read groups: {",".join(config.lucid.allowed_read_groups)}')
    logger.info(f'  - Transport: {config.server.transport}')
    logger.info(f'  - Group routing enabled: {routed}')

    try:
        import graphiti_core

        graphiti_version = getattr(graphiti_core, '__version__', 'unknown')
        logger.info(f'  - Graphiti Core: {graphiti_version}')
    except Exception:
        logger.info('  - Graphiti Core: version unavailable')


def build_mcp_server(
    runtime: LucidRuntime,
    *,
    routed: bool,
    streamable_http_path: str = '/mcp',
) -> FastMCP:
    instruction_group_name = runtime.config.lucid.instruction_group
    instruction_group = resolve_instruction_group(runtime.config, instruction_group_name)
    tool_descriptions = instruction_group.tool_descriptions.as_mapping()
    mcp = FastMCP(
        'Lucid Memory',
        instructions=build_server_instructions(instruction_group, routed=routed),
    )
    mcp.settings.streamable_http_path = streamable_http_path

    @mcp.tool(description=tool_descriptions['add_memory'])
    async def add_memory(
        name: str,
        episode_body: str,
        group_id: str | None = None,
        source: str = 'text',
        source_description: str = '',
        uuid: str | None = None,
    ) -> SuccessResponse | ErrorResponse:
        if runtime.lucid_service is None or runtime.queue_service is None:
            return ErrorResponse(error='Services not initialized')

        try:
            effective_group_id = runtime.effective_write_group(group_id)
            if group_id and group_id != effective_group_id:
                logger.info(
                    'Rewriting disallowed write group %s to default group %s',
                    group_id,
                    effective_group_id,
                )

            episode_type = EpisodeType.text
            if source:
                try:
                    episode_type = EpisodeType[source.lower()]
                except (KeyError, AttributeError):
                    logger.warning(f"Unknown source type '{source}', using 'text' as default")
                    episode_type = EpisodeType.text

            await runtime.queue_service.add_episode(
                group_id=effective_group_id,
                name=name,
                content=episode_body,
                source_description=source_description,
                episode_type=episode_type,
                entity_types=runtime.lucid_service.entity_types,
                uuid=uuid or None,
            )
            return SuccessResponse(
                message=f"Episode '{name}' queued for processing in group '{effective_group_id}'"
            )
        except Exception as exc:
            error_msg = str(exc)
            logger.error(f'Error queuing episode: {error_msg}')
            return ErrorResponse(error=f'Error queuing episode: {error_msg}')

    @mcp.tool(description=tool_descriptions['search_nodes'])
    async def search_nodes(
        query: str,
        group_ids: list[str] | None = None,
        max_nodes: int = 10,
        entity_types: list[str] | None = None,
    ) -> NodeSearchResponse | ErrorResponse:
        if runtime.lucid_service is None:
            return ErrorResponse(error='Lucid service not initialized')

        try:
            client = await runtime.lucid_service.get_client()
            effective_group_ids = runtime.effective_read_groups(group_ids)
            search_filters = SearchFilters(node_labels=entity_types)

            from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF

            results = await client.search_(
                query=query,
                config=NODE_HYBRID_SEARCH_RRF,
                group_ids=effective_group_ids,
                search_filter=search_filters,
            )

            nodes = results.nodes[:max_nodes] if results.nodes else []
            if not nodes:
                return NodeSearchResponse(message='No relevant nodes found', nodes=[])

            node_results = []
            for node in nodes:
                attrs = node.attributes if hasattr(node, 'attributes') else {}
                attrs = {k: v for k, v in attrs.items() if 'embedding' not in k.lower()}
                node_results.append(
                    NodeResult(
                        uuid=node.uuid,
                        name=node.name,
                        labels=node.labels if node.labels else [],
                        created_at=node.created_at.isoformat() if node.created_at else None,
                        summary=node.summary,
                        group_id=node.group_id,
                        attributes=attrs,
                    )
                )
            return NodeSearchResponse(message='Nodes retrieved successfully', nodes=node_results)
        except Exception as exc:
            error_msg = str(exc)
            logger.error(f'Error searching nodes: {error_msg}')
            return ErrorResponse(error=f'Error searching nodes: {error_msg}')

    @mcp.tool(description=tool_descriptions['search_memory_facts'])
    async def search_memory_facts(
        query: str,
        group_ids: list[str] | None = None,
        max_facts: int = 10,
        center_node_uuid: str | None = None,
    ) -> FactSearchResponse | ErrorResponse:
        if runtime.lucid_service is None:
            return ErrorResponse(error='Lucid service not initialized')

        try:
            if max_facts <= 0:
                return ErrorResponse(error='max_facts must be a positive integer')

            client = await runtime.lucid_service.get_client()
            effective_group_ids = runtime.effective_read_groups(group_ids)
            relevant_edges = await client.search(
                group_ids=effective_group_ids,
                query=query,
                num_results=max_facts,
                center_node_uuid=center_node_uuid,
            )

            if not relevant_edges:
                return FactSearchResponse(message='No relevant facts found', facts=[])

            facts = [format_fact_result(edge) for edge in relevant_edges]
            return FactSearchResponse(message='Facts retrieved successfully', facts=facts)
        except Exception as exc:
            error_msg = str(exc)
            logger.error(f'Error searching facts: {error_msg}')
            return ErrorResponse(error=f'Error searching facts: {error_msg}')

    @mcp.tool(description=tool_descriptions['delete_entity_edge'])
    async def delete_entity_edge(uuid: str) -> SuccessResponse | ErrorResponse:
        if runtime.lucid_service is None:
            return ErrorResponse(error='Lucid service not initialized')

        try:
            client = await runtime.lucid_service.get_client()
            entity_edge = await EntityEdge.get_by_uuid(client.driver, uuid)
            if not runtime.can_write_group(entity_edge.group_id):
                return ErrorResponse(
                    error=f'Group {entity_edge.group_id} is not writable for this endpoint'
                )
            await entity_edge.delete(client.driver)
            return SuccessResponse(message=f'Entity edge with UUID {uuid} deleted successfully')
        except Exception as exc:
            error_msg = str(exc)
            logger.error(f'Error deleting entity edge: {error_msg}')
            return ErrorResponse(error=f'Error deleting entity edge: {error_msg}')

    @mcp.tool(description=tool_descriptions['delete_episode'])
    async def delete_episode(uuid: str) -> SuccessResponse | ErrorResponse:
        if runtime.lucid_service is None:
            return ErrorResponse(error='Lucid service not initialized')

        try:
            client = await runtime.lucid_service.get_client()
            episodic_node = await EpisodicNode.get_by_uuid(client.driver, uuid)
            if not runtime.can_write_group(episodic_node.group_id):
                return ErrorResponse(
                    error=f'Group {episodic_node.group_id} is not writable for this endpoint'
                )
            await episodic_node.delete(client.driver)
            return SuccessResponse(message=f'Episode with UUID {uuid} deleted successfully')
        except Exception as exc:
            error_msg = str(exc)
            logger.error(f'Error deleting episode: {error_msg}')
            return ErrorResponse(error=f'Error deleting episode: {error_msg}')

    @mcp.tool(description=tool_descriptions['get_entity_edge'])
    async def get_entity_edge(uuid: str) -> dict[str, Any] | ErrorResponse:
        if runtime.lucid_service is None:
            return ErrorResponse(error='Lucid service not initialized')

        try:
            client = await runtime.lucid_service.get_client()
            entity_edge = await EntityEdge.get_by_uuid(client.driver, uuid)
            if not runtime.can_read_group(entity_edge.group_id):
                return ErrorResponse(
                    error=f'Group {entity_edge.group_id} is not readable for this endpoint'
                )
            return format_fact_result(entity_edge)
        except Exception as exc:
            error_msg = str(exc)
            logger.error(f'Error getting entity edge: {error_msg}')
            return ErrorResponse(error=f'Error getting entity edge: {error_msg}')

    @mcp.tool(description=tool_descriptions['get_episodes'])
    async def get_episodes(
        group_ids: list[str] | None = None,
        max_episodes: int = 10,
    ) -> EpisodeSearchResponse | ErrorResponse:
        if runtime.lucid_service is None:
            return ErrorResponse(error='Lucid service not initialized')

        try:
            client = await runtime.lucid_service.get_client()
            effective_group_ids = runtime.effective_read_groups(group_ids)

            if effective_group_ids:
                episodes = await EpisodicNode.get_by_group_ids(
                    client.driver, effective_group_ids, limit=max_episodes
                )
            else:
                episodes = []

            if not episodes:
                return EpisodeSearchResponse(message='No episodes found', episodes=[])

            episode_results = []
            for episode in episodes:
                episode_results.append(
                    {
                        'uuid': episode.uuid,
                        'name': episode.name,
                        'content': episode.content,
                        'created_at': episode.created_at.isoformat()
                        if episode.created_at
                        else None,
                        'source': episode.source.value
                        if hasattr(episode.source, 'value')
                        else str(episode.source),
                        'source_description': episode.source_description,
                        'group_id': episode.group_id,
                    }
                )

            return EpisodeSearchResponse(
                message='Episodes retrieved successfully',
                episodes=episode_results,
            )
        except Exception as exc:
            error_msg = str(exc)
            logger.error(f'Error getting episodes: {error_msg}')
            return ErrorResponse(error=f'Error getting episodes: {error_msg}')

    @mcp.tool(description=tool_descriptions['clear_graph'])
    async def clear_graph(group_ids: list[str] | None = None) -> SuccessResponse | ErrorResponse:
        if runtime.lucid_service is None:
            return ErrorResponse(error='Lucid service not initialized')

        try:
            client = await runtime.lucid_service.get_client()
            effective_group_ids = runtime.effective_read_groups(group_ids)
            writable_groups = [
                group_id for group_id in effective_group_ids if runtime.can_write_group(group_id)
            ]
            if not writable_groups:
                return ErrorResponse(error='No writable group IDs specified for clearing')

            await clear_data(client.driver, group_ids=writable_groups)
            return SuccessResponse(
                message=f'Graph data cleared successfully for group IDs: {", ".join(writable_groups)}'
            )
        except Exception as exc:
            error_msg = str(exc)
            logger.error(f'Error clearing graph: {error_msg}')
            return ErrorResponse(error=f'Error clearing graph: {error_msg}')

    @mcp.tool(description=tool_descriptions['get_status'])
    async def get_status() -> StatusResponse:
        if runtime.lucid_service is None:
            return StatusResponse(status='error', message='Lucid service not initialized')

        try:
            client = await runtime.lucid_service.get_client()
            async with client.driver.session() as session:
                result = await session.run('MATCH (n) RETURN count(n) as count')
                if result:
                    _ = [record async for record in result]

            return StatusResponse(
                status='ok',
                message=(
                    'Lucid MCP server is running '
                    f'({runtime.config.lucid.profile_name}, '
                    f'write={runtime.config.lucid.default_write_group}, '
                    f'read={",".join(runtime.config.lucid.default_read_groups)})'
                ),
            )
        except Exception as exc:
            error_msg = str(exc)
            logger.error(f'Error checking database connection: {error_msg}')
            return StatusResponse(
                status='error',
                message=f'Lucid MCP server is running but database connection failed: {error_msg}',
            )

    return mcp


def _validate_route_config(route: LucidRouteConfig, root_config: LucidConfig) -> None:
    if route.profile not in root_config.profiles:
        raise ValueError(f'Route {route.path_prefix} references unknown profile: {route.profile}')


def _build_profile_mounts(
    root_config: LucidConfig,
) -> tuple[list[MountedProfileApp], MountedProfileApp | None]:
    mounted_apps: list[MountedProfileApp] = []
    alias_app: MountedProfileApp | None = None
    seen_paths: set[str] = set()

    for route in root_config.routing.routes:
        path_prefix = _normalize_mount_path(route.path_prefix)
        if path_prefix in seen_paths:
            raise ValueError(f'Duplicate Lucid route prefix: {path_prefix}')
        seen_paths.add(path_prefix)

        _validate_route_config(route, root_config)
        profile_config = root_config.resolve_profile(route.profile)
        _log_config(profile_config, routed=True)

        runtime = LucidRuntime(profile_config, enforce_group_policy=True)
        mounted_apps.append(
            MountedProfileApp(
                profile_name=profile_config.lucid.profile_name,
                path_prefix=path_prefix,
                runtime=runtime,
                mcp=build_mcp_server(runtime, routed=True),
                app=Starlette(),
            )
        )

    for mounted in mounted_apps:
        mounted.app = mounted.mcp.streamable_http_app()

    if root_config.routing.compatibility_profile:
        match = next(
            (
                mounted
                for mounted in mounted_apps
                if mounted.profile_name == root_config.routing.compatibility_profile
            ),
            None,
        )
        if match is None:
            raise ValueError(
                'compatibility_profile does not match any configured routed profile: '
                f'{root_config.routing.compatibility_profile}'
            )

        compatibility_mcp = build_mcp_server(
            match.runtime,
            routed=True,
            streamable_http_path=root_config.routing.compatibility_path,
        )
        alias_app = MountedProfileApp(
            profile_name=match.profile_name,
            path_prefix='/',
            runtime=match.runtime,
            mcp=compatibility_mcp,
            app=compatibility_mcp.streamable_http_app(),
        )

    return mounted_apps, alias_app


async def _maybe_destroy_graph(config: LucidConfig) -> None:
    if not getattr(config, 'destroy_graph', False):
        return

    logger.warning('Destroying all graph data as requested...')
    destroy_config = config.resolve_profile(config.routing.default_profile)
    temp_runtime = LucidRuntime(destroy_config, enforce_group_policy=config.routing.enabled)
    await temp_runtime.initialize()
    if temp_runtime.graphiti_client is None:
        raise RuntimeError('Failed to initialize Lucid runtime for destroy_graph')
    await clear_data(temp_runtime.graphiti_client.driver)
    logger.info('All graph data destroyed')


async def initialize_server() -> tuple[ServerConfig, LucidConfig, Path]:
    """Parse CLI arguments and initialize the Lucid server configuration."""
    parser = argparse.ArgumentParser(
        description='Run the Lucid MCP server with graphiti-core and Lucid policy support'
    )
    default_config = Path(__file__).parent.parent.parent / 'config' / 'config.yaml'
    parser.add_argument(
        '--config',
        type=Path,
        default=default_config,
        help='Path to YAML configuration file (default: config/config.yaml)',
    )
    parser.add_argument('--transport', choices=['sse', 'stdio', 'http'])
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    parser.add_argument(
        '--llm-provider',
        choices=['openai', 'azure_openai', 'anthropic', 'gemini', 'groq'],
    )
    parser.add_argument(
        '--embedder-provider',
        choices=['openai', 'azure_openai', 'gemini', 'voyage'],
    )
    parser.add_argument('--database-provider', choices=['neo4j', 'falkordb'])
    parser.add_argument('--model')
    parser.add_argument('--temperature', type=float)
    parser.add_argument('--embedder-model')
    parser.add_argument('--group-id')
    parser.add_argument('--user-id')
    parser.add_argument('--destroy-graph', action='store_true')

    args = parser.parse_args()
    config_path = args.config.resolve()

    if args.config:
        os.environ['CONFIG_PATH'] = str(config_path)

    config = LucidConfig.load_from_path(config_path)
    config.apply_cli_overrides(args)
    if hasattr(args, 'destroy_graph'):
        config.destroy_graph = args.destroy_graph

    return config.server, config, config_path


def build_http_app(
    root_config: LucidConfig,
) -> tuple[Starlette, list[FastMCP]]:
    routed = root_config.routing.enabled

    async def health_check(request) -> JSONResponse:
        return JSONResponse({'status': 'healthy', 'service': 'lucid-mcp'})

    if routed:
        mounted_apps, alias_app = _build_profile_mounts(root_config)
        if not mounted_apps:
            raise ValueError('Group routing is enabled but no routes are configured')

        routes = [Route('/health', endpoint=health_check, methods=['GET'])]
        session_servers: list[FastMCP] = []

        for mounted in mounted_apps:
            routes.append(Mount(mounted.path_prefix, app=mounted.app))
            session_servers.append(mounted.mcp)

        if alias_app is not None:
            routes.append(Mount('', app=alias_app.app))
            session_servers.append(alias_app.mcp)

        runtimes_by_id: dict[int, LucidRuntime] = {}
        for mounted in mounted_apps:
            runtimes_by_id[id(mounted.runtime)] = mounted.runtime
        if alias_app is not None:
            runtimes_by_id[id(alias_app.runtime)] = alias_app.runtime
        unique_runtimes = list(runtimes_by_id.values())

        @asynccontextmanager
        async def lifespan(app: Starlette):
            async with AsyncExitStack() as stack:
                for runtime in unique_runtimes:
                    await runtime.initialize()
                for server in session_servers:
                    await stack.enter_async_context(server.session_manager.run())
                yield

        return Starlette(routes=routes, lifespan=lifespan), session_servers

    direct_config = root_config.resolve_profile(root_config.routing.default_profile)
    _log_config(direct_config, routed=False)
    runtime = LucidRuntime(direct_config, enforce_group_policy=False)
    mcp = build_mcp_server(runtime, routed=False)
    direct_app = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(app: Starlette):
        async with AsyncExitStack() as stack:
            await runtime.initialize()
            await stack.enter_async_context(mcp.session_manager.run())
            yield

    app = Starlette(
        routes=[
            Route('/health', endpoint=health_check, methods=['GET']),
            Mount('', app=direct_app),
        ],
        lifespan=lifespan,
    )
    return app, [mcp]


async def run_http_server(app: Starlette, server_config: ServerConfig) -> None:
    import uvicorn

    host = server_config.host
    port = server_config.port
    display_host = 'localhost' if host == '0.0.0.0' else host

    logger.info(f'Running MCP server with streamable HTTP transport on {host}:{port}')
    logger.info('=' * 60)
    logger.info('Lucid MCP Access Information:')
    logger.info(f'  Base URL: http://{display_host}:{port}/')
    logger.info(f'  MCP Endpoint: http://{display_host}:{port}/mcp')
    logger.info('  Transport: HTTP (streamable)')
    logger.info('=' * 60)
    configure_uvicorn_logging()

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level='info',
        )
    )
    await server.serve()


async def run_mcp_server() -> None:
    server_config, root_config, _root_config_path = await initialize_server()
    routed = root_config.routing.enabled

    if routed and server_config.transport != 'http':
        raise ValueError('Lucid route-based group routing is only supported for HTTP transport')

    if routed:
        logger.info('Lucid group routing is enabled')
        logger.info(
            '  - Compatibility path: %s -> %s',
            root_config.routing.compatibility_path,
            root_config.routing.compatibility_profile,
        )
        for route in root_config.routing.routes:
            logger.info(
                '  - Route %s -> profile %s',
                route.path_prefix,
                route.profile,
            )
    else:
        _log_config(root_config.resolve_profile(root_config.routing.default_profile), routed=False)

    await _maybe_destroy_graph(root_config)

    if server_config.transport == 'http':
        app, _ = build_http_app(root_config)
        await run_http_server(app, server_config)
        return

    direct_config = root_config.resolve_profile(root_config.routing.default_profile)
    runtime = LucidRuntime(direct_config, enforce_group_policy=False)
    await runtime.initialize()
    mcp = build_mcp_server(runtime, routed=False)
    mcp.settings.host = server_config.host
    mcp.settings.port = server_config.port

    logger.info(f'Starting MCP server with transport: {server_config.transport}')
    if server_config.transport == 'stdio':
        await mcp.run_stdio_async()
    elif server_config.transport == 'sse':
        logger.info(
            f'Running MCP server with SSE transport on {mcp.settings.host}:{mcp.settings.port}'
        )
        await mcp.run_sse_async()
    else:
        raise ValueError(f'Unsupported transport: {server_config.transport}')


def main() -> None:
    try:
        asyncio.run(run_mcp_server())
    except KeyboardInterrupt:
        logger.info('Server shutting down...')
    except Exception as exc:
        logger.error(f'Error initializing Lucid MCP server: {exc}')
        raise


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Lucid MCP server built on graphiti-core."""

import argparse
import asyncio
import logging
import os
import sys
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
from starlette.responses import JSONResponse

from lucid_mcp.config import LucidConfig, ServerConfig
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


def configure_uvicorn_logging():
    for logger_name in ['uvicorn', 'uvicorn.error', 'uvicorn.access']:
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        uvicorn_logger.addHandler(handler)
        uvicorn_logger.propagate = False


logger = logging.getLogger(__name__)


def load_mcp_instructions() -> str:
    """Load server-level MCP instructions from Markdown when available."""
    configured_path = os.getenv('LUCID_MCP_INSTRUCTIONS_PATH')
    instruction_path = Path(configured_path) if configured_path else mcp_server_dir / 'config' / 'instructions.md'
    if instruction_path.exists():
        return instruction_path.read_text(encoding='utf-8').strip()

    return """
Lucid is a shared memory service for AI agents built on graphiti-core.

Use Lucid when prior project or user context may matter, or when you learn something durable
that another future session would need. Prefer narrow retrieval over broad exploratory search.

For normal usage, do not invent repo-specific, session-specific, or task-specific group ids.
Lucid applies policy at the server boundary: if a write group is omitted, the server default
is used; if a disallowed write group is requested, the write is routed to the endpoint default.

Good writes are durable, specific, self-contained, and provenance-rich. Skip transient logs,
generic success output, repetitive status, and low-value noise.
""".strip()


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

config: LucidConfig
LUCID_MCP_INSTRUCTIONS = load_mcp_instructions()

mcp = FastMCP(
    'Lucid Memory',
    instructions=LUCID_MCP_INSTRUCTIONS,
)

lucid_service: 'LucidService | None' = None
queue_service: QueueService | None = None
graphiti_client: Graphiti | None = None
semaphore: asyncio.Semaphore


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


def _effective_read_groups(group_ids: list[str] | None) -> list[str]:
    return resolve_read_groups(group_ids, config.lucid)


def _effective_write_group(group_id: str | None) -> str:
    return resolve_write_group(group_id, config.lucid)


@mcp.tool()
async def add_memory(
    name: str,
    episode_body: str,
    group_id: str | None = None,
    source: str = 'text',
    source_description: str = '',
    uuid: str | None = None,
) -> SuccessResponse | ErrorResponse:
    """Add an episode to Lucid memory."""
    global lucid_service, queue_service

    if lucid_service is None or queue_service is None:
        return ErrorResponse(error='Services not initialized')

    try:
        effective_group_id = _effective_write_group(group_id)
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

        await queue_service.add_episode(
            group_id=effective_group_id,
            name=name,
            content=episode_body,
            source_description=source_description,
            episode_type=episode_type,
            entity_types=lucid_service.entity_types,
            uuid=uuid or None,
        )
        return SuccessResponse(
            message=f"Episode '{name}' queued for processing in group '{effective_group_id}'"
        )
    except Exception as exc:
        error_msg = str(exc)
        logger.error(f'Error queuing episode: {error_msg}')
        return ErrorResponse(error=f'Error queuing episode: {error_msg}')


@mcp.tool()
async def search_nodes(
    query: str,
    group_ids: list[str] | None = None,
    max_nodes: int = 10,
    entity_types: list[str] | None = None,
) -> NodeSearchResponse | ErrorResponse:
    """Search for nodes in Lucid memory."""
    global lucid_service

    if lucid_service is None:
        return ErrorResponse(error='Lucid service not initialized')

    try:
        client = await lucid_service.get_client()
        effective_group_ids = _effective_read_groups(group_ids)
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


@mcp.tool()
async def search_memory_facts(
    query: str,
    group_ids: list[str] | None = None,
    max_facts: int = 10,
    center_node_uuid: str | None = None,
) -> FactSearchResponse | ErrorResponse:
    """Search Lucid memory for relevant facts."""
    global lucid_service

    if lucid_service is None:
        return ErrorResponse(error='Lucid service not initialized')

    try:
        if max_facts <= 0:
            return ErrorResponse(error='max_facts must be a positive integer')

        client = await lucid_service.get_client()
        effective_group_ids = _effective_read_groups(group_ids)
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


@mcp.tool()
async def delete_entity_edge(uuid: str) -> SuccessResponse | ErrorResponse:
    """Delete an entity edge from Lucid memory."""
    global lucid_service

    if lucid_service is None:
        return ErrorResponse(error='Lucid service not initialized')

    try:
        client = await lucid_service.get_client()
        entity_edge = await EntityEdge.get_by_uuid(client.driver, uuid)
        if not can_write_group(entity_edge.group_id, config.lucid):
            return ErrorResponse(error=f'Group {entity_edge.group_id} is not writable for this endpoint')
        await entity_edge.delete(client.driver)
        return SuccessResponse(message=f'Entity edge with UUID {uuid} deleted successfully')
    except Exception as exc:
        error_msg = str(exc)
        logger.error(f'Error deleting entity edge: {error_msg}')
        return ErrorResponse(error=f'Error deleting entity edge: {error_msg}')


@mcp.tool()
async def delete_episode(uuid: str) -> SuccessResponse | ErrorResponse:
    """Delete an episode from Lucid memory."""
    global lucid_service

    if lucid_service is None:
        return ErrorResponse(error='Lucid service not initialized')

    try:
        client = await lucid_service.get_client()
        episodic_node = await EpisodicNode.get_by_uuid(client.driver, uuid)
        if not can_write_group(episodic_node.group_id, config.lucid):
            return ErrorResponse(
                error=f'Group {episodic_node.group_id} is not writable for this endpoint'
            )
        await episodic_node.delete(client.driver)
        return SuccessResponse(message=f'Episode with UUID {uuid} deleted successfully')
    except Exception as exc:
        error_msg = str(exc)
        logger.error(f'Error deleting episode: {error_msg}')
        return ErrorResponse(error=f'Error deleting episode: {error_msg}')


@mcp.tool()
async def get_entity_edge(uuid: str) -> dict[str, Any] | ErrorResponse:
    """Get an entity edge from Lucid memory by its UUID."""
    global lucid_service

    if lucid_service is None:
        return ErrorResponse(error='Lucid service not initialized')

    try:
        client = await lucid_service.get_client()
        entity_edge = await EntityEdge.get_by_uuid(client.driver, uuid)
        if not can_read_group(entity_edge.group_id, config.lucid):
            return ErrorResponse(error=f'Group {entity_edge.group_id} is not readable for this endpoint')
        return format_fact_result(entity_edge)
    except Exception as exc:
        error_msg = str(exc)
        logger.error(f'Error getting entity edge: {error_msg}')
        return ErrorResponse(error=f'Error getting entity edge: {error_msg}')


@mcp.tool()
async def get_episodes(
    group_ids: list[str] | None = None,
    max_episodes: int = 10,
) -> EpisodeSearchResponse | ErrorResponse:
    """Get episodes from Lucid memory."""
    global lucid_service

    if lucid_service is None:
        return ErrorResponse(error='Lucid service not initialized')

    try:
        client = await lucid_service.get_client()
        effective_group_ids = _effective_read_groups(group_ids)

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
                    'created_at': episode.created_at.isoformat() if episode.created_at else None,
                    'source': episode.source.value
                    if hasattr(episode.source, 'value')
                    else str(episode.source),
                    'source_description': episode.source_description,
                    'group_id': episode.group_id,
                }
            )

        return EpisodeSearchResponse(
            message='Episodes retrieved successfully', episodes=episode_results
        )
    except Exception as exc:
        error_msg = str(exc)
        logger.error(f'Error getting episodes: {error_msg}')
        return ErrorResponse(error=f'Error getting episodes: {error_msg}')


@mcp.tool()
async def clear_graph(group_ids: list[str] | None = None) -> SuccessResponse | ErrorResponse:
    """Clear graph data for allowed group IDs."""
    global lucid_service

    if lucid_service is None:
        return ErrorResponse(error='Lucid service not initialized')

    try:
        client = await lucid_service.get_client()
        effective_group_ids = _effective_read_groups(group_ids)
        writable_groups = [
            group_id for group_id in effective_group_ids if can_write_group(group_id, config.lucid)
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


@mcp.tool()
async def get_status() -> StatusResponse:
    """Get status of the Lucid MCP server and database connection."""
    global lucid_service

    if lucid_service is None:
        return StatusResponse(status='error', message='Lucid service not initialized')

    try:
        client = await lucid_service.get_client()
        async with client.driver.session() as session:
            result = await session.run('MATCH (n) RETURN count(n) as count')
            if result:
                _ = [record async for record in result]

        return StatusResponse(
            status='ok',
            message=(
                'Lucid MCP server is running '
                f'({config.lucid.profile_name}, write={config.lucid.default_write_group}, '
                f'read={",".join(config.lucid.default_read_groups)})'
            ),
        )
    except Exception as exc:
        error_msg = str(exc)
        logger.error(f'Error checking database connection: {error_msg}')
        return StatusResponse(
            status='error',
            message=f'Lucid MCP server is running but database connection failed: {error_msg}',
        )


@mcp.custom_route('/health', methods=['GET'])
async def health_check(request) -> JSONResponse:
    return JSONResponse({'status': 'healthy', 'service': 'lucid-mcp'})


async def initialize_server() -> ServerConfig:
    """Parse CLI arguments and initialize the Lucid server configuration."""
    global config, lucid_service, queue_service, graphiti_client, semaphore

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

    if args.config:
        os.environ['CONFIG_PATH'] = str(args.config)

    config = LucidConfig()
    config.apply_cli_overrides(args)
    if hasattr(args, 'destroy_graph'):
        config.destroy_graph = args.destroy_graph

    config.graphiti.group_id = config.lucid.default_write_group

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

    try:
        import graphiti_core

        graphiti_version = getattr(graphiti_core, '__version__', 'unknown')
        logger.info(f'  - Graphiti Core: {graphiti_version}')
    except Exception:
        logger.info('  - Graphiti Core: version unavailable')

    if hasattr(config, 'destroy_graph') and config.destroy_graph:
        logger.warning('Destroying all graph data as requested...')
        temp_service = LucidService(config, SEMAPHORE_LIMIT)
        await temp_service.initialize()
        client = await temp_service.get_client()
        await clear_data(client.driver)
        logger.info('All graph data destroyed')

    lucid_service = LucidService(config, SEMAPHORE_LIMIT)
    queue_service = QueueService()
    await lucid_service.initialize()
    graphiti_client = await lucid_service.get_client()
    semaphore = lucid_service.semaphore
    await queue_service.initialize(graphiti_client)

    if config.server.host:
        mcp.settings.host = config.server.host
    if config.server.port:
        mcp.settings.port = config.server.port

    return config.server


async def run_mcp_server():
    mcp_config = await initialize_server()
    logger.info(f'Starting MCP server with transport: {mcp_config.transport}')
    if mcp_config.transport == 'stdio':
        await mcp.run_stdio_async()
    elif mcp_config.transport == 'sse':
        logger.info(
            f'Running MCP server with SSE transport on {mcp.settings.host}:{mcp.settings.port}'
        )
        await mcp.run_sse_async()
    elif mcp_config.transport == 'http':
        display_host = 'localhost' if mcp.settings.host == '0.0.0.0' else mcp.settings.host
        logger.info(
            f'Running MCP server with streamable HTTP transport on {mcp.settings.host}:{mcp.settings.port}'
        )
        logger.info('=' * 60)
        logger.info('Lucid MCP Access Information:')
        logger.info(f'  Base URL: http://{display_host}:{mcp.settings.port}/')
        logger.info(f'  MCP Endpoint: http://{display_host}:{mcp.settings.port}/mcp/')
        logger.info('  Transport: HTTP (streamable)')
        logger.info('=' * 60)
        configure_uvicorn_logging()
        await mcp.run_streamable_http_async()
    else:
        raise ValueError(f'Unsupported transport: {mcp_config.transport}')


def main():
    try:
        asyncio.run(run_mcp_server())
    except KeyboardInterrupt:
        logger.info('Server shutting down...')
    except Exception as exc:
        logger.error(f'Error initializing Lucid MCP server: {exc}')
        raise


if __name__ == '__main__':
    main()

from __future__ import annotations

import asyncio
import copy
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

LOGGER = logging.getLogger(__name__)
SCRIPT_DIR = Path(__file__).resolve().parent
DEPLOY_DIR = SCRIPT_DIR.parent
LUCID_REPO_ROOT = DEPLOY_DIR.parent


@dataclass
class MaintenanceRuntime:
    config: Any
    client: Any
    graphiti_mcp_server_path: Path

    async def close(self) -> None:
        await self.client.close()


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )


def default_config_path() -> Path:
    return DEPLOY_DIR / 'graphiti' / 'config-docker-falkordb.yaml'


def resolve_graphiti_mcp_server_path(explicit_path: str | None = None) -> Path:
    candidates: list[Path] = []

    if explicit_path:
        candidates.append(Path(explicit_path).expanduser())

    env_path = os.environ.get('GRAPHITI_MCP_SERVER_PATH')
    if env_path:
        candidates.append(Path(env_path).expanduser())

    # Convenience fallback when lucid and graphiti are sibling repos.
    candidates.append(LUCID_REPO_ROOT.parent / 'graphiti' / 'mcp_server')

    for candidate in candidates:
        if (
            candidate.is_dir()
            and (candidate / 'pyproject.toml').exists()
            and (candidate / 'src' / 'config' / 'schema.py').exists()
        ):
            return candidate.resolve()

    searched = ', '.join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(
        'Unable to locate graphiti/mcp_server. Pass --graphiti-mcp-server-path or set '
        f'GRAPHITI_MCP_SERVER_PATH. Searched: {searched}'
    )


def _load_env_files(env_files: list[Path]) -> None:
    for env_file in env_files:
        resolved = env_file.expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f'Env file not found: {resolved}')
        load_dotenv(resolved, override=False)


def _ensure_import_path(graphiti_mcp_server_path: Path) -> None:
    mcp_src = graphiti_mcp_server_path / 'src'
    mcp_root = graphiti_mcp_server_path

    for path in (mcp_src, mcp_root):
        rendered = str(path)
        if rendered not in sys.path:
            sys.path.insert(0, rendered)


def _import_graphiti_modules() -> dict[str, Any]:
    from config.schema import GraphitiConfig
    from graphiti_core import Graphiti
    from graphiti_core.driver.falkordb_driver import FalkorDriver
    from services.factories import DatabaseDriverFactory, EmbedderFactory, LLMClientFactory

    return {
        'DatabaseDriverFactory': DatabaseDriverFactory,
        'EmbedderFactory': EmbedderFactory,
        'FalkorDriver': FalkorDriver,
        'Graphiti': Graphiti,
        'GraphitiConfig': GraphitiConfig,
        'LLMClientFactory': LLMClientFactory,
    }


async def build_runtime(
    *,
    config_path: Path | None = None,
    env_files: list[Path] | None = None,
    graphiti_mcp_server_path: str | None = None,
    semaphore_limit: int | None = None,
    require_llm: bool = False,
    require_embedder: bool = False,
) -> MaintenanceRuntime:
    resolved_config = (config_path or default_config_path()).expanduser().resolve()
    if not resolved_config.exists():
        raise FileNotFoundError(f'Config file not found: {resolved_config}')

    _load_env_files(env_files or [])

    resolved_graphiti_path = resolve_graphiti_mcp_server_path(graphiti_mcp_server_path)
    _ensure_import_path(resolved_graphiti_path)
    modules = _import_graphiti_modules()

    os.environ['CONFIG_PATH'] = str(resolved_config)

    GraphitiConfig = modules['GraphitiConfig']
    config = GraphitiConfig()

    llm_client = None
    embedder_client = None

    try:
        llm_client = modules['LLMClientFactory'].create(config.llm)
    except Exception as exc:
        if require_llm:
            raise RuntimeError(f'Failed to create LLM client: {exc}') from exc
        LOGGER.warning('LLM client unavailable for this maintenance run: %s', exc)

    try:
        embedder_client = modules['EmbedderFactory'].create(config.embedder)
    except Exception as exc:
        if require_embedder:
            raise RuntimeError(f'Failed to create embedder client: {exc}') from exc
        LOGGER.warning('Embedder client unavailable for this maintenance run: %s', exc)

    db_config = modules['DatabaseDriverFactory'].create_config(config.database)
    graphiti_kwargs: dict[str, Any] = {
        'llm_client': llm_client,
        'embedder': embedder_client,
        'max_coroutines': semaphore_limit,
    }

    if config.database.provider.lower() == 'falkordb':
        driver = modules['FalkorDriver'](
            host=db_config['host'],
            port=db_config['port'],
            password=db_config['password'],
            database=db_config['database'],
        )
        graphiti_kwargs['graph_driver'] = driver
    else:
        graphiti_kwargs['uri'] = db_config['uri']
        graphiti_kwargs['user'] = db_config['user']
        graphiti_kwargs['password'] = db_config['password']

    client = modules['Graphiti'](**graphiti_kwargs)
    await client.build_indices_and_constraints()

    return MaintenanceRuntime(
        config=config,
        client=client,
        graphiti_mcp_server_path=resolved_graphiti_path,
    )


def clone_client_for_group(client: Any, group_id: str) -> Any:
    from graphiti_core import Graphiti

    if getattr(client.driver, 'provider', None) and client.driver.provider.name == 'FALKORDB':
        cloned_driver = copy.copy(client.driver)
        cloned_driver._database = group_id
    else:
        cloned_driver = client.driver.clone(database=group_id)

    return Graphiti(
        graph_driver=cloned_driver,
        llm_client=client.llm_client,
        embedder=client.embedder,
        cross_encoder=client.cross_encoder,
        store_raw_episode_content=client.store_raw_episode_content,
        max_coroutines=client.max_coroutines,
    )


async def generate_embeddings_for_communities(nodes: list[Any], embedder: Any) -> None:
    await asyncio.gather(*(node.generate_name_embedding(embedder) for node in nodes))

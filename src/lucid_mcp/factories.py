"""Factory classes for creating LLM, Embedder, and Database clients."""

from lucid_mcp.config import DatabaseConfig, EmbedderConfig, LLMConfig

try:
    from graphiti_core.driver.falkordb_driver import FalkorDriver  # noqa: F401

    HAS_FALKOR = True
except ImportError:
    HAS_FALKOR = False

from graphiti_core.embedder import EmbedderClient, OpenAIEmbedder
from graphiti_core.llm_client import LLMClient, OpenAIClient
from graphiti_core.llm_client.config import LLMConfig as GraphitiLLMConfig

try:
    from graphiti_core.embedder.azure_openai import AzureOpenAIEmbedderClient

    HAS_AZURE_EMBEDDER = True
except ImportError:
    HAS_AZURE_EMBEDDER = False

try:
    from graphiti_core.embedder.gemini import GeminiEmbedder

    HAS_GEMINI_EMBEDDER = True
except ImportError:
    HAS_GEMINI_EMBEDDER = False

try:
    from graphiti_core.embedder.voyage import VoyageAIEmbedder

    HAS_VOYAGE_EMBEDDER = True
except ImportError:
    HAS_VOYAGE_EMBEDDER = False

try:
    from graphiti_core.llm_client.azure_openai_client import AzureOpenAILLMClient

    HAS_AZURE_LLM = True
except ImportError:
    HAS_AZURE_LLM = False

try:
    from graphiti_core.llm_client.anthropic_client import AnthropicClient

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    from graphiti_core.llm_client.gemini_client import GeminiClient

    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    from graphiti_core.llm_client.groq_client import GroqClient

    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False


def _validate_api_key(provider_name: str, api_key: str | None, logger) -> str:
    if not api_key:
        raise ValueError(
            f'{provider_name} API key is not configured. Please set the appropriate environment variable.'
        )
    logger.info(f'Creating {provider_name} client')
    return api_key


class LLMClientFactory:
    """Factory for creating LLM clients based on configuration."""

    @staticmethod
    def create(config: LLMConfig) -> LLMClient:
        import logging

        logger = logging.getLogger(__name__)
        provider = config.provider.lower()

        match provider:
            case 'openai':
                if not config.providers.openai:
                    raise ValueError('OpenAI provider configuration not found')

                api_key = config.providers.openai.api_key
                _validate_api_key('OpenAI', api_key, logger)

                from graphiti_core.llm_client.config import LLMConfig as CoreLLMConfig

                small_model = config.model
                llm_config = CoreLLMConfig(
                    api_key=api_key,
                    base_url=config.providers.openai.api_url,
                    model=config.model,
                    small_model=small_model,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                )

                reasoning_prefixes = ('o1', 'o3', 'gpt-5')
                is_reasoning_model = config.model.startswith(reasoning_prefixes)
                if is_reasoning_model:
                    return OpenAIClient(config=llm_config, reasoning='minimal', verbosity='low')
                return OpenAIClient(config=llm_config, reasoning=None, verbosity=None)

            case 'azure_openai':
                if not HAS_AZURE_LLM:
                    raise ValueError('Azure OpenAI LLM client not available in graphiti-core')
                if not config.providers.azure_openai:
                    raise ValueError('Azure OpenAI provider configuration not found')

                azure_config = config.providers.azure_openai
                if not azure_config.api_url:
                    raise ValueError('Azure OpenAI API URL is required')

                api_key = azure_config.api_key
                _validate_api_key('Azure OpenAI', api_key, logger)

                from openai import AsyncOpenAI
                from graphiti_core.llm_client.config import LLMConfig as CoreLLMConfig

                base_url = azure_config.api_url
                if not base_url.endswith('/'):
                    base_url += '/'
                if not base_url.endswith('openai/v1/'):
                    base_url += 'openai/v1/'

                azure_client = AsyncOpenAI(base_url=base_url, api_key=api_key)
                llm_config = CoreLLMConfig(
                    api_key=api_key,
                    base_url=base_url,
                    model=config.model,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                )
                return AzureOpenAILLMClient(
                    azure_client=azure_client,
                    config=llm_config,
                    max_tokens=config.max_tokens,
                )

            case 'anthropic':
                if not HAS_ANTHROPIC:
                    raise ValueError('Anthropic client not available in graphiti-core')
                if not config.providers.anthropic:
                    raise ValueError('Anthropic provider configuration not found')

                api_key = config.providers.anthropic.api_key
                _validate_api_key('Anthropic', api_key, logger)

                llm_config = GraphitiLLMConfig(
                    api_key=api_key,
                    model=config.model,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                )
                return AnthropicClient(config=llm_config)

            case 'gemini':
                if not HAS_GEMINI:
                    raise ValueError('Gemini client not available in graphiti-core')
                if not config.providers.gemini:
                    raise ValueError('Gemini provider configuration not found')

                api_key = config.providers.gemini.api_key
                _validate_api_key('Gemini', api_key, logger)

                llm_config = GraphitiLLMConfig(
                    api_key=api_key,
                    model=config.model,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                )
                return GeminiClient(config=llm_config)

            case 'groq':
                if not HAS_GROQ:
                    raise ValueError('Groq client not available in graphiti-core')
                if not config.providers.groq:
                    raise ValueError('Groq provider configuration not found')

                api_key = config.providers.groq.api_key
                _validate_api_key('Groq', api_key, logger)

                llm_config = GraphitiLLMConfig(
                    api_key=api_key,
                    base_url=config.providers.groq.api_url,
                    model=config.model,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                )
                return GroqClient(config=llm_config)

            case _:
                raise ValueError(f'Unsupported LLM provider: {provider}')


class EmbedderFactory:
    """Factory for creating Embedder clients based on configuration."""

    @staticmethod
    def create(config: EmbedderConfig) -> EmbedderClient:
        import logging

        logger = logging.getLogger(__name__)
        provider = config.provider.lower()

        match provider:
            case 'openai':
                if not config.providers.openai:
                    raise ValueError('OpenAI provider configuration not found')

                api_key = config.providers.openai.api_key
                _validate_api_key('OpenAI Embedder', api_key, logger)

                from graphiti_core.embedder.openai import OpenAIEmbedderConfig

                embedder_config = OpenAIEmbedderConfig(
                    api_key=api_key,
                    embedding_model=config.model,
                    base_url=config.providers.openai.api_url,
                    embedding_dim=config.dimensions,
                )
                return OpenAIEmbedder(config=embedder_config)

            case 'azure_openai':
                if not HAS_AZURE_EMBEDDER:
                    raise ValueError('Azure OpenAI embedder not available in graphiti-core')
                if not config.providers.azure_openai:
                    raise ValueError('Azure OpenAI provider configuration not found')

                azure_config = config.providers.azure_openai
                if not azure_config.api_url:
                    raise ValueError('Azure OpenAI API URL is required')

                api_key = azure_config.api_key
                _validate_api_key('Azure OpenAI Embedder', api_key, logger)

                from openai import AsyncOpenAI

                base_url = azure_config.api_url
                if not base_url.endswith('/'):
                    base_url += '/'
                if not base_url.endswith('openai/v1/'):
                    base_url += 'openai/v1/'

                azure_client = AsyncOpenAI(base_url=base_url, api_key=api_key)
                return AzureOpenAIEmbedderClient(
                    azure_client=azure_client,
                    model=config.model or 'text-embedding-3-small',
                )

            case 'gemini':
                if not HAS_GEMINI_EMBEDDER:
                    raise ValueError('Gemini embedder not available in graphiti-core')
                if not config.providers.gemini:
                    raise ValueError('Gemini provider configuration not found')

                api_key = config.providers.gemini.api_key
                _validate_api_key('Gemini Embedder', api_key, logger)

                from graphiti_core.embedder.gemini import GeminiEmbedderConfig

                gemini_config = GeminiEmbedderConfig(
                    api_key=api_key,
                    embedding_model=config.model or 'models/text-embedding-004',
                    embedding_dim=config.dimensions or 768,
                )
                return GeminiEmbedder(config=gemini_config)

            case 'voyage':
                if not HAS_VOYAGE_EMBEDDER:
                    raise ValueError('Voyage embedder not available in graphiti-core')
                if not config.providers.voyage:
                    raise ValueError('Voyage provider configuration not found')

                api_key = config.providers.voyage.api_key
                _validate_api_key('Voyage Embedder', api_key, logger)

                from graphiti_core.embedder.voyage import VoyageAIEmbedderConfig

                voyage_config = VoyageAIEmbedderConfig(
                    api_key=api_key,
                    embedding_model=config.model or 'voyage-3',
                    embedding_dim=config.dimensions or 1024,
                )
                return VoyageAIEmbedder(config=voyage_config)

            case _:
                raise ValueError(f'Unsupported Embedder provider: {provider}')


class DatabaseDriverFactory:
    """Factory for creating database configuration dictionaries."""

    @staticmethod
    def create_config(config: DatabaseConfig) -> dict:
        provider = config.provider.lower()

        match provider:
            case 'neo4j':
                if config.providers.neo4j:
                    neo4j_config = config.providers.neo4j
                else:
                    from lucid_mcp.config import Neo4jProviderConfig

                    neo4j_config = Neo4jProviderConfig()

                import os

                uri = os.environ.get('NEO4J_URI', neo4j_config.uri)
                username = os.environ.get('NEO4J_USER', neo4j_config.username)
                password = os.environ.get('NEO4J_PASSWORD', neo4j_config.password)

                return {
                    'uri': uri,
                    'user': username,
                    'password': password,
                }

            case 'falkordb':
                if not HAS_FALKOR:
                    raise ValueError('FalkorDB driver not available in graphiti-core')

                if config.providers.falkordb:
                    falkor_config = config.providers.falkordb
                else:
                    from lucid_mcp.config import FalkorDBProviderConfig

                    falkor_config = FalkorDBProviderConfig()

                import os
                from urllib.parse import urlparse

                uri = os.environ.get('FALKORDB_URI', falkor_config.uri)
                password = os.environ.get('FALKORDB_PASSWORD', falkor_config.password)
                parsed = urlparse(uri)
                host = parsed.hostname or 'localhost'
                port = parsed.port or 6379

                return {
                    'driver': 'falkordb',
                    'host': host,
                    'port': port,
                    'password': password,
                    'database': falkor_config.database,
                }

            case _:
                raise ValueError(f'Unsupported Database provider: {provider}')

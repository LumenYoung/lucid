"""Configuration schemas with YAML and environment support for Lucid MCP."""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class YamlSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source for loading from YAML files."""

    def __init__(self, settings_cls: type[BaseSettings], config_path: Path | None = None):
        super().__init__(settings_cls)
        self.config_path = config_path or Path('config.yaml')

    def _expand_env_vars(self, value: Any) -> Any:
        if isinstance(value, str):
            import re

            def replacer(match):
                var_name = match.group(1)
                default_value = match.group(3) if match.group(3) is not None else ''
                return os.environ.get(var_name, default_value)

            pattern = r'\$\{([^:}]+)(:([^}]*))?\}'
            full_match = re.fullmatch(pattern, value)
            if full_match:
                result = replacer(full_match)
                if isinstance(result, str):
                    lower_result = result.lower().strip()
                    if lower_result in ('true', '1', 'yes', 'on'):
                        return True
                    if lower_result in ('false', '0', 'no', 'off'):
                        return False
                    if lower_result == '':
                        return None
                return result
            return re.sub(pattern, replacer, value)
        if isinstance(value, dict):
            return {k: self._expand_env_vars(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._expand_env_vars(item) for item in value]
        return value

    def get_field_value(self, field_name: str, field_info: Any) -> Any:
        return None

    def __call__(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {}

        with open(self.config_path) as handle:
            raw_config = yaml.safe_load(handle) or {}

        return self._expand_env_vars(raw_config)


class ServerConfig(BaseModel):
    transport: str = Field(default='http')
    host: str = Field(default='0.0.0.0')
    port: int = Field(default=8000)


class OpenAIProviderConfig(BaseModel):
    api_key: str | None = None
    api_url: str = 'https://api.openai.com/v1'
    organization_id: str | None = None


class AzureOpenAIProviderConfig(BaseModel):
    api_key: str | None = None
    api_url: str | None = None
    api_version: str = '2024-10-21'
    deployment_name: str | None = None
    use_azure_ad: bool = False


class AnthropicProviderConfig(BaseModel):
    api_key: str | None = None
    api_url: str = 'https://api.anthropic.com'
    max_retries: int = 3


class GeminiProviderConfig(BaseModel):
    api_key: str | None = None
    project_id: str | None = None
    location: str = 'us-central1'


class GroqProviderConfig(BaseModel):
    api_key: str | None = None
    api_url: str = 'https://api.groq.com/openai/v1'


class VoyageProviderConfig(BaseModel):
    api_key: str | None = None
    api_url: str = 'https://api.voyageai.com/v1'
    model: str = 'voyage-3'


class LLMProvidersConfig(BaseModel):
    openai: OpenAIProviderConfig | None = None
    azure_openai: AzureOpenAIProviderConfig | None = None
    anthropic: AnthropicProviderConfig | None = None
    gemini: GeminiProviderConfig | None = None
    groq: GroqProviderConfig | None = None


class LLMConfig(BaseModel):
    provider: str = Field(default='openai')
    model: str = Field(default='gpt-4o-mini')
    temperature: float | None = Field(default=None)
    max_tokens: int = Field(default=4096)
    providers: LLMProvidersConfig = Field(default_factory=LLMProvidersConfig)


class EmbedderProvidersConfig(BaseModel):
    openai: OpenAIProviderConfig | None = None
    azure_openai: AzureOpenAIProviderConfig | None = None
    gemini: GeminiProviderConfig | None = None
    voyage: VoyageProviderConfig | None = None


class EmbedderConfig(BaseModel):
    provider: str = Field(default='openai')
    model: str = Field(default='text-embedding-3-small')
    dimensions: int = Field(default=1536)
    providers: EmbedderProvidersConfig = Field(default_factory=EmbedderProvidersConfig)


class Neo4jProviderConfig(BaseModel):
    uri: str = 'bolt://localhost:7687'
    username: str = 'neo4j'
    password: str | None = None
    database: str = 'neo4j'
    use_parallel_runtime: bool = False


class FalkorDBProviderConfig(BaseModel):
    uri: str = 'redis://localhost:6379'
    password: str | None = None
    database: str = 'default_db'


class DatabaseProvidersConfig(BaseModel):
    neo4j: Neo4jProviderConfig | None = None
    falkordb: FalkorDBProviderConfig | None = None


class DatabaseConfig(BaseModel):
    provider: str = Field(default='falkordb')
    providers: DatabaseProvidersConfig = Field(default_factory=DatabaseProvidersConfig)


class EntityTypeConfig(BaseModel):
    name: str
    description: str


class GraphitiAppConfig(BaseModel):
    group_id: str = Field(default='work')
    episode_id_prefix: str | None = Field(default='')
    user_id: str = Field(default='lucid_mcp')
    entity_types: list[EntityTypeConfig] = Field(default_factory=list)

    def model_post_init(self, __context) -> None:
        if self.episode_id_prefix is None:
            self.episode_id_prefix = ''


class LucidPolicyConfig(BaseModel):
    profile_name: str = 'work'
    default_write_group: str = 'work'
    default_read_groups: list[str] = Field(default_factory=lambda: ['work'])
    allowed_write_groups: list[str] = Field(default_factory=lambda: ['work'])
    allowed_read_groups: list[str] = Field(default_factory=lambda: ['work'])
    rewrite_disallowed_write_group_to_default: bool = True
    fallback_to_default_read_groups: bool = True


class LucidConfig(BaseSettings):
    server: ServerConfig = Field(default_factory=ServerConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedder: EmbedderConfig = Field(default_factory=EmbedderConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    graphiti: GraphitiAppConfig = Field(default_factory=GraphitiAppConfig)
    lucid: LucidPolicyConfig = Field(default_factory=LucidPolicyConfig)
    destroy_graph: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_prefix='',
        env_nested_delimiter='__',
        case_sensitive=False,
        extra='ignore',
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        config_path = Path(os.environ.get('CONFIG_PATH', 'config/config.yaml'))
        yaml_settings = YamlSettingsSource(settings_cls, config_path)
        return (init_settings, env_settings, yaml_settings, dotenv_settings)

    def apply_cli_overrides(self, args) -> None:
        if hasattr(args, 'transport') and args.transport:
            self.server.transport = args.transport
        if hasattr(args, 'host') and args.host:
            self.server.host = args.host
        if hasattr(args, 'port') and args.port:
            self.server.port = args.port
        if hasattr(args, 'llm_provider') and args.llm_provider:
            self.llm.provider = args.llm_provider
        if hasattr(args, 'model') and args.model:
            self.llm.model = args.model
        if hasattr(args, 'temperature') and args.temperature is not None:
            self.llm.temperature = args.temperature
        if hasattr(args, 'embedder_provider') and args.embedder_provider:
            self.embedder.provider = args.embedder_provider
        if hasattr(args, 'embedder_model') and args.embedder_model:
            self.embedder.model = args.embedder_model
        if hasattr(args, 'database_provider') and args.database_provider:
            self.database.provider = args.database_provider
        if hasattr(args, 'group_id') and args.group_id:
            self.graphiti.group_id = args.group_id
            self.lucid.default_write_group = args.group_id
        if hasattr(args, 'user_id') and args.user_id:
            self.graphiti.user_id = args.user_id

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Anthropic
    anthropic_api_key: str = ""

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "tax_chunks"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Langfuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # Models
    planner_model: str = "claude-haiku-4-5-20251001"
    synthesizer_model: str = "claude-sonnet-4-6"
    critic_model: str = "claude-haiku-4-5-20251001"

    # Retrieval
    hybrid_alpha: float = 0.65
    top_k_retrieval: int = 20
    top_k_final: int = 5
    max_critic_iterations: int = 3

    # Embedding
    bge_m3_model: str = "BAAI/bge-m3"
    bge_reranker_model: str = "BAAI/bge-reranker-v2-m3"
    bge_m3_device: str = "cpu"

    # Cache
    semantic_cache_threshold: float = 0.92
    cache_ttl_seconds: int = 86400

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    rate_limit_per_minute: int = 10

    # Scraper schedules (cron syntax)
    scraper_tax_code_cron: str = "0 2 * * *"
    scraper_rs_ge_cron: str = "0 */6 * * *"


@lru_cache
def get_settings() -> Settings:
    return Settings()

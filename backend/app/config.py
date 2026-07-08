from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-large"
    openai_stt_model: str = "whisper-1"
    openai_tts_model: str = "tts-1"
    openai_tts_voice: str = "alloy"

    admin_username: str = "admin"
    admin_password_hash: str = ""

    database_url: str = "sqlite:///./otc.db"
    vector_index_dir: str = "./data/vector_index"
    corpus_dir: str = "./data/corpus"

    retrieval_top_k: int = 5
    chunk_size_chars: int = 1200
    chunk_overlap_chars: int = 200

    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

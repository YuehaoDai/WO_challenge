"""Configuration management using pydantic-settings."""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5")
    reranker_model: str = Field(default="BAAI/bge-reranker-base")

    llm_provider: str = Field(default="ollama")
    ollama_base_url: str = Field(default="http://host.docker.internal:11434")
    ollama_model: str = Field(default="qwen2.5:7b")
    openai_api_key: str = Field(default="")
    openai_base_url: str = Field(default="https://api.openai.com/v1")
    openai_model: str = Field(default="gpt-4o-mini")

    llm_temperature: float = Field(default=0.1)
    llm_max_tokens: int = Field(default=2048)

    faiss_index_path: str = Field(default="/app/data/processed/faiss")
    db_path: str = Field(default="/app/data/processed/app.db")
    chunks_jsonl_path: str = Field(default="/app/data/processed/chunks.jsonl")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()

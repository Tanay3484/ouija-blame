"""All settings come from here. Environment variables use the OB_ prefix."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OB_", env_file=".env", extra="ignore")

    # Gemma through Ollama: the medium, which only points at passages.
    ollama_url: str = "http://localhost:11434"
    model: str = "gemma3:4b"
    llm_timeout_s: float = 180.0
    llm_num_predict: int = 160
    llm_num_thread: int | None = None
    llm_num_ctx: int = 4096

    # How many ranked passages the medium sees, and how many it may choose.
    passages_shown: int = 16
    passages_chosen: int = 3

    # Live séances: clones live here, and repos above the cap are refused (GitHub reports size in KB).
    clone_dir: str = "/tmp/ouija-clones"
    clone_cap_kb: int = 150_000
    clone_keep: int = 6
    git_timeout_s: float = 120.0

    # Requests per minute per client for the routes that cost CPU.
    rate_per_minute: int = 6

    # Serving the built app and the gallery from the same process.
    static_dir: str = "../app/dist"
    gallery_dir: str = "../app/public/gallery"
    cors_origins: str = "*"

    @property
    def ollama_base(self) -> str:
        base = self.ollama_url.rstrip("/")
        return base if "://" in base else f"http://{base}"


@lru_cache
def get_settings() -> Settings:
    return Settings()

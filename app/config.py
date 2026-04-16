"""Application configuration for the VYRA local repository service."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration for the local repository service.

    All settings can be overridden via environment variables with the prefix
    ``VYRA_LOCAL_REPO_``.  Example: ``VYRA_LOCAL_REPO_DATA_DIR=/my/data``.
    """

    # ── Paths ─────────────────────────────────────────────────────────────────
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"

    # ── Network ───────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8100
    domain: str = "localhost"

    # ── Auth ──────────────────────────────────────────────────────────────────
    # When empty or unset, all endpoints are publicly accessible (local dev).
    api_key: str = ""

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"

    # ── Derived paths (not configurable) ─────────────────────────────────────
    @property
    def registry_file(self) -> Path:
        """JSON file listing registered content types."""
        return self.data_dir / "_registry" / "content_types.json"

    @property
    def index_file(self) -> Path:
        """Unified index.json containing all content types."""
        return self.data_dir / "index.json"

    model_config = {
        "env_prefix": "VYRA_LOCAL_REPO_",
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()

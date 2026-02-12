import base64
import os
import tempfile
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    github_app_id: str
    github_private_key: str  # base64-encoded PEM key
    webhook_secret: str
    openrouter_api_key: str
    llm_model: str = "anthropic/claude-sonnet-4"  # any OpenRouter model slug
    database_url: str = "sqlite+aiosqlite:///pr_reviews.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def get_private_key_bytes(self) -> bytes:
        """Decode the base64-encoded private key to raw PEM bytes."""
        return base64.b64decode(self.github_private_key)

    def get_private_key_path(self) -> str:
        """Write private key to a temp file and return the path.

        Some JWT libraries require a file path rather than raw bytes.
        The file is written with restrictive permissions (0600).
        """
        key_bytes = self.get_private_key_bytes()
        fd, path = tempfile.mkstemp(suffix=".pem")
        os.write(fd, key_bytes)
        os.close(fd)
        os.chmod(path, 0o600)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()

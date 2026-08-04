"""Configuration loader for Care-Beacon RAG system."""

import os
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv


class Config:
    """Configuration manager for the application."""

    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize configuration.

        Args:
            config_path: Path to the YAML configuration file
        """
        # Load environment variables
        load_dotenv()

        # Load YAML configuration
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(self.config_path, 'r') as f:
            self._config: Dict[str, Any] = yaml.safe_load(f)

        # Override with environment variables if present
        self._apply_env_overrides()

    def _apply_env_overrides(self):
        """Override configuration with environment variables."""
        # API keys
        if os.getenv("OPENAI_API_KEY"):
            self._config.setdefault("api_keys", {})["openai"] = os.getenv("OPENAI_API_KEY")

        if os.getenv("ANTHROPIC_API_KEY"):
            self._config.setdefault("api_keys", {})["anthropic"] = os.getenv("ANTHROPIC_API_KEY")

        # Redis configuration
        if os.getenv("REDIS_HOST"):
            self._config["cache"]["host"] = os.getenv("REDIS_HOST")
        if os.getenv("REDIS_PORT"):
            self._config["cache"]["port"] = int(os.getenv("REDIS_PORT"))
        if os.getenv("REDIS_PASSWORD"):
            self._config["cache"]["password"] = os.getenv("REDIS_PASSWORD")

        # Logging level
        if os.getenv("LOG_LEVEL"):
            self._config["logging"]["level"] = os.getenv("LOG_LEVEL")

        # Embedding batch size
        if os.getenv("EMBEDDING_BATCH_SIZE"):
            self._config.setdefault("embeddings", {})["batch_size"] = int(os.getenv("EMBEDDING_BATCH_SIZE"))

        # Ingestion batch sizes (for low-memory environments like Render free tier)
        if os.getenv("INGESTION_ARTICLE_BATCH_SIZE"):
            self._config.setdefault("ingestion", {})["article_batch_size"] = int(os.getenv("INGESTION_ARTICLE_BATCH_SIZE"))
        if os.getenv("INGESTION_CHUNK_BATCH_SIZE"):
            self._config.setdefault("ingestion", {})["chunk_batch_size"] = int(os.getenv("INGESTION_CHUNK_BATCH_SIZE"))

        # Vector Database Configuration
        if os.getenv("VECTOR_DB_PROVIDER"):
            self._config.setdefault("vector_db", {})["provider"] = os.getenv("VECTOR_DB_PROVIDER")
        if os.getenv("QDRANT_URL"):
            self._config.setdefault("vector_db", {})["qdrant_url"] = os.getenv("QDRANT_URL")
        if os.getenv("QDRANT_API_KEY"):
            self._config.setdefault("vector_db", {})["qdrant_api_key"] = os.getenv("QDRANT_API_KEY")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by dot-notation key.

        Args:
            key: Configuration key (supports dot notation, e.g., 'embeddings.model')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_api_key(self, provider: str) -> str:
        """Get API key for a specific provider.

        Args:
            provider: Provider name (e.g., 'openai', 'anthropic')

        Returns:
            API key

        Raises:
            ValueError: If API key not found
        """
        api_keys = self._config.get("api_keys", {})
        if provider not in api_keys:
            raise ValueError(f"API key for '{provider}' not found in configuration")
        return api_keys[provider]

    @property
    def config(self) -> Dict[str, Any]:
        """Get the full configuration dictionary."""
        return self._config


# Global configuration instance
_config_instance: Config | None = None


def get_config(config_path: str = "config/config.yaml") -> Config:
    """Get the global configuration instance.

    Args:
        config_path: Path to configuration file

    Returns:
        Configuration instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_path)
    return _config_instance

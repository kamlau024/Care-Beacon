"""Factory for the Qdrant vector database.

ChromaDB support has been removed. This module exists solely to resolve the
configured provider and construct the corresponding database instance.
"""

from typing import Optional, TYPE_CHECKING

from src.config_loader import get_config

if TYPE_CHECKING:
    from src.storage.qdrant_db import QdrantVectorDatabase


def create_vector_database(
    provider: Optional[str] = None,
    **kwargs,
) -> "QdrantVectorDatabase":
    """Create the Qdrant vector database instance.

    Args:
        provider: Database provider (must be "qdrant"). If None, reads from config.
        **kwargs: Additional arguments passed to the database constructor.

    Returns:
        QdrantVectorDatabase instance

    Raises:
        ValueError: If provider is anything other than "qdrant"
    """
    config = get_config()
    provider = provider or config.get("vector_db.provider", "qdrant")

    if provider != "qdrant":
        raise ValueError(
            f"Unsupported vector database provider: {provider!r}. Only 'qdrant' is supported. "
            "Set VECTOR_DB_PROVIDER=qdrant and configure QDRANT_URL and QDRANT_API_KEY."
        )

    from src.storage.qdrant_db import QdrantVectorDatabase

    return QdrantVectorDatabase(**kwargs)

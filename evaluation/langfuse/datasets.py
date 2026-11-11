"""Dataset upload to Langfuse."""

from langfuse import Langfuse


def upsert_dataset(name: str, items: list[dict], client: Langfuse | None = None) -> None:
    """Create the dataset if absent and upsert items, idempotent by item ``id``.

    Each item is a dict with ``id`` and ``input``, plus optional ``expected_output``
    and ``metadata``. Langfuse upserts items that share an id (ids are globally
    unique across datasets, so callers should namespace them per dataset).
    """
    client = client or Langfuse()
    try:
        client.get_dataset(name)
    except Exception:  # not found -> create
        client.create_dataset(name=name)
    for item in items:
        client.create_dataset_item(
            dataset_name=name,
            id=item["id"],
            input=item["input"],
            expected_output=item.get("expected_output"),
            metadata=item.get("metadata"),
        )
    client.flush()

from pathlib import Path

from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, PointStruct, VectorParams


class QdrantStorage:
    """Own a Qdrant connection, using persistent local storage by default."""

    def __init__(
        self,
        path: str | Path = "qdrant_storage",
        *,
        url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        if url:
            self.client = QdrantClient(url=url, api_key=api_key)
        else:
            storage_path = Path(path).expanduser()
            if not storage_path.is_absolute():
                storage_path = Path(__file__).resolve().parent / storage_path
            self.client = QdrantClient(path=str(storage_path))

    def ensure_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: Distance = Distance.COSINE,
    ) -> None:
        """Create a collection or verify its settings without deleting data."""
        expected = VectorParams(size=vector_size, distance=distance)
        if self.client.collection_exists(collection_name):
            collection = self.client.get_collection(collection_name)
            actual = collection.config.params.vectors
            if (
                not isinstance(actual, VectorParams)
                or actual.size != expected.size
                or actual.distance != expected.distance
            ):
                raise ValueError(
                    f"Collection {collection_name!r} has incompatible vector settings. "
                    "Use matching settings or a new collection; existing data was preserved."
                )
            return
        self.client.create_collection(
            collection_name=collection_name, vectors_config=expected
        )

    def upsert(
        self, collection_name: str, points: list[PointStruct]
    ) -> None:
        """Insert or replace points by ID, retaining their document payloads."""
        if points:
            self.client.upsert(
                collection_name=collection_name, points=points, wait=True
            )

    def search(
        self, collection_name: str, vector: list[float], limit: int = 5
    ) -> list[models.ScoredPoint]:
        """Return ranked hits with each chunk's text and source in its payload."""
        results = self.client.query_points(
            collection_name=collection_name,
            query=vector,
            limit=limit,
            with_payload=True,
        )
        # Keep the ranked points intact so text, provenance, and scores stay paired.
        return results.points

    def close(self) -> None:
        self.client.close()

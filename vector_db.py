"""Synchronous vector storage with local persistence and optional server access."""

from pathlib import Path
from threading import RLock

from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, PointStruct, VectorParams

from custom_types import RAGSearchResult, RAGUpsertResult


class QdrantStorage:
    """Own a Qdrant connection, using persistent local storage by default."""

    def __init__(
        self,
        path: str | Path = "qdrant_storage",
        *,
        url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """Open the configured server, or a path relative to this project."""
        self._lock = RLock()
        if url:
            self.client = QdrantClient(url=url, api_key=api_key)
        else:
            storage_path = Path(path).expanduser()
            if not storage_path.is_absolute():
                storage_path = Path(__file__).resolve().parent / storage_path
            # FastAPI and Inngest use different threads; methods serialize access.
            self.client = QdrantClient(
                path=str(storage_path), force_disable_check_same_thread=True
            )

    def get_collections(self) -> models.CollectionsResponse:
        """Check connectivity while sharing the same lock as database writes."""
        with self._lock:
            return self.client.get_collections()

    def ensure_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: Distance = Distance.COSINE,
    ) -> None:
        """Create a collection or verify its settings without deleting data."""
        with self._lock:
            expected = VectorParams(size=vector_size, distance=distance)
            if self.client.collection_exists(collection_name):
                self.validate_collection(collection_name, vector_size, distance)
                return
            self.client.create_collection(
                collection_name=collection_name, vectors_config=expected
            )

    def validate_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: Distance = Distance.COSINE,
    ) -> None:
        """Check a collection without creating or changing it during queries."""
        with self._lock:
            if not self.client.collection_exists(collection_name):
                raise ValueError(
                    "Document collection is missing; ingest a document first"
                )
            actual = self.client.get_collection(collection_name).config.params.vectors
            if (
                not isinstance(actual, VectorParams)
                or actual.size != vector_size
                or actual.distance != distance
            ):
                raise ValueError(
                    f"Collection {collection_name!r} has incompatible vector settings. "
                    "Use matching settings or a new collection; existing data was preserved."
                )

    def upsert(
        self, collection_name: str, points: list[PointStruct]
    ) -> RAGUpsertResult:
        """Insert/replace points and report the submitted count after success."""
        with self._lock:
            if points:
                self.client.upsert(
                    collection_name=collection_name, points=points, wait=True
                )
        return RAGUpsertResult(ingested=len(points))

    def search(
        self, collection_name: str, vector: list[float], limit: int = 5
    ) -> RAGSearchResult:
        """Return ranked hits with each chunk's text and source in its payload."""
        with self._lock:
            results = self.client.query_points(
                collection_name=collection_name,
                query=vector,
                limit=limit,
                with_payload=True,
            )
        # Keep the ranked points intact so text, provenance, and scores stay paired.
        return RAGSearchResult(hits=results.points)

    def close(self) -> None:
        """Release the connection and its local storage lock."""
        with self._lock:
            self.client.close()

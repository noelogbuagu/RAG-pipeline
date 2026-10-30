"""Check shared contracts at serialization and storage boundaries."""

import unittest
from unittest.mock import Mock, patch

from pydantic import ValidationError
from qdrant_client.models import PointStruct, ScoredPoint

from custom_types import DocumentChunk, RAGChunkAndSrc, RAGSearchResult, RAGUpsertResult
from vector_db import QdrantStorage


class CustomTypesTests(unittest.TestCase):
    def test_chunk_round_trip_retains_provenance(self):
        loaded = RAGChunkAndSrc(
            source_id="guide.pdf",
            chunks=[
                DocumentChunk(
                    text="Example", source="guide.pdf", chunk_index=0, page_label="2"
                )
            ],
        )
        restored = RAGChunkAndSrc.model_validate_json(loaded.model_dump_json())
        self.assertEqual(restored, loaded)
        with self.assertRaises(ValidationError):
            RAGChunkAndSrc(source_id=None, chunks=[])
        with self.assertRaises(ValidationError):
            DocumentChunk(text="Example", source="guide.pdf", chunk_index=-1)

    def test_search_views_do_not_replace_hit_provenance(self):
        result = RAGSearchResult(
            hits=[
                ScoredPoint(
                    id=1,
                    version=0,
                    score=0.9,
                    payload={"text": "A", "source": "file.pdf", "page": 2},
                ),
                ScoredPoint(
                    id=2,
                    version=0,
                    score=0.8,
                    payload={"text": "B", "source": "file.pdf", "page": 5},
                ),
                ScoredPoint(id=3, version=0, score=0.7, payload=None),
            ]
        )
        restored = RAGSearchResult.model_validate_json(result.model_dump_json())
        self.assertEqual(restored.contexts, ["A", "B"])
        self.assertEqual(restored.sources, ["file.pdf"])
        self.assertEqual([hit.payload["page"] for hit in restored.hits[:2]], [2, 5])
        self.assertIsNone(restored.hits[2].payload)

    def test_upsert_reports_count_only_after_success(self):
        client = Mock()
        with patch("vector_db.QdrantClient", return_value=client):
            storage = QdrantStorage()
            try:
                self.assertEqual(
                    storage.upsert("documents", []), RAGUpsertResult(ingested=0)
                )
                client.upsert.assert_not_called()
                points = [PointStruct(id=1, vector=[1.0, 0.0, 0.0])]
                self.assertEqual(storage.upsert("documents", points).ingested, 1)
                client.upsert.side_effect = RuntimeError("unavailable")
                with self.assertRaisesRegex(RuntimeError, "unavailable"):
                    storage.upsert("documents", points)
            finally:
                storage.close()

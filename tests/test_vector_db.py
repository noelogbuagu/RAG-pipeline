import tempfile
import unittest

from qdrant_client.models import Distance, PointStruct

from vector_db import QdrantStorage


class QdrantStorageTests(unittest.TestCase):
    def test_upsert_search_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = QdrantStorage(directory)
            try:
                storage.ensure_collection("documents", vector_size=3)
                storage.upsert("documents", [
                    PointStruct(id=1, vector=[1.0, 0.0, 0.0], payload={"text": "old"}),
                    PointStruct(id=2, vector=[0.0, 1.0, 0.0], payload={"text": "other"}),
                ])
                storage.upsert("documents", [
                    PointStruct(id=1, vector=[1.0, 0.0, 0.0], payload={"text": "updated"}),
                ])
            finally:
                storage.close()

            storage = QdrantStorage(directory)
            try:
                storage.ensure_collection("documents", vector_size=3)
                hits = storage.search("documents", [1.0, 0.0, 0.0], limit=1)
                self.assertEqual(len(hits), 1)
                self.assertEqual(hits[0].id, 1)
                self.assertEqual(hits[0].payload["text"], "updated")
                count = storage.client.count("documents")
                self.assertEqual(count.count, 2)
            finally:
                storage.close()

    def test_incompatible_collection_preserves_data(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = QdrantStorage(directory)
            try:
                storage.ensure_collection("documents", vector_size=3)
                storage.upsert("documents", [
                    PointStruct(id=1, vector=[1.0, 0.0, 0.0]),
                ])
                for size, distance in [(4, Distance.COSINE), (3, Distance.DOT)]:
                    with self.assertRaisesRegex(ValueError, "incompatible"):
                        storage.ensure_collection("documents", size, distance)
                hits = storage.search("documents", [1.0, 0.0, 0.0])
                self.assertEqual(hits[0].id, 1)
            finally:
                storage.close()

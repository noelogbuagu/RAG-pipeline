import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from qdrant_client import models

from main import app, rag_ingest_document


class QdrantConnectionTests(unittest.TestCase):
    def test_data_survives_application_restart(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            "os.environ", {"QDRANT_URL": "", "QDRANT_PATH": directory}
        ):
            with TestClient(app):
                client = app.state.vector_db.client
                client.create_collection(
                    "test_documents",
                    vectors_config=models.VectorParams(
                        size=3, distance=models.Distance.COSINE
                    ),
                )
                client.upsert(
                    "test_documents",
                    points=[models.PointStruct(
                        id=1, vector=[1.0, 0.0, 0.0],
                        payload={"text": "Synthetic document"},
                    )],
                )

            # Reopening also proves shutdown released the local storage lock.
            with TestClient(app) as http:
                result = app.state.vector_db.client.query_points(
                    "test_documents", query=[1.0, 0.0, 0.0], limit=1
                )
                self.assertEqual(result.points[0].payload["text"], "Synthetic document")
                response = http.get("/health/qdrant")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"status": "ok", "collections": 1})
                self.assertEqual(http.get("/api/inngest").status_code, 200)

    def test_server_configuration_and_unavailable_health(self):
        client = Mock()
        with patch.dict("os.environ", {
            "QDRANT_URL": "http://localhost:6333", "QDRANT_API_KEY": "test-key"
        }), patch("vector_db.QdrantClient", return_value=client) as constructor:
            with TestClient(app) as http:
                constructor.assert_called_once_with(
                    url="http://localhost:6333", api_key="test-key"
                )
                client.get_collections.side_effect = RuntimeError("private details")
                response = http.get("/health/qdrant")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {"detail": "Qdrant unavailable"})
            client.close.assert_called_once()

    def test_failed_startup_closes_client(self):
        client = Mock()
        client.get_collections.side_effect = RuntimeError("unreachable")
        with patch("vector_db.QdrantClient", return_value=client):
            with self.assertRaisesRegex(RuntimeError, "unreachable"):
                with TestClient(app):
                    self.fail("Startup should fail when Qdrant is unreachable")
        client.close.assert_called_once()

    def test_ingestion_handler_is_synchronous(self):
        self.assertFalse(rag_ingest_document.is_handler_async)
        result = rag_ingest_document._handler(
            SimpleNamespace(event=SimpleNamespace(name="rag/ingest_document"))
        )
        self.assertEqual(result, {
            "status": "not_implemented", "event": "rag/ingest_document"
        })

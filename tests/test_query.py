"""Test query steps with real temporary Qdrant and synthetic embeddings."""

import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import inngest
from qdrant_client.models import PointStruct

import main
from test_ingestion import SavedSteps
from vector_db import QdrantStorage


class QueryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.storage = QdrantStorage(directory.name)
        self.addCleanup(self.storage.close)
        for item in [
            patch.object(main.app.state, "vector_db", self.storage, create=True),
            patch("main.EMBED_DIM", 3),
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"}),
        ]:
            item.start()
            self.addCleanup(item.stop)
        self.ctx = SimpleNamespace(
            event=SimpleNamespace(
                data={"question": "  How does ingestion work?  ", "top_k": 2}
            ),
            step=SavedSteps(),
        )

    def test_query_returns_ranked_chunks_with_sources_and_replays_models(self):
        self.storage.ensure_collection(main.COLLECTION_NAME, 3)
        payloads = [
            {
                "text": "Read and chunk PDFs",
                "source": "guide.pdf",
                "page_label": "2",
                "chunk_index": 1,
            },
            {
                "text": "Store document vectors",
                "source": "notes.docx",
                "chunk_index": 0,
            },
            {"text": "Unrelated content", "source": "other.pdf", "chunk_index": 0},
        ]
        self.storage.upsert(
            main.COLLECTION_NAME,
            [
                PointStruct(id=i + 1, vector=vector, payload=payload)
                for i, (vector, payload) in enumerate(
                    zip(
                        [[1.0, 0.0, 0.0], [0.8, 0.6, 0.0], [0.0, 1.0, 0.0]],
                        payloads,
                        strict=True,
                    )
                )
            ],
        )
        with patch("main.embed_texts", return_value=[[1.0, 0.0, 0.0]]) as embed:
            result = main.rag_query_documents._handler(self.ctx)
            replayed = main.rag_query_documents._handler(self.ctx)
            embed.assert_called_once_with(["How does ingestion work?"])
        self.assertFalse(main.rag_query_documents.is_handler_async)
        self.assertEqual(
            self.ctx.step.executed, ["validate-query", "embed-query", "search-qdrant"]
        )
        self.assertEqual(replayed, result)
        self.assertEqual([hit.id for hit in result.hits], [1, 2])
        self.assertEqual([hit.payload for hit in result.hits], payloads[:2])
        self.assertGreater(result.hits[0].score, result.hits[1].score)
        self.assertEqual(result.sources, ["guide.pdf", "notes.docx"])

    def test_query_retries_search_without_repeating_embedding(self):
        self.storage.ensure_collection(main.COLLECTION_NAME, 3)
        original = self.storage.search
        attempts = 0

        def transient_failure(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("Temporary database failure")
            return original(*args, **kwargs)

        with (
            patch("main.embed_texts", return_value=[[1.0, 0.0, 0.0]]) as embed,
            patch.object(self.storage, "search", side_effect=transient_failure),
        ):
            with self.assertRaisesRegex(RuntimeError, "Temporary"):
                main.rag_query_documents._handler(self.ctx)
            result = main.rag_query_documents._handler(self.ctx)
            embed.assert_called_once()
        self.assertEqual(result.hits, [])

    def test_invalid_inputs_fail_before_embedding(self):
        invalid = [
            {},
            {"question": " "},
            {"question": 123},
            {"question": "x" * 2001},
            *[
                {"question": "test", "top_k": value}
                for value in [0, 21, True, "5", 1.5]
            ],
        ]
        with patch("main.embed_texts") as embed:
            for data in invalid:
                with (
                    self.subTest(data=data),
                    self.assertRaises(inngest.NonRetriableError),
                ):
                    self.ctx.event.data = data
                    main.rag_query_documents._handler(self.ctx)
            embed.assert_not_called()

    def test_missing_or_incompatible_collection_prevents_embedding(self):
        with patch("main.embed_texts") as embed:
            with self.assertRaisesRegex(
                inngest.NonRetriableError, "ingest a document first"
            ):
                main.rag_query_documents._handler(self.ctx)
            self.assertEqual(self.storage.get_collections().collections, [])
            self.storage.ensure_collection(main.COLLECTION_NAME, 4)
            with self.assertRaisesRegex(inngest.NonRetriableError, "incompatible"):
                main.rag_query_documents._handler(self.ctx)
            embed.assert_not_called()

    def test_missing_key_and_default_limit(self):
        self.storage.ensure_collection(main.COLLECTION_NAME, 3)
        self.assertEqual(main.validate_query({"question": "test"}).top_k, 5)
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": ""}),
            patch("main.embed_texts") as embed,
        ):
            with self.assertRaisesRegex(inngest.NonRetriableError, "OPENAI_API_KEY"):
                main.rag_query_documents._handler(self.ctx)
            embed.assert_not_called()

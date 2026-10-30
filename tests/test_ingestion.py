"""Exercise workflow replay against temporary Qdrant with mocked embeddings."""

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import inngest

import main
from custom_types import DocumentSection, RAGLoadedDocument
from vector_db import QdrantStorage


class SavedSteps:
    """Mimic persisted successful outputs; failed steps remain retryable."""

    def __init__(self):
        self.saved = {}
        self.executed = []
        self.serializer = inngest.PydanticSerializer()

    def run(self, name, handler, *args, output_type=None):
        if name not in self.saved:
            self.executed.append(name)
            result = handler(*args)
            self.saved[name] = (
                self.serializer.serialize(result, output_type)
                if output_type is not None
                else json.dumps(result)
            )
        value = self.saved[name]
        return (
            self.serializer.deserialize(value, output_type)
            if output_type is not None
            else json.loads(value)
        )


class IngestionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.file = self.root / "example.pdf"
        self.file.write_bytes(b"Synthetic file identity; extraction is mocked.")
        self.storage = QdrantStorage(self.root / "db")
        self.addCleanup(self.storage.close)
        self.loaded = RAGLoadedDocument(
            source_id=str(self.file),
            sections=[
                DocumentSection(text="First page of a document.", page_label="1"),
                DocumentSection(text="Second page of a document.", page_label="2"),
            ],
        )
        patches = [
            patch("main.DATA_DIR", self.root),
            patch("main.EMBED_DIM", 3),
            patch("main.INGEST_BATCH_SIZE", 1),
            patch.object(main.app.state, "vector_db", self.storage, create=True),
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"}),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.steps = SavedSteps()
        self.ctx = SimpleNamespace(
            event=SimpleNamespace(data={"path": str(self.file)}), step=self.steps
        )

    def test_steps_preserve_provenance_and_reimport_replaces_points(self):
        with (
            patch("main.load_document", return_value=self.loaded),
            patch("main.embed_texts", return_value=[[1.0, 0.0, 0.0]]) as embed,
        ):
            result = main.rag_ingest_document._handler(self.ctx)
            self.assertEqual(result.status, "indexed")
            self.assertEqual(result.ingested, 2)
            self.assertTrue(result.indexed)
            self.assertEqual(
                self.steps.executed,
                [
                    "validate-document",
                    "extract-text",
                    "chunk-text",
                    "prepare-collection",
                    "embed-batch-1",
                    "upsert-batch-1",
                    "embed-batch-2",
                    "upsert-batch-2",
                    "summarize-ingestion",
                ],
            )
            self.ctx.step = SavedSteps()
            main.rag_ingest_document._handler(self.ctx)
            self.assertEqual(embed.call_count, 4)
        hits = self.storage.search(main.COLLECTION_NAME, [1.0, 0.0, 0.0]).hits
        self.assertEqual(len(hits), 2)
        by_page = {hit.payload["page_label"]: hit.payload for hit in hits}
        for index, section in enumerate(self.loaded.sections):
            payload = by_page[section.page_label]
            self.assertEqual(payload["text"], section.text)
            self.assertEqual(payload["source"], str(self.file))
            self.assertEqual(payload["chunk_index"], index)
            self.assertEqual(payload["document_sha256"], main._file_digest(self.file))

    def test_retry_after_write_reuses_embedding_and_does_not_duplicate(self):
        original = self.storage.upsert
        first_write = True

        def lost_acknowledgement(*args):
            nonlocal first_write
            result = original(*args)
            if first_write:
                first_write = False
                raise RuntimeError("Simulated lost acknowledgement")
            return result

        with (
            patch("main.load_document", return_value=self.loaded) as extract,
            patch("main.embed_texts", return_value=[[1.0, 0.0, 0.0]]) as embed,
            patch.object(self.storage, "upsert", side_effect=lost_acknowledgement),
        ):
            with self.assertRaisesRegex(RuntimeError, "acknowledgement"):
                main.rag_ingest_document._handler(self.ctx)
            result = main.rag_ingest_document._handler(self.ctx)
            self.assertEqual(result.ingested, 2)
            self.assertEqual(embed.call_count, 2)
            extract.assert_called_once()
        self.assertEqual(self.steps.executed.count("upsert-batch-1"), 2)
        self.assertEqual(
            len(self.storage.search(main.COLLECTION_NAME, [1.0, 0.0, 0.0]).hits), 2
        )

    def test_empty_document_skips_credentials_embeddings_and_collection(self):
        self.loaded.sections = []
        with (
            patch("main.load_document", return_value=self.loaded),
            patch("main.embed_texts") as embed,
            patch.dict("os.environ", {"OPENAI_API_KEY": ""}),
        ):
            result = main.rag_ingest_document._handler(self.ctx)
        self.assertEqual(result.status, "no_text")
        self.assertEqual(result.ingested, 0)
        self.assertFalse(result.indexed)
        self.assertIsNone(result.collection)
        embed.assert_not_called()
        self.assertEqual(self.storage.get_collections().collections, [])
        self.assertEqual(self.steps.executed[-1], "summarize-ingestion")

    def test_preflight_rejects_invalid_paths(self):
        outside = self.root.parent / "outside.pdf"
        symlink = self.root / "linked.pdf"
        symlink.symlink_to(outside)
        for path in [
            None,
            "",
            str(outside),
            str(symlink),
            str(self.root / "x.doc"),
            str(self.root / "missing.pdf"),
        ]:
            with self.subTest(path=path), self.assertRaises(inngest.NonRetriableError):
                main.validate_document(path)

    def test_changed_file_and_state_limits_fail_before_embedding(self):
        info = main.validate_document(str(self.file))
        self.file.write_bytes(b"Changed content")
        with self.assertRaisesRegex(inngest.NonRetriableError, "changed"):
            main.extract_document(info)
        with patch("main.MAX_CHUNKS", 1):
            with self.assertRaisesRegex(inngest.NonRetriableError, "chunk limit"):
                main.prepare_chunks(self.loaded)
        info = main.validate_document(str(self.file))
        with (
            patch("main.MAX_TEXT_STEP_BYTES", 1),
            patch("main.load_document", return_value=self.loaded),
            self.assertRaisesRegex(inngest.NonRetriableError, "text exceeds"),
        ):
            main.extract_document(info)

    def test_missing_credentials_and_incompatible_collection_prevent_embedding(self):
        with (
            patch("main.load_document", return_value=self.loaded),
            patch("main.embed_texts") as embed,
        ):
            with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
                with self.assertRaises(inngest.NonRetriableError):
                    main.rag_ingest_document._handler(self.ctx)
            self.storage.ensure_collection(main.COLLECTION_NAME, 4)
            with self.assertRaisesRegex(ValueError, "incompatible"):
                main.rag_ingest_document._handler(self.ctx)
            embed.assert_not_called()

    def test_shared_storage_handles_workflow_and_health_threads(self):
        with (
            patch("main.load_document", return_value=self.loaded),
            patch("main.embed_texts", return_value=[[1.0, 0.0, 0.0]]),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            run = pool.submit(main.rag_ingest_document._handler, self.ctx)
            health = pool.submit(self.storage.get_collections)
            health.result()
            self.assertEqual(run.result().ingested, 2)
        self.assertEqual(
            len(self.storage.search(main.COLLECTION_NAME, [1.0, 0.0, 0.0]).hits), 2
        )

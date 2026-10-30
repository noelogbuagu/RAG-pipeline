"""Verify the team sample works with the real Word loader without external APIs."""

import tempfile
import unittest
from pathlib import Path

from data_loader import load_and_chunk_document
from scripts.create_sample_document import SOURCE, create_sample_document


class SampleDocumentTests(unittest.TestCase):
    def test_sample_round_trip_and_existing_file_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = create_sample_document(Path(directory) / "handbook.docx")
            original = path.read_bytes()
            result = load_and_chunk_document(path)
            text = "\n".join(chunk.text for chunk in result.chunks)
            for paragraph in SOURCE.read_text(encoding="utf-8").splitlines():
                if paragraph.strip():
                    self.assertIn(paragraph, text)
            self.assertTrue(
                all(chunk.source == str(path.resolve()) for chunk in result.chunks)
            )
            with self.assertRaises(FileExistsError):
                create_sample_document(path)
            self.assertEqual(path.read_bytes(), original)

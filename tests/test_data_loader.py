import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from data_loader import (
    EMBED_DIM,
    EMBED_MODEL,
    embed_texts,
    load_and_chunk_document,
    splitter,
)


class DataLoaderTests(unittest.TestCase):
    def test_real_pdf_preserves_page_and_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.pdf"
            writer = PdfWriter()
            for text in ["First page text.", "Second page text."]:
                page = writer.add_blank_page(width=612, height=792)
                font = DictionaryObject(
                    {
                        NameObject("/Type"): NameObject("/Font"),
                        NameObject("/Subtype"): NameObject("/Type1"),
                        NameObject("/BaseFont"): NameObject("/Helvetica"),
                    }
                )
                page[NameObject("/Resources")] = DictionaryObject(
                    {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
                )
                stream = DecodedStreamObject()
                stream.set_data(f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode())
                page[NameObject("/Contents")] = stream
            writer.write(path)
            loaded = load_and_chunk_document(path)
            chunks = loaded.chunks
            self.assertEqual(loaded.source_id, str(path.resolve()))
            self.assertEqual(
                [c.text for c in chunks], ["First page text.", "Second page text."]
            )
            self.assertEqual([c.page_label for c in chunks], ["1", "2"])
            self.assertEqual([c.chunk_index for c in chunks], [0, 1])
            self.assertTrue(all(c.source == str(path.resolve()) for c in chunks))

    def test_docx_chunking_and_invalid_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.docx"
            text = "This is a sentence about document retrieval. " * 500
            with ZipFile(path, "w") as archive:
                archive.writestr(
                    "word/document.xml",
                    (
                        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                        f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>"
                    ),
                )
            loaded = load_and_chunk_document(path)
            chunks = loaded.chunks
            self.assertEqual(loaded.source_id, str(path.resolve()))
            self.assertGreater(len(chunks), 1)
            self.assertEqual([c.chunk_index for c in chunks], list(range(len(chunks))))
            self.assertTrue(
                all(len(splitter._tokenizer(c.text)) <= 1000 for c in chunks)
            )
            self.assertTrue(all(c.source == str(path.resolve()) for c in chunks))
            self.assertTrue(all(c.page_label is None for c in chunks))
            with self.assertRaises(FileNotFoundError):
                load_and_chunk_document(Path(directory) / "missing.pdf")
            with self.assertRaises(ValueError):
                load_and_chunk_document(Path(directory) / "legacy.doc")

    def test_embeddings_batch_order_and_dimensions(self):
        with patch("data_loader.OpenAI") as constructor:
            client = constructor.return_value.__enter__.return_value

            def response(**kwargs):
                self.assertEqual(kwargs["model"], EMBED_MODEL)
                self.assertEqual(kwargs["dimensions"], EMBED_DIM)
                return SimpleNamespace(
                    data=[
                        SimpleNamespace(index=i, embedding=[float(text)] * EMBED_DIM)
                        for i, text in reversed(list(enumerate(kwargs["input"])))
                    ]
                )

            client.embeddings.create.side_effect = response
            vectors = embed_texts([str(i) for i in range(65)])
            self.assertEqual([v[0] for v in vectors], list(range(65)))
            self.assertEqual(client.embeddings.create.call_count, 2)

    def test_embeddings_reject_bad_responses_and_blank_input(self):
        with patch("data_loader.OpenAI") as constructor:
            self.assertEqual(embed_texts([]), [])
            with self.assertRaises(ValueError):
                embed_texts([" "])
            constructor.assert_not_called()
            client = constructor.return_value.__enter__.return_value
            for data in [[], [SimpleNamespace(index=0, embedding=[1.0])]]:
                client.embeddings.create.return_value = SimpleNamespace(data=data)
                with self.assertRaises(ValueError):
                    embed_texts(["test"])

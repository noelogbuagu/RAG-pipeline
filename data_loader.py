"""Load PDF/Word documents, preserve provenance, and embed their text."""

from pathlib import Path

from dotenv import load_dotenv
from llama_index.core.node_parser import SentenceSplitter
from llama_index.readers.file import DocxReader, PDFReader
from openai import OpenAI

from custom_types import (
    DocumentChunk,
    DocumentSection,
    RAGChunkAndSrc,
    RAGLoadedDocument,
)

load_dotenv()

EMBED_MODEL = "text-embedding-3-large"
EMBED_DIM = 3072
EMBED_BATCH_SIZE = 64

# These limits are tokens, not characters or words.
splitter = SentenceSplitter(chunk_size=1000, chunk_overlap=200)


def load_document(path: str | Path) -> RAGLoadedDocument:
    """Extract text and page labels without chunking; OCR is not performed."""
    file = Path(path).expanduser().resolve()
    readers = {".pdf": PDFReader, ".docx": DocxReader}
    reader = readers.get(file.suffix.lower())
    if reader is None:
        raise ValueError("Supported document formats are .pdf and .docx")
    if not file.is_file():
        raise FileNotFoundError(file)

    sections: list[DocumentSection] = []
    for document in reader().load_data(file=file):
        if not document.text or not document.text.strip():
            continue
        page_label = document.metadata.get("page_label")
        sections.append(
            DocumentSection(
                text=document.text,
                page_label=str(page_label) if page_label is not None else None,
            )
        )
    return RAGLoadedDocument(source_id=str(file), sections=sections)


def chunk_document(document: RAGLoadedDocument) -> RAGChunkAndSrc:
    """Split each extracted section into token-sized chunks with provenance."""
    chunks: list[DocumentChunk] = []
    for section in document.sections:
        for text in splitter.split_text(section.text):
            if not text.strip():
                continue
            chunks.append(
                DocumentChunk(
                    text=text,
                    source=document.source_id,
                    chunk_index=len(chunks),
                    page_label=section.page_label,
                )
            )
    return RAGChunkAndSrc(chunks=chunks, source_id=document.source_id)


def load_and_chunk_document(path: str | Path) -> RAGChunkAndSrc:
    """Convenience helper for loading and chunking outside an Inngest run."""
    return chunk_document(load_document(path))


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed pre-split text in input order, validating the API response.

    Requires OPENAI_API_KEY and makes billable requests for non-empty input.
    Blank text is rejected; an empty list returns without creating a client.
    """
    if not texts:
        return []
    if any(not text.strip() for text in texts):
        raise ValueError("Embedding inputs must contain non-empty text")

    vectors: list[list[float]] = []
    # Create the client only when needed; loading files requires no API key.
    with OpenAI() as client:
        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[start : start + EMBED_BATCH_SIZE]
            response = client.embeddings.create(
                model=EMBED_MODEL,
                dimensions=EMBED_DIM,
                input=batch,
            )
            ordered = sorted(response.data, key=lambda item: item.index)
            if [item.index for item in ordered] != list(range(len(batch))):
                raise ValueError("Embedding response does not match the input batch")
            if any(len(item.embedding) != EMBED_DIM for item in ordered):
                raise ValueError(f"Expected {EMBED_DIM}-dimensional embeddings")
            vectors.extend(item.embedding for item in ordered)
    return vectors

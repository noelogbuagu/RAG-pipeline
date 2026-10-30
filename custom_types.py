"""Shared data contracts for document loading, storage, and RAG responses."""

from typing import Literal

import pydantic
from qdrant_client.models import ScoredPoint


class RAGDocumentInfo(pydantic.BaseModel):
    """Validated local file identity captured before extraction starts."""

    source_id: str
    file_name: str
    file_type: str
    size_bytes: int = pydantic.Field(ge=0)
    sha256: str


class DocumentSection(pydantic.BaseModel):
    """Extracted text from a PDF page or a Word document."""

    text: str
    page_label: str | None = None


class RAGLoadedDocument(pydantic.BaseModel):
    """Extraction result passed to a separate chunking step."""

    source_id: str
    sections: list[DocumentSection]


class DocumentChunk(pydantic.BaseModel):
    """A text chunk with the provenance needed to cite it later."""

    text: str = pydantic.Field(min_length=1)
    source: str = pydantic.Field(min_length=1)
    chunk_index: int = pydantic.Field(ge=0)
    page_label: str | None = None


class RAGChunkAndSrc(pydantic.BaseModel):
    """Chunks from one document; source_id is its resolved local path."""

    chunks: list[DocumentChunk]
    source_id: str = pydantic.Field(min_length=1)


class RAGIngestResult(pydantic.BaseModel):
    """Final ingestion summary, emitted only after all writes succeed."""

    status: Literal["indexed", "no_text"]
    source: str
    chunks: int = pydantic.Field(ge=0)
    indexed: bool = False
    ingested: int = pydantic.Field(default=0, ge=0)
    collection: str | None = None


class RAGUpsertResult(pydantic.BaseModel):
    """Number of points submitted successfully, including replacements."""

    ingested: int = pydantic.Field(ge=0)


class RAGSearchRequest(pydantic.BaseModel):
    """A short question and bounded number of nearest chunks to retrieve."""

    model_config = pydantic.ConfigDict(str_strip_whitespace=True)

    question: str = pydantic.Field(strict=True, min_length=1, max_length=2000)
    top_k: int = pydantic.Field(default=5, strict=True, ge=1, le=20)


class RAGSearchResult(pydantic.BaseModel):
    """Ranked hits retaining their full payloads for per-chunk citations."""

    hits: list[ScoredPoint]

    @property
    def contexts(self) -> list[str]:
        """Text-only prompt inputs; use hits when attaching citations."""
        return [
            text
            for hit in self.hits
            if isinstance(text := (hit.payload or {}).get("text"), str) and text.strip()
        ]

    @property
    def sources(self) -> list[str]:
        """Unique sources in retrieval order, for display rather than pairing."""
        return list(
            dict.fromkeys(
                source
                for hit in self.hits
                if isinstance(source := (hit.payload or {}).get("source"), str)
                and source.strip()
            )
        )


class RAGQueryResult(pydantic.BaseModel):
    """Future answer response; answer generation is not implemented yet."""

    answer: str
    sources: list[str]
    num_contexts: int = pydantic.Field(ge=0)

"""FastAPI lifecycle and the synchronous Inngest document workflow."""

import datetime
import hashlib
import json
import logging
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import inngest
import inngest.fast_api
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from inngest.experimental import ai
from pydantic import ValidationError
from qdrant_client.models import PointStruct

from answer_generator import generate_answer
from custom_types import (
    DocumentChunk,
    RAGChunkAndSrc,
    RAGDocumentInfo,
    RAGIngestResult,
    RAGLoadedDocument,
    RAGQueryResult,
    RAGSearchRequest,
    RAGSearchResult,
    RAGUpsertResult,
)
from data_loader import (
    EMBED_DIM,
    EMBED_MODEL,
    chunk_document,
    embed_texts,
    load_document,
)
from vector_db import QdrantStorage

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent / "data"
COLLECTION_NAME = "documents-openai-3-large-3072"
# Bound saved embeddings and text for this small local-demo workflow.
INGEST_BATCH_SIZE = 16
MAX_CHUNKS = 256
MAX_TEXT_STEP_BYTES = 2 * 1024 * 1024

inngest_client = inngest.Inngest(
    app_id="rag_app",
    logger=logging.getLogger("uvicorn"),
    is_production=False,
    serializer=inngest.PydanticSerializer(),
)


def _file_digest(file: Path) -> str:
    """Fingerprint file bytes without loading the entire file into memory."""
    with file.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_document(path: object) -> RAGDocumentInfo:
    """Validate event input and capture metadata visible in the first step."""
    if not isinstance(path, str) or not path.strip():
        raise inngest.NonRetriableError(
            "Event data must include a document path under data/"
        )
    file = Path(path).expanduser()
    if not file.is_absolute():
        file = DATA_DIR.parent / file
    file = file.resolve()
    if not file.is_relative_to(DATA_DIR.resolve()):
        raise inngest.NonRetriableError(
            "Document path must be inside the project's data/ folder"
        )
    if file.suffix.lower() not in {".pdf", ".docx"}:
        raise inngest.NonRetriableError("Supported document formats are .pdf and .docx")
    if not file.is_file():
        raise inngest.NonRetriableError(f"Document does not exist: {file.name}")
    return RAGDocumentInfo(
        source_id=str(file),
        file_name=file.name,
        file_type=file.suffix.lower(),
        size_bytes=file.stat().st_size,
        sha256=_file_digest(file),
    )


def extract_document(info: RAGDocumentInfo) -> RAGLoadedDocument:
    """Extract the validated version, rejecting edits during a running import."""
    file = Path(info.source_id)
    if _file_digest(file) != info.sha256:
        raise inngest.NonRetriableError("Document changed; start a new ingestion run")
    loaded = load_document(file)
    if _file_digest(file) != info.sha256:
        raise inngest.NonRetriableError(
            "Document changed during extraction; start a new run"
        )
    if len(loaded.model_dump_json().encode()) > MAX_TEXT_STEP_BYTES:
        raise inngest.NonRetriableError(
            "Document text exceeds the demo step limit; split the file"
        )
    return loaded


def prepare_chunks(loaded: RAGLoadedDocument) -> RAGChunkAndSrc:
    """Chunk extracted text and keep saved run state within demo limits."""
    result = chunk_document(loaded)
    if (
        len(result.chunks) > MAX_CHUNKS
        or len(result.model_dump_json().encode()) > MAX_TEXT_STEP_BYTES
    ):
        raise inngest.NonRetriableError(
            "Document exceeds the demo chunk limit; split the file"
        )
    return result


def prepare_collection() -> dict[str, str | int]:
    """Check credentials and collection compatibility before any paid work."""
    if not os.getenv("OPENAI_API_KEY"):
        raise inngest.NonRetriableError("Set OPENAI_API_KEY before indexing documents")
    app.state.vector_db.ensure_collection(COLLECTION_NAME, EMBED_DIM)
    return {
        "collection": COLLECTION_NAME,
        "model": EMBED_MODEL,
        "dimensions": EMBED_DIM,
    }


def store_batch(
    info: RAGDocumentInfo,
    chunks: list[DocumentChunk],
    vectors: list[list[float]],
) -> RAGUpsertResult:
    """Store a batch with versioned IDs so retried writes replace the same points."""
    if len(chunks) != len(vectors) or any(
        len(vector) != EMBED_DIM for vector in vectors
    ):
        raise ValueError("Embedding count or dimensions do not match the chunks")
    points = [
        PointStruct(
            id=str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    json.dumps(
                        [
                            info.source_id,
                            info.sha256,
                            EMBED_MODEL,
                            EMBED_DIM,
                            chunk.chunk_index,
                            chunk.text,
                        ]
                    ),
                )
            ),
            vector=vector,
            payload={
                **chunk.model_dump(exclude_none=True),
                "document_sha256": info.sha256,
                "embedding_model": EMBED_MODEL,
            },
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    return app.state.vector_db.upsert(COLLECTION_NAME, points)


def summarize_ingestion(
    source: str, chunk_count: int, ingested: int
) -> RAGIngestResult:
    """Report success only when every chunk has been stored."""
    if ingested != chunk_count:
        raise ValueError("Stored point count does not match the chunk count")
    return RAGIngestResult(
        status="indexed" if chunk_count else "no_text",
        source=source,
        chunks=chunk_count,
        ingested=ingested,
        indexed=bool(chunk_count),
        collection=COLLECTION_NAME if chunk_count else None,
    )


@inngest_client.create_function(
    fn_id="RAG: Ingest Document",
    trigger=inngest.TriggerEvent(event="rag/ingest_document"),
    output_type=RAGIngestResult,
    concurrency=[inngest.Concurrency(limit=1)],
)
def rag_ingest_document(ctx: inngest.ContextSync) -> RAGIngestResult:
    """Index a local document through visible, independently retryable stages."""
    info = ctx.step.run(
        "validate-document",
        validate_document,
        ctx.event.data.get("path"),
        output_type=RAGDocumentInfo,
    )
    loaded = ctx.step.run(
        "extract-text", extract_document, info, output_type=RAGLoadedDocument
    )
    chunked = ctx.step.run(
        "chunk-text", prepare_chunks, loaded, output_type=RAGChunkAndSrc
    )
    ingested = 0
    if chunked.chunks:
        ctx.step.run("prepare-collection", prepare_collection)
        for start in range(0, len(chunked.chunks), INGEST_BATCH_SIZE):
            batch = chunked.chunks[start : start + INGEST_BATCH_SIZE]
            batch_number = start // INGEST_BATCH_SIZE + 1
            vectors = ctx.step.run(
                f"embed-batch-{batch_number}",
                embed_texts,
                [chunk.text for chunk in batch],
                output_type=list[list[float]],
            )
            result = ctx.step.run(
                f"upsert-batch-{batch_number}",
                store_batch,
                info,
                batch,
                vectors,
                output_type=RAGUpsertResult,
            )
            ingested += result.ingested
    return ctx.step.run(
        "summarize-ingestion",
        summarize_ingestion,
        info.source_id,
        len(chunked.chunks),
        ingested,
        output_type=RAGIngestResult,
    )


def validate_query(data: dict[str, object]) -> RAGSearchRequest:
    """Check query inputs and storage compatibility before paying for embeddings."""
    try:
        query = RAGSearchRequest.model_validate(data)
    except ValidationError as exc:
        raise inngest.NonRetriableError(
            "Provide a nonblank question (up to 2000 characters) and top_k as an integer from 1 to 20"
        ) from exc
    try:
        app.state.vector_db.validate_collection(COLLECTION_NAME, EMBED_DIM)
    except ValueError as exc:
        raise inngest.NonRetriableError(str(exc)) from exc
    if not os.getenv("OPENAI_API_KEY"):
        raise inngest.NonRetriableError("Set OPENAI_API_KEY before querying documents")
    return query


def search_documents(vectors: list[list[float]], top_k: int) -> RAGSearchResult:
    """Search using one question embedding, retaining ranked payloads and scores."""
    if len(vectors) != 1 or len(vectors[0]) != EMBED_DIM:
        raise ValueError("Expected one question embedding with matching dimensions")
    return app.state.vector_db.search(COLLECTION_NAME, vectors[0], limit=top_k)


def retrieve_documents(
    ctx: inngest.ContextSync,
) -> tuple[RAGSearchRequest, RAGSearchResult]:
    """Share the same durable retrieval steps between search and written answers."""
    query = ctx.step.run(
        "validate-query", validate_query, ctx.event.data, output_type=RAGSearchRequest
    )
    vectors = ctx.step.run(
        "embed-query", embed_texts, [query.question], output_type=list[list[float]]
    )
    retrieved = ctx.step.run(
        "search-qdrant",
        search_documents,
        vectors,
        query.top_k,
        output_type=RAGSearchResult,
    )
    return query, retrieved


@inngest_client.create_function(
    fn_id="RAG: Query Documents",
    trigger=inngest.TriggerEvent(event="rag/query_documents"),
    output_type=RAGSearchResult,
    concurrency=[inngest.Concurrency(limit=1)],
)
def rag_query_documents(ctx: inngest.ContextSync) -> RAGSearchResult:
    """Retain the retrieval-only workflow for inspecting search quality."""
    _, retrieved = retrieve_documents(ctx)
    return retrieved


@inngest_client.create_function(
    fn_id="RAG: Answer Documents",
    trigger=inngest.TriggerEvent(event="rag/answer_documents"),
    output_type=RAGQueryResult,
    concurrency=[inngest.Concurrency(limit=1)],
)
def rag_answer_documents(ctx: inngest.ContextSync) -> RAGQueryResult:
    """Retrieve evidence, then generate a cited answer in its own retryable step."""
    query, retrieved = retrieve_documents(ctx)
    return ctx.step.run(
        "generate-answer",
        generate_answer,
        query.question,
        retrieved,
        output_type=RAGQueryResult,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Own one storage connection and release its lock on shutdown/reload."""
    storage = QdrantStorage(
        path=os.getenv("QDRANT_PATH") or "qdrant_storage",
        url=os.getenv("QDRANT_URL", "").strip() or None,
        api_key=os.getenv("QDRANT_API_KEY") or None,
    )

    try:
        # Fail startup if storage cannot be reached; release it on shutdown/reload.
        storage.get_collections()
        app.state.vector_db = storage
        yield
    finally:
        storage.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health/qdrant")
def qdrant_health(request: Request) -> dict[str, str | int]:
    """Report collection count, returning 503 if storage becomes unavailable."""
    try:
        collections = request.app.state.vector_db.get_collections()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Qdrant unavailable") from exc
    return {"status": "ok", "collections": len(collections.collections)}


inngest.fast_api.serve(
    app,
    inngest_client,
    functions=[rag_ingest_document, rag_query_documents, rag_answer_documents],
)

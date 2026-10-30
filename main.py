import datetime
import logging
import os
import uuid
from contextlib import asynccontextmanager

import inngest
import inngest.fast_api
from inngest.experimental import ai
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

from vector_db import QdrantStorage

load_dotenv()

inngest_client = inngest.Inngest(
    app_id="rag_app",
    logger=logging.getLogger("uvicorn"),
    is_production=False,
    serializer=inngest.PydanticSerializer(),
)


@inngest_client.create_function(
    fn_id="RAG: Ingest Document",
    trigger=inngest.TriggerEvent(event="rag/ingest_document"),
)
def rag_ingest_document(ctx: inngest.ContextSync) -> dict[str, str]:
    # Placeholder until PDF and Word (.docx) ingestion is implemented.
    return {"status": "not_implemented", "event": ctx.event.name}


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage = QdrantStorage(
        path=os.getenv("QDRANT_PATH") or "qdrant_storage",
        url=os.getenv("QDRANT_URL", "").strip() or None,
        api_key=os.getenv("QDRANT_API_KEY") or None,
    )

    try:
        # Fail startup if storage cannot be reached; release it on shutdown/reload.
        storage.client.get_collections()
        app.state.vector_db = storage
        yield
    finally:
        storage.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health/qdrant")
def qdrant_health(request: Request) -> dict[str, str | int]:
    try:
        collections = request.app.state.vector_db.client.get_collections()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Qdrant unavailable") from exc
    return {"status": "ok", "collections": len(collections.collections)}

inngest.fast_api.serve(app, inngest_client, functions=[rag_ingest_document])

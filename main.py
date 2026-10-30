import datetime
import logging
import os
import uuid

import inngest
import inngest.fast_api
from inngest.experimental import ai
from dotenv import load_dotenv
from fastapi import FastAPI

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
async def rag_ingest_document(ctx: inngest.Context) -> dict[str, str]:
    # Placeholder until PDF and Word (.docx) ingestion is implemented.
    return {"status": "not_implemented", "event": ctx.event.name}


app = FastAPI()

inngest.fast_api.serve(app, inngest_client, functions=[rag_ingest_document])

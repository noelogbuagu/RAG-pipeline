# RAG Pipeline

A retrieval-augmented generation pipeline for PDF and Word documents.
Includes a local FastAPI/Inngest setup. Document ingestion, retrieval, and
answer generation will be added next.

For the step-by-step development history and decisions, see the
[build journal](BUILD_JOURNAL.md).

## Getting started

Requires [uv](https://docs.astral.sh/uv/) and Python 3.14 or later.

```sh
uv sync
uv run uvicorn main:app --reload
```

In a second terminal, start the Inngest dev server (requires Node.js/npm):

```sh
npx --yes inngest-cli@latest dev -u http://127.0.0.1:8000/api/inngest
```

If npm's binary installer fails with `UNABLE_TO_GET_ISSUER_CERT_LOCALLY`,
download the official CLI directly. This fallback was tested on Apple Silicon
macOS with v1.49.0:

```sh
curl --fail --location https://github.com/inngest/inngest/releases/download/v1.49.0/inngest_1.49.0_darwin_arm64.tar.gz --output /tmp/rag-inngest-1.49.0.tar.gz
mkdir -p /tmp/rag-inngest-1.49.0
tar -xzf /tmp/rag-inngest-1.49.0.tar.gz -C /tmp/rag-inngest-1.49.0
/tmp/rag-inngest-1.49.0/inngest dev -u http://127.0.0.1:8000/api/inngest
```

Open http://localhost:8288 to see the `rag_app` app and `RAG: Ingest Document`
function. Trigger it with a `rag/ingest_document` event. It currently returns
`{"status":"not_implemented","event":"rag/ingest_document"}`; document
processing is not implemented yet. This shared workflow will handle PDFs and
Word `.docx` files, choosing the reader by file type before shared chunking,
embedding, and indexing steps. It replaces the earlier PDF-specific event.
FastAPI's documentation is at http://127.0.0.1:8000/docs.

The client currently uses `is_production=False` explicitly for local development.
`.env` is loaded on startup for additional settings. No Inngest keys are needed
locally. Before deployment, replace the explicit development setting with
production configuration. Stop each server with Ctrl+C.

## Project files

- `main.py`: FastAPI application and shared document ingestion placeholder.
- `pyproject.toml`: project metadata and dependencies.
- `.python-version`: Python version used by uv.
- `uv.lock`: dependency lockfile; commit updates when dependencies change.

Use `uv add <package>` to add dependencies. Keep local documents in `data/`
and credentials in `.env`; both are ignored by Git.

Local Qdrant persistence will use `qdrant_storage/`, also ignored by Git.
The folder exists; the application connection is not implemented yet.

## Dependencies

- Streamlit for the UI; FastAPI and Uvicorn for the API.
- OpenAI SDK and Boto3 for OpenAI and Amazon Bedrock access.
- Inngest for background workflows.
- LlamaIndex Core and file readers for document ingestion, including PDFs
  and Word `.docx` files. `docx2txt` supports the Word reader; legacy `.doc`
  files must first be converted to `.docx`.
- Qdrant client for vector storage and retrieval.
- python-dotenv for local environment configuration.

Only FastAPI, Inngest, and dotenv are wired into the application so far.

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
- `vector_db.py`: `QdrantStorage`, managing collections, point upserts, and search.
- `pyproject.toml`: project metadata and dependencies.
- `.python-version`: Python version used by uv.
- `uv.lock`: dependency lockfile; commit updates when dependencies change.

Use `uv add <package>` to add dependencies. Keep local documents in `data/`
and credentials in `.env`; both are ignored by Git.

## Qdrant storage

FastAPI opens one Qdrant client at startup and closes it on shutdown or reload.
By default, it persists data in `qdrant_storage/`, which is ignored by Git.
No Docker or separate Qdrant server is required for this local mode.

Check the connection at http://127.0.0.1:8000/health/qdrant. A fresh database
returns `{"status":"ok","collections":0}`. The document collection will be
created when we configure an embedding model and its vector dimensions.

Optional `.env` settings (see `.env.example`):

- `QDRANT_PATH`: local storage directory, defaulting to `qdrant_storage`.
  Relative paths resolve from the project root, regardless of the launch directory.
- `QDRANT_URL`: when set, connects to a server instead of opening local storage,
  for example `http://localhost:6333` for a future Docker setup.
- `QDRANT_API_KEY`: optional credentials for the server connection.

Restart Uvicorn after changing `.env`. Local mode requires one process owning
the storage folder: use a single Uvicorn worker and have other applications
access Qdrant through FastAPI rather than opening that folder themselves.
Changing to a server URL does not migrate existing local data.

Run connection tests with `uv run python -m unittest discover -s tests -v`.
They use temporary storage and synthetic vectors, leaving the demo database alone.

### Storage class

`QdrantStorage` uses the synchronous `QdrantClient` for a straightforward local demo.
FastAPI owns one instance at `app.state.vector_db`; reuse it instead of opening
another client on the same folder. The class exposes:

- `ensure_collection(collection_name, vector_size, distance=Distance.COSINE)`:
  creates a missing collection or checks an existing collection's dimensions and
  distance metric. Incompatible settings raise an error and preserve the data.
- `upsert(collection_name, points)`: inserts or updates a list of `PointStruct`
  objects by ID. Each point contains an embedding and optional document payload.
- `search(collection_name, vector, limit=5)`: returns scored matches with payloads.
- `close()`: releases the client, called by FastAPI during shutdown.

Call these methods directly, without `await`. Create the collection before
inserting points, using the chosen embedding model's vector size. Use unsigned
integer IDs or UUID strings for points. The class stores and queries supplied
vectors; it does not generate embeddings or parse documents.

The health endpoint and Inngest placeholder are synchronous too. FastAPI's
lifespan retains its required async context-manager interface, while opening and
closing storage synchronously. For future remote or higher-concurrency use,
revisit async clients and workload handling as described in the build journal.

## Dependencies

- Streamlit for the UI; FastAPI and Uvicorn for the API.
- OpenAI SDK and Boto3 for OpenAI and Amazon Bedrock access.
- Inngest for background workflows.
- LlamaIndex Core and file readers for document ingestion, including PDFs
  and Word `.docx` files. `docx2txt` supports the Word reader; legacy `.doc`
  files must first be converted to `.docx`.
- Qdrant client for vector storage and retrieval.
- python-dotenv for local environment configuration.

FastAPI, Inngest, dotenv, and the Qdrant connection are wired into the application.
Document extraction, embedding, and indexing remain to be implemented.

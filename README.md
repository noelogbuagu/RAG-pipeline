# RAG Pipeline

A retrieval-augmented generation pipeline for PDF and Word documents.
Includes local FastAPI/Inngest, PDF/Word loading and chunking, OpenAI embeddings,
and indexing and semantic search in persistent Qdrant storage. Answer generation
will be added next.

For the step-by-step development history and decisions, see the
[build journal](BUILD_JOURNAL.md).

The development branches form a stack: `inngest-dev-server` →
`vector-database-setup` → `loading-and-chunking`. The last branch is the starting
point for the next stage; it inherits the completed setup from the first two.

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
function. Place a document under `data/` and send a test event:

```json
{"name": "rag/ingest_document", "data": {"path": "data/example.pdf"}}
```

Use a `.docx` path for Word documents. Set `OPENAI_API_KEY` in `.env` before
indexing; nonempty documents now trigger billable OpenAI embedding requests.
Successful runs return `status: indexed`, `indexed: true`, source, chunk count,
ingested point count, and collection name. A document with no extractable text
returns `status: no_text` and skips embedding and storage.
Paths are resolved from the project root and must stay inside `data/`.
FastAPI's documentation is at http://127.0.0.1:8000/docs.

The client currently uses `is_production=False` explicitly for local development.
`.env` is loaded on startup for additional settings. No Inngest keys are needed
locally. Before deployment, replace the explicit development setting with
production configuration. Stop each server with Ctrl+C.

## Project files

- `main.py`: FastAPI application and Inngest ingestion and query workflows.
- `data_loader.py`: PDF/Word extraction, source-aware chunks, and embedding helper.
- `vector_db.py`: `QdrantStorage`, managing collections, point upserts, and search.
- `custom_types.py`: shared Pydantic models for chunks and pipeline results.
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
returns `{"status":"ok","collections":0}`. The document collection is created
by the first nonempty ingestion run with an OpenAI key configured.

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
Storage methods share a lock so health checks and Inngest worker threads can
safely use the same local client; use those methods instead of bypassing the
lock through `.client`. This still requires a single application process.

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
  objects by ID and returns `RAGUpsertResult(ingested=...)`, counting submitted
  points including replacements. Each point contains an embedding and payload.
- `search(collection_name, vector, limit=5)`: returns a `RAGSearchResult` with
  ranked scored matches in `.hits`.
- `close()`: releases the client, called by FastAPI during shutdown.
- `get_collections()`: lists collections using the same lock as writes.
- `validate_collection(collection_name, vector_size, distance=Distance.COSINE)`:
  checks an existing collection without creating or changing it during queries.

Call these methods directly, without `await`. Create the collection before
inserting points, using the chosen embedding model's vector size. Use unsigned
integer IDs or UUID strings for points. The class stores and queries supplied
vectors; it does not generate embeddings or parse documents.

Keep each chunk's text and provenance in the same point payload, for example:

```python
# embedding is the vector already generated for this specific chunk.
point = PointStruct(
    id=chunk_id,  # A unique integer or UUID, not a position reused for each file.
    vector=embedding,
    payload={"text": chunk_text, "source": document_id, "chunk_index": chunk_index},
)
storage.upsert("documents", [point])
```

`search().hits` contains ranked `ScoredPoint` objects. Each hit contains `id`, `score`,
and its original `payload`, including `text`, `source`, and any page/chunk metadata.
Keep these together when constructing the answer context. A deduplicated source
list is available through `result.sources`; `result.contexts` gives text-only
inputs. These derived properties are convenience views, not parallel lists.
The serialized result retains `hits` as its source of truth for citations.

Dimensions are configured by `ensure_collection`, not inferred by `upsert`.
The collection size, stored embeddings, and query embeddings must agree, and
document/query embeddings must use the same model and settings. `data_loader.py`
selects `text-embedding-3-large` with `EMBED_DIM = 3072`. The workflow passes that
constant to `ensure_collection` for `documents-openai-3-large-3072`. Storage tests
use synthetic vectors and do not configure the actual document collection.

## Loading and embedding

`load_and_chunk_document(path)` returns `RAGChunkAndSrc`: `.source_id` identifies
the document and `.chunks` contains `DocumentChunk` models with `.text`, `.source`,
`.chunk_index`, and optional `.page_label`. The splitter
uses a 1000-token chunk limit and 200-token overlap, within each reader document
(each PDF page is processed separately). DOCX pagination is not inferred.
Scanned PDFs without a text layer need OCR, which is not implemented.

`embed_texts(texts)` is a separate synchronous helper. It creates an OpenAI client
only when called, sends batches of up to 64 texts, requests 3072 dimensions, and
validates response indices and vector lengths so embeddings stay aligned with
their input text. It expects chunks from the loader; arbitrary long input text
must be split first. Calling it requires `OPENAI_API_KEY` in the environment or
`.env` and makes billable API requests. The Inngest workflow calls it with smaller
batches of 16 to keep each saved step output manageable.

## Inngest steps and retries

Each stage appears separately in the run details:

1. `validate-document`: checks the path, format, and existence; returns file name,
   size, resolved source, and a SHA-256 fingerprint.
2. `extract-text`: calls `load_document`, preserving PDF page labels; rejects
   a file that changed since validation.
3. `chunk-text`: calls `chunk_document`, keeping text, source, and page metadata
   together in every chunk. `load_and_chunk_document` remains a convenience
   wrapper for callers that do not need separate steps.
4. `prepare-collection`: checks for an API key and creates or validates the
   collection's 3072-dimensional cosine configuration before embedding.
5. `embed-batch-1`, `upsert-batch-1`, and subsequent numbered pairs: generate
   vectors and store the corresponding chunks in groups of up to 16.
6. `summarize-ingestion`: reports success after every batch has been written.

Helpers are passed directly to `ctx.step.run` with their arguments; lambdas are
not needed. Explicit output types restore Pydantic models when steps replay.
Inngest saves completed step results, so a failed upsert can retry without
repeating a completed embedding step. An embedding request that succeeds but
fails before its step result is saved can still be repeated. Concurrency is
limited to one executing step for this function; it does not lock an entire run.

Point IDs are deterministic UUIDs based on source path, file fingerprint, model,
dimensions, chunk index, and text. Retrying a write or importing the same version
again replaces those points. A new run still generates embeddings again. Changed
files create new versions; automatic removal of older versions is not implemented.
Failed runs can leave completed batches in storage, so indexing is not atomic
across an entire document.

This demo caps each extracted/chunked text result at 2 MiB and documents at
256 chunks to bound saved run state. Larger documents are rejected before
embedding; a later production design should store large intermediate results
outside Inngest and pass references between steps.

## Querying your documents

After successfully ingesting a document, open http://localhost:8288/functions
and invoke **RAG: Query Documents** with this event data:

```json
{"question": "What does the document say about onboarding?", "top_k": 5}
```

Alternatively, use Send Event to create an event and trigger the function:

```json
{
  "name": "rag/query_documents",
  "data": {"question": "What does the document say about onboarding?", "top_k": 5}
}
```

The synchronous function has three steps: `validate-query`, `embed-query`, and
`search-qdrant`. Validation requires a nonblank question of at most 2000
characters and an integer `top_k` from 1 to 20 (default 5). It checks the existing
collection's dimensions and distance metric, plus the presence of an OpenAI key,
before embedding. A missing collection gives an "ingest a document first" error;
queries never create one. The question uses the same embedding model and 3072
dimensions as ingestion, with one billable embedding request per new run.
A failed search can retry using the saved question embedding.

The result's `hits` contain ranked matches with `score` and `payload` (text,
source, chunk index, and PDF page label when available). No vectors are returned.
An existing empty collection returns `hits: []`. Search returns the nearest
chunks without a relevance cutoff, so a returned match is not proof that the
document answers the question. All stored versions are searchable, including
older document versions and batches from incomplete ingestion runs. This stage
retrieves passages; it does not generate an AI-written answer yet.

## Shared models

Use model attributes in Python and `.model_dump()` when a dictionary is needed,
such as a Qdrant payload. Inngest's `PydanticSerializer` and explicit `output_type`
restore the loader model when replaying a stored step. The workflow returns
`RAGIngestResult`; its JSON summary keeps the existing status/source/count fields.
`RAGQueryResult` defines the future answer shape but is not used until answer
generation is implemented.

The health endpoint and Inngest handler are synchronous too. FastAPI's
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
- Pydantic for validation and serialization of shared pipeline models.

FastAPI, Inngest, dotenv, document extraction/chunking, embeddings, Qdrant
indexing and semantic search are wired into the application.
Answer generation and the Streamlit UI remain future work.

# RAG pipeline build journal

This journal follows the construction of a RAG application for PDF and Word
documents. Each milestone explains what we built and why, so the project can
be followed as a learning exercise. The [README](README.md) contains the current
startup instructions; this file records the development story.

Entries below were backfilled on 30 October 2026 from our work and repository
history. Future entries are added with meaningful changes rather than for each
individual edit.

## 1. Connect the project to GitHub

**Date:** 30 October 2026

Created the private repository
[noelogbuagu/RAG-pipeline](https://github.com/noelogbuagu/RAG-pipeline) and linked
the local project to it as the Git remote `origin`. The folder already had Git
initialized with a `main` branch and no commits.

This gives us versioned checkpoints and a remote copy of the project. The
initial setup was later committed and pushed to `main` as `8f87b3f`. We then
created `codex/inngest-dev-server` for the next stage of development.

## 2. Initialize the Python project with uv

**Date:** 30 October 2026 · **Checkpoint:** `8f87b3f`

Ran `uv init .` to create the application skeleton. uv selected Python 3.14;
the initial environment used CPython 3.14.2. The project files serve these roles:

- `pyproject.toml` defines project metadata and dependency requirements.
- `.python-version` records the Python version for uv.
- `uv.lock` records resolved dependency versions for repeatable installation.
- `main.py` is the application entry point.
- `README.md` describes the project and how to start it.

Ran `uv sync` to create `.venv` and verified the generated greeting with
`uv run main.py`. That greeting was subsequently replaced by the server setup.

Added `.gitignore` rules for the environment, Python caches, build outputs,
`.env` credentials, and local documents under `data/`. `.env.example` is allowed
in Git so configuration can be documented without committing actual secrets.

## 3. Install the pipeline dependencies

**Date:** 30 October 2026 · **Checkpoint:** `8f87b3f`

Installed the following with `uv add`, updating both project metadata and the
lockfile:

| Packages | Intended role |
| --- | --- |
| `streamlit` | Document upload and question-answering interface |
| `fastapi`, `uvicorn` | HTTP application and local server |
| `inngest` | Background workflow execution |
| `openai`, `boto3` | Access to OpenAI and Amazon Bedrock |
| `llama-index-core`, `llama-index-readers-file` | Document loading and RAG building blocks |
| `docx2txt` | Word `.docx` text extraction for the LlamaIndex reader |
| `qdrant-client` | Access to the vector database |
| `python-dotenv` | Load local settings from `.env` |

Verified package imports, instantiated the PDF and Word readers, and checked
that Boto3 exposes Bedrock Runtime. `uv pip check` reported compatible installed
dependencies. These checks did not make external model calls or validate
extraction from real documents. Legacy Word `.doc` files need conversion to
`.docx` for the selected Word reader.

## 4. Connect FastAPI to the Inngest dev server

**Date:** 30 October 2026 · **Checkpoint:** `04fad96`

Initially created a small FastAPI application in `app.py` with a
`dev-smoke-test` function listening for `rag/dev.test`. This let us check the
connection independently of document processing while the user edited
`main.py`.

There are two separate processes:

- Uvicorn serves our Python application on port 8000. The Inngest SDK exposes
  `/api/inngest` so the dev server can discover and execute our functions.
- The Inngest dev server runs on port 8288 and provides the dashboard, event
  handling, and workflow execution coordination.

The npm CLI installer failed while verifying the certificate for its GitHub
binary download. Downloading the official v1.49.0 Apple Silicon macOS release
with curl worked; the README records the fallback commands.

Verified the SDK endpoint, successful app synchronization, and a complete
`rag/dev.test` workflow run. That test event explains the early event visible
in the dashboard; it is not a document-ingestion event.

## 5. Make main.py the application entry point

**Date:** 30 October 2026 · **Checkpoint:** `04fad96`

Built on the user's Inngest client configuration in `main.py`:

- `load_dotenv()` loads local environment settings before client creation.
- `app_id="rag_app"` identifies this application to Inngest.
- The Uvicorn logger is passed through `logger=`.
- `is_production=False` explicitly selects local development mode.
- `PydanticSerializer()` configures serialization of workflow outputs.
- `inngest.fast_api.serve(...)` registers the workflow with FastAPI.

Added the missing workflow handler and registered it. Removed the temporary
`app.py` after consolidating the setup into `main.py`. Preserved the user's
imports for future work, including `ai`, `uuid`, `os`, and `datetime`.

The startup command is now `uv run uvicorn main:app --reload`. Automatic reload
restarts the application after saved Python changes. We encountered a port
8000 conflict when starting a second instance; stopping the existing instance
resolved it. Only one server should use that address at a time.

Verified FastAPI startup, its documentation endpoint, Inngest registration, and
the placeholder handler response. Production configuration remains future work.

Vim created `.main.py.swp` while editing. This is an editor recovery file, not
application code; `*.swp` is ignored by Git.

## 6. Use one ingestion workflow for PDF and Word

**Date:** 30 October 2026 · **Checkpoint:** `04fad96`

Generalized the PDF-specific placeholder into `rag_ingest_document`, displayed
as `RAG: Ingest Document`, with the event trigger `rag/ingest_document`.

The intended flow is:

```text
Document upload → rag/ingest_document event → select PDF or DOCX reader
                → extract text → chunk → embed → store in Qdrant
```

Both file types can share the workflow because, after extraction, they use the
same text-processing and indexing stages. Separate functions can be introduced
if their processing requirements later diverge.

The current handler returns `status: not_implemented` and the incoming event
name. It does not read files, generate embeddings, or write to Qdrant. Verified
that the shared function registers and returns that explicit placeholder result.

The dashboard's **Invoke Function** action starts a specific function directly.
To test the event trigger, send this through **Test Event**:

```json
{"name": "rag/ingest_document", "data": {}}
```

The trigger declaration listens for an event; it does not publish one. The
upload flow will eventually publish the event with document details.

Committed the completed development setup as `04fad96` on
`codex/inngest-dev-server`. At this checkpoint it had not been pushed.

## 7. Establish ongoing build documentation

**Date:** 30 October 2026

Created this journal and linked it from the README. Added `AGENTS.md` guidance
to update the journal during meaningful changes and check coverage before
requested commits. Entries explain features, decisions, checks, and limitations
at the milestone level.

This is an agent-maintained workflow, not a background file watcher or Git hook.
Manual edits are documented when Codex next reviews them. The next planned
stage is Qdrant setup: only its Python client is installed so far; a database,
collection, and application connection have not yet been configured.

## 8. Plan for the company laptop and personal laptop

**Date:** 30 October 2026 · **Status:** Decision agreed; application integration pending

The first version is for a team development day on a company laptop, where
installing desktop applications such as Docker Desktop is restricted. The owner
also wants to continue the same GitHub project on a personal laptop with more
freedom to install tools and explore a production deployment.

We chose persistent Qdrant local mode for the initial demo. It runs through the
already installed `qdrant-client` package without Docker or a separate database
server. The initially proposed storage path was `data/qdrant`; milestone 9
records the decision to use the owner's `qdrant_storage/` folder instead.
This choice avoids an installation dependency while keeping Qdrant as the
database technology. Switching to Supabase is unnecessary for this constraint.

Verified local mode in a temporary directory: created a collection, inserted a
synthetic vector, closed and reopened the client, and retrieved the vector by
similarity search. The temporary data was removed after the check. This proves
local storage and retrieval work in the current environment; the application
has not yet been connected to Qdrant and real document ingestion is still pending.

For the local version, plan to keep database access in the FastAPI process and
have Streamlit call the API. Local mode is for a small prototype and does not
provide the separate Qdrant server dashboard. When implementing the connection,
keep the local storage path and future server URL configurable so the workflow
code can be reused on either laptop.

### Continuing on the personal laptop

1. Commit and push the latest code and documentation, then clone the repository
   on the personal laptop and check out the working branch.
2. Run `uv sync` to recreate the Python environment. Create a local `.env` from
   `.env.example` and supply credentials appropriate to that environment.
3. Install Docker Desktop if desired and run Qdrant as a server with persistent
   storage. Change the application connection from a local path to the server
   URL once that configuration is implemented.
4. Re-ingest permitted sample documents or explicitly migrate the stored points
   into the server. Changing the client URL does not transfer the local vectors.
   Neither `.env` nor `data/` travels with a Git clone; the Python client's local
   storage folder should not be treated as a Qdrant server storage volume.
5. Treat Docker as a development/deployment tool, not proof of production
   readiness. A production milestone still needs authentication, network access
   controls, backups, monitoring, and production Inngest configuration.

Use synthetic or public documents on the personal laptop unless company policy
permits transferring the relevant data and credentials. Future journal entries
should explain similar environment-driven choices and the steps to revisit
them, so the demo constraints remain visible when development moves machines.

## 9. Choose the local storage folder

**Date:** 30 October 2026 · **Status:** Folder chosen; connection pending

The owner created `qdrant_storage/` in the project root. We will use that folder
for persistent local Qdrant data instead of the earlier proposed `data/qdrant`.
In local mode this is an ordinary directory managed by the Python client, not
a Docker volume. A client initialized with `QdrantClient(path="qdrant_storage")`
from the project root will store vectors and their associated payloads there
and reopen them on subsequent runs. Source PDFs and Word files can stay in
`data/`; Qdrant stores the indexed information we explicitly write to it.

Added `qdrant_storage/` to `.gitignore` and noted the choice in the README.
The directory is currently empty and the application has not yet created a
Qdrant client. Checked that Git ignores this storage path.

When moving to Docker, use a separate server storage directory or named volume,
then re-ingest documents or migrate points explicitly. The embedded client's
files are not the Qdrant server's storage format. This ignored directory will
not be included in a Git clone on the personal laptop.

## 10. Connect the application to persistent Qdrant storage

**Date:** 30 October 2026 · **Status:** Connection implemented and verified

Added an asynchronous Qdrant client to FastAPI's lifespan in `main.py`.
Startup creates the client and checks access by listing collections. Shutdown
closes it, releasing the local storage lock so automatic reload can reopen the
database. This keeps one client per application process rather than creating a
new connection for each workflow invocation. The client is available as
`app.state.qdrant` for future ingestion and retrieval code.

Local mode uses `qdrant_storage/` by default. `QDRANT_PATH` can override this;
relative paths are anchored to the project root. Setting `QDRANT_URL` selects
server mode instead, with an optional `QDRANT_API_KEY`. These settings are
documented in `.env.example`; existing personal `.env` values were not changed.
The user's reserved imports remain in place.

Added `GET /health/qdrant` to check connectivity and report the collection count.
An unavailable database causes startup to fail; a connection failure after
startup returns HTTP 503 from the health endpoint without exposing error details.

Added three standard-library unittest cases in `tests/test_qdrant_connection.py`.
They verify synthetic vector persistence and search across application restarts,
storage-lock release, health and Inngest endpoints, server configuration selection,
and client cleanup after failed startup. All three passed. The server-mode test
uses a mock; an actual Docker or cloud Qdrant connection has not been tested.

The running FastAPI server reloaded successfully and its health endpoint returned
`{"status":"ok","collections":0}` using local storage. No new dependencies were
needed. No document collection has been created: we still need to choose the
embedding model and vector dimensions before implementing indexing. The
document-ingestion function remains an explicit placeholder.

For this embedded setup, run one Uvicorn worker and keep direct database access
within FastAPI. Restart after `.env` changes; Python code reload does not reliably
reload environment-file changes. The README includes configuration and test commands.

## 11. Extract the QdrantStorage class

**Date:** 30 October 2026 · **Status:** Implemented and tested

Created `vector_db.py` with `QdrantStorage`. It imports Qdrant's models,
`VectorParams`, `Distance`, and `PointStruct`, and uses `AsyncQdrantClient` so
storage operations fit the existing async application. Its constructor opens
persistent local storage at `qdrant_storage/` by default, anchoring relative paths
to the project root. The optional server URL and API-key support from milestone
10 remains available for the later personal-laptop setup; Docker is not required.

The class can create or validate a collection, upsert points by ID, search for
similar vectors with their payloads, and close the connection. Collection setup
requires an explicit vector size; cosine distance is the default. Reopening a
compatible collection preserves its points. A size or distance mismatch raises
an error rather than recreating the collection and losing data.

FastAPI now creates this class in its lifespan and exposes it at
`app.state.vector_db`, replacing the direct client at `app.state.qdrant` from
milestone 10. The health check uses the same instance. No client is created at
module import, and the user's reserved imports were preserved.

All five tests passed: the existing application connection checks plus storage
tests for point replacement, nearest-vector search and payload retrieval,
persistence across reopen, and data preservation after incompatible collection
requests. Tests use temporary directories and synthetic vectors. The application
still has no document collection or real embeddings; parsing, model selection,
and integration of storage methods into the ingestion workflow remain next steps.

## 12. Simplify the demo to synchronous database calls

**Date:** 30 October 2026 · **Status:** Implemented and tested

The owner chose synchronous code for the learning-focused team demo. Replaced
`AsyncQdrantClient` with `QdrantClient` in `vector_db.py` and converted collection
setup, upsert, search, and close into ordinary methods called without `await`.
Local persistence, optional server configuration, and collection compatibility
checks remain unchanged. This supersedes the async approach in milestones 10
and 11; existing data does not need migration for this client change.

Converted the health endpoint to a regular `def`, which FastAPI runs in its
worker thread pool. Converted the ingestion placeholder to a regular function
with `inngest.ContextSync`. FastAPI's lifespan still uses `asynccontextmanager`
because that is its framework interface; its database calls are synchronous.
Preserved the owner's imports for future work.

Converted the tests to synchronous unittest cases and FastAPI TestClient. All
six passed, covering persistence, search, collection safety, server configuration,
failure cleanup, and synchronous Inngest handler registration and output.
The run emitted a ResourceWarning from the installed Qdrant client's temporary
SQLite thread-safety probe: its context manager does not explicitly close that
probe connection. Application clients are explicitly closed, and the storage
reopen tests passed. No dependency code was patched or warning suppressed.

### Revisit on the personal laptop

Synchronous calls are appropriate for this small demo but block their calling
thread until complete. Docker alone does not require an async client. If remote
database latency or concurrent requests become important, evaluate
`AsyncQdrantClient` together with async workflow handlers, or deliberately run
blocking work in workers. Embedded local operations do not automatically become
faster just by adding `async` and `await`.

Before expanding ingestion concurrency, assess shared-client access and SQLite
thread affinity on the target machine; a single Uvicorn worker can still run
multiple handler threads. A Qdrant server is the intended next step for shared
or concurrent database use. Keep these choices separate from Docker installation
and from the broader production-readiness work documented in milestone 8.

## 13. Preserve context and source together during retrieval

**Date:** 30 October 2026 · **Status:** Search correction implemented and tested

Reviewed the owner's search edits, which attempted to build separate context
and unique-source lists. That representation loses the relationship between a
specific chunk and its source, particularly when several chunks share a file.
The edited loop also iterated the query response rather than its `.points`.

Kept the storage method's `list[models.ScoredPoint]` contract and corrected it to
return `results.points`. Each ranked hit retains its ID, score, and complete
payload, so text, source, page, and chunk metadata remain together. Source
deduplication belongs in a later display step; it should not discard the mapping
needed for citations. Missing source metadata remains missing rather than being
assigned another chunk's source.

The upsert method already accepts complete `PointStruct` objects. Each point
must pair an embedding with the text it represents and that text's provenance.
Use chunk IDs unique within the collection; restarting integer IDs at zero for
every document would overwrite earlier points. Parallel lists are unnecessary
at this storage boundary; build one point per chunk before upserting.

Clarified that local mode needs no URL; the optional URL selects a future server.
Dimensions remain explicit in `ensure_collection`. We have not selected an
embedding model or set 3072 as a default. OpenAI documents default output sizes
of 3072 for `text-embedding-3-large` and 1536 for `text-embedding-3-small`, with
configurable shortening for these models. A future model choice must set the
collection size accordingly and use the same model/settings for document and
query embeddings. See the [official embedding guide](https://developers.openai.com/api/docs/guides/embeddings).

Added a regression test using multiple PDF/Word chunks, repeated source names,
page/chunk metadata, and a point with no source. All seven tests passed; ranking
and each point's original payload are preserved. The previously documented
upstream SQLite probe warning still appeared. Real embedding generation and
answer-context formatting have not been implemented.

## 14. Separate the development stages into stacked branches

**Date:** 30 October 2026

Organized the work into descriptive branch names without the `codex/` prefix:

| Branch | Base and scope |
| --- | --- |
| `inngest-dev-server` | Ends at `04fad96`, containing the FastAPI/Inngest setup on top of the initial project on `main`. |
| `vector-database-setup` | Continues from Inngest with the journal, storage decisions, synchronous Qdrant class, tests, and context/source retrieval correction. |
| `loading-and-chunking` | Starts at the completed vector setup and is the working branch for the next stage. |

Preserved existing commits and included the pending retrieval improvements in
the vector stage. The former `codex/inngest-dev-server` branch mixed both stages;
its history is retained through `vector-database-setup`. The replacement branches
are published before removing the old remote branch. No open pull requests
needed retargeting. `main` remains at the initial project setup.

These are stacked branches: vector setup includes the Inngest commits, and
loading/chunking includes both earlier stages. Loading and chunking has not yet
been implemented. Earlier journal entries retain the old branch names where
they describe historical actions.

## 15. Review and connect document loading and chunking

**Date:** 30 October 2026 · **Status:** Loading/chunking implemented; embedding helper tested without live API calls

Reviewed the owner's new `data_loader.py` alongside `vector_db.py` and `main.py`.
Fixed syntax, the PDF reader keyword, the embedding model identifier, and the
embedding function's placement. Retained the intended synchronous approach.
The existing vector database module already fits the required storage interface
and needed no changes in this stage.

Generalized `load_and_chunk_pdf` to `load_and_chunk_document` so the same workflow
supports PDF and Word `.docx`. Each chunk carries its text, resolved source path,
and document-wide chunk index; PDF page labels are preserved when available.
Empty text is skipped. SentenceSplitter's 1000/200 settings measure tokens, not
characters. Splitting occurs within each reader document, so PDF pages remain
separate and overlap does not cross page boundaries. OCR and legacy `.doc`
conversion are not implemented.

The owner's model choice is now `text-embedding-3-large`, with `EMBED_DIM = 3072`.
`embed_texts` requests this dimension explicitly, batches loader chunks in groups
of 64, restores input order using response indices, and validates counts and
dimensions. Empty input makes no request; blank text is rejected. Client creation
is deferred until embedding is requested, so loading files and starting FastAPI
do not require an OpenAI key. No live embedding request was made during this work.

Connected the synchronous Inngest handler to a `load-and-chunk` step. Events now
need `data.path`, such as `data/example.pdf`. The handler resolves paths and
restricts them to the project's `data/` directory, including resolving symlinks
before checking the boundary. It reports `chunked` or `no_text`, the source,
chunk count, and `indexed: false`. It does not claim that vectors were stored.

All 11 tests passed. Generated PDF and DOCX fixtures verify actual extraction,
token-sized splitting, and provenance. Mocked OpenAI responses verify batching,
ordering, invalid responses, and dimensions. Handler tests check the loading
step and path boundary; the existing Qdrant suite remains green. The embedding
API and an actual Inngest document run were not exercised. Future indexing must
use `EMBED_DIM` when creating the collection and pair vectors with chunk payloads.

Updated README and `.env.example`. An empty `custom_types.py` appeared during
the review and was left untouched for the owner's ongoing work.

## 16. Apply shared models and clean up the Python modules

**Date:** 30 October 2026 · **Status:** Implemented and tested

Reviewed the owner's populated `custom_types.py` and corrected the Pydantic
base-class spelling and inconsistent optional source annotation. Source IDs are
required for loader results. Added field constraints for nonnegative counts and
chunk indices. Pydantic is now a direct project dependency rather than only a
transitive dependency.

Moved the chunk contract into `custom_types.py` as a `DocumentChunk` model.
`load_and_chunk_document` now returns `RAGChunkAndSrc`, containing typed chunks
and the document source ID. The Inngest step declares this `output_type`, allowing
its existing Pydantic serializer to restore models on replay. The workflow
returns `RAGIngestResult`, while retaining the previous JSON summary fields and
explicit `indexed: false` behavior.

Applied `RAGUpsertResult` to the storage write method: `ingested` counts submitted
points after a successful call, including replacements; it is not a count of
new documents. Empty writes report zero. Applied `RAGSearchResult` to search:
its `.hits` remain the authoritative ranked points with complete payloads.
`.contexts` and `.sources` are derived Python properties for convenience; sources
are deduplicated in first-hit order and must not be zipped with the contexts.
Serialization preserves hits, so the text/source/page associations survive.
`RAGQueryResult` is corrected and documented for the later answer-generation stage.

Added module, model, and function docstrings; organized imports and formatting
with Ruff; named the embedding batch-size constant. Preserved imports the owner
reserved for future work. No new framework or abstraction layer was introduced.

Updated all current callers and tests for model attributes and `.hits` access.
All 14 tests passed, including model JSON round trips, Inngest serializer replay,
source-preserving search views, write counts/error propagation, actual PDF/DOCX
extraction, and existing storage checks. Embedding calls remain mocked; no live
model API request or answer-generation implementation was added. README documents
the new contracts and dictionary conversion with `.model_dump()`.

## 17. Make ingestion observable through durable steps

**Date:** 30 October 2026 · **Status:** Implemented; tested with mocked embeddings

Expanded `rag_ingest_document` into separate named steps so the development
dashboard shows what is happening and which stage failed. `validate-document`
checks the event path and file format, then returns the source, file name, size,
and SHA-256 fingerprint. `extract-text` calls `load_document`; `chunk-text` calls
`chunk_document`. New shared models (`RAGDocumentInfo`, `DocumentSection`, and
`RAGLoadedDocument`) carry these intermediate results. Kept the existing
`load_and_chunk_document` wrapper for simple callers. Extraction verifies the
fingerprint before and after reading, preventing a changed file from silently
being indexed under an earlier version's identity.

Connected the existing embedding and storage helpers to the workflow.
`prepare-collection` checks that an OpenAI key exists and creates or validates
the `documents-openai-3-large-3072` collection with 3072 dimensions and cosine
distance. Numbered `embed-batch-N` and `upsert-batch-N` steps process up to 16
chunks per batch, keeping vectors paired with their original chunk payloads.
`summarize-ingestion` reports `indexed`, source, chunk count, ingested count,
and collection only after all writes succeed. Empty documents return `no_text`
without creating a collection or requesting embeddings. Real nonempty runs now
require an OpenAI key and incur embedding API charges.

Passed helpers and positional arguments directly to `ctx.step.run`; lambdas add
no value here. Explicit output types and the Pydantic serializer restore models
when successful steps replay. Separating embedding from upserting lets a failed
write reuse the completed embedding step. This is not an exactly-once guarantee
for the external API: a request can succeed before its step output is saved,
and a retry in that interval can repeat it.

Used deterministic UUID point IDs incorporating source, file fingerprint,
embedding configuration, chunk index, and text. Repeated writes for the same
version replace the same points. A separate ingestion run still regenerates
embeddings; there is no cross-run embedding cache. Changed files produce new
versions, and automatic removal of old versions remains future work. An ingestion
failure may leave earlier batches stored; whole-document publication is not atomic.

Added conservative demo limits of 256 chunks and 2 MiB per extracted/chunked text
result to bound saved run state. Larger inputs fail before embedding. For a
production design, store large intermediates externally and pass references.
Inngest concurrency is limited to one executing step, not one entire run. The
synchronous Qdrant wrapper now serializes its methods with a lock and permits
SQLite access across worker threads, since FastAPI health checks and Inngest
steps may use different threads. Call wrapper methods rather than bypassing the
lock through `.client`; local storage still requires one application process.

All 21 tests passed. Tests cover named steps and serialized replay, unchanged-file
reimports, a lost write acknowledgement followed by retry without re-embedding,
source/page associations, empty input, invalid and symlinked paths, edited files,
state limits, missing credentials, incompatible collection settings, and worker
thread access. Existing real PDF/DOCX extraction and temporary storage tests also
pass. OpenAI responses were mocked; no live paid embedding request was made.
Updated README and `.env.example` to describe the now-connected indexing workflow.
Ruff checks (excluding intentionally reserved imports) and `git diff --check`
passed. The running FastAPI server reloaded successfully; its Qdrant health
endpoint returned `status: ok` with zero collections in the untouched demo store.

Reference: Inngest's [Python step.run documentation](https://www.inngest.com/docs/reference/python/steps/run),
[step limits and retry behavior](https://www.inngest.com/docs/durable-execution/primitives/step-run),
and [step concurrency](https://www.inngest.com/docs/functions/concurrency).

## 18. Query indexed documents from the Inngest dashboard

**Date:** 30 October 2026 · **Status:** Implemented; tested with mocked query embeddings

The storage class already supported vector search, but there was no workflow to
turn a question into a query vector. Added synchronous `rag_query_documents` in
`main.py`, registered as **RAG: Query Documents**, triggered by
`rag/query_documents`. Event data contains `question` and optional `top_k`.
The tutorial screenshot shows ingestion; this new function handles retrieval.

Added three visible steps: `validate-query`, `embed-query`, and `search-qdrant`.
`RAGSearchRequest` trims surrounding whitespace, requires a nonblank question of
at most 2000 characters, and accepts a strict integer limit from 1 to 20 (default
5). Validation checks collection settings and API-key presence before embedding.
The shared embedding helper uses the same model and 3072 dimensions as ingestion.
Successful embedding outputs can replay when a subsequent search retries.

Reused `QdrantStorage.search` and `RAGSearchResult`, preserving ranked hits, scores,
and each chunk's source/page payload. Added a read-only `validate_collection`
method and reused its compatibility check in `ensure_collection`. Queries never
create or recreate collections: missing storage reports that a document must be
ingested first. An existing empty collection returns an empty hit list.

All 26 tests passed, including real temporary Qdrant retrieval with mocked
embeddings, top-k ranking and provenance, serialized step replay, search retries
without re-embedding, invalid input, missing/incompatible collections, and missing
credentials. Ruff checks excluding intentionally reserved imports passed. No live
OpenAI calls were made; semantic relevance of real model embeddings was not tested.
README includes both dashboard invocation data and a complete event example;
`.env.example` now notes that queries also require an embedding API key.

This is retrieval only; `RAGQueryResult` remains reserved for future generated
answers. A new query run incurs an embedding request. There is no relevance
threshold or filtering of older document versions or partially ingested batches,
so nearest matches require inspection and are not proof of an answer.

## 19. Add the Streamlit upload and search interface

**Date:** 30 October 2026 · **Status:** Implemented; UI tested with mocked event transport

Adapted the owner's example into `streamlit_app.py`. It supports PDF and Word
`.docx` and uses the existing `rag/ingest_document` event with `path`, plus
`rag/query_documents` with `question` and `top_k`. Reused `RAGSearchRequest`,
`RAGIngestResult`, and `RAGSearchResult` to validate inputs and run outputs.
The UI displays retrieved passages, similarity scores, sources, chunk indices,
and PDF page labels instead of expecting an answer field the backend does not
produce yet. Uploaded text is rendered as text, not interpreted HTML/Markdown.

Kept the interface synchronous using Inngest's `send_sync`, removing the need
for `asyncio.run`. Standard-library HTTP requests read the run-status API, so
no new dependency was needed. One `INNGEST_DEV_SERVER_URL` setting controls both
event submission and status polling, avoiding mismatched server addresses.
Streamlit does not import the FastAPI application or open local Qdrant storage;
FastAPI remains its sole owning process. The processes share the project folder.

Uploads go to Git-ignored `data/uploads/<content-hash>/<sanitized-name>` so they
pass the backend path boundary. Filenames are stripped of path components,
empty files and uploads over 20 MiB are rejected, and file writes are atomic.
Identical contents and filename retain a stable path; changed contents use a
different directory rather than overwriting an input being processed. Files are
not automatically deleted. A copy previously ingested from another path remains
a different source and may yield duplicate passages; older-version cleanup is
still future work. Backend text/chunk limits also continue to apply.

Forms submit only on explicit clicks, avoiding ingestion on every Streamlit
rerun. Session state preserves event IDs and results while interacting with
widgets. Fragments check run status every two seconds without a sleep loop;
HTTP requests time out after five seconds. After two minutes or a polling error,
checks pause and a button resumes checking the same event. This does not cancel
or resend the workflow. Failed/cancelled runs point users to the dashboard.
The UI tracks the latest submission of each kind per browser session; a new
submission replaces that display, and a browser reload loses session tracking.
The underlying events/runs remain in Inngest.

All 33 tests passed. Added upload-path/content checks, synchronous event payload
checks, HTTP response and timeout handling, and Streamlit AppTest coverage for
upload completion, retrieved passages, blank questions, failure states, paused
polling, retained results, and avoiding automatic resubmission on rerun. Event
transport and run responses were mocked; no live workflow or OpenAI request was
triggered. Ruff and whitespace checks passed. The app has not been launched as a
separate server in this task; README documents the third-terminal startup command.

Updated README and `.env.example`. Implementation references:
[Inngest run-status/output API](https://www.inngest.com/docs/examples/fetch-run-status-and-output)
and [Streamlit fragments](https://docs.streamlit.io/develop/concepts/architecture/fragments).

## 20. Apply the installed Streamlit development skill

**Date:** 30 October 2026 · **Status:** Implemented and tested

Used the owner's newly installed `developing-with-streamlit` skill, its best
practices, layout, performance, state, and testing references, and the installed
Streamlit CLI's API documentation to improve the existing interface.

Grouped headings inside their forms and added primary full-width submit buttons
with Material icons, stable widget keys, and question guidance. Both forms now
render before file/network work, keeping search controls available during slow
requests. Enforced the 20 MiB limit in the uploader itself as well as the save
helper. Upload validation and filesystem errors now have specific feedback,
separate from event-delivery errors.

The run fragment now receives a timer only while waiting. When a run completes,
fails, or pauses, a full rerun removes its periodic refresh; results remain
visible without repeated redraws. The resume button performs a full rerun to
register the timer again, avoiding a fragment-only rerun request when the
fragment is executing as part of a full app run. Added a regression test that
resumes the same paused event through completion without sending another event.

Moved event IDs into a Run details expander. Retrieval now summarizes passage
and source counts, explains that similarity is not a confidence percentage,
and initially expands only the first match. Native widgets handle all styling;
no CSS, new dependencies, or theme overrides were added. Kept the project's
existing `.env` configuration and testable `main()` entry point. Initialized
per-session run keys together and bounded the cached client to one entry.

All 35 tests passed, including updated AppTest coverage for timer shutdown,
resume behavior, specific empty-upload feedback, the uploader limit, and retained
results. Ruff and whitespace checks passed. Tests mocked transport and embeddings;
no live document or paid API request was submitted. Found the existing Streamlit
server listening on `127.0.0.1:8501` (PID 32584); no new server was started.

## 21. Commit the backend and separate the Streamlit stage

**Date:** 30 October 2026

Committed the completed loading, ingestion, shared-model, and retrieval work on
`loading-and-chunking` as `5ac2745`. Created `streamlit-ui` directly above it for
the interface, UI tests, installed Streamlit skill links, and corresponding
documentation. Split the README, environment example, and journal at the same
boundary so the backend branch does not describe an interface it does not have.
There were no existing Streamlit commits to move; the changes were uncommitted,
so no published history was rewritten. Both stages were tested in the 35-test
suite before this separation. Local PDFs, Qdrant data, and `.env` remain ignored.
The installed skill entries are relative symlinks into the uv environment and
require `uv sync` on a new checkout. Answer generation will continue on a new
`answer-generation` branch based on `streamlit-ui`.

## 22. Generate written answers with passage references

**Date:** 30 October 2026 · **Status:** Implemented; automated tests use mocked APIs

Published backend commit `5ac2745` on `loading-and-chunking` and Streamlit commit
`50b4d27` on `streamlit-ui`. Continued development on `answer-generation`, based
on the Streamlit branch, without rewriting existing history.

Added `answer_generator.py` and the synchronous **RAG: Answer Documents** workflow,
triggered by `rag/answer_documents`. The original retrieval-only event remains
available. Both workflows use the same validation, question embedding, and Qdrant
search steps. The answer workflow adds `generate-answer`, a separately saved and
retryable step, so generation failures do not repeat successful retrieval.

The helper calls the OpenAI Responses API with default model `gpt-5.4-mini`,
configurable through `OPENAI_ANSWER_MODEL`. No new dependency was needed. The
existing OpenAI key is reused, with a 45-second request timeout, SDK retries
disabled in favor of Inngest retries, `store=False`, and a 2,048-token output
limit. Changing the answer model does not affect stored embeddings.

Passages need nonblank text and source metadata. Total passage text is capped at
60,000 characters; oversized passages are skipped and included ones renumbered.
An empty usable context produces a fixed explanation without a generation call.
The prompt treats retrieved text as untrusted evidence, asks for plain-language
answers grounded only in those passages, preserves uncertainty, and requests
numbered references. Incomplete/empty responses and invalid numeric citation
indices fail instead of publishing a partial or unmappable answer. These are
structural checks, not factual verification or a guarantee against prompt injection.

Activated `RAGQueryResult` with answer, unique context sources, context count,
and ordered hits. Reference `[N]` maps to hit N, retaining its source/page payload.
Sources represent all supplied context, which may include uncited passages.
Streamlit now sends the answer event and shows an Answer section above Supporting
passages. Model text is rendered as text, avoiding model-generated HTML or remote
image rendering. Earlier retrieval-only results in browser session state remain
displayable. No chat history or streaming implementation was added.

All 41 tests passed. New tests verify prompt/data separation, citation mapping,
context budgeting, empty-input behavior, model configuration, response validation,
and generation retries with saved retrieval. Updated AppTest coverage checks the
answer event, written text, supporting passages, and retention across reruns.
OpenAI calls remain mocked; no live generation request or paid model-quality
evaluation was performed. Ruff and whitespace checks passed. README and environment
examples document usage, API charges, configuration, and remaining retrieval limits.

References: [Responses API](https://developers.openai.com/api/reference/python/resources/responses)
and [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini).

## 23. Preserve answer passages across Streamlit reloads

**Date:** 30 October 2026 · **Status:** Fixed and regression-tested

Investigated the reported `RAGSearchResult.hits` validation error when displaying
an answer containing only answer text, source names, and a context count.
An AppTest with an older imported answer model reproduced the exact traceback:
validation accepted the newer payload, but `.model_dump()` silently discarded
the newer `hits` field before saving it in session state. This explains how a
long-lived Streamlit process can lose passages after a code/model update even
when the backend supplies them. A separate test reproduced saved legacy answers
that already lack the field.

The UI now validates incoming results without replacing the received payload
with an older model's serialized fields. Existing answers without `hits` retain
their answer and source list and show an explicit explanation that supporting
passages are unavailable; asking again obtains a fresh result. It does not invent
passages or reinterpret the old context count as an empty retrieval. Compatibility
handling stays in the UI; backend answer and search contracts still require hits.

All 44 tests passed, including new coverage for already-saved legacy answers,
legacy outputs arriving through polling, and a stale imported model retaining
new passage fields. The reproducer first failed with the reported missing-hits
exception and passed after the fix. Ruff and whitespace checks passed. No paid
API calls or document re-ingestion were needed for verification.

## 24. Package a team starter after the hack day

**Date:** 30 October 2026 · **Status:** Prepared and tested for sharing

Created `team-starter` from the working `answer-generation` branch at `67ccfa7`,
preserving the existing development branches and history. The GitHub repository
is private; its visibility and collaborators were not changed. Teammates need
repository access before the branch link or clone command will work. Each person
runs their own local services and database with their own OpenAI API key.

Added `TEAM_SETUP.md` with exact branch cloning, locked dependency installation,
environment setup, three-terminal startup, sample questions, customization entry
points, and troubleshooting. README now points new teammates to that guide.
The setup keeps local Qdrant without Docker, so it remains suitable for managed
laptops. This is a development starter, not a hosted or authenticated team service.

Added a fictional handbook in `examples/team-handbook.txt` and a standard-library
generator, `scripts/create_sample_document.py`, that creates an ignored
`data/team-handbook.docx`. It preserves an existing file and makes no API calls.
The sample lets teammates exercise Word ingestion and grounded answers without
needing the original hack-day document. `.streamlit/secrets.toml` is now ignored
alongside the existing environment, document, and database exclusions.

All 45 tests passed, including reading the generated DOCX through the actual
document loader and checking that a second generation preserves existing bytes.
Ruff and whitespace checks passed. `uv sync --locked --dry-run` reported no
environment changes. Generated the sample twice to verify the command-line flow.
Checked that default private-data paths are ignored and that `.env`, `data`, and
`qdrant_storage` have no committed path history; this is not a comprehensive
secret audit. No live paid API request was made. Windows/Linux setup and a fresh
installation on a teammate's machine remain unverified; the guide states those
limits and the need for a live smoke test with their own credentials.

## 25. Prepare the public repository and real PDF example

**Date:** 30 October 2026 · **Status:** Published and verified public

The owner requested public GitHub access and a conventional repository that
teammates can clone without choosing a special branch. Prepared the completed
app for a fast-forward of `main`, keeping the earlier development history and
the `team-starter` checkpoint. Updated the agent branch guidance accordingly.
Pushed the cleanup to `main` and `team-starter`, then changed repository visibility
to public. GitHub reported `PUBLIC` with `main` as the default branch. Code
licensing remains unchanged pending the owner's optional license choice; the
sample paper retains its own license.

Reorganized README around prerequisites, locked dependency installation, the
environment file, three-terminal startup, and a first upload/question. Added a
table explaining every direct dependency, including Boto3's reserved status:
Bedrock is not implemented and AWS credentials are not needed. Detailed internals
now live in `docs/ARCHITECTURE.md`; installation and runtime fixes live in
`docs/TROUBLESHOOTING.md`. `TEAM_SETUP.md` remains a short pointer so earlier
shared links still work. The example environment exposes an empty API-key field
ready to fill in. Existing functions already have docstrings; updated the backend
module description and annotated the owner's reserved imports for linting without
removing them. Application behavior and dependencies are unchanged.

Removed the fictional handbook, its generator, its generator-specific test, and
the generated local handbook. Included the owner's unchanged `docling.pdf` as
`examples/docling.pdf`, with source/version attribution, a verified CC BY 4.0
license link, checksum, and questions with expected evidence. This is the public
Docling Technical Report (arXiv:2408.09869v5); Docling itself is not used by this
application. The public example is separate from ignored user uploads.

Fetched remote refs and scanned 66 historical file blobs across eight published
refs for common API token formats, private keys, credential-bearing URLs, and
private-data paths. No matches were found. This targeted check is not a guarantee
that every possible secret format is absent. Publishing exposes existing branches
and history, including earlier versions of the fictional sample; current files
remove it without rewriting history.

All 44 remaining tests passed. Ruff lint/format and whitespace checks passed.
The actual PDF loader extracted all nine pages into 18 source-labelled chunks,
with a serialized chunk result of 58,862 bytes, within workflow limits. The copied
PDF's checksum matches the supplied file. No OpenAI requests or production
deployment were performed; live credentials and cross-platform setup still need
testing in each user's environment.

## 26. Run the first live test and quiet the UI test warnings

**Date:** 31 October 2026 · **Status:** Live smoke test passed; test output cleaned

Created a local `.env` from `.env.example` and added a real OpenAI API key, then
started the three local services (Uvicorn, the Inngest dev server, and Streamlit)
as described in the README. Backend health reported `ok`, and Inngest registered
all three functions: Ingest Document, Query Documents, and Answer Documents.

Ran the first live test through the Streamlit UI with `examples/docling.pdf`.
Ingestion completed and the UI reported 18 indexed chunks, matching the earlier
loader check. Asked "Which formats can Docling export to?" with three passages.
The answer, "JSON or Markdown format [1]", agreed with the expected evidence in
`examples/README.md`, and passage [1] was the page 2 text it cited. This is one
question on one document, so it shows the pipeline works end to end but says little
about answer quality in general. The run status in the UI briefly stayed on
"Queued" after Inngest had finished before updating; the cause was not
investigated and may be polling lag in the embedded browser pane.

The Streamlit tests logged `missing ScriptRunContext` warnings because
`streamlit.testing.v1.AppTest` runs the UI outside `streamlit run`. Added a log
filter in `tests/test_streamlit_app.py`, installed in `setUpModule` and removed in
`tearDownModule`, that hides only that message from the
`streamlit.runtime.scriptrunner_utils.script_run_context` logger. Other Streamlit
warnings still appear. Application code is unchanged; all 44 tests still pass.

## 27. Package a production deployment for one team

**Date:** 31 October 2026 · **Status:** Built and tested on a laptop; not yet run on a server

The app began as a local demo (milestone 8 listed what production would still need:
authentication, network controls, backups, monitoring, and production Inngest
settings). The owner chose a team deployment with shared documents, Docker Compose on
one server, OIDC sign-in through a reverse proxy, and self-hosted Inngest. Work is on
the `production-deployment` branch; local development is unchanged.

**Application changes.** Added `config.py`, which reads `APP_ENV` (default
`development`). In production the app requires `OPENAI_API_KEY`, the Inngest event and
signing keys, `INNGEST_BASE_URL`, and `QDRANT_URL`, and stops at startup with one message
naming anything missing instead of failing halfway through a paid workflow. Both the
FastAPI app and Streamlit now take their Inngest mode, address, and event key from the
environment instead of the hard-coded development settings. Streamlit sends the signing
key when reading run status, because the self-hosted server answers 401 without it. In
production the UI hides the Inngest dashboard links, since that dashboard is private.
Qdrant server mode already existed through `QDRANT_URL`; no storage code changed.

**Stack (`deploy/`, `Dockerfile`).** One image runs both the API and the UI as an
unprivileged user, with the tokenizer downloaded at build time. Compose runs Caddy
(automatic HTTPS, 25 MB request limit, security headers), oauth2-proxy (OIDC login
with PKCE and an email-domain allowlist), the UI, the API, self-hosted Inngest backed by
Postgres and Redis, and a Qdrant server protected by an API key. Only Caddy is public;
Inngest's dashboard is bound to the server's loopback and reached by SSH tunnel because it
has no login of its own. The API and UI share an `uploads` volume, because the workflow
reads files the UI saved. `deploy/backup.sh` backs up Postgres, a Qdrant snapshot per
collection, and the uploads, then checks the files. `docs/DEPLOYMENT.md` covers setup,
operation, restore, and security notes, plus a section for preparing a Hetzner server
(own project, a Cloud Firewall that opens SSH only to the owner's IP and 80/443 to all,
DNS, Docker), taken from the owner's earlier Hetzner lab notes. `deploy/.env.production.example`
lists every setting (the real file is ignored by Git).

**Checks actually performed.** 49 unit tests pass (5 new, covering the settings, the
startup guard, and the run-status header). The image built and all services became
healthy. Inngest registered all three functions with signed requests. Through the
Streamlit UI, `docling.pdf` ingested as 18 chunks against the Qdrant server and the
question about table structure answered "TableFormer" with citations, consuming live
OpenAI calls. Unauthenticated requests, including the websocket path, were redirected to
the login provider, and an oversize upload was refused. The backup script ran, and the
Qdrant snapshot restored: the collection was deleted and came back with all 18 points.
Ruff reports the same 10 pre-existing findings as `main` and formatting is clean.

**Not verified.** The Hetzner steps (they follow Hetzner's own guides and the owner's
earlier notes but have not been run on a live server), a real OIDC login with a
registered client and domain, certificate issuance on a public domain, the websocket
through an authenticated session, the Postgres and uploads restore steps, running on a
Linux server, and behavior under load. Single
shared document pool only; per-user separation, OCR, relevance thresholds, version cleanup,
and monitoring or alerting remain future work. `boto3` is still unused.

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

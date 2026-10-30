# Team starter: run your own document Q&A app

This branch includes the working PDF/Word ingestion pipeline, local Qdrant,
Inngest workflows, Streamlit interface, and written answers with source passages.
You run your own copy on your laptop. Docker, a hosted database, and an Inngest
cloud account are not required.

## 1. Get access and clone the right branch

The repository is private. Ask the owner for access and accept the GitHub
invitation before cloning. A branch link does not grant repository access.
If GitHub shows a 404, check your signed-in account and invitation first.

```sh
git clone --branch team-starter --single-branch https://github.com/noelogbuagu/RAG-pipeline.git
cd RAG-pipeline
```

Use this branch rather than `main`, which retains the initial project skeleton.
Make your own branch before experimenting:

```sh
git switch -c your-name/my-experiment
```

You can experiment locally without pushing. To contribute back, push your branch
and open a pull request targeting `team-starter`.

## 2. Install dependencies and add your key

You need Git, [uv](https://docs.astral.sh/uv/getting-started/installation/), and
Node.js/npm for the Inngest CLI. Python 3.14 is selected by `.python-version`;
uv can install it if needed. Use approved installation methods on managed laptops.
The tested environment is macOS with Python 3.14; Windows/Linux have not been
verified end to end. No shell activation is needed when using `uv run`.

```sh
uv sync --locked
cp .env.example .env
```

In PowerShell, use `Copy-Item .env.example .env` for the copy command.
On an existing checkout, keep your current `.env` rather than overwriting it.
Edit `.env`, uncomment `OPENAI_API_KEY`, and add your own API key:

```dotenv
OPENAI_API_KEY=your-own-key-here
```

The key needs API billing/quota and access to `text-embedding-3-large` and
`gpt-5.4-mini`. You can override the answer model with `OPENAI_ANSWER_MODEL` using
a Responses-compatible model available to your account. Do not change the
embedding model/dimensions for an existing collection without reindexing.

Each person's documents and Qdrant database stay in their local checkout.
Embedding requests send document text to OpenAI; answer requests send the question
and retrieved passages. Use documents you are permitted to send to that API.
API usage is charged to the configured account. The fictional sample below is
provided so no hack-day or internal company document is needed.

## 3. Start three terminals

Run each command from the cloned repository folder. Leave all three running.

**Terminal 1 — FastAPI and the local Qdrant connection:**

```sh
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — Inngest development server:**

```sh
npx --yes inngest-cli@latest dev -u http://127.0.0.1:8000/api/inngest
```

The development setup was exercised with Inngest CLI v1.49.0. The npm command
installs the current CLI; if a newer release behaves differently, use the
documented v1.49.0 Apple Silicon binary fallback in [README](README.md#getting-started).
Other platforms need their matching official CLI build. Do not bypass TLS
certificate verification if a company proxy blocks installation.

**Terminal 3 — Streamlit:**

```sh
uv run streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

| Service | Open in your browser | Expected state |
| --- | --- | --- |
| Streamlit | http://127.0.0.1:8501 | Upload and question forms |
| Inngest | http://127.0.0.1:8288/functions | Ingest, Query, and Answer Documents functions |
| Qdrant health | http://127.0.0.1:8000/health/qdrant | `status: ok`; zero collections is normal initially |
| FastAPI docs | http://127.0.0.1:8000/docs | API documentation |

These are local development services, not an authenticated hosted team service.
Share the repository link, not your localhost link. Stop servers with Ctrl+C.
Only FastAPI opens the local Qdrant folder; do not start multiple API workers
or open that folder from a second application.

## 4. Try the fictional sample

Generate a small Word document using only the Python standard library:

```sh
uv run python scripts/create_sample_document.py
```

This creates `data/team-handbook.docx` from the tracked fictional source
[examples/team-handbook.txt](examples/team-handbook.txt). It does not overwrite
an existing document, send an event, or call OpenAI.

Upload that DOCX in Streamlit, click **Ingest document**, and wait for the indexed
confirmation. Then click **Ask** with a question below and up to three passages:

| Question | Evidence the sample contains |
| --- | --- |
| How many days can Nimbus staff work remotely each week? | Two days, agreed with their manager. |
| When must travel expenses be submitted, and what must be attached? | Within 30 days, with an itemized receipt. |
| What should someone do if they lose their work laptop? | Notify IT within one hour and provide the device asset number. |
| What is the annual training budget per person? | Not specified; the answer should acknowledge insufficient information. |

Check the supporting passages and numbered references. Answers are generated and
can be wrong; these expected facts help you assess the result. The sample checks
DOCX ingestion. To try PDF ingestion, upload a small text-based PDF of your own.

## 5. Adapt it to your use case

| Change | Where to start |
| --- | --- |
| Documents | Upload PDF or DOCX in Streamlit; scanned PDFs need OCR, not implemented here. |
| Answer style and grounding instructions | `answer_generator.py` |
| Answer model | `OPENAI_ANSWER_MODEL` in `.env`; restart FastAPI afterwards. |
| Chunk size/overlap and embedding model | `data_loader.py`; changed chunking/model settings need reindexing and a suitable collection. |
| Events and workflow steps | `main.py` |
| UI | `streamlit_app.py` |
| Persistence/server connection | `vector_db.py`, `QDRANT_PATH`, and optional `QDRANT_URL` |

The default local database is `qdrant_storage/`. For a clean experiment, stop
FastAPI, set `QDRANT_PATH=qdrant_storage/my-experiment` in `.env`, restart it, and
ingest the sample. That subfolder is also ignored by Git. Existing data is not
migrated or deleted. Changing a document currently retains older indexed versions.

Do not commit `.env`, documents, or database files. The default directories are
already ignored; if you choose a storage path elsewhere in the repo, add that
path to `.gitignore` before using it. New teammates start with an empty database.
They do not receive the original hack-day PDF, API keys, or indexed contents.

## Troubleshooting and checks

| Symptom | Next step |
| --- | --- |
| Address already in use | Use the existing server or stop it before restarting; avoid duplicate processes. |
| Missing collection | Complete one ingestion before asking a question. |
| API authentication, quota, or model-access error | Check your key, billing, and model permissions; inspect the failed Inngest step. |
| Inngest has no functions | Check FastAPI is running and the CLI uses the exact `/api/inngest` URL above. |
| UI pauses after two minutes | Click **Check this run again**; the workflow may still be running. |
| Old answer lacks passages after a code update | Ask again; no re-upload is needed if ingestion succeeded. Restart Streamlit if imports are stale. |
| No extractable text | Try a PDF with selectable text or the sample DOCX. |

Run the checks without API charges or running services:

```sh
uv run python -m unittest discover -s tests -v
```

Tests use temporary databases and mock external API calls. A live smoke test is
still needed for your API credentials and environment. See [README](README.md)
for architecture/limits and [BUILD_JOURNAL](BUILD_JOURNAL.md) for the build history.

For the owner: invite teammates through repository **Settings → Collaborators →
Add people**, then share the `team-starter` branch link. GitHub access applies to
the repository, including other branches and history, not just this branch.
[GitHub collaborator instructions](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/inviting-collaborators-to-a-personal-repository).

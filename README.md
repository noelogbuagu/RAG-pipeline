# RAG Pipeline

A retrieval-augmented generation pipeline for PDF and Word documents.
Currently contains the initial Python project skeleton; document ingestion,
retrieval, and answer generation will be added next.

## Getting started

Requires [uv](https://docs.astral.sh/uv/) and Python 3.14 or later.

```sh
uv sync
uv run main.py
```

The starter prints `Hello from rag-pipeline!`.

## Project files

- `main.py`: application entry point.
- `pyproject.toml`: project metadata and dependencies.
- `.python-version`: Python version used by uv.
- `uv.lock`: dependency lockfile; commit updates when dependencies change.

Use `uv add <package>` to add dependencies. Keep local documents in `data/`
and credentials in `.env`; both are ignored by Git.

## Dependencies

- Streamlit for the UI; FastAPI and Uvicorn for the API.
- OpenAI SDK and Boto3 for OpenAI and Amazon Bedrock access.
- Inngest for background workflows.
- LlamaIndex Core and file readers for document ingestion, including PDFs
  and Word `.docx` files. `docx2txt` supports the Word reader; legacy `.doc`
  files must first be converted to `.docx`.
- Qdrant client for vector storage and retrieval.
- python-dotenv for local environment configuration.

These dependencies are installed but are not yet wired into the application.

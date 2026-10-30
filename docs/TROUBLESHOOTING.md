# Troubleshooting

Start with the three terminal outputs and the failed step in the
[Inngest dashboard](http://127.0.0.1:8288/functions).

| Symptom | What to do |
| --- | --- |
| `uv`, `git`, or `npx` not found | Install the corresponding prerequisite from the README and reopen your terminal. `npx` comes with npm. |
| Address already in use | Reuse the running server or stop it before restarting. Avoid starting duplicate services. |
| Qdrant folder already accessed / locked | Stop the extra backend process. Only one process can own local storage; do not use multiple Uvicorn workers. |
| No Inngest functions | Start FastAPI first; ensure the CLI uses `http://127.0.0.1:8000/api/inngest`. |
| Missing collection | Successfully ingest a document before asking a question. A fresh database has no collection. |
| OpenAI authentication, quota, or model error | Check `.env`, API billing, and model permissions. Restart services after changing configuration. |
| UI pauses after two minutes | Click **Check this run again**. This resumes polling the existing run without resubmitting it. |
| Old answer has no supporting passages | Ask again. Re-ingestion is unnecessary if the document was indexed successfully. Restart Streamlit if imports are stale after a code update. |
| No extractable text | Try the included PDF or a PDF with selectable text. Scanned documents need OCR, not implemented here. |
| Unsupported Word file | Convert legacy `.doc` files to `.docx`. |
| Direct ingestion rejects a path | Copy the file under `data/`, or upload through Streamlit. `examples/` is not an allowed backend input path. |
| Document exceeds a limit | Use a smaller document: uploads are capped at 20 MiB; workflows allow 256 chunks and 2 MiB per saved text result. |
| Answers mention an older document | Old indexed versions are retained. Try a fresh database as described in the README. |

## Inngest installation behind a company proxy

The npm CLI installer can fail with `UNABLE_TO_GET_ISSUER_CERT_LOCALLY`.
Use your organization's approved certificate/proxy setup. Do not disable TLS
verification. An official CLI binary is another installation route.

The following fallback was tested on **Apple Silicon macOS only**, using v1.49.0:

```sh
curl --fail --location https://github.com/inngest/inngest/releases/download/v1.49.0/inngest_1.49.0_darwin_arm64.tar.gz --output /tmp/rag-inngest-1.49.0.tar.gz
mkdir -p /tmp/rag-inngest-1.49.0
tar -xzf /tmp/rag-inngest-1.49.0.tar.gz -C /tmp/rag-inngest-1.49.0
/tmp/rag-inngest-1.49.0/inngest dev -u http://127.0.0.1:8000/api/inngest
```

Other platforms need the matching binary from the
[official releases](https://github.com/inngest/inngest/releases/tag/v1.49.0).
The README's `@latest` command is not pinned; use this tested release when
investigating a CLI compatibility problem.

## Reporting a problem

Include your OS, Python version (`uv run python --version`), the command you ran,
and the error/failed step. Remove API keys and document contents from logs before
posting. The automated checks run with:

```sh
uv run python -m unittest discover -s tests -v
```

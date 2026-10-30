"""Local PDF/Word upload and retrieval UI; FastAPI owns the Qdrant connection."""

import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen

import inngest
import streamlit as st
from dotenv import load_dotenv

from custom_types import (
    RAGIngestResult,
    RAGQueryResult,
    RAGSearchRequest,
    RAGSearchResult,
)

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")
UPLOAD_DIR = PROJECT_DIR / "data" / "uploads"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
POLL_TIMEOUT_SECONDS = 120


def dev_server_url() -> str:
    """Use one dev-server address for both sending events and reading results."""
    return os.getenv("INNGEST_DEV_SERVER_URL", "http://127.0.0.1:8288").rstrip("/")


@st.cache_resource(max_entries=1, show_spinner=False)
def get_inngest_client() -> inngest.Inngest:
    """Reuse the synchronous development client across Streamlit reruns."""
    return inngest.Inngest(
        app_id="rag_app",
        is_production=False,
        event_api_base_url=dev_server_url(),
        request_timeout=10,
    )


def save_uploaded_document(name: str, content: bytes) -> Path:
    """Atomically save a PDF/DOCX under data/, with stable content-specific paths."""
    # Strip browser-supplied paths, including Windows separators.
    filename = Path(name.replace("\\", "/")).name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise ValueError("Choose a PDF or Word .docx file.")
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("Choose a nonempty document no larger than 20 MiB.")
    stem = re.sub(r"[^\w .-]", "_", Path(filename).stem)[:100] or "document"
    directory = UPLOAD_DIR / hashlib.sha256(content).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{stem}{suffix}"
    # Identical uploads keep their source ID; changed files never overwrite a run's input.
    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        try:
            temporary.write(content)
            temporary.flush()
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
    try:
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    return destination.resolve()


def send_event(name: str, data: dict[str, object]) -> str:
    """Submit one workflow and return its event ID, not a completion claim."""
    event_ids = get_inngest_client().send_sync(inngest.Event(name=name, data=data))
    if len(event_ids) != 1:
        raise RuntimeError("Inngest did not return exactly one event ID.")
    return event_ids[0]


def fetch_run(event_id: str) -> dict | None:
    """Read the single run triggered by one of our events, with a bounded request."""
    url = f"{dev_server_url()}/v1/events/{quote(event_id, safe='')}/runs"
    try:
        with urlopen(url, timeout=5) as response:
            body = json.load(response)
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise RuntimeError(
            "Could not read run status. Check that Inngest is running."
        ) from exc
    runs = body.get("data") if isinstance(body, dict) else None
    if not isinstance(runs, list) or len(runs) > 1:
        raise ValueError("Expected at most one Inngest run for this event.")
    if not runs:
        return None
    if not isinstance(runs[0], dict):
        raise ValueError("Inngest returned an invalid run.")
    return runs[0]


def track_event(kind: str, event_id: str, label: str) -> None:
    """Retain the current event and its output when another widget reruns the app."""
    st.session_state[kind] = {
        "event_id": event_id,
        "label": label,
        "phase": "waiting",
        "started": time.monotonic(),
        "status": "Queued",
    }


def display_output(kind: str, output: dict) -> None:
    """Show the written answer with numbered passages; retain older search results."""
    if kind == "ingestion":
        result = RAGIngestResult.model_validate(output)
        if result.status == "no_text":
            st.warning("No extractable text was found. Scanned PDFs may need OCR.")
        else:
            st.success(
                f"Indexed {result.ingested} chunks. You can now search your documents."
            )
        return
    if "answer" in output:
        # Older saved answers contain a summary but no retrievable passage details.
        answer = RAGQueryResult.model_validate(
            {**output, "hits": output.get("hits", [])}
        )
        st.subheader("Answer")
        st.text(answer.answer)
        if "hits" not in output:
            if answer.sources:
                st.subheader("Sources")
                for source in answer.sources:
                    st.text(source)
            st.info(
                "This saved answer does not include its supporting passages. "
                "Ask the question again to retrieve them and check its citations."
            )
            return
        st.subheader("Supporting passages")
    result = RAGSearchResult.model_validate(output)
    if not result.hits:
        st.info("No passages were returned. Ingest a document successfully first.")
        return
    st.caption(
        f"{len(result.hits)} passages from {len(result.sources)} sources. "
        "Similarity scores rank matches; they are not confidence percentages."
    )
    for index, hit in enumerate(result.hits, start=1):
        payload = hit.payload or {}
        source = str(payload.get("source", "Unknown source"))
        with st.expander(
            f"[{index}] {Path(source).name} · score {hit.score:.3f}",
            expanded=index == 1,
        ):
            # Treat uploaded document contents as text, not executable HTML or Markdown.
            st.text(str(payload.get("text", "")))
            st.caption(f"Source: {source}")
            if payload.get("page_label") is not None:
                st.caption(f"Page: {payload['page_label']}")
            if payload.get("chunk_index") is not None:
                st.caption(f"Chunk index: {payload['chunk_index']}")


def display_run(kind: str) -> None:
    """Poll without a blocking sleep loop; pausing never cancels or resends a job."""
    job = st.session_state.get(kind)
    if job is None:
        return
    st.caption(job["label"])
    with st.expander("Run details", icon=":material/info:"):
        st.text(f"Event: {job['event_id']}")
        st.link_button("Inspect in Inngest", f"{dev_server_url()}/functions")
    if job["phase"] == "waiting":
        try:
            if time.monotonic() - job["started"] >= POLL_TIMEOUT_SECONDS:
                raise TimeoutError(
                    "Still waiting after two minutes. The run may still be working."
                )
            run = fetch_run(job["event_id"])
            if run:
                job["status"] = run.get("status", "Unknown")
                if job["status"] == "Completed":
                    output = run.get("output")
                    if isinstance(output, str):
                        output = json.loads(output)
                    # A session may still be tracking a retrieval-only run from before reload.
                    model = (
                        RAGIngestResult
                        if kind == "ingestion"
                        else (
                            RAGQueryResult
                            if isinstance(output, dict) and "answer" in output
                            else RAGSearchResult
                        )
                    )
                    validation_output = output
                    if (
                        kind != "ingestion"
                        and isinstance(output, dict)
                        and "answer" in output
                    ):
                        validation_output = {**output, "hits": output.get("hits", [])}
                    model.model_validate(validation_output)
                    # Preserve the wire payload: an older imported model can silently
                    # discard new fields during model_dump after Streamlit hot reload.
                    job["output"] = output
                    job["phase"] = "completed"
                elif job["status"] in {"Failed", "Cancelled"}:
                    job["phase"] = "failed"
            st.session_state[kind] = job
        except (RuntimeError, ValueError, TimeoutError) as exc:
            job.update(phase="paused", error=str(exc))
            st.session_state[kind] = job
        if job["phase"] != "waiting":
            # Rebuild the fragment without a timer once polling is no longer needed.
            st.rerun()
    if job["phase"] == "completed":
        display_output(kind, job["output"])
    elif job["phase"] == "failed":
        st.error(
            f"Run {job['status'].lower()}. Open Inngest to inspect the failed step."
        )
    elif job["phase"] == "paused":
        st.warning(job["error"])
        if st.button(
            "Check this run again", key=f"check_{kind}", icon=":material/refresh:"
        ):
            job.update(phase="waiting", started=time.monotonic())
            st.session_state[kind] = job
            st.rerun()
    else:
        st.info(f"Run status: {job['status']}")


def display_tracked_run(kind: str) -> None:
    """Schedule refreshes only while this run is waiting, keeping finished results still."""
    job = st.session_state.get(kind)
    interval = 2 if job and job["phase"] == "waiting" else None
    st.fragment(display_run, run_every=interval, key=f"run_{kind}")(kind)


def main() -> None:
    """Build the local UI without importing main.py or opening Qdrant storage."""
    st.set_page_config(
        page_title="RAG Documents",
        page_icon=":material/find_in_page:",
        layout="centered",
    )
    for kind in ("ingestion", "query"):
        st.session_state.setdefault(kind, None)
    st.title("Ask your documents")
    st.caption(
        "Upload PDF or Word documents, then ask a question and check the passages behind the answer."
    )
    st.link_button(
        "Open Inngest dashboard",
        f"{dev_server_url()}/functions",
        icon=":material/open_in_new:",
    )

    with st.form("ingest_form"):
        st.subheader("1. Ingest a document")
        uploaded = st.file_uploader(
            "Choose a PDF or Word document (up to 20 MiB)",
            type=["pdf", "docx"],
            max_upload_size=MAX_UPLOAD_BYTES // (1024 * 1024),
            key="document_upload",
        )
        ingest = st.form_submit_button(
            "Ingest document",
            key="submit_ingestion",
            type="primary",
            icon=":material/upload_file:",
            width="stretch",
        )
    ingestion_output = st.container()

    with st.form("query_form"):
        st.subheader("2. Ask a question")
        question = st.text_input(
            "Your question",
            max_chars=2000,
            key="question",
            placeholder="What are the main findings?",
        )
        top_k = st.number_input(
            "Maximum passages",
            min_value=1,
            max_value=20,
            value=5,
            step=1,
            key="top_k",
            help="Return up to this many chunks, ranked by similarity.",
        )
        query = st.form_submit_button(
            "Ask",
            key="submit_query",
            type="primary",
            icon=":material/search:",
            width="stretch",
        )
    query_output = st.container()

    # Render both forms first so a slow network call does not hide the search controls.
    if ingest:
        if uploaded is None:
            ingestion_output.warning("Choose a document first.")
        else:
            try:
                with ingestion_output, st.spinner("Saving document…"):
                    path = save_uploaded_document(uploaded.name, uploaded.getvalue())
            except ValueError as exc:
                ingestion_output.warning(str(exc))
            except OSError:
                ingestion_output.error(
                    "Could not save the upload. Check local disk space and permissions."
                )
            else:
                try:
                    with ingestion_output, st.spinner("Submitting ingestion…"):
                        event_id = send_event(
                            "rag/ingest_document", {"path": str(path)}
                        )
                    track_event("ingestion", event_id, uploaded.name)
                except Exception:
                    ingestion_output.error(
                        "Could not submit the document. Check the Inngest server and dashboard before retrying if delivery is uncertain."
                    )
    if query:
        if not question.strip():
            query_output.warning("Enter a question first.")
        else:
            try:
                request = RAGSearchRequest(question=question, top_k=int(top_k))
                with query_output, st.spinner("Requesting an answer…"):
                    event_id = send_event("rag/answer_documents", request.model_dump())
                track_event("query", event_id, request.question)
            except Exception:
                query_output.error(
                    "Could not submit the question. Check the Inngest server and dashboard before retrying."
                )
    with ingestion_output:
        display_tracked_run("ingestion")
    with query_output:
        display_tracked_run("query")


if __name__ == "__main__":
    main()

"""Check local upload safety, event transport, and UI rerun behavior."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import URLError

from streamlit.testing.v1 import AppTest

import streamlit_app as ui


def render_app():
    import streamlit_app

    streamlit_app.main()


class StreamlitAppTests(unittest.TestCase):
    def test_upload_submission_uses_document_event_and_reports_completion(self):
        upload = Mock()
        upload.name = "notes.docx"
        upload.getvalue.return_value = b"synthetic Word file"
        output = {
            "status": "indexed",
            "source": "notes.docx",
            "chunks": 2,
            "ingested": 2,
            "indexed": True,
            "collection": "test",
        }
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("streamlit_app.UPLOAD_DIR", Path(directory)),
            patch("streamlit_app.st.file_uploader", return_value=upload),
            patch("streamlit_app.send_event", return_value="ingest-123") as send,
            patch(
                "streamlit_app.fetch_run",
                return_value={"status": "Completed", "output": output},
            ),
        ):
            app = AppTest.from_function(render_app).run()
            send.assert_not_called()
            app.button[0].click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertIn("Indexed 2 chunks", app.success[0].value)
            name, data = send.call_args.args
            self.assertEqual(name, "rag/ingest_document")
            self.assertEqual(
                Path(data["path"]).read_bytes(), upload.getvalue.return_value
            )
            app.run()
            send.assert_called_once()

    def test_uploads_are_safe_stable_and_do_not_overwrite_changed_content(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("streamlit_app.UPLOAD_DIR", Path(directory)),
        ):
            first = ui.save_uploaded_document("../../guide.pdf", b"first")
            again = ui.save_uploaded_document("guide.pdf", b"first")
            changed = ui.save_uploaded_document("guide.pdf", b"changed")
            word = ui.save_uploaded_document(r"C:\\fakepath\\notes.DOCX", b"word")
            self.assertEqual(first, again)
            self.assertNotEqual(first, changed)
            self.assertEqual(first.read_bytes(), b"first")
            self.assertEqual(word.name, "notes.docx")
            for path in (first, changed, word):
                self.assertTrue(path.is_relative_to(Path(directory).resolve()))
            for name, content in [("file.exe", b"x"), ("empty.pdf", b"")]:
                with self.assertRaises(ValueError):
                    ui.save_uploaded_document(name, content)
            with (
                patch("streamlit_app.MAX_UPLOAD_BYTES", 1),
                self.assertRaises(ValueError),
            ):
                ui.save_uploaded_document("large.pdf", b"xx")

    def test_send_uses_synchronous_client_and_returns_event_id(self):
        client = Mock()
        client.send_sync.return_value = ["event-123"]
        with patch("streamlit_app.get_inngest_client", return_value=client):
            self.assertEqual(
                ui.send_event("rag/ingest_document", {"path": "/data/test.pdf"}),
                "event-123",
            )
            event = client.send_sync.call_args.args[0]
            self.assertEqual(event.name, "rag/ingest_document")
            self.assertEqual(event.data, {"path": "/data/test.pdf"})
            client.send_sync.return_value = []
            with self.assertRaises(RuntimeError):
                ui.send_event("rag/query_documents", {"question": "test"})

    def test_fetch_run_timeout_url_encoding_and_response_validation(self):
        for data, expected in [
            ([], None),
            ([{"status": "Running"}], {"status": "Running"}),
        ]:
            with patch(
                "streamlit_app.urlopen",
                return_value=io.BytesIO(json.dumps({"data": data}).encode()),
            ) as http:
                self.assertEqual(ui.fetch_run("a/b"), expected)
                self.assertTrue(
                    http.call_args.args[0].endswith("/v1/events/a%2Fb/runs")
                )
                self.assertEqual(http.call_args.kwargs["timeout"], 5)
        for body in [{}, {"data": [1]}, {"data": [{}, {}]}]:
            with patch(
                "streamlit_app.urlopen",
                return_value=io.BytesIO(json.dumps(body).encode()),
            ):
                with self.assertRaises(ValueError):
                    ui.fetch_run("event-123")
        with patch("streamlit_app.urlopen", side_effect=URLError("offline")):
            with self.assertRaisesRegex(RuntimeError, "Check that Inngest"):
                ui.fetch_run("event-123")

    def test_search_result_survives_rerun_without_sending_another_event(self):
        output = {
            "answer": "The document explains a useful topic. [1]",
            "sources": ["guide.pdf"],
            "num_contexts": 1,
            "hits": [
                {
                    "id": 1,
                    "version": 0,
                    "score": 0.9,
                    "payload": {
                        "text": "A useful passage",
                        "source": "guide.pdf",
                        "page_label": "3",
                        "chunk_index": 0,
                    },
                }
            ],
        }
        with (
            patch("streamlit_app.send_event", return_value="query-123") as send,
            patch(
                "streamlit_app.fetch_run",
                return_value={"status": "Completed", "output": json.dumps(output)},
            ) as fetch,
            patch("streamlit_app.st.fragment", wraps=ui.st.fragment) as fragment,
        ):
            app = AppTest.from_function(render_app).run()
            self.assertEqual(len(app.exception), 0)
            send.assert_not_called()
            app.text_input[0].set_value("  What is this about?  ")
            app.button[1].click().run()
            self.assertEqual(len(app.exception), 0)
            send.assert_called_once_with(
                "rag/answer_documents", {"question": "What is this about?", "top_k": 5}
            )
            self.assertIn("A useful passage", [text.value for text in app.text])
            self.assertIn(output["answer"], [text.value for text in app.text])
            app.run()
            send.assert_called_once()
            fetch.assert_called_once_with("query-123")
            self.assertIn("A useful passage", [text.value for text in app.text])
            self.assertTrue(
                all(
                    call.kwargs["run_every"] is None
                    for call in fragment.call_args_list[-2:]
                )
            )

    def test_resume_paused_run_rechecks_same_event_without_resubmitting(self):
        with patch("streamlit_app.send_event", return_value="query-123") as send:
            with patch("streamlit_app.POLL_TIMEOUT_SECONDS", 0):
                app = AppTest.from_function(render_app).run()
                app.text_input[0].set_value("test")
                app.button(key="submit_query").click().run()
                self.assertEqual(app.session_state["query"]["phase"], "paused")
            with patch(
                "streamlit_app.fetch_run",
                return_value={"status": "Completed", "output": {"hits": []}},
            ) as fetch:
                app.button(key="check_query").click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(app.session_state["query"]["phase"], "completed")
                fetch.assert_called_once_with("query-123")
                send.assert_called_once()

    def test_invalid_upload_gives_specific_feedback_without_sending(self):
        upload = Mock(name="upload")
        upload.name = "empty.pdf"
        upload.getvalue.return_value = b""
        with (
            patch("streamlit_app.st.file_uploader", return_value=upload) as uploader,
            patch("streamlit_app.send_event") as send,
        ):
            app = AppTest.from_function(render_app).run()
            app.button(key="submit_ingestion").click().run()
            self.assertIn("nonempty document", app.warning[0].value)
            self.assertEqual(uploader.call_args.kwargs["max_upload_size"], 20)
            send.assert_not_called()
            self.assertEqual(len(app.exception), 0)

    def test_ui_handles_blank_questions_failed_runs_and_polling_errors(self):
        with patch("streamlit_app.send_event", return_value="query-123") as send:
            app = AppTest.from_function(render_app).run()
            app.button[1].click().run()
            send.assert_not_called()
            self.assertIn("Enter a question", app.warning[0].value)
            with patch("streamlit_app.fetch_run", return_value={"status": "Failed"}):
                app.text_input[0].set_value("test")
                app.button[1].click().run()
                self.assertIn("Run failed", app.error[0].value)
            with patch(
                "streamlit_app.fetch_run", side_effect=RuntimeError("Server offline")
            ):
                app.button[1].click().run()
                self.assertIn("Server offline", app.warning[0].value)
                self.assertEqual(app.session_state["query"]["phase"], "paused")
            self.assertEqual(len(app.exception), 0)

    def test_timeout_preserves_event_and_does_not_resubmit(self):
        with (
            patch("streamlit_app.send_event", return_value="query-123") as send,
            patch("streamlit_app.fetch_run", return_value=None),
            patch("streamlit_app.POLL_TIMEOUT_SECONDS", 0),
        ):
            app = AppTest.from_function(render_app).run()
            app.text_input[0].set_value("test")
            app.button[1].click().run()
            self.assertIn("Still waiting", app.warning[0].value)
            self.assertEqual(app.session_state["query"]["event_id"], "query-123")
            app.run()
            send.assert_called_once()
            self.assertEqual(len(app.exception), 0)

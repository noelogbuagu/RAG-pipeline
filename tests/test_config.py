"""Check environment-driven settings and the production startup guard."""

import io
import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import config
import streamlit_app as ui
from main import app

PRODUCTION = {
    "APP_ENV": "production",
    "OPENAI_API_KEY": "sk-test",
    "INNGEST_EVENT_KEY": "event",
    "INNGEST_SIGNING_KEY": "abcd",
    "INNGEST_BASE_URL": "http://inngest:8288",
    "QDRANT_URL": "http://qdrant:6333",
}


class ConfigTests(unittest.TestCase):
    def test_development_is_the_default_and_needs_no_production_settings(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(config.is_production())
            self.assertEqual(config.inngest_url(), "http://127.0.0.1:8288")
            self.assertEqual(config.missing_production_settings(), [])
            config.require_production_settings()

    def test_production_requires_every_setting_and_names_the_missing_ones(self):
        with patch.dict("os.environ", {"APP_ENV": " Production "}, clear=True):
            self.assertTrue(config.is_production())
            missing = config.missing_production_settings()
            self.assertEqual(len(missing), len(config.PRODUCTION_REQUIREMENTS))
            with self.assertRaisesRegex(RuntimeError, "INNGEST_SIGNING_KEY"):
                config.require_production_settings()
        blank = {**PRODUCTION, "QDRANT_URL": "  "}
        with (
            patch.dict("os.environ", blank, clear=True),
            self.assertRaisesRegex(RuntimeError, "QDRANT_URL"),
        ):
            config.require_production_settings()
        with patch.dict("os.environ", PRODUCTION, clear=True):
            config.require_production_settings()

    def test_inngest_url_prefers_production_address_and_trims_slash(self):
        env = {
            "INNGEST_BASE_URL": "http://inngest:8288/",
            "INNGEST_DEV_SERVER_URL": "http://localhost:9999",
        }
        with patch.dict("os.environ", env, clear=True):
            self.assertEqual(config.inngest_url(), "http://inngest:8288")
        with patch.dict(
            "os.environ",
            {"INNGEST_DEV_SERVER_URL": "http://localhost:9999"},
            clear=True,
        ):
            self.assertEqual(config.inngest_url(), "http://localhost:9999")

    def test_production_app_refuses_to_start_with_missing_settings(self):
        with (
            patch.dict("os.environ", {"APP_ENV": "production"}, clear=True),
            self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"),
            TestClient(app),
        ):
            pass

    def test_run_status_request_sends_signing_key_only_when_configured(self):
        body = io.BytesIO(json.dumps({"data": []}).encode())
        with patch.dict("os.environ", {"INNGEST_SIGNING_KEY": "abcd"}, clear=True):
            with patch("streamlit_app.urlopen", return_value=body) as http:
                ui.fetch_run("event-1")
            request = http.call_args.args[0]
            self.assertEqual(request.get_header("Authorization"), "Bearer abcd")
        body = io.BytesIO(json.dumps({"data": []}).encode())
        with patch.dict("os.environ", {}, clear=True):
            with patch("streamlit_app.urlopen", return_value=body) as http:
                ui.fetch_run("event-1")
            self.assertIsNone(http.call_args.args[0].get_header("Authorization"))


if __name__ == "__main__":
    unittest.main()

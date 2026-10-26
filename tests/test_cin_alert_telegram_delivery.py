import json
import os
import tempfile
from pathlib import Path
import urllib.error
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from cin_alert_delivery_outbox import enqueue_alert_delivery
from cin_alert_telegram_delivery import (
    TelegramDeliveryError,
    process_due_telegram_alerts,
    send_telegram_notification,
)


NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


class FakeResponse:
    status = 200

    def __init__(self, payload, status=200, raw=None):
        self.status = status
        self.raw = raw if raw is not None else json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.raw[:size] if size >= 0 else self.raw


class TelegramDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "CIN_TELEGRAM_BOT_TOKEN": "123456:fake-test-token",
            "CIN_TELEGRAM_CHAT_ID": "-100123456789",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    @patch("cin_alert_telegram_delivery.urllib.request.urlopen")
    def test_success_sends_only_to_configured_destination(self, mocked):
        mocked.return_value = FakeResponse({"ok": True, "result": {"message_id": 77}})
        result = send_telegram_notification({"text": "BTC threshold crossed", "chat_id": "attacker-controlled"})
        self.assertEqual(result, {"provider": "telegram", "accepted": True, "message_id": 77})
        request = mocked.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/sendMessage"))
        self.assertIn("123456:fake-test-token", request.full_url)
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["chat_id"], "-100123456789")
        self.assertNotIn("attacker-controlled", request.data.decode("utf-8"))
        self.assertEqual(mocked.call_args.kwargs["timeout"], 10)

    @patch("cin_alert_telegram_delivery.urllib.request.urlopen")
    def test_provider_rejection_uses_sanitized_error(self, mocked):
        mocked.return_value = FakeResponse({"ok": False, "description": "private provider detail"})
        with self.assertRaises(TelegramDeliveryError) as raised:
            send_telegram_notification({"text": "Alert"})
        self.assertEqual(raised.exception.code, "telegram_rejected")
        self.assertNotIn("private provider detail", str(raised.exception))

    @patch("cin_alert_telegram_delivery.urllib.request.urlopen")
    def test_http_error_does_not_leak_token_in_error(self, mocked):
        mocked.side_effect = urllib.error.HTTPError(
            "https://api.telegram.org/bot123456:fake-test-token/sendMessage",
            401, "Unauthorized", {}, None,
        )
        with self.assertRaises(TelegramDeliveryError) as raised:
            send_telegram_notification({"text": "Alert"})
        self.assertEqual(raised.exception.code, "telegram_http_error")
        self.assertNotIn("fake-test-token", str(raised.exception))

    @patch("cin_alert_telegram_delivery.urllib.request.urlopen", side_effect=urllib.error.URLError("network"))
    def test_network_error_is_sanitized(self, mocked):
        with self.assertRaises(TelegramDeliveryError) as raised:
            send_telegram_notification({"text": "Alert"})
        self.assertEqual(raised.exception.code, "telegram_network_error")

    @patch("cin_alert_telegram_delivery.urllib.request.urlopen")
    def test_invalid_message_never_calls_provider(self, mocked):
        for payload in ({}, {"text": ""}, {"text": "x" * 4097}, {"text": "bad\x00text"}):
            with self.subTest(payload=str(payload)[:20]):
                with self.assertRaises(TelegramDeliveryError) as raised:
                    send_telegram_notification(payload)
                self.assertEqual(raised.exception.code, "telegram_message_invalid")
        mocked.assert_not_called()

    @patch.dict(os.environ, {"CIN_TELEGRAM_BOT_TOKEN": "", "CIN_TELEGRAM_CHAT_ID": ""})
    @patch("cin_alert_telegram_delivery.urllib.request.urlopen")
    def test_missing_credentials_fail_before_network(self, mocked):
        with self.assertRaises(TelegramDeliveryError) as raised:
            send_telegram_notification({"text": "Alert"})
        self.assertEqual(raised.exception.code, "telegram_configuration_missing")
        mocked.assert_not_called()

    @patch("cin_alert_telegram_delivery.urllib.request.urlopen")
    def test_worker_marks_successful_delivery_sent(self, mocked):
        tmp_path = Path(tempfile.mkdtemp())
        mocked.return_value = FakeResponse({"ok": True, "result": {"message_id": 5}})
        path = tmp_path / "alerts.sqlite3"
        enqueue_alert_delivery(
            path, rule_id="r1", observation_id="e1",
            payload={"text": "BTC alert"}, now=NOW,
        )
        result = process_due_telegram_alerts(str(path), now=NOW)
        self.assertEqual(result["claimed"], 1)
        self.assertEqual(result["results"][0]["status"], "sent")

    @patch("cin_alert_telegram_delivery.urllib.request.urlopen", side_effect=urllib.error.URLError("offline"))
    def test_worker_schedules_retry_without_leaking_provider_detail(self, mocked):
        tmp_path = Path(tempfile.mkdtemp())
        path = tmp_path / "alerts.sqlite3"
        enqueue_alert_delivery(
            path, rule_id="r1", observation_id="e1",
            payload={"text": "BTC alert"}, now=NOW,
        )
        result = process_due_telegram_alerts(str(path), now=NOW)
        self.assertEqual(result["results"][0]["status"], "failed")
        self.assertEqual(result["results"][0]["error_code"], "telegram_network_error")

    @patch.dict(os.environ, {"CIN_TELEGRAM_BOT_TOKEN": "", "CIN_TELEGRAM_CHAT_ID": ""})
    def test_worker_does_not_claim_items_without_configuration(self):
        tmp_path = Path(tempfile.mkdtemp())
        path = tmp_path / "alerts.sqlite3"
        enqueue_alert_delivery(
            path, rule_id="r1", observation_id="e1",
            payload={"text": "BTC alert"}, now=NOW,
        )
        with self.assertRaises(TelegramDeliveryError):
            process_due_telegram_alerts(str(path), now=NOW)
        with __import__("sqlite3").connect(path) as db:
            self.assertEqual(db.execute("SELECT status FROM alert_delivery_outbox").fetchone()[0], "pending")

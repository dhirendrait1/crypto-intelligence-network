"""Offline tests for the explicit one-shot CIN Telegram worker CLI."""
import json
from unittest.mock import patch

import pytest

import cin_alert_telegram_worker as worker


def test_worker_requires_explicit_once_acknowledgement():
    with pytest.raises(SystemExit) as raised:
        worker.main([])
    assert raised.value.code == 2


def test_worker_requires_persistent_database_path(capsys):
    with patch.dict("os.environ", {"CIN_ALERT_DATABASE_PATH": ":memory:"}):
        assert worker.main(["--once"]) == 2
    output = json.loads(capsys.readouterr().err)
    assert output["error_code"] == "alert_database_path_missing"


def test_worker_processes_one_bounded_batch(capsys):
    with patch.dict("os.environ", {"CIN_ALERT_DATABASE_PATH": "/tmp/cin-alerts.sqlite3"}):
        with patch.object(worker, "process_due_telegram_alerts", return_value={
            "provider": "telegram", "claimed": 0, "results": [], "read_only": True
        }) as process:
            assert worker.main(["--once", "--limit", "3"]) == 0
    assert process.call_args.kwargs["limit"] == 3
    assert process.call_args.kwargs["database_path"] if "database_path" in process.call_args.kwargs else process.call_args.args[0] == "/tmp/cin-alerts.sqlite3"
    output = json.loads(capsys.readouterr().out)
    assert output["read_only"] is True


def test_worker_reports_sanitized_telegram_configuration_error(capsys):
    with patch.dict("os.environ", {"CIN_ALERT_DATABASE_PATH": "/tmp/cin-alerts.sqlite3"}):
        with patch.object(worker, "process_due_telegram_alerts", side_effect=worker.TelegramDeliveryError("telegram_configuration_missing")):
            assert worker.main(["--once"]) == 2
    output = json.loads(capsys.readouterr().err)
    assert output == {"status": "error", "error_code": "telegram_configuration_missing"}

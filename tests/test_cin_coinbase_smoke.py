import unittest
from unittest.mock import patch

from scripts.cin_coinbase_smoke import check_product


class FakeResponse:
    def __init__(self, payload):
        import json
        self.raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.raw[:size]


class CoinbaseSmokeTests(unittest.TestCase):
    @patch("scripts.cin_coinbase_smoke.urllib.request.urlopen")
    def test_valid_public_payload_passes_and_labels_base_volume(self, mocked):
        from datetime import datetime, timezone
        mocked.side_effect = [
            FakeResponse({"last": "100", "open": "90", "volume": "12.5"}),
            FakeResponse({"time": datetime.now(timezone.utc).isoformat()}),
        ]
        result = check_product("bitcoin", "BTC-USD")
        self.assertTrue(result["passed"])
        self.assertEqual(result["volume_unit"], "BITCOIN")
        self.assertIn("base-asset-denominated", result["note"])
        self.assertEqual(mocked.call_count, 2)
        for call in mocked.call_args_list:
            self.assertEqual(call.args[0].get_method(), "GET")

    @patch("scripts.cin_coinbase_smoke.urllib.request.urlopen")
    def test_invalid_numeric_and_naive_timestamp_fail_closed(self, mocked):
        mocked.side_effect = [
            FakeResponse({"last": "NaN", "open": "0", "volume": "-1"}),
            FakeResponse({"time": "2026-10-30T12:00:00"}),
        ]
        result = check_product("ethereum", "ETH-USD")
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["stats_last_positive_finite"])
        self.assertFalse(result["checks"]["stats_open_positive_finite"])
        self.assertFalse(result["checks"]["stats_volume_finite_nonnegative"])
        self.assertFalse(result["checks"]["ticker_timestamp_timezone_aware"])


if __name__ == "__main__":
    unittest.main()

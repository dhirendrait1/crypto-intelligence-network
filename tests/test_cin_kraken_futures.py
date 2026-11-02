import json
import unittest
from unittest.mock import patch

import cin_derivatives_market_data_api as api


class Response:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, limit):
        return self.body[:limit]


class KrakenFuturesTests(unittest.TestCase):
    def payload(self):
        return {"result": "success", "serverTime": "2026-11-02T04:00:00Z", "ticker": {
            "symbol": "PF_XBTUSD", "pair": "XBT:USD", "tag": "perpetual",
            "suspended": False, "markPrice": 70000, "indexPrice": 69900,
        }}

    def test_identifies_usd_market_and_leaves_unverified_metrics_unknown(self):
        with patch.object(api.urllib.request, "urlopen", return_value=Response(self.payload())) as fetch:
            result = api._kraken_futures_snapshot()
        self.assertEqual(result["symbol"], "BTCUSD")
        self.assertEqual(result["provider_symbol"], "PF_XBTUSD")
        self.assertEqual(result["data"]["mark_price"], 70000)
        self.assertIsNone(result["data"]["funding_rate"])
        self.assertEqual(result["data_quality"]["freshness_status"], "unknown")
        self.assertEqual(fetch.call_args.kwargs["timeout"], 10)

    def test_rejects_wrong_pair_and_unknown_market_status(self):
        for change in ({"pair": "XBT:USDT"}, {"symbol": "PF_ETHUSD"}, {"suspended": True}, {"markPrice": float("nan")}):
            payload = self.payload()
            payload["ticker"].update(change)
            with self.subTest(change=change), patch.object(api.urllib.request, "urlopen", return_value=Response(payload)):
                with self.assertRaises(ValueError):
                    api._kraken_futures_snapshot()


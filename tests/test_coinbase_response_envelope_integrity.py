"""Offline tests for the Coinbase successful-response JSON envelope."""
import json
import unittest
from unittest.mock import patch

import cin_public_market_candles_api as api


class CoinbaseResponseEnvelopeIntegrityTests(unittest.TestCase):
    def test_accepts_top_level_array_payload(self):
        payload = [[1735722000, "99", "103", "100", "102", "10"]]
        with patch.object(api, "_request_json", return_value=payload):
            self.assertIs(api._coinbase_request_json("https://example.invalid"), payload)

    def test_accepts_empty_array_at_envelope_layer(self):
        with patch.object(api, "_request_json", return_value=[]):
            self.assertEqual(api._coinbase_request_json("https://example.invalid"), [])

    def test_rejects_object_error_envelopes_and_other_non_array_json(self):
        invalid_payloads = (
            {"message": "rate limit"},
            {"error": "unavailable"},
            None,
            "unexpected",
            17,
            True,
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with patch.object(api, "_request_json", return_value=payload):
                    with self.assertRaisesRegex(
                        api._MalformedProviderResponse,
                        "successful response envelope was not a top-level array",
                    ):
                        api._coinbase_request_json("https://example.invalid")

    def test_rejects_invalid_json_body_as_malformed_success(self):
        with patch.object(api, "_request_json", side_effect=json.JSONDecodeError("bad json", "{", 0)):
            with self.assertRaisesRegex(
                api._MalformedProviderResponse, "invalid successful response body"
            ):
                api._coinbase_request_json("https://example.invalid")

    def test_does_not_reinterpret_malformed_success_as_transport_failure(self):
        with patch.object(api, "_request_json", return_value={"error": "temporarily unavailable"}):
            with self.assertRaises(api._MalformedProviderResponse):
                api._coinbase_request_json("https://example.invalid")


if __name__ == "__main__":
    unittest.main()

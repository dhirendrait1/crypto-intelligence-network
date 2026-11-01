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

    def test_empty_product_catalogue_means_requested_product_is_absent(self):
        with patch.object(api, "_coinbase_request_json", return_value=[]):
            with self.assertRaisesRegex(ValueError, "is not listed in the public product catalogue"):
                api._verify_coinbase_product("BTC-USD", "BTC", "USD")

    def test_product_catalogue_rejects_non_object_records(self):
        with self.assertRaisesRegex(
            api._MalformedProviderResponse, "non-object record"
        ):
            api._coinbase_product_catalogue_records([{"id": "BTC-USD", "base_currency": "BTC", "quote_currency": "USD", "status": "online", "trading_disabled": False, "base_increment": "0.00000001", "quote_increment": "0.01"}, None])

    def test_product_catalogue_rejects_missing_or_blank_identifiers(self):
        for record in ({"id": None}, {"id": ""}, {"base_currency": "BTC"}):
            with self.subTest(record=record):
                with self.assertRaisesRegex(
                    api._MalformedProviderResponse, "missing or invalid product identifier"
                ):
                    api._coinbase_product_catalogue_records([record])

    def test_product_catalogue_rejects_duplicate_identifiers_across_records(self):
        with self.assertRaisesRegex(
            api._MalformedProviderResponse, "duplicate product identifiers"
        ):
            api._coinbase_product_catalogue_records([
                {"id": "BTC-USD", "base_currency": "BTC", "quote_currency": "USD", "status": "online", "trading_disabled": False, "base_increment": "0.00000001", "quote_increment": "0.01"}, {"id": "BTC-USD", "base_currency": "BTC", "quote_currency": "USD", "status": "online", "trading_disabled": False, "base_increment": "0.00000001", "quote_increment": "0.01"}
            ])

    def test_empty_candle_page_is_valid_but_not_a_valid_final_snapshot(self):
        self.assertEqual(api._coinbase_page_rows_in_chronological_order([]), [])


    def test_product_catalogue_accepts_required_fields_with_expected_types(self):
        record = {"id": "BTC-USD", "base_currency": "BTC", "quote_currency": "USD",
                  "status": "online", "trading_disabled": False, "base_increment": "0.00000001", "quote_increment": "0.01"}
        self.assertEqual(api._coinbase_product_catalogue_records([record]), [record])

    def test_product_catalogue_rejects_invalid_currency_field_types(self):
        for field_name, invalid_value in (
            ("base_currency", None), ("base_currency", 1), ("base_currency", ""),
            ("quote_currency", None), ("quote_currency", False), ("quote_currency", " "),
        ):
            with self.subTest(field=field_name, value=invalid_value):
                record = {"id": "BTC-USD", "base_currency": "BTC", "quote_currency": "USD",
                          "status": "online", "trading_disabled": False, "base_increment": "0.00000001", "quote_increment": "0.01"}
                record[field_name] = invalid_value
                with self.assertRaises(api._MalformedProviderResponse):
                    api._coinbase_product_catalogue_records([record])

    def test_product_catalogue_rejects_missing_or_unknown_status(self):
        for invalid_status in (None, "", "ONLINE", "suspended", 1):
            with self.subTest(status=invalid_status):
                record = {"id": "BTC-USD", "base_currency": "BTC", "quote_currency": "USD",
                          "status": invalid_status, "trading_disabled": False, "base_increment": "0.00000001", "quote_increment": "0.01"}
                with self.assertRaisesRegex(api._MalformedProviderResponse, "field status"):
                    api._coinbase_product_catalogue_records([record])

    def test_product_catalogue_requires_boolean_trading_disabled(self):
        for invalid_flag in (None, 0, 1, "false", "true"):
            with self.subTest(flag=invalid_flag):
                record = {"id": "BTC-USD", "base_currency": "BTC", "quote_currency": "USD",
                          "status": "online", "trading_disabled": invalid_flag}
                with self.assertRaisesRegex(api._MalformedProviderResponse, "field trading_disabled"):
                    api._coinbase_product_catalogue_records([record])


    def test_product_catalogue_accepts_positive_decimal_increment_strings(self):
        record = {"id": "BTC-USD", "base_currency": "BTC", "quote_currency": "USD",
                  "status": "online", "trading_disabled": False,
                  "base_increment": "0.00000001", "quote_increment": "0.01"}
        self.assertEqual(api._coinbase_product_catalogue_records([record]), [record])

    def test_product_catalogue_rejects_missing_or_non_string_increments(self):
        for field_name, invalid_value in (
            ("base_increment", None), ("base_increment", 0.00000001),
            ("base_increment", 1), ("base_increment", True), ("base_increment", ""),
            ("quote_increment", None), ("quote_increment", 0.01),
            ("quote_increment", False), ("quote_increment", " "),
        ):
            with self.subTest(field=field_name, value=invalid_value):
                record = {"id": "BTC-USD", "base_currency": "BTC", "quote_currency": "USD",
                          "status": "online", "trading_disabled": False,
                          "base_increment": "0.00000001", "quote_increment": "0.01"}
                record[field_name] = invalid_value
                with self.assertRaisesRegex(api._MalformedProviderResponse, field_name):
                    api._coinbase_product_catalogue_records([record])

    def test_product_catalogue_rejects_non_finite_or_non_positive_increments(self):
        for invalid_value in ("NaN", "Infinity", "-Infinity", "0", "-0.01", "-1"):
            for field_name in ("base_increment", "quote_increment"):
                with self.subTest(field=field_name, value=invalid_value):
                    record = {"id": "BTC-USD", "base_currency": "BTC", "quote_currency": "USD",
                              "status": "online", "trading_disabled": False,
                              "base_increment": "0.00000001", "quote_increment": "0.01"}
                    record[field_name] = invalid_value
                    with self.assertRaises(api._MalformedProviderResponse):
                        api._coinbase_product_catalogue_records([record])

    def test_product_catalogue_rejects_malformed_increment_strings(self):
        for invalid_value in ("not-a-number", ".", "1e", "+"):
            with self.subTest(value=invalid_value):
                record = {"id": "BTC-USD", "base_currency": "BTC", "quote_currency": "USD",
                          "status": "online", "trading_disabled": False,
                          "base_increment": invalid_value, "quote_increment": "0.01"}
                with self.assertRaisesRegex(api._MalformedProviderResponse, "increment"):
                    api._coinbase_product_catalogue_records([record])


if __name__ == "__main__":
    unittest.main()

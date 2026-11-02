import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException
import cin_public_social_preview_api as api


class PreviewTests(unittest.TestCase):
    def setUp(self):
        api._cache.clear()
        api._failures.clear()

    @patch.dict(os.environ, {}, clear=True)
    def test_disabled_without_explicit_enable_and_makes_no_call(self):
        with patch.object(api, "fetch_public_observations") as fetch:
            with self.assertRaises(HTTPException) as err:
                api.social_sentiment_preview("bitcoin")
        self.assertEqual(err.exception.status_code, 404)
        fetch.assert_not_called()

    @patch.dict(os.environ, {"CIN_SOCIAL_PREVIEW_ENABLED": "true"}, clear=True)
    def test_nonexact_enable_is_disabled(self):
        with self.assertRaises(HTTPException) as err:
            api.social_sentiment_preview("bitcoin")
        self.assertEqual(err.exception.status_code, 404)

    @patch.dict(os.environ, {"CIN_SOCIAL_PREVIEW_ENABLED": "1"}, clear=True)
    def test_success_is_cached_and_callers_cannot_mutate_cache(self):
        with patch.object(api, "fetch_public_observations", return_value={"sentiment": {"label": "unavailable"}}) as fetch:
            first = api.social_sentiment_preview("bitcoin")
            first["sentiment"]["label"] = "changed"
            second = api.social_sentiment_preview("bitcoin")
        self.assertEqual(second["sentiment"]["label"], "unavailable")
        fetch.assert_called_once_with("bitcoin")

    @patch.dict(os.environ, {"CIN_SOCIAL_PREVIEW_ENABLED": "1"}, clear=True)
    def test_invalid_asset_never_calls_provider(self):
        with patch.object(api, "fetch_public_observations") as fetch:
            with self.assertRaises(HTTPException) as err:
                api.social_sentiment_preview("../../x")
        self.assertEqual(err.exception.status_code, 400)
        fetch.assert_not_called()

    @patch.dict(os.environ, {"CIN_SOCIAL_PREVIEW_ENABLED": "1"}, clear=True)
    def test_provider_failure_is_sanitized_and_not_cached(self):
        with patch.object(api, "fetch_public_observations", side_effect=ValueError("private provider data")) as fetch:
            for _ in range(2):
                with self.assertRaises(HTTPException) as err:
                    api.social_sentiment_preview("bitcoin")
                self.assertEqual(err.exception.status_code, 503)
                self.assertNotIn("private", err.exception.detail)
        self.assertEqual(fetch.call_count, 1)


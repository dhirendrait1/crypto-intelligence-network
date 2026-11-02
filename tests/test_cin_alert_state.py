import unittest

from cin_alert_state import alert_deduplication_key, decide_alert_emission


class AlertDeduplicationCooldownTests(unittest.TestCase):
    def test_key_is_stable(self):
        args = ("rule-1", "obs-2", "above-threshold")
        self.assertEqual(alert_deduplication_key(*args), alert_deduplication_key(*args))

    def test_key_uses_unambiguous_length_prefixes(self):
        self.assertNotEqual(
            alert_deduplication_key("a|b", "c", "d"),
            alert_deduplication_key("a", "b|c", "d"),
        )

    def test_empty_key_parts_rejected(self):
        with self.assertRaises(ValueError):
            alert_deduplication_key("rule", "", "above")

    def test_first_event_is_eligible(self):
        result = decide_alert_emission(
            deduplication_key="k", now="2026-10-28T00:00:00Z", cooldown_seconds=60
        )
        self.assertTrue(result["emit"])
        self.assertEqual(result["reason"], "no_prior_emission")

    def test_duplicate_is_suppressed_even_if_cooldown_elapsed(self):
        result = decide_alert_emission(
            deduplication_key="k", now="2026-10-28T00:10:00Z",
            cooldown_seconds=60, already_emitted=True,
        )
        self.assertFalse(result["emit"])
        self.assertEqual(result["reason"], "duplicate_event")

    def test_cooldown_suppresses_early_event(self):
        result = decide_alert_emission(
            deduplication_key="k", now="2026-10-28T00:00:30Z",
            cooldown_seconds=60, prior_emitted_at="2026-10-28T00:00:00Z",
        )
        self.assertEqual(result["reason"], "cooldown_active")
        self.assertEqual(result["cooldown_remaining_seconds"], 30)

    def test_event_is_eligible_at_exact_cooldown_boundary(self):
        result = decide_alert_emission(
            deduplication_key="k", now="2026-10-28T00:01:00Z",
            cooldown_seconds=60, prior_emitted_at="2026-10-28T00:00:00Z",
        )
        self.assertTrue(result["emit"])
        self.assertEqual(result["reason"], "cooldown_elapsed")

    def test_naive_or_invalid_timestamp_is_not_accepted(self):
        for now in ("2026-10-28T00:00:00", "not-a-time"):
            with self.subTest(now=now):
                result = decide_alert_emission(
                    deduplication_key="k", now=now, cooldown_seconds=60
                )
                self.assertFalse(result["emit"])
                self.assertEqual(result["status"], "invalid_input")

    def test_unknown_prior_time_fails_closed(self):
        result = decide_alert_emission(
            deduplication_key="k", now="2026-10-28T00:01:00Z",
            cooldown_seconds=60, prior_emitted_at="bad-time",
        )
        self.assertFalse(result["emit"])
        self.assertEqual(result["reason"], "prior_emission_time_unknown")

    def test_future_prior_time_fails_closed(self):
        result = decide_alert_emission(
            deduplication_key="k", now="2026-10-28T00:00:00Z",
            cooldown_seconds=60, prior_emitted_at="2026-10-28T00:01:00Z",
        )
        self.assertFalse(result["emit"])
        self.assertEqual(result["reason"], "clock_or_event_time_regression")

    def test_invalid_cooldown_rejected(self):
        for cooldown in (-1, True, 1.5):
            with self.subTest(cooldown=cooldown):
                result = decide_alert_emission(
                    deduplication_key="k", now="2026-10-28T00:00:00Z",
                    cooldown_seconds=cooldown,
                )
                self.assertEqual(result["status"], "invalid_input")


if __name__ == "__main__":
    unittest.main()

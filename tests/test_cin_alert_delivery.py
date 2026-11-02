import unittest

from cin_alert_delivery import (
    initial_delivery_state,
    record_delivery_attempt,
    record_delivery_result,
)


class AlertDeliveryStateTests(unittest.TestCase):
    def test_initial_state(self):
        state = initial_delivery_state("event-1", max_attempts=2)
        self.assertEqual(state["status"], "pending")
        self.assertEqual(state["attempt_count"], 0)
        self.assertEqual(state["max_attempts"], 2)

    def test_initial_state_rejects_bad_inputs(self):
        for event_id, limit in (("", 2), ("event", 0), ("event", True)):
            with self.subTest(event_id=event_id, limit=limit):
                with self.assertRaises(ValueError):
                    initial_delivery_state(event_id, limit)

    def test_attempt_increments_count_and_enters_sending(self):
        state = record_delivery_attempt(initial_delivery_state("e"))
        self.assertEqual(state["status"], "sending")
        self.assertEqual(state["attempt_count"], 1)

    def test_success_requires_timestamp_then_marks_delivered(self):
        sending = record_delivery_attempt(initial_delivery_state("e"))
        missing = record_delivery_result(sending, succeeded=True)
        self.assertEqual(missing["reason"], "delivery_timestamp_required")
        delivered = record_delivery_result(
            sending, succeeded=True, delivered_at="2026-10-28T00:00:00Z"
        )
        self.assertEqual(delivered["status"], "delivered")
        self.assertIsNone(delivered["last_error_code"])

    def test_failure_waits_for_retry_when_attempts_remain(self):
        sending = record_delivery_attempt(initial_delivery_state("e", max_attempts=2))
        failed_attempt = record_delivery_result(
            sending, succeeded=False, error_code="provider_timeout"
        )
        self.assertEqual(failed_attempt["status"], "retry_wait")
        retry = record_delivery_attempt(failed_attempt)
        self.assertEqual(retry["attempt_count"], 2)
        self.assertEqual(retry["status"], "sending")

    def test_failure_on_final_attempt_is_terminal(self):
        state = initial_delivery_state("e", max_attempts=1)
        sending = record_delivery_attempt(state)
        result = record_delivery_result(sending, succeeded=False, error_code="rejected")
        self.assertEqual(result["status"], "failed")

    def test_attempt_cannot_start_from_terminal_state(self):
        state = initial_delivery_state("e")
        sending = record_delivery_attempt(state)
        delivered = record_delivery_result(
            sending, succeeded=True, delivered_at="2026-10-28T00:00:00Z"
        )
        result = record_delivery_attempt(delivered)
        self.assertEqual(result["status"], "delivered")
        self.assertEqual(result["reason"], "status_not_attemptable")

    def test_result_requires_sending_state(self):
        result = record_delivery_result(initial_delivery_state("e"), succeeded=False, error_code="x")
        self.assertEqual(result["status"], "invalid_state")

    def test_failure_requires_stable_error_code(self):
        sending = record_delivery_attempt(initial_delivery_state("e"))
        result = record_delivery_result(sending, succeeded=False)
        self.assertEqual(result["reason"], "failure_error_code_required")

    def test_attempt_limit_cannot_be_exceeded(self):
        state = initial_delivery_state("e", max_attempts=1)
        sending = record_delivery_attempt(state)
        retry_state = {**sending, "status": "retry_wait"}
        result = record_delivery_attempt(retry_state)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], "attempt_limit_reached")


if __name__ == "__main__":
    unittest.main()

"""Offline contract tests for CIN shortlist JSON ranking."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cin_shortlist_scoring import WEIGHTS, SCORE_VERSION
from cin_shortlist_offline_cli import evaluate_snapshot, run_cli


def candidate(symbol, score=80, **gate_overrides):
    gates = dict.fromkeys(("security_clear", "liquidity_sufficient",
                           "data_reliable", "risk_acceptable"), True)
    gates.update(gate_overrides)
    return {"symbol": symbol, "scores": dict.fromkeys(WEIGHTS, score), "gates": gates}


class ShortlistOfflineCliTests(unittest.TestCase):
    def test_deterministic_rank_and_ties(self):
        result = evaluate_snapshot({"candidates": [
            candidate("ETH", 70), candidate("BTC", 90), candidate("ADA", 90)
        ]})
        self.assertEqual(result["score_version"], SCORE_VERSION)
        self.assertEqual([r["symbol"] for r in result["results"]], ["ADA", "BTC", "ETH"])

    def test_rejected_and_missing_data_preserved_without_scores(self):
        missing = candidate("MISS")
        del missing["scores"]["technical"]
        result = evaluate_snapshot({"candidates": [
            candidate("REJ", 100, security_clear=False), missing, candidate("OK", 60),
        ]})
        self.assertEqual(result["results"][0]["symbol"], "OK")
        self.assertEqual(set(r["status"] for r in result["results"]),
                         {"shortlist_eligible", "insufficient_data", "rejected"})
        self.assertTrue(all(r["score"] is None for r in result["results"][1:]))

    def test_input_requires_exact_shape_and_unique_symbols(self):
        bad_inputs = [
            [], {}, {"candidates": [], "extra": True}, {"candidates": {}},
            {"candidates": [candidate("BTC"), candidate("BTC")]},
            {"candidates": [{"symbol": "BTC"}]},
            {"candidates": [dict(candidate("BTC"), extra=1)]},
            {"candidates": [candidate("BTC")] * 101},
        ]
        for case in bad_inputs:
            with self.subTest(case=str(case)[:80]):
                with self.assertRaises(ValueError):
                    evaluate_snapshot(case)

    def test_cli_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text(json.dumps({"candidates": [candidate("BTC")]}), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = run_cli([str(path)])
            self.assertEqual(exit_code, 0)
            parsed = json.loads(output.getvalue())
            self.assertEqual(parsed["results"][0]["score"], "80.00")

    def test_cli_malformed_and_oversized_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            for content in ("not-json", "x" * 2_000_001):
                path.write_text(content, encoding="utf-8")
                errors = io.StringIO()
                with contextlib.redirect_stderr(errors):
                    result = run_cli([str(path)])
                self.assertEqual(result, 2)
                self.assertIn("CIN shortlist input error", errors.getvalue())


if __name__ == "__main__":
    unittest.main()

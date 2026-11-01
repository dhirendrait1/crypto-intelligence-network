"""Offline read-only JSON interface for CIN shortlist scoring.

Input must contain explicit analyst-provided scores and gate evidence.
No network access or market-data retrieval takes place in this module.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cin_shortlist_scoring import SCORE_VERSION, assess_candidate

MAX_INPUT_BYTES = 2_000_000
MAX_CANDIDATES = 100


def evaluate_snapshot(snapshot: object) -> dict:
    if not isinstance(snapshot, dict) or set(snapshot) != {"candidates"}:
        raise ValueError("expected a JSON object containing only 'candidates'")
    candidates = snapshot["candidates"]
    if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
        raise ValueError("candidates must be a list with at most 100 entries")
    results = []
    seen = set()
    for position, candidate in enumerate(candidates):
        if not isinstance(candidate, dict) or set(candidate) != {"symbol", "scores", "gates"}:
            raise ValueError(f"candidate {position}: expected symbol, scores and gates")
        result = assess_candidate(candidate["symbol"], candidate["scores"], candidate["gates"])
        if result["symbol"] in seen:
            raise ValueError(f"duplicate candidate symbol: {result['symbol']}")
        seen.add(result["symbol"])
        results.append(result)
    # Ranked eligible candidates first; preserve all rejected/insufficient entries.
    eligible = sorted(
        (r for r in results if r["status"] == "shortlist_eligible"),
        key=lambda r: (-float(r["score"]), r["symbol"]),
    )
    other = sorted((r for r in results if r["status"] != "shortlist_eligible"),
                   key=lambda r: (r["status"], r["symbol"]))
    return {"score_version": SCORE_VERSION, "results": eligible + other}


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate a CIN offline shortlist snapshot")
    parser.add_argument("input", type=Path, help="JSON snapshot file")
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            raw = handle.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError("input exceeds the 2 MB size limit")
        snapshot = json.loads(raw.decode("utf-8"))
        result = evaluate_snapshot(snapshot)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        print(f"CIN shortlist input error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())

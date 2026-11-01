"""Deterministic, read-only evidence scoring for CIN coin shortlists.

Pure functions: no provider calls, financial transactions, wallets or orders.
Callers must supply validated normalized scores and explicit eligibility evidence.
This is a library candidate; not wired to an API or a live shortlist.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Mapping, Any

SCORE_VERSION = "cin-shortlist-v1"
# 100 points. Individual dimension scores are on a [0, 100] scale.
WEIGHTS = {
    "market_regime": 10,
    "liquidity": 12,
    "technical": 12,
    "on_chain": 10,
    "tokenomics": 10,
    "derivatives": 8,
    "whale_flows": 7,
    "project_fundamentals": 8,
    "news_sentiment": 7,
    "relative_strength": 5,
    "risk_reward": 11,
}
assert sum(WEIGHTS.values()) == 100

REQUIRED_GATES = ("security_clear", "liquidity_sufficient", "data_reliable", "risk_acceptable")


def _score_number(value: Any, name: str) -> Decimal:
    """Parse strict finite scalars; never quietly coerce booleans or non-finite data."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError(f"{name}: expected finite numeric score")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{name}: empty score")
    try:
        score = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{name}: invalid numeric score") from None
    if not score.is_finite() or not (0 <= score <= 100):
        raise ValueError(f"{name}: score must be finite and between 0 and 100")
    return score


def classify(score: Decimal) -> str:
    if score >= 85:
        return "A+"
    if score >= 75:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    if score >= 35:
        return "D"
    return "F"


def assess_candidate(
    symbol: str,
    scores: Mapping[str, Any],
    gates: Mapping[str, bool],
) -> dict[str, Any]:
    """Rank only complete, eligible, evidence-supported candidates.

    A missing dimension is not assigned a synthetic 0 or neutral value.
    Failed gates override the aggregate score. Unknown gates fail closed.
    """
    if not isinstance(symbol, str) or not symbol or symbol != symbol.strip() or len(symbol) > 24:
        raise ValueError("symbol must be a non-empty trimmed string (max 24 chars)")
    if not isinstance(scores, Mapping) or not isinstance(gates, Mapping):
        raise ValueError("scores and gates must be mappings")
    if any(key not in WEIGHTS for key in scores):
        raise ValueError("unknown scoring dimension")
    if any(key not in REQUIRED_GATES for key in gates):
        raise ValueError("unknown eligibility gate")
    if any(type(value) is not bool for value in gates.values()):
        raise ValueError("eligibility gates must be booleans")
    missing_gates = [name for name in REQUIRED_GATES if name not in gates]
    failed_gates = [name for name in REQUIRED_GATES if gates.get(name) is False]
    missing_dimensions = [name for name in WEIGHTS if name not in scores]
    parsed = {key: _score_number(value, key) for key, value in scores.items()}
    base = {
        "symbol": symbol,
        "score_version": SCORE_VERSION,
        "missing_dimensions": missing_dimensions,
        "missing_gates": missing_gates,
        "failed_gates": failed_gates,
    }
    if failed_gates:
        return {**base, "status": "rejected", "score": None, "classification": None}
    if missing_gates or missing_dimensions:
        return {**base, "status": "insufficient_data", "score": None, "classification": None}
    weighted = sum((parsed[key] * weight for key, weight in WEIGHTS.items()), Decimal(0)) / Decimal(100)
    # Retain exact Decimal arithmetic until the presentation boundary.
    rounded = weighted.quantize(Decimal("0.01"))
    return {
        **base,
        "status": "shortlist_eligible",
        "score": str(rounded),
        "classification": classify(weighted),
    }

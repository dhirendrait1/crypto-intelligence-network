"""Pure, read-only validation of explicitly supplied level-two order-book evidence.

This does not fetch, place, route or manage orders. Declared depth and spread
are diagnostics at the supplied snapshot, not guaranteed execution liquidity.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

MAX_AGE_SECONDS = 30
MAX_LEVELS = 200


def _positive(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError(f"{field}: expected positive decimal")
    if isinstance(value, str) and (not value.strip() or len(value) > 80):
        raise ValueError(f"{field}: invalid decimal string")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field}: invalid decimal") from None
    if not result.is_finite() or result <= 0:
        raise ValueError(f"{field}: expected finite positive decimal")
    return result


def _levels(raw: Any, side: str) -> list[tuple[Decimal, Decimal]]:
    if not isinstance(raw, list) or not (1 <= len(raw) <= MAX_LEVELS):
        raise ValueError(f"{side}: expected 1..{MAX_LEVELS} levels")
    output = []
    for i, level in enumerate(raw):
        if not isinstance(level, (list, tuple)) or len(level) != 2:
            raise ValueError(f"{side}[{i}]: expected [price, base_quantity]")
        price = _positive(level[0], f"{side}[{i}].price")
        size = _positive(level[1], f"{side}[{i}].size")
        if output and (price >= output[-1][0] if side == "bids" else price <= output[-1][0]):
            raise ValueError(f"{side}: levels must have strictly ordered distinct prices")
        output.append((price, size))
    return output


def assess_order_book(
    snapshot: Mapping[str, Any],
    *,
    now: datetime | None = None,
    max_spread_bps: Any = "30",
    min_depth_quote_each_side: Any = "10000",
) -> dict[str, Any]:
    """Require independent identity, timestamp, spread and depth evidence.

    Quote depth is the sum of price * base quantity across supplied levels.
    It is not a fill or slippage guarantee and cannot infer other risk gates.
    """
    required = {"symbol", "source", "observed_at", "bids", "asks"}
    if not isinstance(snapshot, Mapping) or set(snapshot) != required:
        raise ValueError("expected symbol, source, observed_at, bids, asks")
    for field, max_length in (("symbol", 24), ("source", 160)):
        value = snapshot[field]
        if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > max_length or any(ord(c) < 33 or ord(c) == 127 for c in value):
            raise ValueError(f"{field}: invalid identity")
    observed = snapshot["observed_at"]
    if not isinstance(observed, str) or not observed or len(observed) > 64:
        raise ValueError("observed_at: invalid timestamp")
    try:
        timestamp = datetime.fromisoformat(observed.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("observed_at: invalid ISO timestamp") from None
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("observed_at: timezone required")
    current = datetime.now(timezone.utc) if now is None else now
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now: timezone required")
    age = (current.astimezone(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds()
    if age < 0:
        raise ValueError("observed_at: future snapshot")
    limit_spread = _positive(max_spread_bps, "max_spread_bps")
    limit_depth = _positive(min_depth_quote_each_side, "min_depth_quote_each_side")
    bids, asks = _levels(snapshot["bids"], "bids"), _levels(snapshot["asks"], "asks")
    best_bid, best_ask = bids[0][0], asks[0][0]
    if best_bid >= best_ask:
        raise ValueError("crossed or locked order book")
    mid = (best_bid + best_ask) / 2
    spread_bps = (best_ask - best_bid) * Decimal(10000) / mid
    bid_depth = sum((price * size for price, size in bids), Decimal(0))
    ask_depth = sum((price * size for price, size in asks), Decimal(0))
    fresh = age <= MAX_AGE_SECONDS
    sufficient = fresh and spread_bps <= limit_spread and min(bid_depth, ask_depth) >= limit_depth
    return {
        "symbol": snapshot["symbol"],
        "source": snapshot["source"],
        "observed_at": timestamp.astimezone(timezone.utc).isoformat(),
        "age_seconds": int(age),
        "snapshot_fresh": fresh,
        "spread_bps": str(spread_bps.quantize(Decimal("0.0001"))),
        "bid_depth_quote": str(bid_depth),
        "ask_depth_quote": str(ask_depth),
        "liquidity_sufficient": sufficient,
        "depth_interpretation": "reported_snapshot_levels_not_execution_guarantee",
        "source_verification": "supplied_not_independently_verified",
    }

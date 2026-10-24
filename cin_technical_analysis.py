"""Read-only, deterministic technical analysis from caller-supplied OHLC candles.

No exchange calls, account access, or trade execution. Outputs are descriptive scenarios,
not investment advice or guaranteed price predictions.
"""
from __future__ import annotations

from typing import Any


def _ema(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    alpha = 2.0 / (period + 1)
    prev = seed
    for i in range(period, len(values)):
        prev = values[i] * alpha + prev * (1 - alpha)
        out[i] = prev
    return out


def _rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) <= period:
        return None
    gains = [max(closes[i] - closes[i - 1], 0.0) for i in range(1, len(closes))]
    losses = [max(closes[i - 1] - closes[i], 0.0) for i in range(1, len(closes))]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)


def _atr(candles: list[dict[str, float]], period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None
    trs = []
    for i, c in enumerate(candles):
        prev_close = candles[i - 1]["close"] if i else c["close"]
        trs.append(max(c["high"] - c["low"], abs(c["high"] - prev_close), abs(c["low"] - prev_close)))
    return round(sum(trs[-period:]) / period, 8)


def _swings(candles: list[dict[str, float]], radius: int = 2) -> tuple[list[float], list[float]]:
    highs, lows = [], []
    for i in range(radius, len(candles) - radius):
        h, lo = candles[i]["high"], candles[i]["low"]
        if all(h > candles[j]["high"] for j in range(i - radius, i + radius + 1) if j != i):
            highs.append(h)
        if all(lo < candles[j]["low"] for j in range(i - radius, i + radius + 1) if j != i):
            lows.append(lo)
    return highs, lows


def analyze_ohlc(candles: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze chronological candles; minimum 35 candles recommended for MACD."""
    if len(candles) < 5 or len(candles) > 500:
        raise ValueError("Provide between 5 and 500 chronological OHLC candles.")
    normalized: list[dict[str, float]] = []
    for i, row in enumerate(candles):
        try:
            o, h, lo, c = (float(row[k]) for k in ("open", "high", "low", "close"))
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"Candle {i} must contain numeric open, high, low, and close.") from None
        if not all(map(lambda x: x == x and abs(x) != float("inf"), (o, h, lo, c))):
            raise ValueError(f"Candle {i} contains a non-finite price.")
        if min(o, h, lo, c) <= 0 or h < max(o, c, lo) or lo > min(o, c, h):
            raise ValueError(f"Candle {i} has inconsistent OHLC prices.")
        normalized_row = {"open": o, "high": h, "low": lo, "close": c}
        if "volume" in row and row["volume"] is not None:
            try:
                volume = float(row["volume"])
            except (TypeError, ValueError):
                raise ValueError(f"Candle {i} volume must be numeric when supplied.") from None
            if not (volume == volume and abs(volume) != float("inf")) or volume < 0:
                raise ValueError(f"Candle {i} volume must be finite and non-negative.")
            normalized_row["volume"] = volume
        normalized.append(normalized_row)

    volume_count = sum("volume" in row for row in normalized)
    if volume_count not in (0, len(normalized)):
        raise ValueError("Volume must be supplied for every candle or omitted for every candle.")

    closes = [x["close"] for x in normalized]
    last = closes[-1]
    swing_highs, swing_lows = _swings(normalized)
    high_pattern = "insufficient_swings"
    low_pattern = "insufficient_swings"
    if len(swing_highs) >= 2:
        high_pattern = "HH" if swing_highs[-1] > swing_highs[-2] else "LH" if swing_highs[-1] < swing_highs[-2] else "EQH"
    if len(swing_lows) >= 2:
        low_pattern = "HL" if swing_lows[-1] > swing_lows[-2] else "LL" if swing_lows[-1] < swing_lows[-2] else "EQL"

    previous_high = swing_highs[-1] if swing_highs else None
    previous_low = swing_lows[-1] if swing_lows else None
    structure_event = "none"
    bias = "neutral"
    if previous_high is not None and last > previous_high:
        structure_event, bias = "BOS_up" if high_pattern == "HH" and low_pattern == "HL" else "CHOCH_up", "bullish"
    elif previous_low is not None and last < previous_low:
        structure_event, bias = "BOS_down" if high_pattern == "LH" and low_pattern == "LL" else "CHOCH_down", "bearish"
    elif high_pattern == "HH" and low_pattern == "HL":
        bias = "bullish"
    elif high_pattern == "LH" and low_pattern == "LL":
        bias = "bearish"

    ema12, ema26 = _ema(closes, 12), _ema(closes, 26)
    macd_line = [None if a is None or b is None else a - b for a, b in zip(ema12, ema26)]
    macd_valid = [x for x in macd_line if x is not None]
    signal_series = _ema(macd_valid, 9)
    macd = macd_valid[-1] if macd_valid else None
    signal = signal_series[-1] if signal_series and signal_series[-1] is not None else None
    atr = _atr(normalized)
    targets = None
    if atr is not None and bias in ("bullish", "bearish"):
        direction = 1 if bias == "bullish" else -1
        targets = {f"T{i}": round(last + direction * atr * multiplier, 8) for i, multiplier in enumerate((1, 2, 3), 1)}

    return {
        "service": "cin",
        "mode": "read_only",
        "input": {"candle_count": len(normalized), "last_close": last, "chronological_order_required": True},
        "market_structure": {
            "swing_high_pattern": high_pattern,
            "swing_low_pattern": low_pattern,
            "latest_swing_high": previous_high,
            "latest_swing_low": previous_low,
            "structure_event": structure_event,
            "directional_bias": bias,
        },
        "indicators": {
            "rsi_14": _rsi(closes),
            "macd_line": round(macd, 8) if macd is not None else None,
            "macd_signal": round(signal, 8) if signal is not None else None,
            "macd_histogram": round(macd - signal, 8) if macd is not None and signal is not None else None,
            "atr_14": atr,
            "volume_latest": normalized[-1].get("volume"),
            "volume_average_20": round(sum(row["volume"] for row in normalized[-20:]) / min(20, len(normalized)), 8) if volume_count else None,
            "relative_volume_20": round(normalized[-1]["volume"] / (sum(row["volume"] for row in normalized[-20:]) / min(20, len(normalized))), 4) if volume_count and sum(row["volume"] for row in normalized[-20:]) > 0 else None,
            "volume_analysis_status": "available" if volume_count else "not_supplied",
        },
        "liquidity_reference_levels": {
            "buy_side_reference": previous_high,
            "sell_side_reference": previous_low,
            "note": "Swing references only; not verified resting liquidity or an order-book measurement."
        },
        "scenario_targets": {
            "status": "illustrative_atr_scenarios" if targets else "unavailable_insufficient_data_or_neutral_bias",
            "targets": targets,
            "method": "last close +/- 1x, 2x, 3x ATR(14), only when directional bias is present",
        },
        "limitations": [
            "Caller-supplied OHLC data is not independently verified.",
            "Swing structure uses a two-candle confirmation window and can lag.",
            "Targets are illustrative volatility scenarios, not predictions or trade instructions.",
            "No entry/exit orders are generated or executed."
        ],
    }

"""Explicitly gated preview of public social keyword hints; no forecast."""
from __future__ import annotations

import copy
import os
import threading
import time

from fastapi import APIRouter, HTTPException

try:
    from app.cin_public_social_mastodon import fetch_public_observations
except ModuleNotFoundError as exc:
    if exc.name not in {"app", "app.cin_public_social_mastodon"}:
        raise
    from cin_public_social_mastodon import fetch_public_observations

router = APIRouter(tags=["experimental-social-preview"])
_CACHE_TTL_SECONDS = 300
_cache = {}
_failures = {}
_lock = threading.Lock()


@router.get("/research/social-sentiment-preview/{asset_id}")
def social_sentiment_preview(asset_id: str):
    """Experimental public observations, disabled unless explicitly enabled."""
    if os.getenv("CIN_SOCIAL_PREVIEW_ENABLED") != "1":
        raise HTTPException(status_code=404, detail="Not found")
    if asset_id not in {"bitcoin", "ethereum"}:
        raise HTTPException(status_code=400, detail="Unsupported asset")
    # Serialize requests per process: no duplicate provider calls on concurrent hits.
    with _lock:
        now = time.monotonic()
        cached = _cache.get(asset_id)
        if cached and 0 <= now - cached[0] < _CACHE_TTL_SECONDS:
            result = copy.deepcopy(cached[1])
            result["cache_age_seconds"] = round(now - cached[0], 2)
            return result
        failed_at = _failures.get(asset_id)
        if failed_at is not None and 0 <= now - failed_at < 60:
            raise HTTPException(status_code=503, detail="Social provider temporarily unavailable")
        try:
            result = fetch_public_observations(asset_id)
        except Exception as exc:
            # Avoid repeated requests during provider outages.
            _failures[asset_id] = time.monotonic()
            # Do not leak provider bodies, exception text, or URLs to API clients.
            raise HTTPException(status_code=503, detail="Social provider unavailable or response invalid") from exc
        _failures.pop(asset_id, None)
        _cache[asset_id] = (time.monotonic(), copy.deepcopy(result))
        result["cache_age_seconds"] = 0
        return result


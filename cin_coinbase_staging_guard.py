"""In-process staging-only auth and bounded outbound-request budget.

Not production authentication/rate limiting: process-local state cannot
coordinate replicas or restarts. Router must remain unmounted in production.
"""
from __future__ import annotations

from collections import deque
import hmac
import os
import threading
import time
from fastapi import HTTPException, Request

WINDOW_SECONDS = 60.0
MAX_REQUESTS = 4
MAX_PROVIDER_GETS = 8  # reserve worst case: product status + L2 book
_LOCK = threading.Lock()
_REQUESTS: deque[float] = deque()
_PROVIDER_RESERVATIONS: deque[tuple[float, int]] = deque()


def require_staging_access(request: Request) -> None:
    # The disabled gate is checked BEFORE header/token interpretation.
    if os.environ.get("CIN_COINBASE_RESEARCH_ENABLED") != "1" or os.environ.get("CIN_COINBASE_RESEARCH_STAGE") != "staging":
        raise HTTPException(status_code=404, detail="Research route unavailable")
    token = os.environ.get("CIN_COINBASE_RESEARCH_TOKEN", "")
    if len(token) < 32 or len(token) > 512 or token.strip() != token:
        raise HTTPException(status_code=503, detail="Staging authentication unavailable")
    values = request.headers.getlist("authorization")
    if len(values) != 1 or not values[0].startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Bearer"})
    credential = values[0][7:]
    if not credential or not hmac.compare_digest(credential, token):
        raise HTTPException(status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Bearer"})


def reserve_research_budget() -> None:
    """Reserve both possible public GETs before entering any provider code.

    Process-local only; release does not refund failed calls (conservative).
    """
    now = time.monotonic()
    with _LOCK:
        while _REQUESTS and now - _REQUESTS[0] >= WINDOW_SECONDS:
            _REQUESTS.popleft()
        while _PROVIDER_RESERVATIONS and now - _PROVIDER_RESERVATIONS[0][0] >= WINDOW_SECONDS:
            _PROVIDER_RESERVATIONS.popleft()
        if len(_REQUESTS) >= MAX_REQUESTS or sum(amount for _, amount in _PROVIDER_RESERVATIONS) + 2 > MAX_PROVIDER_GETS:
            raise HTTPException(status_code=429, detail="Staging research request budget exhausted", headers={"Retry-After": "60"})
        _REQUESTS.append(now)
        _PROVIDER_RESERVATIONS.append((now, 2))

"""Read-only, allowlisted public evidence ingestion for CIN (stdlib only).

This first connector retrieves public GitHub repository metadata for Ethereum
developer-activity context. Retrieval is not independent claim verification.
No tokens, wallet access, trading, or arbitrary URL fetching are supported.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ALLOWED_REPOSITORIES = (
    "ethereum/go-ethereum",
    "ethereum/consensus-specs",
    "ethereum/ethereum-org-website",
)
GITHUB_API_ROOT = "https://api.github.com/repos/"
TIMEOUT_SECONDS = 8
MAX_RESPONSE_BYTES = 1_000_000
FRESHNESS_WINDOW_SECONDS = 7 * 24 * 60 * 60


class EvidenceSourceError(RuntimeError):
    """Raised when a public evidence source cannot be retrieved safely."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _freshness_status(payload: dict[str, Any], *, now: datetime | None = None) -> str:
    """Classify source metadata age without treating freshness as verification."""
    timestamp = payload.get("pushed_at") or payload.get("updated_at")
    if timestamp is None:
        return "unknown"
    # _validate_metadata has already guaranteed a timezone-aware timestamp.
    source_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    current_time = now or datetime.now(timezone.utc)
    age_seconds = (current_time - source_time).total_seconds()
    # Future timestamps are not considered fresh; this can indicate clock skew
    # or unexpected upstream data and should be reviewed by policy.
    if age_seconds < 0:
        return "unknown"
    if age_seconds <= FRESHNESS_WINDOW_SECONDS:
        return "fresh"
    return "stale"


def _validate_metadata(payload: dict[str, Any]) -> tuple[str, list[str]]:
    """Reject malformed metadata and report whether expected fields are present."""
    branch = payload.get("default_branch")
    if branch is not None and (not isinstance(branch, str) or not branch.strip()):
        raise EvidenceSourceError("GitHub default_branch must be a non-empty string or null")

    for field in ("pushed_at", "updated_at"):
        value = payload.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            raise EvidenceSourceError(f"GitHub {field} must be an ISO-8601 timestamp or null")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise EvidenceSourceError(f"GitHub {field} must be an ISO-8601 timestamp or null") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise EvidenceSourceError(f"GitHub {field} timestamp must include a timezone")

    for field in ("stargazers_count", "forks_count", "open_issues_count"):
        value = payload.get(field)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            raise EvidenceSourceError(f"GitHub {field} must be a non-negative integer or null")

    archived = payload.get("archived")
    if archived is not None and not isinstance(archived, bool):
        raise EvidenceSourceError("GitHub archived must be a boolean or null")

    expected_fields = (
        "default_branch", "pushed_at", "updated_at", "stargazers_count",
        "forks_count", "open_issues_count", "archived",
    )
    # Missing or null fields remain usable as partial evidence, but must not be
    # represented as a complete metadata snapshot. Return the exact gaps too.
    missing_fields = [
        field for field in expected_fields
        if field not in payload or payload[field] is None
    ]
    return ("complete" if not missing_fields else "partial"), missing_fields


def fetch_github_repository_evidence(
    repository: str = "ethereum/go-ethereum",
    *,
    timeout: int = TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Fetch a small set of public repository metadata; keep evidence unverified."""
    if repository not in ALLOWED_REPOSITORIES:
        raise ValueError("Repository is not on CIN's public-source allowlist")
    if timeout < 1 or timeout > 15:
        raise ValueError("timeout must be between 1 and 15 seconds")

    url = GITHUB_API_ROOT + repository
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Crypto-Intelligence-Network/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise EvidenceSourceError(f"GitHub returned HTTP {response.status}")
            response_bytes = response.read(MAX_RESPONSE_BYTES + 1)
            if len(response_bytes) > MAX_RESPONSE_BYTES:
                raise EvidenceSourceError("GitHub response exceeded the 1 MB size limit")
            payload = json.loads(response_bytes.decode("utf-8"))
    except HTTPError as exc:
        raise EvidenceSourceError(f"GitHub returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise EvidenceSourceError(f"Public GitHub metadata retrieval failed: {type(exc).__name__}") from exc

    # Validate the response shape before calling string methods. Upstream JSON
    # is external evidence and may be malformed or unexpectedly typed.
    if not isinstance(payload, dict):
        raise EvidenceSourceError("GitHub response must be a JSON object")
    full_name = payload.get("full_name")
    if not isinstance(full_name, str) or full_name.lower() != repository:
        raise EvidenceSourceError("GitHub response did not match the requested repository")
    metadata_completeness, metadata_missing_fields = _validate_metadata(payload)
    source_timestamp_field = (
        "pushed_at" if payload.get("pushed_at") else
        "updated_at" if payload.get("updated_at") else None
    )

    retrieved_at = _utc_now()
    freshness_status = _freshness_status(payload)
    return {
        "symbol": "ETH",
        "category": "developer_activity",
        "metric": "public_repository_activity_metadata",
        "source_name": "GitHub public repository API",
        "source_url": url,
        "repository": repository,
        "published_at": payload.get("pushed_at") or payload.get("updated_at"),
        "source_timestamp_field": source_timestamp_field,
        "retrieved_at": retrieved_at,
        "measurement_period": "repository metadata snapshot",
        "value": {
            "default_branch": payload.get("default_branch"),
            "pushed_at": payload.get("pushed_at"),
            "updated_at": payload.get("updated_at"),
            "stargazers_count": payload.get("stargazers_count"),
            "forks_count": payload.get("forks_count"),
            "open_issues_count": payload.get("open_issues_count"),
            "archived": payload.get("archived"),
        },
        "unit": "repository metadata fields",
        "retrieval_status": "success",
        "validation_status": "metadata_shape_validated",
        "metadata_completeness": metadata_completeness,
        "metadata_missing_fields": metadata_missing_fields,
        "freshness_status": freshness_status,
        "claim_verification_status": "unverified",
        "independently_verified": False,
        "provenance": "public GitHub REST API; allowlisted repository",
        "limitations": [
            "Repository activity is only a partial proxy for ecosystem development.",
            "A successful API response does not verify project quality, adoption, security, or investment merit.",
            "GitHub metadata is not a complete measure of all Ethereum development.",
        ],
    }

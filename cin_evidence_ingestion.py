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


class EvidenceSourceError(RuntimeError):
    """Raised when a public evidence source cannot be retrieved safely."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
            payload = json.loads(response.read(1_000_000).decode("utf-8"))
    except HTTPError as exc:
        raise EvidenceSourceError(f"GitHub returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise EvidenceSourceError(f"Public GitHub metadata retrieval failed: {type(exc).__name__}") from exc

    # Validate the provider identity before normalizing it. Malformed JSON must
    # become a controlled source error rather than an AttributeError.
    if not isinstance(payload, dict):
        raise EvidenceSourceError("GitHub response payload must be a JSON object")
    full_name = payload.get("full_name")
    if not isinstance(full_name, str) or full_name.lower() != repository:
        raise EvidenceSourceError("GitHub response did not match the requested repository")

    string_fields = ("default_branch",)
    timestamp_fields = ("pushed_at", "updated_at")
    integer_fields = ("stargazers_count", "forks_count", "open_issues_count")
    missing_fields = []
    invalid_fields = []

    for field in string_fields:
        value = payload.get(field)
        if value is None:
            missing_fields.append(field)
        elif not isinstance(value, str) or not value.strip():
            invalid_fields.append(field)

    for field in timestamp_fields:
        value = payload.get(field)
        if value is None:
            missing_fields.append(field)
            continue
        if not isinstance(value, str):
            invalid_fields.append(field)
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                invalid_fields.append(field)
        except ValueError:
            invalid_fields.append(field)

    for field in integer_fields:
        value = payload.get(field)
        if value is None:
            missing_fields.append(field)
        elif isinstance(value, bool) or not isinstance(value, int) or value < 0:
            invalid_fields.append(field)

    archived = payload.get("archived")
    if archived is None:
        missing_fields.append("archived")
    elif not isinstance(archived, bool):
        invalid_fields.append("archived")

    if invalid_fields:
        raise EvidenceSourceError(
            "GitHub response contained invalid field types or values: "
            + ", ".join(sorted(set(invalid_fields)))
        )

    retrieved_at = _utc_now()
    return {
        "symbol": "ETH",
        "category": "developer_activity",
        "metric": "public_repository_activity_metadata",
        "source_name": "GitHub public repository API",
        "source_url": url,
        "repository": repository,
        "published_at": payload.get("pushed_at") or payload.get("updated_at"),
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
        "validation_status": "metadata_shape_validated" if not missing_fields else "metadata_partial",
        "missing_fields": sorted(set(missing_fields)),
        "freshness_status": "requires_policy_evaluation",
        "claim_verification_status": "unverified",
        "independently_verified": False,
        "provenance": "public GitHub REST API; allowlisted repository",
        "limitations": [
            "Repository activity is only a partial proxy for ecosystem development.",
            "A successful API response does not verify project quality, adoption, security, or investment merit.",
            "GitHub metadata is not a complete measure of all Ethereum development.",
        ],
    }

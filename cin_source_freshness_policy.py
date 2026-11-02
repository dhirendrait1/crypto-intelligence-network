"""Fail-closed source/data-type freshness policy registry for CIN.

No numeric policies are preconfigured: thresholds must be explicitly reviewed
and added for a specific source_id + data_type pair. Unknown pairs stay unknown.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class FreshnessPolicy:
    source_id: str
    data_type: str
    max_age_seconds: int
    future_tolerance_seconds: int = 0

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.data_type.strip():
            raise ValueError("source_id and data_type must be non-empty")
        if isinstance(self.max_age_seconds, bool) or not isinstance(self.max_age_seconds, int) or self.max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be a positive integer")
        if (isinstance(self.future_tolerance_seconds, bool)
                or not isinstance(self.future_tolerance_seconds, int)
                or self.future_tolerance_seconds < 0):
            raise ValueError("future_tolerance_seconds must be a non-negative integer")


# Deliberately empty until CIN has approved source- and data-type-specific limits.
# Do not populate this with guessed universal thresholds.
DEFAULT_FRESHNESS_POLICIES: Mapping[tuple[str, str], FreshnessPolicy] = {}


def resolve_freshness_policy(
    source_id: object,
    data_type: object,
    *,
    policies: Mapping[tuple[str, str], FreshnessPolicy] = DEFAULT_FRESHNESS_POLICIES,
) -> FreshnessPolicy | None:
    """Return an exact configured policy; never fall back to a universal limit."""
    if not isinstance(source_id, str) or not source_id.strip():
        return None
    if not isinstance(data_type, str) or not data_type.strip():
        return None
    policy = policies.get((source_id.strip(), data_type.strip()))
    if policy is None:
        return None
    if policy.source_id != source_id.strip() or policy.data_type != data_type.strip():
        return None
    return policy

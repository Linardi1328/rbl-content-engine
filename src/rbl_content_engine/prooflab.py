"""ProofLab verification boundary for RBL Media Intelligence.

This module intentionally contains no network, publishing, or model calls. It provides the
contract that future AI content generation must pass before factual claims can become
publish-ready.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    UNSUPPORTED = "unsupported"
    CONFLICTING = "conflicting"


@dataclass(frozen=True)
class VerifiedClaim:
    claim_id: str
    text: str
    evidence_refs: tuple[str, ...]
    status: VerificationStatus

    @property
    def publishable(self) -> bool:
        return self.status is VerificationStatus.VERIFIED and bool(self.evidence_refs)


def require_verified_claims(claims: tuple[VerifiedClaim, ...]) -> tuple[VerifiedClaim, ...]:
    """Fail closed when content contains unsupported or conflicting factual claims."""
    blocked = tuple(claim for claim in claims if not claim.publishable)
    if blocked:
        blocked_ids = ", ".join(claim.claim_id for claim in blocked)
        raise ValueError(f"ProofLab blocked unverified claims: {blocked_ids}")
    return claims

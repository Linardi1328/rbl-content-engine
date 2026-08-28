"""Provider-neutral AI generation contracts for RBL Media Intelligence.

Phase 0/1 remains human-approval-first. This file defines interfaces only; it does not call
an LLM, publish content, or perform external side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .prooflab import VerifiedClaim, require_verified_claims


@dataclass(frozen=True)
class ContentGenerationRequest:
    platform: str
    objective: str
    claims: tuple[VerifiedClaim, ...]


@dataclass(frozen=True)
class ContentDraft:
    platform: str
    body: str
    source_claim_ids: tuple[str, ...]
    approval_required: bool = True


class ContentGenerator(Protocol):
    def generate(self, request: ContentGenerationRequest) -> ContentDraft: ...


def prepare_generation_request(request: ContentGenerationRequest) -> ContentGenerationRequest:
    """Validate factual inputs before any future model provider receives them."""
    require_verified_claims(request.claims)
    return request

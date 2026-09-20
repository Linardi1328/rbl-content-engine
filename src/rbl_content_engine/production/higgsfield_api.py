"""Official Higgsfield API adapter for RBL launch-video production.

This module deliberately lazy-loads the official SDK so core/offline tests remain
network-free. API credentials are read only by the official SDK from environment
variables when a live execution method is invoked.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from typing import Any, Mapping, Protocol

from .providers import CostQuote, CostUnit


HIGGSFIELD_API_PROVIDER_ID = "higgsfield_api"
SEEDANCE_25_TEXT_TO_VIDEO_APPLICATION = "bytedance/seedance-2.5/text-to-video"


class HiggsfieldSdkClient(Protocol):
    def submit(self, application: str, arguments: Mapping[str, Any]) -> Any: ...
    def upload_file(self, path: str | Path) -> str: ...


@dataclass(frozen=True)
class HiggsfieldApiGenerationRequest:
    application: str
    arguments: Mapping[str, Any]
    quote_usd: Decimal
    purpose: str

    def __post_init__(self) -> None:
        if not self.application.strip():
            raise ValueError("application must not be empty")
        if self.application == "LIVE_CATALOG_REQUIRED" or "$" in self.application:
            raise ValueError("application must be resolved from the live Higgsfield API catalog")
        if self.quote_usd < 0:
            raise ValueError("quote_usd must be non-negative")
        if not self.purpose.strip():
            raise ValueError("purpose must not be empty")

    def quote(self) -> CostQuote:
        return CostQuote(
            provider_id=HIGGSFIELD_API_PROVIDER_ID,
            amount=self.quote_usd,
            unit=CostUnit.USD,
            source="HIGGSFIELD_API_CATALOG_OR_ESTIMATE",
        )


@dataclass(frozen=True)
class HiggsfieldApiSubmission:
    request_id: str
    application: str
    purpose: str

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id must not be empty")


def load_official_higgsfield_client() -> HiggsfieldSdkClient:
    """Create the official SDK client only when a live API call is requested."""
    try:
        module = import_module("higgsfield_client")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "official Higgsfield API SDK is not installed; run uv sync --locked"
        ) from exc

    client_type = getattr(module, "SyncClient", None)
    if client_type is None:
        raise RuntimeError("installed higgsfield_client has no SyncClient")
    return client_type()


def upload_reference(
    path: str | Path,
    *,
    client: HiggsfieldSdkClient | None = None,
) -> str:
    actual_client = client or load_official_higgsfield_client()
    uploaded_url = actual_client.upload_file(str(path))
    if not isinstance(uploaded_url, str) or not uploaded_url.strip():
        raise RuntimeError("Higgsfield API upload returned no public URL")
    return uploaded_url


def submit_generation(
    request: HiggsfieldApiGenerationRequest,
    *,
    client: HiggsfieldSdkClient | None = None,
) -> tuple[HiggsfieldApiSubmission, Any]:
    """Submit exactly one billable request and return its controller.

    This function never retries a mutation. A caller must resolve the original
    request outcome before deciding whether another paid submission is warranted.
    """
    actual_client = client or load_official_higgsfield_client()
    controller = actual_client.submit(request.application, dict(request.arguments))
    request_id = getattr(controller, "request_id", None)
    if not isinstance(request_id, str) or not request_id.strip():
        raise RuntimeError("Higgsfield API submit returned no request_id")
    return (
        HiggsfieldApiSubmission(
            request_id=request_id,
            application=request.application,
            purpose=request.purpose,
        ),
        controller,
    )


def wait_for_result(controller: Any) -> Mapping[str, Any]:
    """Wait on an already-submitted request controller; never resubmit."""
    get_result = getattr(controller, "get", None)
    if not callable(get_result):
        raise RuntimeError("request controller has no get() method")
    result = get_result()
    if not isinstance(result, Mapping):
        raise RuntimeError("Higgsfield API result must be a mapping")
    return result


def extract_first_media_url(result: Mapping[str, Any]) -> str:
    """Extract the first obvious image/video URL without guessing opaque schemas."""
    video = result.get("video")
    if isinstance(video, Mapping):
        url = video.get("url")
        if isinstance(url, str) and url.strip():
            return url

    images = result.get("images")
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, Mapping):
            url = first.get("url")
            if isinstance(url, str) and url.strip():
                return url

    jobs = result.get("jobs")
    if isinstance(jobs, list):
        for job in jobs:
            if not isinstance(job, Mapping):
                continue
            results = job.get("results")
            if isinstance(results, Mapping):
                raw = results.get("raw")
                if isinstance(raw, Mapping):
                    url = raw.get("url")
                    if isinstance(url, str) and url.strip():
                        return url

    raise RuntimeError("Higgsfield API result contains no recognized media URL")

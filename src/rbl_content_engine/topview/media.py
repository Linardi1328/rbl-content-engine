"""Local media inspection for the Phase 1D-B Topview reference pilot.

This module performs file-format inspection and hashing only. It does not upload media,
call Topview/MCP, generate content, or approve references.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .references import resolve_workspace_file, sha256_file


JPEG_SOF_MARKERS = {
    0xC0, 0xC1, 0xC2, 0xC3,
    0xC5, 0xC6, 0xC7,
    0xC9, 0xCA, 0xCB,
    0xCD, 0xCE, 0xCF,
}


@dataclass(frozen=True)
class MediaInspection:
    source_path: str
    resolved_path: str
    media_kind: str
    format: str
    mime_type: str
    width: int
    height: int
    byte_size: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": True,
            "source_path": self.source_path,
            "resolved_path": self.resolved_path,
            "media_kind": self.media_kind,
            "format": self.format,
            "mime_type": self.mime_type,
            "width": self.width,
            "height": self.height,
            "byte_size": self.byte_size,
            "sha256": self.sha256,
            "visual_reference_candidate": True,
            "paid_generation_authorized": False,
        }


def _png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("file is not a valid PNG header")
    if data[12:16] != b"IHDR":
        raise ValueError("PNG is missing an IHDR chunk")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if width <= 0 or height <= 0:
        raise ValueError("PNG dimensions must be positive")
    return width, height


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise ValueError("file is not a valid JPEG header")

    index = 2
    while index + 4 <= len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1

        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(data):
            break
        segment_length = int.from_bytes(data[index:index + 2], "big")
        if segment_length < 2 or index + segment_length > len(data):
            raise ValueError("JPEG contains an invalid segment length")

        if marker in JPEG_SOF_MARKERS:
            if segment_length < 7:
                raise ValueError("JPEG SOF segment is too short")
            height = int.from_bytes(data[index + 3:index + 5], "big")
            width = int.from_bytes(data[index + 5:index + 7], "big")
            if width <= 0 or height <= 0:
                raise ValueError("JPEG dimensions must be positive")
            return width, height

        index += segment_length

    raise ValueError("JPEG dimensions could not be determined")


def inspect_media_reference(
    workspace_root: str | Path,
    source_path: str,
) -> MediaInspection:
    """Inspect a local PNG/JPEG reference without external side effects."""

    resolved = resolve_workspace_file(workspace_root, source_path)
    suffix = resolved.suffix.lower()
    data = resolved.read_bytes()

    if suffix == ".png":
        width, height = _png_dimensions(data)
        fmt = "PNG"
        mime = "image/png"
    elif suffix in {".jpg", ".jpeg"}:
        width, height = _jpeg_dimensions(data)
        fmt = "JPEG"
        mime = "image/jpeg"
    else:
        raise ValueError("Phase 1D-B accepts only .png, .jpg, or .jpeg reference files")

    return MediaInspection(
        source_path=source_path,
        resolved_path=str(resolved),
        media_kind="image",
        format=fmt,
        mime_type=mime,
        width=width,
        height=height,
        byte_size=len(data),
        sha256=sha256_file(resolved),
    )

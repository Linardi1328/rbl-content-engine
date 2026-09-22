"""Phase 5 direct-publishing adapters and a small persistent scheduler.

The module intentionally uses only the Python standard library. OAuth setup remains an
external one-time prerequisite; tokens are loaded from the environment and never written
to tracked files.

The scheduler is conservative around uncertain writes:
- a platform is marked IN_PROGRESS before a network mutation;
- a process restart never blindly repeats an IN_PROGRESS mutation;
- TikTok submissions are reconciled by publish_id instead of re-submitted;
- platform failures are isolated so one platform cannot cause duplicate posts elsewhere.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env.local", override=False)

DEFAULT_QUEUE = ROOT / ".production" / "social-publishing-queue.json"
DEFAULT_RECEIPTS = ROOT / ".production" / "publication-receipts"
DEFAULT_AUTH_DIR = ROOT / ".production" / "social-auth"
SUPPORTED_PLATFORMS = ("instagram", "tiktok", "youtube")


class PublishError(RuntimeError):
    """A platform request failed or returned an unusable response."""


class PublishBlocked(PublishError):
    """Publishing is blocked by a local prerequisite or platform policy."""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes

    def json(self) -> dict[str, Any]:
        try:
            value = json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PublishError("provider returned non-JSON response") from exc
        if not isinstance(value, dict):
            raise PublishError("provider returned an unexpected JSON payload")
        return value


class HttpTransport:
    """Small injectable HTTP transport for provider adapters."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        body: bytes | None = None,
        timeout: int = 120,
    ) -> HttpResponse:
        request = urllib.request.Request(
            url,
            data=body,
            headers=dict(headers or {}),
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return HttpResponse(
                    status=int(response.status),
                    headers={str(k): str(v) for k, v in response.headers.items()},
                    body=response.read(),
                )
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            safe = payload.decode("utf-8", errors="replace")[:1000]
            raise PublishError(
                f"provider HTTP {exc.code}: {safe}"
            ) from exc
        except urllib.error.URLError as exc:
            raise PublishError(f"provider transport error: {exc.reason}") from exc


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("datetime must be a non-empty ISO-8601 string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("scheduled datetime must include a timezone offset")
    return parsed


def _require_env(*names: str) -> dict[str, str]:
    values: dict[str, str] = {}
    missing: list[str] = []
    for name in names:
        value = os.environ.get(name, "").strip()
        if not value:
            missing.append(name)
        else:
            values[name] = value
    if missing:
        raise PublishBlocked(
            "missing local credential/config environment variables: "
            + ", ".join(sorted(missing))
        )
    return values


def _json_request(
    transport: HttpTransport,
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: Mapping[str, Any] | None = None,
    extra_headers: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    headers: dict[str, str] = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json; charset=UTF-8"
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    headers.update(dict(extra_headers or {}))
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    response = transport.request(method, url, headers=headers, body=body)
    data = response.json()
    return data


def _form_request(
    transport: HttpTransport,
    method: str,
    url: str,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    encoded = urllib.parse.urlencode(
        {k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in params.items()}
    ).encode("utf-8")
    response = transport.request(
        method,
        url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=encoded,
    )
    return response.json()


def _api_error(payload: Mapping[str, Any], provider: str) -> None:
    if "error" not in payload:
        return
    error = payload.get("error")
    if isinstance(error, Mapping):
        code = error.get("code")
        if code in (None, "", "ok", 0):
            return
        message = error.get("message") or code
        raise PublishError(f"{provider} error: {message}")
    if error:
        raise PublishError(f"{provider} error: {error}")


def _asset_path(manifest: Mapping[str, Any], platform: str) -> Path:
    assets = manifest.get("assets")
    if not isinstance(assets, Mapping):
        raise PublishBlocked("manifest.assets is required")
    entry = assets.get(platform) or assets.get("default")
    if not isinstance(entry, Mapping):
        raise PublishBlocked(f"no asset configured for {platform}")
    raw = entry.get("path")
    if not isinstance(raw, str) or not raw.strip():
        raise PublishBlocked(f"{platform} asset path is missing")
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        raise PublishBlocked(f"{platform} asset file does not exist: {path}")
    return path


def _asset_entry(manifest: Mapping[str, Any], platform: str) -> Mapping[str, Any]:
    assets = manifest.get("assets")
    if not isinstance(assets, Mapping):
        raise PublishBlocked("manifest.assets is required")
    entry = assets.get(platform) or assets.get("default")
    if not isinstance(entry, Mapping):
        raise PublishBlocked(f"no asset configured for {platform}")
    return entry


def _platform_config(manifest: Mapping[str, Any], platform: str) -> Mapping[str, Any]:
    platforms = manifest.get("platforms")
    if not isinstance(platforms, Mapping):
        raise PublishBlocked("manifest.platforms is required")
    config = platforms.get(platform)
    if not isinstance(config, Mapping):
        raise PublishBlocked(f"missing {platform} platform configuration")
    return config


def _enabled_platforms(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    platforms = manifest.get("platforms")
    if not isinstance(platforms, Mapping):
        raise PublishBlocked("manifest.platforms is required")
    return tuple(
        str(name)
        for name, config in platforms.items()
        if isinstance(config, Mapping) and config.get("enabled", True)
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def require_publication_approval(manifest: Mapping[str, Any]) -> None:
    approval = manifest.get("approval")
    if not isinstance(approval, Mapping):
        raise PublishBlocked("final human publication approval is required")
    if approval.get("human_confirmed") is not True:
        raise PublishBlocked("approval.human_confirmed must be true")
    try:
        parse_datetime(str(approval.get("confirmed_at", "")))
    except ValueError as exc:
        raise PublishBlocked(
            "approval.confirmed_at must be a timezone-aware ISO-8601 datetime"
        ) from exc

    approved_hashes = approval.get("asset_sha256")
    if not isinstance(approved_hashes, Mapping):
        raise PublishBlocked("approval.asset_sha256 is required")

    for platform in _enabled_platforms(manifest):
        expected = approved_hashes.get(platform)
        if (
            not isinstance(expected, str)
            or len(expected) != 64
            or any(ch not in "0123456789abcdefABCDEF" for ch in expected)
        ):
            raise PublishBlocked(
                f"approval.asset_sha256.{platform} must be a 64-character SHA-256 hex digest"
            )
        actual = _sha256_file(_asset_path(manifest, platform))
        if actual.lower() != expected.lower():
            raise PublishBlocked(
                f"{platform} asset changed after human approval; publication is blocked"
            )


def validate_post_manifest(
    manifest: Mapping[str, Any],
    *,
    require_approval: bool = True,
) -> None:
    post_id = manifest.get("post_id")
    if not isinstance(post_id, str) or not post_id.strip():
        raise ValueError("post_id must be non-empty")
    scheduled_at = manifest.get("scheduled_at")
    if not isinstance(scheduled_at, str):
        raise ValueError("scheduled_at is required")
    parse_datetime(scheduled_at)

    platforms = manifest.get("platforms")
    if not isinstance(platforms, Mapping) or not platforms:
        raise ValueError("platforms must be a non-empty object")

    enabled = 0
    for name, config in platforms.items():
        if name not in SUPPORTED_PLATFORMS:
            raise ValueError(f"unsupported platform: {name}")
        if not isinstance(config, Mapping):
            raise ValueError(f"{name} config must be an object")
        if config.get("enabled", True):
            enabled += 1
            _asset_entry(manifest, name)
    if enabled == 0:
        raise ValueError("at least one platform must be enabled")

    # TikTok requires an export without application-added brand/logo/watermark.
    tiktok = platforms.get("tiktok")
    if isinstance(tiktok, Mapping) and tiktok.get("enabled", True):
        asset = _asset_entry(manifest, "tiktok")
        if asset.get("promotional_overlay_free") is not True:
            raise ValueError(
                "TikTok asset must declare promotional_overlay_free=true"
            )
        consent = tiktok.get("consent")
        if not isinstance(consent, Mapping):
            raise ValueError("TikTok requires a per-post consent receipt")
        for key in (
            "confirmed",
            "previewed",
            "metadata_editable",
            "music_usage_confirmed",
        ):
            if consent.get(key) is not True:
                raise ValueError(f"TikTok consent.{key} must be true")
        parse_datetime(str(consent.get("confirmed_at", "")))

    instagram = platforms.get("instagram")
    if isinstance(instagram, Mapping) and instagram.get("enabled", True):
        entry = _asset_entry(manifest, "instagram")
        url = entry.get("public_url")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError(
                "Instagram publishing requires assets.instagram.public_url "
                "(or default public_url) with an HTTPS URL"
            )

    if require_approval:
        require_publication_approval(manifest)


def load_post_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("post manifest must be a JSON object")
    validate_post_manifest(payload)
    return payload


def approve_post_manifest(
    path: Path,
    *,
    human_confirmed: bool,
    confirmed_at: datetime | None = None,
) -> dict[str, Any]:
    if not human_confirmed:
        raise PublishBlocked("explicit human confirmation is required")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("post manifest must be a JSON object")

    validate_post_manifest(payload, require_approval=False)
    approved_at = confirmed_at or _utc_now()
    if approved_at.tzinfo is None or approved_at.utcoffset() is None:
        raise ValueError("approval time must be timezone-aware")

    payload["approval"] = {
        "human_confirmed": True,
        "confirmed_at": approved_at.isoformat(),
        "asset_sha256": {
            platform: _sha256_file(_asset_path(payload, platform))
            for platform in _enabled_platforms(payload)
        },
    }
    validate_post_manifest(payload)

    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temp = Path(handle.name)
    temp.replace(path)
    return payload


class InstagramReelsPublisher:
    def __init__(
        self,
        *,
        graph_version: str,
        ig_user_id: str,
        access_token: str,
        transport: HttpTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        poll_seconds: float = 3.0,
        max_polls: int = 40,
    ) -> None:
        if not graph_version.startswith("v"):
            raise PublishBlocked("INSTAGRAM_GRAPH_VERSION must look like vNN.N")
        self.graph_version = graph_version
        self.ig_user_id = ig_user_id
        self.access_token = access_token
        self.transport = transport or HttpTransport()
        self.sleep = sleep
        self.poll_seconds = poll_seconds
        self.max_polls = max_polls

    @classmethod
    def from_env(cls, **kwargs: Any) -> "InstagramReelsPublisher":
        env = _require_env(
            "INSTAGRAM_GRAPH_VERSION",
            "INSTAGRAM_USER_ID",
            "INSTAGRAM_ACCESS_TOKEN",
        )
        return cls(
            graph_version=env["INSTAGRAM_GRAPH_VERSION"],
            ig_user_id=env["INSTAGRAM_USER_ID"],
            access_token=env["INSTAGRAM_ACCESS_TOKEN"],
            **kwargs,
        )

    def publish(
        self, manifest: Mapping[str, Any], config: Mapping[str, Any]
    ) -> dict[str, Any]:
        asset = _asset_entry(manifest, "instagram")
        video_url = str(asset["public_url"])
        caption = str(config.get("caption", ""))
        create_url = (
            f"https://graph.instagram.com/{self.graph_version}/"
            f"{self.ig_user_id}/media"
        )
        create = _form_request(
            self.transport,
            "POST",
            create_url,
            {
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "share_to_feed": bool(config.get("share_to_feed", True)),
                "access_token": self.access_token,
            },
        )
        _api_error(create, "Instagram")
        container_id = create.get("id")
        if not isinstance(container_id, str) or not container_id:
            raise PublishError("Instagram did not return a container id")

        status_url = (
            f"https://graph.instagram.com/{self.graph_version}/{container_id}?"
            + urllib.parse.urlencode(
                {
                    "fields": "status_code,status",
                    "access_token": self.access_token,
                }
            )
        )
        for _ in range(self.max_polls):
            status_payload = _json_request(
                self.transport, "GET", status_url
            )
            _api_error(status_payload, "Instagram")
            code = status_payload.get("status_code")
            if code == "FINISHED":
                break
            if code in {"ERROR", "EXPIRED"}:
                raise PublishError(
                    "Instagram container failed: "
                    + str(status_payload.get("status", code))
                )
            self.sleep(self.poll_seconds)
        else:
            raise PublishError(
                f"Instagram container {container_id} did not finish in time"
            )

        publish_url = (
            f"https://graph.instagram.com/{self.graph_version}/"
            f"{self.ig_user_id}/media_publish"
        )
        result = _form_request(
            self.transport,
            "POST",
            publish_url,
            {
                "creation_id": container_id,
                "access_token": self.access_token,
            },
        )
        _api_error(result, "Instagram")
        media_id = result.get("id")
        if not isinstance(media_id, str) or not media_id:
            raise PublishError("Instagram did not return a media id")
        return {
            "status": "PUBLISHED",
            "provider_id": media_id,
            "container_id": container_id,
        }


class FacebookReelsPublisher:
    def __init__(
        self,
        *,
        graph_version: str,
        access_token: str,
        transport: HttpTransport | None = None,
    ) -> None:
        if not graph_version.startswith("v"):
            raise PublishBlocked("META_GRAPH_VERSION must look like vNN.N")
        self.graph_version = graph_version
        self.access_token = access_token
        self.transport = transport or HttpTransport()

    @classmethod
    def from_env(cls, **kwargs: Any) -> "FacebookReelsPublisher":
        env = _require_env("META_GRAPH_VERSION", "META_PAGE_ACCESS_TOKEN")
        return cls(
            graph_version=env["META_GRAPH_VERSION"],
            access_token=env["META_PAGE_ACCESS_TOKEN"],
            **kwargs,
        )

    def publish(
        self, manifest: Mapping[str, Any], config: Mapping[str, Any]
    ) -> dict[str, Any]:
        path = _asset_path(manifest, "facebook")
        endpoint = (
            f"https://graph.facebook.com/{self.graph_version}/me/video_reels"
        )
        start = _form_request(
            self.transport,
            "POST",
            endpoint,
            {
                "access_token": self.access_token,
                "upload_phase": "start",
            },
        )
        _api_error(start, "Facebook")
        video_id = start.get("video_id")
        upload_url = start.get("upload_url")
        if not isinstance(video_id, str) or not isinstance(upload_url, str):
            raise PublishError("Facebook did not return upload session details")

        payload = path.read_bytes()
        upload = self.transport.request(
            "POST",
            upload_url,
            headers={
                "Authorization": f"OAuth {self.access_token}",
                "offset": "0",
                "file_size": str(len(payload)),
                "Content-Type": "application/octet-stream",
            },
            body=payload,
        ).json()
        _api_error(upload, "Facebook")
        if upload.get("success") is not True:
            raise PublishError("Facebook local Reel upload did not succeed")

        finish = _form_request(
            self.transport,
            "POST",
            endpoint,
            {
                "access_token": self.access_token,
                "video_id": video_id,
                "upload_phase": "finish",
                "video_state": "PUBLISHED",
                "title": str(config.get("title", "")),
                "description": str(config.get("description", "")),
            },
        )
        _api_error(finish, "Facebook")
        if finish.get("success") is not True:
            raise PublishError("Facebook Reel publish did not succeed")
        return {"status": "PUBLISHED", "provider_id": video_id}


def _utf16_units(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _tiktok_chunk_plan(size: int) -> tuple[int, int]:
    if size <= 0:
        raise PublishBlocked("TikTok asset is empty")
    max_chunk = 64 * 1024 * 1024
    if size <= max_chunk:
        return size, 1
    count = (size + max_chunk - 1) // max_chunk
    chunk = size // count
    if chunk < 5 * 1024 * 1024:
        raise PublishBlocked("TikTok chunk plan would violate minimum chunk size")
    return chunk, count


class TikTokPublisher:
    API = "https://open.tiktokapis.com"

    def __init__(
        self,
        *,
        access_token: str,
        transport: HttpTransport | None = None,
    ) -> None:
        self.access_token = access_token
        self.transport = transport or HttpTransport()

    @classmethod
    def from_env(cls, **kwargs: Any) -> "TikTokPublisher":
        transport = kwargs.pop("transport", None) or HttpTransport()
        client_key = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
        client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
        configured_refresh = os.environ.get("TIKTOK_REFRESH_TOKEN", "").strip()
        state_override = os.environ.get("TIKTOK_TOKEN_STATE_PATH", "").strip()
        state_path = (
            Path(state_override).expanduser()
            if state_override
            else DEFAULT_AUTH_DIR / "tiktok.json"
        )

        refresh_token = configured_refresh
        if state_path.is_file():
            try:
                stored = json.loads(state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise PublishBlocked(
                    f"TikTok token state is unreadable: {state_path}"
                ) from exc
            stored_refresh = stored.get("refresh_token")
            if isinstance(stored_refresh, str) and stored_refresh:
                refresh_token = stored_refresh

        if client_key and client_secret and refresh_token:
            body = urllib.parse.urlencode(
                {
                    "client_key": client_key,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                }
            ).encode("utf-8")
            payload = transport.request(
                "POST",
                "https://open.tiktokapis.com/v2/oauth/token/",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Cache-Control": "no-cache",
                },
                body=body,
            ).json()
            access_token = payload.get("access_token")
            new_refresh = payload.get("refresh_token")
            if not isinstance(access_token, str) or not access_token:
                description = payload.get("error_description") or payload.get("error")
                raise PublishBlocked(
                    "TikTok token refresh failed"
                    + (f": {description}" if description else "")
                )
            if not isinstance(new_refresh, str) or not new_refresh:
                new_refresh = refresh_token

            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_payload = {
                "refresh_token": new_refresh,
                "scope": payload.get("scope"),
                "open_id": payload.get("open_id"),
                "updated_at": _utc_now().isoformat(),
            }
            state_path.write_text(
                json.dumps(state_payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            try:
                state_path.chmod(0o600)
            except OSError:
                pass
            return cls(access_token=access_token, transport=transport, **kwargs)

        access_token = os.environ.get("TIKTOK_ACCESS_TOKEN", "").strip()
        if not access_token:
            raise PublishBlocked(
                "configure TIKTOK_CLIENT_KEY + TIKTOK_CLIENT_SECRET + "
                "TIKTOK_REFRESH_TOKEN for unattended refresh, or "
                "TIKTOK_ACCESS_TOKEN for short-lived testing"
            )
        return cls(access_token=access_token, transport=transport, **kwargs)

    def _post(self, path: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        result = _json_request(
            self.transport,
            "POST",
            self.API + path,
            token=self.access_token,
            payload=payload or {},
        )
        _api_error(result, "TikTok")
        return result

    def creator_info(self) -> Mapping[str, Any]:
        payload = self._post("/v2/post/publish/creator_info/query/")
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise PublishError("TikTok creator-info response is missing data")
        return data

    def publish(
        self, manifest: Mapping[str, Any], config: Mapping[str, Any]
    ) -> dict[str, Any]:
        consent = config.get("consent")
        if not isinstance(consent, Mapping) or consent.get("confirmed") is not True:
            raise PublishBlocked("TikTok requires per-post explicit consent")
        if consent.get("previewed") is not True:
            raise PublishBlocked("TikTok requires the creator to preview the post")
        if consent.get("metadata_editable") is not True:
            raise PublishBlocked(
                "TikTok requires preset text/hashtags to remain editable before posting"
            )
        if consent.get("music_usage_confirmed") is not True:
            raise PublishBlocked(
                "TikTok requires Music Usage Confirmation before direct posting"
            )

        asset = _asset_entry(manifest, "tiktok")
        if asset.get("promotional_overlay_free") is not True:
            raise PublishBlocked(
                "TikTok API export must not contain application-added "
                "brand/logo/watermark/promotional overlays"
            )
        path = _asset_path(manifest, "tiktok")
        creator = self.creator_info()
        privacy = str(config.get("privacy_level", "PUBLIC_TO_EVERYONE"))
        options = creator.get("privacy_level_options")
        if not isinstance(options, list) or privacy not in options:
            raise PublishBlocked(
                f"TikTok privacy level {privacy!r} is not currently available"
            )

        caption = str(config.get("caption", ""))
        if _utf16_units(caption) > 2200:
            raise PublishBlocked("TikTok caption exceeds 2200 UTF-16 code units")

        size = path.stat().st_size
        chunk_size, count = _tiktok_chunk_plan(size)
        post_info: dict[str, Any] = {
            "title": caption,
            "privacy_level": privacy,
            "disable_duet": bool(config.get("disable_duet", False)),
            "disable_comment": bool(config.get("disable_comment", False)),
            "disable_stitch": bool(config.get("disable_stitch", False)),
            "video_cover_timestamp_ms": int(
                config.get("video_cover_timestamp_ms", 1000)
            ),
            "is_aigc": bool(asset.get("ai_generated", True)),
        }
        if "brand_organic_toggle" in config:
            post_info["brand_organic_toggle"] = bool(
                config.get("brand_organic_toggle")
            )
        if "brand_content_toggle" in config:
            post_info["brand_content_toggle"] = bool(
                config.get("brand_content_toggle")
            )

        init = self._post(
            "/v2/post/publish/video/init/",
            {
                "post_info": post_info,
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": size,
                    "chunk_size": chunk_size,
                    "total_chunk_count": count,
                },
            },
        )
        data = init.get("data")
        if not isinstance(data, Mapping):
            raise PublishError("TikTok post initialization returned no data")
        publish_id = data.get("publish_id")
        upload_url = data.get("upload_url")
        if not isinstance(publish_id, str) or not isinstance(upload_url, str):
            raise PublishError("TikTok did not return publish/upload identifiers")

        content_type = mimetypes.guess_type(path.name)[0] or "video/mp4"
        if content_type not in {"video/mp4", "video/quicktime", "video/webm"}:
            content_type = "video/mp4"

        with path.open("rb") as handle:
            offset = 0
            for index in range(count):
                if index == count - 1:
                    data_bytes = handle.read()
                else:
                    data_bytes = handle.read(chunk_size)
                if not data_bytes:
                    raise PublishError("TikTok upload ended before expected file size")
                end = offset + len(data_bytes) - 1
                response = self.transport.request(
                    "PUT",
                    upload_url,
                    headers={
                        "Content-Type": content_type,
                        "Content-Length": str(len(data_bytes)),
                        "Content-Range": f"bytes {offset}-{end}/{size}",
                    },
                    body=data_bytes,
                )
                expected = 201 if index == count - 1 else 206
                if response.status != expected:
                    raise PublishError(
                        f"TikTok chunk {index + 1}/{count} returned "
                        f"HTTP {response.status}; expected {expected}"
                    )
                offset = end + 1

        return {
            "status": "SUBMITTED",
            "provider_id": publish_id,
            "creator_username": creator.get("creator_username"),
        }

    def check_status(self, publish_id: str) -> dict[str, Any]:
        payload = self._post(
            "/v2/post/publish/status/fetch/",
            {"publish_id": publish_id},
        )
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise PublishError("TikTok status response is missing data")
        status = data.get("status")
        if status == "PUBLISH_COMPLETE":
            ids = data.get("publicaly_available_post_id")
            return {
                "status": "PUBLISHED",
                "provider_id": publish_id,
                "public_post_ids": ids if isinstance(ids, list) else [],
            }
        if status == "FAILED":
            raise PublishError(
                "TikTok publication failed: " + str(data.get("fail_reason", "unknown"))
            )
        return {
            "status": "SUBMITTED",
            "provider_id": publish_id,
            "provider_status": status,
        }


class YouTubePublisher:
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"

    def __init__(
        self,
        *,
        access_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        refresh_token: str | None = None,
        transport: HttpTransport | None = None,
    ) -> None:
        self.access_token = access_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.transport = transport or HttpTransport()

    @classmethod
    def from_env(cls, **kwargs: Any) -> "YouTubePublisher":
        access = os.environ.get("YOUTUBE_ACCESS_TOKEN", "").strip() or None
        client_id = os.environ.get("YOUTUBE_CLIENT_ID", "").strip() or None
        client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip() or None
        refresh = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip() or None
        if access is None and not all((client_id, client_secret, refresh)):
            raise PublishBlocked(
                "configure YOUTUBE_ACCESS_TOKEN or "
                "YOUTUBE_CLIENT_ID + YOUTUBE_CLIENT_SECRET + YOUTUBE_REFRESH_TOKEN"
            )
        return cls(
            access_token=access,
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh,
            **kwargs,
        )

    def _token(self) -> str:
        if self.access_token:
            return self.access_token
        assert self.client_id and self.client_secret and self.refresh_token
        payload = urllib.parse.urlencode(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        response = self.transport.request(
            "POST",
            self.TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            body=payload,
        ).json()
        token = response.get("access_token")
        if not isinstance(token, str) or not token:
            raise PublishError("YouTube token refresh returned no access_token")
        return token

    def publish(
        self, manifest: Mapping[str, Any], config: Mapping[str, Any]
    ) -> dict[str, Any]:
        path = _asset_path(manifest, "youtube")
        token = self._token()
        title = str(config.get("title", "")).strip()
        if not title:
            raise PublishBlocked("YouTube title is required")

        scheduled = parse_datetime(str(manifest["scheduled_at"]))
        now = _utc_now()
        requested_privacy = str(config.get("privacy_status", "public"))
        status: dict[str, Any] = {
            "privacyStatus": requested_privacy,
            "selfDeclaredMadeForKids": bool(
                config.get("made_for_kids", False)
            ),
            "containsSyntheticMedia": bool(
                _asset_entry(manifest, "youtube").get("ai_generated", True)
            ),
        }
        # If this adapter is intentionally run before the due time, use YouTube's
        # native scheduling contract: private + status.publishAt.
        if scheduled > now:
            status["privacyStatus"] = "private"
            status["publishAt"] = scheduled.astimezone(timezone.utc).isoformat().replace(
                "+00:00", "Z"
            )

        metadata = {
            "snippet": {
                "title": title,
                "description": str(config.get("description", "")),
                "tags": list(config.get("tags", [])),
                "categoryId": str(config.get("category_id", "22")),
                "defaultLanguage": str(config.get("default_language", "en")),
            },
            "status": status,
        }
        query = urllib.parse.urlencode(
            {"uploadType": "resumable", "part": "snippet,status"}
        )
        init = self.transport.request(
            "POST",
            self.UPLOAD_URL + "?" + query,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Length": str(path.stat().st_size),
                "X-Upload-Content-Type": "video/mp4",
            },
            body=json.dumps(metadata).encode("utf-8"),
        )
        location = None
        for key, value in init.headers.items():
            if key.lower() == "location":
                location = value
                break
        if not location:
            payload = init.body.decode("utf-8", errors="replace")[:500]
            raise PublishError(
                "YouTube resumable upload did not return a Location header: "
                + payload
            )

        uploaded = self.transport.request(
            "PUT",
            location,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "video/mp4",
                "Content-Length": str(path.stat().st_size),
            },
            body=path.read_bytes(),
            timeout=300,
        ).json()
        video_id = uploaded.get("id")
        if not isinstance(video_id, str) or not video_id:
            raise PublishError("YouTube upload returned no video id")
        return {
            "status": "NATIVE_SCHEDULED" if "publishAt" in status else "PUBLISHED",
            "provider_id": video_id,
            "publish_at": status.get("publishAt"),
        }


@dataclass
class ScheduledPost:
    job_id: str
    manifest_path: str
    scheduled_at: str
    status: str
    platforms: dict[str, dict[str, Any]]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ScheduledPost":
        return cls(
            job_id=str(payload["job_id"]),
            manifest_path=str(payload["manifest_path"]),
            scheduled_at=str(payload["scheduled_at"]),
            status=str(payload.get("status", "SCHEDULED")),
            platforms={
                str(k): dict(v) for k, v in dict(payload.get("platforms", {})).items()
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "manifest_path": self.manifest_path,
            "scheduled_at": self.scheduled_at,
            "status": self.status,
            "platforms": self.platforms,
        }


class ScheduleQueue:
    def __init__(self, path: Path = DEFAULT_QUEUE) -> None:
        self.path = path
        self.jobs: list[ScheduledPost] = []
        self.load()

    def load(self) -> None:
        if not self.path.is_file():
            self.jobs = []
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        raw = payload.get("jobs", [])
        if not isinstance(raw, list):
            raise ValueError("scheduler queue jobs must be a list")
        self.jobs = [ScheduledPost.from_dict(item) for item in raw]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0.0",
            "jobs": [job.to_dict() for job in self.jobs],
        }
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.path.parent, delete=False
        ) as handle:
            handle.write(text)
            temp = Path(handle.name)
        temp.replace(self.path)

    def add_manifest(self, manifest_path: Path) -> ScheduledPost:
        manifest = load_post_manifest(manifest_path)
        post_id = str(manifest["post_id"])
        if any(job.job_id == post_id for job in self.jobs):
            raise ValueError(f"post_id already scheduled: {post_id}")
        platforms = {}
        for name, config in dict(manifest["platforms"]).items():
            if isinstance(config, Mapping) and config.get("enabled", True):
                platforms[name] = {"status": "SCHEDULED"}
        path = manifest_path.resolve()
        job = ScheduledPost(
            job_id=post_id,
            manifest_path=str(path),
            scheduled_at=str(manifest["scheduled_at"]),
            status="SCHEDULED",
            platforms=platforms,
        )
        self.jobs.append(job)
        self.jobs.sort(key=lambda j: (parse_datetime(j.scheduled_at), j.job_id))
        self.save()
        return job


def _publisher_for(platform: str) -> Any:
    if platform == "instagram":
        return InstagramReelsPublisher.from_env()
    if platform == "tiktok":
        return TikTokPublisher.from_env()
    if platform == "youtube":
        return YouTubePublisher.from_env()
    raise PublishBlocked(f"unsupported platform: {platform}")


def _write_receipt(
    job: ScheduledPost,
    manifest: Mapping[str, Any],
    receipt_dir: Path,
) -> Path:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    path = receipt_dir / f"{job.job_id}.json"
    payload = {
        "schema_version": "1.0.0",
        "post_id": job.job_id,
        "scheduled_at": job.scheduled_at,
        "job_status": job.status,
        "platforms": job.platforms,
        "asset_ai_generated": any(
            isinstance(v, Mapping) and v.get("ai_generated", False)
            for v in dict(manifest.get("assets", {})).values()
        ),
        "updated_at": _utc_now().isoformat(),
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _finish_job_status(job: ScheduledPost) -> None:
    statuses = [value.get("status") for value in job.platforms.values()]
    if statuses and all(status in {"PUBLISHED", "NATIVE_SCHEDULED"} for status in statuses):
        job.status = "COMPLETE"
    elif any(status in {"FAILED", "BLOCKED", "RECONCILE_REQUIRED"} for status in statuses):
        job.status = "PARTIAL"
    elif any(status == "SUBMITTED" for status in statuses):
        job.status = "PROCESSING"
    else:
        job.status = "SCHEDULED"


def publish_due_jobs(
    queue: ScheduleQueue,
    *,
    now: datetime | None = None,
    receipt_dir: Path = DEFAULT_RECEIPTS,
    publisher_factory: Callable[[str], Any] = _publisher_for,
) -> list[str]:
    """Publish/reconcile due jobs once and persist state after every mutation."""
    current = now or _utc_now()
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("scheduler now must be timezone-aware")

    events: list[str] = []
    for job in queue.jobs:
        manifest = load_post_manifest(Path(job.manifest_path))
        due = parse_datetime(job.scheduled_at) <= current

        for platform, platform_state in job.platforms.items():
            state = platform_state.get("status")

            if state in {"PUBLISHED", "NATIVE_SCHEDULED", "FAILED", "BLOCKED", "RECONCILE_REQUIRED"}:
                continue

            if state == "IN_PROGRESS":
                platform_state["status"] = "RECONCILE_REQUIRED"
                platform_state["error"] = (
                    "previous process stopped during an uncertain platform mutation; "
                    "automatic re-submit is blocked to prevent duplicates"
                )
                queue.save()
                events.append(f"{job.job_id}:{platform}:RECONCILE_REQUIRED")
                continue

            if state == "SUBMITTED":
                if platform != "tiktok":
                    continue
                try:
                    publisher = publisher_factory(platform)
                    result = publisher.check_status(
                        str(platform_state["provider_id"])
                    )
                    platform_state.update(result)
                    checked_at = _utc_now().isoformat()
                    platform_state["checked_at"] = checked_at
                    if platform_state.get("status") == "PUBLISHED":
                        platform_state["completed_at"] = checked_at
                except PublishError as exc:
                    platform_state["status"] = "FAILED"
                    platform_state["error"] = str(exc)[:1000]
                queue.save()
                events.append(
                    f"{job.job_id}:{platform}:{platform_state.get('status')}"
                )
                continue

            if not due:
                continue

            config = _platform_config(manifest, platform)
            platform_state["status"] = "IN_PROGRESS"
            platform_state["started_at"] = _utc_now().isoformat()
            queue.save()

            try:
                publisher = publisher_factory(platform)
                result = publisher.publish(manifest, config)
                platform_state.update(result)
                mutation_at = _utc_now().isoformat()
                if platform_state.get("status") == "SUBMITTED":
                    platform_state["submitted_at"] = mutation_at
                elif platform_state.get("status") in {"PUBLISHED", "NATIVE_SCHEDULED"}:
                    platform_state["completed_at"] = mutation_at
            except PublishBlocked as exc:
                platform_state["status"] = "BLOCKED"
                platform_state["error"] = str(exc)[:1000]
            except PublishError as exc:
                platform_state["status"] = "FAILED"
                platform_state["error"] = str(exc)[:1000]
            queue.save()
            events.append(
                f"{job.job_id}:{platform}:{platform_state.get('status')}"
            )

        _finish_job_status(job)
        queue.save()
        _write_receipt(job, manifest, receipt_dir)

    return events


def run_scheduler(
    queue_path: Path = DEFAULT_QUEUE,
    *,
    poll_seconds: float = 30.0,
) -> None:
    """Run the scheduler continuously until interrupted."""
    if poll_seconds < 1:
        raise ValueError("poll_seconds must be at least 1")
    while True:
        queue = ScheduleQueue(queue_path)
        events = publish_due_jobs(queue)
        for event in events:
            print(event)
        time.sleep(poll_seconds)

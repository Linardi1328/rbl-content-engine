"""TikTok Desktop Login Kit OAuth bootstrap for Phase 5 publishing.

This module performs the one-time interactive authorization needed to obtain a
long-lived refresh token. It deliberately persists only refresh-token state in
.production/social-auth/; short-lived access tokens and the client secret are
never written there.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import string
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Mapping

from .core import DEFAULT_AUTH_DIR, HttpTransport, PublishBlocked, PublishError, _utc_now

AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:3455/callback/"
DEFAULT_SCOPES = ("user.info.basic", "video.publish")
_UNRESERVED = string.ascii_letters + string.digits + "-._~"


def generate_code_verifier(length: int = 64) -> str:
    """Generate a PKCE verifier using RFC 3986 unreserved characters."""

    if length < 43 or length > 128:
        raise ValueError("PKCE code verifier length must be between 43 and 128")
    return "".join(secrets.choice(_UNRESERVED) for _ in range(length))


def code_challenge_for(verifier: str) -> str:
    """TikTok Desktop Login Kit uses a hex-encoded SHA-256 PKCE challenge."""

    return hashlib.sha256(verifier.encode("ascii")).hexdigest()


def _validated_redirect_uri(value: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("TikTok desktop redirect URI must use http or https")
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("TikTok desktop redirect URI must use localhost or 127.0.0.1")
    if parsed.port is None:
        raise ValueError("TikTok desktop redirect URI must include a port")
    if not parsed.path:
        raise ValueError("TikTok desktop redirect URI must include a callback path")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError("TikTok desktop redirect URI must not contain params/query/fragment")
    return parsed


def build_authorization_url(
    *,
    client_key: str,
    redirect_uri: str = DEFAULT_REDIRECT_URI,
    scopes: tuple[str, ...] = DEFAULT_SCOPES,
    state: str,
    code_challenge: str,
) -> str:
    """Build the TikTok Desktop Login Kit authorization URL."""

    _validated_redirect_uri(redirect_uri)
    if not client_key.strip():
        raise ValueError("TikTok client key is required")
    if not state:
        raise ValueError("OAuth state is required")
    if not scopes:
        raise ValueError("at least one TikTok OAuth scope is required")

    query = urllib.parse.urlencode(
        {
            "client_key": client_key,
            "response_type": "code",
            "scope": ",".join(scopes),
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def exchange_authorization_code(
    *,
    client_key: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    """Exchange a Desktop Login Kit authorization code for a token bundle."""

    _validated_redirect_uri(redirect_uri)
    if not all((client_key, client_secret, code, code_verifier)):
        raise PublishBlocked("TikTok authorization-code exchange is missing required values")

    body = urllib.parse.urlencode(
        {
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
    ).encode("utf-8")

    response = (transport or HttpTransport()).request(
        "POST",
        TOKEN_URL,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache",
        },
        body=body,
    )
    payload = response.json()
    if payload.get("error"):
        description = payload.get("error_description") or payload.get("error")
        raise PublishBlocked(f"TikTok authorization failed: {description}")

    refresh_token = payload.get("refresh_token")
    access_token = payload.get("access_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise PublishError("TikTok token response did not include a refresh token")
    if not isinstance(access_token, str) or not access_token:
        raise PublishError("TikTok token response did not include an access token")
    return payload


def persist_token_state(
    payload: Mapping[str, Any],
    *,
    state_path: Path | None = None,
) -> Path:
    """Persist only long-lived TikTok refresh-token state."""

    refresh_token = payload.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise PublishError("cannot persist TikTok token state without refresh_token")

    path = state_path or (DEFAULT_AUTH_DIR / "tiktok.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    state_payload = {
        "refresh_token": refresh_token,
        "scope": payload.get("scope"),
        "open_id": payload.get("open_id"),
        "refresh_expires_in": payload.get("refresh_expires_in"),
        "updated_at": _utc_now().isoformat(),
    }
    path.write_text(
        json.dumps(state_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def _callback_handler(
    *,
    expected_path: str,
    expected_state: str,
    result: dict[str, str],
) -> type[BaseHTTPRequestHandler]:
    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            status = 200

            if parsed.path != expected_path:
                status = 404
                message = "Unexpected callback path."
            elif params.get("state", [""])[0] != expected_state:
                result["error"] = "OAuth state mismatch"
                status = 400
                message = "Authorization failed: state mismatch. You can close this window."
            elif params.get("error", [""])[0]:
                result["error"] = params.get("error_description", params["error"])[0]
                status = 400
                message = "TikTok authorization was not completed. You can close this window."
            else:
                code = params.get("code", [""])[0]
                if not code:
                    result["error"] = "TikTok callback did not include an authorization code"
                    status = 400
                    message = "Authorization failed: no code was returned."
                else:
                    result["code"] = code
                    result["scopes"] = params.get("scopes", [""])[0]
                    message = "TikTok authorization received. You can close this window."

            body = (
                "<!doctype html><html><head><meta charset='utf-8'>"
                "<title>RBL Content Engine</title></head>"
                "<body style='font-family:system-ui;padding:40px;max-width:680px;margin:auto'>"
                f"<h1>{message}</h1>"
                "<p>Return to the RBL Content Engine terminal to continue.</p>"
                "</body></html>"
            ).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return CallbackHandler


def run_desktop_oauth(
    *,
    redirect_uri: str = DEFAULT_REDIRECT_URI,
    scopes: tuple[str, ...] = DEFAULT_SCOPES,
    state_path: Path | None = None,
    open_browser: bool = True,
    timeout_seconds: float = 300.0,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    """Run one interactive TikTok Desktop Login Kit authorization."""

    parsed_redirect = _validated_redirect_uri(redirect_uri)
    client_key = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
    if not client_key or not client_secret:
        raise PublishBlocked(
            "configure TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET in .env.local"
        )

    state = secrets.token_urlsafe(32)
    verifier = generate_code_verifier()
    challenge = code_challenge_for(verifier)
    authorization_url = build_authorization_url(
        client_key=client_key,
        redirect_uri=redirect_uri,
        scopes=scopes,
        state=state,
        code_challenge=challenge,
    )

    callback_result: dict[str, str] = {}
    handler = _callback_handler(
        expected_path=parsed_redirect.path,
        expected_state=state,
        result=callback_result,
    )
    server_host = parsed_redirect.hostname or "127.0.0.1"
    server = HTTPServer((server_host, parsed_redirect.port), handler)
    server.timeout = timeout_seconds

    print("TikTok authorization URL:")
    print(authorization_url)
    if open_browser:
        webbrowser.open(authorization_url, new=2)

    try:
        server.handle_request()
    finally:
        server.server_close()

    if "error" in callback_result:
        raise PublishBlocked(f"TikTok authorization failed: {callback_result['error']}")
    code = callback_result.get("code")
    if not code:
        raise PublishBlocked(
            "TikTok authorization callback was not received before the local listener stopped"
        )

    token_payload = exchange_authorization_code(
        client_key=client_key,
        client_secret=client_secret,
        code=code,
        redirect_uri=redirect_uri,
        code_verifier=verifier,
        transport=transport,
    )
    path = persist_token_state(token_payload, state_path=state_path)

    return {
        "status": "AUTHORIZED",
        "open_id": token_payload.get("open_id"),
        "scope": token_payload.get("scope"),
        "state_path": str(path),
        "refresh_expires_in": token_payload.get("refresh_expires_in"),
    }

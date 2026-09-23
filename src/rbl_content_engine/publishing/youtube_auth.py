"""Google OAuth desktop bootstrap for YouTube publishing.

This module performs the one-time interactive authorization needed to obtain a
refresh token for unattended YouTube uploads. It uses Google's installed-app
loopback redirect with PKCE and persists only refresh-token state under
.production/social-auth/. Client credentials remain in ignored .env.local.
"""

from __future__ import annotations

import base64
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

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
DEFAULT_SCOPES = ("https://www.googleapis.com/auth/youtube.upload",)
_UNRESERVED = string.ascii_letters + string.digits + "-._~"


def generate_code_verifier(length: int = 64) -> str:
    """Generate an RFC 7636 PKCE verifier."""

    if length < 43 or length > 128:
        raise ValueError("PKCE code verifier length must be between 43 and 128")
    return "".join(secrets.choice(_UNRESERVED) for _ in range(length))


def code_challenge_for(verifier: str) -> str:
    """Return Google's standard base64url SHA-256 PKCE challenge."""

    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def build_authorization_url(
    *,
    client_id: str,
    redirect_uri: str,
    scopes: tuple[str, ...] = DEFAULT_SCOPES,
    state: str,
    code_challenge: str,
) -> str:
    """Build the Google installed-app authorization URL."""

    if not client_id.strip():
        raise ValueError("Google OAuth client id is required")
    if not redirect_uri.startswith("http://127.0.0.1:"):
        raise ValueError("YouTube desktop OAuth redirect must use 127.0.0.1 loopback")
    if not state:
        raise ValueError("OAuth state is required")
    if not scopes:
        raise ValueError("at least one YouTube OAuth scope is required")

    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def exchange_authorization_code(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    """Exchange an installed-app authorization code for Google tokens."""

    if not all((client_id, client_secret, code, redirect_uri, code_verifier)):
        raise PublishBlocked("YouTube authorization-code exchange is missing required values")

    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
    ).encode("utf-8")
    payload = (transport or HttpTransport()).request(
        "POST",
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=body,
    ).json()

    if payload.get("error"):
        description = payload.get("error_description") or payload.get("error")
        raise PublishBlocked(f"YouTube authorization failed: {description}")

    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    if not isinstance(access_token, str) or not access_token:
        raise PublishError("YouTube token response did not include an access token")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise PublishError(
            "YouTube token response did not include a refresh token; "
            "re-authorize with consent and offline access"
        )
    return payload


def persist_token_state(
    payload: Mapping[str, Any],
    *,
    state_path: Path | None = None,
) -> Path:
    """Persist only long-lived YouTube refresh-token state."""

    refresh_token = payload.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise PublishError("cannot persist YouTube token state without refresh_token")

    path = state_path or (DEFAULT_AUTH_DIR / "youtube.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    state_payload = {
        "refresh_token": refresh_token,
        "scope": payload.get("scope"),
        "token_type": payload.get("token_type"),
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
                message = "YouTube authorization was not completed. You can close this window."
            else:
                code = params.get("code", [""])[0]
                if not code:
                    result["error"] = "Google callback did not include an authorization code"
                    status = 400
                    message = "Authorization failed: no code was returned."
                else:
                    result["code"] = code
                    result["scope"] = params.get("scope", [""])[0]
                    message = "YouTube authorization received. You can close this window."

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
    scopes: tuple[str, ...] = DEFAULT_SCOPES,
    state_path: Path | None = None,
    open_browser: bool = True,
    timeout_seconds: float = 600.0,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    """Run one interactive Google desktop authorization for YouTube upload."""

    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise PublishBlocked(
            "configure YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env.local"
        )

    state = secrets.token_urlsafe(32)
    verifier = generate_code_verifier()
    challenge = code_challenge_for(verifier)
    callback_path = "/callback"
    callback_result: dict[str, str] = {}
    handler = _callback_handler(
        expected_path=callback_path,
        expected_state=state,
        result=callback_result,
    )
    server = HTTPServer(("127.0.0.1", 0), handler)
    server.timeout = timeout_seconds
    redirect_uri = f"http://127.0.0.1:{server.server_port}{callback_path}"

    authorization_url = build_authorization_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scopes=scopes,
        state=state,
        code_challenge=challenge,
    )

    print("YouTube authorization URL:")
    print(authorization_url)
    if open_browser:
        webbrowser.open(authorization_url, new=2)

    try:
        server.handle_request()
    finally:
        server.server_close()

    if "error" in callback_result:
        raise PublishBlocked(
            f"YouTube authorization failed: {callback_result['error']}"
        )
    code = callback_result.get("code")
    if not code:
        raise PublishBlocked(
            "YouTube authorization callback was not received before "
            "the local listener stopped"
        )

    token_payload = exchange_authorization_code(
        client_id=client_id,
        client_secret=client_secret,
        code=code,
        redirect_uri=redirect_uri,
        code_verifier=verifier,
        transport=transport,
    )
    path = persist_token_state(token_payload, state_path=state_path)

    return {
        "status": "AUTHORIZED",
        "scope": token_payload.get("scope"),
        "state_path": str(path),
    }

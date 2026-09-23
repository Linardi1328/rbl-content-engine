from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch

from rbl_content_engine.publishing.__main__ import build_parser
from rbl_content_engine.publishing.core import (
    DEFAULT_AUTH_DIR,
    HttpResponse,
    HttpTransport,
    PublishError,
)
from rbl_content_engine.publishing.youtube_auth import (
    build_authorization_url,
    code_challenge_for,
    exchange_authorization_code,
    generate_code_verifier,
    persist_token_state,
    resolve_token_state_path,
)


class FakeTransport(HttpTransport):
    def __init__(self, response: HttpResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        body: bytes | None = None,
        timeout: int = 120,
    ) -> HttpResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "body": body,
                "timeout": timeout,
            }
        )
        return self.response


class YouTubeDesktopAuthTests(unittest.TestCase):
    def test_pkce_verifier_and_base64url_sha256_challenge(self) -> None:
        verifier = generate_code_verifier(64)
        self.assertEqual(len(verifier), 64)
        challenge = code_challenge_for(verifier)
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        self.assertEqual(challenge, expected)
        self.assertNotIn("=", challenge)

    def test_authorization_url_requests_offline_upload_scope(self) -> None:
        url = build_authorization_url(
            client_id="desktop-client",
            redirect_uri="http://127.0.0.1:49152/callback",
            scopes=("https://www.googleapis.com/auth/youtube.upload",),
            state="csrf-state",
            code_challenge="abc123",
        )
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)

        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "accounts.google.com")
        self.assertEqual(query["client_id"], ["desktop-client"])
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(
            query["scope"],
            ["https://www.googleapis.com/auth/youtube.upload"],
        )
        self.assertEqual(
            query["redirect_uri"],
            ["http://127.0.0.1:49152/callback"],
        )
        self.assertEqual(query["access_type"], ["offline"])
        self.assertEqual(query["prompt"], ["consent"])
        self.assertEqual(query["state"], ["csrf-state"])
        self.assertEqual(query["code_challenge_method"], ["S256"])

    def test_exchange_sends_code_verifier_and_redirect_uri(self) -> None:
        payload = {
            "access_token": "short-lived-access",
            "refresh_token": "long-lived-refresh",
            "expires_in": 3600,
            "scope": "https://www.googleapis.com/auth/youtube.upload",
            "token_type": "Bearer",
        }
        transport = FakeTransport(
            HttpResponse(
                status=200,
                headers={},
                body=json.dumps(payload).encode("utf-8"),
            )
        )

        result = exchange_authorization_code(
            client_id="desktop-client",
            client_secret="desktop-secret",
            code="authorization-code",
            redirect_uri="http://127.0.0.1:49152/callback",
            code_verifier="v" * 64,
            transport=transport,
        )

        self.assertEqual(result["refresh_token"], "long-lived-refresh")
        self.assertEqual(len(transport.calls), 1)
        call = transport.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertEqual(call["url"], "https://oauth2.googleapis.com/token")
        body = urllib.parse.parse_qs(call["body"].decode("utf-8"))
        self.assertEqual(body["grant_type"], ["authorization_code"])
        self.assertEqual(body["code"], ["authorization-code"])
        self.assertEqual(body["code_verifier"], ["v" * 64])
        self.assertEqual(
            body["redirect_uri"],
            ["http://127.0.0.1:49152/callback"],
        )

    def test_persisted_state_excludes_access_token_and_client_secret(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "youtube.json"
            persist_token_state(
                {
                    "access_token": "must-not-persist",
                    "refresh_token": "refresh-me",
                    "scope": "https://www.googleapis.com/auth/youtube.upload",
                    "token_type": "Bearer",
                    "client_secret": "also-must-not-persist",
                },
                state_path=state_path,
            )
            stored_text = state_path.read_text(encoding="utf-8")
            stored = json.loads(stored_text)

            self.assertEqual(stored["refresh_token"], "refresh-me")
            self.assertNotIn("must-not-persist", stored_text)
            self.assertNotIn("also-must-not-persist", stored_text)

    def test_resolve_token_state_path_precedence(self) -> None:
        explicit_path = Path("/custom/youtube.json")
        self.assertEqual(resolve_token_state_path(explicit_path), explicit_path)

        with patch.dict(os.environ, {"YOUTUBE_TOKEN_STATE_PATH": "~/env_youtube.json"}):
            resolved = resolve_token_state_path()
            self.assertEqual(resolved, Path("~/env_youtube.json").expanduser())

            # Explicit path still overrides env var
            self.assertEqual(resolve_token_state_path(explicit_path), explicit_path)

        with patch.dict(os.environ, {}, clear=True):
            resolved_default = resolve_token_state_path()
            self.assertEqual(resolved_default, DEFAULT_AUTH_DIR / "youtube.json")

    def test_persist_token_state_permissions_and_tightening(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target_dir = Path(directory) / "subdir"
            state_path = target_dir / "youtube.json"

            # Pre-create with loose permissions
            target_dir.mkdir(parents=True, exist_ok=True, mode=0o777)
            state_path.write_text("old", encoding="utf-8")
            state_path.chmod(0o666)

            persist_token_state(
                {
                    "refresh_token": "refresh-123",
                    "scope": "https://www.googleapis.com/auth/youtube.upload",
                    "token_type": "Bearer",
                },
                state_path=state_path,
            )

            # Both parent dir and file should be tightened
            file_mode = state_path.stat().st_mode & 0o777
            dir_mode = target_dir.stat().st_mode & 0o777
            self.assertEqual(file_mode, 0o600)
            self.assertEqual(dir_mode, 0o700)

    def test_persist_token_state_fails_closed_on_permission_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "sub" / "youtube.json"
            payload = {
                "refresh_token": "refresh-123",
                "scope": "https://www.googleapis.com/auth/youtube.upload",
                "token_type": "Bearer",
            }

            with patch("os.fchmod", side_effect=OSError("fchmod permission denied")):
                with self.assertRaises(PublishError) as ctx:
                    persist_token_state(payload, state_path=state_path)
                self.assertIn("cannot enforce 0600 permissions", str(ctx.exception))

            with patch.object(Path, "chmod", side_effect=OSError("chmod permission denied")):
                with self.assertRaises(PublishError) as ctx:
                    persist_token_state(payload, state_path=state_path)
                self.assertIn("cannot", str(ctx.exception))

    def test_cli_parser_defaults_timeout_to_600(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["youtube-auth"])
        self.assertEqual(args.timeout_seconds, 600.0)


if __name__ == "__main__":
    unittest.main()

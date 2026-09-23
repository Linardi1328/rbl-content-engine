from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from typing import Any, Mapping

from rbl_content_engine.publishing.core import HttpResponse, HttpTransport
from rbl_content_engine.publishing.youtube_auth import (
    build_authorization_url,
    code_challenge_for,
    exchange_authorization_code,
    generate_code_verifier,
    persist_token_state,
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


if __name__ == "__main__":
    unittest.main()

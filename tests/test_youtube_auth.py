from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import tempfile
import time
import unittest
import urllib.parse
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch

from rbl_content_engine.publishing import youtube_auth
from rbl_content_engine.publishing.__main__ import build_parser
from rbl_content_engine.publishing.core import (
    DEFAULT_AUTH_DIR,
    HttpResponse,
    HttpTransport,
    PublishBlocked,
    PublishError,
    YouTubePublisher,
)
from rbl_content_engine.publishing.youtube_auth import (
    _OAuthServer,
    build_authorization_url,
    code_challenge_for,
    exchange_authorization_code,
    generate_code_verifier,
    persist_token_state,
    resolve_token_state_path,
    run_desktop_oauth,
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


class DummySocket:
    def __init__(self, request_bytes: bytes) -> None:
        self.rfile = io.BytesIO(request_bytes)
        self.wfile = io.BytesIO()

    def makefile(self, mode: str, *args: Any, **kwargs: Any) -> Any:
        if "b" in mode:
            return self.rfile if "r" in mode else self.wfile
        return io.TextIOWrapper(self.rfile if "r" in mode else self.wfile)

    def sendall(self, b: bytes) -> None:
        self.wfile.write(b)


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

    def test_from_env_access_token_takes_precedence_over_invalid_state_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            corrupt_state = Path(directory) / "youtube.json"
            corrupt_state.write_text("NOT VALID JSON {{{", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "YOUTUBE_ACCESS_TOKEN": "mock-access-token",
                    "YOUTUBE_TOKEN_STATE_PATH": str(corrupt_state),
                },
                clear=True,
            ):
                publisher = YouTubePublisher.from_env()
                self.assertEqual(publisher.access_token, "mock-access-token")

    def test_from_env_rejects_non_object_json_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for invalid_content in ["[]", '"just-a-string"', "12345", "null", "true"]:
                state_path = Path(directory) / "youtube.json"
                state_path.write_text(invalid_content, encoding="utf-8")

                with patch.dict(
                    os.environ,
                    {
                        "YOUTUBE_CLIENT_ID": "cid",
                        "YOUTUBE_CLIENT_SECRET": "csec",
                        "YOUTUBE_TOKEN_STATE_PATH": str(state_path),
                    },
                    clear=True,
                ):
                    with self.assertRaises(PublishBlocked) as ctx:
                        YouTubePublisher.from_env()
                    self.assertIn("must be a JSON object", str(ctx.exception))

    def test_from_env_loads_valid_state_when_access_and_refresh_not_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "youtube.json"
            state_path.write_text(
                json.dumps({"refresh_token": "valid-refresh"}),
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "YOUTUBE_CLIENT_ID": "cid",
                    "YOUTUBE_CLIENT_SECRET": "csec",
                    "YOUTUBE_TOKEN_STATE_PATH": str(state_path),
                },
                clear=True,
            ):
                publisher = YouTubePublisher.from_env()
                self.assertEqual(publisher.refresh_token, "valid-refresh")

    def test_oauth_listener_ignores_irrelevant_request_first(self) -> None:
        intercepted_state = None
        orig_build = youtube_auth.build_authorization_url

        def capture_build(**kwargs: Any) -> str:
            nonlocal intercepted_state
            intercepted_state = kwargs["state"]
            return orig_build(**kwargs)

        calls = 0

        def mock_handle_request(server_self: Any) -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                sock = DummySocket(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
                server_self.RequestHandlerClass(sock, ("127.0.0.1", 12345), server_self)
            else:
                req = (
                    f"GET /callback?state={intercepted_state}&code=valid_code HTTP/1.1\r\nHost: localhost\r\n\r\n"
                ).encode("utf-8")
                sock = DummySocket(req)
                server_self.RequestHandlerClass(sock, ("127.0.0.1", 12345), server_self)

        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "youtube.json"
            with (
                patch.dict(
                    os.environ,
                    {"YOUTUBE_CLIENT_ID": "cid", "YOUTUBE_CLIENT_SECRET": "csec"},
                ),
                patch.object(youtube_auth, "build_authorization_url", side_effect=capture_build),
                patch.object(
                    _OAuthServer,
                    "handle_request",
                    autospec=True,
                    side_effect=mock_handle_request,
                ),
            ):
                res = run_desktop_oauth(
                    state_path=state_path,
                    open_browser=False,
                    transport=FakeTransport(
                        HttpResponse(
                            200,
                            {},
                            json.dumps(
                                {
                                    "access_token": "a",
                                    "refresh_token": "r",
                                    "scope": "https://www.googleapis.com/auth/youtube.upload",
                                }
                            ).encode("utf-8"),
                        )
                    ),
                )
                self.assertEqual(res["status"], "AUTHORIZED")
                self.assertEqual(calls, 2)

    def test_oauth_listener_ignores_mismatched_state_first(self) -> None:
        intercepted_state = None
        orig_build = youtube_auth.build_authorization_url

        def capture_build(**kwargs: Any) -> str:
            nonlocal intercepted_state
            intercepted_state = kwargs["state"]
            return orig_build(**kwargs)

        calls = 0

        def mock_handle_request(server_self: Any) -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                sock = DummySocket(b"GET /callback?state=wrong_state&code=bad HTTP/1.1\r\nHost: localhost\r\n\r\n")
                server_self.RequestHandlerClass(sock, ("127.0.0.1", 12345), server_self)
            else:
                req = (
                    f"GET /callback?state={intercepted_state}&code=valid_code HTTP/1.1\r\nHost: localhost\r\n\r\n"
                ).encode("utf-8")
                sock = DummySocket(req)
                server_self.RequestHandlerClass(sock, ("127.0.0.1", 12345), server_self)

        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "youtube.json"
            with (
                patch.dict(
                    os.environ,
                    {"YOUTUBE_CLIENT_ID": "cid", "YOUTUBE_CLIENT_SECRET": "csec"},
                ),
                patch.object(youtube_auth, "build_authorization_url", side_effect=capture_build),
                patch.object(
                    _OAuthServer,
                    "handle_request",
                    autospec=True,
                    side_effect=mock_handle_request,
                ),
            ):
                res = run_desktop_oauth(
                    state_path=state_path,
                    open_browser=False,
                    transport=FakeTransport(
                        HttpResponse(
                            200,
                            {},
                            json.dumps(
                                {
                                    "access_token": "a",
                                    "refresh_token": "r",
                                    "scope": "https://www.googleapis.com/auth/youtube.upload",
                                }
                            ).encode("utf-8"),
                        )
                    ),
                )
                self.assertEqual(res["status"], "AUTHORIZED")
                self.assertEqual(calls, 2)

    def test_oauth_listener_times_out_with_no_callback(self) -> None:
        def mock_timeout(server_self: Any) -> None:
            time.sleep(0.06)

        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "youtube.json"
            with (
                patch.dict(
                    os.environ,
                    {"YOUTUBE_CLIENT_ID": "cid", "YOUTUBE_CLIENT_SECRET": "csec"},
                ),
                patch.object(_OAuthServer, "handle_request", autospec=True, side_effect=mock_timeout),
            ):
                with self.assertRaises(PublishBlocked) as ctx:
                    run_desktop_oauth(
                        state_path=state_path,
                        open_browser=False,
                        timeout_seconds=0.05,
                    )
                self.assertIn("callback was not received before", str(ctx.exception))

    def test_persist_token_state_custom_path_preserves_parent_permissions_and_tightens_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target_dir = Path(directory) / "subdir"
            target_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
            target_dir.chmod(0o755)
            state_path = target_dir / "youtube.json"
            state_path.write_text("old", encoding="utf-8")
            state_path.chmod(0o644)

            persist_token_state(
                {
                    "refresh_token": "refresh-123",
                    "scope": "https://www.googleapis.com/auth/youtube.upload",
                    "token_type": "Bearer",
                },
                state_path=state_path,
            )

            # Custom parent directory must NOT be chmodded
            dir_mode = target_dir.stat().st_mode & 0o777
            self.assertEqual(dir_mode, 0o755)

            # File itself must be tightened to 0o600
            file_mode = state_path.stat().st_mode & 0o777
            self.assertEqual(file_mode, 0o600)

    def test_persist_token_state_default_dir_secures_owner_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake_auth_dir = Path(directory) / "social-auth"
            fake_default_file = fake_auth_dir / "youtube.json"

            with (
                patch("rbl_content_engine.publishing.youtube_auth.DEFAULT_AUTH_DIR", fake_auth_dir),
                patch.dict(os.environ, {}, clear=True),
            ):
                persist_token_state(
                    {
                        "refresh_token": "refresh-default",
                        "scope": "https://www.googleapis.com/auth/youtube.upload",
                        "token_type": "Bearer",
                    },
                    state_path=fake_default_file,
                )
                self.assertEqual(fake_auth_dir.stat().st_mode & 0o777, 0o700)
                self.assertEqual(fake_default_file.stat().st_mode & 0o777, 0o600)

    def test_persist_token_state_rejects_final_target_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target_file = Path(directory) / "real_file.json"
            target_file.write_text("ORIGINAL SENSITIVE DATA", encoding="utf-8")

            symlink_path = Path(directory) / "symlink.json"
            os.symlink(target_file, symlink_path)

            with self.assertRaises(PublishError) as ctx:
                persist_token_state(
                    {
                        "refresh_token": "refresh-symlink",
                        "scope": "https://www.googleapis.com/auth/youtube.upload",
                        "token_type": "Bearer",
                    },
                    state_path=symlink_path,
                )
            self.assertIn("is a symlink", str(ctx.exception))
            # Verify target file was never truncated or touched
            self.assertEqual(target_file.read_text(encoding="utf-8"), "ORIGINAL SENSITIVE DATA")

    def test_persist_token_state_rejects_symlinked_parent_component(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            real_parent = Path(directory) / "real_dir"
            real_parent.mkdir(parents=True, exist_ok=True, mode=0o755)

            symlink_parent = Path(directory) / "symlink_dir"
            os.symlink(real_parent, symlink_parent)

            state_path = symlink_parent / "youtube.json"

            with self.assertRaises(PublishError) as ctx:
                persist_token_state(
                    {
                        "refresh_token": "refresh-symlink-parent",
                        "scope": "https://www.googleapis.com/auth/youtube.upload",
                        "token_type": "Bearer",
                    },
                    state_path=state_path,
                )
            self.assertIn("component is a symlink", str(ctx.exception))

    def test_persist_token_state_atomic_replacement_and_failure_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "youtube.json"
            state_path.write_text("PREVIOUS VALID STATE", encoding="utf-8")
            state_path.chmod(0o600)

            payload = {
                "refresh_token": "refresh-atomic",
                "scope": "https://www.googleapis.com/auth/youtube.upload",
                "token_type": "Bearer",
            }

            # Simulate failure during atomic replacement
            with patch("os.replace", side_effect=OSError("simulated disk rename error")):
                with self.assertRaises(PublishError) as ctx:
                    persist_token_state(payload, state_path=state_path)
                self.assertIn("cannot atomically replace", str(ctx.exception))

            # Previous file should remain completely intact
            self.assertEqual(state_path.read_text(encoding="utf-8"), "PREVIOUS VALID STATE")

            # Any temporary files in directory should have been cleaned up
            remaining_temps = [p for p in Path(directory).iterdir() if p.name.startswith(".youtube-")]
            self.assertEqual(remaining_temps, [])

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

            with patch("os.chmod", side_effect=OSError("chmod permission denied")):
                with self.assertRaises(PublishError) as ctx:
                    persist_token_state(payload, state_path=state_path)
                self.assertIn("cannot enforce 0600 permissions", str(ctx.exception))

    def test_cli_parser_defaults_timeout_to_600(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["youtube-auth"])
        self.assertEqual(args.timeout_seconds, 600.0)


if __name__ == "__main__":
    unittest.main()

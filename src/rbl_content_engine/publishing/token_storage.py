"""Fail-closed atomic local persistence for sensitive OAuth refresh-token state."""

from __future__ import annotations

import json
import os
import secrets
import stat
from pathlib import Path
from typing import Any, Mapping

from .core import DEFAULT_AUTH_DIR, PublishError


def write_private_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Atomically replace a private JSON file; never create tokens with loose modes."""
    if not hasattr(os, "O_NOFOLLOW"):
        raise PublishError("secure token state storage requires O_NOFOLLOW support")

    path = path.expanduser()
    if path.is_symlink():
        raise PublishError("token state destination must not be a symlink")

    uid = os.getuid() if hasattr(os, "getuid") else -1
    for ancestor in path.parents:
        if not ancestor.is_symlink():
            continue
        try:
            holder = ancestor.parent.stat()
        except OSError as exc:
            raise PublishError("cannot inspect token state path") from exc
        if holder.st_uid not in (0, uid) or (holder.st_mode & 0o022):
            raise PublishError("token state path contains an untrusted symlink")

    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if parent.resolve() == DEFAULT_AUTH_DIR.resolve():
            parent.chmod(0o700)
        info = parent.stat()
        if not stat.S_ISDIR(info.st_mode) or (info.st_mode & 0o022):
            raise PublishError("token state directory must not be writable by other users")
        if path.exists() and not path.is_file():
            raise PublishError("token state destination must be a regular file")
    except OSError as exc:
        raise PublishError("cannot prepare secure token state directory") from exc

    temporary = parent / f".tiktok-token-{secrets.token_hex(12)}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        fd = os.open(temporary, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if path.is_symlink():
            raise PublishError("token state destination changed to a symlink")
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except OSError as exc:
        raise PublishError("could not persist secure OAuth token state") from exc
    finally:
        temporary.unlink(missing_ok=True)

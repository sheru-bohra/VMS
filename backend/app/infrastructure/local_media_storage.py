"""Local filesystem storage for visitor media."""

from __future__ import annotations

import os
from pathlib import Path

from app.core.config import settings


class LocalMediaStorageError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def media_root() -> Path:
    return settings.resolved_local_media_root


def resolve_storage_path(storage_rel_path: str) -> Path:
    rel = storage_rel_path.replace("\\", "/").lstrip("/")
    if ".." in rel.split("/"):
        raise LocalMediaStorageError("invalid_path", "Invalid media path.")
    root = media_root().resolve()
    full = (root / rel).resolve()
    if not str(full).startswith(str(root)):
        raise LocalMediaStorageError("invalid_path", "Invalid media path.")
    return full


def ensure_photo_dir(year: int, month: int) -> str:
    rel = f"photos/{year:04d}/{month:02d}"
    full = media_root() / rel
    full.mkdir(parents=True, exist_ok=True)
    return rel


def write_bytes(rel_dir: str, filename: str, data: bytes) -> str:
    safe_name = os.path.basename(filename)
    if safe_name != filename or ".." in filename:
        raise LocalMediaStorageError("invalid_file_name", "Invalid file name.")
    rel_path = f"{rel_dir}/{safe_name}"
    full = resolve_storage_path(rel_path)
    full.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(full), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
    except OSError as exc:
        raise LocalMediaStorageError("write_failed", "Unable to save media file.") from exc
    return rel_path


def read_bytes(storage_rel_path: str) -> bytes:
    full = resolve_storage_path(storage_rel_path)
    if not full.is_file():
        raise LocalMediaStorageError("not_found", "Media file not found.")
    return full.read_bytes()


def delete_file(storage_rel_path: str) -> None:
    try:
        full = resolve_storage_path(storage_rel_path)
        if full.is_file():
            full.unlink()
    except LocalMediaStorageError:
        pass


def rename_file(old_rel: str, new_rel: str) -> str:
    old_full = resolve_storage_path(old_rel)
    new_full = resolve_storage_path(new_rel)
    if not old_full.is_file():
        raise LocalMediaStorageError("not_found", "Media file not found.")
    new_full.parent.mkdir(parents=True, exist_ok=True)
    old_full.rename(new_full)
    return new_rel

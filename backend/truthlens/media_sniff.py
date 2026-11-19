"""Identify media from bytes. Extensions are hints, not proof."""

from __future__ import annotations

import os
import re

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 20_000
MAX_PIXELS = 12_000_000

_IMAGE_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
_VIDEO_EXT = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/mp4",
    ".webm": "video/webm",
    ".avi": "video/avi",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
_AUDIO_EXT = {".wav": "audio/wav"}


class RejectedUpload(Exception):
    def __init__(self, detail: str, code: str):
        super().__init__(detail)
        self.detail = detail
        self.code = code


def sanitize_filename(name: str) -> str:
    base = os.path.basename((name or "").replace("\\", "/").strip())
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    base = base.strip("._")[:80]
    return base or "upload"


def extension_of(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def sniff_mime(data: bytes) -> str | None:
    if len(data) >= 8 and data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 3 and data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "audio/wav"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"AVI ":
        return "video/avi"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return "video/mp4"
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    return None


def _expect(data: bytes, filename: str, allowed_ext: dict[str, str], slot: str) -> str:
    if not data:
        raise RejectedUpload(f"{slot} file is empty.", "empty_file")
    if len(data) > MAX_FILE_BYTES:
        raise RejectedUpload(
            f"{slot} file is {len(data)} bytes. The limit is {MAX_FILE_BYTES} bytes.",
            "file_too_large",
        )
    sniffed = sniff_mime(data)
    if sniffed is None:
        raise RejectedUpload(
            f"{slot} bytes do not match a supported file signature. "
            "The extension was not trusted.",
            "unrecognized_signature",
        )
    ext = extension_of(filename)
    if ext:
        expected = allowed_ext.get(ext)
        if expected is None:
            raise RejectedUpload(
                f"{slot} extension '{ext}' is not accepted for this slot.",
                "extension_rejected",
            )
        if expected != sniffed:
            raise RejectedUpload(
                f"{slot} extension '{ext}' does not match the byte signature {sniffed}.",
                "extension_mismatch",
            )
    elif sniffed not in set(allowed_ext.values()):
        raise RejectedUpload(
            f"{slot} signature {sniffed} is not accepted for this slot.",
            "signature_rejected",
        )
    return sniffed


def validate_image(data: bytes, filename: str) -> str:
    return _expect(data, filename, _IMAGE_EXT, "Image")


def validate_video(data: bytes, filename: str) -> str:
    return _expect(data, filename, _VIDEO_EXT, "Video")


def validate_audio(data: bytes, filename: str) -> str:
    return _expect(data, filename, _AUDIO_EXT, "Audio")


def validate_text(value: str, label: str) -> str:
    text = value or ""
    if len(text) > MAX_TEXT_CHARS:
        raise RejectedUpload(
            f"{label} is longer than {MAX_TEXT_CHARS} characters.",
            "text_too_long",
        )
    return text

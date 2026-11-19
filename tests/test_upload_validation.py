"""Automated tests for upload validation, content sniffing, and sanitization."""

from __future__ import annotations

import io
import pytest
from PIL import Image

from backend.truthlens.media_sniff import (
    MAX_FILE_BYTES,
    MAX_TEXT_CHARS,
    MAX_TOTAL_BYTES,
    RejectedUpload,
    extension_of,
    sanitize_filename,
    sniff_mime,
    validate_audio,
    validate_image,
    validate_text,
    validate_video,
)


def _tiny_png() -> bytes:
    img = Image.new("RGB", (8, 8), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _tiny_jpeg() -> bytes:
    img = Image.new("RGB", (8, 8), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _tiny_gif() -> bytes:
    img = Image.new("RGB", (8, 8), color="green")
    buf = io.BytesIO()
    img.save(buf, format="GIF")
    return buf.getvalue()


def _tiny_wav() -> bytes:
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as h:
        h.setnchannels(1)
        h.setsampwidth(2)
        h.setframerate(16000)
        h.writeframes(b"\x00\x00" * 100)
    return buf.getvalue()


def test_sniff_mime_signatures():
    assert sniff_mime(_tiny_png()) == "image/png"
    assert sniff_mime(_tiny_jpeg()) == "image/jpeg"
    assert sniff_mime(_tiny_gif()) == "image/gif"
    assert sniff_mime(_tiny_wav()) == "audio/wav"
    assert sniff_mime(b"\x00\x01\x02\x03\x04\x05") is None


def test_sanitize_filename_traversal():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\windows\\system32\\cmd.exe") == "cmd.exe"
    assert sanitize_filename("safe-photo.123_test.jpg") == "safe-photo.123_test.jpg"
    assert sanitize_filename("") == "upload"
    assert sanitize_filename("   ") == "upload"
    # special characters converted to underscore
    assert sanitize_filename("foo$bar#baz?.png") == "foo_bar_baz_.png"


def test_extension_of():
    assert extension_of("photo.JPG") == ".jpg"
    assert extension_of("audio.WAV") == ".wav"
    assert extension_of("no_ext") == ""


def test_validate_image_valid():
    png_bytes = _tiny_png()
    mime = validate_image(png_bytes, "test.png")
    assert mime == "image/png"

    jpg_bytes = _tiny_jpeg()
    mime = validate_image(jpg_bytes, "test.jpg")
    assert mime == "image/jpeg"


def test_validate_image_mismatch_rejected():
    png_bytes = _tiny_png()
    with pytest.raises(RejectedUpload) as exc:
        validate_image(png_bytes, "test.jpg")
    assert exc.value.code == "extension_mismatch"


def test_validate_image_unrecognized():
    with pytest.raises(RejectedUpload) as exc:
        validate_image(b"NOT_AN_IMAGE_AT_ALL", "fake.jpg")
    assert exc.value.code == "unrecognized_signature"


def test_validate_empty_file():
    with pytest.raises(RejectedUpload) as exc:
        validate_image(b"", "empty.jpg")
    assert exc.value.code == "empty_file"


def test_validate_file_too_large():
    huge_data = b"\xff\xd8\xff" + (b"\x00" * (MAX_FILE_BYTES + 10))
    with pytest.raises(RejectedUpload) as exc:
        validate_image(huge_data, "large.jpg")
    assert exc.value.code == "file_too_large"


def test_validate_video_gif_and_avi():
    gif_bytes = _tiny_gif()
    assert validate_video(gif_bytes, "animation.gif") == "image/gif"

    # Minimal AVI RIFF header
    avi_header = b"RIFF\x24\x00\x00\x00AVI LIST\x00\x00\x00\x00"
    assert validate_video(avi_header, "clip.avi") == "video/avi"


def test_validate_audio_wav():
    wav_bytes = _tiny_wav()
    assert validate_audio(wav_bytes, "test.wav") == "audio/wav"

    with pytest.raises(RejectedUpload) as exc:
        validate_audio(wav_bytes, "test.mp3")
    assert exc.value.code == "extension_rejected"


def test_validate_text_limits():
    valid = "Hello world " * 50
    assert validate_text(valid, "Statement") == valid

    oversized = "a" * (MAX_TEXT_CHARS + 50)
    with pytest.raises(RejectedUpload) as exc:
        validate_text(oversized, "Statement")
    assert exc.value.code == "text_too_long"

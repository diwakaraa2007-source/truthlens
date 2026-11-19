"""Automated tests for each available analyzer module on real decoded buffers."""

from __future__ import annotations

import io
import os
import tempfile
import wave
import numpy as np
import pytest
from PIL import Image

from backend.truthlens.audio_lab import analyze_audio
from backend.truthlens.fusion import fuse
from backend.truthlens.image_lab import analyze_image
from backend.truthlens.report import sha256_hex
from backend.truthlens.text_lab import analyze_text
from backend.truthlens.video_lab import analyze_video


def _make_test_jpeg(seed: int = 42, paste_rect: bool = False) -> bytes:
    rng = np.random.default_rng(seed)
    pixels = rng.integers(0, 256, size=(64, 64, 3), dtype=np.uint8)
    img = Image.fromarray(pixels, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)
    if not paste_rect:
        return buf.getvalue()
    reopened = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    for y in range(16, 48):
        for x in range(16, 48):
            reopened.putpixel((x, y), (250, 250, 250))
    buf2 = io.BytesIO()
    reopened.save(buf2, format="JPEG", quality=90)
    return buf2.getvalue()


def _make_test_gif(manipulated: bool = False) -> bytes:
    frames = []
    for i in range(6):
        level = 40 + i * 10
        if manipulated and i == 3:
            level = 255
        frames.append(Image.new("RGB", (32, 32), (level, level, level)))
    buf = io.BytesIO()
    frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:], duration=100, loop=0)
    return buf.getvalue()


def _make_test_avi(manipulated: bool = False) -> bytes:
    import cv2
    with tempfile.NamedTemporaryFile(suffix=".avi", delete=False) as f:
        tpath = f.name
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    out = cv2.VideoWriter(tpath, fourcc, 10.0, (32, 32))
    for i in range(6):
        level = 255 if (manipulated and i == 3) else 30 + i * 15
        out.write(np.full((32, 32, 3), level, dtype=np.uint8))
    out.release()
    data = open(tpath, "rb").read()
    os.remove(tpath)
    return data


def _make_test_wav(cutoff: bool = False) -> bytes:
    rng = np.random.default_rng(123)
    samples = rng.uniform(-0.8, 0.8, size=8000)
    if cutoff:
        spectrum = np.fft.rfft(samples)
        freqs = np.fft.rfftfreq(samples.size, d=1.0 / 16000)
        spectrum[freqs >= 3000] = 0
        samples = np.fft.irfft(spectrum, n=samples.size).real
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as h:
        h.setnchannels(1)
        h.setsampwidth(2)
        h.setframerate(16000)
        h.writeframes(pcm.tobytes())
    return buf.getvalue()


def test_image_analyzer_clean_jpeg():
    data = _make_test_jpeg(paste_rect=False)
    digest = sha256_hex(data)
    res = analyze_image(data, digest)
    assert res["status"] == "analyzed"
    assert "ela_min_block_mean" in res["measurements"]
    assert "fft_peak_ratio" in res["measurements"]
    assert "highpass_quadrant_ratio" in res["measurements"]
    assert len(res["observations"]) >= 4
    # Check that EXIF presence is observed without being treated as manipulation
    exif_obs = [o for o in res["observations"] if o["name"] == "EXIF presence"][0]
    assert exif_obs["threshold_exceeded"] is False
    assert "visualizations" in res
    assert res["visualizations"]["ela_heatmap"].startswith("data:image/png;base64,")


def test_image_analyzer_corrupted_data():
    bad_data = b"\xff\xd8\xff\xe0CORRUPTED_BYTES_HERE"
    res = analyze_image(bad_data, sha256_hex(bad_data))
    assert res["status"] == "analysis_failed"
    assert "could not be decoded" in res["error"]


def test_video_analyzer_gif():
    data = _make_test_gif(manipulated=True)
    digest = sha256_hex(data)
    res = analyze_video(data, digest, ".gif")
    assert res["status"] == "analyzed"
    assert res["metadata"]["sampled_frame_count"] == 6
    assert len(res["metadata"]["source_timestamps_seconds"]) == 6
    assert res["measurements"]["max_mean_absolute_difference"] > 5.0
    assert len(res["indicators"]) >= 1
    hit = res["indicators"][0]
    assert hit["frame_number"] == 3
    assert hit["timestamp_seconds"] is not None


def test_video_analyzer_avi_opencv():
    data = _make_test_avi(manipulated=True)
    digest = sha256_hex(data)
    res = analyze_video(data, digest, ".avi")
    assert res["status"] == "analyzed"
    assert "OpenCV" in res["metadata"]["decoder"]
    assert res["metadata"]["sampled_frame_count"] == 6
    assert len(res["frame_steps"]) == 5
    assert len(res["indicators"]) >= 1
    assert res["visualizations"]["frame_difference_chart"].startswith("data:image/png;base64,")


def test_video_analyzer_corrupted_bytes():
    bad_data = b"RIFF\x20\x00\x00\x00AVI NOT_VALID"
    res = analyze_video(bad_data, sha256_hex(bad_data), ".avi")
    assert res["status"] in {"analysis_failed", "unsupported"}


def test_audio_analyzer_pcm_wav():
    data = _make_test_wav(cutoff=True)
    digest = sha256_hex(data)
    res = analyze_audio(data, digest)
    assert res["status"] == "analyzed"
    assert res["metadata"]["sample_rate_hz"] == 16000
    assert res["metadata"]["rolloff_99_hz"] <= 4000.0
    assert len(res["indicators"]) >= 1
    assert "visualizations" in res
    assert res["visualizations"]["magnitude_spectrogram"].startswith("data:image/png;base64,")


def test_audio_analyzer_corrupted_wav():
    res = analyze_audio(b"RIFF\x20\x00\x00\x00WAVE_CORRUPT", "dummyhash")
    assert res["status"] == "analysis_failed"


def test_text_analyzer_lexical_overlap():
    text1 = "The urgent transfer must be wired immediately"
    text2 = "A confidential transfer wired to the account now"
    res = analyze_text(text1, text2, "texthash")
    assert res["status"] == "analyzed"
    assert "transfer" in res["lexical"]["shared_tokens"]
    assert "wired" in res["lexical"]["shared_tokens"]
    assert res["lexical"]["jaccard"] is not None
    # Check that urgency keywords co-occur without causal claim
    obs_names = [o["name"] for o in res["observations"]]
    assert "Lexical urgency list" in obs_names
    urgency_obs = [o for o in res["observations"] if o["name"] == "Lexical urgency list"][0]
    assert "does not prove" in urgency_obs["limitation"]


def test_cross_modal_fusion_cooccurrence_and_conflict():
    parts = {
        "image": {
            "status": "analyzed",
            "observations": [{"threshold_exceeded": True, "name": "JPEG error-level block contrast"}],
        },
        "video": {
            "status": "analyzed",
            "observations": [{"threshold_exceeded": False, "name": "Sampled frame difference"}],
        },
        "audio": {
            "status": "not_provided",
            "observations": [],
        },
    }
    fused = fuse(parts)
    assert fused["status"] == "cooccurrence_only"
    assert "image" in fused["analyzed_modalities"]
    assert "video" in fused["analyzed_modalities"]
    assert "audio" in fused["missing_or_not_run"]
    assert len(fused["conflict"]) >= 1
    assert "audio_visual_sync_status" in fused
    assert "No lip-sync" in fused["audio_visual_sync_reason"]

"""Automated tests verifying report JSON integrity, hash chains, and HTTP API endpoints."""

from __future__ import annotations

import json
from starlette.testclient import TestClient

from backend.server import app
from backend.truthlens import TOOL_VERSION
from backend.truthlens.fixtures import write_fixtures

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "local"
    assert data["tool_version"] == TOOL_VERSION
    assert data["learned_detectors"] == "unavailable"
    assert "video_decoders" in data
    assert data["video_decoders"]["opencv"] is True


def test_privacy_endpoint():
    res = client.get("/api/privacy")
    assert res.status_code == 200
    data = res.json()
    assert "local" in data["where_processing_runs"].lower()
    assert "memory" in data["memory"].lower()
    assert "None" in data["third_party_model_services"]


def test_detectors_endpoint():
    res = client.get("/api/detectors")
    assert res.status_code == 200
    detectors = res.json()
    assert len(detectors) >= 10
    ids = [d["id"] for d in detectors]
    assert "jpeg_ela_block_contrast" in ids
    assert "sampled_frame_mad" in ids
    assert "wav_spectral_rolloff" in ids
    assert "ai_generated_image_classifier" in ids


def test_preset_run_endpoint():
    res = client.post("/api/cases/preset/GFX-JPEG-PASTE/run")
    assert res.status_code == 200
    report = res.json()
    assert report["report_id"].startswith("TL-RPT-")
    assert report["simulation"] is True
    assert report["timezone"] == "UTC"
    assert report["conclusion"] == "Indicators for human review"
    assert len(report["observations"]) >= 1


def test_multimodal_analyze_endpoint():
    fixtures_dir = write_fixtures()
    jpg_data = (fixtures_dir / "generated-consistent-noise.jpg").read_bytes()
    wav_data = (fixtures_dir / "generated-broadband.wav").read_bytes()

    files = [
        ("image_file", ("test_image.jpg", jpg_data, "image/jpeg")),
        ("audio_file", ("test_audio.wav", wav_data, "audio/wav")),
    ]
    data = {
        "text_content": "Official security advisory notice",
        "comparison_text": "Public safety alert",
        "case_id": "TEST-INTAKE-99",
    }
    res = client.post("/api/analyze/multimodal", files=files, data=data)
    assert res.status_code == 200
    report = res.json()
    assert report["case_id"] == "TEST-INTAKE-99"
    assert report["report_id"].startswith("TL-RPT-")
    assert report["simulation"] is False
    assert report["analysis_origin"] == "custom_upload"
    assert len(report["evidence_inventory"]) == 3  # image, audio, pasted text
    assert report["byte_identity_digest"] is not None

    # Verify JSON dump and load consistency
    dumped = json.dumps(report)
    reloaded = json.loads(dumped)
    assert reloaded["report_id"] == report["report_id"]

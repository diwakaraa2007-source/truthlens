"""Automated tests ensuring temporary files are safely deleted and privacy controls hold."""

from __future__ import annotations

import glob
import os
import tempfile
import pytest

from backend.truthlens.fixtures import write_fixtures
from backend.truthlens.report import sha256_hex
from backend.truthlens.video_lab import analyze_video


def _count_temp_video_dirs() -> int:
    temp_root = tempfile.gettempdir()
    return len(glob.glob(os.path.join(temp_root, "truthlens_video_*")))


def test_temporary_video_cleanup_on_success():
    fixtures_dir = write_fixtures()
    avi_path = fixtures_dir / "generated-smooth.avi"
    assert avi_path.exists()
    data = avi_path.read_bytes()

    before_count = _count_temp_video_dirs()
    res = analyze_video(data, sha256_hex(data), ".avi")
    after_count = _count_temp_video_dirs()

    assert res["status"] == "analyzed"
    assert after_count == before_count, "Temporary video directory was not cleaned up on success"


def test_temporary_video_cleanup_on_corrupt_data():
    corrupt_avi = b"RIFF\x20\x00\x00\x00AVI NOT_A_REAL_VIDEO"

    before_count = _count_temp_video_dirs()
    res = analyze_video(corrupt_avi, sha256_hex(corrupt_avi), ".avi")
    after_count = _count_temp_video_dirs()

    assert res["status"] in {"analysis_failed", "unsupported"}
    assert after_count == before_count, "Temporary video directory was not cleaned up on decode error"


def test_no_persisted_evidence_files_created():
    from backend.server import ROOT
    # Ingestion should not create an evidence folder or write raw user files to disk
    fixtures_count = len(list((ROOT / "fixtures" / "generated").iterdir())) if (ROOT / "fixtures" / "generated").exists() else 0
    # Confirm that neither ROOT / 'uploads' nor ROOT / 'evidence' exists
    assert not (ROOT / "uploads").exists()
    assert not (ROOT / "evidence").exists()
    assert not (ROOT / "cases").exists()

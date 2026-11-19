"""Automated tests verifying strict separation between simulation fixtures and custom uploads."""

from __future__ import annotations

import pytest
from backend.truthlens.fixtures import CATALOG, fixture_by_id, preset_public_records, write_fixtures
from backend.truthlens.report import WATERMARK, build_report


def test_preset_catalog_has_documented_labels_and_construction():
    for item in CATALOG:
        assert item["case_id"].startswith("GFX-")
        assert "documented_label" in item
        assert "construction" in item
        assert item["documented_label"].startswith("synthetic_")
        assert len(item["modalities_included"]) >= 1


def test_preset_public_records_do_not_store_measurements():
    records = preset_public_records()
    for rec in records:
        assert rec["watermark"] == WATERMARK
        assert rec["analysis_origin"] == "generated_fixture"
        assert "SIMULATION / GENERATED FIXTURE" in rec["description"]
        assert "No measurement is stored on this card" in rec["expected_findings"]
        # Must not contain precalculated hashes, scores, or frame findings
        assert "sha256" not in rec
        assert "measurements" not in rec
        assert "observations" not in rec
        assert "indicators" not in rec


def test_preset_run_produces_watermarked_report():
    spec = fixture_by_id("GFX-JPEG-PASTE")
    assert spec is not None
    fixtures_dir = write_fixtures()
    data = (fixtures_dir / spec["filename"]).read_bytes()

    report = build_report(
        case_id="GFX-JPEG-PASTE",
        simulation=True,
        analysis_origin="generated_fixture",
        fixture=spec,
        image={
            "data": data,
            "filename": spec["filename"],
            "media_type": "image/jpeg",
            "role": "generated_fixture",
            "suffix": ".jpg",
        },
    )

    assert report["simulation"] is True
    assert report["watermark"] == WATERMARK
    assert report["export_banner"] == WATERMARK
    assert report["analysis_origin"] == "generated_fixture"
    assert WATERMARK in report["executive_summary"]
    assert report["fixture"] is not None
    assert report["fixture"]["documented_label"] == spec["documented_label"]


def test_custom_upload_report_is_not_watermarked_as_simulation():
    clean_jpg = (write_fixtures() / "generated-consistent-noise.jpg").read_bytes()

    report = build_report(
        case_id="TL-CUSTOM-001",
        simulation=False,
        analysis_origin="custom_upload",
        image={
            "data": clean_jpg,
            "filename": "custom_user_photo.jpg",
            "media_type": "image/jpeg",
            "role": "uploaded_bytes",
            "suffix": ".jpg",
        },
    )

    assert report["simulation"] is False
    assert report["watermark"] is None
    assert report["analysis_origin"] == "custom_upload"
    assert report["fixture"] is None
    assert "LOCAL SCREENING REPORT" in report["export_banner"]
    assert "Measurements in this response come from the bytes submitted in this request" in report["executive_summary"]
    assert len(report["evidence_inventory"]) == 1
    inv = report["evidence_inventory"][0]
    assert inv["filename"] == "custom_user_photo.jpg"
    assert inv["role"] == "uploaded_bytes"

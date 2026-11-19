"""Automated checks ensuring no unsupported or misleading claims exist in reports or detectors."""

from __future__ import annotations

import json
import pytest
from backend.truthlens.detectors import detector_registry
from backend.truthlens.fixtures import write_fixtures
from backend.truthlens.report import build_report

FORBIDDEN_PHRASES = [
    "calibrated verdict",
    "calibrated confidence interval",
    "very high confidence",
    "authenticity index",
    "critical risk",
    "immutable audit chain",
    "NIST compliant",
    "nist compliant",
]


def test_detector_registry_claims():
    detectors = detector_registry()
    for d in detectors:
        text = json.dumps(d).lower()
        for forbidden in FORBIDDEN_PHRASES:
            assert forbidden.lower() not in text, f"Found forbidden phrase '{forbidden}' in detector {d['id']}"

        if d["kind"] == "learned":
            assert d["status"] == "UNAVAILABLE"
            assert d["blocker"] is not None
        elif d["kind"] == "heuristic":
            assert d["status"] == "UNVALIDATED PROTOTYPE"
            assert "known_limitations" in d


def test_report_wording_and_neutral_conclusion():
    fixtures_dir = write_fixtures()
    data = (fixtures_dir / "generated-consistent-noise.jpg").read_bytes()

    report = build_report(
        case_id="TL-TEST-WORDING",
        simulation=False,
        analysis_origin="custom_upload",
        image={
            "data": data,
            "filename": "sample.jpg",
            "media_type": "image/jpeg",
            "role": "uploaded_bytes",
            "suffix": ".jpg",
        },
    )

    # Conclusion must be neutral
    assert report["conclusion"] == "Indicators for human review"

    # Check serialization for forbidden phrases
    serialized = json.dumps(report).lower()
    for forbidden in FORBIDDEN_PHRASES:
        assert forbidden.lower() not in serialized, f"Found forbidden phrase '{forbidden}' in report JSON"

    # Verify no combined real/fake probability exists
    assert "probability" not in report or report.get("probability") is None
    assert "real_fake_score" not in report

    # Verify each observation has explicit caveats and non-probability semantics
    for obs in report["observations"]:
        assert "not a probability" in obs["score_type"] or "presence flag" in obs["score_type"] or "count of" in obs["score_type"]
        assert len(obs["alternative_explanations"]) >= 1
        assert obs["limitation"]
        assert "confidence_semantics" in obs
        assert "not a probability" in obs["confidence_semantics"].lower()


def test_missing_modality_is_not_negative_result():
    report = build_report(
        case_id="TL-MISSING-TEST",
        simulation=False,
        analysis_origin="custom_upload",
        statement="Just a single statement",
    )

    parts = report["modality_analyses"]
    for modality in ["image", "video", "audio"]:
        assert parts[modality]["status"] == "not_provided"
        assert "not a negative result" in parts[modality]["note"]

    matrix = report["cross_modal_analysis"]["matrix"]
    for modality in ["image", "video", "audio"]:
        assert "not a negative result" in matrix[modality]

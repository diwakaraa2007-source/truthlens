"""Shared observation records. Measurements stay separate from conclusions."""

from __future__ import annotations

CONFIDENCE_SEMANTICS = (
    "This value is not a probability. No interval estimate is produced. "
    "The comparison line is a predeclared prototype rule."
)


def observation(
    *,
    name: str,
    modality: str,
    source_sha256: str,
    location: str,
    method: str,
    result: str,
    measured_value,
    score_type: str,
    threshold: str,
    threshold_exceeded: bool,
    alternative_explanations: list[str],
    limitation: str,
    frame_number: int | None = None,
    timestamp_seconds: float | None = None,
    segment: str | None = None,
    detector_id: str,
) -> dict:
    return {
        "name": name,
        "modality": modality,
        "source_sha256": source_sha256,
        "location": location,
        "frame_number": frame_number,
        "timestamp_seconds": timestamp_seconds,
        "segment": segment,
        "method": method,
        "result": result,
        "measured_value": measured_value,
        "score_type": score_type,
        "threshold": threshold,
        "threshold_exceeded": bool(threshold_exceeded),
        "confidence_semantics": CONFIDENCE_SEMANTICS,
        "alternative_explanations": alternative_explanations,
        "limitation": limitation,
        "detector_id": detector_id,
        "detector_status": "UNVALIDATED PROTOTYPE",
        "severity": "review" if threshold_exceeded else "note",
        "conclusion": "Indicator for human review" if threshold_exceeded else "Threshold not exceeded",
    }

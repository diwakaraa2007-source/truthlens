"""Assemble one screening report from analyzer output."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from backend.truthlens import TOOL_NAME, TOOL_VERSION
from backend.truthlens.audio_lab import analyze_audio
from backend.truthlens.detectors import detector_registry
from backend.truthlens.fusion import fuse
from backend.truthlens.image_lab import analyze_image
from backend.truthlens.text_lab import analyze_text
from backend.truthlens.video_lab import analyze_video

WATERMARK = "SIMULATION / GENERATED FIXTURE"

_TASKS = {
    "image": "Still-image heuristic screening was not run.",
    "video": "Video frame screening was not run.",
    "audio": "PCM WAV screening was not run.",
    "text": "Lexical screening was not run.",
}


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _missing(modality: str) -> dict:
    return {
        "status": "not_provided",
        "task": _TASKS[modality],
        "note": "Not ingested. This is missing analysis, not a negative result.",
        "error": None,
        "observations": [],
        "indicators": [],
        "visualizations": {},
        "unavailable_detectors": [],
    }


def _inventory(item: dict, ingested_at: str) -> dict:
    return {
        "modality": item["modality"],
        "filename": item["filename"],
        "sha256": item["sha256"],
        "size_bytes": item["size_bytes"],
        "media_type": item["media_type"],
        "role": item["role"],
        "ingested_at": ingested_at,
        "timezone": "UTC",
        "tool_version": TOOL_VERSION,
        "byte_identity": "SHA-256 identifies these preserved bytes only. It is not a custody system and it does not show who handled the file.",
    }


def build_report(
    *,
    case_id: str,
    simulation: bool,
    analysis_origin: str,
    fixture: dict | None = None,
    image: dict | None = None,
    video: dict | None = None,
    audio: dict | None = None,
    statement: str = "",
    comparison: str = "",
) -> dict:
    ingested_at = datetime.now(timezone.utc).isoformat()
    history = [
        f"{TOOL_NAME} {TOOL_VERSION} accepted the intake at {ingested_at} (UTC).",
        "Original bytes are hashed and then screening reads decoded copies.",
        "The server does not write an evidence archive. Video decoding uses a temporary copy that is removed before the response returns.",
    ]
    inventory = []
    parts: dict[str, dict] = {}

    if image:
        digest = sha256_hex(image["data"])
        inventory.append(_inventory({
            "modality": "image",
            "filename": image["filename"],
            "sha256": digest,
            "size_bytes": len(image["data"]),
            "media_type": image["media_type"],
            "role": image["role"],
        }, ingested_at))
        history.append("Image screening decoded a copy of the preserved image bytes.")
        parts["image"] = analyze_image(image["data"], digest)
    else:
        parts["image"] = _missing("image")

    if video:
        digest = sha256_hex(video["data"])
        inventory.append(_inventory({
            "modality": "video",
            "filename": video["filename"],
            "sha256": digest,
            "size_bytes": len(video["data"]),
            "media_type": video["media_type"],
            "role": video["role"],
        }, ingested_at))
        history.append("Video screening wrote a temporary copy, decoded sample frames, and deleted the copy.")
        suffix = video.get("suffix") or ".bin"
        parts["video"] = analyze_video(video["data"], digest, suffix)
    else:
        parts["video"] = _missing("video")

    if audio:
        digest = sha256_hex(audio["data"])
        inventory.append(_inventory({
            "modality": "audio",
            "filename": audio["filename"],
            "sha256": digest,
            "size_bytes": len(audio["data"]),
            "media_type": audio["media_type"],
            "role": audio["role"],
        }, ingested_at))
        history.append("Audio screening read a PCM copy in memory.")
        parts["audio"] = analyze_audio(audio["data"], digest)
    else:
        parts["audio"] = _missing("audio")

    if statement.strip() or comparison.strip():
        payload = statement.encode("utf-8") + b"\n--\n" + comparison.encode("utf-8")
        digest = sha256_hex(payload)
        inventory.append(_inventory({
            "modality": "text",
            "filename": "pasted-text.txt",
            "sha256": digest,
            "size_bytes": len(payload),
            "media_type": "text/plain; charset=utf-8",
            "role": "pasted_text",
        }, ingested_at))
        history.append("Text screening tokenized the pasted strings. The strings are not written to a log.")
        parts["text"] = analyze_text(statement, comparison, digest)
    else:
        parts["text"] = _missing("text")

    observations = []
    indicators = []
    for block in parts.values():
        observations.extend(block.get("observations") or [])
        indicators.extend(block.get("indicators") or [])

    identity_material = "|".join(item["sha256"] for item in inventory).encode("utf-8")
    identity_digest = sha256_hex(identity_material) if inventory else None
    generated_at = datetime.now(timezone.utc).isoformat()
    report_id = "TL-RPT-" + sha256_hex(f"{case_id}|{generated_at}|{identity_digest}".encode("utf-8"))[:16]

    if simulation:
        summary = (
            f"{WATERMARK}. Measurements in this response were computed from generated fixture bytes "
            "by the same analyzers used for an upload. This is not a recording of a person or event. "
            "Conclusion: Indicators for human review."
        )
        banner = WATERMARK
    else:
        summary = (
            "Conclusion: Indicators for human review. Measurements in this response come from the bytes "
            "submitted in this request. No overall real/fake probability is reported. "
            "A modality that was not ingested was not analyzed."
        )
        banner = None

    return {
        "report_id": report_id,
        "case_id": case_id,
        "generated_at": generated_at,
        "timezone": "UTC",
        "tool_name": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "analysis_origin": analysis_origin,
        "simulation": simulation,
        "watermark": banner,
        "export_banner": banner or "LOCAL SCREENING REPORT. Indicators for human review. Not a legal finding.",
        "conclusion": "Indicators for human review",
        "executive_summary": summary,
        "fixture": None if not simulation else {
            "documented_label": None if not fixture else fixture.get("documented_label"),
            "construction": None if not fixture else fixture.get("construction"),
            "note": "The construction note describes how the fixture was made. It is not a detector output.",
        },
        "evidence_inventory": inventory,
        "byte_identity_digest": identity_digest,
        "byte_identity_meaning": "SHA-256 of the listed file hashes joined with '|'. It identifies this response's inputs. It is not a chain of custody and it is not a compliance claim.",
        "processing_history": history,
        "modality_analyses": parts,
        "observations": observations,
        "all_indicators": indicators,
        "cross_modal_analysis": fuse(parts),
        "detectors": detector_registry(),
        "alternative_hypotheses": [
            "Compression, resaving, a camera cut, a quiet room, or ordinary wording can produce the same measurements.",
            "A threshold that was not exceeded does not show that the bytes are unedited.",
        ],
        "limitations_and_caveats": [
            "Every heuristic in this build is an UNVALIDATED PROTOTYPE for real-world media.",
            "Learned detectors listed as UNAVAILABLE did not run and did not contribute a score.",
            "No overall real/fake probability is computed.",
            "The response is held in server memory only for this request and is not stored as a case file.",
        ],
        "recommended_human_checks": [
            "Compare the file with a source that you trust, such as the original camera or the sender you can verify out of band.",
            "Read each measurement with its threshold, alternate explanations, and limitation before deciding what to do.",
            "Treat missing or unsupported modalities as work that did not run.",
        ],
        "privacy": {
            "processing": "local",
            "persistence": "none",
            "third_party_model_services": "none",
            "logs_file_contents": False,
        },
    }

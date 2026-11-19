"""Say when screening signals co-occur. Do not infer intent or identity."""

from __future__ import annotations


def _exceeded(block: dict | None) -> bool:
    if not block or block.get("status") != "analyzed":
        return False
    return any(item.get("threshold_exceeded") for item in block.get("observations", []))


def fuse(parts: dict[str, dict]) -> dict:
    analyzed = [name for name, block in parts.items() if block and block.get("status") == "analyzed"]
    missing = [name for name, block in parts.items() if not block or block.get("status") != "analyzed"]
    exceeded = [name for name in analyzed if _exceeded(parts[name])]
    quiet = [name for name in analyzed if name not in exceeded]
    cooccurrence = []
    conflict = []
    if len(exceeded) >= 2:
        cooccurrence.append({
            "modalities": exceeded,
            "finding": (
                "Predeclared heuristic rules were exceeded in "
                + " and ".join(exceeded)
                + " during this intake. Co-occurrence does not confirm intent, identity, or criminal activity."
            ),
        })
    text = parts.get("text") or {}
    urgency = any(
        item.get("name") == "Lexical urgency list" for item in text.get("observations", [])
    )
    if urgency and "audio" in exceeded:
        cooccurrence.append({
            "modalities": ["text", "audio"],
            "finding": (
                "A listed urgency token and an audio spectrum rule co-occur in this intake. "
                "The text does not show that the audio was cloned, and the audio measurement does not show that a fraud was committed."
            ),
        })
    if exceeded and quiet:
        conflict.append({
            "modalities": exceeded + quiet,
            "finding": (
                "A heuristic rule was exceeded in "
                + " and ".join(exceeded)
                + " and was not exceeded in "
                + " and ".join(quiet)
                + ". These are separate measurements. One does not overturn the other."
            ),
        })
    matrix = {}
    for name, block in parts.items():
        if not block or block.get("status") == "not_provided":
            matrix[name] = "not analyzed — missing input, not a negative result"
        elif block.get("status") == "unsupported":
            matrix[name] = "unsupported in this runtime — not a negative result"
        elif block.get("status") == "analysis_failed":
            matrix[name] = "analysis failed — not a negative result"
        elif _exceeded(block):
            matrix[name] = "heuristic rule exceeded — indicator only"
        else:
            matrix[name] = "analyzed; no predeclared rule exceeded — not an authenticity result"
    return {
        "status": "cooccurrence_only",
        "note": "Cross-modal notes describe co-occurrence or conflict. They do not assign intent, identity, or criminal activity.",
        "analyzed_modalities": analyzed,
        "missing_or_not_run": missing,
        "audio_visual_sync_status": "not_analyzed",
        "audio_visual_sync_reason": "No lip-sync or audio-visual correspondence model is installed.",
        "semantic_media_status": "not_analyzed",
        "semantic_media_reason": "No semantic verifier is installed. Text overlap, when present, is lexical and lives in the text lab.",
        "cooccurrence": cooccurrence,
        "conflict": conflict,
        "matrix": matrix,
    }

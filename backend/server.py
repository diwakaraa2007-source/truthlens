"""Local HTTP service. Serves the existing pages and the screening API.

This process does not deploy to Netlify and does not call an external model API.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.truthlens import TOOL_VERSION
from backend.truthlens.detectors import detector_registry
from backend.truthlens.fixtures import fixture_by_id, preset_public_records, write_fixtures
from backend.truthlens.media_sniff import (
    MAX_TOTAL_BYTES,
    RejectedUpload,
    extension_of,
    sanitize_filename,
    validate_audio,
    validate_image,
    validate_text,
    validate_video,
)
from backend.truthlens.report import build_report
from backend.truthlens.video_lab import _decoder_status

ROOT = Path(__file__).resolve().parents[1]
(ROOT / "fixtures").mkdir(parents=True, exist_ok=True)
app = FastAPI(title="TruthLens local screening", version=TOOL_VERSION)

PRIVACY = {
    "where_processing_runs": "On this local server. The browser sends the intake to this process only.",
    "memory": "File bytes and pasted text are held in memory for the request.",
    "temporary_storage": "Video screening writes one temporary copy and deletes it before the response is returned, including when decoding fails.",
    "persistence": "Uploads, pasted text, and reports are not written to an evidence store.",
    "logs": "The service does not log file contents, pasted text, transcripts, or full personal data.",
    "third_party_model_services": "None. Learned weights are not downloaded.",
    "retention": "Request data is released when the response is finished.",
    "deletion": "Temporary video files are removed on success and on decode errors.",
}


@app.exception_handler(RejectedUpload)
async def rejected_upload(_request, exc: RejectedUpload):
    return JSONResponse(status_code=400, content={"detail": exc.detail, "code": exc.code})


@app.get("/api/health")
def health():
    return {
        "status": "local",
        "tool_version": TOOL_VERSION,
        "learned_detectors": "unavailable",
        "video_decoders": _decoder_status(),
        "third_party_model_services": "none",
    }


@app.get("/api/privacy")
def privacy():
    return PRIVACY


@app.get("/api/detectors")
def detectors():
    return detector_registry()


@app.get("/api/cases/preset")
def presets():
    write_fixtures()
    return preset_public_records()


@app.post("/api/cases/preset/{case_id}/run")
def run_preset(case_id: str):
    spec = fixture_by_id(case_id)
    if spec is None:
        return JSONResponse(status_code=404, content={"detail": "Unknown fixture id.", "code": "unknown_fixture"})
    directory = write_fixtures()
    data = (directory / spec["filename"]).read_bytes()
    payload = {
        "case_id": case_id,
        "simulation": True,
        "analysis_origin": "generated_fixture",
        "fixture": spec,
    }
    slot = spec["modalities_included"][0]
    file_payload = {
        "data": data,
        "filename": spec["filename"],
        "media_type": _mime_for(spec["filename"], data),
        "role": "generated_fixture",
        "suffix": extension_of(spec["filename"]),
    }
    payload[slot] = file_payload
    return build_report(**payload)


def _mime_for(filename: str, data: bytes) -> str:
    ext = extension_of(filename)
    if ext in {".jpg", ".jpeg", ".png", ".webp"}:
        return validate_image(data, filename)
    if ext in {".gif", ".avi", ".mp4", ".webm", ".mov"}:
        return validate_video(data, filename)
    if ext == ".wav":
        return validate_audio(data, filename)
    raise RejectedUpload("Fixture signature was not recognized.", "fixture_invalid")


@app.post("/api/analyze/multimodal")
async def analyze(
    image_file: UploadFile | None = File(default=None),
    video_file: UploadFile | None = File(default=None),
    audio_file: UploadFile | None = File(default=None),
    text_content: str = Form(default=""),
    comparison_text: str = Form(default=""),
    case_id: str = Form(default=""),
):
    statement = validate_text(text_content, "Statement")
    comparison = validate_text(comparison_text, "Comparison text")
    files = {}
    total = 0
    for slot, upload, checker in (
        ("image", image_file, validate_image),
        ("video", video_file, validate_video),
        ("audio", audio_file, validate_audio),
    ):
        if upload is None or not upload.filename:
            continue
        data = await upload.read()
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise RejectedUpload(
                f"Combined uploads exceed {MAX_TOTAL_BYTES} bytes.",
                "total_too_large",
            )
        filename = sanitize_filename(upload.filename)
        media_type = checker(data, filename)
        files[slot] = {
            "data": data,
            "filename": filename,
            "media_type": media_type,
            "role": "uploaded_bytes",
            "suffix": extension_of(filename) or _suffix_from_mime(media_type),
        }
    if not files and not statement.strip() and not comparison.strip():
        raise RejectedUpload(
            "Submit an image, video, WAV, or some text.",
            "empty_intake",
        )
    safe_case = sanitize_filename(case_id) if case_id.strip() else "TL-INTAKE"
    return build_report(
        case_id=safe_case,
        simulation=False,
        analysis_origin="custom_upload",
        statement=statement,
        comparison=comparison,
        **files,
    )


def _suffix_from_mime(media_type: str) -> str:
    return {
        "image/gif": ".gif",
        "image/webp": ".webp",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "video/avi": ".avi",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "audio/wav": ".wav",
    }.get(media_type, ".bin")


@app.get("/")
def index():
    return FileResponse(ROOT / "index.html")


app.mount("/css", StaticFiles(directory=ROOT / "css"), name="css")
app.mount("/js", StaticFiles(directory=ROOT / "js"), name="js")
app.mount("/fixtures", StaticFiles(directory=ROOT / "fixtures"), name="fixtures")

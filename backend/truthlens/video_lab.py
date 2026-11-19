"""Sample decoded video frames. This is not a temporal deepfake detector."""

from __future__ import annotations

import io
import shutil
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from backend.truthlens.image_lab import _png_data_url
from backend.truthlens.observations import observation

FRAME_RATIO_THRESHOLD = 3.0
FRAME_ABS_THRESHOLD = 5.0
MAX_SAMPLED_FRAMES = 24


def _decoder_status() -> dict:
    status = {"pillow_animation": True, "opencv": False, "imageio": False}
    try:
        import cv2  # noqa: F401

        status["opencv"] = True
    except ImportError:
        status["opencv"] = False
    try:
        import imageio.v3  # noqa: F401

        status["imageio"] = True
    except ImportError:
        status["imageio"] = False
    return status


def _sample_indices(count: int) -> list[int]:
    if count <= MAX_SAMPLED_FRAMES:
        return list(range(count))
    return sorted(set(np.linspace(0, count - 1, MAX_SAMPLED_FRAMES, dtype=int).tolist()))


def _pillow_frames(path: Path) -> tuple[list[np.ndarray], list[float], float | None, str]:
    with Image.open(path) as source:
        source.load()
        count = int(getattr(source, "n_frames", 1) or 1)
        duration_ms = float(source.info.get("duration") or 100)
        indices = _sample_indices(count)
        frames = []
        stamps = []
        for index in indices:
            source.seek(index)
            frames.append(np.asarray(source.convert("RGB")))
            stamps.append(round(index * duration_ms / 1000.0, 6))
        fps = 1000.0 / duration_ms if duration_ms else None
        return frames, stamps, fps, f"Pillow animation ({count} container frames, {len(frames)} sampled)"


def _opencv_frames(path: Path) -> tuple[list[np.ndarray], list[float], float | None, str]:
    import cv2

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError("OpenCV could not open the video copy.")
    fps_value = float(capture.get(cv2.CAP_PROP_FPS) or 0) or None
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frames = []
    stamps = []
    indices = []
    if total > 1:
        wanted = set(_sample_indices(total))
        index = 0
        while True:
            pos_msec = float(capture.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
            ok, frame = capture.read()
            if not ok:
                break
            if index in wanted:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(rgb)
                if pos_msec > 0:
                    stamps.append(round(pos_msec / 1000.0, 6))
                elif fps_value:
                    stamps.append(round(index / fps_value, 6))
                else:
                    stamps.append(round(index * 0.1, 6))
                indices.append(index)
            index += 1
            if len(frames) == len(wanted):
                break
    else:
        index = 0
        while len(frames) < MAX_SAMPLED_FRAMES:
            pos_msec = float(capture.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
            ok, frame = capture.read()
            if not ok:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(rgb)
            if pos_msec > 0:
                stamps.append(round(pos_msec / 1000.0, 6))
            elif fps_value:
                stamps.append(round(index / fps_value, 6))
            else:
                stamps.append(round(index * 0.1, 6))
            indices.append(index)
            index += 1
    capture.release()
    if len(frames) < 2:
        raise RuntimeError("Fewer than two frames were decoded.")
    return frames, stamps, fps_value, f"OpenCV sampled frame indexes {indices}"


def _chart(steps: list[float]) -> str:
    width, height = 640, 180
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:, :] = (12, 22, 36)
    peak = max(steps) if steps else 1
    peak = peak or 1
    gap = width / max(1, len(steps))
    for i, value in enumerate(steps):
        bar_h = int((value / peak) * (height - 30))
        x0 = int(i * gap) + 2
        x1 = int((i + 1) * gap) - 2
        y0 = height - 12 - bar_h
        canvas[y0:height - 12, x0:max(x0 + 1, x1)] = (0, 200, 220)
    return _png_data_url(canvas)


def _resize_max(frame: np.ndarray, limit: int = 320) -> np.ndarray:
    image = Image.fromarray(frame.astype(np.uint8), mode="RGB")
    image.thumbnail((limit, limit))
    return np.asarray(image, dtype=np.float32)


def analyze_video(data: bytes, sha256: str, suffix: str) -> dict:
    task = (
        "Sampled inter-frame mean absolute difference on decoded frames. "
        "Not temporal deepfake detection, not face-swap detection, and not authenticity verification."
    )
    decoders = _decoder_status()
    directory = tempfile.mkdtemp(prefix="truthlens_video_")
    try:
        path = Path(directory) / f"copy{suffix or '.bin'}"
        path.write_bytes(data)
        mime_hint = suffix.lower()
        try:
            if mime_hint in {".gif", ".webp"} or data[:6] in {b"GIF87a", b"GIF89a"} or data[8:12] == b"WEBP":
                frames, stamps, fps, decoder_name = _pillow_frames(path)
            elif decoders["opencv"]:
                frames, stamps, fps, decoder_name = _opencv_frames(path)
            else:
                return {
                    "status": "unsupported",
                    "task": task,
                    "error": (
                        "This runtime can screen GIF and animated WEBP locally. "
                        "MP4, MOV, WEBM, and AVI need OpenCV or ffmpeg, and neither is installed. "
                        "No frame finding was produced. This is unsupported analysis, not a negative result."
                    ),
                    "observations": [],
                    "indicators": [],
                    "visualizations": {},
                    "metadata": {"decoders": decoders},
                    "unavailable_detectors": ["temporal_deepfake_detector", "face_swap_detector"],
                }
        except (UnidentifiedImageError, OSError, RuntimeError, ValueError) as exc:
            return {
                "status": "analysis_failed",
                "task": task,
                "error": f"The video copy could not be decoded ({exc.__class__.__name__}: {exc}).",
                "observations": [],
                "indicators": [],
                "visualizations": {},
                "metadata": {"decoders": decoders},
                "unavailable_detectors": ["temporal_deepfake_detector", "face_swap_detector"],
            }

        prepared = [_resize_max(frame) for frame in frames]
        # Align sizes to the first sampled frame for a numeric difference.
        base_h, base_w = prepared[0].shape[:2]
        aligned = []
        for frame in prepared:
            image = Image.fromarray(frame.astype(np.uint8), mode="RGB").resize((base_w, base_h))
            aligned.append(np.asarray(image, dtype=np.float32))
        steps = []
        for previous, current in zip(aligned, aligned[1:]):
            gray_delta = np.abs(previous.mean(axis=2) - current.mean(axis=2)).mean()
            steps.append(float(gray_delta))
        median_step = float(np.median(steps)) if steps else 0.0
        max_step = float(max(steps)) if steps else 0.0
        ratio = float(max_step / median_step) if median_step > 1e-6 else (999.0 if max_step > FRAME_ABS_THRESHOLD else 1.0)
        hit = bool(max_step > FRAME_ABS_THRESHOLD and ratio > FRAME_RATIO_THRESHOLD)
        hit_index = int(np.argmax(steps)) + 1 if steps else 0
        hit_frame_stamp = stamps[hit_index] if stamps and hit_index < len(stamps) else None
        duration = None
        if stamps and stamps[-1] is not None:
            duration = stamps[-1]
        observations = [
            observation(
                name="Sampled inter-frame mean absolute difference",
                modality="video",
                source_sha256=sha256,
                location=f"sampled frame index {hit_index}",
                frame_number=hit_index,
                timestamp_seconds=hit_frame_stamp,
                segment=f"step between sampled frames {max(0, hit_index - 1)} and {hit_index}",
                method="Grayscale mean absolute difference between consecutive sampled frames from a decoded copy.",
                result=(
                    f"Largest step {max_step:.3f}; median step {median_step:.3f}; ratio {ratio:.3f}. "
                    f"Source timestamp of the later sampled frame: {hit_frame_stamp}."
                    + (" The predeclared step rule was exceeded." if hit else " The predeclared step rule was not exceeded.")
                ),
                measured_value=round(max_step, 6),
                score_type="mean absolute grayscale difference on a 0-255 scale; not a probability",
                threshold=f"max_step > {FRAME_ABS_THRESHOLD} and max_step/median_step > {FRAME_RATIO_THRESHOLD}",
                threshold_exceeded=hit,
                alternative_explanations=[
                    "A cut, a flash, a camera pan, or a scene change can raise frame difference.",
                    "Low frame rate and GIF color quantization also change the difference.",
                ],
                limitation=(
                    "This screen looks at sampled frame differences only. "
                    "It does not track faces, optical flow, or temporal deepfake artifacts."
                ),
                detector_id="sampled_frame_mad",
            )
        ]
        step_rows = []
        for index, value in enumerate(steps, start=1):
            step_rows.append({
                "later_sampled_frame": index,
                "timestamp_seconds": stamps[index] if index < len(stamps) else None,
                "mean_absolute_difference": round(value, 6),
                "threshold_exceeded": bool(
                    hit and index == hit_index
                ),
            })
        return {
            "status": "analyzed",
            "task": task,
            "error": None,
            "metadata": {
                "decoder": decoder_name,
                "decoders": decoders,
                "fps_reported_by_container": fps,
                "duration_seconds": duration,
                "sampled_frame_count": len(frames),
                "source_timestamps_seconds": stamps,
                "optical_flow": "UNAVAILABLE",
                "temporal_deepfake_detector": "UNAVAILABLE",
            },
            "measurements": {
                "max_mean_absolute_difference": round(max_step, 6),
                "median_mean_absolute_difference": round(median_step, 6),
                "max_over_median": None if ratio >= 999 else round(ratio, 6),
            },
            "frame_steps": step_rows,
            "observations": observations,
            "indicators": [item for item in observations if item["threshold_exceeded"]],
            "visualizations": {"frame_difference_chart": _chart(steps)},
            "unavailable_detectors": ["temporal_deepfake_detector", "face_swap_detector"],
        }
    finally:
        shutil.rmtree(directory, ignore_errors=True)
        if Path(directory).exists():
            raise RuntimeError("Temporary video directory was not removed.")

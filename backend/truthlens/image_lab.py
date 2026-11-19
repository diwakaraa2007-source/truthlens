"""Still-image measurements on a decoded copy of the uploaded bytes."""

from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image, UnidentifiedImageError

from backend.truthlens.media_sniff import MAX_PIXELS
from backend.truthlens.observations import observation

ELA_RATIO_THRESHOLD = 0.40
FFT_PEAK_THRESHOLD = 25.0
QUADRANT_RATIO_THRESHOLD = 4.0

Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def _png_data_url(array: np.ndarray) -> str:
    image = Image.fromarray(array.astype(np.uint8), mode="RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _colorize(values: np.ndarray) -> np.ndarray:
    finite = np.isfinite(values)
    if not finite.any():
        return np.zeros((*values.shape, 3), dtype=np.uint8)
    lo = float(np.percentile(values[finite], 5))
    hi = float(np.percentile(values[finite], 95))
    if hi <= lo:
        hi = lo + 1.0
    scaled = np.clip((values - lo) / (hi - lo), 0, 1)
    red = (scaled * 255).astype(np.uint8)
    green = ((1.0 - np.abs(scaled - 0.5) * 2) * 180).astype(np.uint8)
    blue = ((1.0 - scaled) * 255).astype(np.uint8)
    return np.dstack([red, green, blue])


def _box_blur(channel: np.ndarray, radius: int = 2) -> np.ndarray:
    padded = np.pad(channel, radius, mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(padded, (radius * 2 + 1, radius * 2 + 1))
    return windows.mean(axis=(-1, -2))


def analyze_image(data: bytes, sha256: str) -> dict:
    task = (
        "Still-image heuristic screening (JPEG error-level contrast, Fourier peak ratio, "
        "high-pass quadrant variance). Not face-swap detection, not AI-generated-image "
        "classification, and not authenticity verification."
    )
    try:
        with Image.open(io.BytesIO(data)) as source:
            source.load()
            n_frames = int(getattr(source, "n_frames", 1) or 1)
            frame_note = None
            if n_frames > 1:
                source.seek(0)
                frame_note = (
                    f"The file has {n_frames} frames. Image screening used frame 0 only. "
                    "Other frames were not analyzed."
                )
            rgb = np.asarray(source.convert("RGB"), dtype=np.float32)
            exif_present = bool(source.getexif())
            image_format = source.format or "unknown"
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError) as exc:
        return {
            "status": "analysis_failed",
            "task": task,
            "error": f"The image bytes could not be decoded ({exc.__class__.__name__}).",
            "observations": [],
            "indicators": [],
            "visualizations": {},
            "measurements": {},
            "unavailable_detectors": ["ai_generated_image_classifier", "face_swap_detector", "prnu_camera_identification"],
        }

    height, width, _ = rgb.shape
    gray = rgb.mean(axis=2)
    block = 16
    resaved = io.BytesIO()
    Image.fromarray(rgb.astype(np.uint8), mode="RGB").save(resaved, format="JPEG", quality=90)
    with Image.open(resaved) as recompressed:
        recompressed_rgb = np.asarray(recompressed.convert("RGB"), dtype=np.float32)
    ela = np.abs(rgb - recompressed_rgb).mean(axis=2)
    block_means = []
    positions = []
    for y in range(0, height - block + 1, block):
        for x in range(0, width - block + 1, block):
            block_means.append(float(ela[y:y + block, x:x + block].mean()))
            positions.append((x, y))
    if not block_means:
        block_means = [float(ela.mean())]
        positions = [(0, 0)]
    median_block = float(np.median(block_means))
    min_index = int(np.argmin(block_means))
    min_block = float(block_means[min_index])
    ratio = float(min_block / median_block) if median_block > 1e-6 else 1.0
    min_x, min_y = positions[min_index]
    ela_hit = bool(ratio < ELA_RATIO_THRESHOLD and median_block > 1.0)

    spectrum = np.fft.fftshift(np.fft.fft2(gray - gray.mean()))
    magnitude = np.log1p(np.abs(spectrum))
    cy, cx = np.array(magnitude.shape) // 2
    radius = max(2, int(min(magnitude.shape) * 0.04))
    mask = np.ones(magnitude.shape, dtype=bool)
    mask[cy - radius:cy + radius + 1, cx - radius:cx + radius + 1] = False
    peak = float(magnitude[mask].max()) if mask.any() else 0.0
    median_mag = float(np.median(magnitude[mask])) if mask.any() else 1.0
    peak_ratio = float(peak / median_mag) if median_mag > 1e-6 else 0.0
    peak_pos = np.argwhere(magnitude == magnitude[mask].max()) if mask.any() else np.array([[0, 0]])
    fft_hit = bool(peak_ratio > FFT_PEAK_THRESHOLD)

    residual = gray - _box_blur(gray, 2)
    mid_y, mid_x = height // 2, width // 2
    quadrants = {
        "top_left": residual[:mid_y, :mid_x],
        "top_right": residual[:mid_y, mid_x:],
        "bottom_left": residual[mid_y:, :mid_x],
        "bottom_right": residual[mid_y:, mid_x:],
    }
    quadrant_var = {
        name: float(np.var(part)) for name, part in quadrants.items() if part.size
    }
    median_var = float(np.median(list(quadrant_var.values()))) if quadrant_var else 0.0
    max_name = max(quadrant_var, key=quadrant_var.get) if quadrant_var else "none"
    max_var = quadrant_var.get(max_name, 0.0)
    quadrant_ratio = float(max_var / median_var) if median_var > 1e-6 else 1.0
    quadrant_hit = bool(quadrant_ratio > QUADRANT_RATIO_THRESHOLD)

    observations = [
        observation(
            name="JPEG error-level block contrast",
            modality="image",
            source_sha256=sha256,
            location=f"lowest 16px block at x={min_x}, y={min_y}",
            method="Mean absolute difference against a JPEG quality-90 resave of the decoded RGB copy, summarized in 16px blocks.",
            result=(
                f"Lowest block mean {min_block:.3f}; median block mean {median_block:.3f}; "
                f"ratio {ratio:.3f}."
                + (" The predeclared ratio rule was exceeded." if ela_hit else " The predeclared ratio rule was not exceeded.")
            ),
            measured_value=round(ratio, 6),
            score_type="ratio of lowest block mean to median block mean on a 0-255 difference scale; not a probability",
            threshold=f"ratio < {ELA_RATIO_THRESHOLD} and median block mean > 1",
            threshold_exceeded=ela_hit,
            alternative_explanations=[
                "A flat sky, wall, graphic, or caption can have a lower resave difference than textured areas.",
                "A second save, a messaging app, or a screenshot can change error level without a splice.",
            ],
            limitation="Error-level contrast is not proof of a photo edit. This rule is an UNVALIDATED PROTOTYPE on the uploaded pixels.",
            detector_id="jpeg_ela_block_contrast",
        ),
        observation(
            name="Grayscale Fourier peak ratio",
            modality="image",
            source_sha256=sha256,
            location=f"peak bin near row {int(peak_pos[0][0])}, column {int(peak_pos[0][1])} of the shifted spectrum",
            method="Log-magnitude 2D FFT of the grayscale copy. The center disk is excluded from the peak search.",
            result=(
                f"Peak-to-median ratio {peak_ratio:.3f}."
                + (" The predeclared peak rule was exceeded." if fft_hit else " The predeclared peak rule was not exceeded.")
            ),
            measured_value=round(peak_ratio, 6),
            score_type="ratio of off-center log-magnitude peak to median log-magnitude; not a probability",
            threshold=f"peak_ratio > {FFT_PEAK_THRESHOLD}",
            threshold_exceeded=fft_hit,
            alternative_explanations=[
                "Repeated textures, screens, fabric, and raster text can create strong Fourier peaks.",
                "Resizing and JPEG blocking can also raise periodic energy.",
            ],
            limitation="A Fourier peak is not proof of synthesis. No generator classifier is running.",
            detector_id="fft_peak_ratio",
        ),
        observation(
            name="High-pass quadrant variance",
            modality="image",
            source_sha256=sha256,
            location=f"highest quadrant: {max_name}",
            method="Variance of a 5x5 box-blur residual, compared across four quadrants. This is not a PRNU correlation.",
            result=(
                f"Highest quadrant variance {max_var:.3f}; median quadrant variance {median_var:.3f}; "
                f"ratio {quadrant_ratio:.3f}."
                + (" The predeclared variance rule was exceeded." if quadrant_hit else " The predeclared variance rule was not exceeded.")
            ),
            measured_value=round(quadrant_ratio, 6),
            score_type="ratio of highest quadrant residual variance to the median quadrant; not a probability",
            threshold=f"ratio > {QUADRANT_RATIO_THRESHOLD}",
            threshold_exceeded=quadrant_hit,
            alternative_explanations=[
                "A mixed scene, a border, or a blurry region can make residual variance uneven.",
                "Noise reduction and compression both change this residual.",
            ],
            limitation="PRNU camera identification is unavailable. Uneven residual variance is not sensor proof.",
            detector_id="highpass_quadrant_variance",
        ),
        observation(
            name="EXIF presence",
            modality="image",
            source_sha256=sha256,
            location="container metadata",
            method="Pillow EXIF collection on the decoded file.",
            result="EXIF tags were present." if exif_present else "No EXIF tags were read from this file.",
            measured_value=1 if exif_present else 0,
            score_type="presence flag, 1 if any EXIF tag was read, otherwise 0; not a probability",
            threshold="No threshold. Absence is recorded and is not treated as a manipulation indicator.",
            threshold_exceeded=False,
            alternative_explanations=[
                "PNG, GIF, screenshots, and many exports omit EXIF even when the pixels were not edited.",
                "A privacy tool may strip metadata from an otherwise unedited photo.",
            ],
            limitation="Missing EXIF is not evidence of manipulation. Present EXIF is not proof the pixels are unedited.",
            detector_id="jpeg_ela_block_contrast",
        ),
    ]

    return {
        "status": "analyzed",
        "task": task,
        "error": None,
        "frame_note": frame_note,
        "metadata": {
            "format": image_format,
            "width": width,
            "height": height,
            "frames_in_container": n_frames,
            "frames_analyzed": 1,
            "exif_present": exif_present,
            "face_detector": "UNAVAILABLE",
        },
        "measurements": {
            "ela_min_block_mean": round(min_block, 6),
            "ela_median_block_mean": round(median_block, 6),
            "ela_min_over_median": round(ratio, 6),
            "fft_peak_ratio": round(peak_ratio, 6),
            "highpass_quadrant_ratio": round(quadrant_ratio, 6),
        },
        "observations": observations,
        "indicators": [item for item in observations if item["threshold_exceeded"]],
        "visualizations": {
            "ela_heatmap": _png_data_url(_colorize(ela)),
            "noise_heatmap": _png_data_url(_colorize(np.abs(residual))),
            "fft_spectrum": _png_data_url(_colorize(magnitude)),
        },
        "unavailable_detectors": [
            "ai_generated_image_classifier",
            "face_swap_detector",
            "photo_edit_detector",
            "prnu_camera_identification",
        ],
    }

"""Reproducible checks on synthetic media.

The dev and eval seeds are disjoint. The rules are predeclared in the lab
modules. These counts are not an accuracy claim for real photographs, video,
or speech.
"""

from __future__ import annotations

import io
import json
import wave
from pathlib import Path

import numpy as np
from PIL import Image

from backend.truthlens.audio_lab import analyze_audio
from backend.truthlens.image_lab import analyze_image
from backend.truthlens.report import sha256_hex
from backend.truthlens.video_lab import analyze_video

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "validation" / "LATEST_RESULTS.json"


def _confusion(labels: list[bool], flags: list[bool]) -> dict:
    pairs = list(zip(labels, flags))
    tp = sum(label and flag for label, flag in pairs)
    tn = sum((not label) and (not flag) for label, flag in pairs)
    fp = sum((not label) and flag for label, flag in pairs)
    fn = sum(label and (not flag) for label, flag in pairs)
    def ratio(numerator: int, denominator: int):
        if denominator == 0:
            return None
        return round(numerator / denominator, 4)

    return {
        "sample_count": len(labels),
        "known_manipulated": sum(labels),
        "known_real": len(labels) - sum(labels),
        "confusion_matrix": {
            "true_positive": tp,
            "false_positive": fp,
            "true_negative": tn,
            "false_negative": fn,
        },
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "false_positive_rate": ratio(fp, fp + tn),
    }


def _jpeg(seed: int, manipulated: bool) -> bytes:
    generator = np.random.default_rng(seed)
    pixels = generator.integers(0, 256, size=(96, 96, 3), dtype=np.uint8)
    image = Image.fromarray(pixels, mode="RGB")
    first = io.BytesIO()
    image.save(first, format="JPEG", quality=70)
    if not manipulated:
        return first.getvalue()
    with Image.open(io.BytesIO(first.getvalue())) as reopened:
        edited = reopened.convert("RGB")
    for y in range(24, 72):
        for x in range(24, 72):
            edited.putpixel((x, y), (240, 240, 240))
    second = io.BytesIO()
    edited.save(second, format="JPEG", quality=90)
    return second.getvalue()


def _gif(seed: int, manipulated: bool) -> bytes:
    frames = []
    base = 30 + (seed % 17)
    for index in range(8):
        level = min(255, base + index * 6)
        frames.append(Image.new("RGB", (48, 48), (level, level, level)))
    if manipulated:
        frames[4] = Image.new("RGB", (48, 48), (255, 255, 255))
    buffer = io.BytesIO()
    frames[0].save(buffer, format="GIF", save_all=True, append_images=frames[1:], duration=100, loop=0, disposal=2)
    return buffer.getvalue()


def _avi(seed: int, manipulated: bool) -> bytes:
    import cv2
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".avi", delete=False) as f:
        temp_name = f.name
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    out = cv2.VideoWriter(temp_name, fourcc, 10.0, (48, 48))
    base = 30 + (seed % 17)
    for index in range(8):
        level = 255 if (manipulated and index == 4) else min(255, base + index * 6)
        frame = np.full((48, 48, 3), level, dtype=np.uint8)
        out.write(frame)
    out.release()
    data = Path(temp_name).read_bytes()
    Path(temp_name).unlink(missing_ok=True)
    return data


def _wav(seed: int, manipulated: bool) -> bytes:
    generator = np.random.default_rng(seed)
    samples = generator.uniform(-0.8, 0.8, size=8000)
    if manipulated:
        spectrum = np.fft.rfft(samples)
        freqs = np.fft.rfftfreq(samples.size, d=1.0 / 16000)
        spectrum[freqs >= 3000] = 0
        samples = np.fft.irfft(spectrum, n=samples.size).real
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(pcm.tobytes())
    return buffer.getvalue()


def _image_flag(data: bytes) -> bool:
    result = analyze_image(data, sha256_hex(data))
    return any(
        item["detector_id"] == "jpeg_ela_block_contrast" and item["threshold_exceeded"]
        for item in result["observations"]
    )


def _video_flag(data: bytes) -> bool:
    result = analyze_video(data, sha256_hex(data), ".gif")
    return any(item["threshold_exceeded"] for item in result["observations"])


def _video_avi_flag(data: bytes) -> bool:
    result = analyze_video(data, sha256_hex(data), ".avi")
    return any(item["threshold_exceeded"] for item in result["observations"])


def _audio_flag(data: bytes) -> bool:
    result = analyze_audio(data, sha256_hex(data))
    return any(
        item["detector_id"] == "wav_spectral_rolloff" and item["threshold_exceeded"]
        for item in result["observations"]
    )


def _split(seeds: range, builder, flagger) -> dict:
    labels = []
    flags = []
    for seed in seeds:
        real_bytes = builder(seed, False)
        fake_bytes = builder(seed + 50000, True)
        labels.extend([False, True])
        flags.extend([flagger(real_bytes), flagger(fake_bytes)])
    return _confusion(labels, flags)


def run_validation() -> dict:
    dev_seeds = range(0, 20)
    eval_seeds = range(1000, 1020)
    report = {
        "detector_label": "UNVALIDATED PROTOTYPE",
        "data_source": "Synthetic bytes generated in backend/truthlens/validation_run.py. No photographs, recordings of people, or external datasets.",
        "threshold_policy": "Rules are predeclared in image_lab.py, video_lab.py, and audio_lab.py. They were not fit on the eval seeds.",
        "disjoint": "Dev seeds 0-19 and eval seeds 1000-1019 do not overlap. Manipulated copies use seed+50000 and a documented edit.",
        "claim_boundary": "These figures describe this synthetic check only. They are not general accuracy and they are not accuracy on the training data of any model. No learned model was evaluated.",
        "checks": {
            "jpeg_ela_block_contrast": {
                "task": "Separate a single JPEG save of noise from the same construction with a flat rectangle pasted before a second JPEG save.",
                "manipulation_type": "flat 48x48 rectangle pasted onto noise, then JPEG quality 90",
                "known_real": "noise image saved once as JPEG quality 70",
                "threshold": "min_block_mean / median_block_mean < 0.40 and median block mean > 1",
                "dev": _split(dev_seeds, _jpeg, _image_flag),
                "eval": _split(eval_seeds, _jpeg, _image_flag),
            },
            "sampled_frame_mad": {
                "task": "Separate a slow brightness ramp GIF from a ramp with one solid white frame. Not temporal deepfake detection.",
                "manipulation_type": "frame 4 replaced with solid white",
                "known_real": "eight-frame brightness ramp GIF",
                "threshold": "max_step > 5 and max_step/median_step > 3",
                "dev": _split(dev_seeds, _gif, _video_flag),
                "eval": _split(eval_seeds, _gif, _video_flag),
            },
            "sampled_frame_mad_avi": {
                "task": "Separate a slow brightness ramp AVI video from a ramp with one solid white frame via OpenCV decoder.",
                "manipulation_type": "frame 4 replaced with solid white in 10 fps MJPG AVI",
                "known_real": "eight-frame brightness ramp AVI video",
                "threshold": "max_step > 5 and max_step/median_step > 3",
                "dev": _split(dev_seeds, _avi, _video_avi_flag),
                "eval": _split(eval_seeds, _avi, _video_avi_flag),
            },
            "wav_spectral_rolloff": {
                "task": "Separate broadband PCM noise from a 3 kHz FFT low-pass of noise. Not audio-spoof classification.",
                "manipulation_type": "FFT bins at and above 3 kHz set to zero",
                "known_real": "uniform noise, 16 kHz, 16-bit PCM, 0.5 s",
                "threshold": "sample_rate >= 16000 and high_band_energy_ratio < 0.05",
                "dev": _split(dev_seeds, _wav, _audio_flag),
                "eval": _split(eval_seeds, _wav, _audio_flag),
            },
        },
        "not_validated": [
            "ai_generated_image_classifier",
            "face_swap_detector",
            "photo_edit_detector",
            "prnu_camera_identification",
            "audio_spoof_classifier",
            "temporal_deepfake_detector",
            "semantic_entailment",
            "lexical_token_overlap",
        ],
        "lexical_note": "Token overlap is a lexical screen. It has no real/fake label, so this file does not report precision or recall for text.",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = run_validation()
    print(OUTPUT)
    for name, check in result["checks"].items():
        eval_matrix = check["eval"]["confusion_matrix"]
        print(name, "eval", eval_matrix, "precision", check["eval"]["precision"], "recall", check["eval"]["recall"])

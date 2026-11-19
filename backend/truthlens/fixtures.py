"""Deterministic generated fixtures. They are not recordings of real events."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "fixtures" / "generated"

CATALOG = [
    {
        "case_id": "GFX-JPEG-CONSISTENT",
        "title": "Generated consistent JPEG",
        "filename": "generated-consistent-noise.jpg",
        "modalities_included": ["image"],
        "documented_label": "synthetic_consistent_jpeg",
        "construction": "96x96 seeded noise saved once as JPEG quality 75. No paste step.",
    },
    {
        "case_id": "GFX-JPEG-PASTE",
        "title": "Generated JPEG with a flat pasted rectangle",
        "filename": "generated-flat-paste.jpg",
        "modalities_included": ["image"],
        "documented_label": "synthetic_flat_rectangle_pasted_then_resaved",
        "construction": "96x96 seeded noise, JPEG quality 70, then a flat rectangle pasted and resaved at quality 90.",
    },
    {
        "case_id": "GFX-GIF-SMOOTH",
        "title": "Generated GIF with small frame steps",
        "filename": "generated-smooth.gif",
        "modalities_included": ["video"],
        "documented_label": "synthetic_slow_brightness_change",
        "construction": "Eight 64x64 frames, brightness stepping by 8 levels, 100 ms per frame.",
    },
    {
        "case_id": "GFX-GIF-SPIKE",
        "title": "Generated GIF with one replaced frame",
        "filename": "generated-frame-spike.gif",
        "modalities_included": ["video"],
        "documented_label": "synthetic_one_frame_replaced",
        "construction": "Same brightness ramp as the smooth GIF, except frame 4 is solid white.",
    },
    {
        "case_id": "GFX-WAV-BROADBAND",
        "title": "Generated broadband PCM tone-plus-noise",
        "filename": "generated-broadband.wav",
        "modalities_included": ["audio"],
        "documented_label": "synthetic_broadband_wav",
        "construction": "One second of seeded noise at 16 kHz, 16-bit mono PCM.",
    },
    {
        "case_id": "GFX-WAV-LOWPASS",
        "title": "Generated low-pass PCM noise",
        "filename": "generated-lowpass.wav",
        "modalities_included": ["audio"],
        "documented_label": "synthetic_lowpass_wav",
        "construction": "One second of seeded noise at 16 kHz with FFT bins at and above 3 kHz set to zero, then written as PCM WAV.",
    },
    {
        "case_id": "GFX-AVI-SMOOTH",
        "title": "Generated AVI video with smooth brightness steps",
        "filename": "generated-smooth.avi",
        "modalities_included": ["video"],
        "documented_label": "synthetic_avi_slow_brightness_change",
        "construction": "Eight 64x64 frames, brightness stepping by 8 levels, 10 fps MJPG AVI video.",
    },
    {
        "case_id": "GFX-AVI-SPIKE",
        "title": "Generated AVI video with one replaced frame",
        "filename": "generated-frame-spike.avi",
        "modalities_included": ["video"],
        "documented_label": "synthetic_avi_one_frame_replaced",
        "construction": "Same brightness ramp as the smooth AVI video, except frame 4 is solid white, 10 fps MJPG AVI.",
    },
]


def _noise_image(seed: int, size: int = 96) -> Image.Image:
    generator = np.random.default_rng(seed)
    pixels = generator.integers(0, 256, size=(size, size, 3), dtype=np.uint8)
    return Image.fromarray(pixels, mode="RGB")


def _write_wav(path: Path, samples: np.ndarray, sample_rate: int = 16000) -> None:
    pcm = np.clip(samples, -1, 1)
    pcm = (pcm * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


def _lowpass(samples: np.ndarray, sample_rate: int, cutoff_hz: float) -> np.ndarray:
    spectrum = np.fft.rfft(samples)
    freqs = np.fft.rfftfreq(samples.size, d=1.0 / sample_rate)
    spectrum[freqs >= cutoff_hz] = 0
    return np.fft.irfft(spectrum, n=samples.size).real


def write_fixtures(directory: Path | None = None) -> Path:
    target = directory or FIXTURE_DIR
    target.mkdir(parents=True, exist_ok=True)

    consistent = _noise_image(90001)
    consistent.save(target / "generated-consistent-noise.jpg", format="JPEG", quality=75)

    pasted = _noise_image(90001)
    buffer_path = target / "_intermediate-noise.jpg"
    pasted.save(buffer_path, format="JPEG", quality=70)
    with Image.open(buffer_path) as reopened:
        edited = reopened.convert("RGB")
    buffer_path.unlink(missing_ok=True)
    for y in range(24, 72):
        for x in range(24, 72):
            edited.putpixel((x, y), (240, 240, 240))
    edited.save(target / "generated-flat-paste.jpg", format="JPEG", quality=90)

    smooth = []
    for index in range(8):
        level = 40 + index * 8
        smooth.append(Image.new("RGB", (64, 64), (level, level, level)))
    smooth[0].save(
        target / "generated-smooth.gif",
        save_all=True,
        append_images=smooth[1:],
        duration=100,
        loop=0,
        disposal=2,
    )
    spiked = list(smooth)
    spiked[4] = Image.new("RGB", (64, 64), (255, 255, 255))
    spiked[0].save(
        target / "generated-frame-spike.gif",
        save_all=True,
        append_images=spiked[1:],
        duration=100,
        loop=0,
        disposal=2,
    )

    generator = np.random.default_rng(21)
    noise = generator.uniform(-0.8, 0.8, size=16000)
    _write_wav(target / "generated-broadband.wav", noise)
    _write_wav(target / "generated-lowpass.wav", _lowpass(noise, 16000, 3000))

    try:
        import cv2
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        out_smooth = cv2.VideoWriter(str(target / "generated-smooth.avi"), fourcc, 10.0, (64, 64))
        for index in range(8):
            level = 40 + index * 8
            frame = np.full((64, 64, 3), level, dtype=np.uint8)
            out_smooth.write(frame)
        out_smooth.release()

        out_spiked = cv2.VideoWriter(str(target / "generated-frame-spike.avi"), fourcc, 10.0, (64, 64))
        for index in range(8):
            level = 255 if index == 4 else (40 + index * 8)
            frame = np.full((64, 64, 3), level, dtype=np.uint8)
            out_spiked.write(frame)
        out_spiked.release()
    except Exception:
        pass

    return target


def preset_public_records() -> list[dict]:
    return [
        {
            "case_id": item["case_id"],
            "title": item["title"],
            "description": (
                "SIMULATION / GENERATED FIXTURE. "
                + item["construction"]
                + " Launching it runs the same local analyzers used for an upload. "
                "It is not a case file and not a recording of a person or event."
            ),
            "modalities_included": item["modalities_included"],
            "watermark": "SIMULATION / GENERATED FIXTURE",
            "documented_label": item["documented_label"],
            "analysis_origin": "generated_fixture",
            "expected_findings": (
                "No measurement is stored on this card. Measurements appear only after the fixture bytes are analyzed."
            ),
        }
        for item in CATALOG
    ]


def fixture_by_id(case_id: str) -> dict | None:
    for item in CATALOG:
        if item["case_id"] == case_id:
            return item
    return None


if __name__ == "__main__":
    print(write_fixtures())

"""Registry of what this build can and cannot run.

No weights are downloaded. Learned detectors stay unavailable.
"""

from __future__ import annotations

NO_WEIGHTS = (
    "No weights are bundled. This build does not download weights at runtime."
)

LEARNED_FIELDS = (
    "model_name",
    "model_revision",
    "source",
    "license",
    "expected_input",
    "training_domain",
    "preprocessing",
    "threshold",
    "raw_score",
    "known_limitations",
)


def learned_unavailable(detector_id: str, task: str, inputs: str) -> dict:
    return {
        "id": detector_id,
        "kind": "learned",
        "status": "UNAVAILABLE",
        "task": task,
        "supported_inputs": inputs,
        "model_name": None,
        "model_revision": None,
        "source": None,
        "license": None,
        "expected_input": None,
        "training_domain": None,
        "preprocessing": None,
        "threshold": None,
        "raw_score": None,
        "known_limitations": NO_WEIGHTS,
        "blocker": NO_WEIGHTS,
        "commercial_use": "Not applicable. Weights are not included.",
    }


def heuristic(detector_id: str, task: str, inputs: str, method: str, threshold: str) -> dict:
    return {
        "id": detector_id,
        "kind": "heuristic",
        "status": "UNVALIDATED PROTOTYPE",
        "task": task,
        "supported_inputs": inputs,
        "model_name": None,
        "model_revision": None,
        "source": "Local signal measurement in this repository. Not a published model card.",
        "license": "Project code only. No model license because no weights are used.",
        "expected_input": inputs,
        "training_domain": "None. The rule was not trained.",
        "preprocessing": method,
        "threshold": threshold,
        "raw_score": "Returned per file when the measurement runs.",
        "known_limitations": (
            "UNVALIDATED PROTOTYPE. A threshold hit is an indicator for a person to review. "
            "It is not proof of manipulation, authorship, or intent. "
            "Synthetic checks in validation/ do not estimate accuracy on real media."
        ),
        "blocker": None,
        "commercial_use": "Heuristic code has no separate model license. It is not a certified forensic tool.",
    }


def detector_registry() -> list[dict]:
    return [
        heuristic(
            "jpeg_ela_block_contrast",
            "JPEG error-level contrast between 16px blocks after a quality-90 resave. Not photo-edit detection, not AI-image classification, and not authenticity verification.",
            "JPEG, PNG, WEBP, or GIF stills decoded to RGB. GIF and animated WEBP use the first frame only.",
            "Decode a copy to RGB, resave JPEG quality 90, mean absolute difference per 16px block.",
            "min_block_mean / median_block_mean < 0.40",
        ),
        heuristic(
            "fft_peak_ratio",
            "2D Fourier peak ratio on a grayscale copy. Not a generator detector.",
            "Same still images as the JPEG error-level screen.",
            "log-magnitude FFT, peak outside the center 8% divided by the median magnitude.",
            "peak_ratio > 25",
        ),
        heuristic(
            "highpass_quadrant_variance",
            "High-pass residual variance across quadrants. Not PRNU and not camera identification.",
            "Same still images as the JPEG error-level screen.",
            "Subtract a 5x5 box blur, then compare quadrant variance with the median quadrant.",
            "max_quadrant / median_quadrant > 4",
        ),
        heuristic(
            "sampled_frame_mad",
            "Mean absolute difference between sampled decoded frames. Not temporal deepfake detection and not face-swap detection.",
            "GIF, animated WEBP, and, when a local decoder imports, MP4, MOV, WEBM, and AVI.",
            "Decode a temporary copy, sample up to 24 frames, grayscale mean absolute difference.",
            "max_step / median_step > 3 and max_step > 5",
        ),
        heuristic(
            "wav_spectral_rolloff",
            "FFT energy rolloff and high-band energy ratio on PCM WAV. Not audio-spoof classification and not general audio authenticity.",
            "Mono or stereo PCM WAV, 16-bit.",
            "Real FFT of the decoded samples. High band is energy above 4 kHz.",
            "sample_rate >= 16000 and high_band_energy_ratio < 0.05",
        ),
        heuristic(
            "wav_energy_discontinuity",
            "Windowed RMS jump along a PCM WAV. Not proof of an edit.",
            "Mono or stereo PCM WAV, 16-bit, longer than two windows.",
            "20 ms RMS, flag a window above mean + 4 standard deviations.",
            "window_rms > mean_rms + 4 * std_rms",
        ),
        heuristic(
            "lexical_token_overlap",
            "Token overlap between two pasted texts. Lexical screening only, not a semantic verifier and not a claim-support verdict.",
            "Two plain-text fields, each up to 20000 characters.",
            "Lowercase alphanumeric tokens. Overlap size is reported with the token lists.",
            "No match threshold. One shared token is not called a match.",
        ),
        learned_unavailable(
            "ai_generated_image_classifier",
            "AI-generated-image classification. Distinct from face-swap detection, photo-edit detection, and authenticity verification.",
            "Not run.",
        ),
        learned_unavailable(
            "face_swap_detector",
            "Face-swap detection.",
            "Not run.",
        ),
        learned_unavailable(
            "photo_edit_detector",
            "Learned photo-edit detection.",
            "Not run.",
        ),
        learned_unavailable(
            "prnu_camera_identification",
            "PRNU / camera sensor identification.",
            "Not run. The high-pass map is not a PRNU correlate.",
        ),
        learned_unavailable(
            "audio_spoof_classifier",
            "Audio spoof or synthetic-speech classification. Distinct from general audio authenticity.",
            "Not run.",
        ),
        learned_unavailable(
            "temporal_deepfake_detector",
            "Temporal deepfake or lip-sync detection. Distinct from sampled frame-difference screening.",
            "Not run.",
        ),
        learned_unavailable(
            "semantic_entailment",
            "Semantic comparison of claims.",
            "Not run.",
        ),
    ]

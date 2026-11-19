"""PCM WAV measurements. This is not an audio-spoof classifier."""

from __future__ import annotations

import io
import wave

import numpy as np

from backend.truthlens.image_lab import _colorize, _png_data_url
from backend.truthlens.observations import observation

HIGH_BAND_HZ = 4000.0
HIGH_BAND_RATIO_THRESHOLD = 0.05
MIN_SAMPLE_RATE = 16000


def _read_pcm(data: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(data), "rb") as handle:
        if handle.getcomptype() != "NONE":
            raise ValueError("Only uncompressed PCM WAV can be screened.")
        if handle.getsampwidth() != 2:
            raise ValueError("Only 16-bit PCM WAV can be screened.")
        channels = handle.getnchannels()
        if channels < 1 or channels > 2:
            raise ValueError("Only mono or stereo PCM WAV can be screened.")
        sample_rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    samples = np.frombuffer(frames, dtype="<i2").astype(np.float32)
    if channels == 2:
        samples = samples.reshape(-1, 2).mean(axis=1)
    if samples.size == 0:
        raise ValueError("The WAV file has no sample frames.")
    peak = float(np.max(np.abs(samples))) or 1.0
    return samples / peak, sample_rate


def _spectrogram_image(samples: np.ndarray, sample_rate: int) -> str:
    window = max(256, min(1024, samples.size // 4 or 256))
    if samples.size < window:
        tiled = np.pad(samples, (0, window - samples.size))
    else:
        tiled = samples
    hop = window // 2
    rows = []
    for start in range(0, max(1, tiled.size - window), hop):
        chunk = tiled[start:start + window]
        if chunk.size < window:
            break
        spectrum = np.abs(np.fft.rfft(chunk * np.hanning(window)))
        rows.append(np.log1p(spectrum))
    if not rows:
        rows = [np.log1p(np.abs(np.fft.rfft(tiled[:window])))]
    matrix = np.array(rows).T
    return _png_data_url(_colorize(matrix))


def analyze_audio(data: bytes, sha256: str) -> dict:
    task = (
        "PCM WAV spectral energy and short-window level changes. "
        "Not audio-spoof classification and not general audio authenticity."
    )
    try:
        samples, sample_rate = _read_pcm(data)
    except (wave.Error, ValueError, EOFError, OSError, RuntimeError) as exc:
        return {
            "status": "analysis_failed",
            "task": task,
            "error": f"The WAV bytes could not be read ({exc}).",
            "observations": [],
            "indicators": [],
            "visualizations": {},
            "metadata": {},
            "unavailable_detectors": ["audio_spoof_classifier"],
        }

    spectrum = np.abs(np.fft.rfft(samples)) ** 2
    freqs = np.fft.rfftfreq(samples.size, d=1.0 / sample_rate)
    total = float(spectrum.sum()) or 1.0
    cumulative = np.cumsum(spectrum) / total
    rolloff_hz = float(freqs[int(np.searchsorted(cumulative, 0.99))])
    high = float(spectrum[freqs >= HIGH_BAND_HZ].sum()) if sample_rate > HIGH_BAND_HZ * 2 else 0.0
    high_ratio = high / total
    high_hit = bool(sample_rate >= MIN_SAMPLE_RATE and high_ratio < HIGH_BAND_RATIO_THRESHOLD)

    window = max(1, int(sample_rate * 0.02))
    rms_values = []
    rms_times = []
    if samples.size >= window * 2:
        for start in range(0, samples.size - window + 1, window):
            chunk = samples[start:start + window]
            rms_values.append(float(np.sqrt(np.mean(chunk ** 2))))
            rms_times.append(round(start / sample_rate, 6))
    rms = np.array(rms_values) if rms_values else np.array([0.0])
    rms_mean = float(rms.mean())
    rms_std = float(rms.std())
    cutoff = rms_mean + 4 * rms_std
    spike_indexes = [index for index, value in enumerate(rms_values) if rms_std > 1e-8 and value > cutoff]
    spike_hit = bool(spike_indexes)
    spike_at = rms_times[spike_indexes[0]] if spike_indexes else None

    # Autocorrelation pitch is reported only when a peak is distinct. It is not a clone score.
    jitter = None
    voiced = False
    if sample_rate >= 8000 and samples.size > sample_rate // 5:
        clip = samples[: sample_rate]
        corr = np.correlate(clip, clip, mode="full")[clip.size - 1:]
        low = int(sample_rate / 400)
        high_lag = int(sample_rate / 70)
        if high_lag > low + 2 and high_lag < corr.size:
            region = corr[low:high_lag]
            peak = float(region.max()) if region.size else 0.0
            if corr[0] > 0 and peak / corr[0] > 0.5:
                voiced = True
                period = low + int(np.argmax(region))
                periods = []
                hop = period
                for start in range(0, samples.size - period * 2, hop):
                    piece = samples[start:start + period * 2]
                    local = np.correlate(piece, piece, mode="full")[piece.size - 1:]
                    if local.size <= high_lag:
                        continue
                    local_peak = low + int(np.argmax(local[low:high_lag]))
                    periods.append(local_peak / sample_rate)
                if len(periods) >= 3:
                    diffs = np.abs(np.diff(periods))
                    jitter = float(np.mean(diffs) / (np.mean(periods) or 1.0))

    observations = [
        observation(
            name="High-band energy ratio",
            modality="audio",
            source_sha256=sha256,
            location="full decoded PCM buffer",
            segment=f"0.000s–{samples.size / sample_rate:.3f}s",
            method=f"Share of real-FFT energy at or above {HIGH_BAND_HZ:.0f} Hz.",
            result=(
                f"High-band energy ratio {high_ratio:.4f}; 99% energy rolloff {rolloff_hz:.1f} Hz; "
                f"sample rate {sample_rate} Hz."
                + (" The predeclared high-band rule was exceeded." if high_hit else " The predeclared high-band rule was not exceeded.")
            ),
            measured_value=round(high_ratio, 6),
            score_type="fraction of FFT energy above 4 kHz; not a probability and not a vocoder score",
            threshold=f"sample_rate >= {MIN_SAMPLE_RATE} and high_band_energy_ratio < {HIGH_BAND_RATIO_THRESHOLD}",
            threshold_exceeded=high_hit,
            alternative_explanations=[
                "Telephone audio, a low-pass export, music with little treble, or a quiet noise floor can reduce energy above 4 kHz.",
                "A microphone and a lossy edit that was later saved as WAV can also look band-limited.",
            ],
            limitation="A spectral cutoff is not a vocoder detection and is not audio-spoof classification. No speech classifier is running.",
            detector_id="wav_spectral_rolloff",
        ),
        observation(
            name="Short-window level jump",
            modality="audio",
            source_sha256=sha256,
            location="20 ms RMS windows",
            segment=None if spike_at is None else f"first window above the rule at {spike_at:.3f}s",
            timestamp_seconds=spike_at,
            method="Root-mean-square energy in successive 20 ms windows of the normalized PCM copy.",
            result=(
                f"{len(spike_indexes)} window(s) exceeded mean + 4 standard deviations. "
                f"Mean RMS {rms_mean:.4f}; standard deviation {rms_std:.4f}."
                + (" The predeclared level rule was exceeded." if spike_hit else " The predeclared level rule was not exceeded.")
            ),
            measured_value=len(spike_indexes),
            score_type="count of 20 ms windows above a deviation rule; not a probability",
            threshold="window_rms > mean_rms + 4 * std_rms, and std_rms > 0",
            threshold_exceeded=spike_hit,
            alternative_explanations=[
                "A plosive, clap, breath, or music onset can jump in level without an edit.",
                "A fade or a noise gate can also create a sharp level change.",
            ],
            limitation="A level jump is not proof of a splice. The audio-spoof classifier is unavailable.",
            detector_id="wav_energy_discontinuity",
        ),
    ]
    if voiced and jitter is not None:
        observations.append(
            observation(
                name="Autocorrelation period variation",
                modality="audio",
                source_sha256=sha256,
                location="voiced windows where an autocorrelation peak was distinct",
                method="Variation of autocorrelation lag between 70 Hz and 400 Hz. Reported only when the peak is at least half the zero-lag value.",
                result=f"Mean absolute period variation ratio {jitter:.4f}. No rule flags this measurement.",
                measured_value=round(jitter, 6),
                score_type="mean absolute period difference divided by mean period; not a clone score",
                threshold="No threshold. The value is shown as a measurement only.",
                threshold_exceeded=False,
                alternative_explanations=[
                    "Natural speech, a sustained tone, and vibrato can all change this ratio.",
                ],
                limitation="Period variation is not evidence that a voice was cloned or that speech is synthetic.",
                detector_id="wav_spectral_rolloff",
            )
        )

    return {
        "status": "analyzed",
        "task": task,
        "error": None,
        "metadata": {
            "sample_rate_hz": sample_rate,
            "duration_seconds": round(samples.size / sample_rate, 6),
            "channels_mixed_to_mono": True,
            "pitch_variation_measured": voiced and jitter is not None,
            "pitch_variation_ratio": None if jitter is None else round(jitter, 6),
            "rolloff_99_hz": round(rolloff_hz, 3),
            "high_band_energy_ratio": round(high_ratio, 6),
            "audio_spoof_classifier": "UNAVAILABLE",
        },
        "measurements": {
            "high_band_energy_ratio": round(high_ratio, 6),
            "rolloff_99_hz": round(rolloff_hz, 3),
            "rms_spike_count": len(spike_indexes),
        },
        "observations": observations,
        "indicators": [item for item in observations if item["threshold_exceeded"]],
        "visualizations": {"magnitude_spectrogram": _spectrogram_image(samples, sample_rate)},
        "unavailable_detectors": ["audio_spoof_classifier"],
    }

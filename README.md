# TruthLens — Local Multimodal Screening Prototype

> **Notice:** TruthLens is a local multimodal media screening research prototype designed for human-in-the-loop forensic triage. It operates strictly locally with explicit heuristic measurements and reproducible validation on synthetic fixtures. It does not compute uncalibrated "real/fake probabilities" or make legal or causal claims. All findings carry the conclusion: **Indicators for human review**.

---

## 1. Architectural Overview

TruthLens is structured into a lightweight, high-performance local screening stack:

- **Frontend (`index.html`, `js/`, `css/`)**:
  - Interactive cyber-HUD interface with a 7-stage forensic review pipeline:
    1. *Ingest & Cases*: Intake matrix and generated simulation fixtures.
    2. *Image Lab*: Error-Level Analysis (ELA), 2D Fourier spectrum (FFT), high-pass quadrant variance, and EXIF presence.
    3. *Video Forensics*: Inter-frame Mean Absolute Difference (MAD), frame difference timelines, and frame-specific source timestamps.
    4. *Audio & Voice*: High-band energy ratio (>= 4 kHz), 99% spectral rolloff, 20 ms RMS level jumps, and pitch period variation (jitter).
    5. *Text & Claims*: Side-by-side lexical token screening and surface urgency keyword detection.
    6. *Cross-Modal Fusion*: Signal co-occurrence and conflict matrix.
    7. *Forensic Report*: Unified audit report with SHA-256 byte identity, measurement inventory, and JSON export.
  - **3D Holographic Scanner (`js/three-scene.js`)**: Real-time HTML5 3D perspective scanner with customizable wireframe geometry, laser elevation sweep, and alert modes.
  - **Cursor-Linked 3D Ring (`js/orbit-ui.js`)**: Interactive 3D module carousel responsive to mouse coordinates.

- **Backend (`backend/server.py`, `backend/truthlens/`)**:
  - **FastAPI / Uvicorn Service**: Serves the local UI and screening API.
  - **Image Lab (`image_lab.py`)**: Pillow-based still image measurements.
  - **Video Lab (`video_lab.py`)**: Decodes video containers using OpenCV (`opencv-python-headless`) for MP4, AVI, WEBM, MOV and Pillow for GIF/WEBP; samples frames and logs source container timestamps.
  - **Audio Lab (`audio_lab.py`)**: Standard library `wave` and `numpy` FFT/RMS processing for 16-bit uncompressed PCM WAV.
  - **Text Lab (`text_lab.py`)**: Alphanumeric tokenization, Jaccard token overlap, and shared/disjoint token extraction.
  - **Cross-Modal Fusion (`fusion.py`)**: Records signal co-occurrence and conflict without causal or intent claims.
  - **Media Sniffer (`media_sniff.py`)**: Magic byte signature verification, extension validation, path sanitization, and size limits (20 MB total).
  - **Fixtures Engine (`fixtures.py`)**: Generates deterministic synthetic fixtures with documented constructions.
  - **Validation Engine (`validation_run.py`)**: Reproducible evaluation workflow on disjoint synthetic samples.

---

## 2. Windows & VS Code Setup

### Prerequisites
- **Operating System**: Windows 10/11 (or macOS / Linux).
- **Python**: Version 3.10 through 3.14 (Python 3.14 recommended).
- **Visual Studio Code** with the *Python* extension.

### Step-by-Step Installation

1. **Open PowerShell in the Project Directory**:
   ```powershell
   cd "C:\Users\Dhushyanth K S\truthframelens"
   ```

2. **Create and Activate a Virtual Environment**:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   *(If script execution is disabled, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first).*

3. **Install Dependencies**:
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Verify OpenCV & Decoders**:
   ```powershell
   python -c "import cv2, PIL, numpy; print('OpenCV:', cv2.__version__, 'Pillow:', PIL.__version__, 'NumPy:', numpy.__version__)"
   ```

---

## 3. Running TruthLens Locally

### Start the Local Server
Run the local HTTP screening service:
```powershell
python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser to:
```
http://127.0.0.1:8000/
```

### Running the Automated Test Suite
TruthLens includes a 35-test pytest verification suite:
```powershell
pytest -v
```

### Running the Reproducible Validation Workflow
To evaluate the heuristic detectors on disjoint synthetic samples:
```powershell
python -m backend.truthlens.validation_run
```
Results are saved to `validation/LATEST_RESULTS.json`.

---

## 4. Supported Formats & Capabilities

| Modality | Accepted Container Formats | Processing Engine | Screening Measurements Provided |
| :--- | :--- | :--- | :--- |
| **Image** | JPEG, PNG, WEBP, GIF (frame 0) | Pillow, NumPy, SciPy FFT | JPEG error-level contrast (16px blocks), 2D Fourier peak ratio, high-pass residual quadrant variance, EXIF presence. |
| **Video** | MP4, AVI, WEBM, MOV, GIF, WEBP | OpenCV (`opencv-python-headless`), Pillow | Container decoding, frame sampling (up to 24 frames), source timestamp retention, grayscale inter-frame MAD, difference timeline chart. |
| **Audio** | 16-bit uncompressed PCM WAV | Python `wave`, NumPy FFT | High-band energy ratio (>= 4 kHz), 99% spectral rolloff frequency, 20 ms RMS level spikes, autocorrelation period variation (jitter). |
| **Text** | Plain text (UTF-8) | Python regex, Set theory | Lowercase alphanumeric tokenization, Jaccard overlap, shared/unique token lists, lexical urgency keyword check. |

---

## 5. Detector Registry & Honest Coverage Claims

In strict adherence to scientific rigor, TruthLens distinguishes local heuristic measurements from learned model tasks and marks unavailable capabilities clearly:

### Active Heuristic Detectors (Status: `UNVALIDATED PROTOTYPE`)
1. **`jpeg_ela_block_contrast`**: Ratio of lowest 16px block mean to median block mean after JPEG quality-90 resave. *Limitation: Error-level contrast is not proof of a photo edit or synthetic generation.*
2. **`fft_peak_ratio`**: Ratio of off-center 2D log-magnitude FFT peak to median log-magnitude. *Limitation: Strong peaks also arise from natural textures, fabric, raster fonts, and screenshots.*
3. **`highpass_quadrant_variance`**: Variance of a 5x5 box-blur residual across quadrants. *Limitation: Not PRNU camera identification; uneven variance occurs in natural depth-of-field scenes.*
4. **`sampled_frame_mad`**: Grayscale mean absolute difference between sampled decoded frames. *Limitation: Screens inter-frame changes; not temporal deepfake detection, not lip-sync verification, not face-swap detection.*
5. **`wav_spectral_rolloff`**: Real-FFT energy ratio at/above 4 kHz. *Limitation: Band-limiting occurs naturally in telephone audio, low-pass microphones, or quiet rooms.*
6. **`wav_energy_discontinuity`**: 20 ms RMS windows exceeding mean + 4 std. *Limitation: Plosives, music onsets, and room noise also cause level jumps.*
7. **`lexical_token_overlap`**: Surface alphanumeric token overlap. *Limitation: Lexical screening only; does not perform semantic entailment or verify factual truth.*

### Unavailable Learned Models (Status: `UNAVAILABLE`)
The following tasks require heavy learned weights or specialized datasets and are **not bundled** (0 MB download size; no background weight downloads or third-party cloud API calls):
- `ai_generated_image_classifier`
- `face_swap_detector`
- `photo_edit_detector`
- `prnu_camera_identification`
- `audio_spoof_classifier`
- `temporal_deepfake_detector`
- `semantic_entailment`

---

## 6. Privacy & Data Flow Architecture

- **Local Execution**: All processing runs in the local Python process. No file data, embeddings, or transcripts are sent to external services or cloud APIs.
- **In-Memory Handling**: Uploaded byte buffers and pasted texts reside in process memory during the request.
- **No Evidence Persistence**: Raw uploads and generated reports are not stored in a persistent database or disk archive.
- **Temporary Video Cleanup**: Video decoding writes a single temporary working copy in the system temp directory and **immediately deletes it** in a `finally` block on both successful decoding and errors.
- **No Sensitive Logging**: Server logs do not print file contents, pasted texts, transcripts, or personal identifiable information.

---

## 7. Chain-of-Custody & Integrity Semantics

- **SHA-256 Byte Identity**: Every ingested file is hashed immediately upon receipt. SHA-256 confirms byte identity only; it is not an immutable audit chain, not a legally binding custody log, and not a NIST compliance claim.
- **Working Copies**: Preserved original bytes are kept untouched; all decoding and measurement steps operate on decoded copies in memory.
- **Byte Identity Digest**: The combined digest is computed as `SHA-256(hash_1 | hash_2 | ... | hash_n)` to uniquely identify the exact combination of inputs for that specific report.

---

## 8. Simulation Fixtures vs. Custom Uploads

TruthLens strictly separates simulation fixtures from real evidence:
- **Preset Cases**: Every preset card is visibly badged **SIMULATION / GENERATED FIXTURE**. Preset cards store zero pre-calculated findings. Clicking "Run fixture" executes the local analyzers on the deterministic fixture files.
- **Watermarking**: Reports generated from preset fixtures are watermarked with `SIMULATION / GENERATED FIXTURE` on every screen, export, and JSON printout.
- **Custom Uploads**: Custom uploads run independently, carry no simulation watermark, and label findings as `LOCAL SCREENING REPORT: Indicators for human review`.

### Available Preset Fixtures
1. `GFX-JPEG-CONSISTENT`: Consistent 96x96 synthetic noise JPEG (benign baseline).
2. `GFX-JPEG-PASTE`: 96x96 synthetic noise with pasted rectangle resaved at quality 90 (manipulated).
3. `GFX-GIF-SMOOTH`: 8-frame smooth brightness stepping GIF (benign baseline).
4. `GFX-GIF-SPIKE`: 8-frame GIF with frame 4 replaced by solid white (manipulated).
5. `GFX-WAV-BROADBAND`: 16 kHz broadband noise PCM WAV (benign baseline).
6. `GFX-WAV-LOWPASS`: 16 kHz noise with FFT cutoff above 3 kHz (manipulated).
7. `GFX-AVI-SMOOTH`: 8-frame MJPG AVI video with smooth brightness steps (benign baseline).
8. `GFX-AVI-SPIKE`: 8-frame MJPG AVI video with frame 4 spiked to white (manipulated).

---

## 9. Validation Results

Run `python -m backend.truthlens.validation_run` to generate reproducible metrics:

| Detector | Eval Sample Count (Real / Manipulated) | Confusion Matrix (TP / FP / TN / FN) | Precision | Recall | False Positive Rate |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `jpeg_ela_block_contrast` | 40 (20 / 20) | 20 / 0 / 20 / 0 | 1.000 | 1.000 | 0.000 |
| `sampled_frame_mad` (GIF) | 40 (20 / 20) | 20 / 0 / 20 / 0 | 1.000 | 1.000 | 0.000 |
| `sampled_frame_mad_avi` (AVI) | 40 (20 / 20) | 20 / 0 / 20 / 0 | 1.000 | 1.000 | 0.000 |
| `wav_spectral_rolloff` | 40 (20 / 20) | 20 / 0 / 20 / 0 | 1.000 | 1.000 | 0.000 |

*Validation Caveat: Evaluated on disjoint synthetic seeds (dev seeds 0-19, eval seeds 1000-1019). These figures describe the synthetic check only and do not estimate real-world media performance.*

---

## 10. Step-by-Step Demo Guide

1. **Launch Server**:
   ```powershell
   python -m uvicorn backend.server:app --port 8000 --reload
   ```
2. **Open Ingest & Cases Tab**:
   - Scroll to **Generated fixtures**.
   - Click *Run fixture through analyzers* on `GFX-AVI-SPIKE`.
   - The UI runs the local OpenCV analyzer, samples the 8 frames, calculates timestamps, flags frame 4, and routes to the **Forensic Report** with the watermark `SIMULATION / GENERATED FIXTURE`.
3. **Inspect Video Forensics Tab**:
   - Click Tab 3. View the frame difference chart, sampled frame steps, source timestamps, and OpenCV decoder metadata.
4. **Test Custom Video Upload**:
   - Return to Tab 1. Under *Custom Evidence Intake Matrix*, drag and drop any MP4, AVI, WEBM, or GIF file into the Video Evidence dropzone.
   - Enter a statement and comparison text.
   - Click *Run local screening*.
   - View the custom report with `LOCAL SCREENING REPORT: Indicators for human review`, verified SHA-256 hash, and no simulation watermark.
5. **Export Report**:
   - Click *Export JSON* in Tab 7 to download the machine-readable audit report matching the on-screen display.

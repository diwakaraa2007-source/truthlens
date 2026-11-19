/**
 * TruthLens page controller.
 * The page displays the report object returned by the local analyzer.
 */

window.currentReport = null;

const stagedFiles = {
  image: null,
  video: null,
  audio: null
};

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initDropzones();
  initIngestionForm();
  loadPresetCases();
  refreshEngineBadge();
});

function initTabs() {
  document.querySelectorAll(".nav-tab-btn").forEach((tab) => {
    tab.addEventListener("click", () => switchTab(tab.getAttribute("data-tab")));
  });
}

function switchTab(tabId) {
  document.querySelectorAll(".nav-tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-tab") === tabId);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${tabId}`);
  });
}

function initDropzones() {
  const dropzones = [
    { id: "drop-image", inputId: "input-image", type: "image", statusId: "status-image" },
    { id: "drop-video", inputId: "input-video", type: "video", statusId: "status-video" },
    { id: "drop-audio", inputId: "input-audio", type: "audio", statusId: "status-audio" }
  ];
  dropzones.forEach((zone) => {
    const box = document.getElementById(zone.id);
    const input = document.getElementById(zone.inputId);
    const status = document.getElementById(zone.statusId);
    if (!box || !input) return;
    box.addEventListener("click", () => input.click());
    input.addEventListener("change", () => {
      if (input.files && input.files[0]) handleFileSelect(input.files[0], zone.type, status);
    });
    box.addEventListener("dragover", (event) => {
      event.preventDefault();
      box.classList.add("dragover");
    });
    box.addEventListener("dragleave", () => box.classList.remove("dragover"));
    box.addEventListener("drop", (event) => {
      event.preventDefault();
      box.classList.remove("dragover");
      if (event.dataTransfer.files && event.dataTransfer.files[0]) {
        handleFileSelect(event.dataTransfer.files[0], zone.type, status);
      }
    });
  });
}

function handleFileSelect(file, type, statusEl) {
  const limit = 20 * 1024 * 1024;
  if (file.size > limit) {
    showToast("Choose a file of 20 MB or smaller.", "error");
    return;
  }
  const used = Object.entries(stagedFiles)
    .filter(([key, value]) => key !== type && value)
    .reduce((sum, [, value]) => sum + value.size, 0);
  if (used + file.size > limit) {
    showToast("Combined files must stay within 20 MB.", "error");
    return;
  }
  stagedFiles[type] = file;
  if (statusEl) {
    statusEl.textContent = `Staged ${file.name} (${file.size} bytes). The server checks the byte signature.`;
    statusEl.style.display = "block";
  }
  showToast(`Staged ${file.name}`, "info");
}

function initIngestionForm() {
  const form = document.getElementById("custom-ingest-form");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const statement = document.getElementById("input-transcript");
    const comparison = document.getElementById("input-comparison");
    const caseId = document.getElementById("input-custom-case-id");
    const statementText = statement ? statement.value.trim() : "";
    const comparisonText = comparison ? comparison.value.trim() : "";
    if (!stagedFiles.image && !stagedFiles.video && !stagedFiles.audio && !statementText && !comparisonText) {
      showToast("Stage a file or paste some text.", "error");
      return;
    }
    const formData = new FormData();
    if (caseId && caseId.value.trim()) formData.append("case_id", caseId.value.trim());
    if (stagedFiles.image) formData.append("image_file", stagedFiles.image);
    if (stagedFiles.video) formData.append("video_file", stagedFiles.video);
    if (stagedFiles.audio) formData.append("audio_file", stagedFiles.audio);
    if (statementText) formData.append("text_content", statementText);
    if (comparisonText) formData.append("comparison_text", comparisonText);

    showLoading("Screening a copy of the submitted bytes...");
    try {
      const res = await fetch("/api/analyze/multimodal", { method: "POST", body: formData });
      const report = await res.json();
      if (!res.ok) throw new Error(report.detail || `Server returned ${res.status}`);
      window.currentReport = report;
      populateAllViews(report);
      switchTab("report");
      showToast("Screening finished.", "success");
    } catch (err) {
      showToast(`Screening failed: ${err.message}`, "error");
    } finally {
      hideLoading();
    }
  });
}

async function refreshEngineBadge() {
  const badge = document.getElementById("engine-badge");
  if (!badge) return;
  try {
    const res = await fetch("/api/health");
    const body = await res.json();
    if (!res.ok) throw new Error("offline");
    const video = body.video_decoders && body.video_decoders.opencv ? "GIF, WEBP, and OpenCV video" : "GIF and animated WEBP";
    badge.textContent = `LOCAL ${body.tool_version} · ${video}`;
  } catch (_err) {
    badge.textContent = "LOCAL API OFFLINE";
  }
}

function populateAllViews(report) {
  const verdict = document.getElementById("hero-verdict-val");
  const count = document.getElementById("hero-score-val");
  const indicators = document.getElementById("hero-indicators-val");
  if (verdict) verdict.textContent = report.simulation ? "FIXTURE" : "REVIEW";
  if (count) count.textContent = String((report.evidence_inventory || []).length);
  if (indicators) indicators.textContent = String((report.all_indicators || []).length);
  if (window.truthLensScanner && typeof window.truthLensScanner.setAlert === "function") {
    window.truthLensScanner.setAlert((report.all_indicators || []).length > 0);
  }
  const analyses = report.modality_analyses || {};
  populateImageView(analyses.image);
  populateVideoView(analyses.video);
  populateAudioView(analyses.audio);
  populateTextView(analyses.text);
  populateCrossModalView(report.cross_modal_analysis);
  renderForensicReport(report);
}

function populateImageView(block) {
  const container = document.getElementById("image-inspector-container");
  if (!container) return;
  const note = modalityNote(block, "No image was ingested.");
  if (note) {
    container.innerHTML = `<div class="status-note">${escapeHtml(note)}</div>`;
    return;
  }
  const visuals = block.visualizations || {};
  const first = safeImageUrl(visuals.ela_heatmap) || safeImageUrl(visuals.noise_heatmap) || safeImageUrl(visuals.fft_spectrum);
  const meta = block.metadata || {};
  container.innerHTML = `
    <div class="inspector-layout">
      <div class="visualizer-display">
        <div class="visualizer-controls">
          <button class="mode-toggle-btn active" type="button" data-mode="ela_heatmap">Error-level map</button>
          <button class="mode-toggle-btn" type="button" data-mode="noise_heatmap">High-pass residual</button>
          <button class="mode-toggle-btn" type="button" data-mode="fft_spectrum">Fourier magnitude</button>
        </div>
        <div class="visual-viewport">${first ? `<img id="image-visualizer-main" alt="Measurement image" src="${first}" />` : "<p>No map was produced.</p>"}</div>
        <p class="tiny-note">${escapeHtml(block.task || "")}</p>
        <p class="tiny-note">${escapeHtml(meta.width)}×${escapeHtml(meta.height)} ${escapeHtml(meta.format)} · frames analyzed ${escapeHtml(meta.frames_analyzed)} of ${escapeHtml(meta.frames_in_container)} · face detector ${escapeHtml(meta.face_detector)} · EXIF ${meta.exif_present ? "present" : "not read"}</p>
        <p class="tiny-note">${escapeHtml(block.frame_note || "")}</p>
      </div>
      <div class="forensic-card">
        <div class="card-title">Image measurements</div>
        <div class="card-subtitle">UNVALIDATED PROTOTYPE. These are not an authenticity score.</div>
        <div class="indicators-list">${renderObservationList(block.observations, "No image measurement was produced.")}</div>
      </div>
    </div>
  `;
  const image = container.querySelector("#image-visualizer-main");
  container.querySelectorAll(".mode-toggle-btn").forEach((button) => {
    button.addEventListener("click", () => {
      container.querySelectorAll(".mode-toggle-btn").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      const next = safeImageUrl(visuals[button.getAttribute("data-mode")]);
      if (image && next) image.src = next;
    });
  });
}

function populateVideoView(block) {
  const container = document.getElementById("video-inspector-container");
  if (!container) return;
  const note = modalityNote(block, "No video was ingested.");
  if (note) {
    container.innerHTML = `<div class="status-note">${escapeHtml(note)}</div>`;
    return;
  }
  const meta = block.metadata || {};
  const chart = safeImageUrl((block.visualizations || {}).frame_difference_chart);
  const rows = (block.frame_steps || []).map((step) => `
    <div class="frame-row ${step.threshold_exceeded ? "frame-hit" : ""}">
      <strong>Sampled frame ${escapeHtml(step.later_sampled_frame)}</strong>
      <span>t=${escapeHtml(step.timestamp_seconds)}s</span>
      <span>mean absolute difference ${escapeHtml(step.mean_absolute_difference)}</span>
    </div>
  `).join("");
  container.innerHTML = `
    <div class="forensic-card">
      <div class="card-title">Sampled frame difference</div>
      <div class="card-subtitle">${escapeHtml(block.task || "")}</div>
      <p class="tiny-note">Decoder: ${escapeHtml(meta.decoder)} · container fps ${escapeHtml(meta.fps_reported_by_container)} · sampled frames ${escapeHtml(meta.sampled_frame_count)} · duration ${escapeHtml(meta.duration_seconds)}s · optical flow ${escapeHtml(meta.optical_flow)} · temporal deepfake detector ${escapeHtml(meta.temporal_deepfake_detector)}</p>
      <div class="timeline-scrubber-box">
        ${chart ? `<img class="timeline-chart-img" alt="Frame difference chart" src="${chart}" />` : "<p>No chart was produced.</p>"}
      </div>
      <div class="frame-list">${rows}</div>
      <div class="indicators-list">${renderObservationList(block.observations, "No video measurement was produced.")}</div>
    </div>
  `;
}

function populateAudioView(block) {
  const container = document.getElementById("audio-inspector-container");
  if (!container) return;
  const note = modalityNote(block, "No audio was ingested.");
  if (note) {
    container.innerHTML = `<div class="status-note">${escapeHtml(note)}</div>`;
    return;
  }
  const meta = block.metadata || {};
  const chart = safeImageUrl((block.visualizations || {}).magnitude_spectrogram);
  container.innerHTML = `
    <div class="inspector-layout">
      <div class="forensic-card">
        <div class="card-title">PCM spectrum</div>
        <div class="card-subtitle">${escapeHtml(block.task || "")}</div>
        <div class="visual-viewport">${chart ? `<img alt="Magnitude spectrogram" src="${chart}" />` : "<p>No spectrogram was produced.</p>"}</div>
        <div class="metric-row">
          <div><span>Sample rate</span><strong>${escapeHtml(meta.sample_rate_hz)} Hz</strong></div>
          <div><span>Duration</span><strong>${escapeHtml(meta.duration_seconds)} s</strong></div>
          <div><span>99% rolloff</span><strong>${escapeHtml(meta.rolloff_99_hz)} Hz</strong></div>
          <div><span>Energy above 4 kHz</span><strong>${escapeHtml(meta.high_band_energy_ratio)}</strong></div>
          <div><span>Period variation</span><strong>${escapeHtml(meta.pitch_variation_ratio)}</strong></div>
          <div><span>Spoof classifier</span><strong>${escapeHtml(meta.audio_spoof_classifier)}</strong></div>
        </div>
      </div>
      <div class="forensic-card">
        <div class="card-title">Audio measurements</div>
        <div class="indicators-list">${renderObservationList(block.observations, "No audio measurement was produced.")}</div>
      </div>
    </div>
  `;
}

function populateTextView(block) {
  const container = document.getElementById("text-inspector-container");
  if (!container) return;
  const note = modalityNote(block, "No text was ingested.");
  if (note) {
    container.innerHTML = `<div class="status-note">${escapeHtml(note)}</div>`;
    return;
  }
  const lexical = block.lexical || {};
  const meta = block.metadata || {};
  const shared = (lexical.shared_tokens || []).map((token) => `<span class="token-chip">${escapeHtml(token)}</span>`).join(" ") || "<span class='tiny-note'>No shared tokens.</span>";
  const leftOnly = (lexical.only_in_statement || []).map((token) => `<span class="token-chip">${escapeHtml(token)}</span>`).join(" ") || "<span class='tiny-note'>None.</span>";
  const rightOnly = (lexical.only_in_comparison || []).map((token) => `<span class="token-chip">${escapeHtml(token)}</span>`).join(" ") || "<span class='tiny-note'>None.</span>";
  container.innerHTML = `
    <div class="forensic-card">
      <div class="card-title">Simple lexical screening</div>
      <div class="card-subtitle">${escapeHtml(block.task || "")}</div>
      <p class="tiny-note">Statement tokens ${escapeHtml(meta.statement_token_count)} · comparison tokens ${escapeHtml(meta.comparison_token_count)} · type/token ratio ${escapeHtml(meta.type_token_ratio_statement)} · semantic verifier ${escapeHtml(meta.semantic_verifier)}</p>
      <div class="text-columns">
        <div><h3>Statement</h3><pre>${escapeHtml(lexical.statement_text || "")}</pre></div>
        <div><h3>Comparison text</h3><pre>${escapeHtml(lexical.comparison_text || "")}</pre></div>
      </div>
      <h3>Shared tokens</h3><div class="token-row">${shared}</div>
      <h3>Only in the statement</h3><div class="token-row">${leftOnly}</div>
      <h3>Only in the comparison</h3><div class="token-row">${rightOnly}</div>
      <p class="tiny-note">Jaccard ${escapeHtml(lexical.jaccard)}. ${lexical.both_texts_present ? "Both texts were supplied." : "A second text was not supplied, so overlap was not computed."}</p>
      <div class="indicators-list">${renderObservationList(block.observations, "No lexical observation was produced.")}</div>
    </div>
  `;
}

function populateCrossModalView(cross) {
  const container = document.getElementById("crossmodal-inspector-container");
  if (!container) return;
  if (!cross) {
    container.innerHTML = `<div class="status-note">No cross-modal note was produced.</div>`;
    return;
  }
  const matrix = Object.entries(cross.matrix || {}).map(([name, value]) =>
    `<div class="matrix-cell"><strong>${escapeHtml(name)}</strong><div>${escapeHtml(value)}</div></div>`
  ).join("");
  container.innerHTML = `
    <div class="forensic-card">
      <div class="card-title">Co-occurrence and conflict</div>
      <div class="card-subtitle">${escapeHtml(cross.note || "")}</div>
      <div class="matrix-grid">${matrix}</div>
      <p class="tiny-note">Audio-visual sync: ${escapeHtml(cross.audio_visual_sync_status)}. ${escapeHtml(cross.audio_visual_sync_reason)}</p>
      <p class="tiny-note">Semantic media comparison: ${escapeHtml(cross.semantic_media_status)}. ${escapeHtml(cross.semantic_media_reason)}</p>
    </div>
  `;
}

function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `badge badge-${type === "error" ? "critical" : type === "success" ? "online" : "trust"}`;
  toast.style.position = "fixed";
  toast.style.bottom = "24px";
  toast.style.right = "24px";
  toast.style.zIndex = "9999";
  toast.style.padding = "10px 18px";
  toast.style.fontSize = "0.85rem";
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.4s ease";
    setTimeout(() => toast.remove(), 400);
  }, 3500);
}

function showLoading(text) {
  const overlay = document.getElementById("loading-overlay");
  const label = document.getElementById("loading-text");
  if (overlay) overlay.classList.add("active");
  if (label) label.textContent = text;
}

function hideLoading() {
  const overlay = document.getElementById("loading-overlay");
  if (overlay) overlay.classList.remove("active");
}

/**
 * Report view. The exported JSON is the same object the page rendered.
 */

function renderForensicReport(report) {
  const container = document.getElementById("report-container");
  if (!container || !report) return;

  const banner = report.simulation
    ? `<div class="sim-banner">SIMULATION / GENERATED FIXTURE</div>`
    : `<div class="local-banner">${escapeHtml(report.export_banner || "")}</div>`;
  const inventory = (report.evidence_inventory || []).map((item) => `
    <tr>
      <td><span class="modality-pill ${escapeHtml(item.modality)}">${escapeHtml(item.modality)}</span> ${escapeHtml(item.filename)}<div class="tiny-note">${escapeHtml(item.role)}</div></td>
      <td class="hash-line">${escapeHtml(item.sha256)}</td>
      <td>${escapeHtml(item.size_bytes)} bytes</td>
      <td>${escapeHtml(item.media_type)}</td>
      <td>${escapeHtml(item.ingested_at)} ${escapeHtml(item.timezone || "")}</td>
      <td>${escapeHtml(item.tool_version)}</td>
    </tr>
  `).join("");
  const cross = report.cross_modal_analysis || {};
  const matrixRows = Object.entries(cross.matrix || {}).map(([name, value]) =>
    `<div class="matrix-cell"><strong>${escapeHtml(name)}</strong><div>${escapeHtml(value)}</div></div>`
  ).join("");
  const coRows = (cross.cooccurrence || []).map((item) =>
    `<div class="check-item">${escapeHtml((item.modalities || []).join(" + "))}: ${escapeHtml(item.finding)}</div>`
  ).join("") || `<div class="status-note">No co-occurrence note.</div>`;
  const conflictRows = (cross.conflict || []).map((item) =>
    `<div class="check-item">${escapeHtml((item.modalities || []).join(" + "))}: ${escapeHtml(item.finding)}</div>`
  ).join("") || `<div class="status-note">No conflict note.</div>`;

  container.innerHTML = `
    ${banner}
    <div class="report-actions">
      <div>
        <h2>Screening report</h2>
        <div class="report-meta">Report ID ${escapeHtml(report.report_id)} · Generated ${escapeHtml(report.generated_at)} ${escapeHtml(report.timezone || "UTC")} · ${escapeHtml(report.tool_version)}</div>
      </div>
      <div class="report-buttons">
        <button class="btn btn-secondary" type="button" id="btn-export-json">Export JSON</button>
        <button class="btn" type="button" onclick="window.print()">Print</button>
      </div>
    </div>
    <div class="report-header-banner">
      <div class="verdict-badge-large verdict-review">${escapeHtml(report.conclusion || "Indicators for human review")}</div>
      <p class="summary-copy">${escapeHtml(report.executive_summary)}</p>
      <div class="audit-hash-bar">
        <span>SHA-256 of listed input hashes: ${escapeHtml(report.byte_identity_digest || "none")}</span>
        <span>${escapeHtml(report.byte_identity_meaning || "")}</span>
      </div>
    </div>
    <div class="forensic-card">
      <div class="forensic-card-header"><div class="card-title">Measurements (${(report.observations || []).length})</div></div>
      <div class="indicators-list">${renderObservationList(report.observations, "No measurement was produced.")}</div>
    </div>
    <div class="forensic-card">
      <div class="forensic-card-header">
        <div>
          <div class="card-title">Threshold exceedances (${(report.all_indicators || []).length})</div>
          <div class="card-subtitle">An exceedance is an indicator for a person to review. It is not proof of manipulation.</div>
        </div>
      </div>
      <div class="indicators-list">${renderObservationList(report.all_indicators, "No predeclared rule was exceeded. That is not a negative authenticity result.")}</div>
    </div>
    <div class="forensic-card">
      <div class="forensic-card-header"><div class="card-title">Cross-modal notes</div></div>
      <p class="summary-copy">${escapeHtml(cross.note || "")}</p>
      <p class="tiny-note">Audio-visual sync: ${escapeHtml(cross.audio_visual_sync_status)} — ${escapeHtml(cross.audio_visual_sync_reason)}</p>
      <p class="tiny-note">Semantic comparison: ${escapeHtml(cross.semantic_media_status)} — ${escapeHtml(cross.semantic_media_reason)}</p>
      <div class="matrix-grid">${matrixRows}</div>
      <div class="split-notes">
        <div><h3>Co-occurrence</h3>${coRows}</div>
        <div><h3>Conflict</h3>${conflictRows}</div>
      </div>
    </div>
    <div class="split-notes">
      <div class="forensic-card">
        <div class="card-title">Other explanations</div>
        ${(report.alternative_hypotheses || []).map((line) => `<div class="check-item">${escapeHtml(line)}</div>`).join("")}
        <div class="card-title">Limitations</div>
        ${(report.limitations_and_caveats || []).map((line) => `<div class="check-item">${escapeHtml(line)}</div>`).join("")}
      </div>
      <div class="forensic-card">
        <div class="card-title">Human review</div>
        <ul class="checks-checklist">
          ${(report.recommended_human_checks || []).map((line) => `<li class="check-item">${escapeHtml(line)}</li>`).join("")}
        </ul>
      </div>
    </div>
    <div class="forensic-card">
      <div class="card-title">Byte identity of this intake</div>
      <p class="tiny-note">The hash identifies the preserved bytes. Processing used decoded copies. Nothing here is a compliance certification.</p>
      <table class="custody-table">
        <thead>
          <tr><th>File</th><th>SHA-256</th><th>Size</th><th>Type</th><th>Ingested</th><th>Tool</th></tr>
        </thead>
        <tbody>${inventory || `<tr><td colspan="6">No bytes were submitted.</td></tr>`}</tbody>
      </table>
      <ol class="history-list">
        ${(report.processing_history || []).map((line) => `<li>${escapeHtml(line)}</li>`).join("")}
      </ol>
    </div>
  `;
  const exportButton = document.getElementById("btn-export-json");
  if (exportButton) exportButton.addEventListener("click", exportReportJSON);
}

function exportReportJSON() {
  if (!window.currentReport) {
    showToast("No report is loaded.", "error");
    return;
  }
  const blob = new Blob([JSON.stringify(window.currentReport, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${window.currentReport.report_id || "truthlens-report"}.json`;
  link.click();
  URL.revokeObjectURL(url);
  showToast("Report JSON downloaded.", "success");
}

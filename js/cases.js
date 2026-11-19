/**
 * Preset fixtures. Cards do not contain measurements.
 * Measurements are produced only when the fixture file is sent through the analyzers.
 */

async function loadPresetCases() {
  const container = document.getElementById("preset-cases-grid");
  if (!container) return;
  try {
    const res = await fetch("/api/cases/preset");
    if (!res.ok) throw new Error(`Server returned ${res.status}`);
    const cases = await res.json();
    renderPresetCases(cases, container);
  } catch (err) {
    container.innerHTML = `<div class="status-note">Fixture list unavailable (${escapeHtml(err.message)}). Start the local server. No simulated findings are stored in the page.</div>`;
  }
}

function renderPresetCases(cases, container) {
  container.innerHTML = "";
  cases.forEach((item) => {
    const card = document.createElement("div");
    card.className = "case-card";
    const pills = (item.modalities_included || []).map((name) =>
      `<span class="modality-pill ${escapeHtml(name)}">${escapeHtml(name)}</span>`
    ).join(" ");
    card.innerHTML = `
      <div>
        <div class="sim-stamp">SIMULATION / GENERATED FIXTURE</div>
        <div class="case-id-tag">${escapeHtml(item.case_id)}</div>
        <div class="case-title">${escapeHtml(item.title)}</div>
        <div class="case-desc">${escapeHtml(item.description)}</div>
        <div class="case-modalities">${pills}</div>
      </div>
      <div>
        <div class="case-desc">${escapeHtml(item.expected_findings || "")}</div>
        <button class="btn" type="button" data-case="${escapeHtml(item.case_id)}">Run fixture through analyzers</button>
      </div>
    `;
    card.querySelector("button").addEventListener("click", () => runPresetInvestigation(item.case_id));
    container.appendChild(card);
  });
}

async function runPresetInvestigation(caseId) {
  showLoading(`Analyzing generated fixture ${caseId}...`);
  try {
    const res = await fetch(`/api/cases/preset/${encodeURIComponent(caseId)}/run`, { method: "POST" });
    const report = await res.json();
    if (!res.ok) throw new Error(report.detail || `Server returned ${res.status}`);
    window.currentReport = report;
    populateAllViews(report);
    switchTab("report");
    showToast("Generated fixture screening finished.", "success");
  } catch (err) {
    showToast(`Fixture run failed: ${err.message}`, "error");
  } finally {
    hideLoading();
  }
}

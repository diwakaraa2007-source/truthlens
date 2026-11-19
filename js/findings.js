/**
 * Shared rendering for measurements. Values are escaped before they enter HTML.
 */

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[ch]));
}

function safeImageUrl(url) {
  return typeof url === "string" && url.startsWith("data:image/png;base64,") ? url : "";
}

function renderObservation(item, index) {
  const explanations = (item.alternative_explanations || []).map((line) => `<div>${escapeHtml(line)}</div>`).join("");
  const where = [
    item.location,
    item.frame_number == null ? "" : `frame ${item.frame_number}`,
    item.timestamp_seconds == null ? "" : `t=${item.timestamp_seconds}s`,
    item.segment || ""
  ].filter(Boolean).join(" · ");
  return `
    <article class="indicator-item severity-${escapeHtml(item.severity || "note")}">
      <div class="indicator-top">
        <span class="indicator-title">#${index + 1} ${escapeHtml(item.name)}</span>
        <span class="severity-pill pill-${escapeHtml(item.severity || "note")}">${escapeHtml(item.conclusion || item.severity || "note")}</span>
      </div>
      <div class="indicator-loc">${escapeHtml(item.modality)} · ${escapeHtml(where)}</div>
      <dl class="finding-grid">
        <dt>Method</dt><dd>${escapeHtml(item.method)}</dd>
        <dt>Result</dt><dd>${escapeHtml(item.result)}</dd>
        <dt>Measured value</dt><dd>${escapeHtml(item.measured_value)}</dd>
        <dt>Score type</dt><dd>${escapeHtml(item.score_type)}</dd>
        <dt>Threshold</dt><dd>${escapeHtml(item.threshold)}</dd>
        <dt>What the number means</dt><dd>${escapeHtml(item.confidence_semantics)}</dd>
        <dt>Source SHA-256</dt><dd class="hash-line">${escapeHtml(item.source_sha256)}</dd>
        <dt>Detector</dt><dd>${escapeHtml(item.detector_id)} · ${escapeHtml(item.detector_status)}</dd>
      </dl>
      <div class="indicator-caveat"><strong>Other benign causes:</strong> ${explanations || "None recorded."}</div>
      <div class="indicator-caveat"><strong>Limitation:</strong> ${escapeHtml(item.limitation)}</div>
    </article>
  `;
}

function renderObservationList(items, emptyText) {
  if (!items || !items.length) {
    return `<div class="status-note">${escapeHtml(emptyText)}</div>`;
  }
  return items.map((item, index) => renderObservation(item, index)).join("");
}

function modalityNote(block, emptyLabel) {
  if (!block || block.status === "not_provided") {
    return block && block.note ? block.note : `${emptyLabel} This is missing analysis, not a negative result.`;
  }
  if (block.status === "unsupported" || block.status === "analysis_failed") {
    return block.error || "This analysis did not complete. That is not a negative result.";
  }
  return "";
}

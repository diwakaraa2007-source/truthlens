/**
 * Cursor-linked 3D stage.
 * The page tilts toward the pointer, cards lean under the cursor,
 * and every forensic module orbits as a readable face.
 */
(function () {
  const MODULES = [
    {
      id: "ingest",
      kicker: "01 · INTAKE",
      title: "Ingest & Cases",
      badge: "Intake",
      body: "Stage an image, a video, a PCM WAV file, and two texts. Generated fixtures are marked and are analyzed only when you run them.",
      points: ["SHA-256 byte identity", "20 MB per request", "Not stored after the response"]
    },
    {
      id: "image",
      kicker: "02 · PIXELS",
      title: "Image Lab",
      badge: "ELA / FFT",
      body: "Error-level contrast, a high-pass residual, a Fourier peak ratio, and EXIF presence. This is not face-swap detection or an AI-image classifier.",
      points: ["Error-level map", "High-pass residual", "Fourier magnitude"]
    },
    {
      id: "video",
      kicker: "03 · TIME",
      title: "Video Forensics",
      badge: "Temporal",
      body: "Uploaded MP4, AVI, WEBM, MOV, GIF, and WEBP frames are sampled via OpenCV and Pillow. Frame differences and source timestamps are analyzed. Not temporal deepfake detection.",
      points: ["Sampled frame difference", "Source timestamps", "Unsupported stays visible"]
    },
    {
      id: "audio",
      kicker: "04 · VOICE",
      title: "Audio & Voice",
      badge: "Spectral",
      body: "16-bit PCM WAV is measured for high-band energy and short-window level jumps. No audio-spoof classifier is installed.",
      points: ["FFT energy", "Level jumps", "Spoof model unavailable"]
    },
    {
      id: "text",
      kicker: "05 · CLAIMS",
      title: "Text & Claims",
      badge: "Context",
      body: "Two pasted texts are compared by tokens. Overlap is lexical. Different wording is not called a contradiction.",
      points: ["Both texts shown", "Shared tokens", "No semantic model"]
    },
    {
      id: "crossmodal",
      kicker: "06 · FUSION",
      title: "Cross-Modal Fusion",
      badge: "Synthesis",
      body: "The page can say that measurements co-occur or conflict. It does not treat one signal as proof of intent or identity.",
      points: ["Co-occurrence", "Conflict", "Missing stays missing"]
    },
    {
      id: "report",
      kicker: "07 · AUDIT",
      title: "Forensic Report",
      badge: "Audit Report",
      body: "The report lists measurements, the bytes' SHA-256, and the label Indicators for human review.",
      points: ["Same JSON as the page", "Report ID and time", "Human review"]
    }
  ];

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  document.addEventListener("DOMContentLoaded", () => {
    const ring = document.getElementById("orbit-ring");
    const stage = document.getElementById("orbit-stage");
    const readout = document.getElementById("orbit-readout");
    if (!ring || !stage) return;

    const main = document.querySelector("main.main-container");
    document.body.classList.add("page-tilt");

    ring.innerHTML = MODULES.map((mod, i) => `
      <button class="orbit-card" type="button" data-tab="${mod.id}" data-index="${i}" style="--i:${i}">
        <span class="orbit-kicker">${mod.kicker}</span>
        <span class="orbit-title">${mod.title}</span>
        <span class="orbit-badge">${mod.badge}</span>
        <span class="orbit-body">${mod.body}</span>
        <span class="orbit-points">${mod.points.map((p) => `<span>${p}</span>`).join("")}</span>
      </button>
    `).join("");

    const core = document.createElement("div");
    core.className = "orbit-core";
    core.id = "orbit-core";
    core.innerHTML = `
      <div class="orbit-core-kicker" id="core-kicker"></div>
      <div class="orbit-core-title" id="core-title"></div>
      <p class="orbit-core-body" id="core-body"></p>
      <div class="orbit-live" id="orbit-live"></div>
    `;
    stage.appendChild(core);

    const cards = [...ring.querySelectorAll(".orbit-card")];
    const coreKicker = document.getElementById("core-kicker");
    const coreTitle = document.getElementById("core-title");
    const coreBody = document.getElementById("core-body");
    const live = document.getElementById("orbit-live");
    const count = MODULES.length;
    const step = 360 / count;

    let yaw = 0;
    let tiltX = 12;
    let targetYaw = 0;
    let targetTilt = 12;
    let pointerInside = false;
    let pointerNX = 0;
    let pointerNY = 0;
    let activeIndex = 0;
    let pageX = 0;
    let pageY = 0;

    function liveLine() {
      const verdict = document.getElementById("hero-verdict-val");
      const score = document.getElementById("hero-score-val");
      const flags = document.getElementById("hero-indicators-val");
      if (!live || !verdict) return;
      live.textContent = `${verdict.textContent} · ${score ? score.textContent : "--%"} · ${flags ? flags.textContent : "0"} signals`;
    }

    function showModule(index) {
      const mod = MODULES[index];
      if (!mod || (index === activeIndex && coreTitle.textContent === mod.title)) {
        liveLine();
        return;
      }
      activeIndex = index;
      coreKicker.textContent = mod.kicker;
      coreTitle.textContent = mod.title;
      coreBody.textContent = mod.body;
      liveLine();
      cards.forEach((card, i) => card.classList.toggle("is-front", i === index));
      if (readout) {
        readout.textContent = `${mod.kicker}  ·  ${mod.points.join("  ·  ")}`;
      }
    }

    cards.forEach((card) => {
      card.addEventListener("click", () => {
        const tab = card.getAttribute("data-tab");
        const index = Number(card.getAttribute("data-index"));
        targetYaw = -index * step;
        yaw = targetYaw;
        showModule(index);
        if (typeof switchTab === "function") switchTab(tab);
      });
    });

    showModule(0);

    const heroVerdict = document.getElementById("hero-verdict-val");
    if (heroVerdict && window.MutationObserver) {
      const sync = () => liveLine();
      new MutationObserver(sync).observe(heroVerdict, { childList: true, characterData: true, subtree: true });
      ["hero-score-val", "hero-indicators-val"].forEach((id) => {
        const node = document.getElementById(id);
        if (node) new MutationObserver(sync).observe(node, { childList: true, characterData: true, subtree: true });
      });
    }

    function faceDelta(angle, index) {
      let face = (angle + index * step) % 360;
      if (face > 180) face -= 360;
      if (face < -180) face += 360;
      return face;
    }

    function facingIndex(angle) {
      let best = 0;
      let bestDelta = 999;
      for (let i = 0; i < count; i++) {
        const d = Math.abs(faceDelta(angle, i));
        if (d < bestDelta) {
          bestDelta = d;
          best = i;
        }
      }
      return best;
    }

    function applyPose() {
      ring.style.transform = `rotateX(${tiltX.toFixed(2)}deg) rotateY(${yaw.toFixed(2)}deg)`;
      const front = facingIndex(yaw);
      cards.forEach((card, i) => {
        const mag = Math.abs(faceDelta(yaw, i));
        const visible = mag < 100;
        card.style.opacity = visible ? String(1 - mag / 140) : "0.08";
        card.style.pointerEvents = mag < 70 ? "auto" : "none";
        card.classList.toggle("is-front", i === front);
      });
      if (front !== activeIndex) showModule(front);
    }

    function frame() {
      if (!reduceMotion) {
        const steer = pointerInside ? pointerNX * 1.35 : 0;
        targetYaw += pointerInside ? 0.16 + steer : 0.32;
        yaw += (targetYaw - yaw) * 0.08;
        tiltX += (targetTilt - tiltX) * 0.08;
        if (main) {
          const typing = document.activeElement && /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
          const rx = typing ? 0 : pageY * -5;
          const ry = typing ? 0 : pageX * 7;
          main.style.transform = `rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(2)}deg)`;
        }
        applyPose();
      }
      requestAnimationFrame(frame);
    }

    window.addEventListener("mousemove", (e) => {
      pageX = e.clientX / window.innerWidth - 0.5;
      pageY = e.clientY / window.innerHeight - 0.5;
    });

    stage.addEventListener("mouseenter", () => {
      pointerInside = true;
    });
    stage.addEventListener("mouseleave", () => {
      pointerInside = false;
      targetTilt = 12;
    });
    stage.addEventListener("mousemove", (e) => {
      const rect = stage.getBoundingClientRect();
      pointerNX = (e.clientX - rect.left) / rect.width - 0.5;
      pointerNY = (e.clientY - rect.top) / rect.height - 0.5;
      targetTilt = 8 + pointerNY * -18;
    });

    document.addEventListener("mousemove", (e) => {
      const card = e.target.closest(".forensic-card, .case-card, .dropzone-box, .stat-box, .hologram-hero");
      if (!card || reduceMotion) return;
      if (card.dataset.tiltBound !== "1") return;
      const rect = card.getBoundingClientRect();
      const px = (e.clientX - rect.left) / rect.width - 0.5;
      const py = (e.clientY - rect.top) / rect.height - 0.5;
      const max = card.classList.contains("hologram-hero") ? 6 : 9;
      card.style.transform = `perspective(900px) rotateX(${(-py * max).toFixed(2)}deg) rotateY(${(px * max).toFixed(2)}deg) translateZ(10px)`;
    });

    function armTilt(root) {
      root.querySelectorAll(".forensic-card, .case-card, .dropzone-box, .stat-box, .hologram-hero").forEach((el) => {
        if (el.dataset.tiltBound === "1") return;
        el.dataset.tiltBound = "1";
        el.addEventListener("mouseleave", () => {
          el.style.transform = "";
        });
      });
    }

    armTilt(document);
    const grid = document.getElementById("preset-cases-grid");
    if (grid && window.MutationObserver) {
      new MutationObserver(() => armTilt(grid)).observe(grid, { childList: true });
    }

    if (reduceMotion) {
      stage.classList.add("orbit-static");
      applyPose();
    } else {
      requestAnimationFrame(frame);
    }
  });
})();

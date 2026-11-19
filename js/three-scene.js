/**
 * TruthLens 3D Holographic Forensic Scanner Engine
 * Real-time 3D WebGL/Canvas perspective engine with rotating biometric wireframe,
 * dynamic sweeping laser plane, and anomaly-reactive particle swarm.
 */

class TruthLens3DScanner {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;

    this.ctx = this.canvas.getContext("2d");
    this.width = this.canvas.parentElement.clientWidth || 340;
    this.height = this.canvas.parentElement.clientHeight || 250;
    this.canvas.width = this.width;
    this.canvas.height = this.height;

    // 3D Camera & Rotation state
    this.cameraDistance = 4.2;
    this.rotX = 0.25;
    this.rotY = 0.0;
    this.autoRotate = true;
    this.wireframeMode = "icosahedron"; // 'icosahedron' | 'face_mesh'
    this.isAlertMode = false;

    // Laser scan plane state
    this.laserY = -1.2;
    this.laserDir = 1;
    this.laserSpeed = 0.022;

    // Interaction
    this.isDragging = false;
    this.lastMouseX = 0;
    this.lastMouseY = 0;
    this.spin = 0;
    this.pointerActive = false;
    this.pointerRotX = 0.25;
    this.pointerRotY = 0;

    // 3D Geometry vertices and edges
    this.initGeometry();
    this.initParticles();
    this.bindEvents();
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  initGeometry() {
    // 3D Icosahedron / Geodesic forensic node sphere
    const phi = (1 + Math.sqrt(5)) / 2;
    const a = 1.0;
    const b = 1.0 / phi;

    const rawVertices = [
      [-b, a, 0], [b, a, 0], [-b, -a, 0], [b, -a, 0],
      [0, -b, a], [0, b, a], [0, -b, -a], [0, b, -a],
      [a, 0, -b], [a, 0, b], [-a, 0, -b], [-a, 0, b]
    ];

    // Normalize vertices to radius 1.2
    this.vertices = rawVertices.map(v => {
      const len = Math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2]);
      return [v[0]/len * 1.25, v[1]/len * 1.25, v[2]/len * 1.25];
    });

    // Edges connecting vertices
    this.edges = [];
    for (let i = 0; i < this.vertices.length; i++) {
      for (let j = i + 1; j < this.vertices.length; j++) {
        const dx = this.vertices[i][0] - this.vertices[j][0];
        const dy = this.vertices[i][1] - this.vertices[j][1];
        const dz = this.vertices[i][2] - this.vertices[j][2];
        const dist = Math.sqrt(dx*dx + dy*dy + dz*dz);
        // Connect neighbors
        if (dist < 1.4) {
          this.edges.push([i, j]);
        }
      }
    }

    // Biometric facial contour points (simulated 3D facial mask)
    this.facePoints = [
      // Jawline
      [-0.9, 0.4, 0.4], [-0.7, -0.2, 0.6], [-0.4, -0.8, 0.7], [0, -1.0, 0.8],
      [0.4, -0.8, 0.7], [0.7, -0.2, 0.6], [0.9, 0.4, 0.4],
      // Eyes & Brow
      [-0.45, 0.35, 0.75], [-0.2, 0.4, 0.82], [0.2, 0.4, 0.82], [0.45, 0.35, 0.75],
      // Nose bridge & tip
      [0, 0.45, 0.85], [0, 0.1, 0.95], [0, -0.15, 1.05],
      // Mouth
      [-0.3, -0.45, 0.85], [0, -0.42, 0.92], [0.3, -0.45, 0.85], [0, -0.55, 0.88]
    ];
  }

  initParticles() {
    this.particles = [];
    const count = 120;
    for (let i = 0; i < count; i++) {
      const radius = 1.3 + Math.random() * 1.5;
      const theta = Math.random() * Math.PI * 2;
      const phi = (Math.random() - 0.5) * Math.PI;
      this.particles.push({
        x: radius * Math.cos(phi) * Math.cos(theta),
        y: radius * Math.sin(phi),
        z: radius * Math.cos(phi) * Math.sin(theta),
        speed: 0.008 + Math.random() * 0.015,
        angle: theta,
        radius: radius,
        size: 1 + Math.random() * 2
      });
    }
  }

  bindEvents() {
    window.addEventListener("resize", () => {
      this.width = this.canvas.parentElement.clientWidth || 340;
      this.height = this.canvas.parentElement.clientHeight || 250;
      this.canvas.width = this.width;
      this.canvas.height = this.height;
    });

    this.canvas.addEventListener("mousedown", (e) => {
      this.isDragging = true;
      this.autoRotate = false;
      this.lastMouseX = e.clientX;
      this.lastMouseY = e.clientY;
    });

    window.addEventListener("mouseup", () => {
      this.isDragging = false;
    });

    window.addEventListener("mousemove", (e) => {
      if (this.isDragging) {
        const dx = e.clientX - this.lastMouseX;
        const dy = e.clientY - this.lastMouseY;
        this.rotY += dx * 0.01;
        this.rotX += dy * 0.01;
        this.lastMouseX = e.clientX;
        this.lastMouseY = e.clientY;
        return;
      }
      const nx = e.clientX / window.innerWidth - 0.5;
      const ny = e.clientY / window.innerHeight - 0.5;
      this.pointerRotY = nx * 1.8;
      this.pointerRotX = 0.2 + ny * 0.95;
      this.pointerActive = true;
      this.autoRotate = false;
    });

    // Toggle controls
    const toggleSpeedBtn = document.getElementById("btn-toggle-scan");
    if (toggleSpeedBtn) {
      toggleSpeedBtn.addEventListener("click", () => {
        this.laserSpeed = this.laserSpeed > 0.03 ? 0.015 : 0.045;
      });
    }

    const resetCamBtn = document.getElementById("btn-reset-cam");
    if (resetCamBtn) {
      resetCamBtn.addEventListener("click", () => {
        this.rotX = 0.25;
        this.rotY = 0.0;
        this.pointerRotX = 0.25;
        this.pointerRotY = 0;
        this.autoRotate = true;
        this.pointerActive = false;
      });
    }

    const toggleModeBtn = document.getElementById("btn-toggle-mode");
    if (toggleModeBtn) {
      toggleModeBtn.addEventListener("click", () => {
        this.wireframeMode = this.wireframeMode === "icosahedron" ? "face_mesh" : "icosahedron";
      });
    }
  }

  project(p) {
    // 3D perspective projection
    // Rotate around Y
    const yaw = this.rotY + this.spin;
    const cosY = Math.cos(yaw);
    const sinY = Math.sin(yaw);
    let x1 = p[0] * cosY - p[2] * sinY;
    let z1 = p[0] * sinY + p[2] * cosY;

    // Rotate around X
    const cosX = Math.cos(this.rotX);
    const sinX = Math.sin(this.rotX);
    let y2 = p[1] * cosX - z1 * sinX;
    let z2 = p[1] * sinX + z1 * cosX;

    // Distance camera
    const zDist = z2 + this.cameraDistance;
    const fov = 340;
    const scale = fov / Math.max(0.1, zDist);

    return {
      x: this.width / 2 + x1 * scale,
      y: this.height / 2 - y2 * scale,
      scale: scale,
      z: zDist
    };
  }

  setAlert(isAlert) {
    this.isAlertMode = isAlert;
  }

  animate() {
    this.ctx.clearRect(0, 0, this.width, this.height);

    this.spin += 0.01;
    if (!this.isDragging && this.pointerActive) {
      this.rotX += (this.pointerRotX - this.rotX) * 0.08;
      this.rotY += (this.pointerRotY - this.rotY) * 0.08;
    } else if (this.autoRotate && !this.isDragging) {
      this.rotY += 0.004;
    }

    // Laser plane vertical sweep
    this.laserY += this.laserSpeed * this.laserDir;
    if (this.laserY > 1.3) this.laserDir = -1;
    if (this.laserY < -1.3) this.laserDir = 1;

    // 1. Draw 3D Cyber Floor Grid
    this.ctx.lineWidth = 1;
    this.ctx.strokeStyle = "rgba(0, 240, 255, 0.12)";
    const floorY = -1.4;
    const gridSize = 4;
    const gridStep = 0.8;

    for (let gx = -gridSize; gx <= gridSize; gx += gridStep) {
      const p1 = this.project([gx, floorY, -gridSize]);
      const p2 = this.project([gx, floorY, gridSize]);
      this.ctx.beginPath();
      this.ctx.moveTo(p1.x, p1.y);
      this.ctx.lineTo(p2.x, p2.y);
      this.ctx.stroke();
    }

    for (let gz = -gridSize; gz <= gridSize; gz += gridStep) {
      const p1 = this.project([-gridSize, floorY, gz]);
      const p2 = this.project([gridSize, floorY, gz]);
      this.ctx.beginPath();
      this.ctx.moveTo(p1.x, p1.y);
      this.ctx.lineTo(p2.x, p2.y);
      this.ctx.stroke();
    }

    // 2. Draw 3D Particle Field
    const particleColor = this.isAlertMode ? "rgba(255, 0, 85," : "rgba(0, 240, 255,";
    this.particles.forEach(p => {
      p.angle += p.speed;
      const px = p.radius * Math.cos(p.angle);
      const pz = p.radius * Math.sin(p.angle);
      const proj = this.project([px, p.y, pz]);

      const alpha = Math.max(0.15, Math.min(0.85, (4.5 - proj.z) / 3));
      this.ctx.fillStyle = `${particleColor} ${alpha})`;
      this.ctx.beginPath();
      this.ctx.arc(proj.x, proj.y, p.size, 0, Math.PI * 2);
      this.ctx.fill();
    });

    // 3. Draw 3D Laser Scanning Ring Plane
    const scanRingRadius = 1.35;
    const scanRingPoints = [];
    const ringSegments = 24;
    for (let i = 0; i <= ringSegments; i++) {
      const rad = (i / ringSegments) * Math.PI * 2;
      scanRingPoints.push([
        Math.cos(rad) * scanRingRadius,
        this.laserY,
        Math.sin(rad) * scanRingRadius
      ]);
    }

    const ringProj = scanRingPoints.map(p => this.project(p));
    this.ctx.beginPath();
    this.ctx.strokeStyle = this.isAlertMode ? "rgba(255, 0, 85, 0.85)" : "rgba(0, 240, 255, 0.85)";
    this.ctx.lineWidth = 2;
    ringProj.forEach((p, idx) => {
      if (idx === 0) this.ctx.moveTo(p.x, p.y);
      else this.ctx.lineTo(p.x, p.y);
    });
    this.ctx.stroke();

    // 4. Draw 3D Wireframe Target
    if (this.wireframeMode === "icosahedron") {
      const projectedNodes = this.vertices.map(v => this.project(v));

      // Edges
      this.ctx.lineWidth = 1.2;
      this.edges.forEach(([i, j]) => {
        const p1 = projectedNodes[i];
        const p2 = projectedNodes[j];
        const midY = (this.vertices[i][1] + this.vertices[j][1]) / 2;
        const distToLaser = Math.abs(midY - this.laserY);

        if (distToLaser < 0.25) {
          // Highlight edge intersected by laser
          this.ctx.strokeStyle = this.isAlertMode ? "rgba(255, 0, 85, 0.95)" : "rgba(0, 255, 157, 0.95)";
          this.ctx.lineWidth = 2.2;
        } else {
          this.ctx.strokeStyle = this.isAlertMode ? "rgba(255, 0, 85, 0.35)" : "rgba(0, 240, 255, 0.35)";
          this.ctx.lineWidth = 1.0;
        }

        this.ctx.beginPath();
        this.ctx.moveTo(p1.x, p1.y);
        this.ctx.lineTo(p2.x, p2.y);
        this.ctx.stroke();
      });

      // Nodes
      projectedNodes.forEach((p, idx) => {
        const nodeY = this.vertices[idx][1];
        const isNearLaser = Math.abs(nodeY - this.laserY) < 0.25;
        this.ctx.fillStyle = isNearLaser ? (this.isAlertMode ? "#ff0055" : "#00ff9d") : (this.isAlertMode ? "#ff5588" : "#00f0ff");
        this.ctx.beginPath();
        this.ctx.arc(p.x, p.y, isNearLaser ? 4 : 2.5, 0, Math.PI * 2);
        this.ctx.fill();
      });

    } else {
      // Biometric Facial Mesh Mode
      const projectedFace = this.facePoints.map(p => this.project(p));
      this.ctx.lineWidth = 1.5;
      this.ctx.strokeStyle = this.isAlertMode ? "rgba(255, 0, 85, 0.7)" : "rgba(0, 240, 255, 0.7)";

      this.ctx.beginPath();
      projectedFace.forEach((p, idx) => {
        if (idx === 0) this.ctx.moveTo(p.x, p.y);
        else this.ctx.lineTo(p.x, p.y);
      });
      this.ctx.stroke();

      projectedFace.forEach(p => {
        this.ctx.fillStyle = this.isAlertMode ? "#ff0055" : "#00ff9d";
        this.ctx.beginPath();
        this.ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
        this.ctx.fill();
      });
    }

    // Diagnostics text overlay
    this.ctx.font = "9px monospace";
    this.ctx.fillStyle = this.isAlertMode ? "rgba(255, 0, 85, 0.8)" : "rgba(0, 240, 255, 0.7)";
    this.ctx.fillText(`3D SCANNER: ${this.wireframeMode.toUpperCase()}`, 10, 15);
    this.ctx.fillText(`LASER ELEVATION: ${this.laserY.toFixed(2)}m`, 10, 27);
    this.ctx.fillText(`ORBIT: [${(this.rotX * 57.3).toFixed(0)}°, ${(this.rotY * 57.3).toFixed(0)}°]`, 10, 39);

    requestAnimationFrame(this.animate);
  }
}

// Instantiate on load
window.addEventListener("DOMContentLoaded", () => {
  window.truthLensScanner = new TruthLens3DScanner("three-canvas");
});

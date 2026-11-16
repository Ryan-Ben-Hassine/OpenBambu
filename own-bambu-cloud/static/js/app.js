/**
 * Own your bambu Cloud - Frontend Application Controller
 * Pure vanilla JavaScript, zero heavy frameworks, responsive and fast.
 * Author: Ryan Ben Hassine (https://ryanbenhassine.com)
 * License: https://ryanbenhassine.com
 * Copyright (c) 2026 Ryan Ben Hassine. All rights reserved.
 */

const App = {
  activePrinterId: null,
  printers: [],
  filaments: [],
  telemetry: {},
  settings: {},
  pollTimer: null,

  async init() {
    this.bindEvents();
    await this.loadPrinters();
    await this.loadFilaments();
    await this.loadSettings();
    this.startPolling();
  },

  bindEvents() {
    // Navigation Tabs (Sidebar)
    document.querySelectorAll('.nav-item-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const targetTab = btn.getAttribute('data-tab');
        this.switchTab(targetTab);
      });
    });

    // Printer Selector
    const printerSelect = document.getElementById('printerSelect');
    if (printerSelect) {
      printerSelect.addEventListener('change', (e) => {
        this.selectPrinter(e.target.value);
      });
    }

    // Bed Position Slider
    const bedSlider = document.getElementById('bedSlider');
    if (bedSlider) {
      bedSlider.addEventListener('change', (e) => {
        this.sendAction('bed_pct', parseInt(e.target.value));
      });
      bedSlider.addEventListener('input', (e) => {
        const valEl = document.getElementById('bedSliderVal');
        if (valEl) valEl.innerText = `${e.target.value}% (~${Math.round((e.target.value / 100) * 256)}mm)`;
      });
    }

    // Video Logo Upload
    const logoInput = document.getElementById('logoFileInput');
    if (logoInput) {
      logoInput.addEventListener('change', (e) => this.uploadLogo(e.target.files[0]));
    }
  },

  switchTab(tabId) {
    document.querySelectorAll('.nav-item-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));

    const activeBtn = document.querySelector(`.nav-item-btn[data-tab="${tabId}"]`);
    const activeSection = document.getElementById(`tab-${tabId}`);
    if (activeBtn) activeBtn.classList.add('active');
    if (activeSection) activeSection.classList.add('active');

    // Update Topbar Title
    const titleEl = document.getElementById('pageTitle');
    if (titleEl) {
      const titles = {
        dashboard: '<i class="ti ti-dashboard" style="color: var(--primary);"></i> Dashboard',
        filaments: '<i class="ti ti-cylinder" style="color: var(--primary);"></i> Filament Stock & AMS Sync',
        aieye: '<i class="ti ti-eye" style="color: var(--primary);"></i> AI Eye Guardian',
        videos: '<i class="ti ti-video" style="color: var(--primary);"></i> Video Studio & Logo Watermark',
        schedule: '<i class="ti ti-calendar-time" style="color: var(--primary);"></i> Schedule Queue <span class="badge-pro" style="margin-left:6px;">PRO</span>',
        printers: '<i class="ti ti-printer" style="color: var(--primary);"></i> Configured Bambu Printers'
      };
      titleEl.innerHTML = titles[tabId] || 'Own your bambu Cloud';
    }

    if (tabId === 'filaments') {
      this.loadFilaments();
    } else if (tabId === 'printers') {
      this.renderPrintersList();
    } else if (tabId === 'videos') {
      this.loadVideos();
    } else if (tabId === 'aieye') {
      this.loadAIHistory();
    }
  },

  // ================= PRINTERS MANAGEMENT =================
  async loadPrinters() {
    try {
      const res = await fetch('/api/printers');
      const data = await res.json();
      this.printers = data.printers || [];

      const select = document.getElementById('printerSelect');
      const emptyState = document.getElementById('emptyPrintersState');
      const dashGrid = document.querySelector('#tab-dashboard .dashboard-grid');

      if (select) select.innerHTML = '';

      if (this.printers.length === 0) {
        this.activePrinterId = null;
        if (emptyState) emptyState.style.display = 'block';
        if (dashGrid) dashGrid.style.display = 'none';
        if (select) {
          select.innerHTML = '<option value="">No Printer Added</option>';
        }
        this.renderPrintersList();
        return;
      }

      // We have printers
      if (emptyState) emptyState.style.display = 'none';
      if (dashGrid) dashGrid.style.display = 'grid';

      if (select) {
        this.printers.forEach(p => {
          const opt = document.createElement('option');
          opt.value = p.id;
          opt.textContent = `${p.name} (${p.model || 'P1S'})`;
          if (p.is_default || p.id === this.activePrinterId) opt.selected = true;
          select.appendChild(opt);
        });
      }

      if (!this.activePrinterId || !this.printers.some(p => p.id === this.activePrinterId)) {
        const defaultP = this.printers.find(p => p.is_default) || this.printers[0];
        this.activePrinterId = defaultP.id;
      }

      this.updateCameraSource();
      this.renderPrintersList();
    } catch (err) {
      console.error('Failed to load printers:', err);
    }
  },

  renderPrintersList() {
    const container = document.getElementById('printersListTable');
    if (!container) return;

    if (this.printers.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 2.5rem 1rem; color: var(--text-dim);">
          <i class="ti ti-printer-off" style="font-size: 2.5rem; margin-bottom: 0.75rem; display: block; opacity: 0.5;"></i>
          <p style="font-size: 0.95rem; margin-bottom: 1rem;">No printers configured yet.</p>
          <button class="btn-primary" onclick="App.openModal('addPrinterModal')">
            <i class="ti ti-plus"></i> Add Bambu Printer Manually
          </button>
        </div>
      `;
      return;
    }

    let html = `
      <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; font-size: 0.88rem; text-align: left;">
          <thead>
            <tr style="border-bottom: 1px solid var(--border); color: var(--text-muted); font-size: 0.78rem; text-transform: uppercase;">
              <th style="padding: 0.75rem;">Name</th>
              <th style="padding: 0.75rem;">Model</th>
              <th style="padding: 0.75rem;">Local IP</th>
              <th style="padding: 0.75rem;">Serial</th>
              <th style="padding: 0.75rem; text-align: right;">Action</th>
            </tr>
          </thead>
          <tbody>
    `;

    this.printers.forEach(p => {
      const isCurrent = p.id === this.activePrinterId;
      html += `
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.04); ${isCurrent ? 'background: rgba(249,115,22,0.04);' : ''}">
          <td style="padding: 0.85rem; font-weight: 700;">
            ${p.name} ${isCurrent ? '<span style="font-size: 0.7rem; background: var(--primary); color:#fff; padding:2px 6px; border-radius:4px; margin-left:6px;">ACTIVE</span>' : ''}
          </td>
          <td style="padding: 0.85rem; color: var(--text-muted);">${p.model || 'P1S'}</td>
          <td style="padding: 0.85rem; font-family: monospace; color: var(--text-main);">${p.ip}</td>
          <td style="padding: 0.85rem; font-family: monospace; color: var(--text-dim); font-size: 0.8rem;">${p.serial}</td>
          <td style="padding: 0.85rem; text-align: right;">
            ${!isCurrent ? `<button class="preset-btn" onclick="App.selectPrinter('${p.id}')" style="margin-right: 6px;"><i class="ti ti-check"></i> Select</button>` : ''}
            <button class="preset-btn" style="color: var(--danger); border-color: rgba(239,68,68,0.25);" onclick="App.deletePrinter('${p.id}', '${p.name.replace(/'/g, "\\'")}')" title="Delete Printer">
              <i class="ti ti-trash"></i>
            </button>
          </td>
        </tr>
      `;
    });

    html += `</tbody></table></div>`;
    container.innerHTML = html;
  },

  async deletePrinter(printerId, printerName) {
    if (!confirm(`Are you sure you want to remove "${printerName}" from JSON config?`)) return;

    try {
      const res = await fetch(`/api/printers/${printerId}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.ok) {
        if (this.activePrinterId === printerId) {
          this.activePrinterId = null;
        }
        await this.loadPrinters();
      }
    } catch (err) {
      alert('Failed to delete printer: ' + err.message);
    }
  },

  selectPrinter(printerId) {
    this.activePrinterId = printerId;
    const select = document.getElementById('printerSelect');
    if (select) select.value = printerId;
    this.updateCameraSource();
    this.renderPrintersList();
    this.pollTelemetry();
  },

  async submitNewPrinter() {
    const name = document.getElementById('newPrinterName').value.trim();
    const model = document.getElementById('newPrinterModel').value;
    const ip = document.getElementById('newPrinterIp').value.trim();
    const accessCode = document.getElementById('newPrinterAccessCode').value.trim();
    const serial = document.getElementById('newPrinterSerial').value.trim();

    if (!name || !ip || !accessCode || !serial) {
      alert('Please fill out all required fields (Name, IP, Access Code, Serial).');
      return;
    }

    try {
      const res = await fetch('/api/printers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name, model, ip, access_code: accessCode, serial, is_default: this.printers.length === 0
        })
      });
      const data = await res.json();
      if (data.ok) {
        this.closeModal('addPrinterModal');
        // Clear form
        document.getElementById('newPrinterName').value = '';
        document.getElementById('newPrinterIp').value = '';
        document.getElementById('newPrinterAccessCode').value = '';
        document.getElementById('newPrinterSerial').value = '';

        await this.loadPrinters();
        this.selectPrinter(data.printer.id);
        this.switchTab('dashboard');
      }
    } catch (err) {
      alert('Failed to save printer: ' + err.message);
    }
  },

  // ================= FILAMENT STOCK & AMS SYNC =================
  async loadFilaments() {
    try {
      const res = await fetch('/api/filaments');
      const data = await res.json();
      this.filaments = data.filaments || [];
      this.renderFilaments();
    } catch (err) {
      console.warn('Failed to load filaments:', err);
    }
  },

  renderFilaments() {
    const container = document.getElementById('filamentsGrid');
    if (!container) return;

    if (this.filaments.length === 0) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 2.5rem 1rem; color: var(--text-dim);">
          <i class="ti ti-cylinder" style="font-size: 2.5rem; opacity: 0.4; display: block; margin-bottom: 0.75rem;"></i>
          <p style="font-size: 0.95rem; margin-bottom: 1rem;">No filament spools in inventory yet.</p>
          <button class="btn-primary" onclick="App.openModal('addFilamentModal')">
            <i class="ti ti-plus"></i> Add First Spool to Stock
          </button>
        </div>
      `;
      return;
    }

    let html = '';
    this.filaments.forEach(f => {
      const remainPct = Math.round((f.remaining_grams / (f.initial_grams || 1000)) * 100);
      html += `
        <div class="filament-card">
          <div class="filament-header">
            <div class="filament-swatch" style="background-color: ${f.color_hex};"></div>
            <div>
              <div class="filament-brand">${f.brand}</div>
              <div class="filament-name">${f.color_name}</div>
            </div>
            <span class="filament-material-badge">${f.material}</span>
          </div>

          <div class="spool-weight-bar">
            <div class="spool-weight-fill" style="width: ${remainPct}%; background-color: ${f.color_hex};"></div>
          </div>

          <div class="spool-weight-meta">
            <span>Remaining: ${Math.round(f.remaining_grams)}g (${remainPct}%)</span>
            <span>Spool: ${Math.round(f.initial_grams || 1000)}g</span>
          </div>

          <div style="display: flex; gap: 0.5rem; margin-top: 1rem;">
            <div style="flex: 1; position: relative;">
              <select class="form-select" style="padding: 0.4rem 0.6rem; font-size: 0.78rem;" onchange="App.assignSpoolToAms('${f.id}', this.value); this.value='';">
                <option value="">Sync to AMS Slot ▾</option>
                <option value="1">Assign to Slot 1</option>
                <option value="2">Assign to Slot 2</option>
                <option value="3">Assign to Slot 3</option>
                <option value="4">Assign to Slot 4</option>
              </select>
            </div>
            <button class="preset-btn" style="color: var(--danger); border-color: rgba(239,68,68,0.25);" onclick="App.deleteFilament('${f.id}')" title="Delete Spool">
              <i class="ti ti-trash"></i>
            </button>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  },

  async submitNewFilament() {
    const brand = document.getElementById('spoolBrand').value.trim() || 'Generic';
    const material = document.getElementById('spoolMaterial').value;
    const colorName = document.getElementById('spoolColorName').value.trim() || 'Standard';
    const colorHex = document.getElementById('spoolColorHex').value;
    const weight = parseFloat(document.getElementById('spoolWeight').value) || 1000;

    try {
      const res = await fetch('/api/filaments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          brand,
          material,
          color_name: colorName,
          color_hex: colorHex,
          remaining_grams: weight,
          initial_grams: weight,
          diameter: 1.75
        })
      });
      const data = await res.json();
      if (data.ok) {
        this.closeModal('addFilamentModal');
        // Reset inputs
        document.getElementById('spoolBrand').value = '';
        document.getElementById('spoolColorName').value = '';
        await this.loadFilaments();
      }
    } catch (err) {
      alert('Failed to add filament: ' + err.message);
    }
  },

  async deleteFilament(filamentId) {
    if (!confirm('Remove this spool from filament stock?')) return;
    try {
      const res = await fetch(`/api/filaments/${filamentId}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.ok) {
        await this.loadFilaments();
      }
    } catch (err) {
      alert('Failed to delete filament: ' + err.message);
    }
  },

  async assignSpoolToAms(filamentId, slotNum) {
    if (!slotNum) return;
    if (!this.activePrinterId) {
      alert('Please connect or select a Bambu printer first.');
      return;
    }

    const slotIndex = parseInt(slotNum) - 1;
    try {
      const res = await fetch(`/api/printers/${this.activePrinterId}/ams/assign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ams_id: 0,
          tray_id: slotIndex,
          filament_id: filamentId
        })
      });
      const data = await res.json();
      if (data.ok) {
        alert(`Spool successfully assigned & synced to AMS Slot ${slotNum}!`);
        this.pollTelemetry();
      }
    } catch (err) {
      alert('Failed to sync to AMS: ' + err.message);
    }
  },

  // ================= SETTINGS =================
  async loadSettings() {
    try {
      const res = await fetch('/api/settings');
      this.settings = await res.json();
      this.applySettingsToUI();
    } catch (err) {
      console.error('Failed to load settings:', err);
    }
  },

  applySettingsToUI() {
    if (!this.settings) return;
    const ai = this.settings.ai_eye || {};
    const provSelect = document.getElementById('aiProviderSelect');
    if (provSelect) provSelect.value = ai.provider || 'openai';

    const openAiKey = document.getElementById('openaiApiKey');
    if (openAiKey && ai.openai) openAiKey.value = ai.openai.api_key || '';

    const openAiModel = document.getElementById('openaiModel');
    if (openAiModel && ai.openai) openAiModel.value = ai.openai.model || 'gpt-4o-mini';

    const osBaseUrl = document.getElementById('osBaseUrl');
    if (osBaseUrl && ai.opensource) osBaseUrl.value = ai.opensource.base_url || 'http://localhost:11434/v1';

    const osModel = document.getElementById('osModel');
    if (osModel && ai.opensource) osModel.value = ai.opensource.model || 'llava';

    const vp = this.settings.video_processor || {};
    if (vp.logo_filename) {
      const preview = document.getElementById('logoPreviewText');
      if (preview) preview.innerText = `Current Logo: ${vp.logo_filename}`;
    }
  },

  // ================= CAMERA & TELEMETRY =================
  updateCameraSource() {
    const camImg = document.getElementById('liveCameraStream');
    if (camImg) {
      if (this.activePrinterId) {
        camImg.src = `/api/printers/${this.activePrinterId}/camera/stream?t=${Date.now()}`;
      } else {
        camImg.src = '/static/placeholder.jpg';
      }
    }
  },

  startPolling() {
    this.pollTelemetry();
    this.pollTimer = setInterval(() => this.pollTelemetry(), 2500);
  },

  async pollTelemetry() {
    if (!this.activePrinterId) return;
    try {
      const res = await fetch(`/api/printers/${this.activePrinterId}/status`);
      if (!res.ok) return;
      const data = await res.json();
      this.telemetry = data.telemetry || {};
      const bedState = data.bed_state || {};
      this.renderTelemetry(this.telemetry, bedState);
    } catch (err) {
      console.warn('Telemetry poll error:', err);
    }
  },

  renderTelemetry(t, bed) {
    // Basic status badge
    const stateBadge = document.getElementById('printerStateBadge');
    const state = (t.gcode_state || 'IDLE').toUpperCase();
    if (stateBadge) {
      stateBadge.textContent = state;
      stateBadge.className = `stat-pill-val state-${state.toLowerCase()}`;
    }

    const jobNameEl = document.getElementById('jobName');
    if (jobNameEl) jobNameEl.innerText = t.subtask_name || (state === 'IDLE' ? 'Printer Idle / Standby' : state);

    const progressPctEl = document.getElementById('progressPctText');
    if (progressPctEl) progressPctEl.innerText = `${t.progress_pct || 0}%`;

    const progressFill = document.getElementById('progressFillBar');
    if (progressFill) progressFill.style.width = `${t.progress_pct || 0}%`;

    const remainTimeEl = document.getElementById('remainingTimeText');
    if (remainTimeEl) {
      const mins = t.remaining_minutes || 0;
      remainTimeEl.innerText = mins > 60 ? `${Math.floor(mins / 60)}h ${mins % 60}m remaining` : `${mins}m remaining`;
    }

    const layerEl = document.getElementById('layerProgressText');
    if (layerEl) layerEl.innerText = `Layer: ${t.layer_num || 0} / ${t.total_layer_num || 0}`;

    // Light button in camera toolbar
    const lightBtn = document.getElementById('lightToggleBtn');
    if (lightBtn) {
      if (t.chamber_light) {
        lightBtn.style.color = 'var(--primary)';
        lightBtn.style.borderColor = 'var(--primary)';
      } else {
        lightBtn.style.color = '';
        lightBtn.style.borderColor = '';
      }
    }

    // Thermal readouts
    const nozTemp = document.getElementById('nozzleTemp');
    if (nozTemp) nozTemp.innerText = `${t.nozzle_temp || 0}°C`;
    const nozTarget = document.getElementById('nozzleTarget');
    if (nozTarget) nozTarget.innerText = `/ ${t.nozzle_target || 0}°C`;

    const bedTemp = document.getElementById('bedTemp');
    if (bedTemp) bedTemp.innerText = `${t.bed_temp || 0}°C`;
    const bedTarget = document.getElementById('bedTarget');
    if (bedTarget) bedTarget.innerText = `/ ${t.bed_target || 0}°C`;

    const chamberTemp = document.getElementById('chamberTemp');
    if (chamberTemp) chamberTemp.innerText = `${t.chamber_temp || 0}°C`;

    // Fans
    const fans = t.fans || {};
    const fanCool = document.getElementById('fanPartCool');
    if (fanCool) fanCool.innerText = `${fans.part_cooling_pct || 0}%`;
    const fanAux = document.getElementById('fanAux');
    if (fanAux) fanAux.innerText = `${fans.aux_pct || 0}%`;
    const fanChamber = document.getElementById('fanChamber');
    if (fanChamber) fanChamber.innerText = `${fans.chamber_pct || 0}%`;

    // Bed Position Tracker
    if (bed) {
      const pct = bed.bed_position_pct || 0;
      const z = bed.bed_position_z || 0.0;
      const bedVal = document.getElementById('bedSliderVal');
      if (bedVal) bedVal.innerText = `${pct}% (~${z}mm)`;
      const slider = document.getElementById('bedSlider');
      if (slider && document.activeElement !== slider) slider.value = pct;
    }

    // AMS Spools
    this.renderAMS(t.ams);
  },

  renderAMS(amsUnits) {
    const container = document.getElementById('amsSlotGrid');
    if (!container) return;
    if (!amsUnits || amsUnits.length === 0) {
      container.innerHTML = '<div style="color:var(--text-dim); font-size:0.8rem; grid-column:span 4; text-align:center; padding:0.5rem 0;">No AMS Connected / Standalone Spool</div>';
      return;
    }

    let html = '';
    amsUnits.forEach(unit => {
      (unit.trays || []).forEach((tray, idx) => {
        html += `
          <div class="ams-slot-card">
            <div class="ams-spool-circle" style="background-color: ${tray.color_hex};"></div>
            <div class="ams-slot-label">Slot ${idx + 1}</div>
            <div class="ams-slot-type">${tray.material} (${tray.remain_pct}%)</div>
          </div>
        `;
      });
    });
    container.innerHTML = html;
  },

  // ================= HARDWARE ACTIONS =================
  async sendAction(action, value = null, axis = null, dist = null) {
    if (!this.activePrinterId) return;
    try {
      const res = await fetch(`/api/printers/${this.activePrinterId}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, value, axis, dist })
      });
      const data = await res.json();
      if (data.ok) {
        this.pollTelemetry();
      }
    } catch (err) {
      console.error('Action failed:', err);
    }
  },

  toggleLight() {
    const isCurrentlyOn = this.telemetry.chamber_light || false;
    this.sendAction('light', !isCurrentlyOn);
  },

  sendGcode() {
    const input = document.getElementById('gcodeInput');
    if (!input || !input.value.trim()) return;
    this.sendAction('gcode', input.value.trim());
    input.value = '';
  },

  // ================= MODALS =================
  openModal(modalId) {
    const el = document.getElementById(modalId);
    if (el) el.classList.add('open');
  },

  closeModal(modalId) {
    const el = document.getElementById(modalId);
    if (el) el.classList.remove('open');
  },

  // ================= AI EYE GUARDIAN =================
  async runAIEyeInspection() {
    const resultBox = document.getElementById('aiInspectionResult');
    const btn = document.getElementById('runInspectBtn');
    if (btn) btn.disabled = true;
    if (resultBox) {
      resultBox.innerHTML = '<div style="color:var(--primary); font-weight:600;"><i class="ti ti-loader spin"></i> AI Guardian inspecting camera frame...</div>';
    }

    try {
      const res = await fetch(`/api/ai_eye/inspect?printer_id=${this.activePrinterId || ''}`, { method: 'POST' });
      const data = await res.json();
      const r = data.result || {};

      if (r.status === 'pro_locked') {
        this.openModal('proUpgradeModal');
        if (resultBox) resultBox.innerHTML = '';
        return;
      }

      let statusColor = 'var(--success)';
      let badgeLabel = '🟢 HEALTHY';
      if (r.status === 'warning') {
        statusColor = 'var(--warning)';
        badgeLabel = '🟡 WARNING';
      } else if (r.status === 'failure' || r.status === 'critical') {
        statusColor = 'var(--danger)';
        badgeLabel = '🔴 FAILURE DETECTED';
      }

      if (resultBox) {
        resultBox.innerHTML = `
          <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 1rem; margin-top: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
              <span style="font-weight: 800; color: ${statusColor}; font-size: 0.95rem;">${badgeLabel}</span>
              <span style="color: var(--text-dim); font-size: 0.75rem;">Confidence: ${r.confidence || 0}%</span>
            </div>
            <p style="font-size: 0.88rem; color: var(--text-main); margin-bottom: 0.5rem;">${r.summary || 'No issues detected.'}</p>
            <div style="font-size: 0.75rem; color: var(--text-muted);">
              Issue: <strong>${r.issue_type || 'none'}</strong> • Recommended Action: <strong>${r.recommended_action || 'continue'}</strong>
            </div>
          </div>
        `;
      }
      this.loadAIHistory();
    } catch (err) {
      if (resultBox) {
        resultBox.innerHTML = `<div style="color:var(--danger);">Inspection failed: ${err.message}</div>`;
      }
    } finally {
      if (btn) btn.disabled = false;
    }
  },

  async saveAISettings() {
    const provider = document.getElementById('aiProviderSelect').value;
    const openaiKey = document.getElementById('openaiApiKey').value.trim();
    const openaiModel = document.getElementById('openaiModel').value;
    const osBaseUrl = document.getElementById('osBaseUrl').value.trim();
    const osModel = document.getElementById('osModel').value.trim();

    try {
      const res = await fetch('/api/ai_eye/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider,
          enabled: true,
          openai_key: openaiKey,
          openai_model: openaiModel,
          opensource_base_url: osBaseUrl,
          opensource_model: osModel
        })
      });
      const data = await res.json();
      if (data.ok) {
        alert('AI Eye settings saved successfully!');
      }
    } catch (err) {
      alert('Error saving settings: ' + err.message);
    }
  },

  async loadAIHistory() {
    try {
      const res = await fetch('/api/ai_eye/history');
      const data = await res.json();
      const list = data.inspections || [];
      const container = document.getElementById('aiHistoryContainer');
      if (!container) return;

      if (list.length === 0) {
        container.innerHTML = '<div style="color:var(--text-dim); font-size:0.85rem;">No inspection records yet.</div>';
        return;
      }

      let html = '';
      list.slice(-10).reverse().forEach(item => {
        const timeStr = new Date(item.timestamp * 1000).toLocaleTimeString();
        let color = item.status === 'healthy' ? 'var(--success)' : (item.status === 'warning' ? 'var(--warning)' : 'var(--danger)');
        html += `
          <div style="display:flex; justify-content:space-between; align-items:center; padding: 0.6rem 0; border-bottom: 1px solid var(--border);">
            <div>
              <span style="font-weight:700; color:${color}; font-size:0.82rem;">${item.status.toUpperCase()}</span>
              <span style="color:var(--text-muted); font-size:0.8rem; margin-left:8px;">${item.summary}</span>
            </div>
            <span style="color:var(--text-dim); font-size:0.75rem;">${timeStr}</span>
          </div>
        `;
      });
      container.innerHTML = html;
    } catch (err) {
      console.warn('Could not load AI history:', err);
    }
  },

  // ================= VIDEO PROCESSOR =================
  async uploadLogo(file) {
    if (!file) return;
    const formData = new FormData();
    formData.append('logo', file);

    try {
      const res = await fetch('/api/videos/upload_logo', { method: 'POST', body: formData });
      const data = await res.json();
      if (data.ok) {
        const preview = document.getElementById('logoPreviewText');
        if (preview) preview.innerText = `Current Logo: ${data.filename}`;
        alert('Logo uploaded successfully!');
      }
    } catch (err) {
      alert('Logo upload failed: ' + err.message);
    }
  },

  async processDemoVideo() {
    const btn = document.getElementById('processDemoBtn');
    if (btn) btn.disabled = true;
    try {
      const res = await fetch('/api/videos/demo', { method: 'POST' });
      const data = await res.json();
      if (data.ok) {
        alert('Video processed with custom logo watermark!');
        this.loadVideos();
      } else {
        alert('Processing error: ' + (data.result?.error || 'Unknown'));
      }
    } catch (err) {
      alert('Error: ' + err.message);
    } finally {
      if (btn) btn.disabled = false;
    }
  },

  async loadVideos() {
    try {
      const res = await fetch('/api/videos/list');
      const data = await res.json();
      const list = data.timelapses || [];
      const container = document.getElementById('videosListContainer');
      if (!container) return;

      if (list.length === 0) {
        container.innerHTML = '<div style="color:var(--text-dim); font-size:0.85rem;">No processed videos yet. Click "Generate Demo Timelapse" to test logo watermark burning.</div>';
        return;
      }

      let html = '';
      list.forEach(v => {
        html += `
          <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 1rem; margin-bottom: 0.75rem; display: flex; justify-content: space-between; align-items: center;">
            <div>
              <div style="font-weight:700; font-size:0.9rem; color:var(--text-main);">${v.filename}</div>
              <div style="font-size:0.75rem; color:var(--text-muted);">Size: ${v.size_mb} MB • Watermark Logo: ${v.has_logo ? 'Applied' : 'None'} (${v.position})</div>
            </div>
            <a href="${v.download_url}" target="_blank" class="btn-primary" style="padding: 0.4rem 0.8rem; font-size: 0.8rem; text-decoration: none;">
              <i class="ti ti-download"></i> Download MP4
            </a>
          </div>
        `;
      });
      container.innerHTML = html;
    } catch (err) {
      console.warn('Could not load videos:', err);
    }
  },

  // ================= PRO LICENSING =================
  async submitProKey() {
    const key = document.getElementById('proLicenseKeyInput').value.trim();
    if (!key) return;

    try {
      const res = await fetch('/api/schedule/unlock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ license_key: key })
      });
      const data = await res.json();
      if (data.ok) {
        alert('Own your bambu Cloud Pro unlocked successfully!');
        this.closeModal('proUpgradeModal');
      } else {
        alert('Invalid key: ' + data.detail);
      }
    } catch (err) {
      alert('Upgrade error: ' + err.message);
    }
  }
};

document.addEventListener('DOMContentLoaded', () => App.init());

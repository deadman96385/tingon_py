const state = {
  profiles: [],
  positions: [],
  n2Modes: [],
  playbackBehaviors: [],
  mockMode: false,
  devices: [],
  session: { connected: false, device: null },
  editingSlot: null,
  selectedRangePreset: 1,
  lastProfile: null,
};

const els = {
  scanButton: document.getElementById("scan-button"),
  scanName: document.getElementById("scan-name"),
  scanTimeout: document.getElementById("scan-timeout"),
  deviceList: document.getElementById("device-list"),
  disconnectButton: document.getElementById("disconnect-button"),
  connectionSummary: document.getElementById("connection-summary"),
  eventState: document.getElementById("event-state"),
  activeProfile: document.getElementById("active-profile"),
  emptyHero: document.getElementById("empty-hero"),
  controlView: document.getElementById("control-view"),
  heroTitle: document.getElementById("hero-title"),
  heroSubtitle: document.getElementById("hero-subtitle"),
  heroHeading: document.getElementById("hero-heading"),
  heroDescription: document.getElementById("hero-description"),
  heroFigure: document.getElementById("hero-figure"),
  heroImage: document.getElementById("hero-image"),
  playToggleButton: document.getElementById("play-toggle-button"),
  refreshSessionButton: document.getElementById("refresh-session-button"),
  intimatePlaybackSection: document.getElementById("intimate-playback-section"),
  playbackGrid: document.getElementById("playback-grid"),
  intimateModeSection: document.getElementById("intimate-mode-section"),
  modeGrid: document.getElementById("mode-grid"),
  positionPanel: document.getElementById("position-panel"),
  positionGrid: document.getElementById("position-grid"),
  intimateManualSection: document.getElementById("intimate-manual-section"),
  motorControls: document.getElementById("motor-controls"),
  customSlots: document.getElementById("custom-slots"),
  intimateCustomSection: document.getElementById("intimate-custom-section"),
  n2ModePanel: document.getElementById("n2-mode-panel"),
  n2ModeGrid: document.getElementById("n2-mode-grid"),
  manualCopy: document.getElementById("manual-copy"),
  m2RangeSection: document.getElementById("m2-range-section"),
  rangeStart: document.getElementById("range-start"),
  rangeEnd: document.getElementById("range-end"),
  rangeStartValue: document.getElementById("range-start-value"),
  rangeEndValue: document.getElementById("range-end-value"),
  applyRangeButton: document.getElementById("apply-range-button"),
  saveRangeButton: document.getElementById("save-range-button"),
  rangePresetGrid: document.getElementById("range-preset-grid"),
  applianceControlsSection: document.getElementById("appliance-controls-section"),
  applianceControls: document.getElementById("appliance-controls"),
  applianceCopy: document.getElementById("appliance-copy"),
  applianceStatusSection: document.getElementById("appliance-status-section"),
  applianceStatus: document.getElementById("appliance-status"),
  customDialog: document.getElementById("custom-dialog"),
  customDialogTitle: document.getElementById("custom-dialog-title"),
  customDialogMeta: document.getElementById("custom-dialog-meta"),
  customStepList: document.getElementById("custom-step-list"),
  addStepButton: document.getElementById("add-step-button"),
  saveCustomButton: document.getElementById("save-custom-button"),
};

const HERO_ASSETS = {
  a1: "/static/assets/a1.png",
  n1: "/static/assets/n1.png",
  n2: "/static/assets/n2.png",
  m1: "/static/assets/m1.png",
  m2: "/static/assets/m2.png",
  "xpower.png": "/static/assets/xpower.png",
  "wanhe.png": "/static/assets/wanhe.png",
};

const PLAYBACK_ASSETS = {
  loop: "/static/assets/playback_loop.png",
  random: "/static/assets/playback_random.png",
  sequence: "/static/assets/playback_sequence.png",
};

const PLAYBACK_COPY = {
  loop: "Hold the selected preset until you change it.",
  random: "Switch to a different preset automatically every 30 seconds.",
  sequence: "Move through the preset list in order every 30 seconds.",
};

const STATUS_LABELS = {
  power: "Power",
  target_hum: "Target Humidity",
  drainage: "Drainage",
  dehumidification: "Dehumidification",
  error: "Fault",
  air_intake_temp: "Air Intake Temp",
  air_intake_hum: "Air Intake Humidity",
  air_outlet_temp: "Air Outlet Temp",
  air_outlet_hum: "Air Outlet Humidity",
  eva_temp: "Evaporator Temp",
  wind_speed: "Wind Speed",
  compressor_status: "Compressor",
  defrost: "Defrost",
  work_time: "Work Time",
  total_work_time: "Total Work Time",
  timer: "Timer",
  timer_entries: "Scheduled Timers",
  timer_remind_time: "Timer Reminder",
  setting_water_temp: "Target Water Temp",
  inlet_water_temp: "Inlet Water Temp",
  outlet_water_temp: "Outlet Water Temp",
  bathroom_mode: "Bathroom Mode",
  wind_status: "Fan",
  discharge: "Discharge",
  water_status: "Water Status",
  fire_status: "Fire Status",
  equipment_failure: "Equipment Failure",
  cruise_insulation_temp: "Cruise Insulation Temp",
  zero_cold_water_mode: "Zero Cold Water Mode",
  zero_cold_water: "Zero Cold Water",
  eco_cruise: "Eco Cruise",
  single_cruise: "Single Cruise",
  water_pressurization: "Water Pressurization",
  diandong: "Motorized Assist",
};

const ZERO_COLD_WATER_MODE_LABELS = {
  0: "Off",
  1: "On",
  3: "Enhanced",
};

const STATUS_FORMATTERS = {
  power: (value) => (value ? "On" : "Off"),
  drainage: (value) => (value ? "On" : "Off"),
  dehumidification: (value) => (value ? "On" : "Off"),
  compressor_status: (value) => (value ? "Running" : "Idle"),
  wind_status: (value) => (value ? "On" : "Off"),
  water_status: (value) => (value ? "Flowing" : "Idle"),
  fire_status: (value) => (value ? "Ignited" : "Off"),
  eco_cruise: (value) => (value ? "On" : "Off"),
  single_cruise: (value) => (value ? "On" : "Off"),
  water_pressurization: (value) => (value ? "On" : "Off"),
  diandong: (value) => (value ? "On" : "Off"),
  zero_cold_water: (value) => (value ? "On" : "Off"),
  zero_cold_water_mode: (value) => ZERO_COLD_WATER_MODE_LABELS[value] ?? String(value),
  defrost: (value) => (value ? "On" : "Off"),
  bathroom_mode: (value) => ({ 1: "Normal", 2: "Kitchen", 4: "Eco", 5: "Season" }[value] || String(value)),
  timer_entries: (value) => {
    if (!Array.isArray(value) || value.length === 0) return "None";
    return value
      .map((entry) => {
        const action = entry?.switch ? "On" : "Off";
        const enabled = entry?.status ? "" : " (disabled)";
        const hours = Number(entry?.hours || 0);
        return `${action} in ${hours}h${enabled}`;
      })
      .join(", ");
  },
};

const BATHROOM_MODE_CODES = {
  normal: 1,
  kitchen: 2,
  eco: 4,
  season: 5,
};

function showMessage(node, text) {
  node.classList.add("empty-state");
  node.textContent = text;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `Request failed: ${response.status}`);
  }
  return data;
}

function debounce(fn, delay = 180) {
  let handle = null;
  return (...args) => {
    if (handle !== null) {
      window.clearTimeout(handle);
    }
    handle = window.setTimeout(() => fn(...args), delay);
  };
}

function setEventState(text) {
  els.eventState.textContent = state.mockMode ? `${text} | mock` : text;
}

function currentDevice() {
  return state.session?.device || null;
}

function currentUi() {
  return currentDevice()?.profile_ui || null;
}

function currentStatus() {
  return currentDevice()?.status || {};
}

function currentControlState() {
  return currentDevice()?.control_state || {};
}

function slotLabel(slotId) {
  return `Slot ${slotId - 31}`;
}

function currentModeLabels() {
  return currentUi()?.mode_labels || [];
}

function currentModeCards() {
  return currentUi()?.mode_cards || [];
}

function modeLabel(mode) {
  return currentModeLabels()[mode - 1] || `Mode ${mode}`;
}

function durationOptions() {
  return [10, 20, 30, 40, 50, 60];
}

function customSummary(items) {
  if (!items || !items.length) {
    return "No saved steps yet.";
  }
  return items.map((item) => `${modeLabel(item.mode)} for ${item.sec}s`).join(" | ");
}

function renderDeviceList() {
  if (!state.devices.length) {
    showMessage(els.deviceList, "No devices found in the last scan.");
    return;
  }

  els.deviceList.classList.remove("empty-state");
  els.deviceList.innerHTML = "";
  const template = document.getElementById("device-card-template");

  for (const device of state.devices) {
    const node = template.content.firstElementChild.cloneNode(true);
    node.querySelector(".device-card-name").textContent = device.display_name || device.name;
    node.querySelector(".device-card-rssi").textContent = `RSSI ${device.rssi}`;
    const meta = [device.family, device.profile].filter(Boolean).join(" | ");
    node.querySelector(".device-card-meta").textContent = device.supported
      ? meta
      : device.profile
        ? `${meta} | unsupported in web UI`
        : "profile not inferred";
    node.querySelector(".device-card-address").textContent = device.address;
    if (!device.supported) {
      node.classList.add("unsupported");
      node.disabled = true;
    }
    node.addEventListener("click", () => connectToDevice(device));
    els.deviceList.appendChild(node);
  }
}

function figureClass(profile) {
  return profile ? `figure-${profile}` : "figure-idle";
}

function profileDescription(ui) {
  if (ui.family === "appliance") {
    if (ui.supports_humidity) {
      return "Set your ideal humidity, control the main functions, and keep an eye on current room conditions.";
    }
    return "Adjust water temperature, switch heating modes, and check the current heater status at a glance.";
  }
  if (ui.supports_custom_range) {
    return "Pick a pattern, fine-tune the speed, shape the active range, and choose where the motion is focused.";
  }
  if (ui.supports_n2_mode) {
    return "Switch between sensation styles and fine-tune each intensity level to match the moment.";
  }
  if (ui.supports_second_motor) {
    return "Explore built-in patterns, balance both motors, and save your favorite combinations.";
  }
  return "Choose a pattern, set the intensity you want, and save favorites for quick access.";
}

function heroAssetPath(ui) {
  return HERO_ASSETS[ui.hero_asset] || null;
}

function syncHero(ui, profile) {
  const assetPath = heroAssetPath(ui);
  els.heroFigure.className = `device-figure ${figureClass(profile)}`;
  if (assetPath) {
    els.heroFigure.classList.add("has-image");
    els.heroImage.src = assetPath;
    els.heroImage.alt = ui.display_name;
    els.heroImage.classList.remove("hidden");
  } else {
    els.heroFigure.classList.remove("has-image");
    els.heroImage.removeAttribute("src");
    els.heroImage.classList.add("hidden");
  }
}

function renderPlaybackGrid(ui, controlState) {
  els.intimatePlaybackSection.classList.toggle("hidden", !ui.supports_preset_mode);
  els.playbackGrid.innerHTML = "";
  if (!ui.supports_preset_mode) {
    return;
  }
  const active = controlState.playback_behavior || "loop";
  for (const behavior of ui.playback_behaviors || state.playbackBehaviors) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "playback-card";
    if (behavior === active) {
      button.classList.add("active");
    }
    button.innerHTML = `
      <img src="${PLAYBACK_ASSETS[behavior]}" alt="">
      <strong>${behavior.charAt(0).toUpperCase()}${behavior.slice(1)}</strong>
      <p>${PLAYBACK_COPY[behavior]}</p>
    `;
    button.addEventListener("click", async () => {
      await api("/api/intimate/playback-behavior", {
        method: "POST",
        body: JSON.stringify({ behavior }),
      }).then(updateSessionFromApi).catch(reportError);
    });
    els.playbackGrid.appendChild(button);
  }
}

function renderModeStrip(ui, status) {
  els.modeGrid.innerHTML = "";
  const cards = ui.mode_cards || currentModeCards();
  const midpoint = Math.ceil(cards.length / 2);
  const rows = [cards.slice(0, midpoint), cards.slice(midpoint)];
  const scroller = document.createElement("div");
  scroller.className = "mode-strip-scroll";

  rows.forEach((rowItems) => {
    if (!rowItems.length) {
      return;
    }
    const row = document.createElement("div");
    row.className = "mode-row";
    row.style.gridTemplateColumns = `repeat(${rowItems.length}, minmax(0, 1fr))`;
    rowItems.forEach((card) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "mode-card";
      if (status.mode === card.id) {
        button.classList.add("active");
      }
      const icon = status.mode === card.id ? card.active_icon : card.icon;
      button.innerHTML = `
        <img src="/static/assets/${icon}" alt="">
        <span>${card.label}</span>
      `;
      button.addEventListener("click", async () => {
        await api("/api/intimate/mode", {
          method: "POST",
          body: JSON.stringify({ mode: card.id }),
        }).then(updateSessionFromApi).catch(reportError);
      });
      row.appendChild(button);
    });
    scroller.appendChild(row);
  });
  els.modeGrid.appendChild(scroller);
}

function renderPositionPanel(enabled, activePosition) {
  els.positionPanel.classList.toggle("hidden", !enabled);
  els.positionGrid.innerHTML = "";
  if (!enabled) {
    return;
  }
  for (const position of ["front", "middle", "back", "all"]) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "selector-chip";
    if (activePosition === position) {
      button.classList.add("active");
    }
    button.textContent = position;
    button.addEventListener("click", async () => {
      await api("/api/intimate/position", {
        method: "POST",
        body: JSON.stringify({ position }),
      }).then(updateSessionFromApi).catch(reportError);
    });
    els.positionGrid.appendChild(button);
  }
}

function motorDefinitions(ui, status) {
  if (ui.profile === "m1") {
    return [
      { key: "motor1", label: "Motor 1", value: status.motor1 || 0 },
      { key: "motor2", label: "Motor 2", value: status.motor2 || 0 },
    ];
  }
  if (ui.profile === "n2") {
    return [
      { key: "motor1", label: "Vibration", value: status.motor1 || 0 },
      { key: "motor2", label: "Electric Shock", value: status.motor2 || 0 },
    ];
  }
  if (ui.profile === "m2") {
    return [{ key: "motor1", label: "Speed", value: status.motor1 || 0 }];
  }
  return [{ key: "motor1", label: "Motor 1", value: status.motor1 || 0 }];
}
function renderMotorControls(ui, status) {
  els.motorControls.innerHTML = "";
  const sliders = motorDefinitions(ui, status);
  const applyMotor = debounce(async () => {
    const values = Object.fromEntries(
      [...els.motorControls.querySelectorAll(".slider-input")].map((input) => [
        input.dataset.key,
        Number(input.value),
      ]),
    );
    await api("/api/intimate/motor", {
      method: "POST",
      body: JSON.stringify({
        motor1: values.motor1 || 0,
        motor2: Object.hasOwn(values, "motor2") ? values.motor2 : null,
      }),
    }).then(updateSessionFromApi).catch(reportError);
  }, 160);

  for (const slider of sliders) {
    const template = document.getElementById("slider-template");
    const node = template.content.firstElementChild.cloneNode(true);
    const label = node.querySelector(".slider-label");
    const value = node.querySelector(".slider-value");
    const input = node.querySelector(".slider-input");
    label.textContent = slider.label;
    value.textContent = slider.value;
    input.value = slider.value;
    input.dataset.key = slider.key;
    input.addEventListener("input", () => {
      value.textContent = input.value;
      applyMotor();
    });
    els.motorControls.appendChild(node);
  }

  if (ui.profile === "m2") {
    els.manualCopy.textContent = "Adjust speed and choose which section of the device is active.";
  } else if (ui.profile === "n2") {
    els.manualCopy.textContent = "Set vibration and electric shock levels separately.";
  } else if (ui.supports_second_motor) {
    els.manualCopy.textContent = "Set the intensity for both motors.";
  } else {
    els.manualCopy.textContent = "Set the intensity for the active motor.";
  }
}

function renderN2Modes(enabled, activeMode) {
  els.n2ModePanel.classList.toggle("hidden", !enabled);
  els.n2ModeGrid.innerHTML = "";
  if (!enabled) {
    return;
  }
  for (const modeName of state.n2Modes) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "selector-chip";
    if (activeMode === modeName) {
      button.classList.add("active");
    }
    button.textContent = modeName.replaceAll("_", " ");
    button.addEventListener("click", async () => {
      await api("/api/intimate/n2-mode", {
        method: "POST",
        body: JSON.stringify({ name: modeName }),
      }).then(updateSessionFromApi).catch(reportError);
    });
    button.title = "Local selector";
    els.n2ModeGrid.appendChild(button);
  }
}

function renderCustomSlots(ui, status) {
  els.customSlots.innerHTML = "";
  for (const slotId of [32, 33, 34]) {
    const items = status[`custom_${slotId}`] || [];
    const card = document.createElement("div");
    card.className = "custom-slot-card";
    if (status.custom_mode === slotId) {
      card.classList.add("active");
    }
    card.innerHTML = `
      <strong>${slotLabel(slotId)}</strong>
      <div class="custom-slot-summary">${customSummary(items)}</div>
    `;
    const actions = document.createElement("div");
    actions.className = "custom-slot-actions";
    const useButton = document.createElement("button");
    useButton.type = "button";
    useButton.className = "pill-button";
    useButton.textContent = "Use";
    useButton.disabled = !items.length;
    useButton.addEventListener("click", async () => {
      await api(`/api/intimate/custom/${slotId}/use`, {
        method: "POST",
      }).then(updateSessionFromApi).catch(reportError);
    });
    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.className = "ghost-button";
    editButton.textContent = items.length ? "Edit" : "Create";
    editButton.addEventListener("click", () => openCustomDialog(slotId, items, ui.custom_step_limit));
    actions.appendChild(useButton);
    actions.appendChild(editButton);
    card.appendChild(actions);
    els.customSlots.appendChild(card);
  }
}

function openCustomDialog(slotId, items, stepLimit) {
  state.editingSlot = {
    slotId,
    items: items.length ? items.map((item) => ({ ...item })) : [{ mode: 1, sec: 10 }],
    modeLabels: currentModeLabels(),
    stepLimit,
  };
  els.customDialogTitle.textContent = slotLabel(slotId);
  els.customDialogMeta.textContent = `Up to ${stepLimit} steps. Each step can run for 10, 20, 30, 40, 50, or 60 seconds.`;
  renderCustomEditor();
  els.customDialog.showModal();
}

function renderCustomEditor() {
  if (!state.editingSlot) {
    return;
  }
  els.customStepList.innerHTML = "";
  state.editingSlot.items.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "custom-step";
    const availableModes = state.editingSlot.modeLabels.length
      ? state.editingSlot.modeLabels
      : Array.from({ length: 12 }, (_value, offset) => `Mode ${offset + 1}`);
    const modeOptions = availableModes.map((label, offset) => {
      const modeValue = offset + 1;
      const selected = item.mode === modeValue ? " selected" : "";
      return `<option value="${modeValue}"${selected}>${modeValue}. ${label}</option>`;
    }).join("");
    const secOptions = durationOptions().map((seconds) => {
      const selected = item.sec === seconds ? " selected" : "";
      return `<option value="${seconds}"${selected}>${seconds} seconds</option>`;
    }).join("");
    row.innerHTML = `
      <div class="custom-step-field">
        <label>Pattern</label>
        <select aria-label="Pattern">${modeOptions}</select>
      </div>
      <div class="custom-step-field">
        <label>Duration</label>
        <select aria-label="Duration">${secOptions}</select>
      </div>
      <button type="button" aria-label="Remove step">x</button>
    `;
    const [modeWrap, secWrap, removeButton] = row.children;
    const modeInput = modeWrap.querySelector("select");
    const secInput = secWrap.querySelector("select");
    modeInput.addEventListener("input", () => {
      state.editingSlot.items[index].mode = Number(modeInput.value);
      renderCustomEditor();
    });
    secInput.addEventListener("input", () => {
      state.editingSlot.items[index].sec = Number(secInput.value);
      renderCustomEditor();
    });
    removeButton.addEventListener("click", () => {
      state.editingSlot.items.splice(index, 1);
      if (!state.editingSlot.items.length) {
        state.editingSlot.items.push({ mode: 1, sec: 10 });
      }
      renderCustomEditor();
    });
    const hint = document.createElement("div");
    hint.className = "custom-step-hint";
    hint.textContent = `Step ${index + 1} plays ${modeLabel(item.mode)} for ${item.sec} seconds.`;
    row.appendChild(hint);
    els.customStepList.appendChild(row);
  });
  els.addStepButton.disabled = state.editingSlot.items.length >= state.editingSlot.stepLimit;
}

async function saveCustomDialog() {
  if (!state.editingSlot) {
    return;
  }
  const body = {
    items: state.editingSlot.items.map((item) => ({
      mode: Number(item.mode),
      sec: Number(item.sec),
    })),
  };
  await api(`/api/intimate/custom/${state.editingSlot.slotId}`, {
    method: "POST",
    body: JSON.stringify(body),
  }).then(updateSessionFromApi).catch(reportError);
  els.customDialog.close();
}

function syncRangeInputs(status) {
  const start = Number(status.range_start ?? 0);
  const end = Number(status.range_end ?? 92);
  els.rangeStart.value = start;
  els.rangeEnd.value = end;
  els.rangeStartValue.textContent = start;
  els.rangeEndValue.textContent = end;
}

function renderRangePanel(ui, status, controlState) {
  els.m2RangeSection.classList.toggle("hidden", !ui.supports_custom_range);
  els.rangePresetGrid.innerHTML = "";
  if (!ui.supports_custom_range) {
    return;
  }
  syncRangeInputs(status);
  const presets = controlState.range_presets || [];
  presets.forEach((preset, index) => {
    const slot = index + 1;
    const card = document.createElement("div");
    card.className = "range-preset-card";
    if (slot === state.selectedRangePreset) {
      card.classList.add("selected");
    }
    if (slot === controlState.active_range_preset) {
      card.classList.add("active");
    }
    card.innerHTML = `
      <strong>Preset ${slot}</strong>
      <div class="range-preset-copy">${preset.start} to ${preset.end}</div>
    `;
    const actions = document.createElement("div");
    actions.className = "range-preset-actions";
    const loadButton = document.createElement("button");
    loadButton.type = "button";
    loadButton.className = "ghost-button";
    loadButton.textContent = "Load";
    loadButton.addEventListener("click", () => {
      state.selectedRangePreset = slot;
      els.rangeStart.value = preset.start;
      els.rangeEnd.value = preset.end;
      els.rangeStartValue.textContent = preset.start;
      els.rangeEndValue.textContent = preset.end;
      renderSession();
    });
    const useButton = document.createElement("button");
    useButton.type = "button";
    useButton.className = "pill-button";
    useButton.textContent = "Use";
    useButton.addEventListener("click", async () => {
      state.selectedRangePreset = slot;
      await api(`/api/intimate/range/preset/${slot}/use`, {
        method: "POST",
      }).then(updateSessionFromApi).catch(reportError);
    });
    actions.appendChild(loadButton);
    actions.appendChild(useButton);
    card.appendChild(actions);
    els.rangePresetGrid.appendChild(card);
  });
}

function renderToggleCard({ title, copy, active, onLabel = "Turn On", offLabel = "Turn Off", onClick }) {
  const card = document.createElement("div");
  card.className = "toggle-card";
  const button = document.createElement("button");
  button.type = "button";
  button.className = active ? "pill-button" : "ghost-button";
  button.textContent = active ? offLabel : onLabel;
  button.addEventListener("click", onClick);
  card.innerHTML = `<strong>${title}</strong><p>${copy}</p>`;
  card.appendChild(button);
  return card;
}

function renderSliderCard({ title, copy, value, min = 0, max = 100, onChange }) {
  const template = document.getElementById("slider-template");
  const node = template.content.firstElementChild.cloneNode(true);
  node.querySelector(".slider-label").textContent = title;
  node.querySelector(".slider-value").textContent = value;
  const input = node.querySelector(".slider-input");
  input.min = min;
  input.max = max;
  input.value = value;
  const copyNode = document.createElement("p");
  copyNode.textContent = copy;
  copyNode.style.margin = "8px 0 0";
  copyNode.style.color = "var(--muted)";
  copyNode.style.fontSize = "13px";
  const apply = debounce(async () => {
    await onChange(Number(input.value));
  }, 160);
  input.addEventListener("input", () => {
    node.querySelector(".slider-value").textContent = input.value;
    apply();
  });
  node.appendChild(copyNode);
  return node;
}

function renderModeButtonGroup(options, activeMode, onSelect) {
  const wrap = document.createElement("div");
  wrap.className = "mode-button-group";
  wrap.innerHTML = `<strong>Bathroom Mode</strong><p>Select the Wanhe heater operating mode.</p>`;
  const grid = document.createElement("div");
  grid.className = "mode-button-grid";
  for (const option of options) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = activeMode === BATHROOM_MODE_CODES[option.value] ? "pill-button" : "ghost-button";
    button.textContent = option.label;
    button.addEventListener("click", () => onSelect(option.value));
    grid.appendChild(button);
  }
  wrap.appendChild(grid);
  return wrap;
}

function renderChoiceCard({ title, copy, options, activeValue, onSelect }) {
  const wrap = document.createElement("div");
  wrap.className = "mode-button-group";
  wrap.innerHTML = `<strong>${title}</strong><p>${copy}</p>`;
  const grid = document.createElement("div");
  grid.className = "mode-button-grid";
  for (const option of options) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = activeValue === option.value ? "pill-button" : "ghost-button";
    button.textContent = option.label;
    button.addEventListener("click", () => onSelect(option.value));
    grid.appendChild(button);
  }
  wrap.appendChild(grid);
  return wrap;
}

function renderProvisionCard(ui, { ssidValue = "", passwordValue = "", urlValue = "" } = {}) {
  const card = document.createElement("div");
  card.className = "toggle-card provision-card";
  card.innerHTML = `
    <strong>WiFi Provisioning</strong>
    <p>Send WiFi credentials to the device over BLE so it can reach the network.</p>
  `;
  const form = document.createElement("div");
  form.className = "provision-form";
  form.innerHTML = `
    <label class="field"><span>SSID</span><input type="text" class="provision-ssid" placeholder="Network name"></label>
    <label class="field"><span>Password</span><input type="password" class="provision-password" placeholder="Password"></label>
    <label class="field"><span>Config URL (optional)</span><input type="text" class="provision-url" placeholder=""></label>
  `;
  form.querySelector(".provision-ssid").value = ssidValue;
  form.querySelector(".provision-password").value = passwordValue;
  form.querySelector(".provision-url").value = urlValue;
  const submit = document.createElement("button");
  submit.type = "button";
  submit.className = "pill-button";
  submit.textContent = "Send Credentials";
  const status = document.createElement("p");
  status.className = "provision-status";
  status.style.margin = "8px 0 0";
  status.style.color = "var(--muted)";
  status.style.fontSize = "13px";
  submit.addEventListener("click", async () => {
    const ssid = form.querySelector(".provision-ssid").value.trim();
    const password = form.querySelector(".provision-password").value;
    const configUrl = form.querySelector(".provision-url").value.trim();
    if (!ssid) {
      status.textContent = "SSID is required.";
      return;
    }
    submit.disabled = true;
    status.textContent = "Sending...";
    try {
      const result = await api("/api/appliance/provision", {
        method: "POST",
        body: JSON.stringify({ ssid, password, config_url: configUrl, encrypt: true }),
      });
      status.textContent = result?.mock
        ? `Mock provisioning accepted for ${ssid}.`
        : `Credentials sent to ${ssid}.`;
    } catch (err) {
      status.textContent = err?.message || "Provisioning failed.";
    } finally {
      submit.disabled = false;
    }
  });
  card.appendChild(form);
  card.appendChild(submit);
  card.appendChild(status);
  return card;
}

function renderTimerCard(status) {
  const card = document.createElement("div");
  card.className = "toggle-card provision-card";
  card.innerHTML = `
    <strong>Timers</strong>
    <p>Schedule the dehumidifier to turn on or off after a delay (1-23 hours).</p>
  `;
  const list = document.createElement("div");
  list.className = "timer-list";
  const rawEntries = Array.isArray(status.timer_entries) ? status.timer_entries : [];
  const entries = rawEntries.map((entry) => ({
    switch: entry?.switch ? 1 : 0,
    status: entry?.status ? 1 : 0,
    hours: Math.max(1, Math.min(23, Number(entry?.hours || 1))),
  }));

  const renderList = () => {
    list.innerHTML = "";
    if (entries.length === 0) {
      const empty = document.createElement("p");
      empty.className = "timer-empty";
      empty.style.color = "var(--muted)";
      empty.style.fontSize = "13px";
      empty.textContent = "No timers scheduled.";
      list.appendChild(empty);
      return;
    }
    entries.forEach((entry, index) => {
      const row = document.createElement("div");
      row.className = "timer-row";
      row.innerHTML = `
        <label class="field">
          <span>Action</span>
          <select class="timer-switch">
            <option value="1">Turn On</option>
            <option value="0">Turn Off</option>
          </select>
        </label>
        <label class="field">
          <span>In (hours)</span>
          <input type="number" class="timer-hours" min="1" max="23" step="1">
        </label>
        <label class="field timer-enabled-field">
          <span>Enabled</span>
          <input type="checkbox" class="timer-enabled">
        </label>
        <button type="button" class="ghost-button timer-remove">Remove</button>
      `;
      row.querySelector(".timer-switch").value = String(entry.switch);
      row.querySelector(".timer-hours").value = String(entry.hours);
      row.querySelector(".timer-enabled").checked = Boolean(entry.status);
      row.querySelector(".timer-switch").addEventListener("change", (event) => {
        entries[index].switch = Number(event.target.value);
      });
      row.querySelector(".timer-hours").addEventListener("change", (event) => {
        const raw = Number(event.target.value);
        entries[index].hours = Math.max(1, Math.min(23, Number.isFinite(raw) ? raw : 1));
        event.target.value = String(entries[index].hours);
      });
      row.querySelector(".timer-enabled").addEventListener("change", (event) => {
        entries[index].status = event.target.checked ? 1 : 0;
      });
      row.querySelector(".timer-remove").addEventListener("click", () => {
        entries.splice(index, 1);
        renderList();
      });
      list.appendChild(row);
    });
  };
  renderList();

  const buttonRow = document.createElement("div");
  buttonRow.className = "timer-buttons";
  buttonRow.style.display = "flex";
  buttonRow.style.gap = "8px";
  buttonRow.style.marginTop = "10px";

  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.className = "ghost-button";
  addBtn.textContent = "Add Timer";
  addBtn.addEventListener("click", () => {
    if (entries.length >= 6) {
      statusLine.textContent = "Maximum of 6 timer entries.";
      return;
    }
    entries.push({ switch: 1, status: 1, hours: 1 });
    renderList();
  });

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "pill-button";
  saveBtn.textContent = "Save Timers";

  const statusLine = document.createElement("p");
  statusLine.className = "timer-status";
  statusLine.style.margin = "8px 0 0";
  statusLine.style.color = "var(--muted)";
  statusLine.style.fontSize = "13px";

  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    statusLine.textContent = "Saving...";
    try {
      await api("/api/appliance/timer", {
        method: "POST",
        body: JSON.stringify({ entries }),
      }).then(updateSessionFromApi);
      statusLine.textContent = entries.length === 0
        ? "Cleared all timers."
        : `Saved ${entries.length} timer${entries.length === 1 ? "" : "s"}.`;
    } catch (err) {
      statusLine.textContent = err?.message || "Failed to save timers.";
    } finally {
      saveBtn.disabled = false;
    }
  });

  buttonRow.appendChild(addBtn);
  buttonRow.appendChild(saveBtn);
  card.appendChild(list);
  card.appendChild(buttonRow);
  card.appendChild(statusLine);
  return card;
}

function formatStatusValue(key, value) {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  if (STATUS_FORMATTERS[key]) {
    return STATUS_FORMATTERS[key](value);
  }
  if (key.includes("hum")) {
    return `${value}%`;
  }
  if (key.includes("temp")) {
    return `${value}C`;
  }
  if (key.includes("time")) {
    return `${value} min`;
  }
  if (typeof value === "boolean") {
    return value ? "On" : "Off";
  }
  return String(value);
}

function humanizeStatusKey(key) {
  return STATUS_LABELS[key] || key.replaceAll("_", " ");
}

function renderStatusGrid(status) {
  els.applianceStatus.innerHTML = "";
  const entries = Object.entries(status).filter(([key]) => !key.startsWith("custom_"));
  if (!entries.length) {
    showMessage(els.applianceStatus, "No appliance status values have been read yet.");
    return;
  }
  els.applianceStatus.classList.remove("empty-state");
  for (const [key, value] of entries) {
    const card = document.createElement("div");
    card.className = "status-card";
    card.innerHTML = `
      <strong>${humanizeStatusKey(key)}</strong>
      <div class="status-card-value">${formatStatusValue(key, value)}</div>
    `;
    els.applianceStatus.appendChild(card);
  }
}

function renderApplianceControls(ui, status) {
  els.applianceControls.innerHTML = "";
  els.applianceCopy.textContent = ui.supports_humidity
    ? "Use the main controls to manage power, humidity, drainage, and dehumidification."
    : "Use the main controls to manage power, water temperature, and heater mode.";

  const isOn = Boolean(status.power);
  els.applianceControls.appendChild(renderToggleCard({
    title: "Power",
    copy: "Toggle the appliance power state.",
    active: isOn,
    onClick: async () => api("/api/appliance/power", {
      method: "POST",
      body: JSON.stringify({ on: !isOn }),
    }).then(updateSessionFromApi).catch(reportError),
  }));

  if (ui.supports_humidity) {
    els.applianceControls.appendChild(renderSliderCard({
      title: "Target Humidity",
      copy: "Adjust the requested humidity target for the dehumidifier.",
      value: Number(status.target_hum || 0),
      min: 0,
      max: 100,
      onChange: async (percent) => api("/api/appliance/humidity", {
        method: "POST",
        body: JSON.stringify({ percent }),
      }).then(updateSessionFromApi).catch(reportError),
    }));
  }

  if (ui.supports_drainage) {
    const drainageOn = Boolean(status.drainage);
    els.applianceControls.appendChild(renderToggleCard({
      title: "Drainage",
      copy: "Enable or disable drainage mode.",
      active: drainageOn,
      onClick: async () => api("/api/appliance/drainage", {
        method: "POST",
        body: JSON.stringify({ on: !drainageOn }),
      }).then(updateSessionFromApi).catch(reportError),
    }));
  }

  if (ui.supports_dehumidification) {
    const dehumOn = Boolean(status.dehumidification);
    els.applianceControls.appendChild(renderToggleCard({
      title: "Dehumidification",
      copy: "Enable or disable active dehumidification.",
      active: dehumOn,
      onClick: async () => api("/api/appliance/dehumidification", {
        method: "POST",
        body: JSON.stringify({ on: !dehumOn }),
      }).then(updateSessionFromApi).catch(reportError),
    }));
  }

  if (ui.supports_water_temperature) {
    const temp = Number(status.setting_water_temp ?? status.outlet_water_temp ?? 0);
    els.applianceControls.appendChild(renderSliderCard({
      title: "Water Temperature",
      copy: "Adjust the requested water temperature setpoint.",
      value: temp,
      min: 0,
      max: 100,
      onChange: async (nextTemp) => api("/api/appliance/water-temperature", {
        method: "POST",
        body: JSON.stringify({ temp: nextTemp }),
      }).then(updateSessionFromApi).catch(reportError),
    }));
  }

  if (ui.supports_bathroom_mode) {
    els.applianceControls.appendChild(renderModeButtonGroup(
      ui.mode_options || [],
      status.bathroom_mode,
      async (name) => api("/api/appliance/bathroom-mode", {
        method: "POST",
        body: JSON.stringify({ name }),
      }).then(updateSessionFromApi).catch(reportError),
    ));
  }

  if (ui.supports_cruise_insulation_temp) {
    els.applianceControls.appendChild(renderSliderCard({
      title: "Cruise Insulation Temp",
      copy: "Hold-temperature setpoint for cruise insulation mode.",
      value: Number(status.cruise_insulation_temp || 0),
      min: 0,
      max: 100,
      onChange: async (temp) => api("/api/appliance/cruise-temp", {
        method: "POST",
        body: JSON.stringify({ temp }),
      }).then(updateSessionFromApi).catch(reportError),
    }));
  }

  if (ui.supports_zero_cold_water_mode) {
    els.applianceControls.appendChild(renderChoiceCard({
      title: "Zero Cold Water Mode",
      copy: "Pre-circulate hot water so the tap runs warm immediately.",
      options: [
        { value: 0, label: "Off" },
        { value: 1, label: "On" },
        { value: 3, label: "Enhanced" },
      ],
      activeValue: Number(status.zero_cold_water_mode ?? 0),
      onSelect: async (mode) => api("/api/appliance/zero-cold-water-mode", {
        method: "POST",
        body: JSON.stringify({ mode }),
      }).then(updateSessionFromApi).catch(reportError),
    }));
  }

  if (ui.supports_eco_cruise) {
    const ecoOn = Boolean(status.eco_cruise);
    els.applianceControls.appendChild(renderToggleCard({
      title: "Eco Cruise",
      copy: "Energy-saving cruise insulation schedule.",
      active: ecoOn,
      onClick: async () => api("/api/appliance/eco-cruise", {
        method: "POST",
        body: JSON.stringify({ on: !ecoOn }),
      }).then(updateSessionFromApi).catch(reportError),
    }));
  }

  if (ui.supports_water_pressurization) {
    const pressureOn = Boolean(status.water_pressurization);
    els.applianceControls.appendChild(renderToggleCard({
      title: "Water Pressurization",
      copy: "Boost outgoing water pressure when supply is low.",
      active: pressureOn,
      onClick: async () => api("/api/appliance/water-pressurization", {
        method: "POST",
        body: JSON.stringify({ on: !pressureOn }),
      }).then(updateSessionFromApi).catch(reportError),
    }));
  }

  if (ui.supports_single_cruise) {
    const singleOn = Boolean(status.single_cruise);
    els.applianceControls.appendChild(renderToggleCard({
      title: "Single Cruise",
      copy: "Maintain one cruise insulation cycle while the heater runs.",
      active: singleOn,
      onClick: async () => api("/api/appliance/single-cruise", {
        method: "POST",
        body: JSON.stringify({ on: !singleOn }),
      }).then(updateSessionFromApi).catch(reportError),
    }));
  }

  if (ui.supports_zero_cold_water) {
    const zcwOn = Boolean(status.zero_cold_water);
    els.applianceControls.appendChild(renderToggleCard({
      title: "Zero Cold Water",
      copy: "Trigger a single zero-cold-water circulation burst.",
      active: zcwOn,
      onClick: async () => api("/api/appliance/zero-cold-water", {
        method: "POST",
        body: JSON.stringify({ on: !zcwOn }),
      }).then(updateSessionFromApi).catch(reportError),
    }));
  }

  if (ui.supports_diandong) {
    const jogOn = Boolean(status.diandong);
    els.applianceControls.appendChild(renderToggleCard({
      title: "Jogging+",
      copy: "Open the faucet and close it within 3 seconds to trigger zero cold water once.",
      active: jogOn,
      onClick: async () => api("/api/appliance/diandong", {
        method: "POST",
        body: JSON.stringify({ on: !jogOn }),
      }).then(updateSessionFromApi).catch(reportError),
    }));
  }

  if (ui.supports_timer) {
    els.applianceControls.appendChild(renderTimerCard(status));
  }

  if (ui.supports_provision) {
    els.applianceControls.appendChild(renderProvisionCard(ui));
  }
}

function renderIntimateView(ui, status, controlState) {
  els.playToggleButton.classList.remove("hidden");
  els.intimatePlaybackSection.classList.remove("hidden");
  els.intimateModeSection.classList.remove("hidden");
  els.intimateManualSection.classList.remove("hidden");
  els.intimateCustomSection.classList.remove("hidden");
  els.applianceControlsSection.classList.add("hidden");
  els.applianceStatusSection.classList.add("hidden");
  renderPlaybackGrid(ui, controlState);
  renderModeStrip(ui, status);
  renderPositionPanel(ui.supports_position, status.position || "all");
  renderMotorControls(ui, status);
  renderRangePanel(ui, status, controlState);
  renderN2Modes(ui.supports_n2_mode, status.n2_mode || "vibration");
  renderCustomSlots(ui, status);
}

function renderApplianceView(ui, status) {
  els.playToggleButton.classList.add("hidden");
  els.n2ModePanel.classList.add("hidden");
  els.intimatePlaybackSection.classList.add("hidden");
  els.intimateModeSection.classList.add("hidden");
  els.intimateManualSection.classList.add("hidden");
  els.intimateCustomSection.classList.add("hidden");
  els.m2RangeSection.classList.add("hidden");
  els.applianceControlsSection.classList.remove("hidden");
  els.applianceStatusSection.classList.remove("hidden");
  renderApplianceControls(ui, status);
  renderStatusGrid(status);
}

function renderSession() {
  const session = state.session;
  if (!session.connected || !session.device) {
    els.emptyHero.classList.remove("hidden");
    els.controlView.classList.add("hidden");
    els.connectionSummary.textContent = "No active device session.";
    els.activeProfile.textContent = "None";
    return;
  }

  const { device } = session;
  const ui = device.profile_ui;
  const status = device.status || {};
  const controlState = device.control_state || {};
  const name = device.name || ui.display_name;

  els.emptyHero.classList.add("hidden");
  els.controlView.classList.remove("hidden");
  els.connectionSummary.textContent = `${name} | ${device.address}`;
  els.activeProfile.textContent = ui.display_name;
  els.heroTitle.textContent = ui.display_name;
  els.heroSubtitle.textContent = `${name} | ${device.address}`;
  els.heroHeading.textContent = ui.display_name;
  els.heroDescription.textContent = profileDescription(ui);
  syncHero(ui, device.profile);
  els.playToggleButton.textContent = status.play ? "Stop" : "Play";

  if (ui.family === "appliance") {
    renderApplianceView(ui, status);
    return;
  }
  renderIntimateView(ui, status, controlState);
}

function updateSessionFromApi(payload) {
  const nextProfile = payload?.device?.profile || null;
  const nextActivePreset = payload?.device?.control_state?.active_range_preset || 1;
  if (nextProfile !== state.lastProfile) {
    state.selectedRangePreset = nextActivePreset;
    state.lastProfile = nextProfile;
  } else if (payload?.device?.profile === "m2" && !state.selectedRangePreset) {
    state.selectedRangePreset = nextActivePreset;
  }
  state.session = payload;
  renderSession();
}

function reportError(error) {
  console.error(error);
  setEventState(error.message);
}

async function connectToDevice(device) {
  setEventState("Connecting...");
  await api("/api/connect", {
    method: "POST",
    body: JSON.stringify({ address: device.address, profile: device.profile }),
  }).then(updateSessionFromApi).catch(reportError);
}

async function loadProfiles() {
  const data = await api("/api/profiles");
  state.profiles = data.profiles;
  state.positions = data.positions;
  state.n2Modes = data.n2_modes;
  state.playbackBehaviors = data.playback_behaviors || [];
  state.mockMode = Boolean(data.mock_mode);
}

async function loadSession() {
  updateSessionFromApi(await api("/api/session"));
}

async function performScan() {
  setEventState("Scanning...");
  const data = await api("/api/scan", {
    method: "POST",
    body: JSON.stringify({
      timeout: Number(els.scanTimeout.value || 6),
      name: els.scanName.value || "",
    }),
  });
  state.devices = data.devices;
  renderDeviceList();
  setEventState("Scan complete");
}

function connectEvents() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocol}://${location.host}/api/events`);
  ws.addEventListener("open", () => setEventState("Live"));
  ws.addEventListener("close", () => {
    setEventState("Reconnecting...");
    window.setTimeout(connectEvents, 1500);
  });
  ws.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.event === "session") {
      updateSessionFromApi(message.payload);
    }
    if (message.event === "scan_started") {
      setEventState("Scanning...");
    }
    if (message.event === "scan_completed") {
      setEventState("Live");
    }
  });
}

function bindEvents() {
  els.scanButton.addEventListener("click", () => performScan().catch(reportError));
  els.disconnectButton.addEventListener("click", () => {
    api("/api/disconnect", { method: "POST" }).then(updateSessionFromApi).catch(reportError);
  });
  els.playToggleButton.addEventListener("click", () => {
    const device = currentDevice();
    if (!device || device.profile_ui.family !== "intimate") {
      return;
    }
    const status = currentStatus();
    api("/api/intimate/play", {
      method: "POST",
      body: JSON.stringify({
        play: !status.play,
        mode: status.mode > 0 ? status.mode : 1,
      }),
    }).then(updateSessionFromApi).catch(reportError);
  });
  els.refreshSessionButton.addEventListener("click", () => {
    const device = currentDevice();
    if (!device) {
      return;
    }
    const path = device.profile_ui.family === "appliance" ? "/api/appliance/status" : "/api/intimate/custom";
    api(path).then(updateSessionFromApi).catch(reportError);
  });
  els.addStepButton.addEventListener("click", () => {
    if (!state.editingSlot || state.editingSlot.items.length >= state.editingSlot.stepLimit) {
      return;
    }
    state.editingSlot.items.push({ mode: 1, sec: 10 });
    renderCustomEditor();
  });
  els.saveCustomButton.addEventListener("click", () => {
    saveCustomDialog().catch(reportError);
  });
  els.rangeStart.addEventListener("input", () => {
    const start = Number(els.rangeStart.value);
    const end = Number(els.rangeEnd.value);
    if (start > end) {
      els.rangeEnd.value = start;
      els.rangeEndValue.textContent = start;
    }
    els.rangeStartValue.textContent = els.rangeStart.value;
  });
  els.rangeEnd.addEventListener("input", () => {
    const start = Number(els.rangeStart.value);
    const end = Number(els.rangeEnd.value);
    if (end < start) {
      els.rangeStart.value = end;
      els.rangeStartValue.textContent = end;
    }
    els.rangeEndValue.textContent = els.rangeEnd.value;
  });
  els.applyRangeButton.addEventListener("click", () => {
    api("/api/intimate/range", {
      method: "POST",
      body: JSON.stringify({
        start: Number(els.rangeStart.value),
        end: Number(els.rangeEnd.value),
      }),
    }).then(updateSessionFromApi).catch(reportError);
  });
  els.saveRangeButton.addEventListener("click", () => {
    api(`/api/intimate/range/preset/${state.selectedRangePreset}/save`, {
      method: "POST",
      body: JSON.stringify({
        start: Number(els.rangeStart.value),
        end: Number(els.rangeEnd.value),
      }),
    }).then(updateSessionFromApi).catch(reportError);
  });
}

async function init() {
  bindEvents();
  await loadProfiles();
  await loadSession();
  renderDeviceList();
  connectEvents();
}

init().catch(reportError);

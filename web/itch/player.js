/*
 * Quintra browser player
 * Copyright 2026 Quintra contributors
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This file forms one browser program with WasmBoy and is distributed under
 * GPL-3.0-or-later. The independently compiled Quintra ROM is cartridge data.
 */
(() => {
  "use strict";

  const api = window.WasmBoy && window.WasmBoy.WasmBoy;
  const canvas = document.querySelector("#game");
  const shell = document.querySelector("#player-shell");
  const launch = document.querySelector("#launch");
  const status = document.querySelector("#status");
  const mute = document.querySelector("#mute");
  const fullscreen = document.querySelector("#fullscreen");
  const exportSave = document.querySelector("#export-save");
  const importSave = document.querySelector("#import-save");
  const saveFile = document.querySelector("#save-file");
  const soundBanner = document.querySelector("#sound-banner");
  const gamepadStatus = document.querySelector("#gamepad-status");
  const touchControls = document.querySelector(".touch-controls");
  const touchButtons = Array.from(document.querySelectorAll("[data-touch-input]"));
  const swapAbButton = document.querySelector("#swap-ab");
  const displayModeButton = document.querySelector("#display-mode");
  const settingsButton = document.querySelector("#settings");
  const settingsPanel = document.querySelector("#settings-panel");
  const settingsClose = document.querySelector("#settings-close");
  const settingsStatus = document.querySelector("#settings-status");
  const recalibrateButton = document.querySelector("#recalibrate");
  const resetMappingButton = document.querySelector("#reset-mapping");
  const displayChoiceButtons = Array.from(document.querySelectorAll("[data-display-mode]") || []);
  const calibrationOverlay = document.querySelector("#pad-calibration");
  const calibrationTitle = document.querySelector("#pad-calibration-title");
  const calibrationDetail = document.querySelector("#pad-calibration-detail");
  const calibrationSkip = document.querySelector("#pad-calibration-skip");
  const stage = document.querySelector("#player-stage");
  const screenWrap = document.querySelector("#screen-wrap");
  const saveSize = 32 * 1024;
  const handledKeys = new Set([
    "ArrowUp", "ArrowRight", "ArrowDown", "ArrowLeft",
    "KeyW", "KeyA", "KeyS", "KeyD", "KeyX", "KeyZ",
    "Enter", "ShiftLeft", "ShiftRight", "Backspace"
  ]);

  let ready = false;
  let started = false;
  let muted = false;
  let saveBusy = false;
  let activeGamepadIndex = null;
  let gamepadStatusText = "";
  let resumeAfterVisibility = false;
  let visibilityTask = Promise.resolve();
  let gamepadPollHandle = 0;
  const gamepadButtonsDown = new Map();
  // Standard-mapping indices: 0/1 are the two lower face buttons (Nintendo
  // pads report A as 1, Xbox-style pads as 0) and 9 is Start/Plus.
  const launchGamepadButtons = [0, 1, 9];
  const swapAbStorageKey = "quintra.swapAB";
  const pageParams = readPageParams();
  let swapAB = readSwapAB();
  let padDebugElement = null;
  let padDebugGamepad = null;
  let padDebugMapped = null;
  const displayModes = ["fit", "integer", "stretch"];
  const displayModeLabels = { fit: "Fit", integer: "Integer", stretch: "Stretch" };
  const displayStorageKey = "quintra.display";
  let displayMode = readDisplayMode();
  let displayLayoutHandle = 0;
  let lastFit = { mode: "", scale: 0, width: 0, height: 0, stageWidth: 0, stageHeight: 0, layout: "" };
  const viewportEvents = { resize: 0, orientationchange: 0, visualViewport: 0 };
  // Per-controller calibration ("press the button labelled A"), keyed by
  // gamepad.id: { a, b } raw indices, or { skipped: true }.
  const padMapStorageKey = "quintra.padmap.v1";
  const calibrationTimeoutMs = 20000;
  const calibrationPrompted = new Set();
  let padMap = readPadMap();
  let calibration = null;
  let settingsOpen = false;
  let settingsFocus = 0;
  let overlayPaused = false;
  let uiTimer = 0;
  let uiPadPrevious = {};
  let chordSince = 0;
  let homeWasDown = false;
  let suppressPadUntilRelease = false;
  let lastPolledPads = [];
  const touchPointers = new Map();
  const touchState = {
    UP: false, RIGHT: false, DOWN: false, LEFT: false,
    A: false, B: false, SELECT: false, START: false
  };

  function refreshTouchState() {
    const activeTouches = Array.from(touchPointers.values());
    Object.keys(touchState).forEach(input => {
      touchState[input] = activeTouches.some(touch => touch.inputs.includes(input));
    });
    touchButtons.forEach(button => {
      button.classList.toggle("is-pressed", activeTouches.some(touch => touch.button === button));
    });
  }

  function pressTouchButton(button, event) {
    event.preventDefault();
    const inputs = button.dataset.touchInput.split(" ");
    touchPointers.set(event.pointerId, { button, inputs });
    refreshTouchState();
    if (typeof button.setPointerCapture === "function") {
      try {
        button.setPointerCapture(event.pointerId);
      } catch (error) {
        console.warn("Could not capture touch pointer", error);
      }
    }
  }

  function releaseTouchPointer(event) {
    touchPointers.delete(event.pointerId);
    refreshTouchState();
  }

  function clearTouchPointers() {
    if (!touchPointers.size) return;
    touchPointers.clear();
    refreshTouchState();
  }

  touchButtons.forEach(button => {
    button.addEventListener("pointerdown", event => pressTouchButton(button, event), { passive: false });
    button.addEventListener("pointerup", releaseTouchPointer);
    button.addEventListener("pointercancel", releaseTouchPointer);
    button.addEventListener("lostpointercapture", releaseTouchPointer);
    button.addEventListener("contextmenu", event => event.preventDefault());
  });
  document.addEventListener("pointerup", releaseTouchPointer);
  document.addEventListener("pointercancel", releaseTouchPointer);
  window.addEventListener("blur", clearTouchPointers);
  window.addEventListener("pagehide", clearTouchPointers);

  function readPageParams() {
    try {
      const search = typeof location !== "undefined" && location ? location.search : "";
      if (typeof URLSearchParams === "function") return new URLSearchParams(search || "");
    } catch (error) { /* fall through */ }
    return { get: () => null };
  }

  function storage() {
    try {
      return typeof localStorage !== "undefined" ? localStorage : null;
    } catch (error) {
      return null;
    }
  }

  // Manual A/B swap fallback: ?swapab=1 turns it on, ?swapab=0 off; either
  // choice (and the toolbar toggle) persists in localStorage.
  function readSwapAB() {
    const store = storage();
    const param = pageParams.get("swapab");
    if (param === "1" || param === "0") {
      try { if (store) store.setItem(swapAbStorageKey, param); } catch (error) { /* private mode */ }
      return param === "1";
    }
    try { return !!store && store.getItem(swapAbStorageKey) === "1"; } catch (error) { return false; }
  }

  function setSwapAB(value) {
    swapAB = !!value;
    const store = storage();
    try { if (store) store.setItem(swapAbStorageKey, swapAB ? "1" : "0"); } catch (error) { /* private mode */ }
    refreshSwapAbButton();
    gamepadStatusText = "";
  }

  function refreshSwapAbButton() {
    if (!swapAbButton) return;
    swapAbButton.setAttribute("aria-pressed", swapAB ? "true" : "false");
    swapAbButton.textContent = swapAB ? "Swap A/B: On" : "Swap A/B: Off";
  }

  function readPadMap() {
    const store = storage();
    try {
      const raw = store ? store.getItem(padMapStorageKey) : null;
      const parsed = raw ? JSON.parse(raw) : {};
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (error) {
      return {};
    }
  }

  function writePadMap() {
    const store = storage();
    try { if (store) store.setItem(padMapStorageKey, JSON.stringify(padMap)); } catch (error) { /* private mode */ }
  }

  function calibrationFor(gamepad) {
    const entry = gamepad ? padMap[gamepad.id || ""] : null;
    return entry && Number.isInteger(entry.a) && Number.isInteger(entry.b) && entry.a !== entry.b
      ? entry : null;
  }

  function calibrationStatus(gamepad) {
    if (calibration && gamepad && calibration.padIndex === gamepad.index) {
      return `calibrating (press ${calibration.step})`;
    }
    const entry = gamepad ? padMap[gamepad.id || ""] : null;
    if (!entry) return "none";
    if (entry.skipped) return "skipped";
    return calibrationFor(gamepad) ? `saved a=${entry.a} b=${entry.b}` : "invalid";
  }

  // Display mode: ?display=fit|integer|stretch, the toolbar button, or the
  // stored choice; "fit" by default. Persisted in localStorage.
  function readDisplayMode() {
    const store = storage();
    const param = pageParams.get("display");
    if (displayModes.includes(param)) {
      try { if (store) store.setItem(displayStorageKey, param); } catch (error) { /* private mode */ }
      return param;
    }
    let stored = null;
    try { stored = store ? store.getItem(displayStorageKey) : null; } catch (error) { stored = null; }
    return displayModes.includes(stored) ? stored : "fit";
  }

  // Largest Game Boy screen (160x144, 10:9) for an area of availWidth x
  // availHeight CSS px. fit: integer scale when it is at least 85% of the
  // largest possible size (crisp pixels, little waste), else fractional.
  // integer: always a whole-number scale (fractional only below 1x).
  // stretch: fill the whole area, ignoring aspect.
  function computeGameRect(availWidth, availHeight, mode) {
    const width = Math.max(0, Math.floor(availWidth));
    const height = Math.max(0, Math.floor(availHeight));
    const maxScale = Math.min(width / 160, height / 144);
    if (!(maxScale > 0)) return { width: 0, height: 0, scale: 0 };
    if (mode === "stretch") return { width, height, scale: maxScale };
    const whole = Math.floor(maxScale);
    let scale = maxScale;
    if (whole >= 1 && (mode === "integer" || whole / maxScale >= 0.85)) scale = whole;
    return {
      width: Math.min(width, Math.round(160 * scale)),
      height: Math.min(height, Math.round(144 * scale)),
      scale
    };
  }

  function viewportSize() {
    const viewport = typeof window.visualViewport === "object" ? window.visualViewport : null;
    const width = viewport && viewport.width ? viewport.width : window.innerWidth;
    const height = viewport && viewport.height ? viewport.height : window.innerHeight;
    return { width: Math.floor(width || 0), height: Math.floor(height || 0) };
  }

  function setStyleVar(node, name, value) {
    if (node && node.style && typeof node.style.setProperty === "function") {
      node.style.setProperty(name, value);
    }
  }

  function toggleClass(node, name, on) {
    if (node && node.classList) node.classList.toggle(name, on);
  }

  function layoutDisplay() {
    displayLayoutHandle = 0;
    const root = document.documentElement;
    const fullscreenActive = !!document.fullscreenElement;
    toggleClass(root, "fit-layout", !fullscreenActive);
    toggleClass(shell, "fit-layout", !fullscreenActive);
    if (fullscreenActive) {
      updateFullscreenLayout();
      renderPadDebug();
      return;
    }
    const viewport = viewportSize();
    setStyleVar(shell, "--fit-viewport-height", `${viewport.height}px`);
    const side = viewport.width >= 600 && viewport.width >= viewport.height * 1.15;
    toggleClass(shell, "layout-side", side);
    toggleClass(shell, "layout-stack", !side);
    toggleClass(shell, "layout-short", !side && viewport.height < 560);
    const stageWidth = stage ? stage.clientWidth : 0;
    const stageHeight = stage ? stage.clientHeight : 0;
    const rect = computeGameRect(stageWidth, stageHeight, displayMode);
    if (screenWrap && rect.width > 0) {
      // The wrap has a 2px border on each side; keep the canvas at the scale.
      const border = displayMode === "stretch" ? 0 : 4;
      const fitted = computeGameRect(Math.max(0, stageWidth - border), Math.max(0, stageHeight - border), displayMode);
      setStyleVar(screenWrap, "--fit-game-width", `${fitted.width + border}px`);
      setStyleVar(screenWrap, "--fit-game-height", `${fitted.height + border}px`);
      lastFit = {
        mode: displayMode, scale: fitted.scale, width: fitted.width, height: fitted.height,
        stageWidth, stageHeight, layout: side ? "side" : "stack"
      };
    }
    renderPadDebug();
  }

  function scheduleDisplayLayout() {
    if (displayLayoutHandle) return;
    if (typeof requestAnimationFrame !== "function") {
      layoutDisplay();
      return;
    }
    displayLayoutHandle = requestAnimationFrame(layoutDisplay);
  }

  function refreshDisplayModeButton() {
    displayChoiceButtons.forEach(button => {
      const on = button.dataset && button.dataset.displayMode === displayMode;
      button.setAttribute("aria-pressed", on ? "true" : "false");
    });
    if (!displayModeButton) return;
    displayModeButton.textContent = `Display: ${displayModeLabels[displayMode]}`;
  }

  function setDisplayMode(mode) {
    if (!displayModes.includes(mode)) return;
    displayMode = mode;
    const store = storage();
    try { if (store) store.setItem(displayStorageKey, mode); } catch (error) { /* private mode */ }
    refreshDisplayModeButton();
    scheduleDisplayLayout();
  }

  function getConnectedGamepads() {
    if (typeof navigator.getGamepads !== "function") return [];
    return Array.from(navigator.getGamepads()).filter(Boolean);
  }

  function hasGamepadInput(gamepad) {
    if (gamepad.buttons.some(button => button.pressed || button.value > 0.5)) return true;
    const hatAxis = usesHatAxis(gamepad);
    return gamepad.axes.some((axis, index) => {
      if (hatAxis && index === 9) {
        return Object.values(readHatSwitch(gamepad)).some(Boolean);
      }
      return Math.abs(axis) > 0.35;
    });
  }

  // Nintendo pads (Switch Pro, Joy-Con, NSO pads) print A on the east face
  // button and B on the south one. Every browser layout we know of reports
  // south at index 0 and east at index 1: Chromium's "standard" mapping, the
  // raw Bluetooth HID report (B, A, Y, X, ...) and Linux hid-nintendo's
  // BTN_SOUTH/BTN_EAST order. So Nintendo pads read GB A from 1, B from 0.
  function isNintendoPad(gamepad) {
    return /057e|nintendo|pro controller|joy-?con/i.test(gamepad.id || "");
  }

  // Generic HID (non-standard) pads, including 8BitDo DirectInput and a
  // Switch Pro seen as plain Bluetooth HID, report the D-pad as a hat on
  // axis 9 instead of buttons 12-15.
  function usesHatAxis(gamepad) {
    return gamepad.mapping !== "standard" && typeof gamepad.axes[9] === "number";
  }

  function isXboxPad(gamepad) {
    return /xbox|xinput|x-box|045e|microsoft/i.test(gamepad.id || "");
  }

  function isPlayStationPad(gamepad) {
    return /playstation|dualshock|dualsense|054c|sony/i.test(gamepad.id || "");
  }

  // Families we have a deliberate default for. Anything else is offered a
  // one-time "press the button labelled A" calibration.
  function padFamily(gamepad) {
    if (isEightBitDoDirectInput(gamepad)) return "8bitdo";
    if (isNintendoPad(gamepad)) return "nintendo";
    if (/8bitdo|2dc8/i.test(gamepad.id || "")) return "8bitdo";
    if (isXboxPad(gamepad)) return "xbox";
    if (isPlayStationPad(gamepad)) return "playstation";
    return "unknown";
  }

  function padLayoutLabel(gamepad) {
    if (calibrationFor(gamepad)) return "calibrated";
    if (isEightBitDoDirectInput(gamepad) || isNintendoPad(gamepad)) return "Nintendo layout";
    return "";
  }

  function updateGamepadStatus(gamepad) {
    if (!gamepadStatus) return;
    const layout = gamepad ? padLayoutLabel(gamepad) : "";
    // (padLayoutLabel reports "calibrated" when a saved mapping applies.)
    const nextText = gamepad
      ? `Gamepad: ${gamepad.id || `controller ${gamepad.index + 1}`}${
          layout ? ` · ${layout}` : ""
        }${swapAB ? " · A/B swapped" : ""}`
      : "Gamepad: not detected — press a button";
    if (nextText === gamepadStatusText) return;
    gamepadStatusText = nextText;
    gamepadStatus.textContent = nextText;
  }

  function selectGamepad() {
    const gamepads = getConnectedGamepads();
    lastPolledPads = gamepads;
    const usedGamepad = gamepads.find(hasGamepadInput);

    if (usedGamepad) activeGamepadIndex = usedGamepad.index;

    let selected = gamepads.find(gamepad => gamepad.index === activeGamepadIndex);
    if (!selected) {
      selected = gamepads[0] || null;
      activeGamepadIndex = selected ? selected.index : null;
    }

    updateGamepadStatus(selected);
    return selected;
  }

  function isPressed(gamepad, index) {
    const button = gamepad.buttons[index];
    return !!button && (button.pressed || button.value > 0.5);
  }

  function readHatSwitch(gamepad) {
    // Generic HID pads (8BitDo DirectInput, Switch Pro over plain Bluetooth
    // HID) commonly expose the D-pad as axis 9:
    // -1.0 is up, then seven 2/7 steps clockwise. Neutral is outside
    // the normal [-1, 1] axis range (usually about 3.29).
    const value = gamepad.axes[9];
    if (typeof value !== "number" || value < -1 || value > 1) {
      return { UP: false, RIGHT: false, DOWN: false, LEFT: false };
    }

    const direction = Math.max(0, Math.min(7, Math.round((value + 1) * 3.5)));
    return {
      UP: direction === 0 || direction === 1 || direction === 7,
      RIGHT: direction >= 1 && direction <= 3,
      DOWN: direction >= 3 && direction <= 5,
      LEFT: direction >= 5 && direction <= 7
    };
  }

  function isEightBitDoDirectInput(gamepad) {
    // Some browsers expose only 8BitDo's USB vendor id (2dc8).
    return /8bitdo|2dc8/i.test(gamepad.id || "") &&
      typeof gamepad.axes[9] === "number";
  }

  function readNintendoEvdevHat(gamepad) {
    // Linux hid-nintendo exposes the Pro Controller D-pad as ABS_HAT0X/Y,
    // which Chromium's non-standard mapping reports as axes 4 and 5.
    const none = { UP: false, RIGHT: false, DOWN: false, LEFT: false };
    if (gamepad.mapping === "standard" || !isNintendoPad(gamepad)) return none;
    if (typeof gamepad.axes[9] === "number" || gamepad.axes.length !== 6) return none;
    const x = gamepad.axes[4] || 0;
    const y = gamepad.axes[5] || 0;
    return { UP: y < -0.5, RIGHT: x > 0.5, DOWN: y > 0.5, LEFT: x < -0.5 };
  }

  function familyButtonLayout(gamepad) {
    // 8BitDo DirectInput: Nintendo labels, Select/Start at 10/11.
    if (isEightBitDoDirectInput(gamepad)) {
      return { a: [1], b: [0], select: 10, start: 11, source: "8bitdo" };
    }
    // Nintendo pads: A is east (1), B is south (0). In the standard
    // mapping X (north, 3) and Y (west, 2) double as A and B by label.
    if (isNintendoPad(gamepad)) {
      return gamepad.mapping === "standard"
        ? { a: [1, 3], b: [0, 2], select: 8, start: 9, source: "nintendo" }
        : { a: [1], b: [0], select: 8, start: 9, source: "nintendo" };
    }
    // Everything else (Xbox, PlayStation, generic): positional, as WasmBoy
    // always did: south/west -> GB A, east/north -> GB B.
    return { a: [0, 2], b: [1, 3], select: 8, start: 9, source: "positional" };
  }

  // Effective layout before the player's Swap A/B preference: a saved
  // calibration for this exact gamepad.id wins over the family default.
  function gamepadButtonLayout(gamepad) {
    const base = familyButtonLayout(gamepad);
    const calibrated = calibrationFor(gamepad);
    if (!calibrated) return base;
    return { a: [calibrated.a], b: [calibrated.b], select: base.select, start: base.start, source: "calibrated" };
  }

  function readGamepadState(gamepad) {
    const horizontal = gamepad.axes[0] || 0;
    const vertical = gamepad.axes[1] || 0;
    const hat = usesHatAxis(gamepad)
      ? readHatSwitch(gamepad)
      : readNintendoEvdevHat(gamepad);
    const layout = gamepadButtonLayout(gamepad);
    const pressedA = layout.a.some(index => isPressed(gamepad, index));
    const pressedB = layout.b.some(index => isPressed(gamepad, index));
    return {
      UP: isPressed(gamepad, 12) || vertical < -0.35 || hat.UP,
      RIGHT: isPressed(gamepad, 15) || horizontal > 0.35 || hat.RIGHT,
      DOWN: isPressed(gamepad, 13) || vertical > 0.35 || hat.DOWN,
      LEFT: isPressed(gamepad, 14) || horizontal < -0.35 || hat.LEFT,
      A: swapAB ? pressedB : pressedA,
      B: swapAB ? pressedA : pressedB,
      SELECT: isPressed(gamepad, layout.select),
      START: isPressed(gamepad, layout.start)
    };
  }

  function updatePadDebug(gamepad, mapped) {
    if (pageParams.get("paddebug") !== "1") return;
    padDebugGamepad = gamepad;
    padDebugMapped = mapped;
    renderPadDebug();
  }

  // ?paddebug=1: an on-screen probe for the car. Shows each gamepad's id,
  // mapping and raw pressed indices, the mapped GB buttons, and the live
  // viewport (window, visualViewport, DPR, screen) with the current fit.
  function renderPadDebug() {
    if (pageParams.get("paddebug") !== "1") return;
    if (!padDebugElement) {
      if (typeof document.createElement !== "function" || !document.body) return;
      padDebugElement = document.createElement("pre");
      padDebugElement.id = "pad-debug";
      padDebugElement.setAttribute("aria-live", "off");
      padDebugElement.style.cssText = "position:fixed;left:4px;bottom:4px;z-index:9999;" +
        "margin:0;padding:6px 8px;max-width:96vw;white-space:pre-wrap;" +
        "font:12px/1.35 monospace;color:#0f0;background:rgba(0,0,0,.82);" +
        "border:1px solid #0f0;pointer-events:none";
      document.body.appendChild(padDebugElement);
    }
    const gamepad = padDebugGamepad;
    const mapped = padDebugMapped;
    const lines = getConnectedGamepads().map(pad => {
      const pressed = pad.buttons
        .map((button, index) => (button.pressed || button.value > 0.5) ? index : -1)
        .filter(index => index >= 0);
      const axes = pad.axes.map(axis => axis.toFixed(2)).join(" ");
      return `#${pad.index}${gamepad && pad.index === gamepad.index ? "*" : ""} ` +
        `id="${pad.id}" mapping="${pad.mapping || ""}" ` +
        `layout=${padLayoutLabel(pad) || "positional"}\n` +
        `  buttons=${pad.buttons.length} pressed=[${pressed.join(",")}] axes=[${axes}]`;
    });
    const gb = mapped
      ? Object.keys(mapped).filter(input => mapped[input]).join(" ") || "-"
      : "-";
    const num = value => (typeof value === "number" ? Math.round(value * 100) / 100 : "?");
    const vv = typeof window.visualViewport === "object" && window.visualViewport
      ? window.visualViewport : null;
    const scr = typeof screen === "object" && screen ? screen : (window.screen || null);
    const viewportLine =
      `inner=${num(window.innerWidth)}x${num(window.innerHeight)} ` +
      `vv=${vv ? `${num(vv.width)}x${num(vv.height)}@${num(vv.scale)}` : "n/a"} ` +
      `dpr=${num(window.devicePixelRatio)} ` +
      `screen=${scr ? `${num(scr.width)}x${num(scr.height)}` : "?"}`;
    const fitLine =
      `display=${displayMode} layout=${document.fullscreenElement ? "fullscreen" : lastFit.layout || "?"} ` +
      `stage=${lastFit.stageWidth}x${lastFit.stageHeight} game=${lastFit.width}x${lastFit.height} ` +
      `scale=${num(lastFit.scale)} events: resize=${viewportEvents.resize} ` +
      `orient=${viewportEvents.orientationchange} vv=${viewportEvents.visualViewport}`;
    let mapLine = "map: -";
    if (gamepad) {
      const layout = gamepadButtonLayout(gamepad);
      mapLine = `family=${padFamily(gamepad)} calib=${calibrationStatus(gamepad)} ` +
        `map(${layout.source}) A=[${(swapAB ? layout.b : layout.a).join(",")}] ` +
        `B=[${(swapAB ? layout.a : layout.b).join(",")}] select=${layout.select} start=${layout.start}`;
    }
    padDebugElement.textContent =
      `${lines.join("\n") || "no gamepads"}\nGB: ${gb}  swapAB=${swapAB ? 1 : 0}\n${mapLine}\n` +
      `${viewportLine}\n${fitLine}`;
  }

  function now() {
    return Date.now();
  }

  function pressedIndices(gamepad) {
    return gamepad.buttons
      .map((button, index) => (button && (button.pressed || button.value > 0.5)) ? index : -1)
      .filter(index => index >= 0);
  }

  // After an overlay closes, ignore the pad until every button is up so the
  // press that answered the prompt does not leak into the game.
  function padInputSuppressed(gamepad) {
    if (!suppressPadUntilRelease) return false;
    if (pressedIndices(gamepad).length === 0) suppressPadUntilRelease = false;
    return suppressPadUntilRelease;
  }

  function pauseForOverlay() {
    if (overlayPaused || !started || !api || typeof api.isPlaying !== "function") return;
    if (!api.isPlaying()) return;
    overlayPaused = true;
    Promise.resolve(api.pause()).catch(error => console.error("Could not pause", error));
  }

  // A host overlay (the desktop wrapper's credits screen) owns the pad and
  // keeps the game paused while it is open.
  let hostOverlay = false;
  function setHostOverlay(on, resume = true) {
    hostOverlay = !!on;
    if (hostOverlay) pauseForOverlay();
    else {
      suppressPadUntilRelease = true;
      if (resume) resumeAfterOverlay();
    }
  }

  function resumeAfterOverlay() {
    if (!overlayPaused || calibration || settingsOpen || hostOverlay) return;
    overlayPaused = false;
    Promise.resolve(api.play()).catch(error => console.error("Could not resume", error));
  }

  function ensureUiTimer() {
    if (uiTimer || typeof setInterval !== "function") return;
    uiTimer = setInterval(() => {
      padUiTick();
      if (!calibration && !settingsOpen && typeof clearInterval === "function") {
        clearInterval(uiTimer);
        uiTimer = 0;
      }
    }, 50);
  }

  function renderCalibration() {
    if (!calibrationOverlay) return;
    calibrationOverlay.hidden = !calibration;
    if (!calibration) return;
    if (calibrationTitle) {
      calibrationTitle.textContent = `Press the button labelled ${calibration.step} on your controller`;
    }
    if (calibrationDetail) {
      calibrationDetail.textContent = calibration.step === "A"
        ? `${calibration.padId || "Controller"} · step 1 of 2`
        : `Now the button labelled B · step 2 of 2 (A = button ${calibration.a})`;
    }
  }

  function startCalibration(gamepad, manual = false) {
    if (!calibrationOverlay || !gamepad) return false;
    if (settingsOpen) closeSettings(false);
    calibration = {
      padIndex: gamepad.index,
      padId: gamepad.id || "",
      step: "A",
      a: null,
      manual,
      waitRelease: true,
      deadline: now() + calibrationTimeoutMs
    };
    calibrationPrompted.add(calibration.padId);
    renderCalibration();
    pauseForOverlay();
    ensureUiTimer();
    renderPadDebug();
    return true;
  }

  function finishCalibration(reason) {
    if (!calibration) return;
    const { padId, a, step } = calibration;
    if (reason === "skip" || reason === "timeout") {
      if (step === "B" && a !== null) {
        // A was recorded; assume B is its partner on the other face button.
        const pad = getConnectedGamepads().find(item => (item.id || "") === padId);
        const base = pad ? familyButtonLayout(pad).b[0] : 0;
        const b = a === 0 ? 1 : a === 1 ? 0 : (base !== a ? base : (a === 0 ? 1 : 0));
        padMap[padId] = { a, b, at: now(), partial: true };
        writePadMap();
      } else if (!padMap[padId]) {
        padMap[padId] = { skipped: true, at: now() };
        writePadMap();
      }
    }
    calibration = null;
    suppressPadUntilRelease = true;
    gamepadStatusText = "";
    renderCalibration();
    if (settingsStatus) {
      settingsStatus.textContent = reason === "saved"
        ? "Controller calibrated." : `Calibration ${reason}.`;
    }
    resumeAfterOverlay();
    renderPadDebug();
  }

  function calibrationTick(pads = getConnectedGamepads()) {
    if (!calibration) return;
    const pad = pads.find(item =>
      item.index === calibration.padIndex && (item.id || "") === calibration.padId);
    if (!pad) {
      calibration = null;
      renderCalibration();
      resumeAfterOverlay();
      return;
    }
    if (now() > calibration.deadline) {
      finishCalibration("timeout");
      return;
    }
    const pressed = pressedIndices(pad);
    if (calibration.waitRelease) {
      if (pressed.length === 0) calibration.waitRelease = false;
      return;
    }
    if (pressed.length === 0) return;
    const index = pressed[0];
    if (calibration.step === "A") {
      calibration.a = index;
      calibration.step = "B";
      calibration.waitRelease = true;
      calibration.deadline = now() + calibrationTimeoutMs;
      renderCalibration();
      return;
    }
    if (index === calibration.a) return;
    padMap[calibration.padId] = { a: calibration.a, b: index, at: now() };
    writePadMap();
    finishCalibration("saved");
  }

  // Unknown controller families get the prompt once (per id, per page and
  // until skipped or calibrated); known families keep their defaults.
  function maybeAutoCalibrate(gamepad) {
    if (!gamepad || !calibrationOverlay || calibration || settingsOpen) return;
    if (padFamily(gamepad) !== "unknown") return;
    const id = gamepad.id || "";
    if (padMap[id] || calibrationPrompted.has(id)) return;
    if (!gamepad.buttons || gamepad.buttons.length < 2) return;
    startCalibration(gamepad, false);
  }

  function settingsItems() {
    if (!settingsPanel || typeof settingsPanel.querySelectorAll !== "function") return [];
    return Array.from(settingsPanel.querySelectorAll(".settings-item"))
      .filter(item => !item.disabled && !item.hidden);
  }

  function focusSettingsItem(index) {
    const items = settingsItems();
    if (!items.length) return;
    settingsFocus = (index + items.length) % items.length;
    items.forEach((item, i) => toggleClass(item, "is-focused", i === settingsFocus));
    if (typeof items[settingsFocus].focus === "function") items[settingsFocus].focus();
  }

  function openSettings() {
    if (!settingsPanel || settingsOpen) return;
    if (calibration) finishCalibration("skip");
    settingsOpen = true;
    settingsPanel.hidden = false;
    if (settingsStatus) settingsStatus.textContent = "";
    uiPadPrevious = {};
    focusSettingsItem(0);
    pauseForOverlay();
    ensureUiTimer();
  }

  function closeSettings(resume = true) {
    if (!settingsPanel || !settingsOpen) return;
    settingsOpen = false;
    settingsPanel.hidden = true;
    suppressPadUntilRelease = true;
    if (resume) resumeAfterOverlay();
    if (canvas && typeof canvas.focus === "function") canvas.focus();
  }

  function settingsTick(gamepad) {
    if (!settingsOpen || !gamepad) return;
    if (padInputSuppressed(gamepad)) return;
    const state = readGamepadState(gamepad);
    const edge = input => state[input] && !uiPadPrevious[input];
    if (edge("UP") || edge("LEFT")) focusSettingsItem(settingsFocus - 1);
    else if (edge("DOWN") || edge("RIGHT")) focusSettingsItem(settingsFocus + 1);
    else if (edge("A")) {
      const item = settingsItems()[settingsFocus];
      if (item && typeof item.click === "function") item.click();
    } else if (edge("B") || edge("START")) {
      closeSettings();
    }
    uiPadPrevious = state;
  }

  // Gamepad route into settings: Home/Guide (standard index 16), or hold
  // Select + Start together for about half a second.
  function settingsChordTick(gamepad) {
    if (!gamepad || settingsOpen || calibration || !settingsPanel) return;
    const home = isPressed(gamepad, 16);
    const layout = gamepadButtonLayout(gamepad);
    const chord = isPressed(gamepad, layout.select) && isPressed(gamepad, layout.start);
    if (home && !homeWasDown) {
      homeWasDown = true;
      openSettings();
      return;
    }
    homeWasDown = home;
    if (!chord) {
      chordSince = 0;
      return;
    }
    if (!chordSince) chordSince = now();
    else if (now() - chordSince >= 500) {
      chordSince = 0;
      openSettings();
    }
  }

  function padUiTick(pads = getConnectedGamepads()) {
    if (hostOverlay) return;
    if (calibration) {
      calibrationTick(pads);
      return;
    }
    const active = pads.find(pad => pad.index === activeGamepadIndex) || pads[0] || null;
    if (settingsOpen) {
      settingsTick(active);
      return;
    }
    if (active) {
      settingsChordTick(active);
      maybeAutoCalibrate(active);
    }
  }

  function resetPadMapping() {
    padMap = {};
    writePadMap();
    calibrationPrompted.clear();
    gamepadStatusText = "";
    if (settingsStatus) settingsStatus.textContent = "Saved controller mappings cleared.";
    updateGamepadStatus(selectGamepad());
  }

  function enableAnyConnectedGamepad() {
    const responsive = api && api.ResponsiveGamepad;
    if (!responsive || typeof responsive.getState !== "function") return;

    // WasmBoy's built-in gamepad reader maps browser button 0 -> A and 1 -> B
    // (plus 2/3 via its X/Y plugin) on gamepad 0, positionally, whatever the
    // controller. OR-ing that with our own mapping made a Switch Pro's B
    // (south, index 0) press GB A and its A press GB B. Silence it so only
    // readGamepadState below decides what a pad's buttons mean.
    if (responsive.Gamepad && typeof responsive.Gamepad.getState === "function") {
      responsive.Gamepad.getState = () => ({});
    }

    const getState = responsive.getState.bind(responsive);
    responsive.getState = () => {
      const state = getState() || {};
      Object.keys(touchState).forEach(input => {
        state[input] = state[input] || touchState[input];
      });
      const gamepad = selectGamepad();
      if (!gamepad) {
        updatePadDebug(null, null);
        return state;
      }

      padUiTick(lastPolledPads);
      if (calibration || settingsOpen || padInputSuppressed(gamepad)) {
        updatePadDebug(gamepad, null);
        return state;
      }
      const directState = readGamepadState(gamepad);
      Object.keys(directState).forEach(input => {
        state[input] = state[input] || directState[input];
      });
      updatePadDebug(gamepad, directState);
      return state;
    };
  }

  function setStatus(message, isError = false) {
    status.textContent = message;
    status.classList.toggle("error", isError);
  }

  function fail(error) {
    console.error(error);
    setStatus("Browser player failed to start", true);
    launch.disabled = true;
    launch.setAttribute("aria-busy", "false");
    launch.querySelector("strong").textContent = "Player error";
    launch.querySelector("span").textContent = "Download the cartridge ROM below to play in an emulator.";
  }

  async function prepare() {
    if (!api) {
      throw new Error("WasmBoy did not load");
    }

    enableAnyConnectedGamepad();

    await api.config({
      enableBootROMIfAvailable: false,
      isGbcEnabled: true,
      isGbcColorizationEnabled: true,
      randomizeStartupRam: false,
      disablePauseOnHidden: true,
      cartridgeRamStorageKey: "quintra:mbc5:sram:v1",
      cartridgeRamStorageSize: 32 * 1024,
      isAudioEnabled: true,
      audioWorkletDirectOutput: true,
      audioTargetLatencyInSeconds: 0.042,
      maxNumberOfAutoSaveStates: 2,
      onReady: () => setStatus("Cartridge ready")
    }, canvas);
    await api.loadROM("quintra.gbc", { fileName: "quintra.gbc" });
    ready = true;
    launch.querySelector("strong").textContent = "Enter the Riftwild";
    launch.querySelector("span").textContent = "Click, tap, or press A / Start to play with sound";
    launch.setAttribute("aria-busy", "false");
    launch.disabled = false;
    exportSave.disabled = false;
    importSave.disabled = false;
    setStatus("Ready — click or press Start to play");
    if (typeof window.dispatchEvent === "function" && typeof Event === "function") {
      window.dispatchEvent(new Event("quintra:ready"));
    }
  }

  // WasmBoy keeps one AudioContext per GB channel. Browsers create them
  // suspended outside a user gesture and may suspend ("interrupted" on
  // Safari) them again after tab switches, fullscreen or audio-route changes.
  function audioContexts() {
    let channels = {};
    try { channels = api._getAudioChannels() || {}; } catch (error) { return []; }
    return Object.values(channels)
      .map(channel => channel && channel.audioContext ? { channel, context: channel.audioContext } : null)
      .filter(Boolean);
  }

  function audioRunning() {
    const contexts = audioContexts();
    return contexts.length > 0 && contexts.every(({ context }) => context.state === "running");
  }

  // Pausing the emulator stops new samples. The worklet keeps rendering, so
  // an unsuspended context drains the 42 ms queue and then counts silence.
  async function suspendAudio() {
    const pending = audioContexts()
      .filter(({ context }) => context.state === "running" && typeof context.suspend === "function")
      .map(async ({ context }) => {
        try { await context.suspend(); } catch (error) { /* best effort */ }
      });
    await Promise.all(pending);
  }

  function refreshSoundBanner() {
    if (!soundBanner) return;
    soundBanner.hidden = !started || muted || audioRunning();
    if (!soundBanner.hidden) ensureGamepadPolling();
  }

  // Safari/WebKit: prime a suspended or "interrupted" webkitAudioContext
  // with a one-sample silent buffer inside the gesture; iOS will not unlock
  // output otherwise, even after resume() resolves.
  function primeContext(context) {
    try {
      const buffer = context.createBuffer(1, 1, context.sampleRate || 44100);
      const source = context.createBufferSource();
      source.buffer = buffer;
      source.connect(context.destination);
      if (source.start) source.start(0); else if (source.noteOn) source.noteOn(0);
    } catch (error) { /* priming is best effort */ }
  }

  async function resumeAudio() {
    if (!api) return false;
    // Creates the contexts on first use (inside the gesture when possible).
    try { api.resumeAudioContext(); } catch (error) { /* contexts not created yet */ }
    // WasmBoy only resumes "suspended"; Safari also reports "interrupted".
    // resume() is called synchronously here so it stays inside the gesture.
    const pending = audioContexts()
      .filter(({ context }) => context.state !== "running" && context.state !== "closed")
      .map(async ({ channel, context }) => {
        primeContext(context);
        try {
          await context.resume();
          // Restart the channel clock so queued samples do not lag behind.
          channel.audioPlaytime = context.currentTime;
        } catch (error) {
          console.warn("Could not resume audio", error);
        }
      });
    await Promise.all(pending);
    refreshSoundBanner();
    return audioRunning();
  }

  // No de-duplication: a resume attempt started outside a gesture (focus,
  // visibilitychange) must not swallow the next real tap or key press.
  function unlockAudio() {
    if (audioRunning()) { refreshSoundBanner(); return Promise.resolve(true); }
    return resumeAudio();
  }

  function watchAudioState() {
    audioContexts().forEach(({ context }) => {
      if (context.__quintraWatched) return;
      context.__quintraWatched = true;
      if (context.addEventListener) context.addEventListener("statechange", refreshSoundBanner);
      else context.onstatechange = refreshSoundBanner;
    });
    refreshSoundBanner();
  }

  function pollGamepadButtons() {
    gamepadPollHandle = 0;
    let pressedNow = false;
    let launchPressed = false;
    getConnectedGamepads().forEach(gamepad => {
      const previous = gamepadButtonsDown.get(gamepad.index) || [];
      const current = gamepad.buttons.map(button => button.pressed || button.value > 0.5);
      current.forEach((down, index) => {
        if (!down || previous[index]) return;
        pressedNow = true;
        if (launchGamepadButtons.includes(index)) launchPressed = true;
      });
      gamepadButtonsDown.set(gamepad.index, current);
    });
    // A press that answered (or is answering) an overlay must not launch.
    const overlayBefore = !!(calibration || settingsOpen || suppressPadUntilRelease);
    padUiTick();
    if (suppressPadUntilRelease && getConnectedGamepads().every(pad => pressedIndices(pad).length === 0)) {
      suppressPadUntilRelease = false;
    }
    if (overlayBefore || calibration || settingsOpen || suppressPadUntilRelease) launchPressed = false;
    if (launchPressed && ready && !started) start().catch(fail);
    else if (pressedNow) unlockAudio();
    // Only watch raw buttons while there is something to do: before launch,
    // or while sound is still suspended. Gameplay input stays on WasmBoy's
    // own once-per-frame ResponsiveGamepad poll.
    if (!started || !audioRunning()) ensureGamepadPolling();
  }

  function ensureGamepadPolling() {
    if (gamepadPollHandle || typeof requestAnimationFrame !== "function") return;
    gamepadPollHandle = requestAnimationFrame(pollGamepadButtons);
  }

  async function start() {
    if (!ready || started) return;
    started = true;
    launch.hidden = true;
    await unlockAudio();
    await api.play();
    watchAudioState();
    canvas.focus();
    setStatus("Playing");
  }

  async function snapshotRam() {
    const resume = api.isPlaying();
    const state = await api.saveState();
    const ram = state && state.wasmboyMemory && state.wasmboyMemory.cartridgeRam;
    if (!ram || ram.byteLength < saveSize) {
      throw new Error(`Expected at least ${saveSize} bytes of cartridge RAM, got ${ram ? ram.byteLength : 0}`);
    }
    await api.saveLoadedCartridge({ title: "Quintra" });
    if (resume) await api.play();
    return new Uint8Array(ram).slice(0, saveSize);
  }

  async function exportCartridgeSave() {
    if (saveBusy) return;
    saveBusy = true;
    try {
      setStatus("Exporting save…");
      const ram = await snapshotRam();
      const url = URL.createObjectURL(new Blob([ram], { type: "application/octet-stream" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = "quintra.sav";
      link.click();
      URL.revokeObjectURL(url);
      setStatus("Save exported");
    } catch (error) {
      console.error(error);
      setStatus("Could not export save", true);
    } finally {
      saveBusy = false;
      canvas.focus();
    }
  }

  // Replace cartridge RAM with exactly saveSize bytes (save import, and the
  // desktop wrapper's on-disk save).
  async function importRam(bytes) {
    if (!bytes || bytes.byteLength !== saveSize) {
      throw new Error(`Quintra saves must be exactly ${saveSize} bytes`);
    }
    const resume = api.isPlaying();
    const state = await api.saveState();
    const currentRam = state.wasmboyMemory.cartridgeRam;
    const importedRam = new Uint8Array(currentRam.byteLength);
    importedRam.set(bytes);
    state.wasmboyMemory.cartridgeRam = importedRam;
    await api.loadState(state);
    await api.saveLoadedCartridge({ title: "Quintra" });
    if (resume) await api.play();
  }

  // Live battery RAM straight from the core's memory, without pausing the
  // emulator (saveState would pause and drop queued audio).
  let cartridgeRamLocation = null;
  async function readRamLive() {
    if (cartridgeRamLocation === null) {
      cartridgeRamLocation = await api._getWasmConstant("CARTRIDGE_RAM_LOCATION");
    }
    const section = await api._getWasmMemorySection(cartridgeRamLocation, cartridgeRamLocation + saveSize);
    return new Uint8Array(section).slice(0, saveSize);
  }

  async function importCartridgeSave(file) {
    if (!file || saveBusy) return;
    saveBusy = true;
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (bytes.byteLength !== saveSize) {
        throw new Error(`Quintra saves must be exactly ${saveSize} bytes`);
      }

      setStatus("Importing save…");
      await importRam(bytes);
      setStatus("Save imported");
      window.dispatchEvent(new CustomEvent("quintra:save-imported", { detail: bytes }));
    } catch (error) {
      console.error(error);
      setStatus(error.message || "Could not import save", true);
    } finally {
      saveBusy = false;
      saveFile.value = "";
      canvas.focus();
    }
  }

  launch.addEventListener("click", () => start().catch(fail));

  mute.addEventListener("click", () => {
    muted = !muted;
    const master = api._getAudioChannels().master;
    if (muted) master.mute(); else master.unmute();
    if (!muted) unlockAudio();
    refreshSoundBanner();
    mute.textContent = muted ? "Unmute" : "Mute";
    mute.setAttribute("aria-pressed", String(muted));
    canvas.focus();
  });

  fullscreen.addEventListener("click", async () => {
    if (document.fullscreenElement) {
      await document.exitFullscreen();
    } else {
      await shell.requestFullscreen();
    }
    canvas.focus();
  });

  function updateFullscreenLayout() {
    if (document.fullscreenElement !== shell) return;
    const controlsHeight = touchControls ? touchControls.getBoundingClientRect().height : 0;
    const availableHeight = Math.max(0, window.innerHeight - controlsHeight);
    const gameWidth = Math.min(window.innerWidth, availableHeight * 10 / 9);
    shell.style.setProperty("--fullscreen-game-width", `${gameWidth}px`);
    shell.style.setProperty("--fullscreen-game-height", `${gameWidth * 9 / 10}px`);
  }

  document.addEventListener("fullscreenchange", () => {
    if (started) unlockAudio();
    fullscreen.textContent = document.fullscreenElement ? "Exit fullscreen" : "Fullscreen";
    scheduleDisplayLayout();
  });
  window.addEventListener("resize", () => {
    viewportEvents.resize += 1;
    scheduleDisplayLayout();
  });
  window.addEventListener("orientationchange", () => {
    viewportEvents.orientationchange += 1;
    scheduleDisplayLayout();
  });
  if (typeof window.visualViewport === "object" && window.visualViewport &&
      typeof window.visualViewport.addEventListener === "function") {
    ["resize", "scroll"].forEach(type => window.visualViewport.addEventListener(type, () => {
      viewportEvents.visualViewport += 1;
      scheduleDisplayLayout();
    }));
  }
  if (typeof ResizeObserver === "function" && stage) {
    new ResizeObserver(() => scheduleDisplayLayout()).observe(stage);
  }
  refreshDisplayModeButton();
  if (displayModeButton) {
    displayModeButton.addEventListener("click", () => {
      setDisplayMode(displayModes[(displayModes.indexOf(displayMode) + 1) % displayModes.length]);
    });
  }
  layoutDisplay();
  if (pageParams.get("paddebug") === "1" && typeof setInterval === "function") {
    setInterval(renderPadDebug, 250);
  }
  window.QuintraDisplay = { computeGameRect, layoutDisplay, get mode() { return displayMode; } };
  // Test/diagnostic hooks for the pad UI.
  window.QuintraPads = {
    tick: () => padUiTick(),
    startCalibration: () => startCalibration(selectGamepad(), true),
    skipCalibration: () => finishCalibration("skip"),
    openSettings,
    closeSettings: () => closeSettings(),
    resetMapping: resetPadMapping,
    get calibrating() { return calibration ? calibration.step : null; },
    get settingsOpen() { return settingsOpen; },
    layoutFor: gamepad => gamepadButtonLayout(gamepad),
    familyOf: gamepad => padFamily(gamepad)
  };
  // Host hooks for the desktop wrapper (desktop/renderer/desktop.js). The
  // web page does not use them.
  window.QuintraPlayer = {
    get ready() { return ready; },
    get started() { return started; },
    start: () => start(),
    importRam,
    readRamLive,
    snapshotRam,
    closeSettings: (resume = true) => closeSettings(resume),
    setHostOverlay
  };

  exportSave.addEventListener("click", exportCartridgeSave);
  importSave.addEventListener("click", () => saveFile.click());
  saveFile.addEventListener("change", () => importCartridgeSave(saveFile.files[0]));

  // Any gesture may (re)unlock audio. Capture phase so handlers that stop
  // propagation (touch D-pad, launch) still count.
  ["keydown", "pointerdown", "touchstart", "touchend", "mousedown", "click"].forEach(type => {
    document.addEventListener(type, () => { if (started) unlockAudio(); }, { capture: true, passive: true });
  });
  if (soundBanner) soundBanner.addEventListener("click", () => { unlockAudio(); canvas.focus(); });
  window.addEventListener("focus", () => { if (started) unlockAudio(); });
  ensureGamepadPolling();

  refreshSwapAbButton();
  if (swapAbButton) {
    swapAbButton.addEventListener("click", () => {
      setSwapAB(!swapAB);
      updateGamepadStatus(selectGamepad());
    });
  }
  displayChoiceButtons.forEach(button => {
    button.addEventListener("click", () => setDisplayMode(button.dataset.displayMode));
  });
  if (settingsButton) settingsButton.addEventListener("click", () => openSettings());
  if (settingsClose) settingsClose.addEventListener("click", () => closeSettings());
  if (recalibrateButton) {
    recalibrateButton.addEventListener("click", () => {
      const pad = selectGamepad();
      if (!pad) {
        if (settingsStatus) settingsStatus.textContent = "Connect a controller and press any button first.";
        return;
      }
      startCalibration(pad, true);
    });
  }
  if (resetMappingButton) resetMappingButton.addEventListener("click", resetPadMapping);
  if (calibrationSkip) calibrationSkip.addEventListener("click", () => finishCalibration("skip"));

  window.addEventListener("gamepadconnected", event => {
    ensureGamepadPolling();
    if (activeGamepadIndex === null) activeGamepadIndex = event.gamepad.index;
    updateGamepadStatus(event.gamepad);
    maybeAutoCalibrate(event.gamepad);
  });

  window.addEventListener("gamepaddisconnected", event => {
    if (activeGamepadIndex === event.gamepad.index) activeGamepadIndex = null;
    updateGamepadStatus(getConnectedGamepads()[0] || null);
  });

  document.addEventListener("keydown", event => {
    if (event.code === "Escape" && (calibration || settingsOpen)) {
      if (calibration) finishCalibration("skip");
      else closeSettings();
      event.preventDefault();
      return;
    }
    if (settingsOpen) return;
    if (!started && ready && (event.code === "Enter" || event.code === "KeyX")
        && document.activeElement !== launch) {
      start().catch(fail);
    }
    if (started && handledKeys.has(event.code)) event.preventDefault();
  }, { passive: false });

  document.addEventListener("visibilitychange", () => {
    const hidden = document.visibilityState === "hidden";
    if (hidden) clearTouchPointers();
    visibilityTask = visibilityTask.then(async () => {
      if (!ready) return;
      if (hidden) {
        const playing = started && api.isPlaying();
        resumeAfterVisibility = resumeAfterVisibility || playing;
        if (playing) {
          await api.pause();
          await suspendAudio();
        }
        await api.saveLoadedCartridge({ title: "Quintra" });
      } else if (resumeAfterVisibility && document.visibilityState === "visible") {
        resumeAfterVisibility = false;
        await api.play();
        setStatus("Playing");
        if (started) await unlockAudio();
      } else if (!hidden && started) {
        await unlockAudio();
      }
    }).catch(error => console.error("Could not update player visibility", error));
  });

  window.addEventListener("error", event => fail(event.error || new Error(event.message)));
  prepare().catch(fail);
})();

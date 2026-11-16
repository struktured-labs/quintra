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
    swapAbButton.textContent = swapAB ? "A/B swapped" : "Swap A/B";
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

  function padLayoutLabel(gamepad) {
    if (isEightBitDoDirectInput(gamepad) || isNintendoPad(gamepad)) return "Nintendo layout";
    return "";
  }

  function updateGamepadStatus(gamepad) {
    if (!gamepadStatus) return;
    const layout = gamepad ? padLayoutLabel(gamepad) : "";
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

  function gamepadButtonLayout(gamepad) {
    // 8BitDo DirectInput: Nintendo labels, Select/Start at 10/11.
    if (isEightBitDoDirectInput(gamepad)) {
      return { a: [1], b: [0], select: 10, start: 11 };
    }
    // Nintendo pads: A is east (1), B is south (0). In the standard
    // mapping X (north, 3) and Y (west, 2) double as A and B by label.
    if (isNintendoPad(gamepad)) {
      return gamepad.mapping === "standard"
        ? { a: [1, 3], b: [0, 2], select: 8, start: 9 }
        : { a: [1], b: [0], select: 8, start: 9 };
    }
    // Everything else (Xbox, PlayStation, generic): positional, as WasmBoy
    // always did: south/west -> GB A, east/north -> GB B.
    return { a: [0, 2], b: [1, 3], select: 8, start: 9 };
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
    padDebugElement.textContent =
      `${lines.join("\n") || "no gamepads"}\nGB: ${gb}  swapAB=${swapAB ? 1 : 0}`;
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

  async function importCartridgeSave(file) {
    if (!file || saveBusy) return;
    saveBusy = true;
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (bytes.byteLength !== saveSize) {
        throw new Error(`Quintra saves must be exactly ${saveSize} bytes`);
      }

      setStatus("Importing save…");
      const resume = api.isPlaying();
      const state = await api.saveState();
      const currentRam = state.wasmboyMemory.cartridgeRam;
      const importedRam = new Uint8Array(currentRam.byteLength);
      importedRam.set(bytes);
      state.wasmboyMemory.cartridgeRam = importedRam;
      await api.loadState(state);
      await api.saveLoadedCartridge({ title: "Quintra" });
      if (resume) await api.play();
      setStatus("Save imported");
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
    requestAnimationFrame(updateFullscreenLayout);
  });
  window.addEventListener("resize", () => {
    if (document.fullscreenElement === shell) requestAnimationFrame(updateFullscreenLayout);
  });

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

  window.addEventListener("gamepadconnected", event => {
    ensureGamepadPolling();
    if (activeGamepadIndex === null) activeGamepadIndex = event.gamepad.index;
    updateGamepadStatus(event.gamepad);
  });

  window.addEventListener("gamepaddisconnected", event => {
    if (activeGamepadIndex === event.gamepad.index) activeGamepadIndex = null;
    updateGamepadStatus(getConnectedGamepads()[0] || null);
  });

  document.addEventListener("keydown", event => {
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

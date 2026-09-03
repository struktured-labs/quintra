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
  const gamepadStatus = document.querySelector("#gamepad-status");
  const touchButtons = Array.from(document.querySelectorAll("[data-touch-input]"));
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
  const touchPointers = new Map();
  const touchState = {
    UP: false, RIGHT: false, DOWN: false, LEFT: false,
    A: false, B: false, SELECT: false, START: false
  };

  function refreshTouchState() {
    Object.keys(touchState).forEach(input => {
      touchState[input] = Array.from(touchPointers.values()).some(inputs => inputs.includes(input));
    });
  }

  function pressTouchButton(button, event) {
    event.preventDefault();
    const inputs = button.dataset.touchInput.split(" ");
    touchPointers.set(event.pointerId, inputs);
    refreshTouchState();
    button.classList.toggle("is-pressed", true);
    if (typeof button.setPointerCapture === "function") {
      button.setPointerCapture(event.pointerId);
    }
  }

  function releaseTouchButton(button, event) {
    touchPointers.delete(event.pointerId);
    refreshTouchState();
    button.classList.toggle("is-pressed", false);
  }

  touchButtons.forEach(button => {
    button.addEventListener("pointerdown", event => pressTouchButton(button, event), { passive: false });
    button.addEventListener("pointerup", event => releaseTouchButton(button, event));
    button.addEventListener("pointercancel", event => releaseTouchButton(button, event));
    button.addEventListener("lostpointercapture", event => releaseTouchButton(button, event));
    button.addEventListener("contextmenu", event => event.preventDefault());
  });

  function getConnectedGamepads() {
    if (typeof navigator.getGamepads !== "function") return [];
    return Array.from(navigator.getGamepads()).filter(Boolean);
  }

  function hasGamepadInput(gamepad) {
    return gamepad.buttons.some(button => button.pressed || button.value > 0.5) ||
      gamepad.axes.some(axis => Math.abs(axis) > 0.35);
  }

  function updateGamepadStatus(gamepad) {
    if (!gamepadStatus) return;
    gamepadStatus.textContent = gamepad
      ? `Gamepad: ${gamepad.id || `controller ${gamepad.index + 1}`}${
          isEightBitDoDirectInput(gamepad) ? " · Nintendo layout" : ""
        }`
      : "Gamepad: not detected — press a button";
  }

  function selectGamepadIndex() {
    const gamepads = getConnectedGamepads();
    const usedGamepad = gamepads.find(hasGamepadInput);

    if (usedGamepad) activeGamepadIndex = usedGamepad.index;

    let selected = gamepads.find(gamepad => gamepad.index === activeGamepadIndex);
    if (!selected) {
      selected = gamepads[0] || null;
      activeGamepadIndex = selected ? selected.index : null;
    }

    updateGamepadStatus(selected);
    return selected ? selected.index : 0;
  }

  function isPressed(gamepad, index) {
    const button = gamepad.buttons[index];
    return !!button && (button.pressed || button.value > 0.5);
  }

  function readHatSwitch(gamepad) {
    // 8BitDo's DirectInput modes commonly expose the D-pad as axis 9:
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

  function readGamepadState(gamepad) {
    const horizontal = gamepad.axes[0] || 0;
    const vertical = gamepad.axes[1] || 0;
    const hat = readHatSwitch(gamepad);
    // Linux exposes the Pro 2's Nintendo-labelled face/menu buttons at these
    // DirectInput indices. Preserve the standard browser mapping in XInput.
    const eightBitDoDirectInput = isEightBitDoDirectInput(gamepad);
    const aButton = eightBitDoDirectInput ? 1 : 0;
    const bButton = eightBitDoDirectInput ? 0 : 1;
    const selectButton = eightBitDoDirectInput ? 10 : 8;
    const startButton = eightBitDoDirectInput ? 11 : 9;
    return {
      UP: isPressed(gamepad, 12) || vertical < -0.35 || hat.UP,
      RIGHT: isPressed(gamepad, 15) || horizontal > 0.35 || hat.RIGHT,
      DOWN: isPressed(gamepad, 13) || vertical > 0.35 || hat.DOWN,
      LEFT: isPressed(gamepad, 14) || horizontal < -0.35 || hat.LEFT,
      A: isPressed(gamepad, aButton),
      B: isPressed(gamepad, bButton),
      SELECT: isPressed(gamepad, selectButton),
      START: isPressed(gamepad, startButton)
    };
  }

  function enableAnyConnectedGamepad() {
    const responsive = api && api.ResponsiveGamepad;
    if (!responsive || typeof responsive.getState !== "function") return;

    const getState = responsive.getState.bind(responsive);
    responsive.getState = () => {
      const state = getState() || {};
      Object.keys(touchState).forEach(input => {
        state[input] = state[input] || touchState[input];
      });
      const index = selectGamepadIndex();
      const gamepad = getConnectedGamepads().find(pad => pad.index === index);
      if (!gamepad) return state;

      const directState = readGamepadState(gamepad);
      Object.keys(directState).forEach(input => {
        state[input] = state[input] || directState[input];
      });
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
      isAudioEnabled: true,
      audioWorkletDirectOutput: true,
      audioTargetLatencyInSeconds: 0.024,
      maxNumberOfAutoSaveStates: 2,
      onReady: () => setStatus("Cartridge ready")
    }, canvas);
    await api.loadROM("quintra.gbc", { fileName: "quintra.gbc" });
    ready = true;
    launch.disabled = false;
    exportSave.disabled = false;
    importSave.disabled = false;
    setStatus("Ready — click to play");
  }

  async function start() {
    if (!ready || started) return;
    started = true;
    launch.hidden = true;
    await api.resumeAudioContext();
    await api.play();
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

  document.addEventListener("fullscreenchange", () => {
    fullscreen.textContent = document.fullscreenElement ? "Exit fullscreen" : "Fullscreen";
  });

  exportSave.addEventListener("click", exportCartridgeSave);
  importSave.addEventListener("click", () => saveFile.click());
  saveFile.addEventListener("change", () => importCartridgeSave(saveFile.files[0]));

  window.addEventListener("gamepadconnected", event => {
    if (activeGamepadIndex === null) activeGamepadIndex = event.gamepad.index;
    updateGamepadStatus(event.gamepad);
  });

  window.addEventListener("gamepaddisconnected", event => {
    if (activeGamepadIndex === event.gamepad.index) activeGamepadIndex = null;
    updateGamepadStatus(getConnectedGamepads()[0] || null);
  });

  document.addEventListener("keydown", event => {
    if (started && handledKeys.has(event.code)) event.preventDefault();
  }, { passive: false });

  document.addEventListener("visibilitychange", () => {
    if (ready && document.visibilityState === "hidden") {
      api.saveLoadedCartridge({ title: "Quintra" }).catch(console.error);
    }
  });

  window.addEventListener("error", event => fail(event.error || new Error(event.message)));
  prepare().catch(fail);
})();

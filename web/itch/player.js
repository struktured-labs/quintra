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

    await api.config({
      enableBootROMIfAvailable: false,
      isGbcEnabled: true,
      isGbcColorizationEnabled: true,
      isAudioEnabled: true,
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

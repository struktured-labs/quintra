/*
 * Quintra desktop wrapper (renderer side)
 * Copyright 2026 Quintra contributors
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * Loaded after quintra-player.js only in the Electron build. Forms one
 * program with the browser player and WasmBoy.
 */
(() => {
  "use strict";

  const host = window.QuintraDesktop;
  const player = window.QuintraPlayer;
  const pads = window.QuintraPads;
  if (!host || !player || !pads) return;

  const SAVE_SIZE = 32 * 1024;
  const POLL_MS = 2000;
  const selftest = new URLSearchParams(location.search).get("selftest") === "1";
  const state = window.QuintraDesktopState = {
    running: false, loadedFromDisk: false, migratedFromBrowser: false,
    bootRamSha256: null, writes: 0, lastError: null, fullscreen: true
  };

  document.documentElement.classList.add("desktop");
  document.title = "Quintra";

  // --- Save sync ----------------------------------------------------------

  let lastWritten = null;
  let writing = Promise.resolve();

  const sameBytes = (a, b) => {
    if (!a || !b || a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
    return true;
  };
  const isBlank = bytes => bytes.every(v => v === 0) || bytes.every(v => v === 0xff);

  async function sha256Hex(bytes) {
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest)).map(v => v.toString(16).padStart(2, "0")).join("");
  }

  function persist(bytes, force = false) {
    writing = writing.then(async () => {
      if (!bytes || bytes.length !== SAVE_SIZE) return;
      if (!force && sameBytes(bytes, lastWritten)) return;
      await host.writeSave(bytes);
      lastWritten = bytes.slice();
      state.writes += 1;
    }).catch(error => {
      state.lastError = String(error);
      console.error("Could not write save file", error);
    });
    return writing;
  }

  async function flush() {
    if (!player.ready) return;
    try {
      await persist(await player.readRamLive());
    } catch (error) {
      state.lastError = String(error);
    }
    await writing;
  }

  async function boot() {
    const disk = await host.readSave();
    if (disk && disk.length === SAVE_SIZE) {
      const bytes = new Uint8Array(disk);
      await player.importRam(bytes);
      lastWritten = bytes.slice();
      state.loadedFromDisk = true;
    } else {
      // First desktop run: keep any battery RAM WasmBoy restored from this
      // profile's browser storage by writing it to the save file once.
      const current = await player.readRamLive();
      if (!isBlank(current)) {
        await persist(current, true);
        state.migratedFromBrowser = true;
      }
    }
    state.bootRamSha256 = await sha256Hex(await player.readRamLive());
    if (!selftest || new URLSearchParams(location.search).get("noautostart") !== "1") {
      await player.start();
    }
    state.running = true;
    document.documentElement.classList.add("running");
    setInterval(() => {
      if (!player.started) return;
      player.readRamLive().then(bytes => persist(bytes)).catch(error => { state.lastError = String(error); });
    }, POLL_MS);
  }

  host.onFlushRequest(flush);
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") flush(); });
  window.addEventListener("pagehide", () => { flush(); });

  // Test hook used by the headless self-test only.
  if (selftest) {
    window.QuintraDesktopTest = {
      async importAndFlush(bytes) {
        await player.importRam(new Uint8Array(bytes));
        await persist(await player.readRamLive(), true);
        await writing;
      }
    };
  }

  // --- Settings items -----------------------------------------------------

  const card = document.querySelector("#settings-panel .settings-card");
  const closeItem = document.querySelector("#settings-close");
  const hint = document.querySelector("#settings-panel .settings-hint");
  const settingsStatus = document.querySelector("#settings-status");

  function addItem(id, label, onClick) {
    const button = document.createElement("button");
    button.className = "settings-item";
    button.id = id;
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", onClick);
    card.insertBefore(button, closeItem);
    return button;
  }

  const fullscreenItem = addItem("desktop-fullscreen", "Display: Fullscreen", async () => {
    const on = await host.setFullscreen(!state.fullscreen);
    renderFullscreen(on);
  });
  function renderFullscreen(on) {
    state.fullscreen = !!on;
    fullscreenItem.textContent = on ? "Window mode: Fullscreen (F11)" : "Window mode: Windowed (F11)";
  }
  host.getFullscreen().then(renderFullscreen);
  host.onFullscreen(renderFullscreen);

  const muteButton = document.querySelector("#mute");
  const soundItem = addItem("desktop-sound", "Sound: On", () => {
    if (muteButton) muteButton.click();
    renderSound();
  });
  function renderSound() {
    const muted = muteButton && muteButton.getAttribute("aria-pressed") === "true";
    soundItem.textContent = muted ? "Sound: Off" : "Sound: On";
  }

  const saveInput = document.querySelector("#save-file");
  addItem("desktop-import", "Import browser save (.sav)", () => {
    if (saveInput) saveInput.click();
  });
  if (saveInput) {
    // The player's own handler imports into cartridge RAM; write it to disk.
    saveInput.addEventListener("change", () => setTimeout(() => {
      flush().then(() => { if (settingsStatus) settingsStatus.textContent = "Save imported and written to disk."; });
    }, 500));
  }

  addItem("desktop-credits-item", "Credits and licenses", () => openCredits());
  addItem("desktop-quit", "Quit Quintra", () => host.quit());
  if (hint) {
    hint.textContent = "Gamepad: D-pad moves, A chooses, B closes. Open with Home, Select + Start, or Esc. F11 or Alt+Enter toggles fullscreen.";
  }

  // Esc opens settings (the web player only uses it to close them).
  window.addEventListener("keydown", event => {
    if (event.code !== "Escape") return;
    if (creditsOpen) {
      closeCredits();
      event.preventDefault();
      event.stopImmediatePropagation();
      return;
    }
    if (!pads.settingsOpen && !pads.calibrating) {
      pads.openSettings();
      renderSound();
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);
  document.querySelector("#settings") && document.querySelector("#settings").addEventListener("click", renderSound);

  // --- Credits overlay ----------------------------------------------------

  const docs = [
    { title: "About and source offer", text: null },
    { title: "Quintra license map", url: "licenses/QUINTRA-LICENSE-MAP.md" },
    { title: "Desktop wrapper notices", url: "licenses/DESKTOP-NOTICES.md" },
    { title: "WasmBoy (GPL-3.0-or-later)", url: "licenses/THIRD-PARTY-NOTICES.md" },
    { title: "GPL-3.0 license text", url: "licenses/GPL-3.0-or-later.txt" },
    { title: "Cartridge notices (GBDK, SDCC)", url: "licenses/CARTRIDGE-THIRD-PARTY-NOTICES.md" },
    { title: "GBDK-2020 license", url: "licenses/GBDK-2020-4.5.0-GPLV2-LE.txt" },
    { title: "SDCC runtime notice", url: "licenses/SDCC-runtime-notice.txt" },
    { title: "Electron (MIT)", url: "licenses/ELECTRON-LICENSE.txt", chromium: true }
  ];

  const overlay = document.createElement("div");
  overlay.id = "desktop-credits";
  overlay.className = "desktop-credits";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-label", "Credits and licenses");
  overlay.hidden = true;
  overlay.innerHTML = `
    <div class="desktop-credits-card">
      <div class="desktop-credits-head">
        <button type="button" class="desktop-credits-nav" data-dir="-1" aria-label="Previous">◀</button>
        <h2 id="desktop-credits-title"></h2>
        <button type="button" class="desktop-credits-nav" data-dir="1" aria-label="Next">▶</button>
      </div>
      <pre id="desktop-credits-body" tabindex="0"></pre>
      <div class="desktop-credits-foot">
        <button type="button" id="desktop-chromium" hidden>Open Chromium licenses (A)</button>
        <span>◀ ▶ switch · ▲ ▼ scroll · B or Esc closes</span>
        <button type="button" id="desktop-credits-close">Close</button>
      </div>
    </div>`;
  document.querySelector("#player-shell").appendChild(overlay);
  const titleEl = overlay.querySelector("#desktop-credits-title");
  const bodyEl = overlay.querySelector("#desktop-credits-body");
  const chromiumButton = overlay.querySelector("#desktop-chromium");
  let creditsOpen = false;
  let docIndex = 0;
  let creditsPoll = 0;
  let prevPad = {};
  let info = null;

  async function aboutText() {
    info = info || await host.info();
    return [
      "QUINTRA",
      "",
      `Desktop build ${info.version} (Electron ${info.electron}, Chromium ${info.chrome}, ${info.platform}).`,
      `Your save file: ${info.savePath}`,
      "",
      "Quintra is a Game Boy Color game. This desktop edition runs the original",
      "cartridge in WasmBoy, a GPL-3.0-or-later emulator, through Quintra's",
      "browser player and desktop wrapper (also GPL-3.0-or-later). The ROM is",
      "independent cartridge data: its software is MPL-2.0 and its art, music",
      "and story are all rights reserved (see the license map).",
      "",
      "SOURCE OFFER",
      "The complete corresponding source for the GPL-covered parts (the browser",
      "player, the desktop wrapper and the WasmBoy fork) is published at:",
      "  https://github.com/struktured-labs/quintra  (web/ and desktop/)",
      "  https://github.com/struktured-labs/wasmboy",
      "For at least three years after we last distribute this version, anyone",
      "may also request that source by opening an issue on the quintra",
      "repository; we will provide it at no more than the cost of distribution.",
      "",
      "Electron and Chromium are distributed under their own licenses; see the",
      "Electron page in this list and the Chromium license file next to the",
      "game's executable (LICENSES.chromium.html)."
    ].join("\n");
  }

  async function renderDoc() {
    const doc = docs[docIndex];
    titleEl.textContent = `${doc.title}  (${docIndex + 1}/${docs.length})`;
    chromiumButton.hidden = !doc.chromium;
    bodyEl.scrollTop = 0;
    try {
      bodyEl.textContent = doc.url ? await (await fetch(doc.url)).text() : await aboutText();
    } catch (error) {
      bodyEl.textContent = `Could not load ${doc.url}`;
    }
  }

  function openCredits() {
    if (creditsOpen) return;
    creditsOpen = true;
    player.closeSettings(false);
    player.setHostOverlay(true);
    overlay.hidden = false;
    renderDoc();
    bodyEl.focus();
    prevPad = {};
    creditsPoll = requestAnimationFrame(pollCredits);
  }

  function closeCredits() {
    if (!creditsOpen) return;
    creditsOpen = false;
    overlay.hidden = true;
    cancelAnimationFrame(creditsPoll);
    player.setHostOverlay(false, false);
    pads.openSettings();
  }

  function step(dir) {
    docIndex = (docIndex + dir + docs.length) % docs.length;
    renderDoc();
  }

  function pollCredits() {
    if (!creditsOpen) return;
    const pad = (navigator.getGamepads ? Array.from(navigator.getGamepads()) : []).find(Boolean);
    if (pad) {
      const layout = pads.layoutFor(pad);
      const pressed = i => !!pad.buttons[i] && (pad.buttons[i].pressed || pad.buttons[i].value > 0.5);
      const axisY = pad.axes[1] || 0;
      const axisX = pad.axes[0] || 0;
      const now = {
        up: pressed(12) || axisY < -0.5, down: pressed(13) || axisY > 0.5,
        left: pressed(14) || axisX < -0.5, right: pressed(15) || axisX > 0.5,
        a: layout.a.some(pressed), b: layout.b.some(pressed) || pressed(layout.start)
      };
      const edge = key => now[key] && !prevPad[key];
      if (now.up) bodyEl.scrollTop -= 18;
      if (now.down) bodyEl.scrollTop += 18;
      if (edge("left")) step(-1);
      if (edge("right")) step(1);
      if (edge("a") && !chromiumButton.hidden) chromiumButton.click();
      if (edge("b")) { closeCredits(); return; }
      prevPad = now;
    }
    creditsPoll = requestAnimationFrame(pollCredits);
  }

  overlay.querySelectorAll(".desktop-credits-nav").forEach(button => {
    button.addEventListener("click", () => step(Number(button.dataset.dir)));
  });
  overlay.querySelector("#desktop-credits-close").addEventListener("click", closeCredits);
  chromiumButton.addEventListener("click", () => host.openChromiumLicenses());
  overlay.addEventListener("keydown", event => {
    if (event.code === "ArrowLeft") { step(-1); event.preventDefault(); }
    else if (event.code === "ArrowRight") { step(1); event.preventDefault(); }
    else if (event.code === "ArrowDown") { bodyEl.scrollTop += 40; event.preventDefault(); }
    else if (event.code === "ArrowUp") { bodyEl.scrollTop -= 40; event.preventDefault(); }
    event.stopPropagation();
  });

  // --- Cursor -------------------------------------------------------------

  let cursorTimer = 0;
  document.addEventListener("mousemove", () => {
    document.documentElement.classList.remove("hide-cursor");
    clearTimeout(cursorTimer);
    cursorTimer = setTimeout(() => document.documentElement.classList.add("hide-cursor"), 2000);
  });

  // --- Start --------------------------------------------------------------

  function whenReady() {
    if (player.ready) return Promise.resolve();
    return new Promise(resolve => window.addEventListener("quintra:ready", resolve, { once: true }));
  }
  whenReady().then(boot).catch(error => {
    state.lastError = String(error && error.stack || error);
    console.error("Desktop boot failed", error);
  });
})();

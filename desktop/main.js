/*
 * Quintra desktop wrapper (Electron main process)
 * Copyright 2026 Quintra contributors
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * Forms one program with the WasmBoy browser player it hosts. No Steamworks
 * SDK is linked. The bundled ROM is independent cartridge data.
 */
"use strict";

const { app, BrowserWindow, protocol, session, ipcMain, shell, dialog } = require("electron");
const fs = require("fs");
const os = require("os");
const path = require("path");
const crypto = require("crypto");

const SAVE_SIZE = 32 * 1024;
const SCHEME = "app";
const HOST = "quintra";
const ORIGIN = `${SCHEME}://${HOST}`;

function argValue(name) {
  const prefix = `--${name}=`;
  const hit = process.argv.find(arg => arg.startsWith(prefix));
  return hit ? hit.slice(prefix.length) : null;
}

// Test-only switches (self-test output, profile and save overrides, DevTools)
// are ignored in packaged builds unless the self-test harness opts in through
// the environment, so a Steam launch option cannot redirect saves or files.
const allowTestArgs = !app.isPackaged || process.env.QUINTRA_ALLOW_SELFTEST === "1";
const testArg = name => (allowTestArgs ? argValue(name) : null);
const selftestDir = testArg("quintra-selftest");
const userDataOverride = testArg("quintra-user-data");
const saveDirOverride = testArg("quintra-save-dir");

app.setName("Quintra");
if (userDataOverride) app.setPath("userData", path.resolve(userDataOverride));
// Start with sound: there is no click-to-play screen on desktop.
app.commandLine.appendSwitch("autoplay-policy", "no-user-gesture-required");
// Keep the emulator and audio running when the window is not focused.
app.commandLine.appendSwitch("disable-renderer-backgrounding");
app.commandLine.appendSwitch("disable-background-timer-throttling");

// The Linux depot's `quintra` launcher script passes --no-sandbox on the real
// command line (Chromium decides before this file runs); this is a backstop.
// Steam depots do not keep the setuid bit on chrome-sandbox, and Steam's
// Linux runtime container may block user namespaces. Without either, Chromium
// aborts at startup. The app loads only bundled local content and blocks all
// network requests, so fall back to running without the OS-level sandbox.
if (process.platform === "linux") {
  let suidOk = false;
  try {
    const helper = fs.statSync(path.join(path.dirname(process.execPath), "chrome-sandbox"));
    suidOk = helper.uid === 0 && (helper.mode & 0o4000) !== 0;
  } catch (error) { /* no helper */ }
  if (!suidOk) app.commandLine.appendSwitch("no-sandbox");
}

protocol.registerSchemesAsPrivileged([{
  scheme: SCHEME,
  privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true, stream: true }
}]);

// --- Paths ----------------------------------------------------------------

function saveDir() {
  if (saveDirOverride) return path.resolve(saveDirOverride);
  if (process.platform === "win32") {
    // %APPDATA% (Roaming): Steam Auto-Cloud root WinAppDataRoaming.
    return path.join(app.getPath("appData"), "Quintra", "saves");
  }
  // Steam Auto-Cloud root LinuxXdgDataHome.
  const dataHome = process.env.XDG_DATA_HOME && path.isAbsolute(process.env.XDG_DATA_HOME)
    ? process.env.XDG_DATA_HOME
    : path.join(os.homedir(), ".local", "share");
  return path.join(dataHome, "Quintra", "saves");
}

const savePath = () => path.join(saveDir(), "quintra.sav");
const settingsPath = () => path.join(app.getPath("userData"), "desktop-settings.json");
const webRoot = () => path.join(__dirname, "app");

function chromiumLicensePath() {
  // electron-builder places LICENSES.chromium.html next to the executable.
  const exeDir = path.dirname(process.execPath);
  const candidates = [
    path.join(exeDir, "LICENSES.chromium.html"),
    path.join(process.resourcesPath || exeDir, "..", "LICENSES.chromium.html")
  ];
  return candidates.find(file => fs.existsSync(file)) || null;
}

// --- Settings -------------------------------------------------------------

function readSettings() {
  try {
    const parsed = JSON.parse(fs.readFileSync(settingsPath(), "utf8"));
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (error) {
    return {};
  }
}

function writeSettings(patch) {
  const next = { ...readSettings(), ...patch };
  try {
    fs.mkdirSync(path.dirname(settingsPath()), { recursive: true });
    const temp = `${settingsPath()}.tmp`;
    fs.writeFileSync(temp, JSON.stringify(next, null, 2));
    fs.renameSync(temp, settingsPath());
  } catch (error) {
    console.error("Could not write desktop settings", error);
  }
}

// --- Save file ------------------------------------------------------------

function readSaveFile(file) {
  try {
    const bytes = fs.readFileSync(file);
    return bytes.length === SAVE_SIZE ? bytes : null;
  } catch (error) {
    return null;
  }
}

const isBlankSave = bytes => bytes.every(v => v === 0) || bytes.every(v => v === 0xff);

// Prefer the main file. Fall back to the backup when the main file is
// missing, the wrong size, or blank while the backup still holds data.
function readSave() {
  const main = readSaveFile(savePath());
  const backup = readSaveFile(`${savePath()}.bak`);
  if (main && (!isBlankSave(main) || !backup || isBlankSave(backup))) return main;
  return backup || main;
}

function syncDir(dir) {
  if (process.platform === "win32") return;
  try {
    const fd = fs.openSync(dir, "r");
    try { fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
  } catch (error) { /* best effort */ }
}

function writeSave(bytes) {
  if (!Buffer.isBuffer(bytes) || bytes.length !== SAVE_SIZE) {
    throw new Error(`Save must be exactly ${SAVE_SIZE} bytes`);
  }
  const file = savePath();
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const current = readSaveFile(file);
  if (current && current.equals(bytes)) return false;
  // One fixed temp name: the single-instance lock means one writer.
  const temp = `${file}.tmp`;
  const fd = fs.openSync(temp, "w");
  try {
    fs.writeSync(fd, bytes, 0, bytes.length, 0);
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
  if (current) {
    try { fs.copyFileSync(file, `${file}.bak`); } catch (error) { /* best effort */ }
  }
  fs.renameSync(temp, file);
  syncDir(path.dirname(file));
  return true;
}

// --- Protocol and offline policy ------------------------------------------

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json",
  ".wasm": "application/wasm",
  ".png": "image/png",
  ".gbc": "application/octet-stream",
  ".md": "text/plain; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".sha256": "text/plain; charset=utf-8"
};

const blockedRequests = [];

function serveApp(request) {
  const url = new URL(request.url);
  if (url.host !== HOST) return new Response("Not found", { status: 404 });
  let rel;
  try {
    rel = decodeURIComponent(url.pathname);
  } catch (error) {
    return new Response("Bad request", { status: 400 });
  }
  if (rel.endsWith("/")) rel += "index.html";
  const root = webRoot();
  const file = path.resolve(root, `.${path.posix.normalize(`/${rel}`)}`);
  const inside = path.relative(root, file);
  if (!inside || inside.startsWith("..") || path.isAbsolute(inside)) {
    return new Response("Forbidden", { status: 403 });
  }
  try {
    const body = fs.readFileSync(file);
    const type = MIME[path.extname(file).toLowerCase()] || "application/octet-stream";
    return new Response(body, {
      status: 200,
      headers: {
        "content-type": type,
        "cache-control": "no-store",
        "content-security-policy":
          "default-src 'self' app: data: blob:; script-src 'self' app: 'wasm-unsafe-eval' blob:; " +
          "worker-src 'self' app: blob: data:; style-src 'self' app: 'unsafe-inline'; img-src 'self' app: data: blob:; " +
          "connect-src 'self' app: data: blob:; media-src 'self' app: blob: data:; " +
          "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
      }
    });
  } catch (error) {
    return new Response("Not found", { status: 404 });
  }
}

function lockDownSession(ses) {
  ses.webRequest.onBeforeRequest((details, callback) => {
    const allowed = /^(app|data|blob|devtools):/i.test(details.url);
    if (!allowed) blockedRequests.push(details.url);
    callback({ cancel: !allowed });
  });
  ses.setPermissionRequestHandler((webContents, permission, callback) => {
    callback(permission === "fullscreen");
  });
}

// --- Window ---------------------------------------------------------------

let mainWindow = null;
let quitting = false;

function createWindow() {
  const settings = readSettings();
  const fullscreen = selftestDir ? true : settings.fullscreen !== false;
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 480,
    minHeight: 432,
    fullscreen,
    backgroundColor: "#000000",
    autoHideMenuBar: true,
    title: "Quintra",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      spellcheck: false,
      backgroundThrottling: false,
      devTools: !app.isPackaged || !!selftestDir
    }
  });
  mainWindow.setMenu(null);
  mainWindow.once("ready-to-show", () => mainWindow.show());

  const contents = mainWindow.webContents;
  contents.setWindowOpenHandler(() => ({ action: "deny" }));
  contents.on("will-navigate", (event, url) => {
    if (!url.startsWith(`${ORIGIN}/`)) event.preventDefault();
  });
  contents.on("before-input-event", (event, input) => {
    if (input.type !== "keyDown") return;
    const toggle = input.key === "F11" || (input.alt && (input.key === "Enter" || input.code === "Enter"));
    if (toggle) {
      event.preventDefault();
      setFullscreen(!mainWindow.isFullScreen());
    }
  });
  const notify = () => contents.send("quintra:fullscreen", mainWindow.isFullScreen());
  mainWindow.on("enter-full-screen", notify);
  mainWindow.on("leave-full-screen", notify);

  mainWindow.on("close", event => {
    if (quitting) return;
    event.preventDefault();
    flushThenQuit();
  });

  const query = selftestDir ? "?selftest=1" : "";
  mainWindow.loadURL(`${ORIGIN}/index.html${query}`);
  return mainWindow;
}

function setFullscreen(on) {
  if (!mainWindow) return false;
  mainWindow.setFullScreen(!!on);
  if (!selftestDir) writeSettings({ fullscreen: !!on });
  return !!on;
}

// Ask the renderer to write the latest cartridge RAM, then exit. A renderer
// that is stuck or gone cannot block the quit for more than 3 s.
let flushPromise = null;
function flushThenQuit() {
  if (flushPromise) return flushPromise;
  flushPromise = (async () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      const contents = mainWindow.webContents;
      await new Promise(resolve => {
        const done = () => {
          clearTimeout(timer);
          ipcMain.removeListener("quintra:flushed", done);
          resolve();
        };
        const timer = setTimeout(done, 3000);
        ipcMain.on("quintra:flushed", done);
        contents.send("quintra:flush");
      });
    }
    quitting = true;
    app.quit();
  })();
  return flushPromise;
}

// --- IPC ------------------------------------------------------------------

// Only the game page may call the host API.
function fromApp(event) {
  const url = event.senderFrame && event.senderFrame.url;
  return typeof url === "string" && url.startsWith(`${ORIGIN}/`);
}

function guard(channel, handler) {
  ipcMain.handle(channel, (event, ...args) => {
    if (!fromApp(event)) throw new Error("Rejected IPC sender");
    return handler(event, ...args);
  });
}

function registerIpc() {
  guard("quintra:read-save", () => {
    const bytes = readSave();
    return bytes ? new Uint8Array(bytes) : null;
  });
  guard("quintra:write-save", (event, data) => {
    const bytes = Buffer.from(data instanceof Uint8Array ? data : new Uint8Array(data || []));
    return writeSave(bytes);
  });
  guard("quintra:get-fullscreen", () => (mainWindow ? mainWindow.isFullScreen() : false));
  guard("quintra:set-fullscreen", (event, on) => setFullscreen(on));
  guard("quintra:quit", () => { flushThenQuit(); });
  guard("quintra:info", () => ({
    version: app.getVersion(),
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    platform: process.platform,
    savePath: savePath(),
    selftest: !!selftestDir,
    chromiumLicenses: !!chromiumLicensePath()
  }));
  guard("quintra:open-chromium-licenses", async () => {
    const file = chromiumLicensePath();
    if (!file) return false;
    const viewer = new BrowserWindow({
      width: 960, height: 720, parent: mainWindow, title: "Chromium licenses", autoHideMenuBar: true,
      webPreferences: { sandbox: true, contextIsolation: true, javascript: false }
    });
    viewer.setMenu(null);
    viewer.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
    viewer.webContents.on("will-navigate", event => event.preventDefault());
    await viewer.loadFile(file);
    return true;
  });
}

// --- Self-test (CI / headless only; enabled by --quintra-selftest=DIR) ------

async function runSelftest(window) {
  const outDir = path.resolve(selftestDir);
  fs.mkdirSync(outDir, { recursive: true });
  const contents = window.webContents;
  const report = { ok: false, steps: [], savePath: savePath() };
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  const js = code => contents.executeJavaScript(code, true);
  const shot = async name => {
    const image = await contents.capturePage();
    const file = path.join(outDir, name);
    fs.writeFileSync(file, image.toPNG());
    const size = image.getSize();
    report.steps.push({ shot: name, width: size.width, height: size.height });
    return image;
  };
  const hash = image => crypto.createHash("sha256").update(image.toBitmap()).digest("hex");
  const press = async (keyCode, ms = 120) => {
    contents.sendInputEvent({ type: "keyDown", keyCode });
    await wait(ms);
    contents.sendInputEvent({ type: "keyUp", keyCode });
  };
  try {
    const mode = argValue("quintra-selftest-mode") || "full";
    for (let i = 0; i < 300; i++) {
      if (await js("!!(window.QuintraDesktopState && window.QuintraDesktopState.running)")) break;
      await wait(100);
    }
    const state = await js("JSON.parse(JSON.stringify(window.QuintraDesktopState || {}))");
    report.steps.push({ state, fullscreen: window.isFullScreen() });
    if (!state.running) throw new Error("player never reached running state");

    if (mode === "verify-save") {
      // Run 2: the RAM WasmBoy started with must be the disk file.
      const disk = readSave();
      const ramHex = state.bootRamSha256;
      const diskHex = disk ? crypto.createHash("sha256").update(disk).digest("hex") : null;
      report.steps.push({ bootRamSha256: ramHex, diskSha256: diskHex, loadedFromDisk: state.loadedFromDisk });
      if (!disk || ramHex !== diskHex || !state.loadedFromDisk) throw new Error("disk save was not loaded into cartridge RAM");
      report.ok = true;
      return;
    }

    await wait(3000);
    const boot = await shot("boot.png");
    await press("Enter");
    await wait(2500);
    const title = await shot("title.png");
    await press("Enter");
    await wait(2500);
    await press("Enter");
    await wait(3000);
    await shot("play.png");
    report.steps.push({ titleChanged: hash(boot) !== hash(title) });

    // Simulated gamepads: label-correct layouts in the real renderer, then a
    // virtual pad's Start must reach the emulator (frame changes).
    const pad = await js(`(async () => {
      const mk = (id, mapping, pressed) => ({
        id, index: 0, connected: true, mapping, timestamp: performance.now(), axes: [0, 0, 0, 0],
        buttons: Array.from({ length: 17 }, (_, i) => ({ pressed: pressed.includes(i), touched: false, value: pressed.includes(i) ? 1 : 0 }))
      });
      const xbox = mk("Xbox Wireless Controller (STANDARD GAMEPAD Vendor: 045e Product: 0b13)", "standard", []);
      const pro = mk("Pro Controller (STANDARD GAMEPAD Vendor: 057e Product: 2009)", "standard", []);
      const lx = window.QuintraPads.layoutFor(xbox), lp = window.QuintraPads.layoutFor(pro);
      return { xboxA: lx.a, xboxB: lx.b, proA: lp.a, proB: lp.b, xboxFamily: window.QuintraPads.familyOf(xbox), proFamily: window.QuintraPads.familyOf(pro) };
    })()`);
    report.steps.push({ padLayouts: pad });
    const layoutsOk = pad.xboxA[0] === 0 && pad.xboxB[0] === 1 && pad.proA[0] === 1 && pad.proB[0] === 0;
    if (!layoutsOk) throw new Error("gamepad layouts are not label-correct");

    // End to end through WasmBoy: a virtual Xbox pad's D-pad moves the hero
    // cursor, then a virtual Switch Pro's east button (labelled A on that
    // pad) chooses the hero.
    await js(`(() => {
      const ids = {
        xbox: "Xbox Wireless Controller (STANDARD GAMEPAD Vendor: 045e Product: 0b13)",
        pro: "Pro Controller (STANDARD GAMEPAD Vendor: 057e Product: 2009)"
      };
      let kind = "xbox";
      let held = -1;
      const make = () => ({
        id: ids[kind], index: 0, connected: true, mapping: "standard", timestamp: performance.now(), axes: [0, 0, 0, 0],
        buttons: Array.from({ length: 17 }, (_, i) => ({ pressed: i === held, touched: false, value: i === held ? 1 : 0 }))
      });
      navigator.getGamepads = () => [make(), null, null, null];
      window.__quintraVirtualPad = { use(k) { kind = k; }, hold(i) { held = i; } };
      window.dispatchEvent(Object.assign(new Event("gamepadconnected"), { gamepad: make() }));
    })()`);
    const tap = async (button) => {
      await js(`window.__quintraVirtualPad.hold(${button})`);
      await wait(200);
      await js("window.__quintraVirtualPad.hold(-1)");
      await wait(1200);
    };
    await wait(400);
    const beforePad = await shot("pad-before.png");
    await tap(13);
    const afterDown = await shot("pad-xbox-down.png");
    await js("window.__quintraVirtualPad.use('pro')");
    await wait(300);
    await tap(1);
    await wait(1200);
    const afterA = await shot("pad-pro-a.png");
    const padDown = hash(beforePad) !== hash(afterDown);
    const padA = hash(afterDown) !== hash(afterA);
    report.steps.push({ virtualXboxDownMovedCursor: padDown, virtualProEastAChose: padA });
    if (!padDown || !padA) throw new Error("virtual gamepad input did not reach the game");

    // Settings (Esc), credits overlay, and the windowed toggle.
    await press("Escape");
    await wait(600);
    await shot("settings.png");
    const settingsOpen = await js("window.QuintraPads.settingsOpen");
    await js("document.querySelector('#desktop-credits-item').click()");
    await wait(800);
    await shot("credits.png");
    await press("ArrowRight");
    await wait(600);
    await shot("credits-license-map.png");
    const creditsOpen = await js("!document.querySelector('#desktop-credits').hidden");
    await press("Escape");
    await wait(400);
    await press("Escape");
    await wait(400);
    setFullscreen(false);
    await wait(1200);
    const windowed = !window.isFullScreen();
    await shot("windowed.png");
    setFullscreen(true);
    await wait(1200);
    report.steps.push({ settingsOpen, creditsOpen, windowedToggle: windowed, backToFullscreen: window.isFullScreen() });
    if (!settingsOpen || !creditsOpen || !windowed) throw new Error("settings, credits or windowed toggle failed");

    // Save round-trip, run 1: pattern -> cartridge RAM -> disk file.
    const pattern = Buffer.alloc(SAVE_SIZE);
    for (let i = 0; i < SAVE_SIZE; i++) pattern[i] = (i * 31 + 7) & 0xff;
    const patternHex = crypto.createHash("sha256").update(pattern).digest("hex");
    await js(`window.QuintraDesktopTest.importAndFlush(new Uint8Array([${Array.from(pattern).join(",")}]))`);
    const disk = readSave();
    const diskHex = disk ? crypto.createHash("sha256").update(disk).digest("hex") : null;
    report.steps.push({ patternSha256: patternHex, diskSha256: diskHex });
    if (diskHex !== patternHex) throw new Error("save file on disk does not match cartridge RAM");

    report.blockedRequests = blockedRequests.slice();
    report.ok = true;
  } catch (error) {
    report.error = String(error && error.stack || error);
  } finally {
    report.blockedRequests = blockedRequests.slice();
    fs.writeFileSync(path.join(outDir, `report-${argValue("quintra-selftest-mode") || "full"}.json`), JSON.stringify(report, null, 2));
    await flushThenQuit();
  }
}

// --- Boot -----------------------------------------------------------------

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(() => {
    protocol.handle(SCHEME, serveApp);
    lockDownSession(session.defaultSession);
    registerIpc();
    const window = createWindow();
    if (selftestDir) window.webContents.once("did-finish-load", () => runSelftest(window));
  });

  app.on("window-all-closed", () => app.quit());

  // Steam (Deck "Exit Game", Stop) and session logout end the game with a
  // signal; write the latest save before going.
  for (const signal of ["SIGTERM", "SIGINT", "SIGHUP"]) {
    process.on(signal, () => { flushThenQuit(); });
  }
}

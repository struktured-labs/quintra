#!/usr/bin/env node
// Per-controller "press the button labelled A" calibration, the Settings
// panel (one Swap A/B preference, recalibrate, reset, display), and their
// interaction: calibration fixes the controller, Swap A/B is a preference
// applied once on top (never a double swap).
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const playerPath = process.argv[2];
if (!playerPath) throw new Error("usage: test_itch_pad_calibration.mjs PLAYER_JS");
const source = fs.readFileSync(playerPath, "utf8");

function element(id, extra = {}) {
  const listeners = new Map();
  const attrs = new Map();
  const classes = new Set();
  return Object.assign({
    id, disabled: false, hidden: false, value: "", files: [], dataset: {}, style: {},
    textContent: "", children: [], focused: false,
    classList: {
      toggle(name, force) { if (force) classes.add(name); else classes.delete(name); },
      contains(name) { return classes.has(name); }
    },
    addEventListener(type, cb) { listeners.set(type, cb); },
    dispatch(type, event = {}) { const cb = listeners.get(type); if (cb) cb(event); },
    click() { this.dispatch("click", {}); },
    setAttribute(name, value) { attrs.set(name, String(value)); },
    getAttribute(name) { return attrs.get(name); },
    appendChild(child) { this.children.push(child); return child; },
    setPointerCapture() {}, focus() { this.focused = true; },
    querySelector() { return element(); },
    requestFullscreen: async () => {}
  }, extra);
}

function makeStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return { data, getItem: k => (data.has(k) ? data.get(k) : null), setItem: (k, v) => { data.set(k, String(v)); } };
}

const btn = pressed => ({ pressed, value: pressed ? 1 : 0 });
function pad({ id, mapping = "standard", buttons = 17, index = 0 }) {
  return { index, id, mapping, buttons: Array.from({ length: buttons }, () => btn(false)), axes: [0, 0, 0, 0] };
}
function press(p, ...indices) { p.buttons.forEach((_, i) => { p.buttons[i] = btn(indices.includes(i)); }); }

async function loadPlayer({ pads, search = "", store = makeStorage(), clock = { t: 1000 } }) {
  const elements = new Map();
  for (const id of [
    "game", "player-shell", "launch", "status", "mute", "fullscreen", "export-save", "import-save",
    "save-file", "gamepad-status", "settings", "settings-close", "settings-status", "recalibrate",
    "reset-mapping", "swap-ab", "pad-calibration", "pad-calibration-title", "pad-calibration-detail",
    "pad-calibration-skip", "player-stage", "screen-wrap"
  ]) elements.set(`#${id}`, element(id));
  elements.get("#settings-panel") || elements.set("#settings-panel", element("settings-panel"));
  elements.get("#pad-calibration").hidden = true;
  elements.get("#settings-panel").hidden = true;
  const displayButtons = ["fit", "integer", "stretch"].map(mode => {
    const e = element(`display-${mode}`); e.dataset = { displayMode: mode }; return e;
  });
  const items = [elements.get("#swap-ab"), ...displayButtons, elements.get("#recalibrate"),
    elements.get("#reset-mapping"), elements.get("#settings-close")];
  elements.get("#settings-panel").querySelectorAll = sel => (sel === ".settings-item" ? items : []);
  const docListeners = new Map();
  let playing = false;
  const responsiveGamepad = {
    Gamepad: { getState: () => ({ A: true, B: true }) }, // must be silenced
    getState() {
      const g = this.Gamepad.getState() || {};
      return { UP: false, RIGHT: false, DOWN: false, LEFT: false, A: !!g.A, B: !!g.B, SELECT: false, START: false };
    }
  };
  const api = {
    ResponsiveGamepad: responsiveGamepad,
    config: async () => {}, loadROM: async () => {}, resumeAudioContext: async () => {},
    play: async () => { playing = true; }, pause: async () => { playing = false; },
    isPlaying: () => playing, saveLoadedCartridge: async () => {},
    _getAudioChannels: () => ({ master: { mute() {}, unmute() {} } })
  };
  const FakeDate = { now: () => clock.t };
  const win = { WasmBoy: { WasmBoy: api }, addEventListener() {} };
  const context = {
    console: { log: console.log, error: console.error, warn() {} },
    Uint8Array, Blob, URL, URLSearchParams, JSON, Date: FakeDate,
    location: { search }, localStorage: store,
    navigator: { getGamepads: () => pads },
    document: {
      body: element("body"),
      createElement: tag => element(tag),
      querySelector: s => elements.get(s),
      querySelectorAll: s => (s === "[data-display-mode]" ? displayButtons : []),
      addEventListener(type, cb) { docListeners.set(type, [...(docListeners.get(type) || []), cb]); },
      documentElement: {
        getAttribute(name) {
          return name === "data-quintra-build" ? "" : null;
        }
      },
      fullscreenElement: null, visibilityState: "visible"
    },
    window: win
  };
  vm.runInNewContext(source, context, { filename: playerPath });
  await new Promise(resolve => setImmediate(resolve));
  return {
    state: () => responsiveGamepad.getState(), hooks: win.QuintraPads, elements, store, clock,
    body: context.document.body,
    displayButtons, key: code => (docListeners.get("keydown") || []).forEach(cb => cb({ code, preventDefault() {} })),
    setPlaying: v => { playing = v; }, isPlaying: () => playing
  };
}
const gb = s => (s.A && s.B ? "A+B" : s.A ? "A" : s.B ? "B" : "-");

// Unknown pad whose raw order is by label (0 = A, 1 = B): the positional
// default would be backwards, so the player prompts and records it.
{
  const p = pad({ id: "Wireless Gamepad (Vendor: 1234 Product: 5678)" });
  const player = await loadPlayer({ pads: [p] });
  assert.equal(player.hooks.familyOf(p), "unknown");
  player.state(); // first frame sees the unknown pad
  assert.equal(player.hooks.calibrating, "A", "unknown pad should be prompted for A");
  assert.equal(player.elements.get("#pad-calibration").hidden, false, "calibration overlay should show");
  assert.match(player.elements.get("#pad-calibration-title").textContent, /labelled A/);
  player.hooks.tick(); // all buttons up: armed
  press(p, 0);
  assert.equal(gb(player.state()), "-", "pad input must not reach the game while calibrating");
  player.hooks.tick();
  assert.equal(player.hooks.calibrating, "B", "A recorded, now asks for B");
  assert.match(player.elements.get("#pad-calibration-title").textContent, /labelled B/);
  player.hooks.tick(); // still holding: wait for release
  press(p); player.hooks.tick();
  press(p, 1); player.hooks.tick();
  assert.equal(player.hooks.calibrating, null, "calibration should finish after B");
  assert.equal(player.elements.get("#pad-calibration").hidden, true);
  const saved = JSON.parse(player.store.getItem("quintra.padmap.v1"))[p.id];
  assert.equal(saved.a, 0); assert.equal(saved.b, 1);
  assert.equal(gb(player.state()), "-", "the answering press should not leak into the game");
  press(p); player.state();
  press(p, 0); assert.equal(gb(player.state()), "A", "calibrated label A -> GB A");
  press(p, 1); assert.equal(gb(player.state()), "B", "calibrated label B -> GB B");
  press(p, 2); assert.equal(gb(player.state()), "-", "calibration replaces the positional X/Y aliases");

  // Persistence: a new page load uses the saved mapping without prompting.
  const again = await loadPlayer({ pads: [p], store: player.store });
  press(p); again.state();
  assert.equal(again.hooks.calibrating, null, "saved calibration should not prompt again");
  press(p, 0); assert.equal(gb(again.state()), "A");
  assert.match(again.elements.get("#gamepad-status").textContent, /calibrated/);

  // Swap A/B preference on top of calibration: applied exactly once.
  again.elements.get("#swap-ab").click();
  assert.equal(again.store.getItem("quintra.swapAB"), "1");
  assert.match(again.elements.get("#swap-ab").textContent, /On/);
  press(p, 0); assert.equal(gb(again.state()), "B", "swap flips calibrated A once");
  press(p, 1); assert.equal(gb(again.state()), "A", "swap flips calibrated B once");
  const viaParam = await loadPlayer({ pads: [p], store: again.store, search: "?swapab=0" });
  press(p, 0); assert.equal(gb(viaParam.state()), "A", "?swapab=0 overrides the stored preference");
  assert.equal(viaParam.store.getItem("quintra.swapAB"), "0");

  // Reset clears saved mappings; the pad is prompted again.
  viaParam.hooks.resetMapping();
  assert.equal(viaParam.store.getItem("quintra.padmap.v1"), "{}");
  press(p); viaParam.state();
  assert.equal(viaParam.hooks.calibrating, "A", "reset should re-offer calibration");
  viaParam.key("Escape");
  assert.equal(viaParam.hooks.calibrating, null, "Esc skips calibration");
  assert.equal(JSON.parse(viaParam.store.getItem("quintra.padmap.v1"))[p.id].skipped, true);
  press(p, 0); viaParam.state(); press(p); viaParam.state();
  press(p, 0); assert.equal(gb(viaParam.state()), "A", "skipped pad falls back to positional");
  const later = await loadPlayer({ pads: [p], store: viaParam.store });
  press(p); later.state();
  assert.equal(later.hooks.calibrating, null, "a skipped pad is not nagged again");
}

// Known families are not prompted; a manual recalibration still wins.
{
  const p = pad({ id: "Pro Controller (STANDARD GAMEPAD Vendor: 057e Product: 2009)" });
  const player = await loadPlayer({ pads: [p] });
  player.state();
  assert.equal(player.hooks.calibrating, null, "Nintendo pads use their label default");
  press(p, 1); assert.equal(gb(player.state()), "A");
  // Recalibrate from Settings: this car reports A at 0, B at 1.
  press(p); player.state();
  player.elements.get("#settings").click();
  assert.equal(player.hooks.settingsOpen, true);
  player.elements.get("#recalibrate").click();
  assert.equal(player.hooks.settingsOpen, false, "recalibrate closes settings");
  assert.equal(player.hooks.calibrating, "A");
  player.hooks.tick();
  press(p, 0); player.hooks.tick();
  press(p); player.hooks.tick();
  press(p, 1); player.hooks.tick();
  press(p); player.state();
  press(p, 0); assert.equal(gb(player.state()), "A", "calibration overrides the Nintendo default");
  press(p, 1); assert.equal(gb(player.state()), "B");
  assert.equal(player.hooks.layoutFor(p).source, "calibrated");
}

// Timeout: never blocks play. A recorded A with no B infers the partner.
{
  const clock = { t: 1000 };
  const p = pad({ id: "Mystery Pad" });
  const player = await loadPlayer({ pads: [p], clock });
  player.state();
  assert.equal(player.hooks.calibrating, "A");
  player.hooks.tick();
  press(p, 1); player.hooks.tick();
  press(p); player.hooks.tick();
  clock.t += 21000; player.hooks.tick();
  assert.equal(player.hooks.calibrating, null, "calibration times out");
  const saved = JSON.parse(player.store.getItem("quintra.padmap.v1"))["Mystery Pad"];
  assert.deepEqual([saved.a, saved.b], [1, 0], "B is inferred as the other face button");
  const q = pad({ id: "Silent Pad" });
  const other = await loadPlayer({ pads: [q], clock });
  other.state();
  clock.t += 21000; other.hooks.tick();
  assert.equal(other.hooks.calibrating, null, "an unanswered prompt also times out");
  assert.equal(JSON.parse(other.store.getItem("quintra.padmap.v1"))["Silent Pad"].skipped, true);
  other.elements.get("#pad-calibration-skip").click(); // harmless when idle
}

// Settings panel: gamepad navigation, display choice, chord to open,
// launch is not triggered by panel input, keyboard Esc closes.
{
  const clock = { t: 5000 };
  const p = pad({ id: "Xbox Wireless Controller (STANDARD GAMEPAD Vendor: 045e)" });
  const player = await loadPlayer({ pads: [p], clock });
  player.elements.get("#launch").click();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(player.isPlaying(), true, "launch starts the game");
  player.state();
  // Hold Select + Start for half a second.
  press(p, 8, 9); player.state();
  clock.t += 600; player.state();
  assert.equal(player.hooks.settingsOpen, true, "Select + Start hold opens settings");
  assert.equal(player.isPlaying(), false, "settings pause the game");
  assert.equal(player.elements.get("#settings-panel").hidden, false);
  press(p); player.hooks.tick(); // release (suppressed until all up)
  player.hooks.tick();
  press(p, 13); player.hooks.tick(); // D-pad down -> Fit
  press(p); player.hooks.tick();
  press(p, 13); player.hooks.tick(); // -> Integer
  press(p); player.hooks.tick();
  press(p, 0); player.hooks.tick(); // Xbox A (positional GB A) chooses
  assert.equal(player.store.getItem("quintra.display"), "integer", "gamepad picks the display mode");
  assert.equal(player.displayButtons[1].getAttribute("aria-pressed"), "true");
  press(p); player.hooks.tick();
  press(p, 1); player.hooks.tick(); // B closes
  assert.equal(player.hooks.settingsOpen, false, "B closes settings");
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(player.isPlaying(), true, "closing settings resumes the game");
  press(p); player.state();
  player.elements.get("#settings").click();
  player.key("Escape");
  assert.equal(player.hooks.settingsOpen, false, "Esc closes settings");
  // Home button opens it too.
  press(p, 16); player.state();
  assert.equal(player.hooks.settingsOpen, true, "Home opens settings");
  player.hooks.closeSettings();
}

// paddebug shows calibration status and effective mapping (after swap).
{
  const store = makeStorage({
    "quintra.padmap.v1": JSON.stringify({ "Wireless Gamepad": { a: 0, b: 1 } }),
    "quintra.swapAB": "1"
  });
  const p = pad({ id: "Wireless Gamepad" });
  const player = await loadPlayer({ pads: [p], store, search: "?paddebug=1" });
  press(p, 0); player.state();
  const text = player.body.children[0].textContent;
  assert.match(text, /family=unknown calib=saved a=0 b=1/, "overlay shows calibration status");
  assert.match(text, /map\(calibrated\) A=\[1\] B=\[0\]/, "overlay shows the effective mapping after swap");
  assert.match(text, /swapAB=1/);
}
console.log("itch pad calibration + settings checks passed");

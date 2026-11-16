#!/usr/bin/env node
// Issue #69: Nintendo-labelled pads (Switch Pro over Bluetooth, e.g. in the
// Tesla in-car Chromium browser) must map Nintendo A -> GB A and B -> GB B,
// for both "standard" and generic-HID mappings, without changing the
// positional Xbox/PlayStation mapping. Also covers the ?swapab / localStorage
// fallback and the ?paddebug=1 overlay.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const playerPath = process.argv[2];
if (!playerPath) throw new Error("usage: test_itch_gamepad_layouts.mjs PLAYER_JS");
const source = fs.readFileSync(playerPath, "utf8");

function element(id) {
  const listeners = new Map();
  const attrs = new Map();
  const classes = new Set();
  return {
    id, disabled: false, hidden: false, value: "", files: [], dataset: {}, style: {},
    textContent: "", children: [],
    classList: {
      toggle(name, force) { if (force) classes.add(name); else classes.delete(name); },
      contains(name) { return classes.has(name); }
    },
    addEventListener(type, cb) { listeners.set(type, cb); },
    dispatch(type, event = {}) { listeners.get(type)(event); },
    setAttribute(name, value) { attrs.set(name, String(value)); },
    getAttribute(name) { return attrs.get(name); },
    appendChild(child) { this.children.push(child); return child; },
    setPointerCapture() {}, focus() {}, click() {},
    querySelector() { return element(); },
    requestFullscreen: async () => {}
  };
}

function makeStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: key => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => { data.set(key, String(value)); }
  };
}

const btn = pressed => ({ pressed, value: pressed ? 1 : 0 });
function pad({ id, mapping, buttons = 17, axes = 4, index = 0 }) {
  return {
    index, id, mapping,
    buttons: Array.from({ length: buttons }, () => btn(false)),
    axes: Array.from({ length: axes }, () => 0)
  };
}

// Load the player with a WasmBoy stub whose ResponsiveGamepad mimics the
// real one: its built-in Gamepad reads navigator gamepad 0 positionally
// (0 -> A, 1 -> B, 2 -> X -> A, 3 -> Y -> B) and getState ORs it in.
async function loadPlayer({ pads, search = "", store = makeStorage() }) {
  const elements = new Map();
  for (const id of [
    "game", "player-shell", "launch", "status", "mute", "fullscreen", "swap-ab",
    "export-save", "import-save", "save-file", "gamepad-status"
  ]) elements.set(`#${id}`, element(id));
  const body = element("body");
  const getGamepads = () => pads;
  const builtinGamepad = {
    getState() {
      const p = getGamepads()[0];
      if (!p) return false;
      const on = i => !!p.buttons[i] && p.buttons[i].pressed;
      return { A: on(0) || on(2), B: on(1) || on(3), SELECT: on(8), START: on(9),
        DPAD_UP: on(12), DPAD_DOWN: on(13), DPAD_LEFT: on(14), DPAD_RIGHT: on(15) };
    }
  };
  const responsiveGamepad = {
    Gamepad: builtinGamepad,
    getState() {
      const g = this.Gamepad.getState() || {};
      return { UP: !!g.DPAD_UP, RIGHT: !!g.DPAD_RIGHT, DOWN: !!g.DPAD_DOWN, LEFT: !!g.DPAD_LEFT,
        A: !!g.A, B: !!g.B, SELECT: !!g.SELECT, START: !!g.START };
    }
  };
  const api = {
    ResponsiveGamepad: responsiveGamepad,
    config: async () => {}, loadROM: async () => {}, resumeAudioContext: async () => {},
    play: async () => {}, pause: async () => {}, isPlaying: () => false,
    saveLoadedCartridge: async () => {},
    _getAudioChannels: () => ({ master: { mute() {}, unmute() {} } })
  };
  const context = {
    console: { log: console.log, error: console.error, warn() {} },
    Uint8Array, Blob, URL, URLSearchParams,
    location: { search },
    localStorage: store,
    navigator: { getGamepads },
    document: {
      body,
      createElement: tag => element(tag),
      querySelector: selector => elements.get(selector),
      querySelectorAll: () => [],
      addEventListener() {},
      fullscreenElement: null,
      visibilityState: "visible"
    },
    window: { WasmBoy: { WasmBoy: api }, addEventListener() {} }
  };
  vm.runInNewContext(source, context, { filename: playerPath });
  await new Promise(resolve => setImmediate(resolve));
  return { state: () => responsiveGamepad.getState(), elements, body, store, win: context.window };
}

function press(p, index) {
  p.buttons.forEach((_, i) => { p.buttons[i] = btn(i === index); });
}

async function expectFaces(label, p, expected, opts = {}) {
  const player = await loadPlayer({ pads: [p], ...opts });
  for (const [index, want] of Object.entries(expected)) {
    press(p, Number(index));
    const s = player.state();
    const got = s.A && s.B ? "A+B" : s.A ? "A" : s.B ? "B" : "-";
    assert.equal(got, want, `${label}: browser button ${index} should give GB ${want}, got ${got}`);
  }
  press(p, -1);
  return player;
}

// (a) Switch Pro, Chromium standard mapping: 0 = B (south), 1 = A (east),
// 2 = Y (west), 3 = X (north).
await expectFaces("Switch Pro standard",
  pad({ id: "Pro Controller (STANDARD GAMEPAD Vendor: 057e Product: 2009)", mapping: "standard" }),
  { 0: "B", 1: "A", 2: "B", 3: "A" });

// (b) Switch Pro over plain Bluetooth HID (non-standard mapping), as a
// Chromium without a Switch mapper (Tesla) reports it: 0 = B, 1 = A,
// D-pad as a hat on axis 9.
{
  const p = pad({ id: "057e-2009-Pro Controller", mapping: "", buttons: 14, axes: 10 });
  p.axes[9] = 3.285714;
  const player = await expectFaces("Switch Pro generic HID", p, { 0: "B", 1: "A", 9: "-" });
  press(p, 9);
  assert.equal(player.state().START, true, "Switch Pro Plus should reach GB Start");
  press(p, 8);
  assert.equal(player.state().SELECT, true, "Switch Pro Minus should reach GB Select");
  press(p, -1);
  p.axes[9] = -1;
  let s = player.state();
  assert.equal(s.UP, true, "generic-HID Switch Pro hat up should reach GB Up");
  p.axes[9] = 1 / 7;
  s = player.state();
  assert.equal(s.DOWN, true, "generic-HID Switch Pro hat down should reach GB Down");
  p.axes[9] = 3.285714;
  s = player.state();
  assert.equal(s.UP || s.DOWN || s.LEFT || s.RIGHT, false, "neutral hat should not move");
}

// (b2) Linux hid-nintendo evdev order (non-standard): 0 = BTN_SOUTH (B),
// 1 = BTN_EAST (A); D-pad as ABS_HAT0X/Y on axes 4/5.
{
  const p = pad({ id: "Nintendo Co., Ltd. Pro Controller", mapping: "", buttons: 14, axes: 6 });
  const player = await expectFaces("Switch Pro hid-nintendo", p, { 0: "B", 1: "A" });
  p.axes[4] = -1;
  assert.equal(player.state().LEFT, true, "hid-nintendo hat X should reach GB Left");
  p.axes[4] = 0; p.axes[5] = 1;
  assert.equal(player.state().DOWN, true, "hid-nintendo hat Y should reach GB Down");
  p.axes[5] = 0;
  const s = player.state();
  assert.equal(s.UP || s.DOWN || s.LEFT || s.RIGHT, false, "neutral hid-nintendo hat should not move");
  assert.match(player.elements.get("#gamepad-status").textContent, /Nintendo layout/);
}

// Joy-Con pair, standard mapping.
await expectFaces("Joy-Con standard",
  pad({ id: "Joy-Con L+R (STANDARD GAMEPAD Vendor: 057e Product: 200e)", mapping: "standard" }),
  { 0: "B", 1: "A" });

// (c) Xbox standard pad stays positional: south (A) -> GB A, east (B) -> GB B.
{
  const player = await expectFaces("Xbox standard",
    pad({ id: "Xbox Wireless Controller (STANDARD GAMEPAD Vendor: 045e Product: 0b13)", mapping: "standard" }),
    { 0: "A", 1: "B", 2: "A", 3: "B" });
  assert.doesNotMatch(player.elements.get("#gamepad-status").textContent, /Nintendo layout/);
}
// PlayStation standard pad: cross -> GB A, circle -> GB B (unchanged).
await expectFaces("DualSense standard",
  pad({ id: "DualSense Wireless Controller (STANDARD GAMEPAD Vendor: 054c Product: 0ce6)", mapping: "standard" }),
  { 0: "A", 1: "B" });

// Fallback: ?swapab=1 flips A/B for any pad and persists.
{
  const store = makeStorage();
  const player = await expectFaces("Switch Pro standard + ?swapab=1",
    pad({ id: "Pro Controller (STANDARD GAMEPAD Vendor: 057e Product: 2009)", mapping: "standard" }),
    { 0: "A", 1: "B" }, { search: "?swapab=1", store });
  assert.equal(store.getItem("quintra.swapAB"), "1", "?swapab=1 should persist");
  assert.equal(player.elements.get("#swap-ab").getAttribute("aria-pressed"), "true");
  assert.match(player.elements.get("#gamepad-status").textContent, /A\/B swapped/);
}
{
  const store = makeStorage({ "quintra.swapAB": "1" });
  const p = pad({ id: "Xbox Wireless Controller", mapping: "standard" });
  const player = await expectFaces("Xbox + stored swap", p, { 0: "B", 1: "A" }, { store });
  player.elements.get("#swap-ab").dispatch("click");
  assert.equal(store.getItem("quintra.swapAB"), "0", "toggle should persist off");
  press(p, 0);
  assert.equal(player.state().A, true, "toggling swap off should restore positional A");
  assert.equal(player.state().B, false);
}
{
  const store = makeStorage({ "quintra.swapAB": "1" });
  await expectFaces("?swapab=0 clears stored swap",
    pad({ id: "Xbox Wireless Controller", mapping: "standard" }), { 0: "A" },
    { search: "?swapab=0", store });
  assert.equal(store.getItem("quintra.swapAB"), "0");
}

// Debug overlay: hidden by default, shown with ?paddebug=1.
{
  const p = pad({ id: "057e-2009-Pro Controller", mapping: "", buttons: 14, axes: 10 });
  p.axes[9] = 3.285714;
  const quiet = await loadPlayer({ pads: [p] });
  quiet.state();
  assert.equal(quiet.body.children.length, 0, "no debug overlay without ?paddebug=1");

  const debug = await loadPlayer({ pads: [p], search: "?paddebug=1" });
  press(p, 1);
  debug.state();
  assert.equal(debug.body.children.length, 1, "?paddebug=1 should add one overlay");
  const text = debug.body.children[0].textContent;
  assert.match(text, /057e-2009-Pro Controller/, "overlay should show gamepad.id");
  assert.match(text, /mapping=""/, "overlay should show gamepad.mapping");
  assert.match(text, /pressed=\[1\]/, "overlay should show pressed raw indices");
  assert.match(text, /GB: A\b/, "overlay should show the mapped GB button");
  debug.state();
  assert.equal(debug.body.children.length, 1, "overlay should be reused, not duplicated");
}

console.log("itch gamepad layout checks passed: Switch Pro standard/HID/evdev, Joy-Con, Xbox, DualSense, swapab, paddebug");

// Display fit math (issue: windowed Tesla browser cut the game off).
{
  const store = makeStorage();
  const player = await loadPlayer({ pads: [], search: "?display=integer", store });
  const display = player.win.QuintraDisplay;
  assert.ok(display, "player should expose QuintraDisplay");
  assert.equal(display.mode, "integer", "?display=integer should select integer mode");
  assert.equal(store.getItem("quintra.display"), "integer", "?display should persist");
  const fit = (w, h, m) => display.computeGameRect(w, h, m);
  assert.deepEqual({ ...fit(640, 600, "fit") }, { width: 640, height: 576, scale: 4 }, "4x fits exactly");
  assert.deepEqual({ ...fit(700, 620, "fit") }, { width: 640, height: 576, scale: 4 },
    "fit snaps to integer when it keeps >= 85% of the size");
  const frac = fit(780, 780, "fit");
  assert.equal(frac.width, 780); assert.equal(frac.height, 702);
  assert.ok(frac.scale > 4.8 && frac.scale < 4.9, "fit goes fractional when integer wastes > 15%");
  assert.deepEqual({ ...fit(780, 780, "integer") }, { width: 640, height: 576, scale: 4 });
  assert.equal(fit(120, 100, "integer").height, 100, "below 1x integer falls back to fractional");
  assert.deepEqual({ width: fit(900, 500, "stretch").width, height: fit(900, 500, "stretch").height },
    { width: 900, height: 500 }, "stretch fills the area");
  for (const [w, h] of [[1920, 960], [1100, 800], [1280, 650], [1024, 600], [500, 800]]) {
    for (const m of ["fit", "integer"]) {
      const r = fit(w, h, m);
      assert.ok(r.width <= w && r.height <= h, `${m} ${w}x${h} must fit`);
      assert.ok(Math.abs(r.width / r.height - 10 / 9) < 0.01, `${m} ${w}x${h} keeps 10:9`);
    }
  }
}
console.log("itch display fit checks passed");

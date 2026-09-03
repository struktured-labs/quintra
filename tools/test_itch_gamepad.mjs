#!/usr/bin/env node

import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const playerPath = process.argv[2];
if (!playerPath) throw new Error("usage: test_itch_gamepad.mjs PLAYER_JS");

const listeners = new Map();
const elements = new Map();
let gamepadStatusWrites = 0;
const element = (dataset = {}) => {
  const ownListeners = new Map();
  const classes = new Set();
  let textContent = "";
  const item = {
    disabled: false,
    hidden: false,
    value: "",
    files: [],
    dataset,
    classList: {
      toggle(name, force) {
        if (force) classes.add(name); else classes.delete(name);
      },
      contains(name) { return classes.has(name); }
    },
    addEventListener(type, callback) { ownListeners.set(type, callback); },
    dispatch(type, event) { ownListeners.get(type)(event); },
    setPointerCapture() {},
    setAttribute() {},
    focus() {},
    click() {},
    querySelector() { return element(); },
    requestFullscreen: async () => {}
  };
  Object.defineProperty(item, "textContent", {
    get() { return textContent; },
    set(value) {
      textContent = value;
      if (dataset.gamepadStatus) gamepadStatusWrites += 1;
    }
  });
  return item;
};

const touchDiagonal = element({ touchInput: "UP RIGHT" });
const touchA = element({ touchInput: "A" });
touchA.setPointerCapture = () => { throw new DOMException("pointer unavailable", "NotFoundError"); };
const touchButtons = [touchDiagonal, touchA];

for (const id of [
  "game", "player-shell", "launch", "status", "mute", "fullscreen",
  "export-save", "import-save", "save-file", "gamepad-status"
]) elements.set(`#${id}`, element(id === "gamepad-status" ? { gamepadStatus: "true" } : {}));

let originalStateCalls = 0;
let gamepadPollCalls = 0;
let pointerCaptureWarnings = 0;
const responsiveGamepad = {
  getState() {
    originalStateCalls += 1;
    return { UP: false, RIGHT: false, DOWN: false, LEFT: false,
      A: false, B: false, SELECT: false, START: false };
  }
};
const api = {
  ResponsiveGamepad: responsiveGamepad,
  config: async () => {},
  loadROM: async () => {},
  resumeAudioContext: async () => {},
  play: async () => {},
  isPlaying: () => false,
  _getAudioChannels: () => ({ master: { mute() {}, unmute() {} } })
};

let pads = [
  null,
  { index: 1, id: "idle virtual pad", buttons: [{ pressed: false, value: 0 }], axes: [0, 0] },
  { index: 2, id: "8BitDo Pro 2", buttons: Array.from({ length: 15 }, (_, index) => ({
      pressed: index === 1,
      value: index === 1 ? 1 : 0
    })),
    axes: [0, 0, 0, 0, 0, 0, 0, 0, 0, -1] }
];

const context = {
  console: {
    log: console.log,
    error: console.error,
    warn() { pointerCaptureWarnings += 1; }
  },
  Uint8Array,
  Blob,
  URL,
  navigator: { getGamepads: () => {
    gamepadPollCalls += 1;
    return pads;
  } },
  document: {
    querySelector: selector => elements.get(selector),
    querySelectorAll: selector => selector === "[data-touch-input]" ? touchButtons : [],
    addEventListener() {},
    fullscreenElement: null,
    visibilityState: "visible"
  },
  window: {
    WasmBoy: { WasmBoy: api },
    addEventListener(type, callback) { listeners.set(type, callback); }
  }
};

vm.runInNewContext(fs.readFileSync(playerPath, "utf8"), context, { filename: playerPath });
await new Promise(resolve => setImmediate(resolve));

let state = responsiveGamepad.getState();
assert.equal(state.A, true, "active nonzero gamepad input should reach WasmBoy");
assert.equal(state.B, false, "8BitDo physical A should not trigger GBC B");
assert.equal(originalStateCalls, 1, "keyboard/touch state should still be polled");
assert.equal(state.UP, true, "8BitDo DirectInput hat up should reach WasmBoy");
assert.match(elements.get("#gamepad-status").textContent, /8BitDo Pro 2/);
assert.match(elements.get("#gamepad-status").textContent, /Nintendo layout/,
  "active 8BitDo profile should be visible to the player");
assert.equal(gamepadPollCalls, 1, "custom mappings should poll browser gamepads once per frame");
assert.equal(gamepadStatusWrites, 1, "initial controller selection should update its status once");

responsiveGamepad.getState();
assert.equal(gamepadPollCalls, 2, "each later frame should add only one browser gamepad poll");
assert.equal(gamepadStatusWrites, 1, "unchanged controller status should not rewrite the DOM");

pads[2].buttons[1] = { pressed: false, value: 0 };
pads[2].buttons[0] = { pressed: true, value: 1 };
state = responsiveGamepad.getState();
assert.equal(state.A, false, "8BitDo physical B should not trigger GBC A");
assert.equal(state.B, true, "8BitDo physical B should trigger GBC B");

pads[2].buttons[0] = { pressed: false, value: 0 };
pads[2].buttons[10] = { pressed: true, value: 1 };
state = responsiveGamepad.getState();
assert.equal(state.SELECT, true, "8BitDo Select should reach GBC Select");

pads[2].buttons[10] = { pressed: false, value: 0 };
pads[2].buttons[11] = { pressed: true, value: 1 };
state = responsiveGamepad.getState();
assert.equal(state.START, true, "8BitDo Start should reach GBC Start");

pads[2].buttons[11] = { pressed: false, value: 0 };
pads[2].axes[9] = -0.7142857;
state = responsiveGamepad.getState();
assert.equal(state.UP, true, "8BitDo hat diagonal should preserve vertical input");
assert.equal(state.RIGHT, true, "8BitDo hat diagonal should preserve horizontal input");

pads[2].axes[9] = 3.285714;
pads[2].axes[0] = 0.8;
state = responsiveGamepad.getState();
assert.equal(state.RIGHT, true, "analog movement should be mapped directly");
assert.equal(state.UP, false, "8BitDo neutral hat value should not produce movement");
assert.match(elements.get("#gamepad-status").textContent, /8BitDo Pro 2/,
  "selected gamepad should remain sticky while connected");

pads[2].id = "2dc8-6006";
responsiveGamepad.getState();
assert.match(elements.get("#gamepad-status").textContent, /Nintendo layout/,
  "8BitDo's numeric vendor id should activate the Nintendo layout");

pads = [null, pads[1], null];
listeners.get("gamepaddisconnected")({ gamepad: { index: 2 } });
responsiveGamepad.getState();
assert.match(elements.get("#gamepad-status").textContent, /idle virtual pad/,
  "disconnect should fall back to another connected gamepad");

const pointerEvent = pointerId => ({ pointerId, preventDefault() {} });
touchDiagonal.dispatch("pointerdown", pointerEvent(7));
touchA.dispatch("pointerdown", pointerEvent(8));
state = responsiveGamepad.getState();
assert.equal(state.UP, true, "touch diagonal should hold up");
assert.equal(state.RIGHT, true, "touch diagonal should hold right");
assert.equal(state.A, true, "a second touch should hold A simultaneously");
assert.equal(touchA.classList.contains("is-pressed"), true, "pressed touch control should show feedback");
assert.equal(pointerCaptureWarnings, 1, "pointer capture failure should remain non-fatal");

touchA.dispatch("pointerup", pointerEvent(8));
state = responsiveGamepad.getState();
assert.equal(state.A, false, "released touch A should clear");
assert.equal(state.UP, true, "releasing A should not release another pointer's direction");

touchDiagonal.dispatch("pointerup", pointerEvent(7));
state = responsiveGamepad.getState();
assert.equal(state.UP, false, "released touch direction should clear");
assert.equal(state.RIGHT, false, "released touch diagonal should clear both directions");

console.log("itch input checks passed: 8BitDo mapping, D-pad hats, numeric vendor id, and multi-touch controls");

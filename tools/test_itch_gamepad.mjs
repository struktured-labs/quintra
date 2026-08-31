#!/usr/bin/env node

import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const playerPath = process.argv[2];
if (!playerPath) throw new Error("usage: test_itch_gamepad.mjs PLAYER_JS");

const listeners = new Map();
const elements = new Map();
const element = () => ({
  disabled: false,
  hidden: false,
  textContent: "",
  value: "",
  files: [],
  classList: { toggle() {} },
  addEventListener() {},
  setAttribute() {},
  focus() {},
  click() {},
  querySelector() { return element(); },
  requestFullscreen: async () => {}
});

for (const id of [
  "game", "player-shell", "launch", "status", "mute", "fullscreen",
  "export-save", "import-save", "save-file", "gamepad-status"
]) elements.set(`#${id}`, element());

const observedIndexes = [];
const gamepadInput = {
  getState(index) {
    observedIndexes.push(index);
    return {};
  }
};
const api = {
  ResponsiveGamepad: { Gamepad: gamepadInput },
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
  { index: 2, id: "8BitDo Pro 2", buttons: [{ pressed: true, value: 1 }], axes: [0, 0] }
];

const context = {
  console,
  Uint8Array,
  Blob,
  URL,
  navigator: { getGamepads: () => pads },
  document: {
    querySelector: selector => elements.get(selector),
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

gamepadInput.getState();
assert.equal(observedIndexes.at(-1), 2, "active nonzero gamepad should be selected");
assert.match(elements.get("#gamepad-status").textContent, /8BitDo Pro 2/);

pads[2].buttons[0] = { pressed: false, value: 0 };
gamepadInput.getState();
assert.equal(observedIndexes.at(-1), 2, "selected gamepad should remain sticky while connected");

pads = [null, pads[1], null];
listeners.get("gamepaddisconnected")({ gamepad: { index: 2 } });
gamepadInput.getState();
assert.equal(observedIndexes.at(-1), 1, "disconnect should fall back to another connected gamepad");

console.log("itch gamepad checks passed: active nonzero, sticky selection, disconnect fallback");

#!/usr/bin/env node
// Unit test for the opt-in local play telemetry sampler in player.js.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const playerPath = process.argv[2];
if (!playerPath) throw new Error("usage: test_itch_telemetry.mjs PLAYER_JS");
const src = fs.readFileSync(playerPath, "utf8");
const start = src.indexOf("  const TELEMETRY_KEY");
const end = src.indexOf("  function startTelemetry()");
assert.ok(start > 0 && end > start, "telemetry block not found");
const ctx = { pageParams: new URLSearchParams(""), out: null };
vm.createContext(ctx);
vm.runInContext(src.slice(start, end) + "\nout = { createTelemetry, telemetryCsv, telemetryEnabled };", ctx);
const { createTelemetry, telemetryCsv, telemetryEnabled } = ctx.out;

// Off by default and never touches storage without the opt-in.
assert.equal(telemetryEnabled(), false);

const tel = createTelemetry({}, "test-build");
const base = { screen: 5, seed: 1234, room: 1, bosses: 0, victory: 0, runTimer: 10,
  difficulty: 0, hero: "corvin", hpMax: 14, hp: 14, status: 0, statusTicks: 0, boss: false };
let t = 0;
const step = (patch, dt = 100) => { t += dt; Object.assign(base, patch); tel.sample({ ...base }, t); };

// Attract mode (screen 4) is ignored.
tel.sample({ ...base, screen: 4 }, 0);
assert.equal(tel.data.runs.length, 0);

step({});
step({ runTimer: 11 }, 1000);
step({ hp: 12 });                       // a hit in stage 1
step({ bosses: 1, room: 21 }, 1000);    // stage 1 Colossus down -> stage 2
step({ boss: true, runTimer: 30 }, 1000);
step({ status: 9, statusTicks: 20 });   // bleed lands during the boss
step({ hp: 4 });
step({ hp: 0 }, 1500);                  // dies 1.6 s after the bleed

const run = tel.data.runs[0];
assert.equal(tel.data.runs.length, 1);
assert.equal(run.stages.length, 2);
assert.equal(run.stages[0].dmg, 2);
assert.equal(run.stages[0].boss_cleared, 1);
assert.equal(run.stages[1].status.bleed, 1);
assert.equal(run.stages[1].status_in_boss, 1);
assert.equal(run.outcome, "died");
assert.equal(run.death.stage, 2);
assert.equal(run.death.status, "bleed");
assert.ok(run.death.status_age_s > 1 && run.death.status_age_s < 2.5, run.death.status_age_s);
assert.equal(run.death.in_boss, 1);

// A new run (new seed) starts a fresh record.
step({ seed: 999, room: 1, bosses: 0, hp: 14, status: 0, statusTicks: 0, boss: false });
assert.equal(tel.data.runs.length, 2);
const csv = telemetryCsv(tel.data);
assert.match(csv.split("\n")[0], /^run,build,hero,difficulty/);
assert.match(csv, /,2,.*,1,1,bleed,/);
console.log("[telemetry] sampler OK");

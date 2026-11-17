#!/usr/bin/env node
// Headless self-test for the packaged Linux desktop build.
// Run 1 boots the app under Xvfb, captures screenshots, checks gamepad
// mapping with a virtual pad, and writes a save. Run 2 starts with a fresh
// profile (empty IndexedDB) and the same save dir, and must boot with the
// cartridge RAM from the disk file.
// SPDX-License-Identifier: GPL-3.0-or-later
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const root = path.resolve(desktop, "..");
const bin = process.argv[2] || path.join(root, "builds/desktop/electron/linux-unpacked/quintra");
const out = path.resolve(process.argv[3] || path.join(root, "builds/desktop/selftest"));
if (!fs.existsSync(bin)) {
  console.error(`Missing ${bin}. Run desktop/scripts/package.sh first.`);
  process.exit(1);
}
fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(out, { recursive: true });
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "quintra-selftest-"));
const saveDir = path.join(tmp, "saves");

function run(mode, profile) {
  const args = [
    "-a", "-s", "-screen 0 1280x800x24", bin,
    `--quintra-selftest=${out}`, `--quintra-selftest-mode=${mode}`,
    `--quintra-user-data=${path.join(tmp, profile)}`, `--quintra-save-dir=${saveDir}`
  ];
  const started = Date.now();
  const result = spawnSync("xvfb-run", args, { encoding: "utf8", timeout: 180000 });
  fs.writeFileSync(path.join(out, `log-${mode}.txt`), `${result.stdout || ""}\n${result.stderr || ""}`);
  const reportFile = path.join(out, `report-${mode}.json`);
  const report = fs.existsSync(reportFile) ? JSON.parse(fs.readFileSync(reportFile, "utf8")) : { ok: false, error: "no report" };
  console.log(`${mode}: ok=${report.ok} exit=${result.status} ${Math.round((Date.now() - started) / 1000)}s`);
  if (!report.ok) console.log(JSON.stringify(report, null, 2));
  return report;
}

const full = run("full", "profile-1");
const verify = run("verify-save", "profile-2");
const savePath = path.join(saveDir, "quintra.sav");
const saveBytes = fs.existsSync(savePath) ? fs.statSync(savePath).size : 0;
if (fs.existsSync(savePath)) fs.copyFileSync(savePath, path.join(out, "quintra.sav"));
const blocked = [...(full.blockedRequests || []), ...(verify.blockedRequests || [])];
const summary = {
  ok: full.ok && verify.ok && saveBytes === 32768 && blocked.length === 0,
  full: full.ok, verifySave: verify.ok, saveBytes, blockedRequests: blocked,
  steps: full.steps
};
fs.writeFileSync(path.join(out, "summary.json"), JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 2));
fs.rmSync(tmp, { recursive: true, force: true });
process.exit(summary.ok ? 0 : 1);

#!/usr/bin/env node
// Stage the itch web package as the desktop app content.
// SPDX-License-Identifier: GPL-3.0-or-later
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const root = path.resolve(desktop, "..");
const web = path.join(root, "builds", "itch-web");
const app = path.join(desktop, "app");

for (const required of ["index.html", "quintra.gbc", "emulator/quintra-player.js", "emulator/wasmboy.js", "build.json"]) {
  if (!fs.existsSync(path.join(web, required))) {
    console.error(`Missing ${path.join(web, required)}. Run tools/build_itch_web.sh first.`);
    process.exit(1);
  }
}

fs.rmSync(app, { recursive: true, force: true });
fs.cpSync(web, app, { recursive: true });
fs.mkdirSync(path.join(app, "desktop"), { recursive: true });
fs.copyFileSync(path.join(desktop, "renderer", "desktop.js"), path.join(app, "desktop", "desktop.js"));
fs.copyFileSync(path.join(desktop, "renderer", "desktop.css"), path.join(app, "desktop", "desktop.css"));
fs.copyFileSync(path.join(desktop, "DESKTOP-NOTICES.md"), path.join(app, "licenses", "DESKTOP-NOTICES.md"));

const electronLicense = path.join(desktop, "node_modules", "electron", "dist", "LICENSE");
if (!fs.existsSync(electronLicense)) {
  console.error(`Missing ${electronLicense}. Run npm ci in desktop/ first.`);
  process.exit(1);
}
fs.copyFileSync(electronLicense, path.join(app, "licenses", "ELECTRON-LICENSE.txt"));

const indexPath = path.join(app, "index.html");
let html = fs.readFileSync(indexPath, "utf8");
const playerTag = html.match(/<script src="emulator\/quintra-player\.js[^"]*"><\/script>/);
if (!playerTag) throw new Error("index.html has no quintra-player.js script tag");
html = html.replace(playerTag[0], `${playerTag[0]}\n    <script src="desktop/desktop.js"></script>`);
html = html.replace("</head>", `    <link rel="stylesheet" href="desktop/desktop.css">\n  </head>`);
html = html.replace(/<title>[^<]*<\/title>/, "<title>Quintra</title>");
fs.writeFileSync(indexPath, html);

const build = JSON.parse(fs.readFileSync(path.join(app, "build.json"), "utf8"));
build.channel = "desktop";
fs.writeFileSync(path.join(app, "build.json"), `${JSON.stringify(build, null, 2)}\n`);
// The web zip's ROM checksum file stays; the itch-only cover is not needed.
console.log(`Staged ${app} (web ${build.version}, ROM ${build.romSha256.slice(0, 12)})`);

/*
 * Quintra desktop wrapper (preload)
 * Copyright 2026 Quintra contributors
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
"use strict";

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("QuintraDesktop", {
  readSave: () => ipcRenderer.invoke("quintra:read-save"),
  writeSave: bytes => ipcRenderer.invoke("quintra:write-save", bytes),
  getFullscreen: () => ipcRenderer.invoke("quintra:get-fullscreen"),
  setFullscreen: on => ipcRenderer.invoke("quintra:set-fullscreen", !!on),
  quit: () => ipcRenderer.invoke("quintra:quit"),
  info: () => ipcRenderer.invoke("quintra:info"),
  openChromiumLicenses: () => ipcRenderer.invoke("quintra:open-chromium-licenses"),
  onFullscreen: callback => ipcRenderer.on("quintra:fullscreen", (event, on) => callback(!!on)),
  onFlushRequest: callback => ipcRenderer.on("quintra:flush", async () => {
    try { await callback(); } finally { ipcRenderer.send("quintra:flushed"); }
  })
});

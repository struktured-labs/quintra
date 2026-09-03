#!/usr/bin/env python3
"""Exercise a built Quintra web player in real Firefox."""

from __future__ import annotations

import argparse
import json
import os
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--layout-only", action="store_true")
    parser.add_argument("--portrait", action="store_true")
    args = parser.parse_args()
    if args.duration < 3:
        parser.error("--duration must be at least 3 seconds")
    if args.portrait:
        os.environ["MOZ_HEADLESS_WIDTH"] = "500"
        os.environ["MOZ_HEADLESS_HEIGHT"] = "814"

    options = Options()
    options.add_argument("-headless")
    options.set_preference("media.autoplay.default", 0)
    options.set_preference("media.autoplay.blocking_policy", 0)
    driver = webdriver.Firefox(options=options)
    try:
        driver.set_window_size(1200, 900)
        driver.get(args.url)
        wait = WebDriverWait(driver, 30)
        wait.until(lambda browser: browser.find_element(By.ID, "status").text.startswith("Ready"))
        launch_state = driver.execute_script(
            """
            const launch = document.querySelector('#launch');
            return {
              disabled: launch.disabled,
              busy: launch.getAttribute('aria-busy'),
              title: launch.querySelector('strong').textContent,
              detail: launch.querySelector('span').textContent
            };
            """
        )
        driver.find_element(By.ID, "launch").click()
        wait.until(lambda browser: browser.find_element(By.ID, "status").text == "Playing")
        driver.execute_script(
            """
            window.__quintraGateSamples = [];
            window.__quintraGateTimer = setInterval(() => {
              const d = window.WasmBoy.WasmBoy.getAudioDiagnostics();
              if (!d || !d.worklet) return;
              window.__quintraGateSamples.push({
                underruns: d.worklet.underrunFrames,
                drops: d.worklet.droppedFrames,
                trim: d.worklet.driftTrim,
                rate: d.worklet.playbackRate,
                queue: d.worklet.queuedSeconds,
                timeouts: d.producer.ackTimeouts
              });
            }, 50);
            """
        )
        time.sleep(2)
        baseline = driver.execute_script("return window.WasmBoy.WasmBoy.getAudioDiagnostics();")
        time.sleep(args.duration - 2)
        result = driver.execute_script(
            """
            clearInterval(window.__quintraGateTimer);
            const api = window.WasmBoy.WasmBoy;
            const final = api.getAudioDiagnostics();
            const samples = window.__quintraGateSamples;
            const canvas = document.querySelector('#game');
            const pixels = canvas.getContext('2d').getImageData(0, 0, 160, 144).data;
            const colors = new Set();
            let nearBlack = 0;
            for (let i = 0; i < pixels.length; i += 4) {
              colors.add(`${pixels[i]},${pixels[i + 1]},${pixels[i + 2]},${pixels[i + 3]}`);
              if (pixels[i] < 12 && pixels[i + 1] < 12 && pixels[i + 2] < 12) nearBlack++;
            }
            return {
              final, samples, colors: colors.size, nearBlack,
              status: document.querySelector('#status').textContent,
              sampleRate: api._getAudioChannels().master.audioContext.sampleRate
            };
            """
        )
        driver.find_element(By.ID, "fullscreen").click()
        wait.until(lambda browser: browser.execute_script("return Boolean(document.fullscreenElement)"))
        result["fullscreen"] = driver.execute_script(
            """
            const box = element => {
              const rect = element.getBoundingClientRect();
              return { top: rect.top, bottom: rect.bottom, width: rect.width, height: rect.height };
            };
            return {
              active: document.fullscreenElement === document.querySelector('#player-shell'),
              viewport: { width: innerWidth, height: innerHeight },
              screen: box(document.querySelector('.screen-wrap')),
              controls: box(document.querySelector('.touch-controls'))
            };
            """
        )
    finally:
        driver.quit()

    final = result["final"]
    worklet = final["worklet"]
    producer = final["producer"]
    samples = result.pop("samples")
    report = {
        "audioChecked": not args.layout_only,
        "status": result["status"],
        "colors": result["colors"],
        "nearBlack": result["nearBlack"],
        "launch": launch_state,
        "fullscreen": result["fullscreen"],
    }
    if not args.layout_only:
        report.update({
            "sampleRate": result["sampleRate"],
            "underrunDelta": worklet["underrunFrames"] - baseline["worklet"]["underrunFrames"],
            "dropDelta": worklet["droppedFrames"] - baseline["worklet"]["droppedFrames"],
            "ackTimeoutDelta": producer["ackTimeouts"] - baseline["producer"]["ackTimeouts"],
            "finalQueueMs": worklet["queuedSeconds"] * 1000,
            "finalDriftTrim": worklet["driftTrim"],
            "finalPlaybackRate": worklet["playbackRate"],
            "minimumPlaybackRate": min(sample["rate"] for sample in samples),
            "maximumPlaybackRate": max(sample["rate"] for sample in samples),
        })
    failures = []
    if report["status"] != "Playing":
        failures.append("player did not remain in Playing state")
    if report["launch"] != {
        "disabled": False,
        "busy": "false",
        "title": "Enter the Riftwild",
        "detail": "Click to start with sound",
    }:
        failures.append("ready cartridge did not expose the sound-enabled launch action")
    if not args.layout_only:
        if report["sampleRate"] != 44100:
            failures.append(f'audio context ran at {report["sampleRate"]} Hz')
        if report["underrunDelta"] != 0:
            failures.append(f'{report["underrunDelta"]} audio frames underran after warmup')
        if report["dropDelta"] != 0:
            failures.append(f'{report["dropDelta"]} audio frames were dropped after warmup')
        if report["ackTimeoutDelta"] != 0:
            failures.append(f'{report["ackTimeoutDelta"]} audio acknowledgements timed out')
        if report["finalPlaybackRate"] != 1 or report["finalDriftTrim"] != 0:
            failures.append("audio did not finish at exact pitch")
    if report["colors"] < 8 or report["nearBlack"] > 160 * 144 // 4:
        failures.append("rendered frame looks blank or corrupted")
    fullscreen = report["fullscreen"]
    if not fullscreen["active"]:
        failures.append("player did not enter fullscreen")
    if fullscreen["screen"]["bottom"] > fullscreen["viewport"]["height"] + 1:
        failures.append("fullscreen canvas extends below the viewport")
    if fullscreen["controls"]["bottom"] > fullscreen["viewport"]["height"] + 1:
        failures.append("fullscreen touch controls extend below the viewport")
    ratio = fullscreen["screen"]["width"] / fullscreen["screen"]["height"]
    if abs(ratio - 10 / 9) > 0.002:
        failures.append(f"fullscreen canvas ratio is {ratio:.4f}, expected 10:9")

    print(json.dumps(report, indent=2, sort_keys=True))
    if failures:
        raise SystemExit("Firefox gate failed: " + "; ".join(failures))
    print("Firefox gate passed")


if __name__ == "__main__":
    main()

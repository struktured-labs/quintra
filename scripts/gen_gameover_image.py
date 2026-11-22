#!/usr/bin/env python3
"""gpt-image-2.6-sunburst for the Game Over visor. Never prints the API key.

usage: gen_gameover_image.py NAME SIZE QUALITY N PROMPTFILE [EDIT_IMAGE...]
"""
import os
import sys
import json
import base64
import time
import pathlib
import urllib.request
import urllib.error
import uuid

OUT = pathlib.Path("/tmp/q-gameover-art")
LEDGER = OUT / "ledger.jsonl"
JOB_CAP = 2.00


def spent():
    if not LEDGER.exists():
        return 0.0
    return sum(json.loads(l).get("cost", 0)
               for l in LEDGER.read_text().splitlines() if l.strip())


def cost_of(u):
    d = u.get("input_tokens_details", {})
    return (d.get("image_tokens", 0) * 8e-6
            + d.get("text_tokens", 0) * 5e-6
            + u.get("output_tokens", 0) * 30e-6)


def main():
    name, size, quality, n, pf = sys.argv[1:6]
    edits = sys.argv[6:]
    prompt = pathlib.Path(pf).read_text()
    if spent() >= JOB_CAP:
        print("BUDGET STOP")
        sys.exit(2)
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("MISSING KEY")
        sys.exit(1)
    hdr = {"Authorization": "Bearer " + key}
    if edits:
        b = uuid.uuid4().hex
        parts = []

        def field(k, v):
            parts.append(
                f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
            )

        for k, v in [("model", "gpt-image-2.6-sunburst"),
                     ("prompt", prompt), ("n", n), ("size", size),
                     ("quality", quality)]:
            field(k, v)
        for p in edits:
            parts.append(
                f"--{b}\r\nContent-Disposition: form-data; name=\"image[]\"; "
                f"filename=\"{pathlib.Path(p).name}\"\r\nContent-Type: image/png\r\n\r\n".encode()
                + pathlib.Path(p).read_bytes() + b"\r\n"
            )
        parts.append(f"--{b}--\r\n".encode())
        body = b"".join(parts)
        hdr["Content-Type"] = "multipart/form-data; boundary=" + b
        url = "https://api.openai.com/v1/images/edits"
    else:
        body = json.dumps({
            "model": "gpt-image-2.6-sunburst",
            "prompt": prompt,
            "n": int(n),
            "size": size,
            "quality": quality,
        }).encode()
        hdr["Content-Type"] = "application/json"
        url = "https://api.openai.com/v1/images/generations"
    t0 = time.time()
    try:
        resp = json.loads(urllib.request.urlopen(
            urllib.request.Request(url, data=body, headers=hdr),
            timeout=400,
        ).read())
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:600])
        sys.exit(1)
    (OUT / "raw").mkdir(parents=True, exist_ok=True)
    for i, d in enumerate(resp["data"]):
        (OUT / "raw" / f"{name}-{i}.png").write_bytes(base64.b64decode(d["b64_json"]))
    u = resp.get("usage", {})
    c = cost_of(u)
    with LEDGER.open("a") as f:
        f.write(json.dumps({
            "name": name,
            "n": len(resp["data"]),
            "usage": u,
            "cost": round(c, 6),
            "secs": round(time.time() - t0, 1),
        }) + "\n")
    print(name, len(resp["data"]), "cost $%.4f job $%.4f" % (c, spent()))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Assemble the GitHub Pages artifact from a completed `make manual` build.

Writes `_site/` with the HTML preview under `manual/`, the reader PDF as
`manual/quintra-manual.pdf`, and a root page that redirects to `manual/`.
Never copies a ROM or zip.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SITE_SRC = ROOT / "docs/manual/build/site"
PDF_SRC = ROOT / "docs/manual/build/pdf/quintra-manual.pdf"
OUT = ROOT / "_site"
FORBIDDEN_SUFFIXES = {".gbc", ".gb", ".zip"}


def die(msg: str) -> None:
    print(f"assemble-pages: {msg}", file=sys.stderr)
    raise SystemExit(1)


def add_pdf_link(index: Path) -> None:
    text = index.read_text()
    if "quintra-manual.pdf" in text:
        return
    new, n = re.subn(
        r"(<p>Status:.*?</p>)",
        r'\1\n<p><a href="quintra-manual.pdf">Download the reader PDF</a>.</p>',
        text,
        count=1,
    )
    if n != 1:
        die("could not find the status line in index.html")
    index.write_text(new)


def write_root_redirect(path: Path) -> None:
    path.write_text(
        """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="0; url=manual/">
<link rel="canonical" href="manual/">
<title>Quintra instruction manual</title>
</head>
<body>
<p><a href="manual/">Open the Quintra instruction manual</a>.</p>
</body>
</html>
"""
    )


def main() -> None:
    if not (SITE_SRC / "index.html").is_file():
        die(f"missing built site at {SITE_SRC}")
    if not PDF_SRC.is_file():
        die(f"missing reader PDF at {PDF_SRC}")

    if OUT.exists():
        shutil.rmtree(OUT)
    dest = OUT / "manual"
    shutil.copytree(SITE_SRC, dest)
    shutil.copy2(PDF_SRC, dest / "quintra-manual.pdf")
    add_pdf_link(dest / "index.html")
    write_root_redirect(OUT / "index.html")

    forbidden = [
        p
        for p in OUT.rglob("*")
        if p.is_file() and p.suffix.lower() in FORBIDDEN_SUFFIXES
    ]
    if forbidden:
        names = "\n".join(str(p) for p in forbidden)
        die(f"refusing to publish a ROM or zip:\n{names}")

    for required in (
        OUT / "index.html",
        dest / "index.html",
        dest / "quintra-manual.pdf",
        dest / "preview.css",
    ):
        if not required.is_file():
            die(f"missing {required}")
    print(f"assemble-pages: wrote {OUT}")


if __name__ == "__main__":
    main()

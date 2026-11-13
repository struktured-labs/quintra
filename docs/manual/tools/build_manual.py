#!/usr/bin/env python3
"""Build the Quintra manual from docs/manual/content.

One Markdown package feeds:
  - a reader PDF (single pages, A6 trim)
  - a saddle-stitched booklet PDF (bleed, crop marks)
  - a JS-free HTML preview for local reading

The Next.js site should consume the Markdown, not this preview's CSS.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image
from pypdf import PageObject, PdfReader, PdfWriter, Transformation

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
FONTS = ROOT / "fonts"
TOOLS = ROOT / "tools"
BUILD = ROOT / "build"
TYPST = Path.home() / ".local" / "bin" / "typst"

TRIM_W = 105.0
TRIM_H = 148.0
BLEED = 3.0
SLUG = 6.0

FORBIDDEN = re.compile(
    r"hexa|dragmar|\.gbc\b|itch\.io|butler|password|download the rom",
    re.I,
)
TAG = re.compile(r"</?[a-zA-Z!]")


def die(msg: str) -> None:
    print(f"manual: {msg}", file=sys.stderr)
    raise SystemExit(1)


def load_manifest() -> dict:
    return json.loads((CONTENT / "manifest.json").read_text())


def parse_md(text: str, source: str) -> list:
    if TAG.search(text):
        die(f"{source} contains raw HTML or CSS-like markup")
    lines = text.replace("\r\n", "\n").split("\n")
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            if level > 3 or not line[level:level + 1].isspace():
                die(f"{source}: bad heading: {line}")
            blocks.append(("h", level, line[level:].strip()))
            i += 1
            continue
        if line.startswith("> "):
            quote = []
            while i < len(lines) and lines[i].startswith("> "):
                quote.append(lines[i][2:].strip())
                i += 1
            blocks.append(("quote", " ".join(quote)))
            continue
        if line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(lines[i][2:].strip())
                i += 1
            blocks.append(("ul", items))
            continue
        if line.startswith("!["):
            match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)\s*$", line.strip())
            if not match:
                die(f"{source}: bad image line: {line}")
            blocks.append(("img", match.group(1).strip(), match.group(2).strip()))
            i += 1
            continue
        para = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", ">", "- ", "![")):
            para.append(lines[i].strip())
            i += 1
        blocks.append(("p", " ".join(para)))
    out = []
    i = 0
    while i < len(blocks):
        block = blocks[i]
        if block[0] == "img":
            if (
                i + 1 >= len(blocks)
                or blocks[i + 1][0] != "p"
                or not blocks[i + 1][1].startswith("Caption:")
            ):
                die(f"{source}: image {block[2]} needs a Caption line")
            alt, path = block[1], block[2]
            if not alt:
                die(f"{source}: image {path} needs alt text")
            caption = blocks[i + 1][1][len("Caption:"):].strip()
            if not caption:
                die(f"{source}: empty caption for {path}")
            image = CONTENT / path
            if not image.is_file():
                die(f"{source}: missing {path}")
            out.append(("img", alt, path, caption))
            i += 2
            continue
        out.append(block)
        i += 1
    return out


def typst_text(value: str) -> str:
    return "".join("\\" + ch if ch in "\\#$*_`@<>[]" else ch for ch in value)


def typst_inline(value: str) -> str:
    parts = re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", value)
    chunks = []
    for part in parts:
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            chunks.append(f"#strong[{typst_text(part[2:-2])}]")
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            chunks.append(f"#emph[{typst_text(part[1:-1])}]")
        else:
            chunks.append(typst_text(part))
    return "".join(chunks)


def html_inline(value: str) -> str:
    escaped = html.escape(value)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    return escaped


def png_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as im:
        return im.size


def upscale(src: Path, dest: Path) -> tuple[int, float, float]:
    """Nearest-neighbor integer scale that fits the A6 text width at 300 dpi file resolution."""
    width, _height = png_size(src)
    content_mm = 80.0
    scale = int(content_mm * 300 / (width * 25.4))
    scale = max(2, min(8, scale))
    while width * scale / 300 * 25.4 > content_mm and scale > 2:
        scale -= 1
    mm = width * scale / 300 * 25.4
    effective = 300 / scale
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        big = im.resize((im.width * scale, im.height * scale), Image.Resampling.NEAREST)
        big.save(dest)
    return scale, mm, effective


def render_body(blocks, image_mm: dict, skip_lists: bool = False) -> str:
    parts = []
    for block in blocks:
        kind = block[0]
        if kind == "h":
            level, text = block[1], block[2]
            parts.append(f"{'=' * level} {typst_inline(text)}\n")
        elif kind == "p":
            if block[1].startswith("Caption:"):
                continue
            parts.append(typst_inline(block[1]) + "\n")
        elif kind == "quote":
            parts.append(
                "#block(inset: (left: 2.2mm, y: 0.6mm), "
                "stroke: (left: 1.4pt + rgb(\"#b4532a\")))["
                f"#emph[{typst_inline(block[1])}]]\n"
            )
        elif kind == "ul":
            if skip_lists:
                continue
            items = ",\n".join(f"[{typst_inline(item)}]" for item in block[1])
            parts.append(f"#list(\n{items},\n)\n")
        elif kind == "img":
            _alt, path, caption = block[1], block[2], block[3]
            mm = image_mm[path]
            rel = Path("images") / (Path(path).name)
            parts.append(
                "#block(breakable: false, above: 0.8em, below: 0.7em)[\n"
                f"  #align(center)[#image(\"{rel}\", width: {mm:.2f}mm, alt: \"{typst_text(block[1]).replace('\\\"', '')}\")]\n"
                "  #v(0.8mm)\n"
                "  #align(center, text(font: \"Noto Sans\", size: 7.5pt, fill: rgb(\"#5c4a38\"))["
                f"{typst_inline(caption)}])\n"
                "]\n"
            )
    return "\n".join(parts)


def cover_page(blocks, bleed: float, plate_mm: float) -> str:
    title = next(b[2] for b in blocks if b[0] == "h")
    subtitle = next(b[1] for b in blocks if b[0] == "p" and not b[1].startswith("Caption:"))
    page_w = TRIM_W + bleed * 2
    page_h = TRIM_H + bleed * 2
    return f"""
#page(width: {page_w}mm, height: {page_h}mm, margin: (x: {8 + bleed}mm, y: {9 + bleed}mm), header: none, footer: none, fill: rgb("#140c18"))[
  #align(center)[
    #text(font: "Noto Sans", size: 18pt, weight: "bold", fill: rgb("#f6e7c2"), tracking: 0.18em)[{typst_text(title.upper())}]
    #v(1.4mm)
    #text(font: "Noto Serif", size: 8pt, style: "italic", fill: rgb("#f6e7c2"))[{typst_inline(subtitle)}]
    #v(1.5mm)
    #line(length: 28mm, stroke: 0.6pt + rgb("#e6c27a"))
    #v(3mm)
    #image("images/cover-plate.png", width: {plate_mm:.2f}mm, alt: "Five sparks under the rift")
    #v(2mm)
    #text(font: "Noto Sans", size: 7pt, fill: rgb("#e6c27a"), tracking: 0.08em)[V0.20.20  ·  IN DEVELOPMENT]
  ]
]
"""


def back_page(blocks, bleed: float, spark_mm: float) -> str:
    paras = [b[1] for b in blocks if b[0] == "p" and not b[1].startswith("Caption:")]
    page_w = TRIM_W + bleed * 2
    page_h = TRIM_H + bleed * 2
    body = "\n#v(2.2mm)\n".join(
        f"#text(font: \"Noto Serif\", size: 8.5pt, fill: rgb(\"#f6e7c2\"))[{typst_inline(p)}]"
        for p in paras
    )
    return f"""
#page(width: {page_w}mm, height: {page_h}mm, margin: (x: {10 + bleed}mm, y: {12 + bleed}mm), header: none, footer: none, fill: rgb("#140c18"))[
  #align(center)[
    #text(font: "Noto Sans", size: 16pt, weight: "bold", fill: rgb("#f6e7c2"), tracking: 0.18em)[QUINTRA]
    #v(4mm)
    #image("images/five-sparks.png", width: {spark_mm:.2f}mm, alt: "Five sparks")
    #v(4mm)
    {body}
  ]
]
"""


def preamble(bleed: float) -> str:
    page_w = TRIM_W + bleed * 2
    page_h = TRIM_H + bleed * 2
    top = 12 + bleed
    bottom = 13 + bleed
    inside = 12 + bleed
    outside = 9 + bleed
    return f"""
#set page(
  width: {page_w}mm,
  height: {page_h}mm,
  margin: (inside: {inside}mm, outside: {outside}mm, top: {top}mm, bottom: {bottom}mm),
  fill: rgb("#f6f0e4"),
  header-ascent: 0.4em,
  footer-descent: 0.6em,
  header: context {{
    let name = current.get()
    if name == none or name == "" {{ none }} else {{
      set text(font: "Noto Sans", size: 7pt, fill: rgb("#5c4a38"))
      grid(
        columns: (1fr, auto),
        align(left, smallcaps(name)),
        align(right, [Quintra]),
      )
      v(0.6mm)
      line(length: 100%, stroke: 0.3pt + rgb("#ddcbb0"))
    }}
  }},
  footer: context {{
    set text(font: "Noto Sans", size: 7.5pt, fill: rgb("#5c4a38"))
    align(center)[#counter(page).display()]
  }},
)
#set text(font: "Noto Serif", size: 8.5pt, fill: rgb("#1c140e"), hyphenate: true, lang: "en")
#set par(justify: true, leading: 0.58em, spacing: 0.55em)
#show heading.where(level: 1): it => {{
  current.update(it.body)
  pagebreak(weak: true)
  block(breakable: false, below: 0.55em, above: 0em)[
    #text(font: "Noto Sans", size: 13pt, weight: "bold", fill: rgb("#6b2a22"))[#it.body]
    #v(1mm)
    #line(length: 100%, stroke: 0.45pt + rgb("#b4532a"))
  ]
}}
#show heading.where(level: 2): it => block(breakable: false, above: 0.85em, below: 0.25em)[
  #text(font: "Noto Sans", size: 10pt, weight: "bold", fill: rgb("#3d2914"))[#it.body]
]
#show heading.where(level: 3): it => block(breakable: false, above: 0.7em, below: 0.2em)[
  #text(font: "Noto Sans", size: 9pt, weight: "bold", fill: rgb("#3d2914"))[#it.body]
]
"""


def pad_page() -> str:
    rules = "\n".join(
        "#line(length: 100%, stroke: 0.35pt + rgb(\"#ddcbb0\"))\n#v(6.4mm)"
        for _ in range(11)
    )
    return f"""
#page(header: none)[
  #text(font: "Noto Sans", size: 11pt, weight: "bold", fill: rgb("#6b2a22"))[Field notes]
  #v(1mm)
  #line(length: 100%, stroke: 0.45pt + rgb("#b4532a"))
  #v(3.2mm)
  {rules}
]
"""


def document(manifest, sections, image_mm, bleed: float, pads: int) -> str:
    chunks = [
        '#let current = state("sec", "")',
        cover_page(sections["cover.md"], bleed, image_mm["images/cover-plate.png"]),
        preamble(bleed),
    ]
    for section in manifest["sections"]:
        role = section.get("pdf", "body")
        if role != "body":
            continue
        blocks = sections[section["source"]]
        skip = bool(section.get("toc"))
        chunks.append(render_body(blocks, image_mm, skip_lists=skip))
        if skip:
            chunks.append(
                '#outline(title: [On these pages], depth: 1, indent: 0.4em)\n'
            )
    chunks.extend(pad_page() for _ in range(pads))
    return "\n".join(chunks)


def write_document(manifest, parsed, image_mm, bleed, pads, dest: Path) -> None:
    by_source = parsed
    chunks = [
        '#let current = state("sec", "")',
        cover_page(by_source["cover.md"], bleed, image_mm["images/cover-plate.png"]),
        preamble(bleed),
    ]
    for section in manifest["sections"]:
        if section.get("pdf", "body") != "body":
            continue
        blocks = by_source[section["source"]]
        chunks.append(render_body(blocks, image_mm, skip_lists=bool(section.get("toc"))))
        if section.get("toc"):
            chunks.append("#outline(title: [On these pages], depth: 1, indent: 0.4em)\n")
    chunks.extend(pad_page() for _ in range(pads))
    back = next(s for s in manifest["sections"] if s.get("pdf") == "back")
    chunks.append(back_page(by_source[back["source"]], bleed, image_mm["images/five-sparks.png"]))
    dest.write_text("\n".join(chunks))


def compile_typst(src: Path, out: Path) -> str:
    typst = TYPST if TYPST.is_file() else "typst"
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [str(typst), "compile", "--font-path", str(FONTS), str(src), str(out)],
        cwd=src.parent,
        text=True,
        capture_output=True,
    )
    log = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        die(f"typst failed\n{log}")
    if re.search(r"overflow|doesn't fit|does not fit", log, re.I):
        die(f"typst reported overflow\n{log}")
    return log


def page_count(pdf: Path) -> int:
    return len(PdfReader(str(pdf)).pages)


def mm(value: float) -> float:
    return value * 72.0 / 25.4


def impose(src: Path, dest: Path) -> None:
    reader = PdfReader(str(src))
    pages = list(reader.pages)
    count = len(pages)
    if count % 4 != 0:
        die(f"booklet page count {count} is not a multiple of 4")
    sheet_w = mm(SLUG * 2 + (TRIM_W + BLEED * 2) * 2)
    sheet_h = mm(SLUG * 2 + (TRIM_H + BLEED * 2))
    page_w = mm(TRIM_W + BLEED * 2)
    page_h = mm(TRIM_H + BLEED * 2)
    slug = mm(SLUG)
    writer = PdfWriter()
    sheets = count // 4
    for i in range(sheets):
        # Outside: back-side page | front-side page. Inside: next | previous.
        pairs = (
            (count - 1 - 2 * i, 2 * i),
            (2 * i + 1, count - 2 - 2 * i),
        )
        for left, right in pairs:
            sheet = PageObject.create_blank_page(width=sheet_w, height=sheet_h)
            for index, x in ((left, slug), (right, slug + page_w)):
                sheet.merge_transformed_page(
                    pages[index],
                    Transformation().translate(x, slug),
                )
            writer.add_page(sheet)
    marks = marks_pdf(sheet_w, sheet_h, page_w, page_h, slug)
    mark_page = PdfReader(str(marks)).pages[0]
    for page in writer.pages:
        page.merge_page(mark_page)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as handle:
        writer.write(handle)


def marks_pdf(sheet_w, sheet_h, page_w, page_h, slug) -> Path:
    """Crop marks in the slug, aligned to the trim (3 mm inside each bleed page)."""
    bleed = mm(BLEED)
    trim_w = mm(TRIM_W)
    trim_h = mm(TRIM_H)
    mark = mm(4)
    gap = mm(1.2)
    path = BUILD / "pdf" / "marks.typ"
    lines = []

    def tick(x1, y1, x2, y2):
        # Typst place() measures from the top-left, downward.
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        angle = 0 if abs(y2 - y1) < 0.1 else -90
        lines.append(
            f"#place(dx: {min(x1, x2):.2f}pt, dy: {sheet_h - max(y1, y2):.2f}pt, "
            f"line(length: {length:.2f}pt, angle: {angle}deg, stroke: 0.3pt + rgb(\"#222\")))"
        )

    # Inner horizontal ticks would cross the fold into the other page's trim.
    # Keep outer horizontals, and vertical ticks in the head and foot slug.
    sides = (("left", slug), ("right", slug + page_w))
    for side, origin in sides:
        left = origin + bleed
        right = left + trim_w
        bottom = slug + bleed
        top = bottom + trim_h
        if side == "left":
            tick(left - gap - mark, bottom, left - gap, bottom)
            tick(left - gap - mark, top, left - gap, top)
        else:
            tick(right + gap, bottom, right + gap + mark, bottom)
            tick(right + gap, top, right + gap + mark, top)
        tick(left, bottom - gap - mark, left, bottom - gap)
        tick(right, bottom - gap - mark, right, bottom - gap)
        tick(left, top + gap, left, top + gap + mark)
        tick(right, top + gap, right, top + gap + mark)
    path.write_text(
        f"#set page(width: {sheet_w:.2f}pt, height: {sheet_h:.2f}pt, margin: 0pt, fill: none)\n"
        + "\n".join(lines)
        + "\n"
    )
    out = path.with_suffix(".pdf")
    compile_typst(path, out)
    return out


def export_pages(pdf_src_typ: Path, dest_dir: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for old in dest_dir.glob("page-*.png"):
        old.unlink()
    typst = TYPST if TYPST.is_file() else "typst"
    pattern = dest_dir / "page-{p}.png"
    proc = subprocess.run(
        [
            str(typst), "compile", "--font-path", str(FONTS),
            "--format", "png", "--ppi", "110",
            str(pdf_src_typ), str(pattern),
        ],
        cwd=pdf_src_typ.parent,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        die(f"page render failed\n{proc.stdout}\n{proc.stderr}")
    return sorted(dest_dir.glob("page-*.png"), key=lambda p: int(p.stem.split("-")[1]))


def contact_sheet(pages: list[Path], dest: Path) -> None:
    thumbs = []
    for path in pages:
        with Image.open(path) as im:
            thumbs.append(im.convert("RGB"))
    if not thumbs:
        die("no pages to contact")
    w, h = thumbs[0].size
    gap = 8
    # Cover alone, then facing spreads (2-3, 4-5, ...).
    spreads = [(thumbs[0], None)]
    for i in range(1, len(thumbs), 2):
        right = thumbs[i + 1] if i + 1 < len(thumbs) else None
        spreads.append((thumbs[i], right))
    cols = 2
    rows = (len(spreads) + cols - 1) // cols
    cell_w = w * 2 + gap
    cell_h = h
    sheet = Image.new("RGB", (cols * cell_w + (cols + 1) * gap, rows * cell_h + (rows + 1) * gap), (40, 32, 28))
    for index, (left, right) in enumerate(spreads):
        r, c = divmod(index, cols)
        x = gap + c * (cell_w + gap)
        y = gap + r * (cell_h + gap)
        if right is None and index == 0:
            sheet.paste(left, (x + w // 2, y))
        else:
            sheet.paste(left, (x, y))
            if right is not None:
                sheet.paste(right, (x + w + gap, y))
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, "PNG")
    # Also one image per spread for review.
    spread_dir = dest.parent / "spreads"
    spread_dir.mkdir(parents=True, exist_ok=True)
    for index, (left, right) in enumerate(spreads):
        if right is None:
            frame = left
        else:
            frame = Image.new("RGB", (w * 2 + gap, h), (40, 32, 28))
            frame.paste(left, (0, 0))
            frame.paste(right, (w + gap, 0))
        frame.save(spread_dir / f"spread-{index:02d}.png")


def html_blocks(blocks) -> str:
    parts = []
    for block in blocks:
        kind = block[0]
        if kind == "h":
            level, text = block[1], block[2]
            parts.append(f"<h{level}>{html_inline(text)}</h{level}>")
        elif kind == "p":
            parts.append(f"<p>{html_inline(block[1])}</p>")
        elif kind == "quote":
            parts.append(f"<blockquote><p>{html_inline(block[1])}</p></blockquote>")
        elif kind == "ul":
            items = "".join(f"<li>{html_inline(item)}</li>" for item in block[1])
            parts.append(f"<ul>{items}</ul>")
        elif kind == "img":
            alt, path, caption = block[1], block[2], block[3]
            name = Path(path).name
            parts.append(
                "<figure>"
                f"<img src=\"images/{html.escape(name)}\" alt=\"{html.escape(alt)}\" width=\"{png_size(CONTENT / path)[0]}\" height=\"{png_size(CONTENT / path)[1]}\">"
                f"<figcaption>{html_inline(caption)}</figcaption>"
                "</figure>"
            )
    return "\n".join(parts)


def write_site(manifest, parsed) -> None:
    site = BUILD / "site"
    if site.exists():
        shutil.rmtree(site)
    image_dir = site / "images"
    image_dir.mkdir(parents=True)
    for image in (CONTENT / "images").glob("*.png"):
        shutil.copy2(image, image_dir / image.name)
    shutil.copy2(TOOLS / "preview.css", site / "preview.css")
    web_sections = [s for s in manifest["sections"] if s.get("web", True)]
    nav = []
    for section in web_sections:
        nav.append(f"<li><a href=\"{html.escape(section['slug'])}.html\">{html.escape(section['title'])}</a></li>")
    nav_html = "<ul>" + "".join(nav) + "</ul>"
    base = manifest["base_path"]
    blurb = manifest["blurb"]

    def page(slug, title, body, current=None):
        links = []
        for section in web_sections:
            current_attr = " aria-current=\"page\"" if section["slug"] == current else ""
            links.append(
                f"<li><a href=\"{html.escape(section['slug'])}.html\"{current_attr}>"
                f"{html.escape(section['title'])}</a></li>"
            )
        doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="quintra-manual-base" content="{html.escape(base)}">
<title>{html.escape(title)} — Quintra</title>
<link rel="stylesheet" href="preview.css">
</head>
<body>
<a class="skip" href="#content">Skip to content</a>
<header class="banner">
<p><a href="index.html"><strong>QUINTRA</strong></a></p>
<p>{html.escape(blurb)}</p>
<p>Status: {html.escape(manifest["status"])}. Cartridge title {html.escape(manifest["version_label"])}.</p>
</header>
<nav aria-label="Manual"><ul>
{''.join(links)}
</ul></nav>
<main id="content">
{body}
</main>
<footer class="colophon">
<p>struktured labs. Local preview. Relative links. Intended mount {html.escape(base)}. No scripts.</p>
</footer>
</body>
</html>
"""
        (site / f"{slug}.html").write_text(doc)
        if FORBIDDEN.search(doc):
            die(f"web page {slug} contains a forbidden string")

    index_items = "".join(
        f"<li><a href=\"{html.escape(s['slug'])}.html\">{html.escape(s['title'])}</a></li>"
        for s in web_sections
    )
    page(
        "index",
        "Instruction manual",
        f"<h1>Quintra</h1><p>{html.escape(blurb)}</p>"
        f"<p>Status: {html.escape(manifest['status'])}.</p>"
        f"<ul>{index_items}</ul>",
    )
    for section in web_sections:
        blocks = parsed[section["source"]]
        page(section["slug"], section["title"], html_blocks(blocks), current=section["slug"])
    # The PDF-only tease must not be copied into the site under any name.
    hidden = site / "after-the-sanctum.html"
    if hidden.exists():
        die("web export included the PDF-only section")
    site_text = "\n".join(p.read_text() for p in site.rglob("*.html"))
    if FORBIDDEN.search(site_text):
        die("web export contains a forbidden string")
    (site / "manual.json").write_text(json.dumps({
        "base_path": base,
        "content_package": "docs/manual/content/",
        "sections": [
            {"slug": s["slug"], "title": s["title"], "source": s["source"]}
            for s in web_sections
        ],
    }, indent=2) + "\n")


def assert_pdf_clean(pdf: Path) -> None:
    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(pdf)).pages)
    if re.search(r"hexa|dragmar", text, re.I):
        die("PDF names the hidden encounter")
    if ".gbc" in text.lower() or "itch.io" in text.lower():
        die("PDF contains a download or host link")


def main() -> None:
    subprocess.check_call([sys.executable, str(TOOLS / "make_art.py")])
    manifest = load_manifest()
    parsed = {}
    for section in manifest["sections"]:
        source = section["source"]
        text = (CONTENT / source).read_text()
        if section.get("web", True) and FORBIDDEN.search(text):
            die(f"{source} is on the web and contains a forbidden string")
        parsed[source] = parse_md(text, source)
    # PDF-only file is allowed to be cryptic and must still avoid the name.
    tease = (CONTENT / "snippets/after-the-sanctum.md").read_text()
    if re.search(r"hexa|dragmar", tease, re.I):
        die("the isolated tease names the encounter")

    image_mm = {}
    scaled = BUILD / "pdf" / "work" / "images"
    if scaled.exists():
        shutil.rmtree(scaled)
    scaled.mkdir(parents=True)
    dpi_notes = []
    for image in sorted((CONTENT / "images").glob("*.png")):
        rel = f"images/{image.name}"
        scale, width_mm, effective = upscale(image, scaled / image.name)
        image_mm[rel] = width_mm
        dpi_notes.append(f"{image.name}: native {png_size(image)[0]}px, x{scale}, effective {effective:.0f} dpi")
    (BUILD / "pdf" / "dpi.txt").write_text("\n".join(dpi_notes) + "\n")

    work = BUILD / "pdf" / "work"
    write_document(manifest, parsed, image_mm, 0.0, 0, work / "reader.typ")
    compile_typst(work / "reader.typ", work / "reader-unpadded.pdf")
    count = page_count(work / "reader-unpadded.pdf")
    pads = (4 - (count % 4)) % 4
    write_document(manifest, parsed, image_mm, 0.0, pads, work / "reader.typ")
    reader_pdf = BUILD / "pdf" / "quintra-manual.pdf"
    compile_typst(work / "reader.typ", reader_pdf)
    final_count = page_count(reader_pdf)
    if final_count % 4 != 0:
        die(f"reader PDF is {final_count} pages")
    write_document(manifest, parsed, image_mm, BLEED, pads, work / "press.typ")
    press_pdf = work / "press.pdf"
    compile_typst(work / "press.typ", press_pdf)
    if page_count(press_pdf) != final_count:
        die("press PDF page count drifted from the reader")
    booklet = BUILD / "pdf" / "quintra-manual-booklet.pdf"
    impose(press_pdf, booklet)
    assert_pdf_clean(reader_pdf)
    pages = export_pages(work / "reader.typ", BUILD / "pages")
    contact_sheet(pages, BUILD / "contact" / "spreads-contact.png")
    write_site(manifest, parsed)
    print(f"pages {final_count} (padded {pads})")
    print(f"reader {reader_pdf}")
    print(f"booklet {booklet}")
    print(f"site {BUILD / 'site' / 'index.html'}")


if __name__ == "__main__":
    main()

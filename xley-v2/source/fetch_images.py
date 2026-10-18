"""Download the Higgsfield concept images listed in assets/gen/manifest.json
and save web-sized JPEGs next to it for the deck. Composites (several images
on one canvas, e.g. the cover duo) are built from the downloaded originals.

Usage:  python3 source/fetch_images.py
Needs network access to the Higgsfield CDN host named in the manifest.
Missing images are skipped; the deck falls back to vector placeholders.
"""
import io
import json
import pathlib
import sys
import urllib.request

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
GEN = HERE / "assets" / "gen"
RAW = HERE / "assets" / "raw"          # full-size PNGs, git-ignored
MAX_EDGE = {"default": 1400, "xoxo": 900, "infl": 1000, "ep": 1100}


def max_edge(name):
    for prefix, edge in MAX_EDGE.items():
        if name.startswith(prefix):
            return edge
    return MAX_EDGE["default"]


def crop_frac(im, box):
    """Crop by a fractional [left, top, right, bottom] box."""
    l, t, r, b = box
    w, h = im.size
    return im.crop((round(l * w), round(t * h), round(r * w), round(b * h)))


def save_jpeg(im, name):
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
    (GEN / f"{name}.jpg").write_bytes(buf.getvalue())
    return len(buf.getvalue()) // 1024


def compose(comp):
    """Place raw images on a vertical-gradient canvas, fading their left and right edges into it."""
    w, h = comp["size"]
    top, bottom = comp["bg"]
    canvas = Image.new("RGB", (w, h))
    for y in range(h):
        t = y / (h - 1)
        canvas.paste(tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)), (0, y, w, y + 1))
    feather = comp.get("feather", 0)
    for layer in comp["layers"]:
        im = Image.open(RAW / f"{layer['src']}.png").convert("RGB")
        if "crop" in layer:
            im = crop_frac(im, layer["crop"])
        x, y, lw, lh = layer["box"]
        im = im.resize((lw, lh), Image.LANCZOS)
        mask = Image.new("L", (lw, lh), 255)
        for i in range(feather):
            v = round(255 * i / feather)
            mask.paste(v, (i, 0, i + 1, lh))
            mask.paste(v, (lw - 1 - i, 0, lw - i, lh))
        canvas.paste(im, (x, y), mask)
    return canvas


def main():
    manifest = json.loads((GEN / "manifest.json").read_text())
    RAW.mkdir(parents=True, exist_ok=True)
    ok = 0
    for name, item in manifest["images"].items():
        if "file" not in item:
            print(f"skip {name}: no result file recorded yet")
            continue
        raw = RAW / f"{name}.png"
        if not raw.exists():
            url = manifest["cdn"] + item["file"]
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    raw.write_bytes(r.read())
            except Exception as e:  # network policy, expired URL, etc.
                print(f"fail {name}: {e}")
                continue
        im = Image.open(raw).convert("RGB")
        if "crop" in item:
            im = crop_frac(im, item["crop"])
        edge = max_edge(name)
        im.thumbnail((edge, edge), Image.LANCZOS)
        kb = save_jpeg(im, name)
        print(f"ok   {name}: {im.size[0]}x{im.size[1]}, {kb} KB")
        ok += 1
    for name, comp in manifest.get("composites", {}).items():
        try:
            im = compose(comp)
        except FileNotFoundError as e:
            print(f"skip {name}: {pathlib.Path(e.filename).name} not downloaded")
            continue
        kb = save_jpeg(im, name)
        print(f"ok   {name}: composite {im.size[0]}x{im.size[1]}, {kb} KB")
        ok += 1
    print(f"{ok} images ready")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

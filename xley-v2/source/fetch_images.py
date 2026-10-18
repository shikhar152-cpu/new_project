"""Download the Higgsfield concept images listed in assets/gen/manifest.json
and save web-sized JPEGs next to it for the deck.

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
        if "crop" in item:  # fractional [left, top, right, bottom]
            l, t, r, b = item["crop"]
            w, h = im.size
            im = im.crop((round(l * w), round(t * h), round(r * w), round(b * h)))
        edge = max_edge(name)
        im.thumbnail((edge, edge), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
        (GEN / f"{name}.jpg").write_bytes(buf.getvalue())
        print(f"ok   {name}: {im.size[0]}x{im.size[1]}, {len(buf.getvalue())//1024} KB")
        ok += 1
    print(f"{ok} images ready")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

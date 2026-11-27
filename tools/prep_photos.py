#!/usr/bin/env python3
"""Turn your photos into 16:9 wallpaper candidates for the TV (1280x720).

    python prep_photos.py PHOTO_FOLDER_OR_FILE OUT_FOLDER [--no-pair] [--trim-bottom 0.0] [--focus 0.22]

* Portrait photos are shown two side by side (each panel 640x720), paired so the two look as different as
  possible. Near-identical burst shots are dropped when there are enough photos.
* Landscape/square photos are cropped to 16:9 on their own.
* --trim-bottom 0.1 cuts the bottom 10% of every photo first (camera watermark strips, caption bars).
* --focus is how far toward the top the crop window sits (0 = top, 0.5 = middle); 0.22 keeps faces in frame.
Originals are never modified. Needs Pillow (pillow-heif is used for .heic when installed).
"""
import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Pillow is missing: pip install pillow")
try:  # optional: iPhone / modern Android HEIC photos
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass

EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
W, H = 1280, 720


def find_photos(src):
    p = Path(src).expanduser()
    if p.is_file():
        return [p] if p.suffix.lower() in EXT else []
    return sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower() in EXT and not f.name.startswith("."))


def load(path, trim):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    if trim > 0:
        im = im.crop((0, 0, im.width, round(im.height * (1 - trim))))
    return im


def panel(im, w, h, focus):
    """Scale to cover w x h, then crop with the window biased toward the top."""
    s = max(w / im.width, h / im.height)
    im = im.resize((max(w, round(im.width * s)), max(h, round(im.height * s))), Image.LANCZOS)
    x = (im.width - w) // 2
    y = round((im.height - h) * focus)
    return im.crop((x, y, x + w, y + h))


def signature(im):
    return list(im.convert("L").resize((12, 16), Image.BILINEAR).getdata())


def dist(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def build(photos, out_dir, pair=True, trim=0.0, focus=0.22):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ims = [load(p, trim) for p in photos]
    portrait = [i for i in ims if i.height > i.width]
    other = [i for i in ims if i.height <= i.width]
    n = 0

    def save(img):
        nonlocal n
        n += 1
        img.save(out / ("%02d.jpg" % n), quality=92)

    if pair and len(portrait) >= 2:
        sigs = [signature(i) for i in portrait]
        keep = []
        for i, s in enumerate(sigs):          # drop burst duplicates, but only when there is plenty to choose from
            if all(dist(s, sigs[k]) > 14 for k in keep):
                keep.append(i)
        if len(keep) < 4:
            keep = list(range(len(portrait)))
        rest = list(keep)
        pairs = []
        while len(rest) > 1:
            a = rest.pop(0)
            b = max(rest, key=lambda k: dist(sigs[a], sigs[k]))
            rest.remove(b)
            pairs.append((a, b))
        if rest:
            pairs.append((rest[0], pairs[0][1] if pairs else rest[0]))
        for a, b in pairs:
            c = Image.new("RGB", (W, H))
            c.paste(panel(portrait[a], W // 2, H, focus), (0, 0))
            c.paste(panel(portrait[b], W // 2, H, focus), (W // 2, 0))
            save(c)
    else:
        for im in portrait:
            save(panel(im, W, H, focus))
    for im in other:
        save(panel(im, W, H, 0.3))
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("out")
    ap.add_argument("--no-pair", action="store_true", help="never put two portraits side by side")
    ap.add_argument("--trim-bottom", type=float, default=0.0, metavar="FRACTION")
    ap.add_argument("--focus", type=float, default=0.22)
    a = ap.parse_args(argv)
    photos = find_photos(a.source)
    if not photos:
        sys.exit("no photos found in %s" % a.source)
    if not 0 <= a.trim_bottom < 0.5 or not 0 <= a.focus <= 1:
        sys.exit("--trim-bottom must be 0..0.5 and --focus 0..1")
    count = build(photos, a.out, pair=not a.no_pair, trim=a.trim_bottom, focus=a.focus)
    print("%d photos -> %d wallpapers in %s" % (len(photos), count, a.out))


if __name__ == "__main__":
    main()

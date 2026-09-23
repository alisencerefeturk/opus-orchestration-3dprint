#!/usr/bin/env python3
"""Render a labelled 2x2 contact sheet of a model for visual review.

Views: isometric (perspective), front, right, bottom (orthographic).
Input: a .scad file, or an .stl/.3mf/.off (wrapped in an OpenSCAD import()).

Image size is chosen for Claude's vision limits on high-resolution models
(Opus 4.7 and later: long edge <= 2576 px, <= 4784 visual tokens, one token
per 28x28 px patch). A sheet within those limits is seen at full resolution;
a larger one is silently downscaled.

  --mode draft   tiles 700 px  -> sheet 1400x1456, ~2,600 tokens
  --mode final   tiles 952 px  -> sheet 1904x1960, ~4,760 tokens (max native)

Close-up of one area (single image, draft-tile size unless --size is given):

  render_sheet.py part.scad --closeup "tx,ty,tz,rx,ry,rz,dist" -o detail.png

Needs OpenSCAD and Pillow. Set OPENSCAD=/path/to/openscad if it isn't on PATH.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

# name, OpenSCAD gimbal rotation (rx,ry,rz), projection
VIEWS = [
    ("isometric", "55,0,25", "perspective"),
    ("front (-Y)", "90,0,0", "ortho"),
    ("right (+X)", "90,0,90", "ortho"),
    ("bottom (bed face)", "180,0,0", "ortho"),
]
TILE = {"draft": 700, "final": 952}
LABEL_H = 28
MAX_EDGE = 2576


def find_openscad():
    for cand in (
        os.environ.get("OPENSCAD"),
        shutil.which("openscad"),
        "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD",
    ):
        if cand and os.path.exists(cand):
            return cand
    sys.exit("OpenSCAD not found: install it or set OPENSCAD=/path/to/openscad")


def scad_source(path, tmp):
    if path.lower().endswith(".scad"):
        return os.path.abspath(path)
    wrapper = os.path.join(tmp, "wrap.scad")
    with open(wrapper, "w") as f:
        f.write('import("%s");\n' % os.path.abspath(path).replace('"', '\\"'))
    return wrapper


def render(openscad, src, out, size, camera, projection, viewall):
    cmd = [openscad, "-o", out, "--imgsize=%d,%d" % (size, size),
           "--camera=" + camera, "--projection=" + projection]
    if viewall:
        cmd += ["--viewall", "--autocenter"]
    cmd.append(src)
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(out):
        sys.exit("OpenSCAD failed:\n" + res.stderr[-2000:])
    return [l for l in res.stderr.splitlines() if "WARNING" in l or "ERROR" in l]


def font(px):
    for p in ("/System/Library/Fonts/Helvetica.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, px)
    return ImageFont.load_default()


def labelled(img, text):
    tile = Image.new("RGB", (img.width, img.height + LABEL_H), "white")
    tile.paste(img, (0, LABEL_H))
    ImageDraw.Draw(tile).text((8, 4), text, fill="black", font=font(18))
    return tile


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model")
    ap.add_argument("-o", "--out", help="output PNG (default: <model>-sheet.png)")
    ap.add_argument("--mode", choices=TILE, default="draft")
    ap.add_argument("--closeup", metavar="CAMERA",
                    help='single close-up, OpenSCAD camera "tx,ty,tz,rx,ry,rz,dist"')
    ap.add_argument("--projection", default="perspective", choices=["perspective", "ortho"],
                    help="projection for --closeup")
    ap.add_argument("--size", type=int, help="override tile/close-up size in px")
    args = ap.parse_args()

    openscad = find_openscad()
    base = os.path.splitext(args.model)[0]
    with tempfile.TemporaryDirectory() as tmp:
        src = scad_source(args.model, tmp)

        if args.closeup:
            out = args.out or base + "-closeup.png"
            size = min(args.size or TILE["draft"], MAX_EDGE)
            warnings = render(openscad, src, out, size, args.closeup,
                              args.projection, viewall=False)
        else:
            out = args.out or base + "-sheet.png"
            size = args.size or TILE[args.mode]
            if 2 * (size + LABEL_H) > MAX_EDGE:
                sys.exit("tile too large: the sheet would exceed %d px and be downscaled"
                         % MAX_EDGE)
            tiles, warnings = [], []
            for i, (name, rot, proj) in enumerate(VIEWS):
                png = os.path.join(tmp, "v%d.png" % i)
                warnings += render(openscad, src, png, size,
                                   "0,0,0,%s,0" % rot, proj, viewall=True)
                tiles.append(labelled(Image.open(png).convert("RGB"), name))
            w, h = tiles[0].size
            sheet = Image.new("RGB", (2 * w, 2 * h), "white")
            for i, t in enumerate(tiles):
                sheet.paste(t, ((i % 2) * w, (i // 2) * h))
            draw = ImageDraw.Draw(sheet)
            draw.line([(w, 0), (w, 2 * h)], fill="gray", width=2)
            draw.line([(0, h), (2 * w, h)], fill="gray", width=2)
            sheet.save(out, optimize=True)  # PNG: lossless, no compression artifacts

    im = Image.open(out)
    tokens = -(-im.width // 28) * -(-im.height // 28)
    print("%s  %dx%d px  ~%d visual tokens" % (out, im.width, im.height, tokens))
    for w in dict.fromkeys(warnings):
        print(w)


if __name__ == "__main__":
    main()

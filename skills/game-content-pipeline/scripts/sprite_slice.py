#!/usr/bin/env python3
"""Slice a sprite sheet into frames + TexturePacker-style JSON for Paper2D.

Paper2D natively imports TexturePacker JSON ("smart" format): drop the JSON
next to the sheet PNG in the UE Content Browser and it creates the texture,
sprites, and (via Sprite Actions) flipbooks.

Usage:
  python sprite_slice.py sheet.png --cols 8 --rows 4 --out-dir frames/ --json sheet.paper2d.json
  python sprite_slice.py sheet.png --cols 8 --rows 4 --json sheet.paper2d.json --no-frames
  python sprite_slice.py sheet.png --cols 8 --rows 4 --trim   # skip fully-transparent cells
"""
import argparse
import json
import os
import sys

from PIL import Image


def main():
    p = argparse.ArgumentParser()
    p.add_argument("sheet", help="input sprite sheet PNG")
    p.add_argument("--cols", type=int, required=True)
    p.add_argument("--rows", type=int, required=True)
    p.add_argument("--out-dir", default=None, help="write individual frame PNGs here")
    p.add_argument("--json", default=None, help="write Paper2D/TexturePacker JSON here")
    p.add_argument("--name", default=None, help="base frame name (default: sheet filename)")
    p.add_argument("--trim", action="store_true", help="skip fully transparent cells")
    p.add_argument("--no-frames", action="store_true", help="JSON only, no per-frame PNGs")
    args = p.parse_args()

    img = Image.open(args.sheet).convert("RGBA")
    w, h = img.size
    fw, fh = w // args.cols, h // args.rows
    if w % args.cols or h % args.rows:
        print(f"WARN: {w}x{h} not evenly divisible by {args.cols}x{args.rows}; "
              f"using {fw}x{fh} cells, edge pixels dropped", file=sys.stderr)

    base = args.name or os.path.splitext(os.path.basename(args.sheet))[0]
    frames = {}
    idx = 0
    for r in range(args.rows):
        for c in range(args.cols):
            box = (c * fw, r * fh, (c + 1) * fw, (r + 1) * fh)
            cell = img.crop(box)
            if args.trim and cell.getbbox() is None:
                continue
            fname = f"{base}_{idx:03d}.png"
            frames[fname] = {
                "frame": {"x": box[0], "y": box[1], "w": fw, "h": fh},
                "rotated": False,
                "trimmed": False,
                "spriteSourceSize": {"x": 0, "y": 0, "w": fw, "h": fh},
                "sourceSize": {"w": fw, "h": fh},
                "pivot": {"x": 0.5, "y": 0.5},
            }
            if args.out_dir and not args.no_frames:
                os.makedirs(args.out_dir, exist_ok=True)
                cell.save(os.path.join(args.out_dir, fname))
            idx += 1

    if args.json:
        doc = {
            "frames": frames,
            "meta": {
                "app": "sprite_slice.py",
                "image": os.path.basename(args.sheet),
                "format": "RGBA8888",
                "size": {"w": w, "h": h},
                "scale": "1",
            },
        }
        with open(args.json, "w") as f:
            json.dump(doc, f, indent=2)

    print(f"{idx} frames ({fw}x{fh})"
          + (f" -> {args.out_dir}" if args.out_dir and not args.no_frames else "")
          + (f", JSON -> {args.json}" if args.json else ""))


if __name__ == "__main__":
    main()

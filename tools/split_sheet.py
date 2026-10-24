# -*- coding: utf-8 -*-
"""把表情包拼图（网格图）切成单张：按白色/浅色间隔做连通域切割，自动切开黏连块。

用法：python tools/split_sheet.py incoming/acfun/sjzx_01.jpg [更多图...]
输出：incoming/sheet/<名字>_NN.png
"""
from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "incoming" / "sheet"
MIN_SIDE = 38
MIN_AREA = 900
TARGET = 360


def components(mask: np.ndarray, min_side=MIN_SIDE, min_area=MIN_AREA):
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    boxes = []
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or seen[y, x]:
                continue
            q = deque([(x, y)])
            seen[y, x] = True
            x0 = x1 = x
            y0 = y1 = y
            n = 0
            while q:
                cx, cy = q.popleft()
                n += 1
                x0, x1 = min(x0, cx), max(x1, cx)
                y0, y1 = min(y0, cy), max(y1, cy)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((nx, ny))
            if n >= min_area and (x1 - x0) >= min_side and (y1 - y0) >= min_side:
                boxes.append((x0, y0, x1 + 1, y1 + 1, n))
    return boxes


def split_box(box, gray, depth=0):
    """把明显过宽的块从最亮的竖列切开，过高的块从最亮的横排切开。"""
    x0, y0, x1, y1, _ = box
    w, h = x1 - x0, y1 - y0
    if w > 1.5 * h:
        lo, hi = x0 + int(w * 0.25), x0 + int(w * 0.75)
        if hi - lo >= 4:
            cols = gray[y0:y1, lo:hi].mean(axis=0)
            cut = lo + int(np.argmax(cols))
            return (split_box((x0, y0, cut, y1, 0), gray, depth + 1)
                    + split_box((cut, y0, x1, y1, 0), gray, depth + 1))
    if h > 1.5 * w:
        lo, hi = y0 + int(h * 0.25), y0 + int(h * 0.75)
        if hi - lo >= 4:
            rows = gray[lo:hi, x0:x1].mean(axis=1)
            cut = lo + int(np.argmax(rows))
            return (split_box((x0, y0, x1, cut, 0), gray, depth + 1)
                    + split_box((x0, cut, x1, y1, 0), gray, depth + 1))
    return [box]


def split(path: Path, tag: str):
    img = Image.open(path).convert("RGB")
    a = np.asarray(img).astype(np.int16)
    gray = a.mean(axis=2)
    near_white = (a.min(axis=2) > 228) & ((a.max(axis=2) - a.min(axis=2)) < 22)
    mask = ~near_white
    boxes = components(mask)
    refined = []
    for b in boxes:
        refined += split_box(b, gray)
    refined = [b for b in refined
               if (b[2] - b[0]) >= MIN_SIDE and (b[3] - b[1]) >= MIN_SIDE]
    print(f"{path.name}: {len(refined)} cells")
    made = []
    for i, (x0, y0, x1, y1, _) in enumerate(refined, 1):
        crop = img.crop((x0, y0, x1, y1))
        w, h = crop.size
        scale = TARGET / min(w, h)
        crop = crop.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        crop = crop.filter(ImageFilter.UnsharpMask(radius=1.6, percent=90, threshold=3))
        out = OUT / f"{tag}_{i:03d}.png"
        crop.save(out)
        made.append(out)
    return made


def main(argv):
    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    for p in argv:
        made += split(Path(p), Path(p).stem)
    print("total", len(made))
    if made:
        cols, cell = 8, 170
        rows = (len(made) + cols - 1) // cols
        sheet = Image.new("RGB", (cell * cols, cell * rows), (246, 244, 240))
        for i, p in enumerate(made):
            im = Image.open(p).convert("RGB")
            im.thumbnail((cell - 8, cell - 8))
            sheet.paste(im, ((i % cols) * cell + 4, (i // cols) * cell + 4))
        sheet.save(ROOT / "preview" / "sheet_split_check.png")
        print("saved preview/sheet_split_check.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

# -*- coding: utf-8 -*-
"""把切好的单张表情加入 memes/：按感知哈希去重，接在后面编号。

用法：python tools/add_sheet_memes.py <图片或目录> ...
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
MEMES = ROOT / "memes"
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
BATCH = "acfun"


def ahash_bits(img: Image.Image) -> str:
    g = img.convert("L").resize((16, 16), Image.LANCZOS)
    px = list(g.getdata())
    avg = sum(px) / len(px)
    return "".join("1" if v > avg else "0" for v in px)


def ham(a: str, b: str) -> int:
    return sum(1 for x, y in zip(a, b) if x != y)


def collect(argv) -> list[Path]:
    files = []
    for arg in argv:
        p = Path(arg)
        if p.is_dir():
            files += sorted(q for q in p.iterdir() if q.suffix.lower() in EXTS)
        elif p.is_file():
            files.append(p)
    return files


def main(argv):
    files = collect(argv)
    if not files:
        print("no input")
        return 1

    existing = []
    for p in sorted(MEMES.glob("hajimi_*.jpg")):
        try:
            existing.append((p.name, ahash_bits(Image.open(p).convert("RGB"))))
        except Exception:
            pass

    src_file = MEMES / "sources.json"
    sources = json.loads(src_file.read_text("utf-8")) if src_file.exists() else []
    next_idx = max([int(re.findall(r"\d+", p.stem)[0])
                    for p in MEMES.glob("hajimi_*.jpg")] or [0]) + 1

    added = dup = skipped = 0
    for p in files:
        try:
            img = Image.open(p).convert("RGB")
        except Exception:
            skipped += 1
            continue
        h = ahash_bits(img)
        if any(ham(h, eh) <= 8 for _, eh in existing):
            dup += 1
            continue
        w, ht = img.size
        if min(w, ht) < 110:
            skipped += 1
            continue
        name = f"hajimi_{next_idx:02d}.jpg"
        img.save(MEMES / name, quality=92)
        existing.append((name, h))
        sources.append({"file": name, "query": "AcFun 三角洲鼠鼠哈基米", "src": "",
                        "title": p.stem, "batch": BATCH})
        next_idx += 1
        added += 1

    src_file.write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"added {added}, duplicate {dup}, skipped {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

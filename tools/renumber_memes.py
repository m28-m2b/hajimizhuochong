# -*- coding: utf-8 -*-
"""把 memes/ 里的图重新按 01..N 连续编号，并同步更新 sources.json。"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEMES = ROOT / "memes"


def main() -> int:
    files = sorted(MEMES.glob("hajimi_*.jpg"), key=lambda p: int(re.findall(r"\d+", p.stem)[0]))
    meta = {}
    src_file = MEMES / "sources.json"
    if src_file.exists():
        for item in json.loads(src_file.read_text("utf-8")):
            meta[item["file"]] = item

    # 先改成临时名，避免重命名冲突
    tmp = []
    for i, p in enumerate(files, 1):
        t = p.with_name(f"tmp_{i:03d}.jpg")
        p.rename(t)
        tmp.append((t, i))

    out = []
    for t, i in tmp:
        new = MEMES / f"hajimi_{i:02d}.jpg"
        t.rename(new)
        old_name = files[i - 1].name
        item = meta.get(old_name, {"query": "", "src": "", "title": ""})
        item["file"] = new.name
        out.append(item)

    src_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"renumbered {len(out)} images")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

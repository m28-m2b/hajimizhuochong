# -*- coding: utf-8 -*-
"""按 memes/sources.json 重新下载原图，保留原始比例（不裁切），避免梗图上的字被切掉。

用法：python tools/refetch_uncropped.py
"""
from __future__ import annotations

import io
import json
import socket
import ssl
import sys
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MEMES = ROOT / "memes"
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
      "Referer": "https://image.so.com/"}
CTX = ssl._create_unverified_context()
MAX = 620


def main() -> int:
    socket.setdefaulttimeout(20)
    meta = json.loads((MEMES / "sources.json").read_text("utf-8"))
    ok = fail = 0
    for item in meta:
        name, url = item["file"], item["src"]
        try:
            req = urllib.request.Request(url, headers=UA)
            raw = urllib.request.urlopen(req, timeout=20, context=CTX).read()
            img = Image.open(io.BytesIO(raw))
            img.load()
            img = img.convert("RGB")
        except Exception as exc:
            print(f"[warn] {name}: {exc}")
            fail += 1
            continue
        w, h = img.size
        scale = min(1.0, MAX / max(w, h))
        if scale < 1.0:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        img.save(MEMES / name, quality=92)
        print(f"  {name}: {w}x{h} -> {img.size[0]}x{img.size[1]}")
        ok += 1
    print(f"\nrefetched {ok}, failed {fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

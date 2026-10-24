# -*- coding: utf-8 -*-
"""把 imageio-ffmpeg wheel 里的 ffmpeg.exe 取出来，放到 .build/（仅用于把 mp3 转 wav）。"""
from __future__ import annotations

import io
import json
import ssl
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / ".build"
CTX = ssl._create_unverified_context()
UA = {"User-Agent": "Mozilla/5.0"}


def main() -> int:
    data = json.loads(urllib.request.urlopen(
        urllib.request.Request("https://pypi.org/pypi/imageio-ffmpeg/json", headers=UA),
        timeout=30, context=CTX).read())
    wheel = next((f for f in data["urls"]
                  if f["filename"].endswith("win_amd64.whl")), None)
    if not wheel:
        print("no win_amd64 wheel")
        return 1
    print("downloading", wheel["filename"], wheel["size"] // 1024 // 1024, "MB")
    raw = urllib.request.urlopen(urllib.request.Request(wheel["url"], headers=UA),
                                 timeout=300, context=CTX).read()
    BUILD.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for name in z.namelist():
            if name.lower().endswith(".exe") and "ffmpeg" in name.lower():
                target = BUILD / "ffmpeg.exe"
                target.write_bytes(z.read(name))
                print("extracted ->", target, target.stat().st_size // 1024 // 1024, "MB")
                return 0
    print("ffmpeg.exe not found in wheel")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

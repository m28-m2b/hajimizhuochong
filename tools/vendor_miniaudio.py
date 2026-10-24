# -*- coding: utf-8 -*-
"""直接下载 miniaudio 的 wheel 并解压到 vendor/（绕过 pip 的临时目录限制）。

miniaudio 里打包了 dr_mp3/dr_wav/dr_flac，可以纯 Python 解码 mp3，不需要 ffmpeg。
"""
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
VENDOR = ROOT / "vendor"
CTX = ssl._create_unverified_context()
UA = {"User-Agent": "Mozilla/5.0"}


def main() -> int:
    meta_url = "https://pypi.org/pypi/miniaudio/json"
    data = json.loads(urllib.request.urlopen(
        urllib.request.Request(meta_url, headers=UA), timeout=30, context=CTX).read())
    version = data["info"]["version"]
    tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    wheel = None
    for f in data["urls"]:
        name = f["filename"]
        if name.endswith(".whl") and tag in name and "win_amd64" in name:
            wheel = f
            break
    if not wheel:
        print("no matching wheel for", tag)
        return 1
    print("picking", wheel["filename"], wheel["size"] // 1024, "KB")
    raw = urllib.request.urlopen(
        urllib.request.Request(wheel["url"], headers=UA), timeout=120, context=CTX).read()
    VENDOR.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        z.extractall(VENDOR)
    print("extracted to", VENDOR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

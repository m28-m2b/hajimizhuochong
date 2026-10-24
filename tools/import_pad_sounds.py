# -*- coding: utf-8 -*-
"""抓 HajimiPad 音效板「第一个板块（哈基米原聲大碟）」的 9 个音效，转成 wav。

用法：python tools/import_pad_sounds.py
"""
from __future__ import annotations

import json
import ssl
import subprocess
import sys
import urllib.parse
import urllib.request
import wave
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sounds"
TMP = ROOT / ".build" / "tmp"
FFMPEG = ROOT / ".build" / "ffmpeg.exe"
BASE = "https://hibikiwtnb.github.io/HajimiPad/audio/"
SR = 22050
CTX = ssl._create_unverified_context()
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")}

# HajimiPad 音效板第 1 个板块
FIRST_BOARD = [
    ("私人笑声1.m4a", "pad_01", "私人笑声1"),
    ("私人笑声2.m4a", "pad_02", "私人笑声2"),
    ("私人笑声3.m4a", "pad_03", "私人笑声3"),
    ("哈基米1.m4a", "pad_04", "哈基米1"),
    ("哈基米2.m4a", "pad_05", "哈基米2"),
    ("南北绿豆.m4a", "pad_06", "南北绿豆"),
    ("曼波.m4a", "pad_07", "曼波"),
    ("wow.m4a", "pad_08", "wow"),
    ("欧耶.m4a", "pad_09", "欧耶"),
]
MAX_SECONDS = 4.0
PEAK = 0.72


def download(url: str) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                  timeout=60, context=CTX).read()


def to_wav(src: Path, dst: Path) -> bool:
    cmd = [str(FFMPEG), "-y", "-loglevel", "error", "-i", str(src),
           "-ac", "1", "-ar", str(SR), "-t", str(MAX_SECONDS), str(dst)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        print("   ffmpeg:", r.stderr.decode("utf-8", "ignore")[:150])
        return False
    return dst.exists()


def polish(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        raw = w.readframes(w.getnframes())
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    peak = float(np.abs(x).max()) or 1.0
    x = x / peak * PEAK
    k = int(SR * 0.02)
    if len(x) > 2 * k:
        x[:k] *= np.linspace(0, 1, k)
        x[-k:] *= np.linspace(1, 0, k)
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return len(x) / SR


def main() -> int:
    if not FFMPEG.exists():
        print("缺少 ffmpeg，请先运行 python tools/get_ffmpeg.py")
        return 1
    OUT.mkdir(exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    meta = []
    ok = 0
    for fname, stem, label in FIRST_BOARD:
        url = BASE + urllib.parse.quote(fname)
        try:
            data = download(url)
        except Exception as exc:
            print(f"[warn] {fname}: {exc}")
            continue
        src = TMP / fname
        src.write_bytes(data)
        dst = OUT / f"{stem}.wav"
        if not to_wav(src, dst):
            continue
        dur = polish(dst)
        meta.append({"file": dst.name, "label": label, "src": url, "seconds": round(dur, 2)})
        print(f"  {dst.name}  {dur:.2f}s  {len(data)/1024:.0f}KB  <- {label}")
        ok += 1
        src.unlink(missing_ok=True)

    meta_file = OUT / "hajimi_sources.json"
    old = json.loads(meta_file.read_text("utf-8")) if meta_file.exists() else []
    old = [m for m in old if not m["file"].startswith("pad_")]
    meta_file.write_text(json.dumps(old + meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ndone {ok}/{len(FIRST_BOARD)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

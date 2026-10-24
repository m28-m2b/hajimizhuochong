# -*- coding: utf-8 -*-
"""从酷我下哈基米/曼波音频 -> ffmpeg 解码 -> 自动挑一段最响亮的片段 -> 存成 wav。

用法：python tools/make_hajimi_sounds.py --count 6
产物：sounds/hajimi_01.wav ... + sounds/hajimi_sources.json
"""
from __future__ import annotations

import argparse
import ast
import json
import socket
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
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
      "Referer": "https://www.kuwo.cn/"}
CTX = ssl._create_unverified_context()
SR = 22050
QUERIES = ["哈基米 曼波", "哈基米", "曼波 哈基米", "哈基米 BGM"]


def get(url, timeout=30):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                  timeout=timeout, context=CTX).read()


def search(keyword, n=20):
    q = urllib.parse.quote(keyword)
    url = (f"http://search.kuwo.cn/r.s?all={q}&ft=music&itemset=web_2013&client=kt"
           f"&pn=0&rn={n}&rformat=json&encoding=utf8")
    txt = get(url).decode("utf-8", "ignore")
    try:
        data = ast.literal_eval(txt)
    except Exception:
        return []
    out = []
    for it in data.get("abslist") or []:
        rid = str(it.get("MUSICRID", "")).replace("MUSIC_", "")
        if not rid.isdigit():
            continue
        out.append({"rid": rid, "name": (it.get("SONGNAME") or "").replace("&nbsp;", " "),
                    "artist": (it.get("ARTIST") or "").replace("&nbsp;", " "),
                    "duration": int(it.get("DURATION") or 0)})
    return out


def audio_url(rid):
    url = (f"http://antiserver.kuwo.cn/anti.s?type=convert_url3&rid=MUSIC_{rid}"
           "&format=mp3&response=url")
    return json.loads(get(url).decode("utf-8", "ignore")).get("url")


def decode_to_mono(mp3: Path, wav: Path) -> bool:
    cmd = [str(FFMPEG), "-y", "-loglevel", "error", "-i", str(mp3),
           "-ac", "1", "-ar", str(SR), "-vn", str(wav)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        print("   ffmpeg fail:", r.stderr.decode("utf-8", "ignore")[:120])
        return False
    return wav.exists()


def read_wav(path: Path):
    with wave.open(str(path), "rb") as w:
        n = w.getnframes()
        ch = w.getnchannels()
        raw = w.readframes(n)
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x


def best_window(x: np.ndarray, seconds: float = 3.4) -> tuple[int, int]:
    """找一个平均能量最高的窗口。"""
    win = int(SR * seconds)
    if len(x) <= win:
        return 0, len(x)
    hop = int(SR * 0.1)
    frames = (len(x) - win) // hop
    best, best_score = 0, -1.0
    for i in range(frames + 1):
        seg = x[i * hop:i * hop + win]
        rms = float(np.sqrt((seg ** 2).mean()))
        peak = float(np.abs(seg).max())
        if peak < 0.05:
            continue
        # 偏好响亮但不削顶的片段
        score = rms * (1.0 - max(0.0, peak - 0.95))
        if score > best_score:
            best, best_score = i * hop, score
    return best, best + win


def save_wav(path: Path, x: np.ndarray):
    x = np.clip(x, -1, 1)
    pcm = (x * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=6)
    ap.add_argument("--seconds", type=float, default=3.4)
    args = ap.parse_args(argv)

    socket.setdefaulttimeout(30)
    OUT.mkdir(exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    meta_file = OUT / "hajimi_sources.json"
    meta = json.loads(meta_file.read_text("utf-8")) if meta_file.exists() else []
    used_rid = {m["rid"] for m in meta}
    idx = len(meta)

    for q in QUERIES:
        if idx >= args.count:
            break
        try:
            songs = search(q)
        except Exception as exc:
            print("[warn]", q, exc)
            continue
        print(f"[info] {q}: {len(songs)}")
        for s in songs:
            if idx >= args.count:
                break
            if s["rid"] in used_rid:
                continue
            title = f"{s['name']} - {s['artist']}"
            print(f"  try {title[:36]}")
            try:
                url = audio_url(s["rid"])
                if not url:
                    print("   no url")
                    continue
                raw = get(url)
            except Exception as exc:
                print("   download fail:", exc)
                continue
            if len(raw) < 50000:
                print("   too small")
                continue
            mp3 = TMP / f"{s['rid']}.mp3"
            mp3.write_bytes(raw)
            wav_tmp = TMP / f"{s['rid']}.wav"
            if not decode_to_mono(mp3, wav_tmp):
                continue
            x = read_wav(wav_tmp)
            if len(x) < SR:
                print("   too short")
                continue
            a, b = best_window(x, args.seconds)
            seg = x[a:b].copy()
            # 30ms 淡入淡出
            k = int(SR * 0.03)
            seg[:k] *= np.linspace(0, 1, k)
            seg[-k:] *= np.linspace(1, 0, k)
            if np.abs(seg).max() < 1e-6:
                print("   silent")
                continue
            seg = seg / max(1.0, np.abs(seg).max()) * 0.9
            idx += 1
            name = f"hajimi_{idx:02d}.wav"
            save_wav(OUT / name, seg)
            meta.append({"file": name, "rid": s["rid"], "title": title,
                         "src": url, "from_s": round(a / SR, 2),
                         "seconds": round(len(seg) / SR, 2)})
            used_rid.add(s["rid"])
            print(f"   saved {name}  {len(seg)/SR:.1f}s (from {a/SR:.1f}s)")
            mp3.unlink(missing_ok=True)
            wav_tmp.unlink(missing_ok=True)

    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ntotal {idx} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

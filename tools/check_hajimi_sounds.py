# -*- coding: utf-8 -*-
"""检查抓来的哈基米片段：时长/响度/频谱，并统一音量后输出一张检查图。"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
SOUNDS = ROOT / "sounds"
SR = 22050
TARGET_PEAK = 0.72


def read(path):
    with wave.open(str(path), "rb") as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def write(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def spec(x, n_fft=1024, hop=256):
    win = np.hanning(n_fft)
    frames = max(1, (len(x) - n_fft) // hop)
    out = np.zeros((frames, n_fft // 2))
    for i in range(frames):
        out[i] = np.abs(np.fft.rfft(x[i * hop:i * hop + n_fft] * win))[: n_fft // 2]
    out = 20 * np.log10(out + 1e-6)
    return np.clip((out + 60) / 60, 0, 1).T[::-1]


def main():
    files = sorted(SOUNDS.glob("hajimi_*.wav"))
    if not files:
        print("no clips")
        return 1
    rows, stats = [], []
    for p in files:
        x = read(p)
        peak = float(np.abs(x).max()) or 1.0
        x = x / peak * TARGET_PEAK          # 统一音量
        write(p, x)
        rms = float(np.sqrt((x ** 2).mean()))
        sp = np.abs(np.fft.rfft(x * np.hanning(len(x))))
        freqs = np.fft.rfftfreq(len(x), 1 / SR)
        dom = float(freqs[int(np.argmax(sp))])
        stats.append((p.name, len(x) / SR, rms, peak, dom))
        rows.append((p.name, x))

    cw, wh, sh, pad = 520, 80, 100, 8
    img = Image.new("RGB", (190 + cw + 16, len(rows) * (wh + sh + pad) + 50), (16, 18, 24))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 14)
    small = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 12)
    for i, (name, x) in enumerate(rows):
        y0 = 40 + i * (wh + sh + pad)
        d.text((8, y0), name, font=font, fill=(235, 235, 235))
        st = stats[i]
        d.text((8, y0 + 20), f"{st[1]:.2f}s  rms {st[2]:.2f}", font=small, fill=(150, 200, 255))
        d.text((8, y0 + 38), f"主频 {st[4]:.0f}Hz", font=small, fill=(150, 200, 255))
        wv = np.zeros((wh, cw, 3), dtype=np.uint8)
        mid = wh // 2
        for px in range(cw):
            a = int(px / cw * len(x))
            b = max(a + 1, int((px + 1) / cw * len(x)))
            seg = x[a:b]
            lo = int(mid - seg.max() * (mid - 2))
            hi = int(mid - seg.min() * (mid - 2))
            wv[lo:hi + 1, px] = (110, 220, 160)
        img.paste(Image.fromarray(wv), (190, y0))
        sg = spec(x)
        g = Image.fromarray((sg * 255).astype(np.uint8)).resize((cw, sh))
        ga = np.asarray(g).astype(np.float32)
        tint = np.stack([ga * 0.5, ga * 0.95, ga * 1.0], axis=2).clip(0, 255).astype(np.uint8)
        img.paste(Image.fromarray(tint), (190, y0 + wh + 2))

    out = ROOT / "preview" / "hajimi_sound_check.png"
    out.parent.mkdir(exist_ok=True)
    img.save(out)
    for s in stats:
        print(f"{s[0]:14s} {s[1]:.2f}s rms={s[2]:.3f} peak={s[3]:.2f} dom={s[4]:.0f}Hz")
    print("saved", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

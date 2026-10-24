# -*- coding: utf-8 -*-
"""检查合成音效：时长、响度、主频，并画出波形 + 频谱图，方便肉眼验证。

用法：python tools/check_sounds.py
输出：preview/sound_check.png
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hajimi_sound import SOUNDS, SR  # noqa: E402


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        n = w.getnframes()
        raw = w.readframes(n)
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def spectrogram(x: np.ndarray, n_fft: int = 1024, hop: int = 256) -> np.ndarray:
    win = np.hanning(n_fft)
    frames = max(1, (len(x) - n_fft) // hop)
    out = np.zeros((frames, n_fft // 2))
    for i in range(frames):
        seg = x[i * hop:i * hop + n_fft] * win
        spec = np.abs(np.fft.rfft(seg))[: n_fft // 2]
        out[i] = spec
    out = 20 * np.log10(out + 1e-6)
    out = np.clip((out + 60) / 60, 0, 1)
    return out.T[::-1]          # 频率轴翻上去，方便看图


def main() -> int:
    folder = ROOT / "sounds"
    rows = []
    stats = []
    for name in SOUNDS:
        path = folder / f"{name}.wav"
        if not path.exists():
            print(f"missing {path}")
            return 1
        x = read_wav(path)
        dur = len(x) / SR
        rms = float(np.sqrt((x ** 2).mean()))
        peak = float(np.abs(x).max())
        spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
        freqs = np.fft.rfftfreq(len(x), 1 / SR)
        dom = float(freqs[int(np.argmax(spec))])
        stats.append((name, dur, rms, peak, dom))
        rows.append((name, x, spectrogram(x)))

    cell_w, wave_h, spec_h, pad = 520, 90, 110, 10
    W = 200 + cell_w + pad * 2
    H = len(rows) * (wave_h + spec_h + pad) + 60
    img = Image.new("RGB", (W, H), (16, 18, 24))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 14)
    small = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 12)

    for i, (name, x, sg) in enumerate(rows):
        y0 = 50 + i * (wave_h + spec_h + pad)
        d.text((10, y0), name, font=font, fill=(240, 240, 240))
        st = stats[i]
        d.text((10, y0 + 20), f"{st[1]:.2f}s", font=small, fill=(150, 200, 255))
        d.text((10, y0 + 38), f"主频 {st[4]:.0f}Hz", font=small, fill=(150, 200, 255))

        # 波形
        wv = np.zeros((wave_h, cell_w, 3), dtype=np.uint8)
        mid = wave_h // 2
        for px in range(cell_w):
            a = int(px / cell_w * len(x))
            b = int((px + 1) / cell_w * len(x))
            seg = x[a:b]
            if len(seg):
                lo = int(mid - seg.max() * (mid - 2))
                hi = int(mid - seg.min() * (mid - 2))
                wv[lo:hi + 1, px] = (110, 220, 160)
        img.paste(Image.fromarray(wv), (200, y0))

        # 频谱
        g = Image.fromarray((sg * 255).astype(np.uint8)).resize((cell_w, spec_h))
        ga = np.asarray(g).astype(np.float32)
        tint = np.stack([ga * 0.45, ga * 0.9, ga * 1.0], axis=2).clip(0, 255).astype(np.uint8)
        img.paste(Image.fromarray(tint), (200, y0 + wave_h + 2))

    out = ROOT / "preview" / "sound_check.png"
    out.parent.mkdir(exist_ok=True)
    img.save(out)
    for s in stats:
        print(f"{s[0]:12s} dur={s[1]:.2f}s rms={s[2]:.3f} peak={s[3]:.2f} dom={s[4]:.0f}Hz")
    print("saved", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

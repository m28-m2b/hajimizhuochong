# -*- coding: utf-8 -*-
"""哈基米音效：全部用代码合成，不依赖任何音频素材。

包含：短喵、撒娇喵、长喵呜、哈基米唱歌、呼噜、惊讶叽、弹跳、啵、星星音、
呜咽、低吼、嘿嘿笑。合成后存成 wav 到 sounds/，播放走 winsound（异步、不阻塞）。

单独跑一次可以试听/重建：
    python hajimi_sound.py --render sounds --play meow_short
"""
from __future__ import annotations

import argparse
import math
import wave
from pathlib import Path

import numpy as np

SR = 22050
ROOT = Path(__file__).resolve().parent
SOUND_DIR = ROOT / "sounds"

# ---------------------------------------------------------------- 基础工具
def _t(dur: float) -> np.ndarray:
    return np.arange(int(SR * dur)) / SR


def _contour(points, n: int) -> np.ndarray:
    """把 [(位置0~1, 值), ...] 插值成 n 点曲线。"""
    xs = np.array([p[0] for p in points], dtype=float)
    ys = np.array([p[1] for p in points], dtype=float)
    gx = np.linspace(0, 1, n)
    return np.interp(gx, xs, ys)


def _env(n: int, attack: float = 0.02, release: float = 0.25,
         tail: float = 0.0) -> np.ndarray:
    e = np.ones(n)
    a = max(1, int(attack * SR))
    r = max(1, int(release * SR))
    e[:a] = np.linspace(0, 1, a) ** 0.7
    if r < n:
        e[-r:] = np.linspace(1, 0, r) ** 1.6
    if tail:
        k = np.linspace(0, 1, n)
        e *= np.exp(-tail * k)
    return e


def _vowel(f0, formants, dur, harm=16, bright=1.0) -> np.ndarray:
    """共振峰加法合成：用谐波幅度模拟元音。f0 可为数组。"""
    n = int(SR * dur)
    if np.isscalar(f0):
        f0 = np.full(n, float(f0))
    else:
        f0 = _contour(f0, n) if len(f0) == 2 else np.asarray(f0, dtype=float)[:n]
    phase = np.cumsum(2 * np.pi * f0 / SR)
    sig = np.zeros(n)
    for k in range(1, harm + 1):
        fk = k * f0
        amp = np.zeros(n)
        for F, bw, w in formants:
            amp += w * np.exp(-0.5 * ((fk - F) / bw) ** 2)
        sig += amp * np.sin(k * phase) / (k ** 0.75)
    return sig * bright


def _noise(n: int, lp: float = 1.0) -> np.ndarray:
    x = np.random.default_rng(7).normal(0, 1, n)
    if lp < 1.0:                       # 简单一阶低通
        y = np.empty_like(x)
        acc = 0.0
        for i, v in enumerate(x):
            acc += lp * (v - acc)
            y[i] = acc
        return y
    return x


def _fade(x: np.ndarray, ms: float = 6.0) -> np.ndarray:
    k = max(1, int(SR * ms / 1000))
    if len(x) > 2 * k:
        x[:k] *= np.linspace(0, 1, k)
        x[-k:] *= np.linspace(1, 0, k)
    return x


def _norm(x: np.ndarray, peak: float = 0.82) -> np.ndarray:
    m = float(np.max(np.abs(x))) or 1.0
    return x / m * peak


# ---------------------------------------------------------------- 各种音效
A = [(800, 130, 1.0), (1250, 160, 0.55), (2650, 220, 0.22)]
I = [(320, 90, 1.0), (2280, 210, 0.60), (3000, 260, 0.28)]
U = [(360, 90, 1.0), (820, 130, 0.45), (2400, 220, 0.18)]
E = [(520, 110, 1.0), (1850, 180, 0.50), (2550, 220, 0.22)]


def meow_short() -> np.ndarray:
    dur = 0.30
    n = int(SR * dur)
    f0 = _contour([(0, 640), (0.18, 760), (0.55, 600), (1, 470)], n)
    y = _vowel(f0, I, dur) * 0.55 + _vowel(f0 * 0.995, A, dur) * 0.75
    y = y * _env(n, 0.012, 0.16, tail=1.2)
    return _norm(_fade(y))


def meow_cute() -> np.ndarray:
    dur = 0.44
    n = int(SR * dur)
    f0 = _contour([(0, 780), (0.25, 980), (0.6, 900), (1, 620)], n)
    vib = 1 + 0.02 * np.sin(2 * np.pi * 7 * _t(dur))
    y = (_vowel(f0 * vib, I, dur) * 0.6 + _vowel(f0 * vib, A, dur) * 0.55
         + _vowel(f0 * vib, U, dur) * 0.25)
    y = y * _env(n, 0.015, 0.22, tail=1.4)
    return _norm(_fade(y))


def meow_long() -> np.ndarray:
    dur = 0.72
    n = int(SR * dur)
    f0 = _contour([(0, 430), (0.2, 620), (0.45, 700), (0.75, 560), (1, 380)], n)
    vib = 1 + 0.025 * np.sin(2 * np.pi * 5.5 * _t(dur))
    y = (_vowel(f0 * vib, A, dur) * 0.8 + _vowel(f0 * vib, U, dur) * 0.5
         + _vowel(f0 * vib, I, dur) * 0.2)
    y = y * _env(n, 0.03, 0.3, tail=1.0)
    return _norm(_fade(y))


def hajimi_sing() -> np.ndarray:
    """哈-基-米 三个音节，像玩具猫在唱。"""
    parts = []
    for vowel, base, dur, up in ((A, 560, 0.20, 1.10), (I, 640, 0.16, 1.05),
                                 (U, 700, 0.30, 0.92)):
        n = int(SR * dur)
        f0 = np.linspace(base, base * up, n)
        f0 *= 1 + 0.02 * np.sin(2 * np.pi * 8 * np.arange(n) / SR)
        seg = _vowel(f0, vowel, dur) * _env(n, 0.012, 0.10, tail=0.8)
        parts.append(seg)
        gap = np.zeros(int(SR * 0.045))
        parts.append(gap)
    y = np.concatenate(parts)
    y[: int(SR * 0.01)] += _noise(int(SR * 0.01)) * 0.05   # 轻轻的起音
    return _norm(_fade(y, 10))


def purr() -> np.ndarray:
    dur = 1.25
    n = int(SR * dur)
    base = _noise(n, lp=0.08)
    am = 0.5 + 0.5 * np.sin(2 * np.pi * 26 * _t(dur))
    tone = np.sin(2 * np.pi * 78 * _t(dur)) * 0.25
    y = (base * 0.9 + tone) * am
    y *= _env(n, 0.08, 0.35)
    return _norm(_fade(y, 20), 0.5)


def squeak() -> np.ndarray:
    dur = 0.18
    n = int(SR * dur)
    f0 = _contour([(0, 900), (0.35, 1450), (1, 1150)], n)
    y = _vowel(f0, I, dur, harm=10) * _env(n, 0.006, 0.07, tail=2.0)
    y[: int(SR * 0.008)] += _noise(int(SR * 0.008)) * 0.25
    return _norm(_fade(y))


def pop() -> np.ndarray:
    dur = 0.13
    n = int(SR * dur)
    f = _contour([(0, 1100), (0.3, 520), (1, 300)], n)
    y = np.sin(np.cumsum(2 * np.pi * f / SR)) * np.exp(-9 * _t(dur))
    y[: int(SR * 0.006)] += _noise(int(SR * 0.006)) * 0.35
    return _norm(_fade(y, 3))


def boing() -> np.ndarray:
    dur = 0.42
    n = int(SR * dur)
    f = _contour([(0, 180), (0.25, 520), (0.5, 430), (0.75, 520), (1, 380)], n)
    y = np.sin(np.cumsum(2 * np.pi * f / SR)) * np.exp(-3.2 * _t(dur))
    y += 0.3 * np.sin(np.cumsum(4 * np.pi * f / SR)) * np.exp(-4.5 * _t(dur))
    return _norm(_fade(y, 5))


def sparkle() -> np.ndarray:
    notes = [(1046.5, 0.00), (1318.5, 0.09), (1568.0, 0.18), (2093.0, 0.27)]
    dur = 0.62
    n = int(SR * dur)
    y = np.zeros(n)
    for f, t0 in notes:
        i0 = int(t0 * SR)
        seg = np.sin(2 * np.pi * f * _t(0.3)) * np.exp(-7 * _t(0.3))
        seg = seg[: max(0, n - i0)] * 0.5
        y[i0:i0 + len(seg)] += seg
    return _norm(_fade(y, 4))


def sad() -> np.ndarray:
    dur = 0.85
    n = int(SR * dur)
    f0 = _contour([(0, 560), (0.3, 480), (0.65, 400), (1, 250)], n)
    vib = 1 + 0.05 * np.sin(2 * np.pi * 6 * _t(dur))
    y = _vowel(f0 * vib, U, dur) * 0.9 + _vowel(f0 * vib, A, dur) * 0.5
    y *= _env(n, 0.03, 0.4, tail=1.0)
    return _norm(_fade(y))


def angry() -> np.ndarray:
    dur = 0.5
    n = int(SR * dur)
    f0 = _contour([(0, 150), (0.4, 190), (1, 130)], n) * (
        1 + 0.04 * np.sin(2 * np.pi * 22 * _t(dur)))
    phase = np.cumsum(2 * np.pi * f0 / SR)
    y = sum(np.sin(k * phase) / k for k in range(1, 18))
    y = y * 0.6 + _noise(n, lp=0.15) * 0.55
    y *= _env(n, 0.02, 0.25, tail=0.6)
    return _norm(_fade(y))


def giggle() -> np.ndarray:
    dur = 0.66
    n = int(SR * dur)
    y = np.zeros(n)
    for i, t0 in enumerate((0.0, 0.16, 0.32, 0.46)):
        d = 0.11 - i * 0.008
        m = int(SR * d)
        f0 = np.linspace(520 - i * 30, 430 - i * 30, m)
        seg = _vowel(f0, E, d, harm=10)
        seg = seg * np.exp(-8 * np.arange(m) / SR) * (0.9 - 0.12 * i)
        i0 = int(t0 * SR)
        y[i0:i0 + m] += seg[: max(0, n - i0)]
    return _norm(_fade(y, 5))


SOUNDS = {
    "meow_short": meow_short,
    "meow_cute": meow_cute,
    "meow_long": meow_long,
    "hajimi_sing": hajimi_sing,
    "purr": purr,
    "squeak": squeak,
    "pop": pop,
    "boing": boing,
    "sparkle": sparkle,
    "sad": sad,
    "angry": angry,
    "giggle": giggle,
}


def write_wav(path: Path, samples: np.ndarray):
    data = np.clip(samples, -1, 1)
    pcm = (data * 32767).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def build_all(folder: Path = SOUND_DIR, force: bool = False) -> dict[str, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    made = {}
    for name, fn in SOUNDS.items():
        path = folder / f"{name}.wav"
        if force or not path.exists():
            write_wav(path, fn())
        made[name] = path
    return made


# ---------------------------------------------------------------- 播放
class SoundBank:
    """异步播放（winsound），任一时刻只播一个；静音时直接忽略。

    除了代码合成的音效，还会自动收录 sounds/ 下从网上抓来的 hajimi_NN.wav
    （真实哈基米/曼波片段），优先用于切换时播放。
    """

    def __init__(self, folder: Path = SOUND_DIR, muted: bool = False):
        self.folder = Path(folder)
        self.muted = muted
        self.last: str | None = None
        try:
            self.files = build_all(self.folder)
        except Exception:
            self.files = {}
        # 网上抓的真实片段
        self.clips: list[str] = []
        try:
            for p in sorted(self.folder.glob("hajimi_[0-9][0-9].wav")):
                self.files[p.stem] = p
                self.clips.append(p.stem)
        except Exception:
            pass
        # HajimiPad 音效板第一板块的短音效（点击时优先播这些）
        self.pads: list[str] = []
        try:
            for p in sorted(self.folder.glob("pad_[0-9][0-9].wav")):
                self.files[p.stem] = p
                self.pads.append(p.stem)
        except Exception:
            pass
        self._winsound = None
        try:
            import winsound  # noqa: F401  (仅 Windows)
            self._winsound = winsound
        except Exception:
            self._winsound = None

    @property
    def available(self) -> bool:
        return bool(self.files) and self._winsound is not None

    def play(self, name: str) -> str | None:
        if self.muted or not self.available:
            return None
        path = self.files.get(name)
        if not path or not path.exists():
            return None
        try:
            self._winsound.PlaySound(
                str(path),
                self._winsound.SND_FILENAME | self._winsound.SND_ASYNC
                | self._winsound.SND_NODEFAULT)
        except Exception:
            return None
        self.last = name
        return name


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成/试听哈基米音效")
    ap.add_argument("--render", default=str(SOUND_DIR), help="输出目录")
    ap.add_argument("--force", action="store_true", help="强制重建")
    ap.add_argument("--play", default=None, help="生成后播放某个音效")
    ap.add_argument("--list", action="store_true", help="列出所有音效")
    args = ap.parse_args(argv)

    files = build_all(Path(args.render), force=args.force)
    if args.list or not args.play:
        for name, p in files.items():
            print(f"{name:12s} {p.stat().st_size / 1024:6.1f} KB  {p.name}")
    if args.play:
        bank = SoundBank(Path(args.render))
        import time
        print("playing:", bank.play(args.play))
        time.sleep(1.2)


if __name__ == "__main__":
    main()

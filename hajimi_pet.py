# -*- coding: utf-8 -*-
"""哈基米桌宠 · 主程序

- 无边框、背景透明、始终置顶
- 单击小猫咪：自动切换到下一个表情（带弹跳 + 对话气泡）
- 按住拖动：挪动位置；滚轮：缩放；右键：菜单
- 全程不需要任何图片素材，形象由代码绘制

用法：
    pythonw hajimi_pet.py
    python  hajimi_pet.py --scale 1.1 --expr 2 --log run.log
"""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox

from hajimi_art import DESIGN, EXPRESSIONS, STORE, HajimiArt
from hajimi_memes import MemePack
from hajimi_sound import SoundBank

# 手绘表情 -> 音效
EXPR_SOUND = {
    "normal": "meow_short", "happy": "giggle", "huh": "squeak",
    "angry": "angry", "cry": "sad", "love": "hajimi_sing",
    "shock": "pop", "sleepy": "purr", "smug": "sparkle",
}
# 梗图模式轮流用的音效
MEME_SOUNDS = ["meow_short", "meow_cute", "hajimi_sing", "pop", "boing",
               "meow_long", "sparkle", "squeak"]

KEY = (255, 0, 255)
KEY_ARR = np.array(KEY, dtype=np.uint8)
KEY_HEX = "#ff00ff"
STATE_FILE = Path(os.environ.get("APPDATA", str(Path.home()))) / "hajimi-pet.json"


class PetApp:
    BASE_W = 400          # 窗口基准宽
    BASE_ART = 340        # 猫咪绘制盒基准尺寸
    BUBBLE_H = 112        # 气泡区高度
    FPS_MS = 40           # 25 fps

    def __init__(self, root: tk.Tk, art: HajimiArt, args):
        self.root = root
        self.art = art
        self.args = args
        self.log_path = Path(args.log) if args.log else None

        self.pack = MemePack(getattr(args, "memes", None))
        self.sound = SoundBank(muted=bool(getattr(args, "mute", False)))
        self.sound_var = tk.BooleanVar(value=not self.sound.muted)
        want = getattr(args, "mode", None)
        if want in ("draw", "meme"):
            self.mode = want if (want == "draw" or self.pack.ready) else "draw"
        else:
            self.mode = "meme" if self.pack.ready else "draw"
        self.mode_var = tk.BooleanVar(value=(self.mode == "meme"))

        self.expr = int(args.expr) % self.total()
        self.scale = float(args.scale)
        self.bubble_until = 0.0
        self.bubble_img = None
        self._resize_cache: dict[tuple, Image.Image] = {}
        self._bubble_cache: dict[tuple, Image.Image] = {}
        self._photo = None

        self.blink = False
        self.next_blink = time.time() + random.uniform(1.5, 3.5)
        self.blink_until = 0.0
        self.hop_t0 = 0.0
        self.hop = 0.0
        self.sq = 1.0
        self.br = 1.0
        self._sig = None
        self.auto = bool(args.auto)
        self.auto_var = tk.BooleanVar(value=self.auto)
        self.next_auto = time.time() + 12.0

        self.w = int(self.BASE_W * self.scale)
        self.h = int((self.BASE_ART + self.BUBBLE_H) * self.scale)
        self.art_px = int(self.BASE_ART * self.scale)
        self.t0 = time.time()

        self._build_window()
        self._load_state()
        self._apply_geometry()
        self._make_bubble()
        self._bind()
        self.root.update_idletasks()
        meta = self._meta(self.expr)
        self._log(event="start", expr=self.expr, key=meta[0], mode=self.mode,
                  x=self.root.winfo_x(), y=self.root.winfo_y(), w=self.w, h=self.h,
                  scale=round(self.scale, 3), items=self.total())
        self.root.after(60, self._tick)
        self.root.after(1100, self._play_sound)      # 出场先喵一声

    # ------------------------------------------------------------ 模式
    def total(self) -> int:
        return len(self.pack) if (self.mode == "meme" and self.pack.ready) else len(EXPRESSIONS)

    def _meta(self, idx: int):
        """返回 (key, label, 气泡文案)；文案为 None 表示不显示气泡。"""
        if self.mode == "meme" and self.pack.ready:
            idx %= len(self.pack)
            return f"meme_{idx + 1:02d}", self.pack.name(idx), self.pack.caption(idx)
        spec = EXPRESSIONS[idx % len(EXPRESSIONS)]
        return spec["key"], spec["label"], spec["bubble"]

    def set_mode(self, mode: str):
        if mode == self.mode or (mode == "meme" and not self.pack.ready):
            return
        self.mode = mode
        self.mode_var.set(mode == "meme")
        self.expr = 0
        self.bubble_until = 0.0
        self._resize_cache.clear()
        self._sig = None
        self._make_bubble()
        self._log(event="mode", mode=mode, items=self.total())

    def _on_mode_toggle(self):
        self.set_mode("meme" if self.mode_var.get() else "draw")

    # ------------------------------------------------------------ 窗口
    def _build_window(self):
        r = self.root
        r.overrideredirect(True)
        r.config(bg=KEY_HEX, highlightthickness=0, bd=0)
        try:
            r.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            r.attributes("-transparentcolor", KEY_HEX)
        except tk.TclError:
            pass
        self.label = tk.Label(r, bd=0, bg=KEY_HEX, highlightthickness=0)
        self.label.pack(fill="both", expand=True)

    def _apply_geometry(self):
        x = self.pos[0] if self.pos else self._default_pos()[0]
        y = self.pos[1] if self.pos else self._default_pos()[1]
        self.root.geometry(f"{self.w}x{self.h}+{int(x)}+{int(y)}")

    def _default_pos(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        return sw - self.w - 70, sh - self.h - 90

    # ------------------------------------------------------------ 状态持久化
    def _load_state(self):
        self.pos = None
        try:
            data = json.loads(STATE_FILE.read_text("utf-8"))
            if not self.args.pos:
                self.pos = (int(data["x"]), int(data["y"]))
            if self.args.scale == 1.0 and "scale" in data:
                self.scale = min(1.6, max(0.6, float(data["scale"])))
                self.w = int(self.BASE_W * self.scale)
                self.h = int((self.BASE_ART + self.BUBBLE_H) * self.scale)
                self.art_px = int(self.BASE_ART * self.scale)
            if not getattr(self.args, "mute", False) and "muted" in data:
                self.sound.muted = bool(data["muted"])
                self.sound_var.set(not self.sound.muted)
        except (OSError, ValueError, KeyError):
            pass
        if self.args.pos:
            try:
                px, py = self.args.pos.split(",")
                self.pos = (int(px), int(py))
            except ValueError:
                self.pos = None

    def _save_state(self):
        try:
            x, y = self.root.winfo_x(), self.root.winfo_y()
            STATE_FILE.write_text(json.dumps(
                {"x": x, "y": y, "scale": round(self.scale, 3),
                 "muted": bool(self.sound.muted)}, ensure_ascii=False),
                encoding="utf-8")
        except OSError:
            pass

    # ------------------------------------------------------------ 事件
    def _bind(self):
        # 统一绑在顶层窗口上：Tk 的 bindtags 已包含顶层，子控件上的点击也会冒泡到这里，
        # 这样真实鼠标点击和窗口消息投递都能命中，且只触发一次。
        r = self.root
        r.bind("<ButtonPress-1>", self._on_press)
        r.bind("<B1-Motion>", self._on_drag)
        r.bind("<ButtonRelease-1>", self._on_release)
        r.bind("<Button-3>", self._on_menu)
        r.bind("<Button-2>", lambda e: self.advance(randomize=True))
        r.bind("<MouseWheel>", self._on_wheel)

    def _on_press(self, e):
        self._drag_from = (e.x_root, e.y_root)
        self._win_from = (self.root.winfo_x(), self.root.winfo_y())
        self._moved = 0
        self._press_t = time.time()

    def _on_drag(self, e):
        dx = e.x_root - self._drag_from[0]
        dy = e.y_root - self._drag_from[1]
        self._moved = max(self._moved, abs(dx) + abs(dy))
        if self._moved > 4:
            self.root.geometry(f"+{self._win_from[0] + dx}+{self._win_from[1] + dy}")

    def _on_release(self, e):
        if self._moved <= 4 and time.time() - self._press_t < 0.8:
            self.advance()

    def _on_wheel(self, e):
        self.rescale(1.06 if e.delta > 0 else 1 / 1.06)

    def _on_menu(self, e):
        m = tk.Menu(self.root, tearoff=0, font=("Microsoft YaHei UI", 9))
        m.add_command(label="下一个", command=self.advance)
        m.add_command(label="随机一个", command=lambda: self.advance(randomize=True))
        m.add_separator()
        if self.pack.ready:
            m.add_checkbutton(label=f"用梗图（{len(self.pack)} 张，关掉=手绘猫）",
                              variable=self.mode_var, command=self._on_mode_toggle)
        n_sound = len(self.sound.clips)
        m.add_checkbutton(label=f"音效（{n_sound} 段哈基米原声）" if n_sound else "音效",
                          variable=self.sound_var, command=self._on_sound_toggle)
        m.add_checkbutton(label="自动切换（每 12 秒）", variable=self.auto_var,
                          command=self._on_auto_toggle)
        m.add_separator()
        m.add_command(label="放大", command=lambda: self.rescale(1.08))
        m.add_command(label="缩小", command=lambda: self.rescale(1 / 1.08))
        m.add_command(label="恢复大小", command=lambda: self.rescale(1.0 / self.scale))
        m.add_separator()
        m.add_command(label="关于哈基米", command=self._about)
        m.add_command(label="退出", command=self.quit)
        m.tk_popup(e.x_root, e.y_root)

    def _about(self):
        mode = (f"梗图模式，{len(self.pack)} 张图（memes/ 目录）"
                if self.mode == "meme" else f"手绘模式，{len(EXPRESSIONS)} 个表情")
        messagebox.showinfo(
            "哈基米桌宠",
            "哈基米哈基米～\n\n"
            "单击：换一个\n拖动：挪位置\n滚轮：放大缩小\n右键：菜单\n\n"
            f"当前：{mode}")

    def _on_auto_toggle(self):
        self.auto = bool(self.auto_var.get())
        self.next_auto = time.time() + 12.0

    # ------------------------------------------------------------ 行为
    def advance(self, step: int = 1, randomize: bool = False):
        n = self.total()
        if randomize:
            pool = [i for i in range(n) if i != self.expr]
            idx = random.choice(pool) if pool else self.expr
        else:
            idx = (self.expr + step) % n
        self.set_expression(idx)

    def set_expression(self, idx: int):
        self.expr = idx % self.total()
        self.hop_t0 = time.time()
        self.blink = False
        self._make_bubble()
        self.bubble_until = time.time() + 2.4 if self.bubble_img is not None else 0.0
        key, label, _ = self._meta(self.expr)
        self._log(event="switch", expr=self.expr, key=key, label=label, mode=self.mode,
                  t=round(time.time() - self.t0, 3))
        self._play_sound()

    # ------------------------------------------------------------ 音效
    def _sound_for(self, idx: int) -> str:
        """优先用音效板第一板块的短音效，其次酷我抓的长片段，最后合成音效。"""
        pads = self.sound.pads
        clips = self.sound.clips
        if self.mode == "meme":
            if pads:
                return pads[idx % len(pads)]
            if clips:
                return clips[idx % len(clips)]
            return MEME_SOUNDS[idx % len(MEME_SOUNDS)]
        key = self._meta(idx)[0]
        if key in ("love", "happy", "smug"):
            if pads:
                return pads[("love", "happy", "smug").index(key) % len(pads)]
            if clips:
                return clips[("love", "happy", "smug").index(key) % len(clips)]
        return EXPR_SOUND.get(key, "meow_short")

    def _play_sound(self) -> str | None:
        name = self.sound.play(self._sound_for(self.expr))
        if name:
            self._log(event="sound", name=name)
        return name

    def _on_sound_toggle(self):
        self.sound.muted = not bool(self.sound_var.get())
        self._save_state()
        if not self.sound.muted:
            self._play_sound()

    def rescale(self, factor: float):
        new = min(1.6, max(0.6, self.scale * factor))
        if abs(new - self.scale) < 1e-3:
            return
        old_center = (self.root.winfo_x() + self.w / 2, self.root.winfo_y() + self.h)
        self.scale = new
        self.w = int(self.BASE_W * self.scale)
        self.h = int((self.BASE_ART + self.BUBBLE_H) * self.scale)
        self.art_px = int(self.BASE_ART * self.scale)
        self._resize_cache.clear()
        self._bubble_cache.clear()
        self._make_bubble()
        x = int(old_center[0] - self.w / 2)
        y = int(old_center[1] - self.h)
        self.root.geometry(f"{self.w}x{self.h}+{x}+{y}")

    def quit(self):
        self._log(event="quit", expr=self.expr)
        if not self.args.selftest:
            self._save_state()
        self.root.destroy()

    # ------------------------------------------------------------ 绘制
    def _make_bubble(self):
        text = self._meta(self.expr)[2]
        if not text:
            self.bubble_img = None
            return
        img = self.art.bubble(text)
        if self.scale != 1.0:
            w = max(1, int(img.width * self.scale))
            h = max(1, int(img.height * self.scale))
            img = img.resize((w, h), Image.LANCZOS)
        self.bubble_img = img

    def _scaled_cat(self, cw: int, ch: int) -> Image.Image:
        key = (self.mode, self.expr, self.blink, cw, ch)
        img = self._resize_cache.get(key)
        if img is None:
            if self.mode == "meme":
                base = self.pack.render(self.expr, max(cw, ch))
                if base is None:
                    base = Image.new("RGBA", (max(cw, ch), max(cw, ch)), (0, 0, 0, 0))
                img = base.resize((cw, ch), Image.LANCZOS)
            else:
                img = self.art.render(self.expr, self.blink).resize((cw, ch), Image.LANCZOS)
            if len(self._resize_cache) > 24:
                self._resize_cache.clear()
            self._resize_cache[key] = img
        return img

    def _layout(self):
        """当前这一帧的摆放参数（尺寸量化到 2px，便于复用缩放结果）。"""
        if self.mode == "meme":
            side = max(2, int(round(self.art_px * self.sq / 2)) * 2)
            cw = ch = side
            x = (self.w - cw) // 2
            y = (self.h - ch) // 2 + int(round(self.hop))
        else:
            cw = max(2, int(round(self.art_px * self.br * self.sq / 2)) * 2)
            ch = max(2, int(round(self.art_px * (2 - self.br) * self.sq / 2)) * 2)
            x = (self.w - cw) // 2
            y = self.h - ch + int(round(self.hop))
        bubble_on = self.bubble_img is not None and time.time() < self.bubble_until
        return cw, ch, x, y, bubble_on

    def _compose(self, layout=None) -> Image.Image:
        cw, ch, x, y, bubble_on = layout or self._layout()
        frame = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        cat = self._scaled_cat(cw, ch)
        frame.alpha_composite(cat, (x, y))

        if bubble_on:
            b = self.bubble_img
            bx = (self.w - b.width) // 2
            if self.mode == "meme":
                by = y - b.height + 12
            else:
                by = self.h - self.art_px - int(self.art_px * 0.02) - b.height + 6
            frame.alpha_composite(b, (bx, max(0, by)))
        return frame

    def _to_photo(self, frame: Image.Image):
        arr = np.asarray(frame)
        alpha = arr[:, :, 3][:, :, None]
        rgb = np.where(alpha < 128, KEY_ARR, arr[:, :, :3])
        return ImageTk.PhotoImage(Image.fromarray(rgb.astype(np.uint8), "RGB"))

    # ------------------------------------------------------------ 主循环
    def _tick(self):
        now = time.time()
        t = now - self.t0

        if self.mode == "draw" and now >= self.next_blink:
            self.blink = True
            self.blink_until = now + 0.12
            self.next_blink = now + random.uniform(2.0, 5.5)
        elif self.blink and now > self.blink_until:
            self.blink = False

        # 呼吸
        ph = math.sin(t * 2.0)
        self.br = 1.0 + 0.010 * ph
        self.hop = 2.0 * math.sin(t * 1.3)

        # 点击弹跳
        if self.hop_t0:
            dt = now - self.hop_t0
            if dt < 0.42:
                k = dt / 0.42
                pulse = math.sin(math.pi * k)
                self.sq = 1.0 + 0.09 * pulse
                self.hop -= 14 * pulse
            else:
                self.hop_t0 = 0.0
                self.sq = 1.0

        # 自动切换
        if self.auto and now >= self.next_auto:
            self.next_auto = now + 12.0
            self.advance(randomize=True)

        try:
            layout = self._layout()
            sig = (self.mode, self.expr, self.blink) + layout
            if sig != self._sig:
                self._sig = sig
                photo = self._to_photo(self._compose(layout))
                self.label.configure(image=photo)
                self._photo = photo
        except Exception as exc:                      # 出错也不让循环停掉
            self._log(event="error", error=repr(exc))

        # 隔一会儿把窗口重新提到最顶层，防止被其他置顶窗口（音量面板之类）盖住
        self._ticks = getattr(self, "_ticks", 0) + 1
        if self._ticks % 40 == 0:
            self._raise_topmost()

        self.root.after(self.FPS_MS, self._tick)

    def _raise_topmost(self):
        try:
            hwnd = int(self.root.winfo_id())
            user32 = ctypes.windll.user32
            user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0,   # HWND_TOPMOST
                                0x0001 | 0x0002 | 0x0010)  # NOSIZE|NOMOVE|NOACTIVATE
        except Exception:
            pass

    # ------------------------------------------------------------ 日志（便于自动化验证）
    def _log(self, **kw):
        if not self.log_path:
            return
        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": round(time.time(), 3), **kw},
                                   ensure_ascii=False) + "\n")
        except OSError:
            pass


# ---------------------------------------------------------------- 预览素材
def _bg(size):
    """浅色渐变桌面背景，方便预览。"""
    W, H = size
    top, bottom = (238, 242, 247), (214, 222, 232)
    col = np.zeros((H, 1, 3), dtype=np.uint8)
    for y in range(H):
        k = y / max(1, H - 1)
        col[y, 0] = [int(top[i] + (bottom[i] - top[i]) * k) for i in range(3)]
    arr = np.repeat(col, W, axis=1)
    return Image.fromarray(arr, "RGB").convert("RGBA")


def _preview_frame(art: HajimiArt, expr: int, scale: float = 1.0, pulse: float = 0.0):
    W, H = int(400 * scale), int(452 * scale)
    art_px = int(340 * scale)
    frame = _bg((W, H))
    sq = 1.0 + 0.09 * pulse
    cw = ch = int(art_px * sq)
    cat = art.render(expr, scale=DESIGN).resize((cw, ch), Image.LANCZOS)
    frame.alpha_composite(cat, ((W - cw) // 2, H - ch - int(9 * pulse)))
    b = art.bubble(EXPRESSIONS[expr]["bubble"])
    if scale != 1.0:
        b = b.resize((int(b.width * scale), int(b.height * scale)), Image.LANCZOS)
    frame.alpha_composite(b, ((W - b.width) // 2,
                              H - art_px - int(art_px * 0.02) - b.height + 6))
    return frame


def _preview_meme_frame(pack, idx: int, scale: float = 1.0, pulse: float = 0.0):
    W, H = int(400 * scale), int(452 * scale)
    art_px = int(340 * scale)
    frame = _bg((W, H))
    side = int(art_px * (1.0 + 0.09 * pulse))
    sticker = pack.render(idx, max(2, side))
    if sticker is None:
        return frame
    sticker = sticker.resize((side, side), Image.LANCZOS)
    frame.alpha_composite(sticker, ((W - side) // 2, (H - side) // 2 - int(9 * pulse)))
    return frame


def make_preview(art: HajimiArt, out: Path, pack=None):
    """生成表情九宫格 + 窗口效果图 + 点击切换演示 GIF（有梗图则一并生成）。"""
    out.mkdir(parents=True, exist_ok=True)

    sheet = Image.new("RGBA", (DESIGN * 3, DESIGN * 3), (250, 246, 238, 255))
    for i in range(len(EXPRESSIONS)):
        sheet.alpha_composite(art.render(i, scale=DESIGN),
                              ((i % 3) * DESIGN, (i // 3) * DESIGN))
    sheet.convert("RGB").save(out / "expr_sheet.png")

    _preview_frame(art, 0, scale=2.0).convert("RGB").save(out / "window_2x.png")

    frames = []
    for i in range(len(EXPRESSIONS)):
        for step in range(12):
            pulse = math.sin(math.pi * (step / 5.0)) if step <= 5 else 0.0
            frames.append(_preview_frame(art, i, 1.0, pulse).convert("RGB"))
        frames.extend([frames[-1]] * 4)
    frames.extend([frames[-1]] * 6)

    pal = [f.quantize(colors=96, method=Image.FASTOCTREE) for f in frames]
    pal[0].save(out / "hajimi_click_demo.gif", save_all=True, append_images=pal[1:],
                duration=80, loop=0, optimize=True, disposal=2)

    saved = [out / "expr_sheet.png", out / "hajimi_click_demo.gif",
             out / "window_2x.png"]

    if pack is not None and pack.ready:
        cs = pack.contact_sheet(cell=200, cols=6)
        if cs is not None:
            cs.save(out / "meme_sheet.png")
            saved.append(out / "meme_sheet.png")
        front = _preview_meme_frame(pack, 0, scale=2.0).convert("RGB")
        front.save(out / "window_meme_2x.png")
        saved.append(out / "window_meme_2x.png")

        mframes = []
        for i in range(len(pack)):
            for step in range(8):
                pulse = math.sin(math.pi * (step / 3.0)) if step <= 3 else 0.0
                mframes.append(_preview_meme_frame(pack, i, 0.62, pulse).convert("RGB"))
            mframes.extend([mframes[-1]] * 3)
        mframes.extend([mframes[-1]] * 6)
        mpal = [f.quantize(colors=64, method=Image.FASTOCTREE) for f in mframes]
        mpal[0].save(out / "meme_click_demo.gif", save_all=True, append_images=mpal[1:],
                     duration=90, loop=0, optimize=True, disposal=2)
        saved.append(out / "meme_click_demo.gif")

    return saved


# ---------------------------------------------------------------- 自测
def run_selftest(app: "PetApp", out: Path, hold: float = 12.0):
    """在真实窗口里用真实 Tk 事件跑一遍交互，并把结果写进 report.json。"""
    out.mkdir(parents=True, exist_ok=True)
    frames = out / "frames"
    frames.mkdir(exist_ok=True)
    report = {"checks": [], "frames": [], "ok": False}

    def check(name, ok, detail=""):
        report["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
        print(("PASS  " if ok else "FAIL  ") + name + ("   " + detail if detail else ""))

    def save_frame(tag):
        frame = app._compose()
        p = frames / f"{tag}.png"
        frame.save(p)
        report["frames"].append(p.name)

    def click():
        app.root.event_generate("<ButtonPress-1>", x=200, y=300, rootx=320, rooty=445)
        app.root.event_generate("<ButtonRelease-1>", x=200, y=300, rootx=320, rooty=445)
        app.root.update()

    n = app.total()
    steps = []

    def step():
        i = len(steps)
        if i == 0:
            save_frame("00_initial")
        elif i <= 3:
            before = app.expr
            click()
            want = (before + 1) % n
            check(f"click{i}: 切到下一个", app.expr == want,
                  f"{before}({app._meta(before)[0]}) -> {app.expr}({app._meta(app.expr)[0]})")
            save_frame(f"{i:02d}_after_click{ i }")
        elif i == 4:
            check("click: 气泡已显示", app.bubble_until > time.time() or app.bubble_img is None,
                  f"剩余 {max(0.0, app.bubble_until - time.time()):.2f}s")
            before = app.expr
            x0 = app.root.winfo_x()
            app.root.event_generate("<ButtonPress-1>", x=200, y=300, rootx=320, rooty=445)
            app.root.event_generate("<B1-Motion>", x=240, y=300, rootx=380, rooty=445)
            app.root.event_generate("<ButtonRelease-1>", x=240, y=300, rootx=380, rooty=445)
            app.root.update()
            moved = app.root.winfo_x() - x0
            check("drag: 拖动窗口而不换表情", app.expr == before and abs(moved - 60) <= 2,
                  f"expr={app.expr} 位移={moved}px")
            save_frame("04_after_drag")
        elif i == 5:
            s0 = app.scale
            app.root.event_generate("<MouseWheel>", x=200, y=300, delta=120)
            app.root.update()
            check("wheel: 滚轮缩放", app.scale > s0, f"{s0:.3f} -> {app.scale:.3f}")
            save_frame("05_after_wheel")
        elif i == 6:
            # 循环一整圈（n 次点击）应回到起点
            start = app.expr
            for _ in range(n):
                click()
            check("cycle: 点满一圈回到起点", app.expr == start,
                  f"{start} -> {app.expr}")
            check("bubble: 每次切换都刷新气泡",
                  app.bubble_until > time.time() or app.bubble_img is None)
            save_frame("06_after_cycle")
        elif i == 7:
            img = app._to_photo(app._compose())
            check("render: 能生成 Tk 图像", img is not None, f"{img.width()}x{img.height()}")

            # 音效：切换时真的触发了播放
            n_sound = len(app.sound.files)
            check("sound: 音效文件就绪", n_sound > 0,
                  f"{n_sound} 个（其中哈基米原声 {len(app.sound.clips)} 段）")
            before_sound = app.sound.last
            click()
            check("sound: 点击切换触发了音效", app.sound.last is not None,
                  f"{before_sound} -> {app.sound.last}")
            app.sound.muted = True
            app.sound.last = None
            click()
            check("sound: 静音时不播放", app.sound.last is None)
            app.sound.muted = False

            report["ok"] = all(c["ok"] for c in report["checks"])
            (out / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print("\nSELFTEST " + ("PASS" if report["ok"] else "FAIL"))
            if hold <= 0:
                app.quit()
        steps.append(i)
        if len(steps) < 8:
            app.root.after(900, step)
        else:
            # 停留阶段继续自动换表情，方便外部截图比对
            def demo():
                app.advance()
                app.root.after(1200, demo)

            app.root.after(500, demo)
            app.root.after(int(max(hold, 0.5) * 1000), app.quit)

    app.root.after(400, step)


# ---------------------------------------------------------------- 入口
def main(argv=None):
    parser = argparse.ArgumentParser(description="哈基米表情包桌宠")
    parser.add_argument("--scale", type=float, default=1.0, help="初始缩放（0.6-1.6）")
    parser.add_argument("--expr", type=int, default=0, help="初始表情序号")
    parser.add_argument("--pos", type=str, default=None, help="窗口位置，如 1200,700")
    parser.add_argument("--log", type=str, default=None, help="记录运行日志（JSONL）")
    parser.add_argument("--auto", action="store_true", help="启动时开启自动换表情")
    parser.add_argument("--exit-after", type=float, default=0.0, help="若干秒后自动退出（调试用）")
    parser.add_argument("--preview", type=str, default=None, help="只生成预览图/GIF 后退出")
    parser.add_argument("--selftest", type=str, default=None, help="自测：跑一遍点击/拖拽/缩放并输出报告")
    parser.add_argument("--hold", type=float, default=12.0, help="自测完成后停留秒数（便于外部截图）")
    parser.add_argument("--memes", default=str(Path(__file__).with_name("memes")),
                        help="梗图目录（默认 memes/）")
    parser.add_argument("--mode", choices=["draw", "meme"], default=None,
                        help="draw=手绘猫；meme=梗图（默认有梗图就用梗图）")
    parser.add_argument("--mute", action="store_true", help="启动时静音")
    args = parser.parse_args(argv)

    art = HajimiArt()
    if args.preview:
        saved = make_preview(art, Path(args.preview), MemePack(args.memes))
        for p in saved:
            print("saved:", p)
        return 0

    try:  # 让图片按物理像素 1:1 显示，避免系统缩放导致发虚
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    app = PetApp(root, art, args)
    if args.selftest:
        run_selftest(app, Path(args.selftest), args.hold)
    if args.exit_after:
        root.after(int(args.exit_after * 1000), app.quit)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

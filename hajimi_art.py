# -*- coding: utf-8 -*-
"""哈基米桌宠 · 形象绘制模块

全部形象由代码实时绘制（Pillow），不依赖任何外部图片素材。
设计坐标：0.0 - 1.0 的正方形画布，绘制时 4 倍超采样，输出 2 倍图。
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

# ---------------------------------------------------------------- 尺寸常量
DESIGN = 340          # 1 倍显示尺寸
STORE = DESIGN * 2    # 存储尺寸（2x）
CANVAS = DESIGN * 4   # 绘制画布（4x 超采样）
OW = int(CANVAS * 0.010)   # 主描边宽度
OW2 = int(CANVAS * 0.007)  # 次描边宽度

# ---------------------------------------------------------------- 配色
CREAM = (255, 247, 232, 255)
CREAM_LIGHT = (255, 252, 244, 255)
CREAM_DARK = (243, 224, 196, 255)
ORANGE = (246, 176, 106, 255)
ORANGE_D = (231, 147, 76, 255)
PINK = (247, 190, 192, 255)
NOSE_PINK = (240, 140, 152, 255)
BLUSH = (255, 203, 194, 255)
INK = (72, 44, 30, 255)
MOUTH = (94, 51, 40, 255)
TONGUE = (247, 141, 156, 255)
WHISKER = (205, 168, 132, 255)
WHITE = (255, 255, 255, 255)
TEAR = (129, 199, 241, 255)
HEART = (255, 126, 148, 255)
SPARK = (255, 219, 120, 255)
BUBBLE_BG = (255, 253, 247, 255)
BUBBLE_INK = (86, 55, 38, 255)

FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")
FONT_NORMAL = Path(r"C:\Windows\Fonts\msyh.ttc")


# ---------------------------------------------------------------- 表情表
EXPRESSIONS = [
    dict(key="normal", label="日常", bubble="哈基米～", eyes="round", mouth="w",
         blush=True, extras=(), tilt=0.0),
    dict(key="happy", label="开心", bubble="嘿嘿嘿～", eyes="happy", mouth="grin",
         blush=True, extras=("sparkle",), tilt=-2.0),
    dict(key="huh", label="疑惑", bubble="哈？", eyes="round_small", mouth="open",
         blush=False, extras=("question",), tilt=-5.0),
    dict(key="angry", label="生气", bubble="哼！哈基米！", eyes="angry", mouth="fangs",
         blush=True, extras=("anger",), tilt=0.0),
    dict(key="cry", label="哭哭", bubble="呜哇啊啊…", eyes="cry", mouth="wavy",
         blush=True, extras=("tears",), tilt=2.0),
    dict(key="love", label="心动", bubble="最喜欢你啦", eyes="heart", mouth="grin",
         blush=True, extras=("hearts",), tilt=0.0),
    dict(key="shock", label="震惊", bubble="哈？！！", eyes="shock", mouth="open_big",
         blush=False, extras=("sweat", "sparkle"), tilt=0.0),
    dict(key="sleepy", label="困困", bubble="哈基米…Zzz", eyes="sleepy", mouth="small",
         blush=False, extras=("zzz",), tilt=3.0),
    dict(key="smug", label="得意", bubble="哈～基～米～", eyes="smug", mouth="smirk",
         blush=True, extras=("note",), tilt=4.0),
]


# ---------------------------------------------------------------- 小工具
def _bezier(p0, p1, p2, n=48):
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        out.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return out


def _blob(cx, cy, rx, ry, phase=0.0, wobble=0.10, n=64):
    """有机形状的圆斑（用于橘色花斑）。"""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        k = 1.0 + wobble * math.sin(3 * a + phase) + 0.05 * math.sin(5 * a + phase * 2)
        pts.append((cx + math.cos(a) * rx * k, cy + math.sin(a) * ry * k))
    return pts


def _star(cx, cy, r, ratio=0.34, n=4, rot=-math.pi / 2):
    pts = []
    for i in range(n * 2):
        a = rot + math.pi * i / n
        rr = r if i % 2 == 0 else r * ratio
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    return pts


def _heart_pts(cx, cy, s, n=80):
    pts = []
    for i in range(n):
        th = 2 * math.pi * i / n
        x = 16 * math.sin(th) ** 3
        y = -(13 * math.cos(th) - 5 * math.cos(2 * th)
              - 2 * math.cos(3 * th) - math.cos(4 * th))
        pts.append((cx + x * s / 16.0, cy + y * s / 16.0))
    return pts


def _drop(cx, cy, s, rot=0.0):
    """水滴 / 泪珠。"""
    pts = [(0.0, -1.0), (0.55, -0.15), (0.62, 0.35), (0.30, 0.86),
           (0.0, 1.0), (-0.30, 0.86), (-0.62, 0.35), (-0.55, -0.15)]
    ca, sa = math.cos(rot), math.sin(rot)
    return [(cx + (x * ca - y * sa) * s, cy + (x * sa + y * ca) * s) for x, y in pts]


# ---------------------------------------------------------------- 轮廓曲线
_PROFILE = [
    (0.045, 0.004), (0.055, 0.045), (0.070, 0.100), (0.090, 0.150),
    (0.115, 0.196), (0.150, 0.238), (0.190, 0.272), (0.240, 0.300),
    (0.300, 0.320), (0.360, 0.330), (0.420, 0.328), (0.470, 0.316),
    (0.510, 0.298), (0.550, 0.304), (0.600, 0.340), (0.660, 0.372),
    (0.730, 0.394), (0.800, 0.404), (0.860, 0.404), (0.905, 0.392),
    (0.940, 0.360), (0.965, 0.310), (0.982, 0.230), (0.993, 0.120),
    (0.998, 0.030),
]


def _smoothed_profile(n=420):
    vs = np.array([p[0] for p in _PROFILE])
    ws = np.array([p[1] for p in _PROFILE])
    t = np.linspace(vs[0], vs[-1], n)
    w = np.interp(t, vs, ws)
    k = np.exp(-0.5 * (np.arange(-14, 15) / 5.5) ** 2)
    k /= k.sum()
    w = np.convolve(np.pad(w, (14, 14), mode="edge"), k, mode="valid")
    return t, np.clip(w, 0.0, None)


class HajimiArt:
    """负责把某个表情画成图片，并缓存。"""

    def __init__(self):
        self._fonts: dict[tuple[int, bool], ImageFont.FreeTypeFont] = {}
        self._cache: dict[tuple[int, bool], Image.Image] = {}
        self._bubble_cache: dict[str, Image.Image] = {}
        self._t, self._w = _smoothed_profile()
        self._sil, self._head_sil, self._ear_tris = self._build_silhouette()

    # ------------------------------------------------------------ 基础
    def font(self, size: int, bold: bool = True):
        key = (size, bold)
        if key not in self._fonts:
            path = FONT_BOLD if bold else FONT_NORMAL
            try:
                self._fonts[key] = ImageFont.truetype(str(path), size)
            except OSError:
                self._fonts[key] = ImageFont.load_default()
        return self._fonts[key]

    def _w_at(self, v: float) -> float:
        return float(np.interp(v, self._t, self._w))

    def _build_silhouette(self):
        """头 + 身体 + 两只耳朵 拼成一条闭合轮廓，描边才不会断开。"""
        v_bottom = float(self._t[-1])
        v_outer = 0.225     # 耳根外侧落在轮廓上的位置
        v_top = 0.105       # 耳根内侧（靠近头顶）
        tip_l = (0.252, 0.018)
        tip_r = (0.748, 0.018)

        b_lo = (0.5 - self._w_at(v_outer), v_outer)
        b_ro = (0.5 + self._w_at(v_outer), v_outer)
        b_li = (0.5 - self._w_at(v_top), v_top)
        b_ri = (0.5 + self._w_at(v_top), v_top)

        left_down = [(0.5 - self._w_at(v), v) for v in np.linspace(v_outer, v_bottom, 150)]
        right_up = [(0.5 + self._w_at(v), v) for v in np.linspace(v_bottom, v_outer, 150)]
        top_arc = ([(0.5 + self._w_at(v), v) for v in np.linspace(v_outer, 0.045, 60)]
                   + [(0.5 - self._w_at(v), v) for v in np.linspace(0.045, v_outer, 60)])

        pts = left_down + right_up + [b_ro, tip_r, b_ri]
        pts += ([(0.5 + self._w_at(v), v) for v in np.linspace(v_top, 0.045, 26)]
                + [(0.5 - self._w_at(v), v) for v in np.linspace(0.045, v_top, 26)])
        pts += [b_li, tip_l]

        head = left_down + right_up + top_arc

        return pts, head, ([b_lo, tip_l, b_li], [b_ro, tip_r, b_ri])

    @staticmethod
    def _shrink_tri(tri, k=0.52):
        tip, a, b = tri
        cx = (tip[0] + a[0] + b[0]) / 3.0
        cy = (tip[1] + a[1] + b[1]) / 3.0
        return [(cx + (p[0] - cx) * k, cy + (p[1] - cy) * k) for p in tri]

    # ------------------------------------------------------------ 主入口
    def render(self, index: int, blink: bool = False, scale: int = STORE) -> Image.Image:
        key = (index, blink)
        img = self._cache.get(key)
        if img is None:
            img = self._render_full(EXPRESSIONS[index], blink)
            self._cache[key] = img
        if scale != STORE:
            img = img.resize((scale, scale), Image.LANCZOS)
        return img

    def _render_full(self, spec: dict, blink: bool) -> Image.Image:
        layer = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)

        self._draw_body(d)
        self._draw_patches(layer)
        self._draw_ears(layer)
        self._draw_paws(d)
        self._draw_face(d, spec, blink)
        self._draw_extras(d, spec)

        if spec.get("tilt"):
            layer = layer.rotate(spec["tilt"], resample=Image.BICUBIC, expand=False)

        return layer.resize((STORE, STORE), Image.LANCZOS)

    # ------------------------------------------------------------ 坐标
    @staticmethod
    def _p(u, v):
        return (u * CANVAS, v * CANVAS)

    @staticmethod
    def _l(x):
        return x * CANVAS

    @staticmethod
    def _stroke(d, pts, width, color, closed=False):
        """圆头笔刷描边：用密集圆点代替 Pillow 的超宽 line，避免关节漏缝。"""
        r = max(1.0, width / 2.0)
        seq = list(pts) + ([pts[0]] if closed else [])
        step = max(1.0, r * 0.55)
        for (x0, y0), (x1, y1) in zip(seq, seq[1:]):
            dist = math.hypot(x1 - x0, y1 - y0)
            n = max(1, int(dist / step))
            for i in range(n + 1):
                t = i / n
                x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                d.ellipse([x - r, y - r, x + r, y + r], fill=color)

    # ------------------------------------------------------------ 身体
    def _draw_body(self, d: ImageDraw.ImageDraw):
        pts = [self._p(u, v) for u, v in self._sil]
        d.polygon(pts, fill=CREAM)
        self._stroke(d, pts, OW, INK, closed=True)

        # 肚子浅色
        belly = _blob(0.5, 0.80, 0.215, 0.185, phase=0.7, wobble=0.05)
        d.polygon([self._p(u, v) for u, v in belly], fill=CREAM_LIGHT)

    def _draw_ears(self, layer: Image.Image):
        """内耳粉色：只保留耳朵露在头部轮廓外的部分。"""
        mask = Image.new("L", layer.size, 0)
        md = ImageDraw.Draw(mask)
        for tri in self._ear_tris:
            md.polygon([self._p(u, v) for u, v in tri], fill=255)
        md.polygon([self._p(u, v) for u, v in self._head_sil], fill=0)

        pink = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        pd = ImageDraw.Draw(pink)
        for tip, a, b in self._ear_tris:
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            tri = [
                (tip[0] + (mid[0] - tip[0]) * 0.20, tip[1] + (mid[1] - tip[1]) * 0.20),
                (tip[0] + (a[0] - tip[0]) * 0.44, tip[1] + (a[1] - tip[1]) * 0.44),
                (tip[0] + (b[0] - tip[0]) * 0.44, tip[1] + (b[1] - tip[1]) * 0.44),
            ]
            pd.polygon([self._p(u, v) for u, v in tri], fill=PINK)
        pink.putalpha(ImageChops.multiply(pink.getchannel("A"), mask))
        layer.alpha_composite(pink)

    def _draw_patches(self, layer: Image.Image):
        """橘色花斑，裁剪在身体轮廓内。"""
        mask = Image.new("L", layer.size, 0)
        md = ImageDraw.Draw(mask)
        md.polygon([self._p(u, v) for u, v in self._sil], fill=255)

        patch = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        pd = ImageDraw.Draw(patch)
        shapes = [
            (_blob(0.68, 0.115, 0.115, 0.075, phase=1.1), ORANGE),    # 右额头
            (_blob(0.245, 0.185, 0.075, 0.090, phase=2.4), ORANGE_D),  # 左耳根
            (_blob(0.775, 0.735, 0.105, 0.150, phase=0.2), ORANGE),   # 右侧身
            (_blob(0.225, 0.800, 0.085, 0.120, phase=3.3), ORANGE),   # 左侧身
        ]
        for pts, color in shapes:
            pd.polygon([self._p(u, v) for u, v in pts], fill=color)

        patch.putalpha(ImageChops.multiply(patch.getchannel("A"), mask))
        layer.alpha_composite(patch)

    def _draw_tail(self, d: ImageDraw.ImageDraw):
        # 尾巴：藏在身体后面，从右侧探出并向上翘起
        p0, c1, c2, p1 = (0.795, 0.760), (0.930, 0.700), (0.975, 0.470), (0.880, 0.335)
        pts = []
        n = 64
        for i in range(n + 1):
            t = i / n
            u = 1 - t
            x = (u ** 3 * p0[0] + 3 * u * u * t * c1[0]
                 + 3 * u * t * t * c2[0] + t ** 3 * p1[0])
            y = (u ** 3 * p0[1] + 3 * u * u * t * c1[1]
                 + 3 * u * t * t * c2[1] + t ** 3 * p1[1])
            pts.append(self._p(x, y))

        w = self._l(0.080)
        self._stroke(d, pts, w + 2 * OW, INK)
        self._stroke(d, pts, w, CREAM)
        # 橘色尾巴尖
        self._stroke(d, pts[-13:], w, ORANGE)

    def _draw_paws(self, d: ImageDraw.ImageDraw):
        for cx in (0.352, 0.648):
            box = [self._p(cx - 0.098, 0.885), self._p(cx + 0.098, 0.985)]
            d.ellipse(box, fill=CREAM, outline=INK, width=OW)
            for dx in (-0.036, 0.0, 0.036):
                d.line([self._p(cx + dx, 0.930), self._p(cx + dx * 1.2, 0.955)],
                       fill=INK, width=OW2)

    # ------------------------------------------------------------ 五官
    def _draw_face(self, d: ImageDraw.ImageDraw, spec: dict, blink: bool):
        ex = (0.372, 0.628)
        ey = 0.385
        rx, ry = 0.088, 0.102
        mode = "closed" if blink else spec["eyes"]

        # 腮红（先画，避免盖住眼睛）
        if spec.get("blush"):
            for cx in (0.283, 0.717):
                box = [self._p(cx - 0.058, 0.452), self._p(cx + 0.058, 0.512)]
                d.ellipse(box, fill=BLUSH)

        for side, cx in zip(("l", "r"), ex):
            self._draw_eye(d, side, cx, ey, rx, ry, mode)

        # 鼻子
        nose = [self._p(0.500, 0.430), self._p(0.556, 0.448), self._p(0.500, 0.480),
                self._p(0.444, 0.448)]
        d.polygon(nose, fill=NOSE_PINK)
        d.line(nose + [nose[0]], fill=INK, width=int(OW * 0.8), joint="curve")

        self._draw_mouth(d, spec["mouth"])
        self._draw_whiskers(d)

    def _draw_eye(self, d, side, cx, cy, rx, ry, mode):
        x0, y0 = self._p(cx - rx, cy - ry)
        x1, y1 = self._p(cx + rx, cy + ry)
        box = [x0, y0, x1, y1]
        cx_px, cy_px = self._p(cx, cy)
        rx_px, ry_px = self._l(rx), self._l(ry)

        if mode == "round" or mode == "round_small":
            k = 0.86 if mode == "round_small" else 1.0
            b = [cx_px - rx_px * k, cy_px - ry_px * k, cx_px + rx_px * k, cy_px + ry_px * k]
            d.ellipse(b, fill=INK)
            d.ellipse([b[0] + rx_px * 0.12, b[1] + ry_px * 0.08,
                       b[2] - rx_px * 0.12, b[3] - ry_px * 0.10], fill=(58, 34, 24, 255))
            # 高光
            d.ellipse([cx_px - rx_px * 0.62, cy_px - ry_px * 0.70,
                       cx_px + rx_px * 0.10, cy_px - ry_px * 0.04], fill=WHITE)
            d.ellipse([cx_px + rx_px * 0.22, cy_px + ry_px * 0.18,
                       cx_px + rx_px * 0.52, cy_px + ry_px * 0.50],
                      fill=(214, 205, 200, 255))

        elif mode == "happy":  # ∩ 闭眼笑
            d.arc(box, 200, 340, fill=INK, width=int(OW * 1.5))
            d.arc([x0, y0 + ry_px * 0.30, x1, y1 + ry_px * 0.30], 200, 340,
                  fill=INK, width=int(OW * 0.7))

        elif mode == "closed":  # 眨眼
            d.arc([x0, y0 + ry_px * 0.35, x1, y1 + ry_px * 0.35], 200, 340,
                  fill=INK, width=int(OW * 1.3))

        elif mode == "cry":  # ∪ 闭眼 + 泪
            d.arc(box, 20, 160, fill=INK, width=int(OW * 1.5))
            d.arc([x0, y0 - ry_px * 0.30, x1, y1 - ry_px * 0.30], 20, 160,
                  fill=INK, width=int(OW * 0.7))

        elif mode == "heart":
            for s in (0.052,):
                pts = _heart_pts(cx, cy, s)
                d.polygon([self._p(u, v) for u, v in pts], fill=HEART)
                d.line([self._p(u, v) for u, v in pts] + [self._p(*pts[0])],
                       fill=INK, width=int(OW * 0.7), joint="curve")
            d.ellipse([cx_px - rx_px * 0.42, cy_px - ry_px * 0.52,
                       cx_px - rx_px * 0.10, cy_px - ry_px * 0.18], fill=(255, 255, 255, 220))

        elif mode == "shock":  # 大白眼
            d.ellipse(box, fill=WHITE, outline=INK, width=OW)
            pr = rx_px * 0.36
            d.ellipse([cx_px - pr, cy_px - pr * 1.05, cx_px + pr, cy_px + pr * 1.05], fill=INK)
            d.ellipse([cx_px - pr * 0.80, cy_px - pr * 0.95,
                       cx_px - pr * 0.18, cy_px - pr * 0.28], fill=WHITE)

        elif mode == "sleepy":  # 闭眼睡觉
            d.arc([x0, y0 + ry_px * 0.20, x1, y1 + ry_px * 0.20], 200, 340,
                  fill=INK, width=int(OW * 1.6))
            # 睫毛
            for dx, dy in ((-0.72, 0.10), (-0.30, -0.16)):
                px0 = cx_px + dx * rx_px
                py0 = cy_px + ry_px * 0.28 + dy * ry_px
                d.line([(px0, py0), (px0 - rx_px * 0.16, py0 - ry_px * 0.26)],
                       fill=INK, width=int(OW * 0.7))

        elif mode == "smug":  # 得意半眯眼
            b = [cx_px - rx_px, cy_px - ry_px * 0.12, cx_px + rx_px, cy_px + ry_px]
            d.ellipse(b, fill=INK)
            d.rectangle([b[0] - 2, b[1] - ry_px * 0.42, b[2] + 2, b[1] + ry_px * 0.12],
                        fill=CREAM)
            d.line([b[0] - 1, b[1] + ry_px * 0.12, b[2] + 1, b[1] + ry_px * 0.12],
                   fill=INK, width=int(OW * 1.3))
            d.ellipse([cx_px + rx_px * 0.18, cy_px + ry_px * 0.42,
                       cx_px + rx_px * 0.46, cy_px + ry_px * 0.70],
                      fill=(250, 250, 250, 255))

        elif mode == "angry":
            b = [cx_px - rx_px * 0.92, cy_px - ry_px * 0.86,
                 cx_px + rx_px * 0.92, cy_px + ry_px * 0.92]
            d.ellipse(b, fill=INK)
            d.ellipse([b[0] + rx_px * 0.30, b[1] + ry_px * 0.34,
                       b[2] - rx_px * 0.30, b[3] - ry_px * 0.26], fill=(48, 27, 20, 255))
            d.ellipse([cx_px - rx_px * 0.60, cy_px - ry_px * 0.66,
                       cx_px - rx_px * 0.22, cy_px - ry_px * 0.30], fill=(255, 226, 210, 255))
            # 眉毛
            bx0, by0 = self._p(cx - 0.115, 0.285)
            bx1, by1 = self._p(cx + 0.105, 0.325)
            d.line([(bx0, by0), (bx1, by1)], fill=INK, width=int(OW * 1.5))
            d.line([(bx0, by0 + 2), (bx1, by1)], fill=INK, width=int(OW * 0.8))

        elif mode == "wink":
            d.arc(box, 200, 340, fill=INK, width=int(OW * 1.5))

    def _draw_mouth(self, d, style):
        if style == "w":
            y = 0.492
            for cx in (0.468, 0.532):
                box = [self._p(cx - 0.036, y - 0.010), self._p(cx + 0.036, y + 0.045)]
                d.arc(box, 15, 165, fill=INK, width=int(OW * 0.9))
            d.line([self._p(0.5, 0.480), self._p(0.5, 0.497)], fill=INK, width=int(OW * 0.8))

        elif style == "grin":
            box = [self._p(0.392, 0.452), self._p(0.608, 0.585)]
            d.chord(box, 0, 180, fill=MOUTH)
            d.chord([self._p(0.428, 0.470), self._p(0.572, 0.600)], 0, 180, fill=TONGUE)
            d.chord([self._p(0.392, 0.452), self._p(0.608, 0.552)], 0, 180, fill=MOUTH)
            d.chord([self._p(0.420, 0.452), self._p(0.580, 0.520)], 0, 180, fill=MOUTH)
            # 小虎牙
            for fx in (0.442, 0.558):
                tri = [self._p(fx - 0.020, 0.470), self._p(fx + 0.020, 0.470),
                       self._p(fx, 0.505)]
                d.polygon(tri, fill=WHITE)

        elif style == "fangs":
            box = [self._p(0.372, 0.448), self._p(0.628, 0.610)]
            d.chord(box, 0, 180, fill=MOUTH)
            d.chord([self._p(0.430, 0.500), self._p(0.570, 0.625)], 0, 180, fill=TONGUE)
            for fx in (0.430, 0.570):
                tri = [self._p(fx - 0.026, 0.462), self._p(fx + 0.026, 0.462),
                       self._p(fx, 0.520)]
                d.polygon(tri, fill=WHITE)
            # 咬牙线
            d.line([self._p(0.455, 0.492), self._p(0.545, 0.492)], fill=MOUTH, width=OW2)

        elif style == "open":
            box = [self._p(0.455, 0.470), self._p(0.545, 0.545)]
            d.ellipse(box, fill=MOUTH)
            d.chord([self._p(0.465, 0.505), self._p(0.535, 0.552)], 0, 180, fill=TONGUE)

        elif style == "open_big":
            box = [self._p(0.428, 0.462), self._p(0.572, 0.575)]
            d.ellipse(box, fill=MOUTH)
            d.chord([self._p(0.440, 0.520), self._p(0.560, 0.585)], 0, 180, fill=TONGUE)

        elif style == "wavy":
            pts = []
            for i in range(9):
                x = 0.430 + i * 0.0175
                y = 0.500 + (0.020 if i % 2 else -0.020)
                pts.append(self._p(x, y))
            d.line(pts, fill=INK, width=int(OW * 0.9), joint="curve")

        elif style == "small":
            d.arc([self._p(0.462, 0.470), self._p(0.538, 0.520)], 15, 165,
                  fill=INK, width=int(OW * 0.9))

        elif style == "smirk":
            pts = _bezier((0.452, 0.505), (0.505, 0.548), (0.566, 0.492), 32)
            d.line([self._p(u, v) for u, v in pts], fill=INK, width=int(OW * 1.0), joint="curve")

    def _draw_whiskers(self, d):
        spec = [
            ((0.292, 0.438), (0.205, 0.408), (0.128, 0.398)),
            ((0.288, 0.468), (0.196, 0.462), (0.118, 0.462)),
            ((0.292, 0.498), (0.205, 0.518), (0.132, 0.538)),
        ]
        for a, b, c in spec:
            for flip in (1, -1):
                pa = (0.5 + (a[0] - 0.5) * flip, a[1])
                pb = (0.5 + (b[0] - 0.5) * flip, b[1])
                pc = (0.5 + (c[0] - 0.5) * flip, c[1])
                d.line([self._p(*pa), self._p(*pb), self._p(*pc)],
                       fill=WHISKER, width=int(OW * 0.75), joint="curve")

    # ------------------------------------------------------------ 表情装饰
    def _draw_extras(self, d: ImageDraw.ImageDraw, spec: dict):
        for name in spec.get("extras", ()):
            if name == "sparkle":
                for cx, cy, s in ((0.180, 0.120, 0.052), (0.828, 0.205, 0.038),
                                  (0.868, 0.360, 0.028)):
                    pts = _star(cx * CANVAS, cy * CANVAS, s * CANVAS)
                    d.polygon(pts, fill=SPARK)
                    d.line(pts + [pts[0]], fill=(224, 168, 62, 255), width=OW2, joint="curve")
            elif name == "hearts":
                for cx, cy, s in ((0.212, 0.095, 0.050), (0.782, 0.075, 0.042),
                                  (0.858, 0.268, 0.030)):
                    pts = _heart_pts(cx, cy, s)
                    d.polygon([self._p(u, v) for u, v in pts], fill=HEART)
                    d.line([self._p(u, v) for u, v in pts] + [self._p(*pts[0])],
                           fill=INK, width=int(OW * 0.8), joint="curve")
            elif name == "question":
                f = self.font(int(CANVAS * 0.115))
                d.text(self._p(0.812, 0.108), "?", font=f, fill=INK, anchor="mm")
                d.text(self._p(0.884, 0.212), "?", font=self.font(int(CANVAS * 0.080)),
                       fill=(120, 82, 60, 255), anchor="mm")
            elif name == "anger":
                cx, cy = self._p(0.766, 0.128)
                s = self._l(0.052)
                for ang in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2):
                    dx, dy = math.cos(ang), math.sin(ang)
                    d.line([(cx + dx * s * 0.55, cy + dy * s * 0.55),
                            (cx + dx * s * 1.25, cy + dy * s * 1.25)],
                           fill=(232, 96, 92, 255), width=int(OW * 1.2))
            elif name == "tears":
                for cx, cy in ((0.318, 0.560), (0.682, 0.560)):
                    pts = _drop(cx, cy, 0.062)
                    d.polygon([self._p(u, v) for u, v in pts], fill=TEAR)
                    d.line([self._p(u, v) for u, v in pts] + [self._p(*pts[0])],
                           fill=(70, 140, 190, 255), width=int(OW * 0.6), joint="curve")
                    d.ellipse([self._p(cx - 0.028, cy - 0.030), self._p(cx - 0.004, cy - 0.004)],
                              fill=(255, 255, 255, 200))
                for x in (0.336, 0.664):
                    d.line([self._p(x, 0.470), self._p(x + (0.01 if x < 0.5 else -0.01), 0.640)],
                           fill=(168, 212, 240, 255), width=int(OW * 0.7))
            elif name == "sweat":
                pts = _drop(0.786, 0.190, 0.048)
                d.polygon([self._p(u, v) for u, v in pts], fill=TEAR)
                d.line([self._p(u, v) for u, v in pts] + [self._p(*pts[0])],
                       fill=(70, 140, 190, 255), width=int(OW * 0.6), joint="curve")
            elif name == "zzz":
                for i, (cx, cy, sz) in enumerate(((0.790, 0.088, 0.100),
                                                  (0.858, 0.160, 0.078),
                                                  (0.912, 0.216, 0.058))):
                    f = self.font(int(CANVAS * sz))
                    d.text(self._p(cx, cy), "Z", font=f, fill=(120, 96, 190, 255), anchor="mm")
            elif name == "note":
                self._draw_note(d, 0.822, 0.120, 0.085, (214, 116, 160, 255))
                self._draw_note(d, 0.892, 0.212, 0.065, (214, 116, 160, 255), flip=True)

    def _draw_note(self, d, cx, cy, s, color, flip=False):
        """手绘音符（系统字体里 ♪ 常常缺字形，干脆自己画）。"""
        sx = -1 if flip else 1
        head = _blob(cx + 0.0 * sx, cy + s * 0.55, s * 0.46, s * 0.34, wobble=0.03, phase=0.4)
        d.polygon([self._p(u, v) for u, v in head], fill=color)
        x = cx + s * 0.40 * sx
        d.line([self._p(x, cy + s * 0.55), self._p(x, cy - s * 0.85)],
               fill=color, width=int(s * 0.18 * CANVAS))
        d.line([self._p(x, cy - s * 0.85), self._p(x + s * 0.66 * sx, cy - s * 0.58)],
               fill=color, width=int(s * 0.20 * CANVAS), joint="curve")
        d.line([self._p(x + s * 0.66 * sx, cy - s * 0.58),
                self._p(x + s * 0.66 * sx, cy - s * 0.24)],
               fill=color, width=int(s * 0.18 * CANVAS))

    # ------------------------------------------------------------ 气泡
    def bubble(self, text: str, max_width: int = 300) -> Image.Image:
        key = f"{text}|{max_width}"
        img = self._bubble_cache.get(key)
        if img is not None:
            return img

        font = self.font(19)
        bbox = font.getbbox(text)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pad_x, pad_y = 16, 9
        bw = min(max_width, tw + pad_x * 2)
        bh = th + pad_y * 2 + 4
        tail = 11
        w, h = bw + 8, bh + tail + 6

        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # 小尾巴
        tipx = w / 2
        d.polygon([(tipx - 8, h - tail - 6), (tipx + 8, h - tail - 6), (tipx + 1, h - 2)],
                  fill=BUBBLE_BG, outline=BUBBLE_INK)
        d.line([(tipx - 8, h - tail - 6), (tipx + 1, h - 2), (tipx + 8, h - tail - 6)],
               fill=BUBBLE_INK, width=2, joint="curve")
        d.rounded_rectangle([1, 1, w - 2, h - tail - 4], radius=12,
                            fill=BUBBLE_BG, outline=BUBBLE_INK, width=2)
        # 盖住圆角矩形底边被尾巴线穿透的部分
        d.rectangle([tipx - 9, h - tail - 8, tipx + 9, h - tail - 5], fill=BUBBLE_BG)
        d.text((w / 2, (h - tail - 4) / 2 + 1), text, font=font, fill=BUBBLE_INK, anchor="mm")
        self._bubble_cache[key] = img
        return img


if __name__ == "__main__":
    art = HajimiArt()
    sheet = Image.new("RGBA", (DESIGN * 3, DESIGN * 3), (250, 246, 238, 255))
    for i, spec in enumerate(EXPRESSIONS):
        tile = art.render(i, scale=DESIGN)
        sheet.alpha_composite(tile, ((i % 3) * DESIGN, (i // 3) * DESIGN))
    out = Path(__file__).with_name("preview")
    out.mkdir(exist_ok=True)
    sheet.convert("RGB").save(out / "expr_sheet.png")
    print("saved", out / "expr_sheet.png")

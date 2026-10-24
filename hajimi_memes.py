# -*- coding: utf-8 -*-
"""梗图包：把 memes/ 里的图片做成「圆角贴纸」，供桌宠点击切换。

- 支持 jpg/png/webp/bmp，自动居中裁成正方形
- 统一加白色贴纸边 + 深色描边 + 圆角
- 可选 memes/captions.txt 提供每张图的台词（# 开头为注释）
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

INK = (72, 44, 30, 255)
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


class MemePack:
    def __init__(self, folder: Path | str | None, display: int = 340):
        self.folder = Path(folder) if folder else None
        self.display = display
        self.files: list[Path] = []
        self.captions: dict[int, str] = {}
        self._cache: dict[tuple[int, int], Image.Image] = {}
        self._src: dict[int, Image.Image] = {}
        if self.folder and self.folder.is_dir():
            self.files = sorted(p for p in self.folder.iterdir()
                                if p.suffix.lower() in EXTS and p.is_file())
            self._load_captions()

    def _load_captions(self):
        f = self.folder / "captions.txt"
        if not f.is_file():
            return
        try:
            lines = [ln.strip() for ln in f.read_text("utf-8").splitlines()]
        except OSError:
            return
        lines = [ln for ln in lines if ln and not ln.startswith("#")]
        for i, ln in enumerate(lines):
            self.captions[i] = ln

    def __len__(self) -> int:
        return len(self.files)

    @property
    def ready(self) -> bool:
        return bool(self.files)

    def caption(self, index: int) -> str | None:
        return self.captions.get(index % len(self.files)) if self.files else None

    def name(self, index: int) -> str:
        return self.files[index % len(self.files)].stem if self.files else ""

    def _source(self, index: int) -> Image.Image | None:
        index %= len(self.files)
        img = self._src.get(index)
        if img is None:
            try:
                img = Image.open(self.files[index]).convert("RGB")
            except Exception:
                return None
            self._src[index] = img
        return img

    def render(self, index: int, size: int) -> Image.Image | None:
        """返回一张方形贴纸（RGBA，圆角外侧透明）。"""
        if not self.files:
            return None
        key = (index % len(self.files), size)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        src = self._source(index)
        if src is None:
            return None

        w, h = src.size
        border = max(4, int(size * 0.030))
        radius = max(6, int(size * 0.11))
        line = max(2, int(size * 0.012))
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(canvas)
        d.rounded_rectangle([line // 2, line // 2, size - 1 - line // 2, size - 1 - line // 2],
                            radius=radius, fill=(255, 252, 246, 255),
                            outline=INK, width=line)

        inner = size - border * 2
        if inner < 8:
            return None
        # 等比缩放 + 白边留白，避免把梗图上的字裁掉
        pic = ImageOps.pad(src, (inner, inner), method=Image.LANCZOS,
                           color=(255, 252, 246), centering=(0.5, 0.42))
        mask = Image.new("L", (inner, inner), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, inner - 1, inner - 1], radius=max(3, radius - border // 2), fill=255)
        canvas.paste(pic, (border, border), mask)

        if len(self._cache) > 24:
            self._cache.clear()
        self._cache[key] = canvas
        return canvas

    def contact_sheet(self, cell: int = 170, cols: int = 6) -> Image.Image | None:
        if not self.files:
            return None
        rows = (len(self.files) + cols - 1) // cols
        sheet = Image.new("RGB", (cell * cols, (cell + 6) * rows), (246, 243, 238))
        for i in range(len(self.files)):
            sticker = self.render(i, cell - 8)
            if sticker is None:
                continue
            sheet.paste(sticker, ((i % cols) * cell + 4, (i // cols) * (cell + 6) + 4),
                        sticker)
        return sheet

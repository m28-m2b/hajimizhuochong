# -*- coding: utf-8 -*-
"""补充抓图：只保留标题里带“猫/喵/哈基米”的、接近方形的图，避开贴纸面板截图。

用法：python tools/fetch_memes_more2.py --start 65 --count 16
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import socket
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MEMES = ROOT / "memes"
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
      "Accept-Language": "zh-CN,zh;q=0.9"}
CTX = ssl._create_unverified_context()
QUERIES = [
    "猫咪表情包",
    "猫猫表情包 好笑",
    "小猫 沙雕 表情",
    "猫 meme 表情包",
    "哈基米 猫猫",
    "猫猫头 表情包",
]
HINT = ("猫", "喵", "哈基米", "cat", "meme")
BAD = ("贴纸", "打包", "下载", "合集", "面板")


def get(url, timeout=18):
    h = dict(UA)
    h["Referer"] = "https://image.so.com/"
    return urllib.request.urlopen(urllib.request.Request(url, headers=h),
                                  timeout=timeout, context=CTX).read()


def search(query, pn):
    url = f"https://image.so.com/j?q={urllib.parse.quote(query)}&pn={pn}&rn=30&src=srp"
    data = json.loads(get(url).decode("utf-8", "ignore"))
    return [{"thumb": it["thumb"], "img": it.get("img") or it["thumb"],
             "title": it.get("title", ""), "query": query}
            for it in data.get("list", []) if it.get("thumb")]


def ahash(img):
    g = img.convert("L").resize((16, 16), Image.LANCZOS)
    px = list(g.getdata())
    avg = sum(px) / len(px)
    return hashlib.md5("".join("1" if v > avg else "0" for v in px).encode()).hexdigest()


def load(b):
    try:
        img = Image.open(io.BytesIO(b))
        img.load()
    except Exception:
        return None
    if img.format not in ("JPEG", "PNG", "WEBP", "BMP"):
        return None
    w, h = img.size
    if w < 260 or h < 260:
        return None
    r = w / h
    if r < 0.75 or r > 1.45:
        return None
    img = img.convert("RGB")
    s = min(1.0, 620 / max(w, h))
    if s < 1.0:
        img = img.resize((int(w * s), int(h * s)), Image.LANCZOS)
    return img


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=65)
    ap.add_argument("--count", type=int, default=16)
    args = ap.parse_args(argv)
    socket.setdefaulttimeout(20)

    seen = {}
    for p in MEMES.glob("hajimi_*.jpg"):
        try:
            seen[ahash(Image.open(p).convert("RGB"))] = p.name
        except Exception:
            pass

    sources = json.loads((MEMES / "sources.json").read_text("utf-8"))
    idx, saved = args.start, 0
    for q in QUERIES:
        if idx >= args.start + args.count:
            break
        for pn in (30, 60, 90, 120, 150):
            if idx >= args.start + args.count:
                break
            try:
                items = search(q, pn)
            except Exception as exc:
                print("[warn]", q, pn, exc)
                continue
            for it in items:
                if idx >= args.start + args.count:
                    break
                title = it["title"]
                low = title.lower()
                if not any(h in low for h in HINT):
                    continue
                if any(b in title for b in BAD):
                    continue
                for url in (it["thumb"], it["img"]):
                    try:
                        img = load(get(url))
                    except Exception:
                        continue
                    if img is None:
                        continue
                    h = ahash(img)
                    if h in seen:
                        break
                    seen[h] = title
                    name = f"hajimi_{idx:02d}.jpg"
                    img.save(MEMES / name, quality=92)
                    sources.append({"file": name, "query": q, "src": url,
                                    "title": title, "batch": "more2"})
                    print(f"  {name} <- {title[:24]} | {url[:60]}")
                    idx += 1
                    saved += 1
                    break
                time.sleep(0.06)

    (MEMES / "sources.json").write_text(
        json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nadded {saved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

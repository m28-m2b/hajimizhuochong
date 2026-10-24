# -*- coding: utf-8 -*-
"""再抓一批哈基米梗图，追加到 memes/（自动跳过已有的相似图）。

用法：python tools/fetch_memes_more.py --count 20
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
    "哈基米 表情包 搞笑",
    "哈基米 猫 沙雕",
    "哈基米 大笑 表情",
    "哈基米 生气 表情",
    "哈基米 可爱 猫猫",
    "小猫 梗图 表情包",
    "哈基米 猫 凝视",
]


def get(url, timeout=18, referer="https://image.so.com/"):
    h = dict(UA)
    h["Referer"] = referer
    return urllib.request.urlopen(urllib.request.Request(url, headers=h),
                                  timeout=timeout, context=CTX).read()


def search_360(query, pn):
    url = f"https://image.so.com/j?q={urllib.parse.quote(query)}&pn={pn}&rn=30&src=srp"
    data = json.loads(get(url).decode("utf-8", "ignore"))
    out = []
    for it in data.get("list", []):
        if it.get("thumb"):
            out.append({"thumb": it["thumb"], "img": it.get("img") or it["thumb"],
                        "title": it.get("title", ""), "query": query})
    return out


def ahash(img: Image.Image) -> str:
    g = img.convert("L").resize((16, 16), Image.LANCZOS)
    px = list(g.getdata())
    avg = sum(px) / len(px)
    return hashlib.md5("".join("1" if v > avg else "0" for v in px).encode()).hexdigest()


def load(img_bytes, max_side=620):
    try:
        img = Image.open(io.BytesIO(img_bytes))
        img.load()
    except Exception:
        return None
    if img.format not in ("JPEG", "PNG", "WEBP", "BMP"):
        return None
    w, h = img.size
    if w < 220 or h < 220:
        return None
    ratio = w / h
    if ratio < 0.55 or ratio > 1.8:
        return None
    img = img.convert("RGB")
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return img


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=20)
    ap.add_argument("--start", type=int, default=31)
    args = ap.parse_args(argv)

    socket.setdefaulttimeout(20)
    targets = {args.start + i for i in range(args.count)}

    seen = {}
    for p in MEMES.glob("hajimi_*.jpg"):
        try:
            seen[ahash(Image.open(p).convert("RGB"))] = p.name
        except Exception:
            pass

    sources = json.loads((MEMES / "sources.json").read_text("utf-8"))
    have = {s["file"] for s in sources}
    saved = 0
    idx = args.start

    for query in QUERIES:
        if idx >= args.start + args.count:
            break
        for pn in (30, 60, 90, 120):
            if idx >= args.start + args.count:
                break
            try:
                items = search_360(query, pn)
            except Exception as exc:
                print(f"[warn] {query} pn={pn}: {exc}")
                continue
            for it in items:
                if idx >= args.start + args.count:
                    break
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
                    seen[h] = f"hajimi_{idx}.jpg"
                    name = f"hajimi_{idx:02d}.jpg"
                    img.save(MEMES / name, quality=92)
                    sources.append({"file": name, "query": query, "src": url,
                                    "title": it.get("title", ""), "batch": "more"})
                    print(f"  {name} <- {url[:80]}")
                    idx += 1
                    saved += 1
                    break
                time.sleep(0.08)

    (MEMES / "sources.json").write_text(
        json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nadded {saved} images, total files: {len(list(MEMES.glob('hajimi_*.jpg')))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

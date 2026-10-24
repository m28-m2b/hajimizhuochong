# -*- coding: utf-8 -*-
"""抓一批「哈基米」梗图，存到 memes/ 目录。

用法：
    python tools/fetch_memes.py --limit 30

来源：360 图片搜索（image.so.com，接口可直连）+ Bing 图片搜索兜底。
抓的是搜索结果的缩略图/原图，尺寸刚好适合桌宠；抓到后按尺寸、比例、去重过滤。
"""
from __future__ import annotations

import argparse
import hashlib
import html as html_mod
import io
import json
import re
import socket
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "memes"
UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}
QUERIES = [
    "哈基米表情包",
    "哈基米 猫 表情包",
    "哈基米 梗图",
    "哈基米 表情",
]
CTX = ssl._create_unverified_context()


def get(url: str, timeout: float = 15.0, referer: str = "") -> bytes:
    headers = dict(UA)
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read()


def search_360(query: str, pages: int = 2) -> list[dict]:
    out = []
    for p in range(pages):
        q = urllib.parse.quote(query)
        url = f"https://image.so.com/j?q={q}&pn={30 + p * 30}&rn=30&src=srp"
        try:
            data = json.loads(get(url, referer="https://image.so.com/").decode("utf-8", "ignore"))
        except Exception as exc:
            print(f"[warn] 360 search failed: {query} ({exc})")
            break
        for it in data.get("list", []):
            thumb, img = it.get("thumb"), it.get("img")
            if not thumb:
                continue
            out.append({"title": it.get("title", ""), "thumb": thumb, "img": img or thumb,
                        "query": query})
    return out


def search_bing(query: str) -> list[dict]:
    q = urllib.parse.quote(query)
    page = get(f"https://cn.bing.com/images/search?q={q}&form=HDRSC2").decode("utf-8", "ignore")
    out = []
    for blob in re.findall(r'm="(\{.*?\})"', page):
        try:
            data = json.loads(html_mod.unescape(blob))
        except json.JSONDecodeError:
            continue
        if data.get("murl"):
            out.append({"title": data.get("t", ""), "thumb": data.get("turl") or data["murl"],
                        "img": data["murl"], "query": query})
    return out


def ahash(img: Image.Image) -> str:
    g = img.convert("L").resize((16, 16), Image.LANCZOS)
    px = list(g.getdata())
    avg = sum(px) / len(px)
    bits = "".join("1" if v > avg else "0" for v in px)
    return hashlib.md5(bits.encode()).hexdigest()


def prepare(raw: bytes, size: int = 460) -> Image.Image | None:
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception:
        return None
    if img.format not in ("JPEG", "PNG", "WEBP", "BMP"):
        return None
    w, h = img.size
    if w < 220 or h < 220:
        return None
    ratio = w / h
    if ratio < 0.62 or ratio > 1.62:
        return None
    img = img.convert("RGB")
    side = min(w, h)
    img = img.crop(((w - side) // 2, (h - side) // 2,
                    (w - side) // 2 + side, (h - side) // 2 + side))
    return img.resize((size, size), Image.LANCZOS)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--size", type=int, default=460)
    args = ap.parse_args(argv)

    socket.setdefaulttimeout(20)
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("hajimi_*.jpg"):
        old.unlink()

    seen: dict[str, str] = {}
    sources: list[dict] = []
    saved = 0
    candidates: list[dict] = []
    for q in QUERIES:
        candidates += search_360(q)
        time.sleep(0.4)
    for q in ("哈基米 表情包", "hajimi cat meme"):
        try:
            candidates += search_bing(q)
        except Exception as exc:
            print(f"[warn] bing failed: {exc}")

    print(f"[info] {len(candidates)} candidates")
    for it in candidates:
        if saved >= args.limit:
            break
        for url in (it["thumb"], it["img"]):
            try:
                raw = get(url, referer=it.get("url") or "https://image.so.com/")
            except Exception:
                continue
            img = prepare(raw, args.size)
            if img is None:
                continue
            key = ahash(img)
            if key in seen:
                break
            seen[key] = url
            saved += 1
            name = f"hajimi_{saved:02d}.jpg"
            img.save(OUT / name, quality=90)
            sources.append({"file": name, "query": it["query"], "src": url,
                            "title": it.get("title", "")})
            print(f"  saved {name}  <- {url[:90]}")
            break
        time.sleep(0.1)

    (OUT / "sources.json").write_text(
        json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ntotal {saved} images -> {OUT}")


if __name__ == "__main__":
    main()

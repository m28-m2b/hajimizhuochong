# -*- coding: utf-8 -*-
"""从酷我抓哈基米/猫叫音频，存到 sounds/web/。

没有 ffmpeg 也没关系：播放用 MCI，可以直接只播一段（比如 0~2.5 秒）。
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import socket
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sounds" / "web"
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
      "Referer": "https://www.kuwo.cn/"}
CTX = ssl._create_unverified_context()
QUERIES = ["哈基米", "哈基米 猫", "哈基米 BGM", "猫叫 音效", "猫咪 撒娇 叫声"]


def get(url, timeout=25):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                  timeout=timeout, context=CTX).read()


def search(keyword, n=15):
    q = urllib.parse.quote(keyword)
    url = (f"http://search.kuwo.cn/r.s?all={q}&ft=music&itemset=web_2013&client=kt"
           f"&pn=0&rn={n}&rformat=json&encoding=utf8")
    txt = get(url).decode("utf-8", "ignore")
    try:
        data = ast.literal_eval(txt)
    except Exception:
        return []
    items = []
    for it in data.get("abslist") or []:
        rid = str(it.get("MUSICRID", "")).replace("MUSIC_", "")
        if not rid.isdigit():
            continue
        items.append({
            "rid": rid,
            "name": (it.get("SONGNAME") or "").replace("&nbsp;", " "),
            "artist": (it.get("ARTIST") or "").replace("&nbsp;", " "),
            "duration": int(it.get("DURATION") or 0),
        })
    return items


def audio_url(rid):
    q = urllib.parse.quote(f"corp=kuwo&p2p=1&type=convert_url2&sig=0&format=mp3&rid={rid}")
    raw = get("https://mobi.kuwo.cn/mobi.s?f=kuwo&q=" + q) if False else None
    url = (f"http://antiserver.kuwo.cn/anti.s?type=convert_url3&rid=MUSIC_{rid}"
           "&format=mp3&response=url")
    data = json.loads(get(url).decode("utf-8", "ignore"))
    return data.get("url")


def probe_ms(path: Path) -> int | None:
    import ctypes
    winmm = ctypes.windll.winmm
    buf = ctypes.create_unicode_buffer(256)
    if winmm.mciSendStringW(f'open "{path}" type mpegvideo alias probe', buf, 256, None) != 0:
        winmm.mciSendStringW("close probe", None, 0, None)
        return None
    winmm.mciSendStringW("set probe time format milliseconds", None, 0, None)
    winmm.mciSendStringW("status probe length", buf, 256, None)
    try:
        ms = int(buf.value)
    except ValueError:
        ms = None
    winmm.mciSendStringW("close probe", None, 0, None)
    return ms


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--max-mb", type=float, default=7.0)
    args = ap.parse_args(argv)

    socket.setdefaulttimeout(25)
    OUT.mkdir(parents=True, exist_ok=True)
    meta_file = OUT / "sources.json"
    meta = json.loads(meta_file.read_text("utf-8")) if meta_file.exists() else []
    seen = {m.get("rid") for m in meta}
    saved = 0

    for kw in QUERIES:
        if saved >= args.limit:
            break
        try:
            items = search(kw)
        except Exception as exc:
            print(f"[warn] search {kw}: {exc}")
            continue
        print(f"[info] {kw}: {len(items)} songs")
        for it in items:
            if saved >= args.limit:
                break
            if it["rid"] in seen:
                continue
            print(f"  try {it['name'][:26]} / {it['artist'][:10]} / {it['duration']}s")
            try:
                url = audio_url(it["rid"])
            except Exception as exc:
                print("    url fail:", exc)
                continue
            if not url:
                print("    no url")
                continue
            try:
                data = get(url)
            except Exception as exc:
                print("    download fail:", exc)
                continue
            if len(data) < 30000:
                print("    too small")
                continue
            if len(data) > args.max_mb * 1024 * 1024:
                print("    too big")
                continue
            name = f"web_{saved + 1:02d}.mp3"
            path = OUT / name
            path.write_bytes(data)
            ms = probe_ms(path)
            if not ms:
                print("    not playable, removed")
                path.unlink(missing_ok=True)
                continue
            meta.append({"file": name, "rid": it["rid"], "name": it["name"],
                         "artist": it["artist"], "query": kw, "ms": ms, "src": url})
            seen.add(it["rid"])
            saved += 1
            print(f"    saved {name}  {ms/1000:.1f}s  {len(data)/1024:.0f}KB")

    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved {saved} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""抓取英国 MAIB 碰撞事故报告（按 seed.csv 里的 NO x/yyyy 编号）。

流程：gov.uk 搜索 API -> 报告页 -> 找 PDF 附件 -> 下载。
没有 PDF 的，退回落网页正文。

用法：
    python src/crawl/fetch_uk.py --limit 3 --dry-run
    python src/crawl/fetch_uk.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import (DATA, ensure_dir, iter_csv, normalize_id, safe_filename,
                    setup_logging, write_csv)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
API = ("https://www.gov.uk/api/search.json?filter_organisations="
       "marine-accident-investigation-branch&count=10&q=")


def http_get(url: str, timeout: int = 40) -> bytes:
    time.sleep(random.uniform(1.2, 2.5))
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept-Language": "en-GB,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def find_report_page(accident_no: str):
    """用 gov.uk 搜索 API 找报告页，返回 (url, title) 或 (None, None)。"""
    q = urllib.parse.quote(accident_no)
    data = json.loads(http_get(API + q).decode("utf-8", "ignore"))
    results = [r for r in data.get("results", []) if r.get("format") == "maib_report"]
    if not results:
        return None, None
    # 优先标题/描述里含编号的
    for r in results:
        blob = (r.get("title", "") + " " + r.get("description", "")).upper()
        if normalize_id(accident_no) in normalize_id(blob):
            return "https://www.gov.uk" + r["link"], r.get("title", "")
    r = results[0]
    return "https://www.gov.uk" + r["link"], r.get("title", "")


def find_pdf(page_url: str, html: str):
    links = re.findall(r'href="([^"]+\.pdf[^"]*)"', html, re.I)
    for link in links:
        full = urllib.parse.urljoin(page_url, link)
        if "assets.publishing.service.gov.uk" in full or "/media/" in full:
            return full
    return None


def strip_html(html: str) -> str:
    html = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<(p|div|br|li|h\d)[^>]*>", "\n", html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"[ \t]+", " ", text)
    return "\n".join(l.strip() for l in text.split("\n") if l.strip())


def main():
    ap = argparse.ArgumentParser(description="抓取 MAIB 碰撞事故报告")
    ap.add_argument("--seed", default=str(DATA / "seed" / "seed.csv"))
    ap.add_argument("--out", default=str(DATA / "pdf" / "uk"))
    ap.add_argument("--manifest", default=str(DATA / "manifest_uk.csv"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    logger = setup_logging("fetch_uk", DATA / "logs" / "fetch_uk.log")
    rows = [r for r in iter_csv(args.seed) if r.get("country") == "UK"]
    if args.limit:
        rows = rows[: args.limit]
    logger.info("英国待抓取 %d 篇", len(rows))

    ensure_dir(args.out)
    manifest = []
    ok = fail = 0

    for i, row in enumerate(rows, 1):
        acc = normalize_id(row.get("accident_no")) or row["accident_file"]
        try:
            page, title = find_report_page(acc)
            if not page:
                raise RuntimeError("搜索无结果")
            html = http_get(page).decode("utf-8", "ignore")
            pdf = find_pdf(page, html)
            if args.dry_run:
                logger.info("[%d] %s -> %s | pdf=%s", i, acc, page, pdf or "无")
                ok += 1
                continue
            if pdf:
                blob = http_get(pdf)
                if blob[:4] != b"%PDF":
                    raise RuntimeError("附件不是 PDF")
                path = Path(args.out) / f"{safe_filename(acc)}.pdf"
                path.write_bytes(blob)
                kind = "pdf"
            else:
                text = strip_html(html)
                path = Path(args.out) / f"{safe_filename(acc)}.txt"
                path.write_text(text, encoding="utf-8")
                kind = "html"
            manifest.append({
                "accident_no": acc, "source": "UK", "status": "ok", "kind": kind,
                "title": title or "", "url": page,
                "file": str(path.relative_to(DATA)),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
                "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            ok += 1
            logger.info("[%d/%d] %s  %s  %d KB", i, len(rows), acc, kind,
                        path.stat().st_size // 1024)
        except Exception as e:  # noqa: BLE001
            fail += 1
            manifest.append({"accident_no": acc, "source": "UK", "status": "fail",
                             "kind": "", "title": "", "url": "", "file": "",
                             "sha256": "", "bytes": 0,
                             "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S")})
            logger.warning("[%d/%d] %s 失败：%s", i, len(rows), acc, e)

        if i % 10 == 0:
            write_csv(args.manifest, manifest,
                      ["accident_no", "source", "status", "kind", "title", "url",
                       "file", "sha256", "bytes", "fetched_at"])

    write_csv(args.manifest, manifest,
              ["accident_no", "source", "status", "kind", "title", "url",
               "file", "sha256", "bytes", "fetched_at"])
    logger.info("完成：成功 %d，失败 %d，manifest=%s", ok, fail, args.manifest)


if __name__ == "__main__":
    main()

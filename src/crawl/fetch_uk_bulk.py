# -*- coding: utf-8 -*-
"""按关键词批量抓取英国 MAIB 碰撞类报告（不依赖 seed 编号匹配）。

关键词 collision / contact，取回报告页，下载 PDF 附件。

用法：
    python src/crawl/fetch_uk_bulk.py --keywords collision,contact --max 120
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

from common import DATA, ensure_dir, setup_logging, write_csv

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
SEARCH = ("https://www.gov.uk/api/search.json?filter_organisations="
          "marine-accident-investigation-branch&filter_format=maib_report"
          "&count=100&start={start}&q={q}")


def http_get(url: str, timeout: int = 45) -> bytes:
    time.sleep(random.uniform(1.0, 2.2))
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept-Language": "en-GB,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def collect(keyword: str) -> list[dict]:
    out, start = [], 0
    while True:
        url = SEARCH.format(start=start, q=urllib.parse.quote(keyword))
        data = json.loads(http_get(url).decode("utf-8", "ignore"))
        results = data.get("results", [])
        out.extend(results)
        total = data.get("total", 0)
        start += len(results)
        if not results or start >= total:
            break
    return out


def strip_html(html: str) -> str:
    html = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<(p|div|br|li|h\d)[^>]*>", "\n", html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"[ \t]+", " ", text)
    return "\n".join(l.strip() for l in text.split("\n") if l.strip())


def find_pdf(page_url: str, html: str):
    for link in re.findall(r'href="([^"]+\.pdf[^"]*)"', html, re.I):
        full = urllib.parse.urljoin(page_url, link)
        if "assets.publishing.service.gov.uk" in full or "/media/" in full:
            return full
    return None


def main():
    ap = argparse.ArgumentParser(description="按关键词抓 MAIB 报告")
    ap.add_argument("--keywords", default="collision,contact")
    ap.add_argument("--max", type=int, default=120)
    ap.add_argument("--out", default=str(DATA / "pdf" / "uk"))
    ap.add_argument("--manifest", default=str(DATA / "manifest_uk.csv"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    logger = setup_logging("fetch_uk_bulk", DATA / "logs" / "fetch_uk_bulk.log")
    ensure_dir(args.out)

    seen, items = set(), []
    for kw in args.keywords.split(","):
        got = collect(kw.strip())
        logger.info("关键词 %s：%d 条", kw, len(got))
        for r in got:
            link = r.get("link")
            if link and link not in seen:
                seen.add(link)
                items.append(r)
    logger.info("去重后 %d 篇，最多抓 %d 篇", len(items), args.max)
    items = items[: args.max]

    manifest, ok, fail = [], 0, 0
    for i, r in enumerate(items, 1):
        slug = r["link"].rstrip("/").split("/")[-1]
        page_url = "https://www.gov.uk" + r["link"]
        pdf_path = Path(args.out) / f"{slug[:90]}.pdf"
        rec = {"accident_no": slug, "source": "UK", "status": "", "kind": "",
               "title": r.get("title", ""), "url": page_url, "file": "",
               "sha256": "", "bytes": 0,
               "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        try:
            if pdf_path.exists() and pdf_path.stat().st_size > 1000:
                rec.update({"status": "ok", "kind": "pdf",
                            "file": str(pdf_path.relative_to(DATA)),
                            "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
                            "bytes": pdf_path.stat().st_size})
                manifest.append(rec)
                ok += 1
                continue
            html = http_get(page_url).decode("utf-8", "ignore")
            pdf = find_pdf(page_url, html)
            if args.dry_run:
                logger.info("[%d] %s | %s", i, slug[:50], pdf or "网页正文")
                continue
            if pdf:
                blob = http_get(pdf)
                if blob[:4] != b"%PDF":
                    raise RuntimeError("不是 PDF")
                pdf_path.write_bytes(blob)
                rec.update({"status": "ok", "kind": "pdf",
                            "file": str(pdf_path.relative_to(DATA)),
                            "sha256": hashlib.sha256(blob).hexdigest(),
                            "bytes": len(blob)})
            else:
                text = strip_html(html)
                if len(text) < 800:
                    raise RuntimeError(f"网页正文过短（{len(text)} 字符）")
                txt_path = pdf_path.with_suffix(".txt")
                txt_path.write_text(text, encoding="utf-8")
                rec.update({"status": "ok", "kind": "html",
                            "file": str(txt_path.relative_to(DATA)),
                            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                            "bytes": len(text)})
            ok += 1
            logger.info("[%d/%d] %s  %s  %d KB", i, len(items), slug[:46],
                        rec["kind"], rec["bytes"] // 1024)
        except Exception as e:  # noqa: BLE001
            rec["status"] = "fail"
            fail += 1
            logger.warning("[%d/%d] %s 失败：%s", i, len(items), slug[:40], e)
        manifest.append(rec)
        if i % 10 == 0:
            write_csv(args.manifest, manifest,
                      ["accident_no", "source", "status", "kind", "title", "url",
                       "file", "sha256", "bytes", "fetched_at"])

    write_csv(args.manifest, manifest,
              ["accident_no", "source", "status", "kind", "title", "url",
               "file", "sha256", "bytes", "fetched_at"])
    logger.info("完成：成功 %d，失败 %d", ok, fail)


if __name__ == "__main__":
    main()

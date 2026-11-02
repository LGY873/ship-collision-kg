# -*- coding: utf-8 -*-
"""S1-3 / S1-4：按种子表抓取事故报告 PDF。

策略（按优先级）：
  1) seed.csv 里已有 report_url 的，直接下；
  2) 美国：拼 NTSB 案件页 https://www.ntsb.gov/investigations/Pages/{accident_no}.aspx，
     从页面里找第一个 .pdf 链接；
  3) 英国：先查 gov.uk 搜索 API（公开接口），拿到报告页，再找附件 PDF；
  4) 都失败的，标记 missing，留给人工补（--urls 传入手工映射）。

用法：
    python src/crawl/fetch_reports.py --limit 5 --dry-run      # 先试 5 条，只看解析出的 URL
    python src/crawl/fetch_reports.py --source UK --limit 20
    python src/crawl/fetch_reports.py                          # 全量（可断点续跑）

注意：真正跑之前务必先用 --limit 3 验证 URL 规则是否仍然有效；
      站点改版是常态，改版后只需改 resolve_* 两个函数。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import (DATA, ensure_dir, iter_csv, normalize_id, safe_filename,
                    setup_logging, write_csv)

UA = "Xijing-University-BSc-Research/1.0 (academic use; contact: student@example.edu)"
MIN_INTERVAL = 1.5


def http_get(url: str, timeout: int = 40, retries: int = 3) -> bytes:
    last = None
    for attempt in range(retries):
        time.sleep(MIN_INTERVAL + random.uniform(0, 1.2))
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/pdf,application/json;q=0.9,*/*;q=0.8",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 ** attempt * 2)
    raise RuntimeError(f"GET failed: {url} ({last})")


def find_pdfs(html: str, base: str) -> list[str]:
    links = re.findall(r'href="([^"]+\.pdf[^"]*)"', html, flags=re.I)
    out = []
    for link in links:
        full = urllib.parse.urljoin(base, link)
        if full not in out:
            out.append(full)
    return out


def resolve_us(accident_no: str, logger) -> str | None:
    """NTSB 案件页 -> PDF。accident_no 形如 DCA15LM023。"""
    if not accident_no:
        return None
    page = f"https://www.ntsb.gov/investigations/Pages/{accident_no}.aspx"
    try:
        html = http_get(page).decode("utf-8", "ignore")
    except Exception:
        return None
    pdfs = find_pdfs(html, page)
    # 优先取调查报告（文件名含 MAR / MIR / Report）
    for p in pdfs:
        if re.search(r"(MAR|MIR|report)", p, flags=re.I):
            return p
    return pdfs[0] if pdfs else None


def resolve_uk(accident_no: str, logger) -> str | None:
    """gov.uk 搜索 API -> 报告页 -> 附件 PDF。accident_no 形如 NO 12/2018。"""
    if not accident_no:
        return None
    q = urllib.parse.quote(accident_no)
    api = ("https://www.gov.uk/api/search.json?filter_organisations="
           "marine-accident-investigation-branch&count=5&q=" + q)
    try:
        data = json.loads(http_get(api).decode("utf-8", "ignore"))
    except Exception:
        return None
    results = data.get("results") or []
    if not results:
        return None
    page = "https://www.gov.uk" + results[0]["link"]
    try:
        html = http_get(page).decode("utf-8", "ignore")
    except Exception:
        return None
    pdfs = find_pdfs(html, page)
    return pdfs[0] if pdfs else page  # 没有 PDF 时退回网页正文


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["accident_no"]: r for r in csv.DictReader(f)}


def save_manifest(path: Path, rows: dict):
    fields = ["accident_no", "source", "status", "url", "pdf_path", "sha256",
              "bytes", "fetched_at", "note"]
    write_csv(path, list(rows.values()), fields)


def main():
    ap = argparse.ArgumentParser(description="抓取海事事故报告 PDF")
    ap.add_argument("--seed", default=str(DATA / "seed" / "seed.csv"))
    ap.add_argument("--out", default=str(DATA / "pdf"))
    ap.add_argument("--manifest", default=str(DATA / "manifest.csv"))
    ap.add_argument("--source", choices=["US", "UK"], help="只跑某一国")
    ap.add_argument("--limit", type=int, default=0, help="最多处理多少条（调试用）")
    ap.add_argument("--dry-run", action="store_true", help="只解析 URL，不下载")
    ap.add_argument("--urls", help="手工 URL 表（accident_no,url），优先使用")
    args = ap.parse_args()

    logger = setup_logging("fetch", DATA / "logs" / "fetch.log")
    seed = list(iter_csv(args.seed))
    if args.source:
        seed = [r for r in seed if r["country"] == args.source]
    if args.limit:
        seed = seed[: args.limit]
    logger.info("待处理 %d 条", len(seed))

    manual = {}
    if args.urls and Path(args.urls).exists():
        manual = {r["accident_no"]: r["url"] for r in iter_csv(args.urls) if r.get("url")}

    manifest = load_manifest(Path(args.manifest))
    ensure_dir(args.out)
    stats = {"ok": 0, "skip": 0, "fail": 0, "missing": 0}

    for i, row in enumerate(seed, 1):
        acc = normalize_id(row.get("accident_no")) or row.get("accident_key", "")
        if manifest.get(acc, {}).get("status") == "ok":
            stats["skip"] += 1
            continue

        url = row.get("report_url") or manual.get(acc) or ""
        if not url:
            if row["country"] == "US":
                url = resolve_us(acc, logger) or ""
            elif row["country"] == "UK":
                url = resolve_uk(acc, logger) or ""
        if not url:
            manifest[acc] = {"accident_no": acc, "source": row["country"],
                             "status": "missing", "url": "", "pdf_path": "",
                             "sha256": "", "bytes": 0,
                             "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                             "note": "no url resolved; add to urls.csv manually"}
            stats["missing"] += 1
            logger.warning("[%d/%d] %s 未解析到 URL", i, len(seed), acc)
            continue

        if args.dry_run:
            logger.info("[%d/%d] %s -> %s", i, len(seed), acc, url)
            continue

        try:
            blob = http_get(url)
            if blob[:4] != b"%PDF":
                # 网页正文兜底
                txt_path = ensure_dir(Path(args.out) / row["country"].lower()) / f"{safe_filename(acc)}.html"
                txt_path.write_bytes(blob)
                manifest[acc] = {"accident_no": acc, "source": row["country"],
                                 "status": "html", "url": url, "pdf_path": str(txt_path),
                                 "sha256": hashlib.sha256(blob).hexdigest(),
                                 "bytes": len(blob),
                                 "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                 "note": "not a PDF"}
                stats["ok"] += 1
                logger.info("[%d/%d] %s -> HTML 兜底", i, len(seed), acc)
                continue

            pdf_dir = ensure_dir(Path(args.out) / row["country"].lower())
            pdf_path = pdf_dir / f"{safe_filename(acc)}.pdf"
            pdf_path.write_bytes(blob)
            manifest[acc] = {"accident_no": acc, "source": row["country"],
                             "status": "ok", "url": url, "pdf_path": str(pdf_path),
                             "sha256": hashlib.sha256(blob).hexdigest(),
                             "bytes": len(blob),
                             "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                             "note": ""}
            stats["ok"] += 1
            logger.info("[%d/%d] %s -> %s (%d KB)", i, len(seed), acc,
                        pdf_path.name, len(blob) // 1024)
        except Exception as e:  # noqa: BLE001
            manifest[acc] = {"accident_no": acc, "source": row["country"],
                             "status": f"fail", "url": url, "pdf_path": "",
                             "sha256": "", "bytes": 0,
                             "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                             "note": str(e)[:200]}
            stats["fail"] += 1
            logger.error("[%d/%d] %s 失败：%s", i, len(seed), acc, e)

        if i % 10 == 0:
            save_manifest(Path(args.manifest), manifest)

    save_manifest(Path(args.manifest), manifest)
    total = sum(stats.values())
    logger.info("完成 %d 条：ok=%d skip=%d fail=%d missing=%d",
                total, stats["ok"], stats["skip"], stats["fail"], stats["missing"])
    if total:
        logger.info("成功率 %.1f%%（ok / (ok+fail+missing)）",
                    100.0 * stats["ok"] / max(1, stats["ok"] + stats["fail"] + stats["missing"]))


if __name__ == "__main__":
    main()

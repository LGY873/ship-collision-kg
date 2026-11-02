# -*- coding: utf-8 -*-
"""抓取中国海事局碰撞/触碰事故调查报告。

数据来源：https://www.msa.gov.cn/page/sgdcbg/list.jhtml
参数 articleOrigin = 直属海事局名称，返回 JSON（articleTitle / url / articleAbstract）。
筛出标题含“碰撞/触碰”的报告，进入文章页，取 PDF 附件。

用法：
    python src/crawl/fetch_cn.py --limit 5 --dry-run
    python src/crawl/fetch_cn.py
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
BASE = "https://www.msa.gov.cn"
LIST_API = BASE + "/page/sgdcbg/list.jhtml"

BUREAUS = ["上海海事局", "天津海事局", "辽宁海事局", "河北海事局", "山东海事局",
           "浙江海事局", "福建海事局", "广东海事局", "广西海事局", "海南海事局",
           "长江海事局", "江苏海事局", "黑龙江海事局", "深圳海事局", "连云港海事局"]
KEYWORDS = ("碰撞", "触碰")


def http_get(url: str, timeout: int = 45, data: bytes | None = None) -> bytes:
    time.sleep(random.uniform(1.0, 2.0))
    headers = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9", "Referer": BASE}
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["X-Requested-With"] = "XMLHttpRequest"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def list_bureau(bureau: str, page: int, size: int = 20):
    data = urllib.parse.urlencode({"articleOrigin": bureau, "pageNum": page,
                                   "pageSize": size}).encode()
    raw = http_get(LIST_API, data=data)
    return json.loads(raw.decode("utf-8", "ignore"))


def main():
    ap = argparse.ArgumentParser(description="抓取中国海事局碰撞事故报告")
    ap.add_argument("--out", default=str(DATA / "pdf" / "cn"))
    ap.add_argument("--manifest", default=str(DATA / "manifest_cn.csv"))
    ap.add_argument("--max-per-bureau", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    logger = setup_logging("fetch_cn", DATA / "logs" / "fetch_cn.log")
    ensure_dir(args.out)

    # 1) 抓列表并筛选
    items, seen = [], set()
    for bureau in BUREAUS:
        got = total = 0
        for page in range(1, args.max_per_bureau + 1):
            try:
                d = list_bureau(bureau, page)
            except Exception as e:  # noqa: BLE001
                logger.warning("%s 第 %d 页失败：%s", bureau, page, e)
                break
            total = d.get("total", 0)
            rows = d.get("list") or []
            for it in rows:
                title = (it.get("articleTitle") or "").strip()
                url = it.get("url") or ""
                if not url or url in seen:
                    continue
                if not any(k in title for k in KEYWORDS):
                    continue
                seen.add(url)
                items.append({"bureau": bureau, "title": title,
                              "url": urllib.parse.urljoin(BASE, url),
                              "abstract": it.get("articleAbstract") or ""})
                got += 1
            if len(rows) < 20 or page * 20 >= total:
                break
        logger.info("%-8s 共 %d 条，命中碰撞/触碰 %d 条", bureau, total, got)

    if args.limit:
        items = items[: args.limit]
    logger.info("合计命中 %d 篇", len(items))

    # 2) 逐篇下 PDF
    manifest, ok, fail = [], 0, 0
    for i, it in enumerate(items, 1):
        aid = hashlib.md5(it["url"].encode()).hexdigest()[:12]
        pdf_path = Path(args.out) / f"cn_{aid}.pdf"
        rec = {"accident_no": f"cn_{aid}", "source": "CN", "status": "", "kind": "",
               "title": it["title"], "url": it["url"], "bureau": it["bureau"],
               "file": "", "sha256": "", "bytes": 0,
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
            page = http_get(it["url"]).decode("utf-8", "ignore")
            pdfs = re.findall(r'href="([^"]+\.pdf)"', page, re.I)
            if not pdfs:
                raise RuntimeError("文章页无 PDF")
            pdf_url = urllib.parse.urljoin(it["url"], pdfs[0])
            if args.dry_run:
                logger.info("[%d] %s | %s", i, it["title"][:36], pdf_url)
                continue
            blob = http_get(pdf_url)
            if blob[:4] != b"%PDF":
                raise RuntimeError("附件不是 PDF")
            pdf_path.write_bytes(blob)
            rec.update({"status": "ok", "kind": "pdf",
                        "file": str(pdf_path.relative_to(DATA)),
                        "sha256": hashlib.sha256(blob).hexdigest(),
                        "bytes": len(blob)})
            ok += 1
            logger.info("[%d/%d] %s  %d KB", i, len(items), it["title"][:34], len(blob) // 1024)
        except Exception as e:  # noqa: BLE001
            rec["status"] = "fail"
            fail += 1
            logger.warning("[%d/%d] %s 失败：%s", i, len(items), it["title"][:30], e)
        manifest.append(rec)
        if i % 10 == 0:
            write_csv(args.manifest, manifest,
                      ["accident_no", "source", "status", "kind", "title", "url",
                       "bureau", "file", "sha256", "bytes", "fetched_at"])

    write_csv(args.manifest, manifest,
              ["accident_no", "source", "status", "kind", "title", "url",
               "bureau", "file", "sha256", "bytes", "fetched_at"])
    logger.info("完成：成功 %d，失败 %d", ok, fail)


if __name__ == "__main__":
    main()

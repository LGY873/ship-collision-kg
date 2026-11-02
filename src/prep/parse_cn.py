# -*- coding: utf-8 -*-
"""解析中国海事局事故报告 PDF（中文）。

要点：
  * 中文报告没有 Synopsis/Analysis 这类英文小标题，改用「一、事故概况」这类中文标题；
  * 水印行（“此报告仅用于安全参考…”）逐个删除；
  * 只保留文字量足够的 PDF，扫描件单独记录。

用法：
    python src/prep/parse_cn.py
"""
from __future__ import annotations

import hashlib
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import DATA, iter_csv, setup_logging, write_csv, write_jsonl
from clean_text import clean_lines, join_blocks

CN_HEAD = re.compile(r"^\s*[一二三四五六七八九十]+[、.．]\s*(.{2,20})\s*$")
# 抽取时重点取这几节
KEEP_KEYS = ("事故概况", "事故经过", "事故原因", "原因分析", "责任认定",
             "调查结论", "事故损失", "重要因素", "事实认定")
WATERMARK = re.compile(r"(仅用于安全参考|不作其他用途|内部资料|注意保密)")


def split_cn_sections(text: str) -> dict:
    lines = text.split("\n")
    marks = []
    for i, ln in enumerate(lines):
        m = CN_HEAD.match(ln.strip())
        if m:
            marks.append((i, m.group(1).strip()))
    if not marks:
        return {"_full": text}
    out = {}
    if marks[0][0] > 0:
        out["_preamble"] = "\n".join(lines[: marks[0][0]]).strip()
    for idx, (ln_no, title) in enumerate(marks):
        end = marks[idx + 1][0] if idx + 1 < len(marks) else len(lines)
        body = "\n".join(lines[ln_no + 1: end]).strip()
        out[title] = out.get(title, "") + ("\n" if title in out else "") + body
    return out


def drop_watermark(lines: list[str]) -> list[str]:
    """重复出现超过 8 次的行视为水印。"""
    cnt = Counter(l.strip() for l in lines if l.strip())
    return [l for l in lines if not (l.strip() and cnt[l.strip()] > 8 and WATERMARK.search(l))]


def build(manifest_row: dict, text: str, path: Path) -> dict:
    lines, hits = clean_lines(text)
    lines = drop_watermark(lines)
    cleaned = join_blocks(lines)
    sections = split_cn_sections("\n".join(lines))

    PRIORITY = ("事故原因", "原因分析", "责任认定", "调查结论", "事故经过",
                "重要因素", "事实认定", "事故损失", "事故概况")

    def prio(k: str) -> int:
        for i, key in enumerate(PRIORITY):
            if key in k:
                return i
        return 99

    chosen = sorted((prio(k), k, v) for k, v in sections.items()
                    if not k.startswith("_") and any(x in k for x in KEEP_KEYS))
    body = "\n\n".join(f"## {k}\n{v}" for _, k, v in chosen) or cleaned
    extraction = body[:5000]

    title = manifest_row.get("title", "")
    return {
        "doc_id": f"cn_{path.stem.replace('cn_', '')}",
        "corpus_type": "fulltext",
        "source": "CN",
        "country": "CN",
        "accident_key": path.stem,
        "accident_no": path.stem,
        "accident_type": "collision" if "碰撞" in title else ("contact" if "触碰" in title else "other"),
        "collision_tier": "A" if "碰撞" in title else "B",
        "vessels": [],
        "date": "",
        "location": "",
        "lat": "",
        "lon": "",
        "lang": "zh",
        "engine": "pymupdf",
        "title": title,
        "text": extraction,
        "sections": {k: v for k, v in sections.items() if not k.startswith("_")},
        "sectioned": any(not k.startswith("_") for k in sections),
        "n_chars": len(cleaned),
        "n_tokens": len(extraction),
        "clean_hits": hits,
        "url": manifest_row.get("url", ""),
        "sha256": hashlib.sha256(cleaned.encode("utf-8")).hexdigest(),
        "split": "",
    }


def main():
    logger = setup_logging("parse_cn", DATA / "logs" / "parse_cn.log")
    import pymupdf

    rows = list(iter_csv(DATA / "manifest_cn.csv"))
    by_name = {}
    for r in rows:
        if r.get("file"):
            by_name[Path(r["file"]).stem] = r

    records, report = [], []
    seen_hash = set()
    for f in sorted((DATA / "pdf" / "cn").glob("*.pdf")):
        try:
            doc = pymupdf.open(str(f))
            text = "\n".join(p.get_text("text") for p in doc)
            pages = doc.page_count
            doc.close()
        except Exception as e:  # noqa: BLE001
            logger.warning("打开失败 %s：%s", f.name, e)
            continue

        row = by_name.get(f.stem, {})
        digest = hashlib.sha256(f.read_bytes()).hexdigest()
        dup = digest in seen_hash
        seen_hash.add(digest)

        status = "ok"
        if len(text.strip()) < 800:
            status = "scanned"
        elif dup:
            status = "duplicate"

        report.append({"file": f.name, "pages": pages, "chars": len(text),
                       "status": status, "title": (row.get("title") or "")[:60]})
        if status != "ok":
            logger.warning("%s -> %s（%d 字符）", f.name, status, len(text))
            continue

        rec = build(row, text, f)
        records.append(rec)
        logger.info("%-40s %6d 字符  分节=%s  %s", f.name, rec["n_chars"],
                    rec["sectioned"], (row.get("title") or "")[:30])

    n = write_jsonl(DATA / "corpus" / "corpus_cn.jsonl", records)
    write_csv(DATA / "reports" / "parse_report_cn.csv", report,
              ["file", "pages", "chars", "status", "title"])
    lens = sorted(r["n_chars"] for r in records)
    logger.info("可用 %d 篇；跳过 %d 篇（扫描/重复）", n, len(report) - n)
    if lens:
        logger.info("字符数 min=%d 中位=%d max=%d", lens[0], lens[len(lens) // 2], lens[-1])


if __name__ == "__main__":
    main()

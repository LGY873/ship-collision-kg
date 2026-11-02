# -*- coding: utf-8 -*-
"""S2-1：PDF（以及网页/文本）解析为语料。

三级兜底：pdfplumber → PyMuPDF → 跳过并标记 needs_ocr。
同时支持 .txt / .html，方便在没装 PDF 库时先跑通链路。

用法：
    python src/prep/parse_pdf.py --pdf-dir data/pdf --seed data/seed/seed.csv \
        --out data/corpus/corpus_pdf.jsonl --include-txt
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import (DATA, iter_csv, normalize_id, setup_logging, write_jsonl)
from clean_text import clean_lines, join_blocks
from segment import extract_for_extraction, split_sections

HTML_TAG = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.S | re.I)


def extract_text(path: Path, logger) -> tuple[str, str]:
    """返回 (文本, 解析引擎)"""
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore"), "text"
    if suffix in (".html", ".htm"):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        raw = HTML_TAG.sub(" ", raw)
        return re.sub(r"[ \t]+", " ", raw), "html"
    if suffix == ".pdf":
        try:
            import pdfplumber  # type: ignore
            parts = []
            with pdfplumber.open(str(path)) as pdf:
                for page in pdf.pages:
                    parts.append(page.extract_text() or "")
            txt = "\n".join(parts)
            if len(txt.strip()) >= 800:
                return txt, "pdfplumber"
        except ImportError:
            logger.warning("未安装 pdfplumber，尝试 PyMuPDF")
        except Exception as e:  # noqa: BLE001
            logger.warning("pdfplumber 失败 %s：%s", path.name, e)
        try:
            import fitz  # type: ignore
            doc = fitz.open(str(path))
            txt = "\n".join(page.get_text() for page in doc)
            doc.close()
            return txt, "pymupdf"
        except ImportError:
            pass
        except Exception as e:  # noqa: BLE001
            logger.warning("PyMuPDF 失败 %s：%s", path.name, e)
        return "", "failed"
    return "", "unsupported"


def build_record(seed_row: dict, text: str, engine: str, doc_id: str) -> dict:
    lines, hits = clean_lines(text)
    cleaned = join_blocks(lines)
    # 分节必须在保留行结构的文本上做，否则标题会被合并进正文
    sections = split_sections("\n".join(lines))
    extraction_text = extract_for_extraction(sections)
    # MAB 简报没有 Factual/Analysis 小标题，按标题抽会只剩 Probable Cause 一段。
    # 覆盖不足 40% 时回退到全文（截断到模型可承受的长度）。
    if len(extraction_text) < 0.4 * len(cleaned):
        extraction_text = cleaned[:12000]
        sections["_fallback_fulltext"] = True
    vessels = [v for v in (seed_row.get("vessels") or "").split("|") if v]
    return {
        "doc_id": doc_id,
        "corpus_type": "fulltext",
        "source": seed_row.get("source", ""),
        "country": seed_row.get("country", ""),
        "accident_key": seed_row.get("accident_key", ""),
        "accident_no": normalize_id(seed_row.get("accident_no")) or seed_row.get("accident_key", ""),
        "accident_type": seed_row.get("accident_type", ""),
        "collision_tier": seed_row.get("collision_tier", ""),
        "vessels": vessels,
        "date": seed_row.get("date", ""),
        "location": seed_row.get("location", ""),
        "lat": seed_row.get("lat", ""),
        "lon": seed_row.get("lon", ""),
        "lang": "en",
        "engine": engine,
        "text": extraction_text,
        "sections": {k: v for k, v in sections.items() if not k.startswith("_")},
        "sectioned": bool(sections.get("sectioned")),
        "used_fallback": bool(sections.get("_fallback_fulltext")),
        "n_chars": len(cleaned),
        "n_tokens": len(extraction_text) // 4,
        "clean_hits": hits,
        "url": seed_row.get("report_url", ""),
        "sha256": hashlib.sha256(cleaned.encode("utf-8")).hexdigest(),
        "split": "",
    }


def main():
    ap = argparse.ArgumentParser(description="PDF/HTML/TXT -> corpus.jsonl")
    ap.add_argument("--pdf-dir", default=str(DATA / "pdf"))
    ap.add_argument("--seed", default=str(DATA / "seed" / "seed.csv"))
    ap.add_argument("--out", default=str(DATA / "corpus" / "corpus_pdf.jsonl"))
    ap.add_argument("--include-txt", action="store_true", help="同时处理 .txt/.html")
    args = ap.parse_args()

    logger = setup_logging("parse", DATA / "logs" / "parse.log")
    stem2seed = {}
    for r in iter_csv(args.seed):
        stem2seed[r["accident_file"]] = r

    files = sorted(Path(args.pdf_dir).rglob("*"))
    exts = {".pdf"}
    if args.include_txt:
        exts |= {".txt", ".html", ".htm"}
    files = [f for f in files if f.is_file() and f.suffix.lower() in exts]
    logger.info("待解析文件 %d 个", len(files))

    records, stats = [], {"ok": 0, "empty": 0, "no_seed": 0}
    for f in files:
        row = stem2seed.get(f.stem)
        if not row:
            stats["no_seed"] += 1
            logger.warning("跳过（种子表无对应记录）：%s", f.name)
            continue
        text, engine = extract_text(f, logger)
        if len(text.strip()) < 200:
            stats["empty"] += 1
            logger.warning("正文过短（可能是扫描件）：%s", f.name)
            continue
        rec = build_record(row, text, engine, doc_id=f"{row['source'].lower()}_{f.stem}")
        records.append(rec)
        stats["ok"] += 1
        logger.info("%-40s %-11s %6d 字符  分节=%s", f.name, engine,
                    rec["n_chars"], rec["sectioned"])

    write_jsonl(args.out, records)
    logger.info("完成：ok=%d empty=%d no_seed=%d -> %s",
                stats["ok"], stats["empty"], stats["no_seed"], args.out)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""按“一批编号命名的 PDF”批量解析，并对齐种子表。

真实数据的两种情况都要覆盖：
  1) 新报告（2015 年后）：首页写 “Accident no. DCA15LM023”；
  2) 老报告（MAR/MIR）：没有 DCA 号，只有报告号 “NTSB/MAR-11/04”，
     而种子表里这一列正好也是 MAR-11/04。

匹配优先级：正文案件号 -> 正文报告号 -> 文件名。

用法：
    python src/prep/parse_batch.py --pdf-dir "D:\\报告" --limit 20
    python src/prep/parse_batch.py --pdf-dir "D:\\报告"
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import (DATA, iter_csv, setup_logging, write_csv, write_jsonl)
from parse_pdf import build_record

CASE_RES = [
    r"\b(DCA\d{2}[A-Z]{2}\d{3})\b",             # DCA15LM023
    r"\b([A-Z]{3}-\d{2}-\d{2})\b",              # MAB-19-01 早期写法
]
REPORT_RES = [
    r"\b((?:MAR|MAB|MIR|MSR|RIR|AAR|AIR|ASR)[-/ ]?\d{2}[-/ ]\d{2})\b",
]
COLLISION_WORDS = ("collision", "allision", "contact", "struck", "collided")


def norm_key(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def extract_text_pdf(path: Path, logger):
    try:
        import pymupdf  # type: ignore
    except ImportError:
        try:
            import fitz as pymupdf  # type: ignore
        except ImportError:
            return "", 0, "no_lib"
    try:
        doc = pymupdf.open(str(path))
    except Exception as e:  # noqa: BLE001
        logger.warning("打开失败 %s：%s", path.name, e)
        return "", 0, "open_failed"
    pages = doc.page_count
    text = "\n".join(page.get_text("text") for page in doc)
    doc.close()
    return text, pages, "pymupdf"


def head_ids(text: str, head_chars: int = 8000):
    head = text[:head_chars]
    case_ids, report_ids = [], []
    for pat in CASE_RES:
        case_ids += re.findall(pat, head, flags=re.I)
    for pat in REPORT_RES:
        report_ids += re.findall(pat, head, flags=re.I)
    dedup = lambda xs: list(dict.fromkeys(x.strip() for x in xs))
    return dedup(case_ids), dedup(report_ids)


def main():
    ap = argparse.ArgumentParser(description="批量解析目录下的 PDF 并对齐种子表")
    ap.add_argument("--pdf-dir", required=True)
    ap.add_argument("--seed", default=str(DATA / "seed" / "seed.csv"))
    ap.add_argument("--out", default=str(DATA / "corpus" / "corpus_us_full.jsonl"))
    ap.add_argument("--report", default=str(DATA / "reports" / "parse_report.csv"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--min-chars", type=int, default=800)
    ap.add_argument("--country", default="US",
                    help="只与这个国家的种子行对齐，避免数字编号串到别国")
    args = ap.parse_args()

    logger = setup_logging("parse_batch", DATA / "logs" / "parse_batch.log")
    seed_rows = list(iter_csv(args.seed))
    by_key = {norm_key(r["accident_no"]): r for r in seed_rows
              if r.get("accident_no") and r.get("country") == args.country}

    files = sorted(Path(args.pdf_dir).rglob("*.pdf"),
                   key=lambda p: (len(p.stem), p.stem, str(p.parent)))
    if args.limit:
        files = files[: args.limit]
    logger.info("PDF %d 个；种子 %d 行（唯一案件号 %d）", len(files), len(seed_rows), len(by_key))

    records, report = [], []
    stats = {"seed": 0, "extra": 0, "scanned": 0, "unmatched": 0}
    matched_keys = set()

    for i, f in enumerate(files, 1):
        text, pages, engine = extract_text_pdf(f, logger)
        n_chars = len(text)
        case_ids, report_ids = head_ids(text) if text.strip() else ([], [])

        rid, row, method = "", None, ""
        for cand in case_ids:
            if norm_key(cand) in by_key:
                rid, row, method = norm_key(cand), by_key[norm_key(cand)], "case_no"
                break
        if not rid:
            for cand in report_ids:
                if norm_key(cand) in by_key:
                    rid, row, method = norm_key(cand), by_key[norm_key(cand)], "report_no"
                    break
        if not rid:
            if norm_key(f.stem) in by_key:
                rid, row, method = norm_key(f.stem), by_key[norm_key(f.stem)], "filename"
        if not rid:
            # 不在种子表里也算解析成功，只是 scope=extra
            rid = norm_key(case_ids[0]) if case_ids else (
                norm_key(report_ids[0]) if report_ids else "")
            method = "case_no_unknown" if case_ids else (
                "report_no_unknown" if report_ids else "")

        head_text = text[:3000].lower()
        collision_like = any(w in head_text for w in COLLISION_WORDS)

        if n_chars < args.min_chars:
            status = "scanned"
            stats["scanned"] += 1
        elif row is not None:
            status = "seed"
            stats["seed"] += 1
            matched_keys.add(rid)
        elif rid:
            status = "extra"
            stats["extra"] += 1
        else:
            status = "unmatched"
            stats["unmatched"] += 1

        report.append({
            "file": str(f.relative_to(args.pdf_dir)).replace("\\", "/"),
            "pages": pages, "chars": n_chars, "engine": engine,
            "status": status, "match": method,
            "key": rid,
            "seed_accident_no": (row or {}).get("accident_no", ""),
            "seed_tier": (row or {}).get("collision_tier", ""),
            "seed_vessels": (row or {}).get("vessels", "")[:60],
            "collision_like": "1" if collision_like else "0",
            "title": next((ln.strip() for ln in text.split("\n") if ln.strip()), "")[:90],
        })

        if status in ("seed", "extra") and text.strip():
            acc_no = (row or {}).get("accident_no") or rid
            key = norm_key(acc_no)
            meta = row or {}
            rec = build_record(meta, text, engine, doc_id=f"us_{key or norm_key(f.stem)}")
            rec.update({
                "accident_no": acc_no,
                "in_seed": 1 if row is not None else 0,
                "collision_like": 1 if collision_like else 0,
                "pdf_file": str(f.relative_to(args.pdf_dir)).replace("\\", "/"),
                "pages": pages,
                "matched_by": method,
                "corpus_type": "fulltext",
            })
            records.append(rec)

        if i % 50 == 0 or i == len(files):
            logger.info("[%d/%d] seed=%d extra=%d scanned=%d unmatched=%d",
                        i, len(files), stats["seed"], stats["extra"],
                        stats["scanned"], stats["unmatched"])

    # 同一事故多份文件：保留字符最多的
    best = {}
    for r in records:
        k = norm_key(r["accident_no"])
        if k not in best or r["n_chars"] > best[k]["n_chars"]:
            best[k] = r
    records = list(best.values())

    write_csv(args.report, report,
              ["file", "pages", "chars", "engine", "status", "match", "key",
               "seed_accident_no", "seed_tier", "seed_vessels", "collision_like", "title"])
    n = write_jsonl(args.out, records)

    lens = sorted(r["n_chars"] for r in records)
    seg = sum(1 for r in records if r["sectioned"])
    in_seed_n = sum(1 for r in records if r["in_seed"])
    extra_n = len(records) - in_seed_n
    extra_coll = sum(1 for r in records if not r["in_seed"] and r["collision_like"])
    logger.info("可解析 %d 篇（种子内 %d / 种子外 %d，其中标题像碰撞的 %d）",
                n, in_seed_n, extra_n, extra_coll)
    logger.info("扫描件/过短 %d；无编号未匹配 %d", stats["scanned"], stats["unmatched"])
    if lens:
        logger.info("字符数 min=%d 中位=%d max=%d；可自动分节 %d 篇（%.0f%%）",
                    lens[0], lens[len(lens) // 2], lens[-1], seg, 100.0 * seg / len(records))
    logger.info("种子覆盖 %d/%d（%.0f%%）", len(matched_keys), len(by_key),
                100.0 * len(matched_keys) / max(1, len(by_key)))
    logger.info("语料：%s；报告：%s", args.out, args.report)


if __name__ == "__main__":
    main()

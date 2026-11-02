# -*- coding: utf-8 -*-
"""兜底路径 B：没有 PDF 时，用 seed.csv 的字段拼出“事故短文”语料。

这一步的价值有两个：
  1) 让整条链路（语料 -> 划分 -> 抽取 -> 评测 -> 图谱）在第一天就能跑通；
  2) PDF 抓取失败时，实验仍可继续，论文里如实说明数据边界即可。

用法：
    python src/prep/build_corpus_from_fields.py --seed data/seed/seed.csv \
        --out data/corpus/corpus_fields.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import DATA, iter_csv, normalize_id, setup_logging, write_jsonl


def compose(row: dict, max_chars: int = 4000) -> tuple[str, dict]:
    vessels = [v for v in (row.get("vessels") or "").split("|") if v]
    parts, sections = [], {}

    head = f"Collision accident report {row.get('accident_no') or row.get('accident_key')}"
    if row.get("date"):
        head += f", occurred on {row['date']}"
    if row.get("location"):
        head += f", at {row['location']}"
    head += "."
    parts.append(head)
    sections["synopsis"] = head

    if len(vessels) >= 2:
        s = ("Vessels involved: " + "; ".join(vessels) +
             ". The vessels collided in the reported water area.")
        parts.append(s)
        sections["vessels"] = s
    elif vessels:
        s = "Vessel involved: " + vessels[0] + "."
        parts.append(s)
        sections["vessels"] = s

    if row.get("weather"):
        s = "Weather and visibility at the time: " + row["weather"]
        parts.append(s)
        sections["weather"] = s
    if row.get("hydro"):
        s = "Hydrographic and waterway conditions: " + row["hydro"]
        parts.append(s)
        sections["hydro"] = s
    if row.get("risk_factors"):
        s = "Risk and contributing factors identified by the investigation: " + row["risk_factors"]
        parts.append(s)
        sections["analysis"] = s
    if row.get("other_factors"):
        s = "Other contributing factors: " + row["other_factors"]
        parts.append(s)
        sections["analysis"] = sections.get("analysis", "") + " " + s
    if row.get("outcome"):
        s = "Consequences of the accident: " + row["outcome"]
        parts.append(s)
        sections["conclusions"] = s

    text = "\n\n".join(parts)[:max_chars]
    return text, sections


def main():
    ap = argparse.ArgumentParser(description="field-level corpus (path B)")
    ap.add_argument("--seed", default=str(DATA / "seed" / "seed.csv"))
    ap.add_argument("--out", default=str(DATA / "corpus" / "corpus_fields.jsonl"))
    ap.add_argument("--min-chars", type=int, default=120)
    args = ap.parse_args()

    logger = setup_logging("corpus_fields", DATA / "logs" / "corpus_fields.log")
    rows = list(iter_csv(args.seed))
    records, skipped = [], 0
    for r in rows:
        text, sections = compose(r)
        if len(text) < args.min_chars:
            skipped += 1
            continue
        vessels = [v for v in (r.get("vessels") or "").split("|") if v]
        records.append({
            "doc_id": f"{r['source'].lower()}_{r['accident_file']}",
            "corpus_type": "fields",
            "source": r["source"],
            "country": r["country"],
            "accident_key": r["accident_key"],
            "accident_no": normalize_id(r["accident_no"]) or r["accident_key"],
            "accident_type": r["accident_type"],
            "collision_tier": r["collision_tier"],
            "vessels": vessels,
            "date": r["date"],
            "location": r["location"],
            "lat": r["lat"],
            "lon": r["lon"],
            "lang": "en",
            "engine": "fields",
            "text": text,
            "sections": sections,
            "sectioned": True,
            "n_chars": len(text),
            "n_tokens": len(text) // 4,
            "url": r.get("report_url", ""),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "split": "",
        })

    n = write_jsonl(args.out, records)
    lens = sorted(len(r["text"]) for r in records)
    logger.info("写出 %d 篇（跳过 %d 篇过短）", n, skipped)
    if lens:
        logger.info("字符长度：min=%d 中位=%d max=%d", lens[0], lens[len(lens) // 2], lens[-1])


if __name__ == "__main__":
    main()

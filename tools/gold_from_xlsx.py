# -*- coding: utf-8 -*-
"""把标注工作簿转成标准 gold.jsonl，并做一致性检查。

用法：
    python tools/gold_from_xlsx.py --xlsx data/gold/标注工作簿.xlsx \
        --corpus data/corpus/corpus_us_seed_split.jsonl --out data/gold/gold.jsonl
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import DATA, ROOT, read_json, read_jsonl, setup_logging, write_csv, write_jsonl

from openpyxl import load_workbook


def find_span(text: str, needle: str):
    """返回 (start, end)；找不到返回 (-1, -1)。"""
    needle = (needle or "").strip()
    if not needle:
        return -1, -1
    i = text.find(needle)
    if i >= 0:
        return i, i + len(needle)
    low = text.lower().find(needle.lower())
    if low >= 0:
        return low, low + len(needle)
    # 容忍多余空白
    pattern = re.sub(r"\s+", r"\\s+", re.escape(needle))
    m = re.search(pattern, text, flags=re.I)
    if m:
        return m.start(), m.end()
    return -1, -1


def rows_of(ws):
    header = [c.value for c in ws[2]]
    for row in ws.iter_rows(min_row=3, values_only=True):
        if not row or not any(row):
            continue
        yield dict(zip(header, row))


def main():
    ap = argparse.ArgumentParser(description="xlsx -> gold.jsonl")
    ap.add_argument("--xlsx", default=str(DATA / "gold" / "标注工作簿.xlsx"))
    ap.add_argument("--corpus", default=str(DATA / "corpus" / "corpus_us_seed_split.jsonl"))
    ap.add_argument("--out", default=str(DATA / "gold" / "gold.jsonl"))
    ap.add_argument("--problems", default=str(DATA / "gold" / "annotation_problems.csv"))
    args = ap.parse_args()

    logger = setup_logging("gold_from_xlsx", DATA / "logs" / "gold.log")
    onto = read_json(ROOT / "ontology" / "ontology.json")
    corpus = {r["doc_id"]: r for r in read_jsonl(args.corpus)}

    wb = load_workbook(args.xlsx, read_only=True, data_only=True)
    if "实体" not in wb.sheetnames or "关系" not in wb.sheetnames:
        logger.error("工作簿缺少【实体】或【关系】工作表")
        return

    ents_by_doc = defaultdict(list)
    for row in rows_of(wb["实体"]):
        doc = (row.get("doc_id") or "").strip()
        typ = (row.get("实体类型") or "").strip()
        txt = (row.get("实体原文（逐字来自正文）") or "").strip()
        if not doc or not typ or not txt:
            continue
        ents_by_doc[doc].append({"type": typ, "text": txt})

    rels_by_doc = defaultdict(list)
    for row in rows_of(wb["关系"]):
        doc = (row.get("doc_id") or "").strip()
        head = (row.get("头实体原文") or "").strip()
        rel = (row.get("关系类型") or "").strip()
        tail = (row.get("尾实体原文") or "").strip()
        ev = (row.get("证据句（原文照抄）") or "").strip()
        if not doc or not rel:
            continue
        rels_by_doc[doc].append({"head": head, "relation": rel, "tail": tail, "evidence": ev})

    gold, problems = [], []
    stats = Counter()

    for doc_id, ents in ents_by_doc.items():
        src = corpus.get(doc_id)
        if src is None:
            problems.append({"doc_id": doc_id, "stage": "doc", "detail": "语料里没有这篇"})
            continue
        text = src["text"]
        used, out_ents, text2id = {}, [], {}

        for e in ents:
            typ = e["type"]
            if typ not in onto["entities"]:
                problems.append({"doc_id": doc_id, "stage": "entity_type", "detail": typ})
                continue
            start, end = find_span(text, e["text"])
            if start < 0:
                problems.append({"doc_id": doc_id, "stage": "entity_not_found",
                                 "detail": e["text"][:60]})
                stats["entity_missing"] += 1
                continue
            key = (typ, e["text"].lower())
            if key in used:
                continue
            used[key] = True
            eid = f"e{len(out_ents) + 1}"
            text2id.setdefault(e["text"], eid)
            out_ents.append({"id": eid, "type": typ, "text": e["text"],
                             "start": start, "end": end, "attributes": {}})

        out_rels = []
        for r in rels_by_doc.get(doc_id, []):
            rel = r["relation"]
            if rel not in onto["relations"]:
                problems.append({"doc_id": doc_id, "stage": "relation_type", "detail": rel})
                continue
            hid, tid = text2id.get(r["head"]), text2id.get(r["tail"])
            if not hid or not tid:
                problems.append({"doc_id": doc_id, "stage": "relation_endpoint",
                                 "detail": f"{r['head'][:30]} -> {r['tail'][:30]}"})
                stats["rel_missing"] += 1
                continue
            if hid == tid:
                problems.append({"doc_id": doc_id, "stage": "self_loop", "detail": rel})
                continue
            htype = next(x["type"] for x in out_ents if x["id"] == hid)
            ttype = next(x["type"] for x in out_ents if x["id"] == tid)
            spec = onto["relations"][rel]
            if htype not in spec["domain"] or ttype not in spec["range"]:
                problems.append({"doc_id": doc_id, "stage": "domain_range",
                                 "detail": f"{htype}-{rel}->{ttype}"})
                continue
            out_rels.append({"head": hid, "relation": rel, "tail": tid,
                             "evidence": r["evidence"]})
            stats["rel_ok"] += 1

        if not out_ents:
            continue
        stats["docs"] += 1
        stats["entities"] += len(out_ents)
        gold.append({
            "doc_id": doc_id,
            "accident_no": src.get("accident_no", ""),
            "country": src.get("country", ""),
            "accident_type": src.get("accident_type", ""),
            "collision_tier": src.get("collision_tier", ""),
            "split": src.get("split", ""),
            "text": text,
            "entities": out_ents,
            "relations": out_rels,
        })

    n = write_jsonl(args.out, gold)
    if problems:
        write_csv(args.problems, problems, ["doc_id", "stage", "detail"])

    logger.info("写出 %d 篇标注 -> %s", n, args.out)
    logger.info("实体 %d 个，关系 %d 条", stats["entities"], stats["rel_ok"])
    logger.info("问题：实体找不到 %d，关系端点是空 %d，其余见 %s",
                stats["entity_missing"], stats["rel_missing"], args.problems)
    if problems:
        kinds = Counter(p["stage"] for p in problems)
        logger.info("问题分类：%s", dict(kinds))


if __name__ == "__main__":
    main()

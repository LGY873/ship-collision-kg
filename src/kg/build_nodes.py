# -*- coding: utf-8 -*-
"""S6-1：三元组 -> nodes.csv / rels.csv（供 Neo4j 导入）。

用法：
    python src/kg/build_nodes.py --run-id p1_qwen7b_test
    python src/kg/build_nodes.py --runs p1_qwen7b_test p2_qwen7b_test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import DATA, read_jsonl, setup_logging, write_csv

RUNS = DATA / "runs"
KG = DATA / "kg"


def norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"^[^a-z0-9\u4e00-\u9fff]+", "", s)
    s = re.sub(r"^the\s+|^a\s+|^an\s+", "", s)
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_") or "unknown"


def node_key(ent: dict) -> tuple[str, str]:
    """返回 (label, gid)。gid 全局唯一，用于跨文档合并同一实体。"""
    label = ent["type"]
    t = ent.get("text") or ""
    if label == "Accident":
        key = norm(ent.get("accident_no") or t)
    elif label == "Ship":
        key = norm(t)
    elif label == "Person":
        key = norm(ent.get("attributes", {}).get("role") or t)
    elif label == "Environment":
        key = norm(t)[:60]
    elif label == "Consequence":
        key = norm(t)[:60]
    else:
        key = norm(t)[:80]
    return label, f"{label}:{key}"


def main():
    ap = argparse.ArgumentParser(description="三元组导出为 CSV")
    ap.add_argument("--runs", nargs="+", default=["p1_qwen7b_test"])
    ap.add_argument("--out-dir", default=str(KG))
    ap.add_argument("--min-evidence", action="store_true",
                    help="只用 evidence 能在原文找到的关系")
    args = ap.parse_args()

    logger = setup_logging("build_nodes", DATA / "logs" / "build_nodes.log")
    nodes, rels = {}, []
    rel_counter = Counter()

    for run_id in args.runs:
        path = RUNS / run_id / "triples.jsonl"
        if not path.exists():
            logger.warning("跳过（不存在）：%s", path)
            continue
        n_doc = 0
        for doc in read_jsonl(path):
            n_doc += 1
            id2gid = {}
            acc_no = doc.get("accident_no") or ""
            for ent in doc.get("entities", []):
                label, gid = node_key(ent)
                id2gid[ent["id"]] = gid
                if gid not in nodes:
                    nodes[gid] = {"gid": gid, "label": label, "name": ent.get("text", ""),
                                  "props": json.dumps(ent.get("attributes") or {}, ensure_ascii=False),
                                  "source_docs": set()}
                nodes[gid]["source_docs"].add(doc["doc_id"])

            for rel in doc.get("relations", []):
                if args.min_evidence and not rel.get("evidence_ok"):
                    continue
                h, t = id2gid.get(rel["head"]), id2gid.get(rel["tail"])
                if not h or not t:
                    continue
                rels.append({
                    "head": h, "head_label": nodes[h]["label"],
                    "rel": rel["relation"],
                    "tail": t, "tail_label": nodes[t]["label"],
                    "source_doc": doc["doc_id"], "accident_no": acc_no,
                    "model": doc.get("model", ""), "run_id": run_id,
                    "confidence": 1.0 if rel.get("evidence_ok") else 0.5,
                    "evidence": (rel.get("evidence") or "")[:300].replace("\n", " "),
                })
                rel_counter[rel["relation"]] += 1
        logger.info("%s：%d 篇", run_id, n_doc)

    # 去重边：同一 (head, rel, tail) 保留第一条，合并 source
    merged = {}
    for r in rels:
        key = (r["head"], r["rel"], r["tail"])
        if key in merged:
            if r["source_doc"] not in merged[key]["source_doc"]:
                merged[key]["source_doc"] += ";" + r["source_doc"]
            continue
        merged[key] = r
    rel_rows = list(merged.values())

    node_rows = []
    for gid, n in nodes.items():
        node_rows.append({
            "gid": gid, "label": n["label"], "name": n["name"], "props": n["props"],
            "n_docs": len(n["source_docs"]),
            "source_docs": ";".join(sorted(n["source_docs"]))[:500],
        })

    out_dir = Path(args.out_dir)
    write_csv(out_dir / "nodes.csv", node_rows,
              ["gid", "label", "name", "props", "n_docs", "source_docs"])
    write_csv(out_dir / "rels.csv", rel_rows,
              ["head", "head_label", "rel", "tail", "tail_label",
               "source_doc", "accident_no", "model", "run_id", "confidence", "evidence"])

    logger.info("节点 %d，边 %d（去重前 %d）", len(node_rows), len(rel_rows), len(rels))
    by_label = Counter(n["label"] for n in node_rows)
    logger.info("节点分布：%s", dict(by_label))
    logger.info("关系分布：%s", dict(rel_counter.most_common()))
    logger.info("输出目录：%s", out_dir)


if __name__ == "__main__":
    main()

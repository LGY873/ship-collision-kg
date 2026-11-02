# -*- coding: utf-8 -*-
"""生成人工标注模板（可先用模型预标注，再人工改）。

流程建议：
  1) 先用 P1 提示词跑 dev/test 集；
  2) 用本脚本把模型结果转成 gold 模板（实体带 start/end，便于严格匹配）；
  3) 人工在编辑器里“删、改、补”，另存为 gold.jsonl；
  4) 双标的 25 篇必须从空白模板开始（--no-pred），否则一致性会被模型偏好污染。

用法：
    python tools/make_gold_template.py --split dev --n 43 --run-id p1_qwen7b_dev
    python tools/make_gold_template.py --split dev --n 43 --no-pred
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.common import DATA, read_jsonl, setup_logging, write_jsonl  # noqa: E402

RUNS = DATA / "runs"


def locate(text: str, needle: str) -> tuple[int, int]:
    if not needle:
        return -1, -1
    i = text.find(needle)
    if i >= 0:
        return i, i + len(needle)
    low = text.lower().find(needle.lower())
    if low >= 0:
        return low, low + len(needle)
    return -1, -1


def main():
    ap = argparse.ArgumentParser(description="生成 gold 标注模板")
    ap.add_argument("--corpus", default=str(DATA / "corpus" / "corpus_fields_split.jsonl"))
    ap.add_argument("--split", default="dev", choices=["dev", "test", "all"])
    ap.add_argument("--n", type=int, default=0)
    ap.add_argument("--run-id", default="")
    ap.add_argument("--no-pred", action="store_true", help="不填模型预标注（双标用）")
    ap.add_argument("--out", default=str(DATA / "gold" / "gold_template.jsonl"))
    args = ap.parse_args()

    logger = setup_logging("gold_template", DATA / "logs" / "gold_template.log")
    docs = [r for r in read_jsonl(args.corpus)
            if args.split == "all" or r.get("split") == args.split]
    if args.n:
        docs = docs[: args.n]

    preds = {}
    if args.run_id and not args.no_pred:
        p = RUNS / args.run_id / "triples.jsonl"
        if p.exists():
            preds = {r["doc_id"]: r for r in read_jsonl(p)}
            logger.info("载入预标注 %d 篇", len(preds))
        else:
            logger.warning("找不到 %s，将输出空白模板", p)

    rows = []
    for d in docs:
        ents, rels = [], []
        pred = preds.get(d["doc_id"])
        if pred:
            idmap = {}
            for i, e in enumerate(pred.get("entities", []), 1):
                s, t = locate(d["text"], e.get("text", ""))
                nid = f"e{i}"
                idmap[e.get("id")] = nid
                ents.append({"id": nid, "type": e.get("type"), "text": e.get("text"),
                             "start": s, "end": t, "attributes": e.get("attributes", {})})
            for r in pred.get("relations", []):
                h, tl = idmap.get(r.get("head")), idmap.get(r.get("tail"))
                if h and tl:
                    rels.append({"head": h, "relation": r.get("relation"), "tail": tl,
                                 "evidence": r.get("evidence", "")})
        rows.append({
            "doc_id": d["doc_id"],
            "accident_no": d.get("accident_no", ""),
            "country": d.get("country", ""),
            "accident_type": d.get("accident_type", ""),
            "collision_tier": d.get("collision_tier", ""),
            "split": d.get("split", ""),
            "text": d["text"],
            "entities": ents,
            "relations": rels,
            "_note": "人工修订：删掉错的、改正类型/边界、补上漏的；start/end 必须与 text 对齐",
        })

    n = write_jsonl(args.out, rows)
    n_ent = sum(len(r["entities"]) for r in rows)
    n_rel = sum(len(r["relations"]) for r in rows)
    logger.info("写出 %d 篇 -> %s", n, args.out)
    if preds:
        logger.info("预标注实体 %d 个、关系 %d 条（需要人工逐条核对）", n_ent, n_rel)


if __name__ == "__main__":
    main()

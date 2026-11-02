# -*- coding: utf-8 -*-
"""S5-5：评测脚本。对比 gold.jsonl 与某次运行的 triples.jsonl。

用法：
    python src/eval/evaluate.py --run-id p1_qwen7b_test
    python src/eval/evaluate.py --run-id p1_qwen7b_test --gold data/gold/gold.jsonl --split test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import DATA, read_jsonl, setup_logging, write_csv, write_json
from eval.metrics import Accumulator, entity_set, prf, relation_set

RUNS = DATA / "runs"


def main():
    ap = argparse.ArgumentParser(description="评测")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--gold", default=str(DATA / "gold" / "gold.jsonl"))
    ap.add_argument("--split", default="test", choices=["dev", "test", "all"])
    ap.add_argument("--out-prefix", default="")
    args = ap.parse_args()

    run_dir = RUNS / args.run_id
    logger = setup_logging(f"eval.{args.run_id}", run_dir / "eval.log")

    pred_path = run_dir / "triples.jsonl"
    if not pred_path.exists():
        logger.error("找不到 %s，请先跑 postprocess.py", pred_path)
        return
    gold_path = Path(args.gold)
    if not gold_path.exists():
        logger.error("找不到标注文件 %s", gold_path)
        return

    gold = {r["doc_id"]: r for r in read_jsonl(gold_path)}
    pred = {r["doc_id"]: r for r in read_jsonl(pred_path)}
    doc_ids = [d for d in pred if d in gold]
    if args.split != "all":
        doc_ids = [d for d in doc_ids if gold[d].get("split") == args.split]
    logger.info("评测文档 %d 篇（gold 共 %d，pred 共 %d）", len(doc_ids), len(gold), len(pred))
    if not doc_ids:
        logger.error("没有交集：检查 split 字段与 doc_id 是否一致")
        return

    acc = {("entity", "strict"): Accumulator(), ("entity", "loose"): Accumulator(),
           ("relation", "strict"): Accumulator(), ("relation", "loose"): Accumulator()}

    detail = []
    for d in doc_ids:
        g, p = gold[d], pred[d]
        for strict, tag in ((True, "strict"), (False, "loose")):
            gs = entity_set(g.get("entities", []), strict)
            ps = entity_set(p.get("entities", []), strict)
            acc[("entity", tag)].add(gs, ps)
            for typ in {t for t, _ in gs} | {t for t, _ in ps}:
                acc[("entity", tag)].add({x for x in gs if x[0] == typ},
                                         {x for x in ps if x[0] == typ}, by=typ)
            gr = relation_set(g, strict)
            pr = relation_set(p, strict)
            acc[("relation", tag)].add(gr, pr)
            for rel_type in {x[1] for x in gr} | {x[1] for x in pr}:
                acc[("relation", tag)].add({x for x in gr if x[1] == rel_type},
                                           {x for x in pr if x[1] == rel_type}, by=rel_type)
        detail.append({
            "doc_id": d,
            "country": g.get("country", ""),
            "tier": g.get("collision_tier", ""),
            "n_gold_ent": len(g.get("entities", [])),
            "n_pred_ent": len(p.get("entities", [])),
            "n_gold_rel": len(g.get("relations", [])),
            "n_pred_rel": len(p.get("relations", [])),
        })

    rows = []
    for (level, tag), a in acc.items():
        r = a.result()
        rows.append({"level": level, "match": tag, **r, "macro_f1": a.macro()})
        logger.info("%-8s %-6s  P=%.3f  R=%.3f  F1=%.3f  (macro F1=%.3f)  tp=%d fp=%d fn=%d",
                    level, tag, r["p"], r["r"], r["f1"], a.macro(), r["tp"], r["fp"], r["fn"])

    prefix = args.out_prefix or args.run_id
    write_csv(run_dir / f"{prefix}_eval.csv", rows,
              ["level", "match", "tp", "fp", "fn", "p", "r", "f1", "macro_f1"])

    # 按实体类型看长尾
    type_rows = []
    a = acc[("entity", "loose")]
    for typ, (tp, fp, fn) in sorted(a.by_type.items()):
        if typ == "*":
            continue
        p_, r_, f_ = prf(tp, fp, fn)
        type_rows.append({"entity_type": typ, "tp": tp, "fp": fp, "fn": fn,
                          "p": round(p_, 4), "r": round(r_, 4), "f1": round(f_, 4)})
    if type_rows:
        write_csv(run_dir / f"{prefix}_by_type.csv", type_rows,
                  ["entity_type", "tp", "fp", "fn", "p", "r", "f1"])
        logger.info("按类型：%s", ", ".join(f"{r['entity_type']}={r['f1']}" for r in type_rows))

    write_json(run_dir / f"{prefix}_eval.json", {
        "run_id": args.run_id, "n_docs": len(doc_ids), "split": args.split,
        "metrics": rows, "by_type": type_rows,
    })
    logger.info("结果写入 %s", run_dir)


if __name__ == "__main__":
    main()

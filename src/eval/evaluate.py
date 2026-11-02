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
from eval.metrics import (Accumulator, bootstrap_ci, counts, entity_set,
                          partial_counts, prf, relation_partial_sets, relation_set)

RUNS = DATA / "runs"
LEVELS = [("strict", True), ("loose", False), ("partial", None)]


def main():
    ap = argparse.ArgumentParser(description="评测")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--gold", default=str(DATA / "gold" / "gold.jsonl"))
    ap.add_argument("--split", default="all", choices=["dev", "test", "all"],
                    help="按 gold 里的 split 字段筛评测文档；gold 目前全部标注在 dev，"
                         "所以默认 all（等价于那 20 篇），test 集尚未标注")
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
    # 以 gold 为准枚举文档：模型没跑到的文档要计成 FN，否则跑 5 篇也能刷出高分
    if args.split == "all":
        doc_ids = sorted(gold)
    else:
        doc_ids = sorted(d for d, g in gold.items() if g.get("split") == args.split)
    missing = [d for d in doc_ids if d not in pred]
    logger.info("评测文档 %d 篇（gold 共 %d，pred 共 %d）；gold 有标注但未预测 %d 篇",
                len(doc_ids), len(gold), len(pred), len(missing))
    if missing:
        logger.warning("未预测的文档按空结果计 FN：%s%s", ", ".join(missing[:5]),
                       " …" if len(missing) > 5 else "")
    if not doc_ids:
        logger.error("gold 里没有 split=%s 的文档", args.split)
        return

    acc = {(lv, "entity"): Accumulator() for lv, _ in LEVELS}
    acc.update({(lv, "relation"): Accumulator() for lv, _ in LEVELS})

    detail = []
    per_doc = {k: [] for k in acc}
    for d in doc_ids:
        g, p = gold[d], pred.get(d, {})
        for tag, strict in LEVELS:
            if strict is None:
                ec = partial_counts(g.get("entities", []), p.get("entities", []))
                gr, pr = relation_partial_sets(g, p)
                rc = counts(gr, pr)
            else:
                gs = entity_set(g.get("entities", []), strict)
                ps = entity_set(p.get("entities", []), strict)
                ec = counts(gs, ps)
                gr = relation_set(g, strict)
                pr = relation_set(p, strict)
                rc = counts(gr, pr)
            per_doc[(tag, "entity")].append(ec)
            acc[(tag, "entity")].add_counts(*ec)
            per_doc[(tag, "relation")].append(rc)
            acc[(tag, "relation")].add_counts(*rc)
            if strict is not None:
                gs = entity_set(g.get("entities", []), strict)
                ps = entity_set(p.get("entities", []), strict)
                for typ in {t for t, _ in gs} | {t for t, _ in ps}:
                    acc[(tag, "entity")].add({x for x in gs if x[0] == typ},
                                             {x for x in ps if x[0] == typ}, by=typ)
                for rel_type in {x[1] for x in gr} | {x[1] for x in pr}:
                    acc[(tag, "relation")].add({x for x in gr if x[1] == rel_type},
                                               {x for x in pr if x[1] == rel_type}, by=rel_type)
            else:
                # 部分重叠口径：同一类型内部单独配对，才能给出按类型的 P/R/F1
                types = {e.get("type") for e in g.get("entities", [])} | \
                        {e.get("type") for e in p.get("entities", [])}
                for typ in types:
                    gc = [e for e in g.get("entities", []) if e.get("type") == typ]
                    pc = [e for e in p.get("entities", []) if e.get("type") == typ]
                    acc[(tag, "entity")].add_counts(*partial_counts(gc, pc), by=typ)
                for rel_type in {x[1] for x in gr} | {x[1] for x in pr}:
                    acc[(tag, "relation")].add({x for x in gr if x[1] == rel_type},
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
    ci_rows = {}
    # 先出实体级再出关系级，与报告表顺序一致
    for level in ("entity", "relation"):
        for tag, _ in LEVELS:
            a = acc[(tag, level)]
            r = a.result()
            ci = bootstrap_ci(per_doc[(tag, level)])
            ci_rows[f"{level}_{tag}"] = ci
            rows.append({"level": level, "match": tag, **r, "macro_f1": a.macro(),
                         "f1_lo": ci.get("f1", (0, 0))[0], "f1_hi": ci.get("f1", (0, 0))[1]})
            logger.info("%-8s %-7s  P=%.3f  R=%.3f  F1=%.3f [95%% CI %.3f–%.3f]  (macro F1=%.3f)  tp=%d fp=%d fn=%d",
                        level, tag, r["p"], r["r"], r["f1"],
                        ci.get("f1", (0, 0))[0], ci.get("f1", (0, 0))[1],
                        a.macro(), r["tp"], r["fp"], r["fn"])

    prefix = args.out_prefix or args.run_id
    write_csv(run_dir / f"{prefix}_eval.csv", rows,
              ["level", "match", "tp", "fp", "fn", "p", "r", "f1", "f1_lo", "f1_hi", "macro_f1"])
    write_csv(run_dir / f"{prefix}_by_doc.csv", detail,
              ["doc_id", "country", "tier", "n_gold_ent", "n_pred_ent",
               "n_gold_rel", "n_pred_rel"])

    # 按实体类型看长尾（用宽松口径，部分重叠口径不支持按类型累计）
    type_rows = []
    a = acc[("loose", "entity")]
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
        "metrics": rows, "by_type": type_rows, "bootstrap_ci": ci_rows,
        "bootstrap": {"n_boot": 2000, "alpha": 0.05, "seed": 42},
    })
    logger.info("结果写入 %s", run_dir)


if __name__ == "__main__":
    main()

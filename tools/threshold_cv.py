# -*- coding: utf-8 -*-
"""证据一致性阈值的选择是否在「用评测集调参」？用 5 折交叉验证回答。

背景：`--min-evidence-ratio 0.85` 是个经验值。直接拿 20 篇 gold 扫一遍取最高 F1，
等于把评测集当验证集用，写进论文会被质疑。这里做两件事：

1. 全量扫描：每个阈值在 20 篇上的 F1（给读者看趋势）；
2. 5 折交叉验证：在 4 折上挑阈值、在第 5 折上报成绩，轮换 5 次取均值。
   如果 CV 均值与「固定 0.85」接近，说明这个阈值不是过拟合出来的。

用法：
    python tools/threshold_cv.py --run-id p1_qwen7b_dev
"""
from __future__ import annotations

import argparse
import io
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import DATA, read_jsonl  # noqa: E402
from src.eval.metrics import prf, relation_set  # noqa: E402

RUNS = DATA / "runs"
GRID = [0.0, 0.40, 0.60, 0.75, 0.85, 0.90, 0.95]


def load_gold():
    gold = {}
    for g in read_jsonl(DATA / "gold" / "gold.jsonl"):
        gold[g["doc_id"]] = g
    return gold


def per_doc_counts(gold, preds, thr):
    """返回 {doc_id: (tp, fp, fn)}，只统计 gold 与 pred 都有的文档。"""
    out = {}
    for did in gold:
        g = gold[did]
        p = preds.get(did)
        gs = relation_set(g, strict=True)
        ps = set()
        if p:
            kept = {"entities": p.get("entities", []),
                    "relations": [r for r in p.get("relations", [])
                                  if float(r.get("evidence_ratio") or 0) >= thr]}
            ps = relation_set(kept, strict=True)
        out[did] = (len(gs & ps), len(ps - gs), len(gs - ps))
    return out


def aggregate(per_doc, docs):
    tp = sum(per_doc[d][0] for d in docs)
    fp = sum(per_doc[d][1] for d in docs)
    fn = sum(per_doc[d][2] for d in docs)
    return prf(tp, fp, fn)


def main():
    ap = argparse.ArgumentParser(description="证据阈值 5 折交叉验证")
    ap.add_argument("--run-id", default="p1_qwen7b_dev")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    gold = load_gold()
    preds = {d["doc_id"]: d for d in read_jsonl(RUNS / args.run_id / "triples.jsonl")}
    docs = [d for d in gold if d in preds]
    print(f"{args.run_id}：gold {len(gold)} 篇，有预测 {len(docs)} 篇\n")

    print("## 全量扫描（同一批文档上选阈值，仅看趋势）\n")
    print("| 阈值 | 关系 P | 关系 R | 关系 F1 |")
    print("| ---: | ---: | ---: | ---: |")
    cache = {t: per_doc_counts(gold, preds, t) for t in GRID}
    for t in GRID:
        p, r, f = aggregate(cache[t], docs)
        print(f"| {t:.2f} | {p:.3f} | {r:.3f} | **{f:.3f}** |")

    print(f"\n## {args.folds} 折交叉验证（训练折选阈值，测试折报成绩）\n")
    rng = random.Random(args.seed)
    order = sorted(docs)
    rng.shuffle(order)
    folds = [order[i::args.folds] for i in range(args.folds)]

    chosen, scores = [], []
    for i in range(args.folds):
        test = folds[i]
        train = [d for d in order if d not in set(test)]
        best_t, best_f = None, -1.0
        for t in GRID:
            _, _, f = aggregate(cache[t], train)
            if f > best_f:
                best_t, best_f = t, f
        p, r, f = aggregate(cache[best_t], test)
        chosen.append(best_t)
        scores.append(f)
        print(f"- 折 {i + 1}：训练折选出阈值 {best_t:.2f}（训练 F1 {best_f:.3f}）"
              f"→ 测试折 P={p:.3f} R={r:.3f} F1={f:.3f}")

    mean = sum(scores) / len(scores)
    var = sum((s - mean) ** 2 for s in scores) / max(1, len(scores) - 1)
    print(f"\nCV 均值 F1 = **{mean:.3f}**（标准差 {var ** 0.5:.3f}），"
          f"选中的阈值 {sorted(set(chosen))}")

    print("\n## 固定阈值对照（不调参时的表现）\n")
    print("| 阈值 | 全量 F1 |")
    print("| ---: | ---: |")
    for t in (0.0, 0.85):
        _, _, f = aggregate(cache[t], docs)
        label = "不过滤" if t == 0 else f"固定 {t:.2f}"
        print(f"| {label} | {f:.3f} |")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""双标一致性：按“实体类型”计算 Cohen's kappa。

做法：把两名标注者所有实体按归一化文本对齐，得到候选集合；
每个候选的标签是“实体类型”或“O（未标注）”，再算 kappa。

用法：
    python tools/kappa.py --a data/gold/annotator_a.jsonl --b data/gold/annotator_b.jsonl
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from src.common import read_jsonl  # noqa: E402
from src.eval.metrics import norm_text  # noqa: E402


def load(path):
    out = {}
    for r in read_jsonl(path):
        ents = {}
        for e in r.get("entities", []):
            ents[(e.get("type"), norm_text(e.get("text")))] = e.get("type")
        out[r["doc_id"]] = ents
    return out


def kappa(pairs):
    """pairs: [(label_a, label_b), ...]"""
    n = len(pairs)
    if n == 0:
        return 0.0, 0.0
    a_cnt, b_cnt, agree = Counter(), Counter(), 0
    for x, y in pairs:
        a_cnt[x] += 1
        b_cnt[y] += 1
        if x == y:
            agree += 1
    po = agree / n
    labels = set(a_cnt) | set(b_cnt)
    pe = sum((a_cnt[k] / n) * (b_cnt[k] / n) for k in labels)
    k = (po - pe) / (1 - pe) if pe < 1 else 1.0
    return po, k


def main():
    ap = argparse.ArgumentParser(description="Cohen's kappa")
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--by-doc", action="store_true")
    args = ap.parse_args()

    A, B = load(args.a), load(args.b)
    common = sorted(set(A) & set(B))
    print(f"共同文档 {len(common)} 篇（A {len(A)} / B {len(B)}）")
    if not common:
        return

    all_pairs = []
    per_doc = []
    for d in common:
        keys = set(A[d]) | set(B[d])
        # 只比较“文本”层面：同一个文本两人分别给了什么类型
        by_text = defaultdict(lambda: ["O", "O"])
        for (typ, txt) in A[d]:
            by_text[txt][0] = typ
        for (typ, txt) in B[d]:
            by_text[txt][1] = typ
        pairs = [tuple(v) for v in by_text.values()]
        all_pairs.extend(pairs)
        if pairs:
            po, k = kappa(pairs)
            per_doc.append((d, po, k, len(pairs)))

    po, k = kappa(all_pairs)
    print(f"全部实体候选 {len(all_pairs)} 个：一致率 Po={po:.3f}，Cohen's kappa={k:.3f}")
    if k >= 0.75:
        print("结论：一致性合格（>=0.75），可以进入正式实验")
    elif k >= 0.6:
        print("结论：可接受但偏低，建议补充规范说明并重点复核分歧样本")
    else:
        print("结论：一致性不足，必须修订标注规范并回标")

    # 分歧最多的类型
    mm = Counter()
    for x, y in all_pairs:
        if x != y:
            mm[f"{x} vs {y}"] += 1
    if mm:
        print("主要分歧：", dict(mm.most_common(8)))

    if args.by_doc:
        print("\n按文档：")
        for d, po, kk, n in sorted(per_doc, key=lambda x: x[2])[:10]:
            print(f"  {d:<40s} n={n:<4d} Po={po:.2f} kappa={kk:.2f}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""S2-5：按事故号做 6:2:2 分层划分。

关键点：
  * 划分单位是“事故”，同一事故的多篇文档不会被拆到不同 split（防泄漏）；
  * 分层维度：国别 × 碰撞等级 × 长度桶；
  * 结果写 splits.json，并在 corpus 里回填 split 字段，全流程共用一份。

用法：
    python src/prep/split_dataset.py --corpus data/corpus/corpus_fields.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import DATA, read_jsonl, setup_logging, write_json, write_jsonl


def bucket_len(n: int) -> str:
    if n < 800:
        return "S"
    if n < 2000:
        return "M"
    return "L"


def main():
    ap = argparse.ArgumentParser(description="分层划分数据集")
    ap.add_argument("--corpus", default=str(DATA / "corpus" / "corpus_fields.jsonl"))
    ap.add_argument("--out-corpus", default="")
    ap.add_argument("--splits", default=str(DATA / "corpus" / "splits.json"))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    logger = setup_logging("split", DATA / "logs" / "split.log")
    rows = list(read_jsonl(args.corpus))
    if not rows:
        logger.error("语料为空：%s", args.corpus)
        return

    # 事故级聚合
    by_acc = defaultdict(list)
    for r in rows:
        by_acc[r["accident_key"] or r["accident_no"]].append(r)

    strata = defaultdict(list)
    for acc, docs in by_acc.items():
        d = docs[0]
        key = (d["country"], d.get("collision_tier", ""), bucket_len(sum(x["n_chars"] for x in docs)))
        strata[key].append(acc)

    split_of = {}
    for key, accs in sorted(strata.items()):
        # 用 sha256(seed+acc) 排序，保证可复现且与输入顺序无关
        accs = sorted(accs, key=lambda a: hashlib.sha256(f"{args.seed}:{a}".encode()).hexdigest())
        n = len(accs)
        n_train = max(1, round(n * 0.6)) if n >= 3 else n
        n_dev = max(1, round(n * 0.2)) if n >= 3 else 0
        for i, a in enumerate(accs):
            if i < n_train:
                split_of[a] = "train"
            elif i < n_train + n_dev:
                split_of[a] = "dev"
            else:
                split_of[a] = "test"

    # 逐层四舍五入会让 dev/test 漂移，这里按全局配额做一次微调（只动 dev/test）
    total = len(split_of)
    target_dev = round(total * 0.2)
    dev_list = sorted([a for a, s in split_of.items() if s == "dev"],
                      key=lambda a: hashlib.sha256(f"adj:{args.seed}:{a}".encode()).hexdigest())
    test_list = sorted([a for a, s in split_of.items() if s == "test"],
                       key=lambda a: hashlib.sha256(f"adj:{args.seed}:{a}".encode()).hexdigest())
    while len(dev_list) > target_dev and test_list:
        a = dev_list.pop()
        split_of[a] = "test"
        test_list.append(a)
    while len(dev_list) < target_dev and test_list:
        a = test_list.pop()
        split_of[a] = "dev"
        dev_list.append(a)

    for r in rows:
        r["split"] = split_of.get(r["accident_key"] or r["accident_no"], "train")

    out_corpus = args.out_corpus or str(Path(args.corpus).with_name(
        Path(args.corpus).stem + "_split.jsonl"))
    write_jsonl(out_corpus, rows)

    splits = defaultdict(list)
    for r in rows:
        splits[r["split"]].append(r["doc_id"])
    write_json(args.splits, {k: sorted(v) for k, v in splits.items()})

    acc_split = {}
    for acc, s in split_of.items():
        acc_split[s] = acc_split.get(s, 0) + 1

    logger.info("文档：train=%d dev=%d test=%d",
                len(splits.get("train", [])), len(splits.get("dev", [])),
                len(splits.get("test", [])))
    logger.info("事故：train=%d dev=%d test=%d",
                acc_split.get("train", 0), acc_split.get("dev", 0), acc_split.get("test", 0))
    logger.info("划分文件：%s；语料：%s", args.splits, out_corpus)


if __name__ == "__main__":
    main()

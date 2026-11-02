# -*- coding: utf-8 -*-
"""图谱统计：从 data/kg/nodes.csv + rels.csv 出论文用的表格。

用法：
    python tools/kg_stats.py                 # 打印
    python tools/kg_stats.py --md data/kg/kg_stats.md
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import DATA, iter_csv, setup_logging

KG = DATA / "kg"


def main():
    ap = argparse.ArgumentParser(description="知识图谱统计")
    ap.add_argument("--nodes", default=str(KG / "nodes.csv"))
    ap.add_argument("--rels", default=str(KG / "rels.csv"))
    ap.add_argument("--md", default="")
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    logger = setup_logging("kg_stats", None)
    nodes = list(iter_csv(args.nodes))
    rels = list(iter_csv(args.rels))
    logger.info("节点 %d，边 %d", len(nodes), len(rels))

    by_label = Counter(n["label"] for n in nodes)
    name_by_label = defaultdict(list)
    for n in nodes:
        name_by_label[n["label"]].append(n["name"])

    # 度分布（按 gid）
    deg = Counter()
    for r in rels:
        deg[r["head"]] += 1
        deg[r["tail"]] += 1
    label_of = {n["gid"]: n["label"] for n in nodes}
    name_of = {n["gid"]: n["name"] for n in nodes}

    order = ["Accident", "Ship", "Person", "Organization", "Environment",
             "Equipment", "Consequence"]
    lines = []
    lines.append("## 一、节点规模\n")
    lines.append("| 实体类型 | 节点数 | 占比 | 示例 |")
    lines.append("| --- | ---: | ---: | --- |")
    for lab in order:
        c = by_label.get(lab, 0)
        ex = "、".join(name_by_label.get(lab, [])[:3])
        lines.append(f"| {lab} | {c} | {c / len(nodes) * 100:.1f}% | {ex} |")
    lines.append(f"| **合计** | **{len(nodes)}** | 100% | |")

    lines.append("\n## 二、关系规模\n")
    rel_count = Counter(r["rel"] for r in rels)
    lines.append("| 关系类型 | 边数 | 占比 |")
    lines.append("| --- | ---: | ---: |")
    for rel, c in rel_count.most_common():
        lines.append(f"| {rel} | {c} | {c / len(rels) * 100:.1f}% |")
    lines.append(f"| **合计** | **{len(rels)}** | 100% |")

    lines.append("\n## 三、度分布\n")
    buckets = [(0, 0), (1, 1), (2, 2), (3, 5), (6, 10), (11, 20), (21, 10 ** 9)]
    total_nodes = max(1, len(nodes))
    lines.append("| 度区间 | 节点数 | 占比 |")
    lines.append("| --- | ---: | ---: |")
    for lo, hi in buckets:
        c = sum(1 for n in nodes if lo <= deg.get(n["gid"], 0) <= hi)
        lab = f"{lo}" if lo == hi else (f"≥{lo}" if hi > 10 ** 8 else f"{lo}–{hi}")
        lines.append(f"| {lab} | {c} | {c / total_nodes * 100:.1f}% |")

    lines.append("\n## 四、中心节点（度 Top）\n")
    lines.append("| 排名 | 节点 | 类型 | 度 |")
    lines.append("| ---: | --- | --- | ---: |")
    for i, (gid, d) in enumerate(deg.most_common(args.top), 1):
        lines.append(f"| {i} | {name_of.get(gid, gid)} | {label_of.get(gid, '?')} | {d} |")

    # 跨文档实体（出现在多篇里，说明合并生效）
    multi = [n for n in nodes if int(n["n_docs"] or 0) > 1]
    lines.append("\n## 五、跨文档合并\n")
    lines.append(f"出现在 2 篇及以上的节点：**{len(multi)}** 个（占 {len(multi) / total_nodes * 100:.1f}%）")
    if multi:
        lines.append("\n| 节点 | 类型 | 文档数 |")
        lines.append("| --- | --- | ---: |")
        multi.sort(key=lambda n: -int(n["n_docs"]))
        for n in multi[:10]:
            lines.append(f"| {n['name']} | {n['label']} | {n['n_docs']} |")

    # 事故覆盖
    acc_ids = {n["gid"] for n in nodes if n["label"] == "Accident"}
    covered = {r["accident_no"] for r in rels if r["accident_no"]}
    lines.append("\n## 六、事故覆盖\n")
    lines.append(f"事故节点 {len(acc_ids)} 个；有关系输出的事故 {len(covered)} 个")

    # 属性完整度
    lines.append("\n## 七、属性完整度\n")
    lines.append("| 实体类型 | 属性非空率 | 主要属性 |")
    lines.append("| --- | ---: | --- |")
    keys_by_label = defaultdict(Counter)
    filled = Counter()
    for n in nodes:
        try:
            props = json.loads(n["props"] or "{}")
        except json.JSONDecodeError:
            props = {}
        if props:
            filled[n["label"]] += 1
        for k, v in props.items():
            if v:
                keys_by_label[n["label"]][k] += 1
    for lab in order:
        c = by_label.get(lab, 0)
        if not c:
            continue
        top_keys = "、".join(f"{k}" for k, _ in keys_by_label[lab].most_common(4))
        lines.append(f"| {lab} | {filled[lab] / c * 100:.0f}% | {top_keys} |")

    md = "\n".join(lines) + "\n"
    if args.md:
        p = Path(args.md)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md, encoding="utf-8")
        logger.info("已写出 %s", p)
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())

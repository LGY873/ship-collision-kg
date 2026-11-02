# -*- coding: utf-8 -*-
"""不装 Neo4j 也能跑那 8 条分析查询：直接在 nodes.csv / rels.csv 上算。

为什么有这个脚本：`src/kg/queries.py` 依赖 bolt 连接，答辩机器上不一定装了
Neo4j。这个版本用同一份 CSV 做等价统计，结果能直接贴进论文表格，也能当
「不依赖图数据库」的对照实现 —— 两边跑出来的数应该一致。

用法：
    python tools/kg_queries_local.py --list
    python tools/kg_queries_local.py --run q1
    python tools/kg_queries_local.py --run all --md docs/kg_queries.md
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import DATA  # noqa: E402

KG = DATA / "kg"

FACTOR_RELS = ["caused_by_person", "caused_by_equipment", "caused_by_org", "affected_by"]


def load():
    """读 CSV：节点按 gid 索引，边转成 (head, rel, tail) 三元组列表。"""
    npath, rpath = KG / "nodes.csv", KG / "rels.csv"
    if not npath.exists():
        sys.exit(f"缺少 {npath}，先跑 src/kg/build_nodes.py")
    nodes = {}
    with open(npath, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            try:
                row["props"] = json.loads(row.get("props") or "{}")
            except json.JSONDecodeError:
                row["props"] = {}
            nodes[row["gid"]] = row
    rels = []
    if rpath.exists():
        with open(rpath, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                rels.append((row["head"], row["rel"], row["tail"], row))
    return nodes, rels


def name_of(nodes, gid):
    return (nodes.get(gid, {}) or {}).get("name", gid)


def acc_of(nodes, gid):
    """事件号：Accident 节点用 props.accident_no，其余回落到 gid。"""
    n = nodes.get(gid) or {}
    return (n.get("props") or {}).get("accident_no") or n.get("gid", gid)


# ---------------------------------------------------------------- q1
def q1(nodes, rels, limit):
    """高频致因因素：按「多少起事故」去重计数，不是按边数。"""
    counter = Counter()
    docs = defaultdict(set)
    for h, rel, t, _ in rels:
        if rel not in FACTOR_RELS:
            continue
        tl = (nodes.get(t) or {}).get("label", "")
        key = (tl, name_of(nodes, t), rel)
        counter[key] += 1
        docs[key].add(acc_of(nodes, h))
    rows = [(ft, nm, rel, len(docs[(ft, nm, rel)]), cnt)
            for (ft, nm, rel), cnt in counter.items()]
    rows.sort(key=lambda r: (-r[3], -r[4]))
    out = [("因素类型", "因素", "关系", "事故数", "边数")] + rows[:limit]
    return "q1 高频致因因素（按事故数去重）", out


# ---------------------------------------------------------------- q2
def q2(nodes, rels, limit):
    """因素共现：同一事故里同时出现过的因素对（无序对，i<j）。"""
    per_acc = defaultdict(list)
    for h, rel, t, _ in rels:
        if rel not in FACTOR_RELS:
            continue
        per_acc[acc_of(nodes, h)].append((name_of(nodes, t),
                                          (nodes.get(t) or {}).get("label", "")))
    pair = Counter()
    for acc, fs in per_acc.items():
        uniq = sorted(set(fs))
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                pair[(uniq[i], uniq[j])] += 1
    rows = [(a[0], a[1], b[0], b[1], n) for (a, b), n in pair.items()]
    rows.sort(key=lambda r: -r[4])
    out = [("因素 1", "类型 1", "因素 2", "类型 2", "共现事故数")] + rows[:limit]
    return "q2 因素共现对（叠加风险组合）", out


# ---------------------------------------------------------------- q3
def q3(nodes, rels, limit):
    """国别差异：Accident 上挂的关系按国别统计。"""
    counter = Counter()
    for h, rel, t, _ in rels:
        hn = nodes.get(h) or {}
        if hn.get("label") != "Accident":
            continue
        country = (hn.get("props") or {}).get("country") or "unknown"
        counter[(country, rel)] += 1
    rows = [(c, rel, n) for (c, rel), n in counter.items()]
    rows.sort(key=lambda r: (r[0], -r[2]))
    out = [("国别", "关系", "边数")] + rows[:limit]
    return "q3 国别 × 关系分布", out


# ---------------------------------------------------------------- q4
def q4(nodes, rels, limit):
    """船型—事故类型关联。

    本体里事故与船之间只有 involves_ship 一条边，模型很少主动写它；
    若该边为 0，退回「同一份报告里出现过」的关联（语义上等价于该船参与该事故，
    因为一篇报告就是一个事故），并在标题里标明用的是哪种关联。
    """
    def low(v):
        return (v or "unknown").strip().lower() or "unknown"

    counter = Counter()
    used = 0
    for h, rel, t, _ in rels:
        if rel != "involves_ship":
            continue
        used += 1
        an = nodes.get(h) or {}
        sn = nodes.get(t) or {}
        counter[(low((sn.get("props") or {}).get("ship_type")),
                 low((an.get("props") or {}).get("type")))] += 1
    mode = "involves_ship 边"
    if used == 0:
        mode = "同报告关联（involves_ship 缺失）"
        doc2acc, doc2ships = defaultdict(set), defaultdict(list)
        for gid, n in nodes.items():
            if n.get("label") != "Accident":
                continue
            for d in (n.get("source_docs") or "").split(";"):
                if d:
                    doc2acc[d].add(gid)
        for gid, n in nodes.items():
            if n.get("label") != "Ship":
                continue
            for d in (n.get("source_docs") or "").split(";"):
                if d:
                    doc2ships[d].append(gid)
        for d, ships in doc2ships.items():
            for a in doc2acc.get(d, ()):
                an = nodes.get(a) or {}
                for s in ships:
                    sn = nodes.get(s) or {}
                    counter[(low((sn.get("props") or {}).get("ship_type")),
                             low((an.get("props") or {}).get("type")))] += 1
    rows = [(st, at, n) for (st, at), n in counter.items()]
    rows.sort(key=lambda r: (-r[2], r[0]))
    out = [("船型", "事故类型", "事故数")] + rows[:limit]
    return f"q4 船型—事故类型关联（{mode}）", out


# ---------------------------------------------------------------- q5
def q5(nodes, rels, limit):
    """时间趋势：年份取自 Accident.props.date（不是从名字前四位猜）。"""
    per_year = defaultdict(set)
    cons = Counter()
    for gid, n in nodes.items():
        if n.get("label") != "Accident":
            continue
        date = (n.get("props") or {}).get("date") or ""
        year = date[:4]
        if not (len(year) == 4 and year.isdigit() and 1900 < int(year) < 2100):
            continue
        per_year[year].add(gid)
    for h, rel, t, _ in rels:
        if rel != "led_to":
            continue
        an = nodes.get(h) or {}
        date = (an.get("props") or {}).get("date") or ""
        if len(date) >= 4 and date[:4].isdigit():
            cons[date[:4]] += 1
    rows = [(y, len(ids), cons.get(y, 0)) for y, ids in sorted(per_year.items())]
    out = [("年份", "事故数", "后果数")] + rows[:limit]
    return "q5 时间趋势", out


# ---------------------------------------------------------------- q6
def q6(nodes, rels, limit):
    """节点中心性：非 Accident 节点的度（入边 + 出边都算）。"""
    deg = Counter()
    for h, rel, t, _ in rels:
        for x in (h, t):
            if (nodes.get(x) or {}).get("label") != "Accident":
                deg[x] += 1
    rows = [((nodes.get(g) or {}).get("label", ""), name_of(nodes, g), d)
            for g, d in deg.items()]
    rows.sort(key=lambda r: -r[2])
    out = [("类型", "节点", "度")] + rows[:limit]
    return "q6 节点中心性（度）", out


# ---------------------------------------------------------------- q7
def q7(nodes, rels, limit):
    """因素—后果传导：同一事故下的 (因素, 后果) 组合。

    Cypher 版写的是 事故->因素->后果 的两跳；本体里因素节点没有指向后果的边，
    实际等价于「同一事故内因素与后果共现」，这里按等价关系实现并标明。
    """
    per_acc = defaultdict(lambda: {"f": [], "c": []})
    for h, rel, t, _ in rels:
        if rel in FACTOR_RELS:
            per_acc[acc_of(nodes, h)]["f"].append(name_of(nodes, t))
        elif rel == "led_to":
            per_acc[acc_of(nodes, h)]["c"].append(name_of(nodes, t))
    pair = Counter()
    for acc, d in per_acc.items():
        for f in set(d["f"]):
            for c in set(d["c"]):
                pair[(f, c)] += 1
    rows = [(f, c, n) for (f, c), n in pair.items()]
    rows.sort(key=lambda r: -r[2])
    out = [("因素", "后果", "事故数")] + rows[:limit]
    return "q7 因素—后果传导（同事故共现）", out


# ---------------------------------------------------------------- q8
def q8(nodes, rels, limit, param=""):
    """单事故子图：给定事故号，列出它的一跳邻居与边，答辩时当案例展示。"""
    accs = [g for g, n in nodes.items() if n.get("label") == "Accident"]
    gid = next((a for a in accs if acc_of(nodes, a) == (param or "").upper()), None)
    if gid is None:
        gid = next((a for a in accs if (nodes[a].get("props") or {}).get("accident_no")), accs[0] if accs else None)
    if gid is None:
        return "q8 单事故子图", [("提示",), ("图谱里还没有 Accident 节点",)]
    rows = []
    for h, rel, t, meta in rels:
        if h != gid and t != gid:
            continue
        other = t if h == gid else h
        rows.append(((nodes.get(other) or {}).get("label", ""), name_of(nodes, other),
                     rel, meta.get("source_doc", ""),
                     (meta.get("evidence") or "")[:100]))
    rows.sort(key=lambda r: (r[2], r[1]))
    out = [("邻居类型", "邻居", "关系", "来源文档", "证据句")] + rows[:limit]
    acc = nodes.get(gid) or {}
    title = f"q8 单事故子图：{acc.get('name', gid)[:60]}"
    return title, out


QUERIES = {"q1": q1, "q2": q2, "q3": q3, "q4": q4,
           "q5": q5, "q6": q6, "q7": q7, "q8": q8}


def as_markdown(title, rows):
    if not rows:
        return f"### {title}\n\n（无数据）\n"
    head, body = rows[0], rows[1:]
    lines = [f"### {title}", "",
             "| " + " | ".join(str(h) for h in head) + " |",
             "|" + "|".join(["---"] * len(head)) + "|"]
    for r in body:
        cells = [str(c).replace("|", "/").replace("\n", " ")[:80] for c in r]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="不依赖 Neo4j 的 8 条图谱查询")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--run", default="all", help="q1..q8 或 all")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--param", default="", help="q8 的事故号，留空自动挑第一个")
    ap.add_argument("--md", default="", help="把结果写成 markdown 文件")
    args = ap.parse_args()

    if args.list:
        for k in QUERIES:
            print(k, QUERIES[k].__doc__.strip().splitlines()[0])
        return

    nodes, rels = load()
    keys = list(QUERIES) if args.run == "all" else [args.run]
    blocks = []
    for k in keys:
        if k not in QUERIES:
            sys.exit(f"未知查询 {k}")
        if k == "q8":
            title, rows = QUERIES[k](nodes, rels, args.limit, args.param)
        else:
            title, rows = QUERIES[k](nodes, rels, args.limit)
        blocks.append(as_markdown(title, rows))
    text = "\n".join(blocks)
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print(text)
    if args.md:
        p = Path(args.md)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# 图谱分析查询结果\n\n"
                     f"节点 {len(nodes)} 个、边 {len(rels)} 条。\n\n" + text,
                     encoding="utf-8")
        print(f"已写入 {p}")


if __name__ == "__main__":
    main()

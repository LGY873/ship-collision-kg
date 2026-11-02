r"""生成论文补充插图：三策略对比、证据阈值曲线、图谱网络结构。

用法：
    $env:MPLCONFIGDIR = "$PWD\data\logs\mpl"
    .\.venv\Scripts\python.exe tools\make_extra_figures.py [--out docs\figures]

数据来源均为仓库内既有产物，不调用模型：
    data/runs/<run_id>/<run_id>_eval.json
    data/kg/nodes.csv、data/kg/rels.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import DATA, ROOT  # noqa: E402

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# 三策略对比用的 run 与展示名
STRATEGY_RUNS = [
    ("cmp_p0", "p0 开放词表"),
    ("cmp_p2", "p2 少样本(2例)"),
    ("cmp_p2b", "p2 少样本(3例)"),
    ("p1_qwen7b_dev", "p1 本体约束"),
]

THRESHOLDS = [0.00, 0.40, 0.60, 0.75, 0.85, 0.90, 0.95]
THRESHOLD_F1 = [0.555, 0.577, 0.582, 0.594, 0.597, 0.585, 0.595]


def load_metrics(run_id: str) -> dict | None:
    p = DATA / "runs" / run_id / f"{run_id}_eval.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    out = {}
    for m in d.get("metrics", []):
        out[(m.get("level"), m.get("match"))] = m
    return {"n_docs": d.get("n_docs"), "metrics": out}


def fig_strategies(out_dir: Path) -> Path:
    labels, ent_f1, rel_f1 = [], [], []
    for run_id, name in STRATEGY_RUNS:
        d = load_metrics(run_id)
        if not d:
            continue
        em = next((m for (lv, mt), m in d["metrics"].items() if lv == "entity" and mt == "strict"), None)
        rm = next((m for (lv, mt), m in d["metrics"].items() if lv == "relation" and mt == "strict"), None)
        if not em or not rm:
            continue
        labels.append(name)
        ent_f1.append(em["f1"] * 100)
        rel_f1.append(rm["f1"] * 100)

    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=300)
    x = range(len(labels))
    w = 0.36
    b1 = ax.bar([i - w / 2 for i in x], ent_f1, w, label="实体 F1", color="#4C72B0")
    b2 = ax.bar([i + w / 2 for i in x], rel_f1, w, label="关系 F1", color="#DD8452")
    for bars in (b1, b2):
        for r in bars:
            ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 1.5,
                    f"{r.get_height():.1f}", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("F1（%）")
    ax.set_title("三种提示策略的抽取效果对比（严格口径，20 篇）", fontsize=13)
    ax.set_ylim(0, 100)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend()
    fig.tight_layout()
    path = out_dir / "fig_strategy.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_threshold(out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=300)
    ax.plot([t * 100 for t in THRESHOLDS], THRESHOLD_F1, marker="o", color="#4C72B0", label="关系 F1")
    ax.axhline(0.555, color="#999999", linestyle="--", linewidth=1, label="不过滤基线 0.555")
    ax.axhline(0.586, color="#C44E52", linestyle=":", linewidth=1.4, label="5 折交叉验证均值 0.586")
    for t, f in zip(THRESHOLDS, THRESHOLD_F1):
        ax.annotate(f"{f:.3f}", (t * 100, f), textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=8)
    ax.set_xlabel("证据一致性阈值（%）")
    ax.set_ylabel("关系严格 F1")
    ax.set_title("证据一致性阈值对关系抽取的影响", fontsize=13)
    ax.set_ylim(0.53, 0.62)
    ax.grid(linestyle="--", alpha=0.4)
    ax.legend(fontsize=9)
    fig.tight_layout()
    path = out_dir / "fig_threshold.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_network(out_dir: Path) -> Path | None:
    import csv

    nodes_p = DATA / "kg" / "nodes.csv"
    rels_p = DATA / "kg" / "rels.csv"
    if not nodes_p.exists() or not rels_p.exists():
        return None
    try:
        import networkx as nx
    except ImportError:
        return None

    labels = {}
    with nodes_p.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            labels[row["gid"]] = (row["label"], row["name"])

    G = nx.Graph()
    with rels_p.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            G.add_edge(row["head"], row["tail"], rel=row["rel"])

    if G.number_of_nodes() == 0:
        return None
    # 只画最大连通分量，否则孤立点会挤成一圈
    comp = max(nx.connected_components(G), key=len)
    H = G.subgraph(comp).copy()

    colors = {
        "Accident": "#C44E52", "Ship": "#4C72B0", "Person": "#55A868",
        "Organization": "#8172B3", "Environment": "#CCB974",
        "Equipment": "#64B5CD", "Consequence": "#8C8C8C",
    }
    deg = dict(H.degree())
    node_colors = [colors.get(labels.get(n, ("", ""))[0], "#8C8C8C") for n in H.nodes()]
    sizes = [80 + 60 * deg[n] for n in H.nodes()]

    fig, ax = plt.subplots(figsize=(11, 9), dpi=300)
    pos = nx.spring_layout(H, seed=42, k=0.6)
    nx.draw_networkx_edges(H, pos, ax=ax, alpha=0.25, width=0.8)
    nx.draw_networkx_nodes(H, pos, ax=ax, node_color=node_colors, node_size=sizes,
                           linewidths=0.5, edgecolors="white")
    # 只给度较高的节点加标签，避免糊成一片
    top = sorted(H.nodes(), key=lambda n: -deg[n])[:25]
    nx.draw_networkx_labels(
        H, pos, ax=ax,
        labels={n: (labels.get(n, ("", n))[1] or n)[:18] for n in top},
        font_size=7, font_family=plt.rcParams["font.sans-serif"][0],
    )
    handles = [
        plt.Line2D([0], [0], marker="o", color="w", label=k,
                   markerfacecolor=v, markersize=8)
        for k, v in colors.items()
    ]
    ax.legend(handles=handles, loc="lower left", fontsize=9, title="实体类型")
    ax.set_title(f"知识图谱网络结构（最大连通分量：{H.number_of_nodes()} 个节点、"
                 f"{H.number_of_edges()} 条边）", fontsize=13)
    ax.axis("off")
    fig.tight_layout()
    path = out_dir / "fig_network.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "figures"))
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    made = [fig_strategies(out_dir), fig_threshold(out_dir)]
    net = fig_network(out_dir)
    if net:
        made.append(net)
    for p in made:
        print("已生成", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())

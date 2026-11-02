# -*- coding: utf-8 -*-
"""出论文用的图（PNG，300 dpi）。

用法：
    python tools/make_figures.py --run-id p1_qwen7b_dev --out-dir docs/figures
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src.common import DATA, iter_csv, read_json  # noqa: E402

RUNS = DATA / "runs"
KG = DATA / "kg"

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 120
plt.rcParams["savefig.dpi"] = 300
plt.rcParams["savefig.bbox"] = "tight"


def fig_entity_f1(ev: dict, out: Path):
    rows = [r for r in ev.get("by_type", [])]
    if not rows:
        return
    rows.sort(key=lambda r: -r["f1"])
    names = [r["entity_type"] for r in rows]
    f1 = [r["f1"] * 100 for r in rows]
    p = [r["p"] * 100 for r in rows]
    r_ = [r["r"] * 100 for r in rows]
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    x = range(len(names))
    w = 0.27
    ax.bar([i - w for i in x], p, w, label="精确率 P", color="#8FAADC")
    ax.bar(list(x), r_, w, label="召回率 R", color="#FFC000")
    ax.bar([i + w for i in x], f1, w, label="F1", color="#2F5597")
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=20)
    ax.set_ylabel("百分比 (%)")
    ax.set_ylim(0, 105)
    ax.set_title("各实体类型的抽取效果", fontsize=11)
    ax.legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.5, -0.32))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25, linestyle="--")
    fig.savefig(out)
    plt.close(fig)


def fig_per_doc(by_doc: list, out: Path):
    if not by_doc:
        return
    ids = [r["doc_id"].replace("us_", "") for r in by_doc]
    g_e = [int(r["n_gold_ent"]) for r in by_doc]
    p_e = [int(r["n_pred_ent"]) for r in by_doc]
    g_r = [int(r["n_gold_rel"]) for r in by_doc]
    p_r = [int(r["n_pred_rel"]) for r in by_doc]
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.2), sharex=True)
    x = range(len(ids))
    for ax, (g, p_, title) in zip(axes, [(g_e, p_e, "实体数"), (g_r, p_r, "关系数")]):
        ax.plot(list(x), g, "o-", ms=3.5, lw=1.2, label="人工标注", color="#2F5597")
        ax.plot(list(x), p_, "s--", ms=3.5, lw=1.2, label="模型输出", color="#C00000")
        ax.set_title(f"每篇文档的{title}", fontsize=10)
        ax.set_xticks(list(x))
        ax.set_xticklabels(ids, rotation=90, fontsize=6)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.25, linestyle="--")
    axes[0].legend(frameon=False, fontsize=8)
    fig.savefig(out)
    plt.close(fig)


def fig_error_kinds(errors: list, out: Path):
    if not errors:
        return
    kinds = Counter(e.get("kind") or e.get("error_kind") or "unknown" for e in errors)
    items = kinds.most_common()
    names = [k for k, _ in items]
    vals = [v for _, v in items]
    fig, ax = plt.subplots(figsize=(6.0, 3.0))
    bars = ax.barh(names[::-1], vals[::-1], color="#C55A11")
    ax.bar_label(bars, padding=2, fontsize=8)
    ax.set_xlabel("条数")
    ax.set_title("校验不通过的类型分布", fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(out)
    plt.close(fig)


def fig_kg(nodes: list, rels: list, out: Path):
    if not nodes:
        return
    lab = Counter(n["label"] for n in nodes)
    order = ["Accident", "Ship", "Person", "Organization", "Environment",
             "Equipment", "Consequence"]
    names = [k for k in order if lab.get(k)]
    vals = [lab[k] for k in names]
    rc = Counter(r["rel"] for r in rels)
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.4))
    axes[0].bar(names, vals, color="#2F5597")
    for i, v in enumerate(vals):
        axes[0].text(i, v + 0.4, str(v), ha="center", fontsize=8)
    axes[0].set_title(f"知识图谱节点分布（共 {len(nodes)} 个）", fontsize=10)
    axes[0].tick_params(axis="x", rotation=20)
    rel_items = rc.most_common()
    axes[1].barh([k for k, _ in rel_items][::-1], [v for _, v in rel_items][::-1], color="#548235")
    axes[1].set_title(f"关系分布（共 {len(rels)} 条）", fontsize=10)
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(out)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description="生成论文插图")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out-dir", default=str(DATA.parent / "docs" / "figures"))
    args = ap.parse_args()

    run_dir = RUNS / args.run_id
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ev_path = run_dir / f"{args.run_id}_eval.json"
    if ev_path.exists():
        ev = read_json(ev_path)
        fig_entity_f1(ev, out_dir / "fig_entity_f1.png")
        print("ok", out_dir / "fig_entity_f1.png")
    by_doc_path = run_dir / f"{args.run_id}_by_doc.csv"
    if by_doc_path.exists():
        fig_per_doc(list(iter_csv(by_doc_path)), out_dir / "fig_per_doc.png")
        print("ok", out_dir / "fig_per_doc.png")
    err_path = run_dir / "errors.jsonl"
    if err_path.exists():
        import json
        errs = [json.loads(l) for l in err_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        fig_error_kinds(errs, out_dir / "fig_error_kinds.png")
        print("ok", out_dir / "fig_error_kinds.png")
    nodes_p, rels_p = KG / "nodes.csv", KG / "rels.csv"
    if nodes_p.exists() and rels_p.exists():
        fig_kg(list(iter_csv(nodes_p)), list(iter_csv(rels_p)), out_dir / "fig_kg.png")
        print("ok", out_dir / "fig_kg.png")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""把评测结果汇总成论文用的 Markdown 表格。

用法：
    python tools/report_results.py --runs p1_qwen7b_dev p0_qwen7b_dev
    python tools/report_results.py --runs p1_qwen7b_dev --md docs/results.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import DATA, iter_csv, read_json, setup_logging

RUNS = DATA / "runs"


def pct(x):
    try:
        return f"{float(x) * 100:.1f}"
    except (TypeError, ValueError):
        return "—"


def load_run(run_id: str):
    d = RUNS / run_id
    out = {"run_id": run_id, "dir": d}
    meta = d / "meta.json"
    if meta.exists():
        out["meta"] = read_json(meta)
    ev = d / f"{run_id}_eval.json"
    if not ev.exists():
        evs = sorted(d.glob("*_eval.json"))
        ev = evs[0] if evs else None
    if ev and Path(ev).exists():
        out["eval"] = read_json(ev)
    by_doc = d / f"{run_id}_by_doc.csv"
    if by_doc.exists():
        out["by_doc"] = list(iter_csv(by_doc))
    return out


def main():
    ap = argparse.ArgumentParser(description="评测结果汇总")
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--md", default="")
    args = ap.parse_args()

    logger = setup_logging("report", None)
    runs = [load_run(r) for r in args.runs]

    lines = ["# 评测结果汇总\n"]
    lines.append("## 一、运行配置\n")
    lines.append("| run_id | 策略 | 模型 | 划分 | 语料 | max_tokens |")
    lines.append("| --- | --- | --- | --- | --- | ---: |")
    for r in runs:
        m = r.get("meta", {}) or {}
        lines.append(f"| {r['run_id']} | {m.get('strategy', '—')} | {m.get('model', '—')} | "
                     f"{m.get('split', '—')} | {Path(str(m.get('corpus', '—'))).name} | "
                     f"{m.get('max_tokens', '—')} |")

    lines.append("\n## 二、总体指标（strict / loose）\n")
    lines.append("| run_id | 层级 | 匹配 | P | R | F1 | 95% CI | tp | fp | fn |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: |")
    for r in runs:
        ev = r.get("eval") or {}
        for row in ev.get("metrics", []):
            ci = ev.get("bootstrap_ci", {}).get(f"{row['level']}_{row['match']}", {})
            lo, hi = ci.get("f1", [None, None])
            ci_s = f"{pct(lo)}–{pct(hi)}" if lo is not None else "—"
            lines.append(f"| {r['run_id']} | {row['level']} | {row['match']} | "
                         f"{pct(row['p'])} | {pct(row['r'])} | {pct(row['f1'])} | {ci_s} | "
                         f"{row['tp']} | {row['fp']} | {row['fn']} |")

    lines.append("\n## 三、按实体类型（loose 匹配）\n")
    lines.append("| run_id | 实体类型 | P | R | F1 | tp | fp | fn |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for r in runs:
        ev = r.get("eval") or {}
        for row in ev.get("by_type", []):
            lines.append(f"| {r['run_id']} | {row['entity_type']} | {pct(row['p'])} | "
                         f"{pct(row['r'])} | {pct(row['f1'])} | {row['tp']} | {row['fp']} | {row['fn']} |")

    lines.append("\n## 四、按文档明细\n")
    for r in runs:
        rows = r.get("by_doc") or []
        if not rows:
            continue
        lines.append(f"\n### {r['run_id']}\n")
        lines.append("| doc_id | 国别 | 等级 | gold 实体 | pred 实体 | gold 关系 | pred 关系 |")
        lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: |")
        for row in rows:
            lines.append(f"| {row.get('doc_id')} | {row.get('country')} | {row.get('tier')} | "
                         f"{row.get('n_gold_ent')} | {row.get('n_pred_ent')} | "
                         f"{row.get('n_gold_rel')} | {row.get('n_pred_rel')} |")

    md = "\n".join(lines) + "\n"
    if args.md:
        p = Path(args.md)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md, encoding="utf-8")
        logger.info("已写出 %s（%d 行）", p, md.count("\n"))
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())

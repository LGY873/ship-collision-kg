"""把交付物汇总到 交付/ 目录，便于一次性拷到桌面或 U 盘。

只做复制与少量重命名，不改动仓库内原始产物；重复运行会覆盖同名文件。

用法：
    python tools/pack_delivery.py [--dest 交付]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import DATA, ROOT  # noqa: E402

DOCS = ROOT / "docs"

# (源文件, 交付目录内的目标相对路径)
FILES = [
    (DOCS / "论文初稿.docx", "论文初稿.docx"),
    (DOCS / "论文初稿.md", "论文初稿.md"),
    (DOCS / "答辩要点.md", "答辩要点.md"),
    (DOCS / "实验结果.md", "实验结果.md"),
    (DOCS / "kg_stats.md", "图谱数据/kg_stats.md"),
    (DOCS / "kg_queries.md", "图谱数据/kg_queries.md"),
    (DATA / "kg" / "nodes.csv", "图谱数据/nodes_33篇.csv"),
    (DATA / "kg" / "rels.csv", "图谱数据/rels_33篇.csv"),
    (DATA / "kg_all" / "nodes.csv", "图谱数据/nodes_67篇.csv"),
    (DATA / "kg_all" / "rels.csv", "图谱数据/rels_67篇.csv"),
    (DATA / "gold" / "annotation_dev_test.xlsx", "标注工作簿.xlsx"),
    (DATA / "gold" / "gold.jsonl", "图谱数据/gold_20篇人工标注.jsonl"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(ROOT / "交付"))
    args = ap.parse_args()
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    copied, missing = 0, []
    for src, rel in FILES:
        if not src.exists():
            missing.append(str(src.relative_to(ROOT)))
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied += 1

    # 插图整体拷贝
    fig_src = DOCS / "figures"
    fig_dst = dest / "figures"
    if fig_src.exists():
        fig_dst.mkdir(parents=True, exist_ok=True)
        for f in sorted(fig_src.glob("*.png")):
            shutil.copy2(f, fig_dst / f.name)
            copied += 1

    # 交付说明里的「代码仓库说明」是手写版，README 另存一份
    repo_note = dest / "代码仓库说明.md"
    readme_copy = dest / "代码仓库说明-README.md"
    if repo_note.exists() and readme_copy.exists():
        pass

    print(f"已汇总 {copied} 个文件到 {dest}")
    if missing:
        print("缺失（跳过）：")
        for m in missing:
            print("  -", m)
    total = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
    print(f"交付目录合计 {total / 1024 / 1024:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""把可运行源码（含最小数据集）打包到 交付/源码/，供随论文一起提交。

包含：代码、配置、提示词、本体与 Schema、脚本、README、以及复现实验所需的最小数据
（corpus_us_seed_split.jsonl、gold、seed、图谱 CSV、解析报告）。
排除：.venv、.git、data/pdf、data/runs、data/logs、其余大语料。

用法：
    python tools/pack_source.py            # 复制到 交付/源码
    python tools/pack_source.py --zip      # 同时生成 交付/源码.zip
"""
from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import ROOT  # noqa: E402

# 整个目录原样复制
DIRS = [
    "src",
    "tools",
    "prompts",
    "schemas",
    "ontology",
    "configs",
    ".vscode",
]

# 根目录下的单文件
FILES = [
    "README.md",
    "MANIFEST.md",
    "requirements.txt",
    "run_offline.ps1",
    "run_pipeline.ps1",
    ".editorconfig",
    ".gitignore",
]

# 复现所需的最小数据（相对路径）
DATA_FILES = [
    "data/corpus/corpus_us_seed_split.jsonl",
    "data/corpus/splits_us.json",
    "data/seed/seed.csv",
    "data/reports/parse_report.csv",
    "data/gold/gold.jsonl",
    "data/gold/fewshot.jsonl",
    "data/gold/gold_doc_ids.txt",
    "data/gold/annotation_dev_test.xlsx",
    "data/kg/nodes.csv",
    "data/kg/rels.csv",
    "data/kg_all/nodes.csv",
    "data/kg_all/rels.csv",
]

# 复制时跳过的文件名模式
SKIP = {"__pycache__", ".pytest_cache", ".venv", ".git"}

RUNBOOK = """# 源码运行说明

## 1. 环境

- Python 3.10+（开发环境为 3.12）
- 本地大模型：Ollama，`ollama pull qwen2.5:7b-instruct`
- 依赖：`pip install -r requirements.txt`

建议用虚拟环境：

```powershell
cd 源码
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
```

## 2. 先做环境自检

```powershell
python tools/check_env.py      # 检查依赖与数据是否齐全
python tools/smoke_test.py     # 离线回归测试，18 项断言
```

`smoke_test.py` 不调用大模型，几秒即可跑完；全绿说明代码与数据都对。

## 3. 复现实验（需要大模型，耗时较长）

```powershell
# 主实验：dev 33 篇抽取（约 40 分钟，7B 模型本机）
python src/llm/runner.py --strategy p1 --model qwen2.5:7b-instruct --split dev --run-id p1_qwen7b_dev

# 后处理：结构校验 + 事故挂载修复 + 证据一致性
python src/llm/postprocess.py --run-id p1_qwen7b_dev --corpus data/corpus/corpus_us_seed_split.jsonl

# 评测：三档匹配口径 + 95% 置信区间
python src/eval/evaluate.py --run-id p1_qwen7b_dev

# 图谱构建
python src/kg/build_nodes.py --runs p1_qwen7b_dev
```

只想快速验证流程，可加 `--limit 3` 只跑 3 篇。

## 4. 出论文表格与插图

```powershell
python tools/report_results.py --runs p1_qwen7b_dev   # 四张结果表
python tools/kg_stats.py --md                          # 图谱统计
python tools/make_figures.py --run-id p1_qwen7b_dev    # 四张基础图
python tools/kg_queries_local.py --run all --md        # 8 条查询（不依赖 Neo4j）
```

## 5. 环境变量提示（Windows）

- 中文输出乱码：`$env:PYTHONIOENCODING='utf-8'`
- matplotlib 缓存目录不可写时：`$env:MPLCONFIGDIR="$PWD\\data\\logs\\mpl"`

## 6. 目录速览

| 目录 | 内容 |
| --- | --- |
| `src/crawl` | 报告抓取 |
| `src/prep` | 解析、清洗、分节截断、语料与划分构建 |
| `src/llm` | 提示词、模型客户端、批量抽取、后处理校验 |
| `src/eval` | 三档匹配口径、指标、bootstrap 置信区间 |
| `src/kg` | 图谱节点/关系构建、Neo4j 导入、Cypher 查询 |
| `tools/` | 自检、冒烟测试、标注工作簿、统计、出图、打包 |
| `prompts/` | p0/p1/p2 三套提示词 |
| `ontology/` | 7 类实体、12 类关系的本体定义 |

## 7. 已知限制

- 语料为 NTSB 报告正文截断到 12000 字符（原始 PDF 未随附，正文较原文损失约 40–60%）。
- 人工标注 20 篇（全部位于 dev），test 集 34 篇未标注。
- Neo4j 相关脚本需自行安装数据库；不装也不影响复现实验，`tools/kg_queries_local.py` 用 CSV 直接算。
"""


def copy_tree(src: Path, dst: Path) -> int:
    n = 0
    for item in src.rglob("*"):
        if any(part in SKIP for part in item.parts):
            continue
        if item.is_dir():
            continue
        rel = item.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(ROOT / "交付" / "源码"))
    ap.add_argument("--zip", action="store_true", help="同时生成 交付/源码.zip")
    args = ap.parse_args()

    dest = Path(args.dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    copied, missing = 0, []
    for d in DIRS:
        src = ROOT / d
        if src.exists():
            copied += copy_tree(src, dest / d)
    for f in FILES:
        src = ROOT / f
        if src.exists():
            shutil.copy2(src, dest / f)
            copied += 1
        else:
            missing.append(f)
    for f in DATA_FILES:
        src = ROOT / f
        if src.exists():
            target = dest / f
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            copied += 1
        else:
            missing.append(f)

    (dest / "源码运行说明.md").write_text(RUNBOOK, encoding="utf-8")
    copied += 1

    size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
    print(f"源码已打包：{copied} 个文件，{size / 1024 / 1024:.1f} MB → {dest}")
    if missing:
        print("缺失（跳过）：", "；".join(missing))

    if args.zip:
        zp = dest.parent / "源码.zip"
        if zp.exists():
            zp.unlink()
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(dest.rglob("*")):
                if f.is_file():
                    zf.write(f, f.relative_to(dest.parent))
        print(f"压缩包：{zp}（{zp.stat().st_size / 1024 / 1024:.1f} MB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

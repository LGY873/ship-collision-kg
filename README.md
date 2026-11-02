# 船舶碰撞事故知识图谱 · 工程脚手架

> 配套《基于 LLM 的船舶碰撞事故知识图谱构建 —— 毕业设计实施方案》。
> 目标：**今天之内**跑通「一条报告 → 一段 JSON → 一个子图」，之后再谈规模与精度。

---

## 0. 现在就已经跑通的部分

这套代码不是空壳，下面这些结果是在本地真实跑出来的（2026-11-02 全量重跑）：

| 产物 | 路径 | 内容 |
|---|---|---|
| 种子表 | `data/seed/seed.csv` | **285 起**碰撞事故（美国 182 / 英国 103；严格 collision 129 起、触碰类 156 起） |
| 全文语料 | `data/corpus/corpus_us_seed_split.jsonl` | 167 篇 NTSB 全文，**train 100 / dev 33 / test 34**（`splits_us.json`） |
| 主实验 | `data/runs/p1_qwen7b_dev/` | dev 33 篇抽取 + 后处理 + 评测，**关系 F1 0.555 / 实体 F1 0.784**（严格口径，20 篇 gold） |
| 实验报告 | [docs/实验结果.md](docs/实验结果.md) | 主结果、按类型、消融、错误分析、局限，全部带 95% CI |
| 图谱产物 | `data/kg/nodes.csv`、`rels.csv` | 242 节点 / 254 边，属性完整度 100% |
| 图表 | `docs/figures/` | 实体类型 F1、按文档对比、错误类型、图谱分布（300 dpi） |
| 链路自测 | `tools/smoke_test.py` | 18 项断言：分节截断 → 后处理 → 评测口径 → 图谱合并，离线全过 |

论文要用的表格与图都能一条命令重新生成，命令见 [docs/实验结果.md](docs/实验结果.md) 第 8 节。

---

## 1. 三分钟上手

```powershell
# ① 进目录
cd ship-collision-kg

# ② 装依赖（建议虚拟环境）
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# ③ 解决 Windows 中文乱码（每个新终端都要设）
$env:PYTHONIOENCODING = "utf-8"

# ④ 环境自检
python tools/check_env.py

# ⑤ 一键离线全链路（种子表 → 语料 → 划分 → 冒烟 → 评测 → 图谱 CSV）
.\run_offline.ps1

# ⑥ 接上真模型（先确认 Ollama 已启动、已 pull 模型）
python src/llm/client.py --model qwen2.5:7b-instruct --prompt "Return JSON only: {\"ok\": true}"
```

第 ⑥ 步能返回 JSON，说明推理链路通了，可以往下走。

---

## 2. 目录结构与职责

```
ship-collision-kg/
├─ README.md                     ← 本文件（逐日操作手册）
├─ MANIFEST.md                   全部文件清单（含行数统计）
├─ run_offline.ps1               一键离线链路（不联网、不调模型）
├─ run_pipeline.ps1              一键在线链路（解析→抽取→评测→图谱）
├─ requirements.txt
├─ configs/
│  ├─ models.json                模型清单与推理参数
│  └─ crawl.json                 抓取参数（限速、超时、重试）
├─ ontology/ontology.json        本体唯一真源（7 类实体 / 12 类关系 / 枚举 / C1-C10 约束）
├─ schemas/extraction.schema.json 输出 JSON Schema
├─ prompts/
│  ├─ p0_zeroshot.txt            零样本
│  ├─ p1_ontology.txt            本体约束（核心）
│  └─ p2_ontology_fewshot.txt    本体 + 少样本
├─ src/
│  ├─ common.py                  路径、日志、JSONL、编号/日期/经纬度解析
│  ├─ crawl/build_seed.py        三份 Excel → seed.csv          ✅ 已验证
│  ├─ crawl/fetch_reports.py     按编号抓 PDF（可断点续跑）
│  ├─ prep/parse_pdf.py          PDF/HTML/TXT → corpus.jsonl    ✅ 已验证（TXT 通路）
│  ├─ prep/clean_text.py         R1—R12 清洗规则                ✅ 已验证
│  ├─ prep/segment.py            分节、分句、抽取向文本
│  ├─ prep/build_corpus_from_fields.py  字段级兜底语料          ✅ 已验证
│  ├─ prep/split_dataset.py      6:2:2 分层划分                 ✅ 已验证
│  ├─ llm/client.py              Ollama / OpenAI 兼容调用
│  ├─ llm/build_prompt.py        用本体自动填提示词             ✅ 已验证
│  ├─ llm/runner.py              批量抽取（断点续跑）
│  ├─ llm/validate.py            轻量 JSON Schema 校验
│  ├─ llm/postprocess.py         修复→校验→对齐→归一→约束→去重  ✅ 已验证
│  ├─ eval/metrics.py            P/R/F1（严格 / 宽松 / 部分重叠 三档 + bootstrap CI）
│  ├─ eval/evaluate.py           评测主脚本                    ✅ 已验证
│  ├─ kg/build_nodes.py          三元组 → nodes.csv/rels.csv    ✅ 已验证
│  ├─ kg/load_neo4j.py           导入 Neo4j 5.x（属性摊平写入）
│  └─ kg/queries.py              8 条分析查询（Neo4j 版）
├─ tools/
│  ├─ check_env.py               环境自检                      ✅
│  ├─ smoke_test.py              离线全链路自测（18 项断言）    ✅
│  ├─ make_fake_report.py        造一份假报告测解析            ✅
│  ├─ make_gold_template.py      生成标注模板（可预标注）       ✅
│  ├─ make_annotation_workbook.py 标注 Excel（说明/文档/实体/关系）
│  ├─ make_fewshot.py            p2 用的少样本示例（含泄漏检查） ✅
│  ├─ fix_gold_spans.py          校对 gold 的 span 原文一致性   ✅
│  ├─ kg_stats.py                图谱规模/度分布/属性完整度     ✅
│  ├─ kg_queries_local.py        8 条查询的不依赖 Neo4j 实现    ✅
│  ├─ report_results.py          评测结果 → Markdown 表格      ✅
│  ├─ make_figures.py            论文插图（300 dpi，中文字体）  ✅
│  └─ kappa.py                   双标一致性 Cohen's κ          ✅
└─ data/                         所有数据产物（不进 git）
```

---

## 3. Day 0：环境（半天）

### 3.1 Python 与依赖

```powershell
python --version          # 3.10—3.12 均可，优先 3.11
git init                  # 开工就建仓，方便回滚与打 tag
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> PDF 解析依赖 `pdfplumber` 与 `PyMuPDF`。装不上就先只跑字段级语料（路径 B），不影响后面所有步骤。

### 3.2 Ollama（本地推理）

```powershell
ollama pull qwen2.5:7b-instruct
ollama pull llama3.1:8b-instruct
ollama list
```

显存 ≤8 GB 时只拉 7B/8B；14B 用 q4_K_M 或在 12 月前用云端 API 跑（见方案 6.1）。

### 3.3 Neo4j（第 16 天再装也来得及）

装 Neo4j Desktop 5.x（需 JDK 17），建库，记下 bolt 地址与密码，然后：

```powershell
$env:NEO4J_URI="bolt://localhost:7687"
$env:NEO4J_USER="neo4j"
$env:NEO4J_PASSWORD="你的密码"
```

### 3.4 自检

```powershell
python tools/check_env.py
```

期望看到：Python 版本 OK、`openpyxl` OK、`seed.csv` 285 行、Ollama 列出模型。缺什么它会直接说。

---

## 4. 逐日操作（18 天）

> 每天的“验收”都写成可检查的一句话。做完打勾，做不完就按“卡住怎么办”处理，**不要死磕**。
> 关键路径只有一条：**语料 → 标注 → 实验 → 论文**。图谱可以并行，标注不能并行。

### Day 0（10.21）环境与冒烟

见第 3 节。验收：`python tools/check_env.py` 里 Python、openpyxl、seed.csv 三项 OK；Ollama 能列出模型。

### Day 1（10.22）复现种子表

```powershell
python src/crawl/build_seed.py `
  --us "C:\Users\18191\Desktop\美国海事汇总(1).xlsx" `
  --uk "C:\Users\18191\Desktop\英国海事(1).xlsx"
```

期望输出：

```
US: 684 行 -> 461 起事故
UK: 566 行 -> 464 起事故
合并后事故总数：925
碰撞相关事故：285
写出 data/seed/seed.csv：285 行（US 182 / UK 103；A 级 129 / B 级 156）
日期解析成功 277/285；经纬度有效 169/285
```

- **验收**：285 行；A 129 / B 156；日期解析率 ≥95%。
- 想看全部 925 起：加 `--all`。
- 日期解析失败的 8 条：用 `date_raw` 列人工确认后手填（论文写明“人工校正 8 条”即可）。

### Day 2（10.23）抓取先试 3 条

```powershell
python src/crawl/fetch_reports.py --source UK --limit 3 --dry-run
```

期望：打印 3 条 `NO x/yyyy -> https://...pdf`。**先确认 URL 对，再下载。**

```powershell
python src/crawl/fetch_reports.py --source UK --limit 3
```

- **验收**：`data/pdf/uk/` 出现 3 个 PDF；`data/manifest.csv` 对应 3 行 `status=ok` 且有 sha256。
- **卡住怎么办**：`--dry-run` 解析不出 URL，说明站点改版，直接走 Day 4 的手工兜底，不要改爬虫硬磕。

### Day 3—4（10.24—10.25）批量抓取

```powershell
python src/crawl/fetch_reports.py --source US
python src/crawl/fetch_reports.py --source UK
python src/crawl/fetch_reports.py            # 补漏，已成功的会自动跳过
```

- 每条间隔 1.5—3 秒，285 条约 15—25 分钟；晚上跑，避免白天被限流。
- 中断了直接重跑（断点续跑）。
- **验收**：成功 ≥240 篇（85%）。
- **兜底**：失败项手工查 PDF 地址，写成 `urls.csv` 再跑：

```csv
accident_no,url
NO 12/2018,https://assets.publishing.service.gov.uk/media/xxx/xxx.pdf
```

```powershell
python src/crawl/fetch_reports.py --urls urls.csv
```

### Day 5（10.26）语料核验与冻结（M1）

```powershell
python -c "import csv;rows=list(csv.DictReader(open('data/manifest.csv',encoding='utf-8-sig')));from collections import Counter;print(Counter(r['status'] for r in rows))"
```

- **验收**：`Counter({'ok': 240+})`；随机打开 5 个 PDF 确认是碰撞报告。
- 打 tag：`git add -A; git commit -m "data-v1"`。
- 若成功率 <70%：立刻决定走路径 B（字段级语料），当天就能继续，不要拖到 Day 6 再纠结。

### Day 6（10.27）解析

```powershell
python src/prep/parse_pdf.py --include-txt
```

期望：每篇一行日志，显示 `pdfplumber / pymupdf`、字符数、`分节=True`。

- **验收**：`data/corpus/corpus_pdf.jsonl` 篇数 ≥240；抽 3 篇通读，无页眉页脚、无目录残留。
- 统计 `sectioned=False` 的比例（论文可写“X% 的报告可自动分节”）。
- **卡住怎么办**：字符数 <200 的多半是扫描件，先跳过并在论文注明比例，不要为 10 篇去做 OCR。

### Day 7（10.28）清洗质检

```powershell
python src/prep/clean_text.py --input data\pdf\uk\NO_20_2005.txt
python src/prep/segment.py --input data\pdf\uk\NO_20_2005.txt
```

期望：

```
字符数 1400 -> 1251（保留 89.4%）
命中：{'R1': 4, 'R5': 3, ...}
sections: ['synopsis', 'factual', 'analysis', 'conclusions']  sectioned= True
sentences: 23
```

- **验收**：字符保留率在 0.6—0.9；分节能识别出 Synopsis/Analysis/Conclusions。

### Day 8（10.29）语料定稿与划分

```powershell
# 二选一：全文语料 或 字段级兜底语料
python src/prep/split_dataset.py --corpus data\corpus\corpus_pdf.jsonl
# python src/prep/split_dataset.py --corpus data\corpus\corpus_fields.jsonl
```

期望：`文档：train=171 dev=57 test=57`。

- **验收**：`splits.json` 存在；同一事故不在两个 split（脚本已保证）。
- 从这一刻起，**只用 `corpus_*_split.jsonl`**，不要再用回原文件。

### Day 9（10.30）本体定义

照 `ontology/ontology.json` 过一遍，确认三件事：

1. 7 类实体是否够用（试标 3 篇，有没有信息无处安放）；
2. 12 类关系方向是否清晰（统一“以事故为起点向外指”）；
3. 枚举是否够用（`accident_type`、`env_category`…）。

改本体时**必须同步** `schemas/extraction.schema.json` 里的枚举，两处不一致会把模型输出全拦掉。

### Day 10（10.31）本体冻结 + 提示词跑通 + 5 篇试标

上午冻结本体，下午三件事：

```powershell
# ① 渲染提示词，确认本体/枚举/规则都进去了
python src/llm/build_prompt.py --strategy p1 --dump data\logs\p1.txt

# ② 模型自测
python src/llm/client.py --model qwen2.5:7b-instruct

# ③ 5 篇试跑
python src/llm/runner.py --strategy p1 --model qwen2.5:7b-instruct --split dev --limit 5 --run-id try_p1
```

- **验收**：`data/runs/try_p1/raw/` 有 5 个 json，每个是完整 JSON（不是半截）。
- 若 5 篇里 ≥2 篇 JSON 不完整：`--max-tokens 4096` 重跑，再查提示词是否太长。
- 晚上：读 `docs/annotation_guide.md`，用 5 篇做试标，按规范修一遍。

### Day 11（11.01）预标注 + 修订 75 篇

```powershell
# 01: 先让模型把 dev 全跑完（33 篇，约 35 分钟），作为预标注来源
python src/llm/runner.py --strategy p1 --model qwen2.5:7b-instruct --split dev --run-id p1_qwen7b_dev

# 02: 后处理 + 转成标注模板
python src/llm/postprocess.py --run-id p1_qwen7b_dev
python tools/make_gold_template.py --split dev --n 43 --run-id p1_qwen7b_dev --out data\gold\dev_pred.jsonl
```

然后人工在 `dev_pred.jsonl` 上“删、改、补”，目标 75 篇（保存为 `data/gold/gold.jsonl`）。

- **验收**：每篇 ≥8 实体、≥5 关系（短报告可少，单独记录）。

### Day 12（11.02）双标 25 篇

```powershell
python tools/make_gold_template.py --split dev --n 25 --no-pred --out data\gold\annotator_a.jsonl
copy data\gold\annotator_a.jsonl data\gold\annotator_b.jsonl
```

两份**各自独立**标（互不可见），标完合并进 `gold.jsonl` 的对应文档。

- **验收**：25 篇双标完成；双方都没看过对方的结果。

### Day 13（11.03）一致性检验（M2）

```powershell
python tools/kappa.py --a data\gold\annotator_a.jsonl --b data\gold\annotator_b.jsonl
```

| kappa | 动作 |
|---|---|
| ≥0.75 | 进入实验 |
| 0.60—0.75 | 补规范说明，重点复核分歧样本 |
| <0.60 | 改规范，回标（今天发现比答辩前发现好） |

分歧由第三人/导师仲裁，仲裁结果写进 gold。**M2 检查点：本体冻结 + 100 篇标注 + kappa ≥0.75。**

### Day 14（11.04）dev 20 篇三策略对比

```powershell
python src/llm/runner.py --strategy p0 --model qwen2.5:7b-instruct --split dev --limit 20 --run-id cmp_p0
python src/llm/runner.py --strategy p1 --model qwen2.5:7b-instruct --split dev --limit 20 --run-id cmp_p1
python src/llm/runner.py --strategy p2 --model qwen2.5:7b-instruct --split dev --limit 20 --run-id cmp_p2
python src/llm/postprocess.py --run-id cmp_p1
python src/eval/evaluate.py --run-id cmp_p1 --split dev
```

- **验收**：P1 的类型准确率肉眼可见高于 P0（看 `triples.jsonl` 里还有没有 `vessel`、`thing` 这种自由类型）。
- 没差异 → **先改提示词，不要换模型**。

### Day 15（11.05）9 组全量（挂机）

```powershell
$models = "qwen2.5:7b-instruct","llama3.1:8b-instruct","glm4:9b-chat"
foreach ($m in $models) { foreach ($s in "p0","p1","p2") {
  python src/llm/runner.py --strategy $s --model $m --split test
}}
```

- 每篇 20—80 秒（7B 本机量化后），34 篇 ≈ 20—45 分钟/组，9 组要跑一个通宵。
- **验收**：`data/runs/` 下 9 个目录，每个 34 篇；中断重跑自动跳过（原子写，不会留下半截 JSON）。
- 同时（读模型输出的间隙）做 `build_nodes.py`，先用已有结果把图谱管线跑通。

### Day 16（11.06）后处理 + 评测（M3 数据部分）

```powershell
Get-ChildItem data\runs -Directory | Where-Object { $_.Name -match "^(p0|p1|p2)_" } | ForEach-Object {
  python src/llm/postprocess.py --run-id $_.Name
  python src/eval/evaluate.py --run-id $_.Name --split test
}
```

期望（终局表的样子）：

```
entity   loose  P=0.781  R=0.742  F1=0.761  (macro F1=0.69)
relation loose  P=0.643  R=0.581  F1=0.610  (macro F1=0.55)
```

- **验收**：9 份 `*_eval.csv`；同一配置重跑一次，F1 差异 <0.5%。
- 结果自动落盘：`data/runs/{run_id}/{run_id}_eval.csv` / `_by_type.csv` / `_eval.json`。

### Day 17（11.07）错误分析 + 图谱 + 截图

上午错误分析：抽 30 篇（从 `errors.jsonl` 与 `triples.jsonl`），按 7 类归因，填 `docs/error_analysis.md`。

下午图谱：

```powershell
python src/kg/build_nodes.py --runs p1_qwen2.5_7b_instruct_test
python src/kg/load_neo4j.py
python src/kg/queries.py --list
python src/kg/queries.py --run q1 --limit 20
```

- **验收**：节点 ≥8000、边 ≥5000；`q1` 出 Top 20；Browser 里 `q8` 能出单事故子图。
- 截图：`q8` 案例子图 1 张、`q1` 条形图数据、`q7` 路径图 1 张。

### Day 18（11.08）初稿（M3）

论文按“第 3 章 → 第 5 章 → 第 6 章 → 第 4 章 → 第 2 章 → 第 1 章 → 第 7 章”的顺序写，
图表直接从第 6 节的映射表取，**不要手抄数字**。

- **验收**：≥2.5 万字；图 ≥22 幅；表 ≥15 张；9 组结果全在表里；参考文献按 GB/T 7714 重排。
- 当天交导师，并约中期检查的沟通时间。


## 5. 命令速查

| 目的 | 命令 |
|---|---|
| 一键离线全链路 | `.\run_offline.ps1` |
| 一键在线链路 | `.\run_pipeline.ps1 -Limit 5 -Split dev` |
| 环境自检 | `python tools/check_env.py` |
| 种子表 | `python src/crawl/build_seed.py --us ... --uk ...` |
| 抓 PDF（试跑） | `python src/crawl/fetch_reports.py --limit 3 --dry-run` |
| 抓 PDF（正式） | `python src/crawl/fetch_reports.py --source US` |
| 解析 | `python src/prep/parse_pdf.py --include-txt` |
| 清洗单篇 | `python src/prep/clean_text.py --input 文件名` |
| 字段级兜底语料 | `python src/prep/build_corpus_from_fields.py` |
| 划分 | `python src/prep/split_dataset.py --corpus ...` |
| 渲染提示词 | `python src/llm/build_prompt.py --strategy p1 --dump out.txt` |
| 模型自测 | `python src/llm/client.py --model qwen2.5:7b-instruct` |
| 批量抽取 | `python src/llm/runner.py --strategy p1 --model ... --split dev --limit 5` |
| 后处理 | `python src/llm/postprocess.py --run-id xxx` |
| 评测 | `python src/eval/evaluate.py --run-id xxx --split test` |
| 标注重模板 | `python tools/make_gold_template.py --split dev --n 43 --no-pred` |
| 一致性 | `python tools/kappa.py --a A.jsonl --b B.jsonl` |
| 图谱 CSV | `python src/kg/build_nodes.py --runs xxx` |
| 导入 Neo4j | `python src/kg/load_neo4j.py` |
| 分析查询 | `python src/kg/queries.py --run q1` |

---

## 6. 产物 → 论文图表映射

| 论文位置 | 数据来源 | 生成方式 |
|---|---|---|
| 表 3-1 数据结构核查 | `data/seed/seed.csv` 统计 | `pandas.read_csv(...).describe()` |
| 表 3-2 字段完整率 | 三份原始 Excel | `profile_xlsx.py`（方案附带） |
| 表 3-3 碰撞子集 | `seed.csv` 的 `collision_tier` | `value_counts()` |
| 表 3-4 数据集划分 | `splits.json` | 直接读 |
| 图 3-2 语料长度分布 | `corpus_*.jsonl` 的 `n_chars` | `matplotlib.hist` |
| 表 4-x 实体/关系定义 | `ontology.json` | 一半手动整理（论文要中文表述） |
| 表 5-2 结果总表 | 9 份 `*_eval.csv` | 横向合并后按 F1 排序 |
| 图 5-2 F1 对比 | 同上 | 分组柱状图 |
| 表 5-3 错误类型 | `errors.jsonl` + 人工归类 | 手工统计 |
| 表 6-1 图谱规模 | `build_nodes.py` 日志 | 节点/边/分布 |
| 图 6-3 高频致因 | `q1` 结果 | 条形图 |
| 图 6-4 共现网络 | `q2` 结果 | Gephi / pyvis |
| 图 6-7 案例子图 | `q8` | Neo4j Browser 截图 |

---

## 7. 常见问题

**Q1：`--dry-run` 一条 URL 都解析不出来。**
站点改版了。不要改爬虫硬磕：用浏览器打开报告页，把 PDF 地址抄进 `urls.csv`（事故编号, URL），`--urls urls.csv` 照样批量下载。

**Q2：PDF 解析出来是空的。**
扫描件。`parse_pdf.py` 会打 `正文过短` 警告；把这些篇目列出来，论文里说明“扫描件 X 篇未纳入”，或用 PaddleOCR 单独处理（半天工作量）。

**Q3：模型输出 JSON 被截断。**
`max_tokens` 不够：`runner.py --max-tokens 4096`（默认已是 4096）。同时确认提示词没把整篇 2 万字报告塞进去（`segment.py` 按「原因 40% > 分析 30% > 事实 30% > 结论 10%」的预算分节截断，且截断落在句末，不是简单掐头）。

**Q4：`UnicodeEncodeError: 'gbk' codec ...`**
Windows 控制台编码问题。每次新开终端先 `$env:PYTHONIOENCODING="utf-8"`；脚本内部已全部显式 `encoding="utf-8"`。

**Q5：评测结果全是 0。**
九成是 `doc_id` 对不上：gold 来自 `corpus_us_seed_split.jsonl`，预测却跑了 `corpus_fields_split.jsonl`。**三份脚本的默认语料已统一为 `corpus_us_seed_split.jsonl`**；换语料时三处一起换。

**Q6：`split` 字段为空导致评测 0 篇。**
划分脚本输出的是 `corpus_*_split.jsonl`，别用回原文件。

**Q7：Neo4j 报 `Invalid input 'ON'`。**
用了 4.x 语法。5.x 约束写法是 `CREATE CONSTRAINT ... FOR (n:Accident) REQUIRE n.gid IS UNIQUE`，脚本里已经写对，照抄教程时注意。

**Q8：14B 模型跑不动。**
换 `qwen2.5:7b-instruct`；或 14B 只在 100 篇上用云端 API 跑一组（成本几元）。论文里注明量化等级。

**Q9：kappa 只有 0.5。**
规范里“实体边界”没定死。按 `docs/annotation_guide.md` 的“最长名词短语、不含标点”重标 5 篇试标，统一后再批量。

**Q10：图谱节点数远少于预期。**
实体没归一：`Miss Natalie` 与 `MISS NATALIE` 成了两个节点。`postprocess.py` 已做小写归一，若仍不足，检查是否 `--min-evidence` 过滤太狠。

---

## 8. 想改东西时改哪里

| 需求 | 改哪里 | 注意 |
|---|---|---|
| 换模型 | `configs/models.json` + `runner.py --model` | 提示词、参数不变，才是公平对比 |
| 加关系类型 | `ontology/ontology.json` 的 `relations` + `schemas/extraction.schema.json` 的 enum | 两处必须同时改 |
| 改实体枚举 | `ontology.json` 的 `enums` + schema 同名 enum | 改完要重跑提示词渲染 |
| 调提示词 | `prompts/*.txt` | 大改就换 strategy 名，别覆盖旧的（否则实验结果对不上） |
| 加中文语料 | `corpus` 里加 `lang=zh` 的记录 | 中文单独作“跨语言测试集”，不要混进原 test |
| 换评测口径 | `src/eval/metrics.py` 的 `entity_set` / `relation_set` | 改了要在论文里重新定义指标 |

---

## 9. 论文里的“可复现性声明”模板

> 本文所有实验基于 commit `<git rev-parse --short HEAD>`，语料版本 `corpus-v1`（sha256 见 `data/manifest.csv`），
> 本体版本 `1.0`，提示词版本 `p1-v1`。推理参数固定为 temperature=0、top_p=1.0、max_tokens=2048、seed=42。
> 每个实验的结果保存在 `data/runs/{run_id}/`，包含模型原始输出、清洗后三元组与评测明细，可逐条复算。

---

## 10. 错误分析模板（Day 17 填）

```markdown
## 错误类型统计（随机 30 篇）
| 类型 | 数量 | 占比 | 典型例子（原文 → 模型输出 → 正确标注） |
|---|---|---|---|
| 漏抽 FN | | | |
| 多抽 FP | | | |
| 类型错 | | | |
| 边界错 | | | |
| 关系方向错 | | | |
| 关系类型错 | | | |
| 证据伪造 | | | |

## 三点发现
1. …
2. …
3. …
```

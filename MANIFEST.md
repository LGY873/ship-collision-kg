# 文件清单

> 由 `make_manifest.py` 生成；Python 行数不含空行。

## 全部文件

| 路径 | 行数 | 大小 | 作用 |
|---|---:|---:|---|
| `.gitignore` | — | 0.3 KB | Git 忽略规则 |
| `configs/crawl.json` | — | 0.7 KB | 抓取参数（限速、超时、重试）与划分比例 |
| `configs/models.json` | — | 0.5 KB | 模型清单与推理参数 |
| `data/corpus/corpus_fields.jsonl` | — | 1159.7 KB | 字段级兜底语料 285 篇 |
| `data/corpus/corpus_fields_split.jsonl` | — | 1160.9 KB | 带 split 的字段级语料 |
| `data/corpus/corpus_us_extra_collision.jsonl` | — | 3988.0 KB | 种子外碰撞报告 56 篇（可扩充数据集） |
| `data/corpus/corpus_us_full.jsonl` | — | 17973.4 KB | 美国报告全文本 448 篇（实测产物，含种子内外标记） |
| `data/corpus/corpus_us_seed.jsonl` | — | 6266.8 KB | 种子内美国碰撞事故 167 篇（直接可做实验） |
| `data/corpus/splits.json` | — | 5.8 KB | 划分清单：doc_id → train/dev/test |
| `data/gold/README.md` | — | 2.3 KB | gold 目录说明与标注文件格式 |
| `data/reports/_probe.csv` | — | 4.1 KB | — |
| `data/reports/parse_report.csv` | — | 62.2 KB | 599 个 PDF 的逐文件解析报告 |
| `data/seed/seed.csv` | — | 462.6 KB | 种子表：285 起碰撞事故（美 182 / 英 103） |
| `data/urls.template.csv` | — | 0.2 KB | 手工 URL 映射模板（抓取失败时兜底） |
| `docs/18天操作卡.docx` | — | 40.4 KB | 可打印的逐日操作卡 |
| `docs/annotation_guide.md` | — | 6.4 KB | 标注规范：边界、关系方向、七条细则、JSON 格式 |
| `docs/error_analysis.md` | — | 2.4 KB | 错误分析模板（Day 17 填） |
| `ontology/ontology.json` | — | 7.0 KB | 本体唯一真源：7 类实体、12 类关系、枚举、C1—C10 约束 |
| `prompts/p0_zeroshot.txt` | — | 1.1 KB | P0 零样本提示词 |
| `prompts/p1_ontology.txt` | — | 1.5 KB | P1 本体约束提示词（核心实验） |
| `prompts/p2_ontology_fewshot.txt` | — | 1.5 KB | P2 本体约束 + 少样本提示词 |
| `README.md` | — | 21.7 KB | 总手册：环境、18 天逐日命令、排错、论文图表映射 |
| `requirements.txt` | — | 0.1 KB | Python 依赖（PyMuPDF 用于 PDF 解析） |
| `run_offline.ps1` | — | 2.6 KB | 一键离线链路（种子→语料→划分→冒烟→评测→图谱 CSV） |
| `run_pipeline.ps1` | — | 3.2 KB | 一键在线链路（解析→抽取→后处理→评测→图谱） |
| `schemas/extraction.schema.json` | — | 1.9 KB | 抽取结果 JSON Schema（后处理硬校验） |
| `src/common.py` | 169 | 6.2 KB | 公共工具：日志、JSONL、编号归一、日期/经纬度解析 |
| `src/crawl/build_seed.py` | 183 | 8.4 KB | 三份 Excel → 事故级 seed.csv |
| `src/crawl/fetch_reports.py` | 193 | 9.0 KB | 按事故编号抓 PDF（限速、断点续跑、manifest） |
| `src/eval/evaluate.py` | 97 | 4.6 KB | 评测主脚本，输出 CSV/JSON 明细 |
| `src/eval/metrics.py` | 68 | 2.6 KB | 实体/关系 P/R/F1，严格与宽松两套口径 |
| `src/kg/build_nodes.py` | 115 | 5.0 KB | 三元组 → nodes.csv / rels.csv（带溯源属性） |
| `src/kg/load_neo4j.py` | 94 | 4.5 KB | 导入 Neo4j 5.x（约束、索引、批量 MERGE） |
| `src/kg/queries.py` | 120 | 4.2 KB | 8 条分析查询（高频致因、共现、国别差异…） |
| `src/llm/build_prompt.py` | 88 | 3.8 KB | 读取本体自动填充提示词模板 |
| `src/llm/client.py` | 114 | 4.9 KB | Ollama / OpenAI 兼容调用层（标准库实现） |
| `src/llm/postprocess.py` | 188 | 8.5 KB | 修复→校验→原文对齐→归一→关系约束→去重 |
| `src/llm/runner.py` | 91 | 4.3 KB | 批量抽取（断点续跑、逐篇落盘） |
| `src/llm/validate.py` | 63 | 2.8 KB | 轻量 JSON Schema 校验器（不依赖第三方库） |
| `src/prep/build_corpus_from_fields.py` | 105 | 4.3 KB | 兜底路径 B：用字段拼事故短文语料 |
| `src/prep/clean_text.py` | 210 | 7.7 KB | R1—R12 文本清洗（含 PDF 缺字形的 U+FFFD 处理） |
| `src/prep/parse_batch.py` | 170 | 7.8 KB | 整目录批量解析：按案件号/报告号对齐种子表（599 篇实测） |
| `src/prep/parse_pdf.py` | 132 | 6.0 KB | PDF/HTML/TXT → corpus.jsonl（三级解析兜底 + 简报全文回退） |
| `src/prep/segment.py` | 97 | 4.0 KB | 分节（Synopsis/Analysis/Conclusions）与分句（带偏移） |
| `src/prep/split_dataset.py` | 93 | 4.1 KB | 按事故 6:2:2 分层划分（171/57/57） |
| `tools/check_env.py` | 89 | 3.3 KB | 环境自检：依赖、文件、种子数、Ollama、Neo4j |
| `tools/kappa.py` | 91 | 3.3 KB | 双标一致性 Cohen's kappa |
| `tools/make_fake_report.py` | 63 | 2.6 KB | 造一份假报告，测试解析/清洗/分节 |
| `tools/make_gold_template.py` | 89 | 3.9 KB | 生成标注模板（可用模型预标注） |
| `tools/smoke_test.py` | 47 | 2.5 KB | 伪造模型输出，离线跑通后处理→评测→图谱 |

Python 代码合计 **2769** 行（非空行）。

## 数据来源与规模（实测）

- 输入：599 个美国 NTSB 报告 PDF（731 MB），含 MAB 简报与 MAR/MIR 完整报告；
- 解析：PyMuPDF 提取正文，成功率 98%（9 篇扫描件、2 篇无编号）；
- 去重：同一事故多份报告合并后 448 起；
- 对齐：命中种子表 167 起（美国种子 180 起中覆盖 93%），种子外 281 起；
- 语料：正文合计 1756 万字符，单篇中位 1.93 万字符。

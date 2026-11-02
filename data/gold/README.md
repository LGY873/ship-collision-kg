# gold 目录说明

这里放**人工标注**（gold standard）。目录本身进 git，具体标注文件不进（见 `.gitignore`）。

## 文件命名约定

| 文件 | 用途 |
|---|---|
| `gold.jsonl` | 最终标注集（单标 + 双标合并、仲裁后），评测只用这一份 |
| `dev_blank.jsonl` | dev 集空白模板（双标起点） |
| `annotator_a.jsonl` / `annotator_b.jsonl` | 两个标注者的独立结果，只用于算 kappa |
| `dev_pred.jsonl` | 模型预标注版本，人工在其上修订（单标用） |
| `gold_smoke.jsonl` | 冒烟测试产物，可随时删除 |

## gold.jsonl 的格式

一行一篇文档（UTF-8，无 BOM）：

```json
{
  "doc_id": "uk_NO_20_2005",
  "accident_no": "NO 20/2005",
  "country": "UK",
  "accident_type": "collision",
  "collision_tier": "A",
  "split": "dev",
  "text": "完整正文……",
  "entities": [
    {"id": "e1", "type": "Accident", "text": "NO 20/2005", "start": 0, "end": 10, "attributes": {}},
    {"id": "e2", "type": "Ship", "text": "Amenity", "start": 84, "end": 91, "attributes": {"status": "anchored"}}
  ],
  "relations": [
    {"head": "e1", "relation": "involves_ship", "tail": "e2", "evidence": "the bulk carrier Amenity dragged her anchor"}
  ]
}
```

硬性要求：

1. `text[start:end] == entities[i].text`（偏移必须对得上，评测的严格匹配靠它）；
2. `relations` 里的 `head`/`tail` 必须是本文档 `entities` 里的 `id`；
3. `evidence` 必须是原文中的句子，不能改写；
4. 关系方向统一“以事故为起点向外指”（`Accident -> X`）。

## 生成与检查

```powershell
# 空白模板（双标用）
python tools/make_gold_template.py --split dev --n 25 --no-pred --out data\gold\annotator_a.jsonl

# 预标注模板（单标用，需先跑出该 run）
python tools/make_gold_template.py --split dev --n 43 --run-id p1_qwen7b_dev --out data\gold\dev_pred.jsonl

# 偏移自检（改完标注后跑一遍）
python -c "import json;rows=[json.loads(l) for l in open(r'data/gold/gold.jsonl',encoding='utf-8')];bad=[(r['doc_id'],e['id']) for r in rows for e in r['entities'] if r['text'][e['start']:e['end']]!=e['text']];print('docs',len(rows),'bad',len(bad),bad[:5])"

# 双标一致性
python tools/kappa.py --a data\gold\annotator_a.jsonl --b data\gold\annotator_b.jsonl
```

标注规范见 `docs/annotation_guide.md`，**先读规范再动手**。

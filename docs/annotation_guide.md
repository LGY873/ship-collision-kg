# 标注规范（v1.0）

> 配套 `ontology/ontology.json`。标注前通读一遍；标完 5 篇回头再读一遍。
> 目标：两个标注者拿到同一份报告，能标出 90% 以上相同的实体与关系。

---

## 1. 标注什么

一条事故报告 → 一组三元组：

```
(事故) --涉及船舶--> (船舶)
(事故) --人为致因--> (人员：引航员)
(事故) --受制于--> (环境：能见度 10 海里)
(事故) --导致--> (后果：1 人死亡)
```

实体 7 类：`Accident` `Ship` `Person` `Environment` `Equipment` `Organization` `Consequence`
关系 12 类：见 `ontology/ontology.json` 的 `relations`（每类都有 domain/range）。

---

## 2. 实体边界（最容易分歧的地方）

**规则：取能独立指代该实体的最长名词短语，包含限定词，不含标点。**

| 原文 | 标 | 不标 |
|---|---|---|
| `the pilot of the container ship` | `the pilot`（Person） | 整段 |
| `M/V Miss Natalie` | `M/V Miss Natalie`（Ship） | `Miss Natalie` 或 `M` |
| `visibility of about 10 miles` | `visibility of about 10 miles`（Environment） | `10 miles` |
| `the Lower Mississippi River` | `the Lower Mississippi River`（Environment/waterway） | `Mississippi` |
| `the operating company, ABC Marine` | `ABC Marine`（Organization） | 整句 |

补充：
- 船名保留原写法（`M/V`、`MV`、`m/v` 不要自行统一，归一化交给程序）；
- 地名保留到“能定位”的粒度，`mile marker 162` 可单独作 Environment(waterway)；
- 数值+单位整体标（`2.7 kts`），不拆成两个实体。

---

## 3. 关系标注

### 3.1 方向永远“从事故出发”

除 `collided_with`（船-船）与 `crewed_by`/`operated_by`/`equipped_with`（船-人/组织/设备）外，
其余关系都是 `Accident -> X`。写反了，图谱查询会全部落空。

### 3.2 两组必须区分的近义关系

| 关系 | 含义 | 例子 |
|---|---|---|
| `caused_by_person` | 人的行为**导致**事故 | `the pilot's ineffective maneuvering` |
| `involved_person` | 人**被事故波及** | `one crew member was injured` |
| `occurred_at` | **地点**（where） | `Lower Mississippi River` |
| `affected_by` | **条件**（under what condition） | `visibility 10 miles` |

### 3.3 一条关系必须有证据句

`evidence` 填原文中支持该关系的句子（可跨句，用空格连接），**必须逐字复制**。
证据句找不到就不要标这条关系——宁可漏，不要编。

---

## 4. 七条细则

1. **否定与假设**：`did not maintain a proper lookout` 中的行为本身仍算致因，关系照标，
   但在实体 `attributes` 里记 `negated: true`。假设句（`if the vessel had...`）不标。
2. **指代**：`she`、`the vessel`、`the tow` 尽量回指到首次出现的实体，跨句用同一 id。
3. **跨句关系**：允许，但必须写 `evidence`；跨段落的关系不标。
4. **嵌套**：不标嵌套实体。船名里的公司名不单独标（除非报告明确把公司作为责任主体讨论）。
5. **数值**：金额统一 USD、长度 m、速度 kn；原文单位不同的，`attributes` 里同时保留原值。
6. **不确定**：拿不准的标 `uncertain: true`，评测时单独统计，不计入主指标。
7. **同一实体多处出现**：只标一次（首次出现的完整写法），其余靠归一化合并。

---

## 5. 标注文件格式（gold.jsonl）

一行一篇文档：

```json
{
  "doc_id": "uk_NO_20_2005",
  "accident_no": "NO 20/2005",
  "country": "UK",
  "accident_type": "collision",
  "collision_tier": "A",
  "split": "dev",
  "text": "……报告正文……",
  "entities": [
    {"id": "e1", "type": "Accident", "text": "NO 20/2005", "start": 0, "end": 10, "attributes": {}},
    {"id": "e2", "type": "Ship", "text": "Amenity", "start": 84, "end": 91, "attributes": {"status": "anchored"}},
    {"id": "e3", "type": "Environment", "text": "easterly force 8 to 9", "start": 205, "end": 225, "attributes": {"category": "wind"}}
  ],
  "relations": [
    {"head": "e1", "relation": "involves_ship", "tail": "e2", "evidence": "the bulk carrier Amenity dragged her anchor"},
    {"head": "e1", "relation": "affected_by", "tail": "e3", "evidence": "The wind was easterly force 8 to 9"}
  ]
}
```

- `start`/`end` 是相对 `text` 的字符偏移，必须能在 `text[start:end]` 取回 `text` 字段；
- 用 `tools/make_gold_template.py` 生成骨架，偏移会自动算好，你只改内容；
- 改完跑一次自检（见下）。

---

## 6. 标注流程

```
Day 8   生成空白模板（--no-pred）→ 标 5 篇试标 → 对照规范修正
Day 9   预标注 + 人工修订 75 篇（--run-id 预填）
Day 10  双标 25 篇（--no-pred，两人独立）→ kappa → 仲裁分歧
```

### 一致性检验

```powershell
python tools/kappa.py --a data\gold\annotator_a.jsonl --b data\gold\annotator_b.jsonl
```

| kappa | 结论 | 动作 |
|---|---|---|
| ≥0.75 | 合格 | 进入实验 |
| 0.60—0.75 | 可接受 | 补充规范说明，重点复核分歧样本 |
| <0.60 | 不合格 | 修订规范（多半是边界规则），回标 |

### 分歧仲裁

两人 + 第三人（或导师）三方看分歧样本，按“能落到本体哪个槽位”投票，仲裁结果写进 gold.jsonl，
仲裁记录留档（论文附录取 3—5 例，很加分）。

---

## 7. 自检清单（每次改完跑一遍）

```powershell
python -c "
import json
rows=[json.loads(l) for l in open(r'data/gold/gold.jsonl',encoding='utf-8')]
bad=0
for r in rows:
    for e in r['entities']:
        if r['text'][e['start']:e['end']] != e['text']:
            bad+=1; print('offset mismatch', r['doc_id'], e['id'], e['text'][:40])
    ids={e['id'] for e in r['entities']}
    for rel in r['relations']:
        if rel['head'] not in ids or rel['tail'] not in ids:
            bad+=1; print('dangling rel', r['doc_id'], rel)
print('docs', len(rows), 'problems', bad)
"
```

---

## 8. 常见错误

| 错误 | 后果 | 修正 |
|---|---|---|
| 关系方向写反（人→事故） | 图谱查询全空 | 统一 `Accident -> X` |
| 实体文本自行改写（`M.V.` 写成 `MV`） | 原文对齐率暴跌、严格匹配全错 | 逐字复制原文 |
| 只标实体不标关系 | 关系 F1 无从计算 | 两者同步标 |
| 一个句子标了 5 个实体但只连 1 条关系 | 图谱稀疏、孤立节点多 | 每个致因实体至少连一条关系 |
| `evidence` 复制了改写过的句子 | 证据校验不通过 | 直接复制原文 |
| 双标时看到了对方的标注 | kappa 虚高 | 互不可见，第三人仲裁 |

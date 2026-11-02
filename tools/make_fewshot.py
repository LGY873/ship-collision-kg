# -*- coding: utf-8 -*-
"""生成 p2 few-shot 示例文件 data/gold/fewshot.jsonl。

示例取自 **train** 划分的文档（`us_MAB0103`、`us_DCA16FM036`），不参与评测，
避免把评测集（20 篇 dev gold）泄漏进提示词。

每个实体 text 用脚本校验必须在示例正文里逐字出现，防止手写出错。

用法：
    python tools/make_fewshot.py            # 只校验并打印
    python tools/make_fewshot.py --write    # 写 data/gold/fewshot.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import DATA, setup_logging

CORPUS = DATA / "corpus" / "corpus_us_seed_split.jsonl"
OUT = DATA / "gold" / "fewshot.jsonl"

EXAMPLES = [
    {
        "doc_id": "us_MAB0103",
        "output": {
            "accident": {
                "accident_no": None,
                "type": "collision",
                "date": "1998-06-27",
                "location": "Mile 179.5 AHP, Lower Mississippi River, near Donaldsonville, Louisiana",
            },
            "entities": [
                {"id": "e1", "type": "Accident",
                 "text": "collision between the Christine Cenac with tow and the American Heritage",
                 "attributes": {"type": "collision", "date": "1998-06-27",
                                "location": "Mile 179.5 AHP, Lower Mississippi River",
                                "country": "United States"}},
                {"id": "e2", "type": "Ship", "text": "American Heritage",
                 "attributes": {"name": "American Heritage", "ship_type": "towboat",
                                "status": "underway", "flag": "United States"}},
                {"id": "e3", "type": "Ship", "text": "Christine Cenac",
                 "attributes": {"name": "Christine Cenac", "ship_type": "towboat",
                                "status": "underway", "flag": "United States"}},
                {"id": "e4", "type": "Ship", "text": "CTCO 211",
                 "attributes": {"name": "CTCO 211", "ship_type": "tank barge",
                                "status": "underway", "flag": "United States"}},
                {"id": "e5", "type": "Ship", "text": "CTCO 210",
                 "attributes": {"name": "CTCO 210", "ship_type": "tank barge",
                                "status": "underway", "flag": "United States"}},
                {"id": "e6", "type": "Person", "text": "operator of the Christine Cenac",
                 "attributes": {"role": "master"}},
                {"id": "e7", "type": "Person", "text": "operator of the American Heritage",
                 "attributes": {"role": "master"}},
                {"id": "e8", "type": "Organization", "text": "Cenac Towing Company",
                 "attributes": {"name": "Cenac Towing Company", "org_type": "owner"}},
                {"id": "e9", "type": "Organization", "text": "American River Transportation",
                 "attributes": {"name": "American River Transportation", "org_type": "owner"}},
                {"id": "e10", "type": "Environment", "text": "Lower Mississippi River",
                 "attributes": {"category": "waterway", "name": "Lower Mississippi River"}},
                {"id": "e11", "type": "Environment", "text": "river current",
                 "attributes": {"category": "current", "name": "river current"}},
                {"id": "e12", "type": "Consequence",
                 "text": "1680 barrels (70,560 gallons) of crude oil had spilled",
                 "attributes": {"type": "pollution"}},
                {"id": "e13", "type": "Consequence", "text": "no deaths or injuries",
                 "attributes": {"type": "injury"}},
            ],
            "relations": [
                {"head": "e1", "relation": "involves_ship", "tail": "e2",
                 "evidence": "the collision between the Christine Cenac with tow and the American Heritage"},
                {"head": "e1", "relation": "involves_ship", "tail": "e3",
                 "evidence": "the collision between the Christine Cenac with tow and the American Heritage"},
                {"head": "e1", "relation": "involves_ship", "tail": "e4",
                 "evidence": "the port side of CTCO 211 struck the stern of the American Heritage."},
                {"head": "e1", "relation": "involves_ship", "tail": "e5",
                 "evidence": "It also caused the lead tank barge, CTCO 210, to break free of the tow."},
                {"head": "e4", "relation": "collided_with", "tail": "e2",
                 "evidence": "the port side of CTCO 211 struck the stern of the American Heritage."},
                {"head": "e1", "relation": "occurred_at", "tail": "e10",
                 "evidence": "Mile 179.5 AHP, Lower Mississippi River, near Donaldsonville, Louisiana."},
                {"head": "e1", "relation": "affected_by", "tail": "e11",
                 "evidence": "The river current was running 4-5 knots."},
                {"head": "e1", "relation": "caused_by_person", "tail": "e6",
                 "evidence": "the decision by the operator of the Christine Cenac to attempt to overtake and pass the American Heritage tow while the American Heritage operator was making a flanking maneuver at a sharp bend in the river."},
                {"head": "e2", "relation": "operated_by", "tail": "e9",
                 "evidence": "Owner/Operator Vessels Nos. 2 & 3 American River Transportation, Decatur, IL."},
                {"head": "e3", "relation": "operated_by", "tail": "e8",
                 "evidence": "Owner/Operator Vessel No. 1 Cenac Towing Company, Houma, LA"},
                {"head": "e3", "relation": "crewed_by", "tail": "e6",
                 "evidence": "the decision by the operator of the Christine Cenac"},
                {"head": "e1", "relation": "led_to", "tail": "e12",
                 "evidence": "approximately 1680 barrels (70,560 gallons) of crude oil had spilled into the Mississippi River"},
                {"head": "e1", "relation": "led_to", "tail": "e13",
                 "evidence": "There were no deaths or injuries resulting from the accident."},
            ],
        },
    },
    {
        "doc_id": "us_DCA16FM036",
        "output": {
            "accident": {
                "accident_no": "DCA16FM036",
                "type": "allision",
                "date": None,
                "location": "Thebes Railroad Bridge, Mississippi River",
            },
            "entities": [
                {"id": "e1", "type": "Accident",
                 "text": "Michael G Morris tow with the Thebes Railroad Bridge",
                 "attributes": {"accident_no": "DCA16FM036", "type": "allision",
                                "country": "United States"}},
                {"id": "e2", "type": "Ship", "text": "Michael G Morris",
                 "attributes": {"name": "Michael G Morris", "ship_type": "towing vessel",
                                "status": "underway", "flag": "United States"}},
                {"id": "e3", "type": "Ship", "text": "Thebes Railroad Bridge",
                 "attributes": {"name": "Thebes Railroad Bridge", "ship_type": "bridge",
                                "status": "unknown", "flag": "United States"}},
                {"id": "e4", "type": "Person", "text": "Michael G Morris pilot",
                 "attributes": {"role": "pilot"}},
                {"id": "e5", "type": "Organization", "text": "ACBL River Operations LLC",
                 "attributes": {"name": "ACBL River Operations LLC", "org_type": "owner"}},
                {"id": "e6", "type": "Environment", "text": "river current",
                 "attributes": {"category": "current", "name": "river current"}},
            ],
            "relations": [
                {"head": "e1", "relation": "involves_ship", "tail": "e2",
                 "evidence": "the probable cause of the allision of the Michael G Morris tow with the Thebes Railroad Bridge"},
                {"head": "e1", "relation": "involves_ship", "tail": "e3",
                 "evidence": "the probable cause of the allision of the Michael G Morris tow with the Thebes Railroad Bridge"},
                {"head": "e1", "relation": "caused_by_person", "tail": "e4",
                 "evidence": "the pilot not correctly accounting for the river current in the bend just above the bridge, resulting in his late and insufficient use of rudder while making the turn."},
                {"head": "e2", "relation": "crewed_by", "tail": "e4",
                 "evidence": "The Michael G Morris pilot told investigators"},
                {"head": "e2", "relation": "operated_by", "tail": "e5",
                 "evidence": "Owner/operator ACBL River Operations LLC/American Commercial Lines LLC"},
                {"head": "e1", "relation": "affected_by", "tail": "e6",
                 "evidence": "produced fast currents that increased the risk of allision while navigating a tow under the bridge."},
            ],
        },
    },
]


def norm(s: str) -> str:
    """把换行与多空格压成单空格，用于证据句比对（正文按栏宽硬换行）。"""
    return " ".join(s.replace("\r\n", "\n").replace("\n", " ").split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    logger = setup_logging("fewshot", None)

    docs = {}
    for r in (json.loads(l) for l in CORPUS.read_text(encoding="utf-8").splitlines() if l.strip()):
        docs[r["doc_id"]] = r

    problems = 0
    out_rows = []
    for ex in EXAMPLES:
        doc = docs[ex["doc_id"]]
        assert doc["split"] == "train", f"{ex['doc_id']} 不是 train 划分，会造成评测泄漏"
        body = doc["text"].replace("\r\n", "\n")
        flat = norm(body)

        ents = {e["id"]: e for e in ex["output"]["entities"]}
        for e in ex["output"]["entities"]:
            if norm(e["text"]) not in flat:
                logger.error("[%s] 实体 %s 的 text 不在正文里：%r", ex["doc_id"], e["id"], e["text"])
                problems += 1
        for r in ex["output"]["relations"]:
            if r["head"] not in ents or r["tail"] not in ents:
                logger.error("[%s] 关系端点不存在：%s", ex["doc_id"], r)
                problems += 1
            if norm(r["evidence"]) not in flat:
                logger.error("[%s] 证据句不在正文里（%s->%s）：%r",
                             ex["doc_id"], r["head"], r["tail"], r["evidence"][:70])
                problems += 1
        logger.info("[%s] 实体 %d、关系 %d，text 长度 %d",
                    ex["doc_id"], len(ex["output"]["entities"]),
                    len(ex["output"]["relations"]), len(body))
        out_rows.append({"text": body, "output": ex["output"]})

    if problems:
        logger.error("有 %d 处实体/关系端点问题，未写出", problems)
        return 1

    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("w", encoding="utf-8", newline="\n") as f:
            for row in out_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        logger.info("已写出 %s（%d 条示例，%.1f KB）",
                    OUT, len(out_rows), OUT.stat().st_size / 1024)
    else:
        logger.info("校验通过（未写盘，加 --write）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

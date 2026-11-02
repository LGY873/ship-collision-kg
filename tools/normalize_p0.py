# -*- coding: utf-8 -*-
"""把「开放词表」基线（p0 零样本）的自由命名映射回本体，便于和 p1/p2 同口径比较。

p0 提示词故意不给本体，模型会自己起类型名（vessel / crew member / weather…）和
关系名（was operated by / struck…），后处理阶段会因为不在本体里被全部丢掉。
要做三策略对比，就得先做这层映射 —— 这层映射本身就是「不给本体的代价」。

映射规则是**只看名字的关键词**，不看上下文，所以对 p0 是公平的：
任何自动映射都无法做到零损失，论文里应把它算进「本体人工成本」的对照组。

用法：
    python tools/normalize_p0.py --run-id p0_qwen7b_gold
输出：<run>/triples.jsonl（结构同 postprocess 产物，可直接喂 evaluate.py）
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import DATA, read_jsonl, read_json, write_jsonl, setup_logging  # noqa: E402
from src.llm.postprocess import parse_json  # noqa: E402

RUNS = DATA / "runs"

# 关键词 -> 本体 7 类。顺序敏感：具体词在前，泛词在后。
ENTITY_RULES = [
    ("Consequence", ["damage", "injur", "fatalit", "death", "died", "spill", "pollut",
                     "sank", "sink", "flood", "casualt", "million", "$", "loss"]),
    ("Environment", ["weather", "fog", "visibilit", "wind", "current", "tide", "sea",
                     "river", "dark", "night", "rain", "storm", "cloud", "temperature",
                     "depth", "channel", "bank"]),
    ("Equipment", ["engine", "radar", "propeller", "rudder", "pump", "steering", "system",
                   "device", "alarm", "vhf", "ais", "winch", "anchor", "drive", "thruster",
                   "gear", "light", "horn", "whistle", "camera", "gaug"]),
    ("Organization", ["company", "corporation", "corp", "commission", "coast guard",
                      "department", "agency", "authorit", "union", "ltd", "inc", "board",
                      "association", "operator", "owner", "yard", "port"]),
    ("Accident", ["collision", "allision", "ground", "capsiz", "breakaway", "fire",
                  "incident", "fracture", "strike", "contact", "accident"]),
    ("Ship", ["ship", "vessel", "boat", "barge", "tug", "tow", "ferry", "dredge",
              "cutter", "tanker", "carrier", "frigate", "barge", "yacht", "craft",
              "flotilla", "pontoon"]),
    ("Person", ["captain", "master", "mate", "pilot", "crew", "deckhand", "engineer",
                "person", "watchkeeper", "tender", "officer", "individual", "sailor",
                "operator", "helmsman", "man"]),
]

# 关系名关键词 -> 本体关系（先按名字，再按头尾类型兜底）
REL_RULES = [
    ("crewed_by", ["crew", "manned", "staff", "personnel"]),
    ("operated_by", ["operat", "run by", "owned", "managed"]),
    ("caused_by_person", ["human", "person", "crew error", "pilot error", "fatigue"]),
    ("caused_by_equipment", ["equipment", "mechanical", "machinery", "engine failure",
                             "failure", "malfunction", "defect"]),
    ("caused_by_org", ["organization", "company", "management", "policy", "regulation"]),
    ("occurred_at", ["occur", "location", "place", "took place", "happened"]),
    ("affected_by", ["affect", "influence", "contribut", "due to", "because",
                     "environment", "weather"]),
    ("led_to", ["led to", "lead to", "result", "consequence", "caus", "outcome"]),
    ("collided_with", ["collid", "struck", "strike", "allid", "contact", "hit"]),
    ("equipped_with", ["equipp", "fit", "installed", "carried"]),
    ("involved_person", ["involved person", "involves person", "injured"]),
    ("involves_ship", ["involv", "involved", "associated"]),
]


def map_entity_type(raw: str) -> str | None:
    t = (raw or "").lower()
    for target, words in ENTITY_RULES:
        if any(w in t for w in words):
            return target
    return None


def map_relation(raw: str, head_type: str, tail_type: str) -> str | None:
    r = (raw or "").lower()
    for target, words in REL_RULES:
        if any(w in r for w in words):
            # 有类型约束的关系用类型再校验一下，避免 "operated by" 落到 Accident 上
            if target == "operated_by" and head_type != "Ship":
                continue
            if target == "crewed_by" and not (head_type == "Ship" and tail_type == "Person"):
                continue
            if target == "equipped_with" and not (head_type == "Ship" and tail_type == "Equipment"):
                continue
            if target == "occurred_at" and head_type != "Accident":
                continue
            if target.startswith("caused_by") and head_type != "Accident":
                continue
            if target in ("led_to", "involves_ship", "involved_person") and head_type != "Accident":
                continue
            return target
    # 名字没命中：按类型兜底成最常见的那条关系
    if head_type == "Accident" and tail_type == "Ship":
        return "involves_ship"
    if head_type == "Accident" and tail_type == "Person":
        return "involved_person"
    if head_type == "Accident" and tail_type == "Consequence":
        return "led_to"
    if head_type == "Ship" and tail_type == "Person":
        return "crewed_by"
    if head_type == "Ship" and tail_type == "Equipment":
        return "equipped_with"
    if head_type == "Ship" and tail_type == "Ship":
        return "collided_with"
    return None


def main():
    ap = argparse.ArgumentParser(description="p0 开放词表输出 → 本体映射")
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()

    run_dir = RUNS / args.run_id
    logger = setup_logging(f"norm_p0.{args.run_id}", run_dir / "normalize.log")
    files = sorted((run_dir / "raw").glob("*.json"))
    stats = {"docs": 0, "ent_total": 0, "ent_mapped": 0, "rel_total": 0, "rel_mapped": 0}
    out_rows = []

    for f in files:
        rec = read_json(f)
        obj = parse_json(rec.get("raw", ""))
        if not obj:
            continue
        stats["docs"] += 1
        entities, id_map = [], {}
        for i, e in enumerate(obj.get("entities") or [], 1):
            stats["ent_total"] += 1
            t = map_entity_type(e.get("type") or "")
            text = (e.get("text") or "").strip()
            if not t or not text:
                continue
            stats["ent_mapped"] += 1
            nid = f"e{len(entities) + 1}"
            id_map[e.get("id")] = nid
            entities.append({"id": nid, "type": t, "text": text,
                             "attributes": e.get("attributes") or {}})
        by_id = {e["id"]: e for e in entities}
        relations, seen = [], set()
        for r in obj.get("relations") or []:
            stats["rel_total"] += 1
            hid, tid = id_map.get(r.get("head")), id_map.get(r.get("tail"))
            if not hid or not tid or hid == tid:
                continue
            rel = map_relation(r.get("relation") or "", by_id[hid]["type"], by_id[tid]["type"])
            if not rel:
                continue
            key = (hid, rel, tid)
            if key in seen:
                continue
            seen.add(key)
            stats["rel_mapped"] += 1
            relations.append({"head": hid, "head_text": by_id[hid]["text"],
                              "relation": rel, "tail": tid, "tail_text": by_id[tid]["text"],
                              "evidence": (r.get("evidence") or "").strip()[:500],
                              "evidence_ok": False, "evidence_ratio": 0.0,
                              "repaired": False, "factor_class": ""})
        out_rows.append({"doc_id": rec["doc_id"],
                         "accident_no": rec.get("accident_no"),
                         "model": rec.get("model"), "strategy": rec.get("strategy", "p0"),
                         "accident": obj.get("accident") or {},
                         "entities": entities, "relations": relations})

    write_jsonl(run_dir / "triples.jsonl", out_rows)
    logger.info("映射完成：%d 篇，实体 %d/%d，关系 %d/%d → %s",
                stats["docs"], stats["ent_mapped"], stats["ent_total"],
                stats["rel_mapped"], stats["rel_total"], run_dir / "triples.jsonl")
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print(f"已写入 {run_dir / 'triples.jsonl'}")


if __name__ == "__main__":
    main()

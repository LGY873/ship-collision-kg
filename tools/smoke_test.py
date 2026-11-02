# -*- coding: utf-8 -*-
"""离线冒烟测试：在没有任何模型/PDF 的情况下，把
   postprocess -> gold template -> evaluate -> build_nodes
整条链路跑通，确认代码没有低级错误。

    python tools/smoke_test.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.common import DATA, ensure_dir, read_jsonl  # noqa: E402

RUN_ID = "smoke_test"


def fake_prediction(doc: dict) -> dict:
    vessels = doc.get("vessels") or ["Unknown Vessel"]
    ents = [{"id": "e1", "type": "Accident", "text": doc.get("accident_no") or "accident",
             "attributes": {"accident_no": doc.get("accident_no")}}]
    ents.append({"id": "e2", "type": "Ship", "text": vessels[0], "attributes": {}})
    rels = [{"head": "e1", "relation": "involves_ship", "tail": "e2",
             "evidence": doc["text"][:120]}]
    if len(vessels) > 1:
        ents.append({"id": "e3", "type": "Ship", "text": vessels[1], "attributes": {}})
        rels.append({"head": "e1", "relation": "involves_ship", "tail": "e3",
                     "evidence": doc["text"][:120]})
        rels.append({"head": "e2", "relation": "collided_with", "tail": "e3",
                     "evidence": doc["text"][:120]})
    return {"accident": {"accident_no": doc.get("accident_no"),
                         "type": doc.get("accident_type") or "collision",
                         "date": doc.get("date"), "location": doc.get("location")},
            "entities": ents, "relations": rels}


def main():
    corpus = DATA / "corpus" / "corpus_fields_split.jsonl"
    docs = list(read_jsonl(corpus))
    test_docs = [d for d in docs if d.get("split") == "test"][:3]
    assert test_docs, "语料为空，先跑 build_corpus_from_fields.py"

    raw_dir = ensure_dir(DATA / "runs" / RUN_ID / "raw")
    for d in test_docs:
        rec = {"doc_id": d["doc_id"], "accident_no": d.get("accident_no"),
               "strategy": "p1", "model": "smoke-fake", "prompt_sha256": "0" * 16,
               "prompt_chars": 100, "elapsed_sec": 0.1,
               "raw": json.dumps(fake_prediction(d), ensure_ascii=False), "error": ""}
        (raw_dir / f"{d['doc_id']}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[1/4] 伪造 {len(test_docs)} 篇模型输出 -> {raw_dir}")


if __name__ == "__main__":
    main()

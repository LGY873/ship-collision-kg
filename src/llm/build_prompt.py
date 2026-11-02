# -*- coding: utf-8 -*-
"""S5-1：用本体自动填充提示词模板。

用法：
    python src/llm/build_prompt.py --strategy p1 --doc-id uk_xxx --show
    python src/llm/build_prompt.py --strategy p1 --dump runs/_prompt_p1.txt
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import DATA, ROOT, read_json, read_jsonl, setup_logging

TEMPLATES = {"p0": "p0_zeroshot.txt", "p1": "p1_ontology.txt", "p2": "p2_ontology_fewshot.txt"}


def load_ontology(path=None) -> dict:
    return read_json(path or ROOT / "ontology" / "ontology.json")


def ontology_blocks(onto: dict):
    lines = []
    for name, spec in onto["entities"].items():
        attrs = ", ".join(f"{k}:{v.get('type', 'str')}" for k, v in spec["attributes"].items())
        lines.append(f"  {name} ({spec.get('label_zh', '')}) — attributes: {attrs}")
    entity_block = "\n".join(lines)

    rels = []
    for name, spec in onto["relations"].items():
        dom = "|".join(spec["domain"])
        rng = "|".join(spec["range"])
        rels.append(f"  {name:<20s} {dom:<10s} -> {rng:<14s}  # {spec.get('definition', '')}")
    rel_block = "\n".join(rels)

    enum_lines = []
    for k, vals in onto["enums"].items():
        enum_lines.append(f"  {k}: [{', '.join(vals)}]")
    enum_block = "\n".join(enum_lines)
    return entity_block, rel_block, enum_block


def load_examples(path=None, max_n: int = 2) -> str:
    p = Path(path or DATA / "gold" / "fewshot.jsonl")
    if not p.exists():
        return ""
    chunks = []
    for i, ex in enumerate(read_jsonl(p), 1):
        if i > max_n:
            break
        body = ex.get("output") or ex
        chunks.append(
            f"### EXAMPLE {i}\nINPUT: {ex.get('text', '')}\n"
            f"OUTPUT: {json.dumps(body, ensure_ascii=False)}")
    return "\n\n".join(chunks)


def build(strategy: str, text: str, onto: dict | None = None,
          examples: str | None = None, lang: str = "en") -> str:
    onto = onto or load_ontology()
    if lang == "zh" and strategy == "p1":
        tpl_name = "p1_ontology_zh.txt"
    else:
        tpl_name = TEMPLATES[strategy]
    tpl_path = ROOT / "prompts" / tpl_name
    tpl = tpl_path.read_text(encoding="utf-8")
    ent, rel, enum = ontology_blocks(onto)
    if strategy == "p2" and examples is None:
        examples = load_examples()
    return (tpl.replace("{{ENTITY_TYPES}}", ent)
               .replace("{{RELATIONS}}", rel)
               .replace("{{ENUMS}}", enum)
               .replace("{{EXAMPLES}}", examples or "")
               .replace("{{TEXT}}", text))


def main():
    ap = argparse.ArgumentParser(description="生成提示词")
    ap.add_argument("--strategy", choices=list(TEMPLATES), default="p1")
    ap.add_argument("--corpus", default=str(DATA / "corpus" / "corpus_us_seed_split.jsonl"))
    ap.add_argument("--doc-id", default="")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--dump")
    args = ap.parse_args()

    logger = setup_logging("prompt", None)
    text = "On 30 May 2015 the towing vessel George W Banta moved ahead as the " \
           "M/V Miss Natalie approached, and the two vessels collided in the " \
           "Lower Mississippi River in clear weather with 10 miles visibility. " \
           "One person died and the vessel was a total loss."
    if args.doc_id and Path(args.corpus).exists():
        for r in read_jsonl(args.corpus):
            if r["doc_id"] == args.doc_id:
                text = r["text"]
                break
    prompt = build(args.strategy, text)
    logger.info("提示词长度 %d 字符（约 %d token）", len(prompt), len(prompt) // 4)
    if args.dump:
        p = Path(args.dump)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(prompt, encoding="utf-8")
        logger.info("已写出 %s", p)
    if args.show or not args.dump:
        print(prompt)


if __name__ == "__main__":
    main()

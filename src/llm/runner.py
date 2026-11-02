# -*- coding: utf-8 -*-
"""S5-3：批量抽取 runner。

特点：断点续跑、逐篇落盘、失败不中断、记录耗时与原始输出。

用法：
    python src/llm/runner.py --strategy p1 --model qwen2.5:7b-instruct \
        --split dev --limit 5 --run-id p1_qwen7b_dev
    python src/llm/runner.py --strategy p1 --model qwen2.5:7b-instruct --split test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import DATA, ensure_dir, read_jsonl, setup_logging, write_json
from llm.build_prompt import build, load_ontology
from llm.client import make_client

RUNS = DATA / "runs"


def slug(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s).strip("_")


def main():
    ap = argparse.ArgumentParser(description="批量抽取")
    ap.add_argument("--corpus", default=str(DATA / "corpus" / "corpus_fields_split.jsonl"))
    ap.add_argument("--strategy", choices=["p0", "p1", "p2"], default="p1")
    ap.add_argument("--model", default="qwen2.5:7b-instruct")
    ap.add_argument("--split", default="dev", choices=["train", "dev", "test", "all"])
    ap.add_argument("--run-id", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--max-tokens", type=int, default=3072)
    args = ap.parse_args()

    run_id = args.run_id or f"{args.strategy}_{slug(args.model)}_{args.split}"
    raw_dir = ensure_dir(RUNS / run_id / "raw")
    logger = setup_logging(f"runner.{run_id}", RUNS / run_id / "run.log")

    docs = [r for r in read_jsonl(args.corpus)
            if args.split == "all" or r.get("split") == args.split]
    docs = docs[args.start:]
    if args.limit:
        docs = docs[: args.limit]
    logger.info("run_id=%s  strategy=%s  model=%s  docs=%d", run_id, args.strategy,
                args.model, len(docs))

    onto = load_ontology()
    client = make_client(args.model, params={"max_tokens": args.max_tokens})

    write_json(RUNS / run_id / "meta.json", {
        "run_id": run_id, "model": args.model, "strategy": args.strategy,
        "split": args.split, "corpus": str(args.corpus),
        "temperature": 0, "top_p": 1.0, "max_tokens": args.max_tokens,
        "ontology_version": onto.get("version"),
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })

    ok = skip = fail = 0
    t_all = time.time()
    for i, doc in enumerate(docs, 1):
        out_path = raw_dir / f"{doc['doc_id']}.json"
        if out_path.exists() and not args.overwrite:
            skip += 1
            continue
        prompt = build(args.strategy, doc["text"], onto, lang=doc.get("lang", "en"))
        t0 = time.time()
        try:
            raw = client.generate(prompt)
            rec = {
                "doc_id": doc["doc_id"],
                "accident_no": doc.get("accident_no", ""),
                "strategy": args.strategy,
                "model": args.model,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
                "prompt_chars": len(prompt),
                "elapsed_sec": round(time.time() - t0, 2),
                "raw": raw,
                "error": "",
            }
            ok += 1
        except Exception as e:  # noqa: BLE001
            rec = {"doc_id": doc["doc_id"], "accident_no": doc.get("accident_no", ""),
                   "strategy": args.strategy, "model": args.model,
                   "prompt_sha256": "", "prompt_chars": len(prompt),
                   "elapsed_sec": round(time.time() - t0, 2), "raw": "", "error": str(e)[:300]}
            fail += 1
            logger.error("[%d/%d] %s 失败：%s", i, len(docs), doc["doc_id"], e)
        out_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        if i % 5 == 0 or i == len(docs):
            logger.info("[%d/%d] ok=%d skip=%d fail=%d 已用时 %.1f 分钟",
                        i, len(docs), ok, skip, fail, (time.time() - t_all) / 60)

    logger.info("结束：ok=%d skip=%d fail=%d，总用时 %.1f 分钟，输出 %s",
                ok, skip, fail, (time.time() - t_all) / 60, RUNS / run_id)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""校验并修复 gold.jsonl 里实体 start/end 与 text 不一致的问题。

标注规范要求 `text[start:end] == text`（逐字取自正文）。人工标注时常出现
「首字母被顺手大写」这类偏差，导致严格匹配口径下评测被无谓扣分。

用法：
    python tools/fix_gold_spans.py              # 只报告
    python tools/fix_gold_spans.py --apply      # 就地修正实体 text（保留 start/end）
    python tools/fix_gold_spans.py --apply --fix-offsets   # 同时把 start/end 挪到正确位置
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common import DATA, read_jsonl, write_jsonl  # noqa: E402


def locate(text: str, needle: str, near: int) -> int:
    """在 text 里找 needle 的位置；优先返回离 near 最近的一处。"""
    hits, start = [], 0
    while True:
        i = text.find(needle, start)
        if i < 0:
            break
        hits.append(i)
        start = i + 1
    if not hits:
        return -1
    return min(hits, key=lambda i: abs(i - near))


def main() -> int:
    ap = argparse.ArgumentParser(description="校验/修复 gold 实体 span")
    ap.add_argument("--gold", default=str(DATA / "gold" / "gold.jsonl"))
    ap.add_argument("--apply", action="store_true", help="就地修改 gold 文件")
    ap.add_argument("--fix-offsets", action="store_true", help="同时修正 start/end")
    args = ap.parse_args()

    path = Path(args.gold)
    rows = list(read_jsonl(path))
    bad_span, bad_text, fixed_text, fixed_off, unfixed = [], [], 0, 0, []

    for r in rows:
        text = r.get("text", "")
        for e in r.get("entities", []):
            s, t = int(e.get("start", 0)), int(e.get("end", 0))
            got = text[s:t]
            want = e.get("text", "")
            if got == want:
                continue
            bad_span.append((r["doc_id"], e.get("id"), want, got))
            if got.strip().lower() == want.strip().lower():
                # 仅大小写/首尾空白差异：以正文为准
                if args.apply:
                    e["text"] = got
                fixed_text += 1
            elif args.fix_offsets:
                i = locate(text, want, s)
                if i >= 0:
                    if args.apply:
                        e["start"], e["end"] = i, i + len(want)
                    fixed_off += 1
                else:
                    bad_text.append((r["doc_id"], e.get("id"), want))
            else:
                bad_text.append((r["doc_id"], e.get("id"), want))

    total = sum(len(r.get("entities", [])) for r in rows)
    print(f"gold 文档 {len(rows)} 篇，实体 {total} 个")
    print(f"span 不一致 {len(bad_span)} 个（可自动修正 {fixed_text + fixed_off}，需人工 {len(bad_text)}）")
    for row in bad_span[:20]:
        print("  ", row)
    if bad_text:
        print("需人工处理：")
        for row in bad_text:
            print("  ", row)

    if args.apply and (fixed_text or fixed_off):
        write_jsonl(path, rows)
        print(f"已写回 {path}：修正 text {fixed_text} 处、修正 offset {fixed_off} 处")
    elif not args.apply:
        print("未修改；加 --apply 执行修正")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

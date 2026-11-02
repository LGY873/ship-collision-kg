# -*- coding: utf-8 -*-
"""S2-3：分节与分句，保留字符偏移。

NTSB 报告结构：1 Factual Information / 2 Analysis / 3 Conclusions / 4 Probable Cause
MAIB 报告结构：SYNOPSIS / 1 FACTUAL INFORMATION / 2 ANALYSIS / 3 CONCLUSIONS / 4 RECOMMENDATIONS

用法：
    python src/prep/segment.py --input data/text_clean/us/xxx.txt
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SECTION_PATTERNS = [
    ("synopsis", r"^\s*(?:synopsis|summary|executive summary)\s*$"),
    ("factual", r"^\s*(?:\d+\.?\s*)?factual information\s*$"),
    ("analysis", r"^\s*(?:\d+\.?\s*)?(?:analysis|analysis and discussion)\s*$"),
    ("conclusions", r"^\s*(?:\d+\.?\s*)?conclusions?\s*$"),
    ("cause", r"^\s*(?:\d+\.?\s*)?(?:probable cause|probable causes|cause)\s*$"),
    ("recommendations", r"^\s*(?:\d+\.?\s*)?recommendations?\s*$"),
    ("safety", r"^\s*(?:\d+\.?\s*)?(?:safety actions|safety recommendations)\s*$"),
]

ABBREV = {"mr", "mrs", "ms", "dr", "capt", "cmdr", "lt", "no", "nos", "fig", "figs",
          "approx", "e.g", "i.e", "vs", "etc", "inc", "ltd", "co", "st", "mt",
          "u.s", "u.k", "a.m", "p.m", "art", "para", "sec", "vol", "ch", "p", "pp"}


def split_sections(text: str) -> dict:
    """返回 {section_name: text}，未识别的部分放在 _preamble。"""
    lines = text.split("\n")
    marks = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        if len(s) <= 60:
            for name, pat in SECTION_PATTERNS:
                if re.match(pat, s, flags=re.I):
                    marks.append((i, name))
                    break
    if not marks:
        return {"_preamble": text, "sectioned": False}

    out = {}
    if marks[0][0] > 0:
        out["_preamble"] = "\n".join(lines[: marks[0][0]]).strip()
    for idx, (line_no, name) in enumerate(marks):
        end = marks[idx + 1][0] if idx + 1 < len(marks) else len(lines)
        body = "\n".join(lines[line_no + 1: end]).strip()
        if name in out:
            out[name] = out[name] + "\n" + body
        else:
            out[name] = body
    out["sectioned"] = True
    return out


def split_sentences(text: str):
    """返回 [(start, end, sentence)]，偏移基于传入的 text。"""
    out = []
    start = 0
    for m in re.finditer(r"[.!?](?=\s+[A-Z0-9\"“(\[]|\s*$)", text):
        end = m.end()
        seg = text[start:end]
        if not seg.strip():
            start = end
            continue
        # 缩写保护：句末词是 Mr./No./Fig. 等则继续
        tail = re.findall(r"([A-Za-z.]+)\.$", seg.strip())
        if tail and tail[-1].lower().strip(".") in ABBREV:
            continue
        # 太短的片段（目录残留、单字母）丢弃
        if len(seg.strip()) >= 10:
            out.append((start, end, seg.strip()))
        start = end
    if start < len(text):
        seg = text[start:].strip()
        if len(seg) >= 10:
            out.append((start, len(text), seg))
    return out


def extract_for_extraction(sections: dict, max_chars: int = 12000) -> str:
    """抽取输入：取 synopsis + analysis + conclusions + cause，超长截断。"""
    order = ["synopsis", "analysis", "conclusions", "cause"]
    parts = []
    for k in order:
        if k in sections:
            parts.append(f"## {k.upper()}\n{sections[k]}")
    if not parts:
        parts.append(sections.get("_preamble", ""))
    text = "\n\n".join(parts)
    return text[:max_chars]


def main():
    ap = argparse.ArgumentParser(description="分节分句自测")
    ap.add_argument("--input", required=True)
    args = ap.parse_args()
    text = Path(args.input).read_text(encoding="utf-8", errors="ignore")
    secs = split_sections(text)
    print("sections:", [k for k in secs if not k.startswith("_")], "sectioned=", secs.get("sectioned"))
    sents = split_sentences(text)
    print("sentences:", len(sents))
    for s, e, x in sents[:5]:
        print(f"  [{s}:{e}] {x[:90]}")


if __name__ == "__main__":
    main()

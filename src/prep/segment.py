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

# 分节标题：兼容 NTSB（"1 Factual Information"）与 MAIB（"SECTION 2 - ANALYSIS"、
# "3.2.1 Fundamental cause"）两种排版。锚定行尾，避免误吞正文句子。
_SEC_PREFIX = r"^\s*(?:section\s*\d+\s*[-–—:.]?\s*)?(?:\d+(?:\.\d+)*\.?\s*)?"
SECTION_PATTERNS = [
    ("synopsis", _SEC_PREFIX + r"(?:synopsis|summary|executive summary)\s*$"),
    ("factual", _SEC_PREFIX + r"factual information\s*$"),
    ("analysis", _SEC_PREFIX + r"(?:analysis|analysis and discussion)\s*$"),
    ("conclusions", _SEC_PREFIX + r"conclusions?\s*$"),
    ("cause", _SEC_PREFIX + r"(?:probable causes?|fundamental cause|underlying causes?"
                             r"|causes?|cause)\s*$"),
    ("recommendations", _SEC_PREFIX + r"recommendations?\s*$"),
    ("safety", _SEC_PREFIX + r"(?:safety actions|safety recommendations)\s*$"),
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


# 抽取输入的分节优先级与预算比例。
# 关键改动：cause（事故原因）排第一。旧版把 cause 放最后，正文超长时被整段切掉，
# 模型根本看不到事故原因 —— 447 篇全文里有 55% 的文本因此丢失 "probable cause"。
SECTION_BUDGET = [
    ("cause", 0.40),          # 事故原因：最高优先级，论文的核心抽取字段
    ("synopsis", 0.20),       # 摘要：含事故号、船名、时间地点
    ("analysis", 0.30),       # 分析：风险因素与因果链
    ("conclusions", 0.10),    # 结论
    ("factual", 0.30),        # 事实信息：仅在还有余量时补充（船况、天气、人员）
]


def truncate_at_sentence(text: str, limit: int) -> str:
    """在上限内截断，尽量落在句末，避免把句子切一半。"""
    if len(text) <= limit:
        return text
    head = text[:limit]
    last = None
    for m in re.finditer(r"[.!?](?=\s|$)", head):
        last = m
    if last and last.end() >= limit * 0.5:
        return head[: last.end()].rstrip()
    # 没有句末标点（表格、清单、中文无标点长句）：退到最近的空白处，别把词切开
    cut = max(head.rfind(" "), head.rfind("\n"), head.rfind("。"), head.rfind("；"))
    if cut >= limit * 0.8:
        return head[:cut].rstrip()
    return head.rstrip()


def extract_for_extraction(sections: dict, max_chars: int = 24000) -> str:
    """抽取输入：按「事故原因优先」给各节分配预算，超预算在句末截断。

    与旧版的区别：
    1. cause 提到第一位，不再被最后切掉；
    2. 预算按节分配（40/20/30/10），单节超长时只在句末截断；
    3. 预算没用完就继续从各节剩余内容补（否则分节失败的文档只剩摘要，输入被压缩到 2k）；
    4. 默认预算 24000 字符 ≈ 6k tokens，留足 qwen2.5 的 32k 上下文。
    """
    if not sections.get("sectioned"):
        return truncate_at_sentence(sections.get("_preamble", ""), max_chars)

    frac = dict(SECTION_BUDGET)
    avail = [(name, (sections.get(name) or "").strip()) for name, _ in SECTION_BUDGET]
    avail = [(n, b) for n, b in avail if b]
    if not avail:
        return truncate_at_sentence(sections.get("_preamble", ""), max_chars)

    parts, used, consumed = [], 0, {}
    # 分节标题（"## CAUSE\n" 与分隔空行）也占字符，先扣掉，否则总长会超出 max_chars
    overhead = sum(len(f"## {n.upper()}\n") + 2 for n, _ in avail)
    limit = max(1000, max_chars - overhead)
    for name, body in avail:
        remaining = limit - used
        if remaining < 400:
            break
        budget = min(max(1200, int(limit * frac[name])), remaining)
        piece = truncate_at_sentence(body, budget)
        parts.append((name, piece))
        consumed[name] = len(piece)
        used += len(piece)

    # 第二轮：把没花掉的预算按优先级继续填，避免分节少时输入过短
    while used < limit - 1000:
        progressed = False
        for name, body in avail:
            rest = body[consumed.get(name, 0):].strip()
            if len(rest) < 400:
                continue
            remaining = limit - used
            if remaining < 400:
                break
            piece = truncate_at_sentence(rest, remaining)
            parts.append((name, piece))
            consumed[name] += len(piece)
            used += len(piece)
            progressed = True
            if used >= limit - 400:
                break
        if not progressed:
            break
    out = "\n\n".join(f"## {n.upper()}\n{p}" for n, p in parts)
    if len(out) > max_chars:
        out = truncate_at_sentence(out, max_chars)
    return out


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

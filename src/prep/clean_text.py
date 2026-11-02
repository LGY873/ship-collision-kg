# -*- coding: utf-8 -*-
"""S2-2：文本清洗（规则 R1—R12）。

设计原则：能不用正则就不用；每条规则都能单独关闭与统计命中数，
方便在论文里写“清洗前后字符数、各规则命中行数”。

用法（自测）：
    python src/prep/clean_text.py --input data/text/us/xxx.txt
    python src/prep/clean_text.py --dir data/text --out data/text_clean
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import ensure_dir, setup_logging

# ---------- R9 不可见字符 ----------
_LETTER_REPL = re.compile(r"(?<=[A-Za-z])\ufffd+(?=[A-Za-z])")

_CTRL = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\u200b-\u200f\ufeff\ufffd]")

# ---------- R1 页眉页脚 ----------
_PAGE_OF = re.compile(r"^\s*(?:page|pg\.?)\s*\d+\s*(?:of|/)\s*\d+\s*$", re.I)
_PAGE_NUM = re.compile(r"^\s*[-–—]?\s*\d{1,3}\s*[-–—]?\s*$")
_REPORT_HEAD = re.compile(r"^\s*(?:NO|No\.?)\s*\d{1,3}\s*/\s*\d{4}\b.*$")
_MIR_HEAD = re.compile(
    r"^\s*(?:NTSB\s*/\s*)?(?:MAR|MIR|MAB|MSR|RIR)[-/\s]?\d{2}[-/\s]\d{2}\b.*$", re.I)

# ---------- R3 水印 ----------
_WATERMARK = re.compile(
    r"^\s*(?:draft|confidential|for official use only|internal use|"
    r"未经许可|内部资料|仅供参考)\s*$", re.I)

# ---------- R6 图表题注 ----------
_CAPTION = re.compile(
    r"^\s*(?:figure|fig\.?|table|photo|photograph|annex)\s*[\dA-Z][\d\.\-–—:]*\s*[:.]?\s*",
    re.I)

# ---------- R7 参考文献/附录 ----------
_STOP_HEADING = re.compile(
    r"^\s*(?:\d+\.?\s*)?(references|bibliography|appendix|annex(es)?)\s*$", re.I)

# ---------- R8 免责声明 ----------
_DISCLAIMER = re.compile(
    r"(this (report|investigation) (is|was) (not|conducted)|"
    r"the (sole|only) purpose of this report|"
    r"no (liability|responsibility) (is|can be) accepted|"
    r"statutory language prohibits|admission into evidence|"
    r"Title 49 United States Code)", re.I)


def r9_control_chars(lines, hits):
    out = []
    for ln in lines:
        # PDF 字体缺 ToUnicode 时，撇号会变成 U+FFFD（captain??s）。
        # 只在“字母之间”替换成撇号，其余（如时间区间里的破折号）直接删除。
        new = _LETTER_REPL.sub("'", ln)
        new = new.replace("\ufffd", "")
        new = _CTRL.sub("", new)
        if new != ln:
            hits["R9"] += 1
        out.append(new)
    return out


def r4_hyphenation(lines, hits):
    """行尾连字符断词：colli-\\n sion -> collision"""
    out = []
    i = 0
    while i < len(lines):
        cur = lines[i]
        if (i + 1 < len(lines) and re.search(r"[A-Za-z]-$", cur.rstrip())
                and lines[i + 1][:1].islower()):
            merged = cur.rstrip()[:-1] + lines[i + 1].lstrip()
            out.append(merged)
            hits["R4"] += 1
            i += 2
            continue
        out.append(cur)
        i += 1
    return out


def r1_headers_footers(lines, hits, max_head_len=90):
    out = []
    for ln in lines:
        s = ln.strip()
        if not s:
            out.append(ln)
            continue
        if len(s) <= max_head_len and (
                _PAGE_OF.match(s) or _PAGE_NUM.match(s) or _WATERMARK.match(s)
                or _REPORT_HEAD.match(s) or _MIR_HEAD.match(s)):
            hits["R1"] += 1
            continue
        out.append(ln)
    return out


def r10_toc(lines, hits):
    out = []
    for ln in lines:
        s = ln.strip()
        if re.search(r"\.{4,}\s*\d{1,3}\s*$", s) or re.search(r"\s{3,}\d{1,3}\s*$", s) and "…" in s:
            hits["R10"] += 1
            continue
        out.append(ln)
    return out


def r6_captions(lines, hits, max_len=120):
    out = []
    for ln in lines:
        s = ln.strip()
        if s and len(s) <= max_len and _CAPTION.match(s) and not s.lower().startswith("table of"):
            hits["R6"] += 1
            continue
        out.append(ln)
    return out


def r8_disclaimer(lines, hits):
    out = []
    for ln in lines:
        if _DISCLAIMER.search(ln):
            hits["R8"] += 1
            continue
        out.append(ln)
    return out


def r7_stop_at_appendix(lines, hits):
    for i, ln in enumerate(lines):
        if _STOP_HEADING.match(ln.strip()):
            hits["R7"] += 1
            return lines[:i]
    return lines


def r12_dedupe(lines, hits):
    seen = set()
    out = []
    for ln in lines:
        key = re.sub(r"\s+", " ", ln.strip()).lower()
        if 40 <= len(key) <= 300:
            if key in seen:
                hits["R12"] += 1
                continue
            seen.add(key)
        out.append(ln)
    return out


def r5_spacing(lines, hits):
    out = []
    blank = 0
    for ln in lines:
        ln = re.sub(r"[ \t]+", " ", ln).rstrip()
        if not ln:
            blank += 1
            if blank > 1:
                hits["R5"] += 1
                continue
        else:
            blank = 0
        out.append(ln)
    return out


def clean_lines(text: str) -> tuple[list[str], dict]:
    """按行清洗，保留行结构（分节、分句依赖行边界）。"""
    hits = {"R1": 0, "R4": 0, "R5": 0, "R6": 0, "R7": 0, "R8": 0,
            "R9": 0, "R10": 0, "R12": 0}
    text = unicodedata.normalize("NFKC", text.replace("\r\n", "\n").replace("\r", "\n"))
    lines = text.split("\n")
    lines = r9_control_chars(lines, hits)
    lines = r4_hyphenation(lines, hits)
    lines = r7_stop_at_appendix(lines, hits)
    lines = r1_headers_footers(lines, hits)
    lines = r10_toc(lines, hits)
    lines = r6_captions(lines, hits)
    lines = r8_disclaimer(lines, hits)
    lines = r12_dedupe(lines, hits)
    lines = r5_spacing(lines, hits)
    return lines, hits


def join_blocks(lines: list[str]) -> str:
    """把段内单换行合成空格，空行作为段落分隔。"""
    blocks, cur = [], []
    for ln in lines:
        if ln.strip():
            cur.append(ln.strip())
        elif cur:
            blocks.append(" ".join(cur))
            cur = []
    if cur:
        blocks.append(" ".join(cur))
    return "\n\n".join(blocks)


def clean(text: str) -> tuple[str, dict]:
    lines, hits = clean_lines(text)
    return join_blocks(lines), hits


def main():
    ap = argparse.ArgumentParser(description="文本清洗")
    ap.add_argument("--input")
    ap.add_argument("--dir")
    ap.add_argument("--out")
    args = ap.parse_args()
    logger = setup_logging("clean", None)

    if args.input:
        raw = Path(args.input).read_text(encoding="utf-8", errors="ignore")
        cleaned, hits = clean(raw)
        logger.info("字符数 %d -> %d（保留 %.1f%%）", len(raw), len(cleaned),
                    100.0 * len(cleaned) / max(1, len(raw)))
        logger.info("命中：%s", hits)
        if args.out:
            p = Path(args.out)
            ensure_dir(p.parent)
            p.write_text(cleaned, encoding="utf-8")
            logger.info("已写出 %s", p)
        else:
            print(cleaned[:1500])
        return

    if args.dir:
        src = Path(args.dir)
        dst = ensure_dir(args.out or "data/text_clean")
        for f in sorted(src.rglob("*.txt")):
            raw = f.read_text(encoding="utf-8", errors="ignore")
            cleaned, hits = clean(raw)
            rel = f.relative_to(src)
            out = dst / rel
            ensure_dir(out.parent)
            out.write_text(cleaned, encoding="utf-8")
            logger.info("%s  %d -> %d  %s", rel, len(raw), len(cleaned), hits)
        return

    ap.print_help()


if __name__ == "__main__":
    main()

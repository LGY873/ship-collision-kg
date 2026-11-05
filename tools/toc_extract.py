"""从导出的 PDF 里量出每个标题所在的正文页码，生成目录 JSON。

用法（项目 venv，需要 PyMuPDF）：
    python tools/toc_extract.py --md docs/论文初稿.md --pdf docs/论文初稿-模板版.pdf \
        --out docs/toc.json

原理：正文页页脚是阿拉伯数字（1、2、3…），目录页页脚是罗马数字（I、II…）。
先按页脚取到正文页码，再在正文页里找标题文本（去空白后匹配），得到标题→页码。
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import pymupdf  # noqa: E402


def chapter_title_text(text: str) -> str:
    m = re.match(r"^第\s*(\d+)\s*章\s*(.*)$", text)
    if m:
        return f"{m.group(1)} {m.group(2).strip()}"
    m = re.match(r"^附录\s*([A-Z])\s*(.*)$", text)
    if m:
        return f"附录 {m.group(1)} {m.group(2).strip()}".strip()
    return text


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def read_headings(md_path: Path) -> list[dict]:
    """目录条目：前置部分（摘要/ABSTRACT，罗马页码）+ 正文各章与节。"""
    entries = [
        {"level": 1, "text": "摘　要", "page": "", "front": True},
        {"level": 1, "text": "ABSTRACT", "page": "", "front": True},
    ]
    with md_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("## "):
                text = line[3:].strip()
                if text.startswith("摘要") or text.lower().startswith("abstract"):
                    continue
                entries.append({"level": 1, "text": chapter_title_text(text), "page": ""})
                if text.startswith("参考文献"):
                    entries.append({"level": 1, "text": "致　谢", "page": ""})
            elif line.startswith("### "):
                entries.append({"level": 2, "text": line[4:].strip(), "page": ""})
    return entries


def page_footer_number(page: "pymupdf.Page") -> str | None:
    """页脚的页码画在页面最底部，用块坐标取，避免和正文里的数字混淆。

    正文页是阿拉伯数字（"1"），前置部分是罗马数字（"I"）。
    """
    height = page.rect.height
    for block in page.get_text("blocks"):
        if block[1] > height * 0.88:
            text = block[4].strip()
            if text.isdigit():
                return text
            if re.fullmatch(r"[IVXLC]+", text):
                return text
    return None


def page_body_text(page: "pymupdf.Page") -> str:
    """正文文本（去掉底部页码块），用于标题匹配。"""
    height = page.rect.height
    parts = [b[4] for b in page.get_text("blocks") if b[1] <= height * 0.88]
    return norm("\n".join(parts))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", required=True)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--verify", action="store_true", help="对照已有目录 JSON 校验页码是否一致")
    args = ap.parse_args()

    entries = read_headings(Path(args.md))
    doc = pymupdf.open(args.pdf)
    pages = []
    for i in range(doc.page_count):
        page = doc.load_page(i)
        pages.append((i, page_footer_number(page), page_body_text(page)))

    front_pages = [(i, no, txt) for i, no, txt in pages
                   if no is not None and not no.isdigit()]
    body_pages = [(i, no, txt) for i, no, txt in pages if no is not None and no.isdigit()]
    print(f"PDF 共 {doc.page_count} 页，其中前置页 {len(front_pages)} 页、正文页 {len(body_pages)} 页")

    found, missing = 0, []
    for entry in entries:
        key = norm(entry["text"])
        pool = front_pages if entry.get("front") else body_pages
        for i, no, txt in pool:
            if key in txt:
                entry["page"] = no
                found += 1
                break
        else:
            missing.append(entry["text"])

    print(f"标题 {len(entries)} 个，定位到 {found} 个")
    if missing:
        print("未定位：")
        for m in missing:
            print("  -", m)

    out = Path(args.out)
    payload = json.dumps(entries, ensure_ascii=False, indent=2)
    if args.verify and out.exists():
        old = json.loads(out.read_text(encoding="utf-8"))
        old_map = {e["text"]: e["page"] for e in old}
        bad = [e["text"] for e in entries if old_map.get(e["text"]) != e["page"]]
        print(f"页码校验：{len(entries) - len(bad)}/{len(entries)} 一致")
        for t in bad[:10]:
            print(f"  不一致：{t} 旧={old_map.get(t)} 新={dict((e['text'], e['page']) for e in entries).get(t)}")
    else:
        out.write_text(payload, encoding="utf-8")
        print("已写入", out)
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())

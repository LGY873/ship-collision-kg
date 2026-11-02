"""把 docs/论文初稿.md 转成 Word 文档（本科毕业论文版式）。

不是通用 Markdown 转换器，只处理本文档用到的语法：
    # / ## / ### 标题、普通段落、> 引用块、| 表格 |、``` 代码块、--- 分隔线、**粗体**。

中文字体通过 w:eastAsia 显式指定，否则 Word 会回退到默认西文字体。

用法：
    python tools/md_to_docx.py [--src docs\论文初稿.md] [--out docs\论文初稿.docx]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from docx import Document  # noqa: E402
from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Pt, Cm, RGBColor  # noqa: E402

from src.common import ROOT  # noqa: E402

BODY_CN = "宋体"
BODY_EN = "Times New Roman"
HEAD_CN = "黑体"
MONO = "Consolas"


def set_run_font(run, cn: str, en: str, size: float | None = None, bold: bool | None = None):
    run.font.name = en
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), en)
    rfonts.set(qn("w:hAnsi"), en)
    rfonts.set(qn("w:eastAsia"), cn)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold


def add_para(doc, text: str, *, cn=BODY_CN, en=BODY_EN, size=12, bold=False,
             align=None, first_indent=True, space_after=6, line=1.5):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.line_spacing = line
    if first_indent:
        pf.first_line_indent = Pt(size * 2)
    if align is not None:
        p.alignment = align
    add_inline(p, text, cn=cn, en=en, size=size, bold=bold)
    return p


def add_inline(p, text: str, *, cn, en, size, bold=False):
    """处理 **粗体** 与 `代码`；落单的标记按普通字符处理，不让它漏进正文。"""
    for seg in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not seg:
            continue
        if seg.startswith("**") and seg.endswith("**") and len(seg) > 4:
            r = p.add_run(seg[2:-2].replace("`", ""))
            set_run_font(r, cn, en, size, True)
        elif seg.startswith("`") and seg.endswith("`") and len(seg) > 2:
            r = p.add_run(seg[1:-1])
            set_run_font(r, MONO, MONO, size - 1.5, bold)
        else:
            clean = seg.replace("**", "").replace("`", "")
            r = p.add_run(clean)
            set_run_font(r, cn, en, size, bold)


def add_table(doc, rows: list[list[str]]):
    if not rows:
        return
    ncol = max(len(r) for r in rows)
    t = doc.add_table(rows=len(rows), cols=ncol)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        for j in range(ncol):
            cell = t.cell(i, j)
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.space_before = Pt(2)
            txt = row[j] if j < len(row) else ""
            add_inline(p, txt, cn=BODY_CN, en=BODY_EN, size=10.5, bold=(i == 0))
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def split_table_row(line: str) -> list[str]:
    line = line.strip().strip("|")
    return [c.strip() for c in line.split("|")]


def is_sep_row(line: str) -> bool:
    return bool(re.fullmatch(r"\|?[\s:|-]+\|?", line.strip())) and "-" in line


def add_page_number(section) -> None:
    """页脚居中页码（PAGE 域，Word 打开后自动编号）。"""
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    set_run_font(run, BODY_CN, BODY_EN, 10.5)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for el in (begin, instr, sep, end):
        run._r.append(el)


def convert(src: Path, out: Path) -> None:
    lines = src.read_text(encoding="utf-8").splitlines()
    doc = Document()

    # 页面与默认样式
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.top_margin = sec.bottom_margin = Cm(2.54)
    sec.left_margin = sec.right_margin = Cm(3.0)
    add_page_number(sec)

    style = doc.styles["Normal"]
    style.font.name = BODY_EN
    style.font.size = Pt(12)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_CN)

    i = 0
    n = len(lines)
    in_code = False
    code_buf: list[str] = []

    while i < n:
        raw = lines[i]
        line = raw.rstrip()

        # 代码块
        if line.strip().startswith("```"):
            if not in_code:
                in_code, code_buf = True, []
            else:
                in_code = False
                for cl in code_buf:
                    p = doc.add_paragraph()
                    p.paragraph_format.space_after = Pt(0)
                    p.paragraph_format.line_spacing = 1.15
                    p.paragraph_format.left_indent = Pt(12)
                    r = p.add_run(cl if cl else " ")
                    set_run_font(r, MONO, MONO, 9)
                doc.add_paragraph().paragraph_format.space_after = Pt(2)
            i += 1
            continue
        if in_code:
            code_buf.append(raw)
            i += 1
            continue

        stripped = line.strip()

        if not stripped or stripped in ("---", "***"):
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            level, text = len(m.group(1)), m.group(2).strip()
            if level == 1:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(12)
                p.paragraph_format.space_after = Pt(18)
                add_inline(p, text, cn=HEAD_CN, en=HEAD_CN, size=18, bold=True)
            elif level == 2:
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(14)
                p.paragraph_format.space_after = Pt(8)
                add_inline(p, text, cn=HEAD_CN, en=HEAD_CN, size=15, bold=True)
            else:
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(10)
                p.paragraph_format.space_after = Pt(6)
                add_inline(p, text, cn=HEAD_CN, en=HEAD_CN, size=13, bold=True)
            i += 1
            continue

        # 表格
        if stripped.startswith("|") and i + 1 < n and is_sep_row(lines[i + 1]):
            rows = [split_table_row(stripped)]
            i += 2
            while i < n and lines[i].strip().startswith("|"):
                rows.append(split_table_row(lines[i]))
                i += 1
            add_table(doc, rows)
            continue

        # 图片：![alt](相对路径)
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped)
        if m:
            alt, rel = m.group(1), m.group(2)
            img = (src.parent / rel).resolve()
            if img.exists():
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.space_after = Pt(2)
                p.add_run().add_picture(str(img), width=Cm(14.5))
                cap = doc.add_paragraph()
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap.paragraph_format.space_after = Pt(10)
                r = cap.add_run(alt)
                set_run_font(r, BODY_CN, BODY_EN, 10.5)
                r.font.bold = True
            else:
                print(f"[warn] 图片不存在：{img}")
            i += 1
            continue

        # 引用块
        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Pt(18)
            p.paragraph_format.space_after = Pt(6)
            for bi, b in enumerate(buf):
                if bi:
                    p.add_run("\n").font.size = Pt(10.5)
                r_start = len(p.runs)
                add_inline(p, b, cn=BODY_CN, en=BODY_EN, size=10.5)
                for r in p.runs[r_start:]:
                    r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
                    r.font.italic = True
            continue

        # 有序/无序列表
        m = re.match(r"^(\d+\.)\s+(.*)$", stripped)
        if m:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Pt(18)
            p.paragraph_format.space_after = Pt(4)
            add_inline(p, stripped, cn=BODY_CN, en=BODY_EN, size=12)
            i += 1
            continue
        if stripped.startswith("- "):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Pt(18)
            p.paragraph_format.space_after = Pt(4)
            add_inline(p, "· " + stripped[2:], cn=BODY_CN, en=BODY_EN, size=12)
            i += 1
            continue

        # 普通段落：把连续的非空行并成一段（Markdown 软换行）
        buf = [stripped]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith(("#", "|", ">", "```", "- ", "---"))
                    or re.match(r"^\d+\.\s", nxt)):
                break
            buf.append(nxt)
            i += 1
        add_para(doc, "".join(buf))

    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    print(f"已生成 {out}（{out.stat().st_size / 1024:.1f} KB）")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "docs" / "论文初稿.md"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "论文初稿.docx"))
    args = ap.parse_args()
    convert(Path(args.src), Path(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

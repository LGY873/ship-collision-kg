"""按「西京学院 2027 届本科毕业设计（论文）模板」的排版要求生成 Word 文档。

模板实测规格（源文件：西京学院2027届本科毕业设计（论文）模板(1).docx）：
- 页面 A4（21×29.7cm），上下边距 2.7cm，左右 2.5cm，页眉 1.5cm，页脚 2.2cm
- 一级标题：黑体三号（16pt），居中，数字与文字间空一格，段前段后各一行
- 二级标题：黑体四号（14pt），左顶格，数字与文字间空一格
- 三级标题：黑体小四（12pt），左顶格
- 正文：宋体小四（12pt），首行缩进 2 字符，固定行距 22 磅，两端对齐
- 图题在图下方、表题在表上方，宋体五号（10.5pt）居中，按章编号「图 5-1 XXX」
- 所有表格采用三线表，宋体五号，英文 Times New Roman 五号
- 摘要/ABSTRACT 标题黑体三号居中；关键词行黑体小四
- 参考文献小四，悬挂缩进 2 字符；致谢单独占一页
- 页眉：声明页「声 明」，正文起论文题目；正文页眉为双线下边框
- 页码：摘要前用罗马数字（I、II），正文起从 1 开始用阿拉伯数字

用法：
    python tools/md_to_template_docx.py --src docs/论文初稿.md --out docs/论文初稿-模板版.docx
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

SONG = "宋体"
HEI = "黑体"
TNR = "Times New Roman"
LINE = 22.0  # 固定行距 22 磅

# 封面信息（学号/指导教师/班级留空由本人填写）
COVER = {
    "title": "",
    "college": "计算机学院",
    "major": "大数据技术",
    "class_name": "＿＿＿＿＿＿＿＿",
    "student_id": "＿＿＿＿＿＿＿＿",
    "student_name": "＿＿＿＿＿＿＿＿",
    "teacher": "＿＿＿＿＿＿＿＿",
    "date": "2027 年 4 月",
}

DECLARATION = [
    "本人郑重声明：",
    "本人所呈交的毕业设计或论文，是在导师的指导下独立进行研究所取得的成果。"
    "毕业设计或论文中凡引用他人已经发表或未发表的成果、数据、观点等，均已明确注明出处。"
    "除文中已经注明引用的内容外，不包含任何其他个人或集体已经发表或在网上发表的论文。",
    "特此声明。",
]


# ---------------------------------------------------------------- 底层排版工具
# OOXML 子元素必须按架构顺序出现，否则 Word 会以「域嵌套太深」等莫名错误拒绝打开文档。
PBDR_AFTER = (
    "w:shd", "w:tabs", "w:suppressAutoHyphens", "w:kinsoku", "w:wordWrap",
    "w:overflowPunct", "w:topLinePunct", "w:autoSpaceDE", "w:autoSpaceDN", "w:bidi",
    "w:adjustRightInd", "w:snapToGrid", "w:spacing", "w:ind", "w:contextualSpacing",
    "w:mirrorIndents", "w:suppressOverlap", "w:jc", "w:textDirection", "w:textAlignment",
    "w:textboxTightWrap", "w:outlineLvl", "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr",
    "w:pPrChange",
)
PGNUM_AFTER = (
    "w:cols", "w:formProt", "w:vAlign", "w:noEndnote", "w:titlePg", "w:textDirection",
    "w:bidi", "w:rtlGutter", "w:docGrid", "w:printerSettings", "w:sectPrChange",
)
TBLBORDERS_AFTER = (
    "w:shd", "w:tblLayout", "w:tblCellMar", "w:tblLook", "w:tblCaption",
    "w:tblDescription", "w:tblPrChange",
)
TCBORDERS_AFTER = (
    "w:shd", "w:noWrap", "w:tcMar", "w:textDirection", "w:tcFitText", "w:vAlign",
    "w:hideMark", "w:headers", "w:cellIns", "w:cellDel", "w:cellMerge", "w:tcPrChange",
)
OUTLINE_AFTER = (
    "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr", "w:pPrChange",
)


def insert_ordered(parent, element, successors):
    for tag in successors:
        found = parent.find(qn(tag))
        if found is not None:
            found.addprevious(element)
            return element
    parent.append(element)
    return element


def set_font(run, cjk=SONG, latin=TNR, size=12.0, bold=False):
    run.font.name = latin
    run.font.size = Pt(size)
    run.font.bold = bold
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), latin)
    rfonts.set(qn("w:hAnsi"), latin)
    rfonts.set(qn("w:eastAsia"), cjk)
    rfonts.set(qn("w:hint"), "eastAsia")


def fmt_para(p, align=WD_ALIGN_PARAGRAPH.JUSTIFY, first_indent=24.0,
             line=LINE, before=0.0, after=0.0, left=0.0):
    pf = p.paragraph_format
    p.alignment = align
    if first_indent:
        pf.first_line_indent = Pt(first_indent)
    if left:
        pf.left_indent = Pt(left)
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    if line:
        pf.line_spacing = Pt(line)
    return p


def add_outline_level(style, level: int):
    ppr = style.element.get_or_add_pPr()
    node = ppr.find(qn("w:outlineLvl"))
    if node is None:
        node = OxmlElement("w:outlineLvl")
        insert_ordered(ppr, node, OUTLINE_AFTER)
    node.set(qn("w:val"), str(level))


def define_styles(doc):
    normal = doc.styles["Normal"]
    normal.font.name = TNR
    normal.font.size = Pt(12)
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), TNR)
    rfonts.set(qn("w:hAnsi"), TNR)
    rfonts.set(qn("w:eastAsia"), SONG)
    normal.paragraph_format.line_spacing = Pt(LINE)

    specs = [
        ("论文正文", HEI, SONG, TNR, 12.0, WD_ALIGN_PARAGRAPH.JUSTIFY, 24.0, None),
        ("论文标题一级", HEI, HEI, HEI, 16.0, WD_ALIGN_PARAGRAPH.CENTER, 0.0, 0),
        ("论文标题二级", HEI, HEI, HEI, 14.0, WD_ALIGN_PARAGRAPH.LEFT, 0.0, 1),
        ("论文标题三级", HEI, HEI, HEI, 12.0, WD_ALIGN_PARAGRAPH.LEFT, 0.0, 2),
        ("论文图题", TNR, SONG, TNR, 10.5, WD_ALIGN_PARAGRAPH.CENTER, 0.0, None),
        ("论文表题", TNR, SONG, TNR, 10.5, WD_ALIGN_PARAGRAPH.CENTER, 0.0, None),
        ("论文代码", TNR, SONG, TNR, 9.0, WD_ALIGN_PARAGRAPH.LEFT, 0.0, None),
        ("论文引用", TNR, SONG, TNR, 10.5, WD_ALIGN_PARAGRAPH.JUSTIFY, 24.0, None),
    ]
    for name, cjk, _cjk2, latin, size, align, indent, outline in specs:
        st = doc.styles.add_style(name, 1)
        st.base_style = doc.styles["Normal"]
        st.font.name = latin
        st.font.size = Pt(size)
        srpr = st.element.get_or_add_rPr()
        srf = srpr.find(qn("w:rFonts"))
        if srf is None:
            srf = OxmlElement("w:rFonts")
            srpr.append(srf)
        srf.set(qn("w:ascii"), latin)
        srf.set(qn("w:hAnsi"), latin)
        srf.set(qn("w:eastAsia"), cjk)
        pf = st.paragraph_format
        pf.alignment = align
        if indent:
            pf.first_line_indent = Pt(indent)
        if name == "论文标题一级":
            pf.space_before = Pt(LINE)
            pf.space_after = Pt(LINE)
            pf.line_spacing = Pt(LINE)
        elif name == "论文标题二级":
            pf.space_before = Pt(12)
            pf.space_after = Pt(6)
            pf.line_spacing = Pt(LINE)
        elif name == "论文标题三级":
            pf.space_before = Pt(6)
            pf.space_after = Pt(3)
            pf.line_spacing = Pt(LINE)
        elif name in ("论文图题", "论文表题"):
            pf.space_before = Pt(6)
            pf.space_after = Pt(6)
            pf.line_spacing = Pt(LINE)
        elif name == "论文代码":
            pf.line_spacing = Pt(12)
        else:
            pf.line_spacing = Pt(LINE)
        if outline is not None:
            add_outline_level(st, outline)
    return doc


def add_field(paragraph, instr: str, placeholder: str = "", cjk=SONG, latin=TNR, size=10.5):
    """插入一个 Word 域。begin / instrText / separate / result / end 必须分在不同 run 里，
    否则 Word 会报「域嵌套太深」而拒绝打开文档。"""
    def _run(child):
        r = paragraph.add_run()
        r._r.append(child)
        set_font(r, cjk, latin, size)
        return r

    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    begin.set(qn("w:dirty"), "true")
    _run(begin)

    instr_el = OxmlElement("w:instrText")
    instr_el.set(qn("xml:space"), "preserve")
    instr_el.text = instr
    _run(instr_el)

    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    _run(sep)

    if placeholder:
        r = paragraph.add_run(placeholder)
        set_font(r, cjk, latin, size)

    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    _run(end)


def add_page_field(paragraph, size=10.5):
    add_field(paragraph, " PAGE ", "1", size=size)


def style_header(section, text, double_line=False):
    section.header.is_linked_to_previous = False
    hdr = section.header
    p = hdr.paragraphs[0]
    p.text = ""
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    set_font(run, SONG, TNR, 10.5)
    ppr = p._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "double" if double_line else "single")
    bottom.set(qn("w:sz"), "8" if double_line else "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "auto")
    pbdr.append(bottom)
    insert_ordered(ppr, pbdr, PBDR_AFTER)


def style_footer_number(section, fmt="decimal", start=None):
    section.footer.is_linked_to_previous = False
    p = section.footer.paragraphs[0]
    p.text = ""
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_page_field(p)
    sect_pr = section._sectPr
    pg = sect_pr.find(qn("w:pgNumType"))
    if pg is None:
        pg = OxmlElement("w:pgNumType")
        insert_ordered(sect_pr, pg, PGNUM_AFTER)
    pg.set(qn("w:fmt"), fmt)
    if start is not None:
        pg.set(qn("w:start"), str(start))


def clear_header_footer(section):
    section.header.is_linked_to_previous = False
    section.footer.is_linked_to_previous = False
    for p in list(section.header.paragraphs):
        p.text = ""
    for p in list(section.footer.paragraphs):
        p.text = ""


# ---------------------------------------------------------------- Markdown 解析
INLINE_BOLD = re.compile(r"\*\*(.+?)\*\*")


def strip_inline(text: str) -> str:
    text = text.replace("`", "")
    text = INLINE_BOLD.sub(r"\1", text)
    text = text.replace("**", "")
    return text.strip()


INLINE_MATH = re.compile(r"\$([^$\n]+)\$")
TABLE_CAPTION = re.compile(r"^表\s*[A-Z]?\d*[-‐‑]\d+\s")


def add_body_text(paragraph, text, cjk=SONG, size=12.0, latin=TNR):
    """按 **加粗** 切分成 run；行内数学 $x$ 渲染成斜体、去掉美元符号。"""
    def _emit(chunk: str, bold: bool):
        pos = 0
        for m in INLINE_MATH.finditer(chunk):
            if m.start() > pos:
                run = paragraph.add_run(strip_inline(chunk[pos:m.start()]))
                set_font(run, cjk, latin, size, bold=bold)
            run = paragraph.add_run(m.group(1))
            set_font(run, cjk, latin, size, bold=bold)
            run.italic = True
            pos = m.end()
        if pos < len(chunk):
            run = paragraph.add_run(strip_inline(chunk[pos:]))
            set_font(run, cjk, latin, size, bold=bold)

    pos = 0
    for m in INLINE_BOLD.finditer(text):
        if m.start() > pos:
            _emit(text[pos:m.start()], False)
        _emit(m.group(1).replace("`", ""), True)
        pos = m.end()
    if pos < len(text):
        _emit(text[pos:], False)


def is_mostly_ascii(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if ord(c) < 128) / len(letters) > 0.9


def parse_markdown(path: Path):
    """返回 [(kind, payload), ...]：h1/h2/h3/para/quote/code/table/image/list/hr。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        raw = line.rstrip()
        if not raw.strip():
            i += 1
            continue
        if raw.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i].rstrip("\n"))
                i += 1
            i += 1
            blocks.append(("code", buf))
            continue
        if raw.startswith("|"):
            rows = []
            while i < n and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            blocks.append(("table", rows))
            continue
        if raw.startswith("!["):
            m = re.match(r"!\[(.*?)\]\((.*?)\)", raw)
            if m:
                blocks.append(("image", (m.group(1), m.group(2))))
            i += 1
            continue
        if raw.startswith("---") and set(raw) <= {"-", " "}:
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", raw)
        if m:
            level = len(m.group(1))
            blocks.append((f"h{level}", m.group(2).strip()))
            i += 1
            continue
        if raw.startswith(">"):
            blocks.append(("quote", raw.lstrip(">").strip()))
            i += 1
            continue
        if re.match(r"^(\d+\.|[-*])\s+", raw) and not raw.startswith("**"):
            blocks.append(("list", strip_inline(re.sub(r"^(\d+\.|[-*])\s+", "", raw))))
            i += 1
            continue
        blocks.append(("para", strip_inline(raw)))
        i += 1
    return blocks


# ---------------------------------------------------------------- 表格与插图
def three_line_table(doc, rows):
    if not rows:
        return
    cols = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "bottom"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "8")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "auto")
        borders.append(el)
    for edge in ("left", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "none")
        el.set(qn("w:sz"), "0")
        el.set(qn("w:space"), "0")
        borders.append(el)
    insert_ordered(tbl_pr, borders, TBLBORDERS_AFTER)
    for r_idx, row in enumerate(rows):
        for c_idx in range(cols):
            cell = table.cell(r_idx, c_idx)
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.line_spacing = Pt(16)
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            text = row[c_idx] if c_idx < len(row) else ""
            add_body_text(p, text.replace("\\|", "|"), SONG, 10.5)
            if r_idx == 0:
                tc_pr = cell._tc.get_or_add_tcPr()
                for run in p.runs:
                    run.font.bold = False
                tcb = OxmlElement("w:tcBorders")
                bottom = OxmlElement("w:bottom")
                bottom.set(qn("w:val"), "single")
                bottom.set(qn("w:sz"), "6")
                bottom.set(qn("w:space"), "0")
                bottom.set(qn("w:color"), "auto")
                tcb.append(bottom)
                insert_ordered(tc_pr, tcb, TCBORDERS_AFTER)
    return table


# ---------------------------------------------------------------- 文档构建
def build_cover(doc, title):
    for _ in range(2):
        p = doc.add_paragraph()
        fmt_para(p, WD_ALIGN_PARAGRAPH.CENTER, 0, LINE, 0, 0)
    p = doc.add_paragraph()
    fmt_para(p, WD_ALIGN_PARAGRAPH.CENTER, 0, LINE, 0, 0)
    set_font(p.add_run("2027 届本科毕业设计（论文）"), HEI, HEI, 26.0, bold=True)

    for _ in range(3):
        p = doc.add_paragraph()
        fmt_para(p, WD_ALIGN_PARAGRAPH.CENTER, 0, LINE, 0, 0)

    # 题目（自动换行、两行内可容纳）
    for chunk in split_title(title):
        p = doc.add_paragraph()
        fmt_para(p, WD_ALIGN_PARAGRAPH.CENTER, 0, 30.0, 0, 0)
        set_font(p.add_run(chunk), HEI, HEI, 22.0, bold=True)

    for _ in range(3):
        p = doc.add_paragraph()
        fmt_para(p, WD_ALIGN_PARAGRAPH.CENTER, 0, LINE, 0, 0)

    fields = [
        ("学    院", COVER["college"]),
        ("专    业", COVER["major"]),
        ("班    级", COVER["class_name"]),
        ("学    号", COVER["student_id"]),
        ("学生姓名", COVER["student_name"]),
        ("指导教师", COVER["teacher"]),
    ]
    for label, value in fields:
        p = doc.add_paragraph()
        fmt_para(p, WD_ALIGN_PARAGRAPH.CENTER, 0, 30.0, 0, 0)
        set_font(p.add_run(f"{label}："), SONG, SONG, 14.0)
        set_font(p.add_run(f"  {value}  "), SONG, SONG, 14.0)
        run = p.add_run("")
        set_font(run, SONG, SONG, 14.0)
        # 下划线
        ppr = p._p.get_or_add_pPr()
        pbdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), "auto")
        pbdr.append(bottom)
        insert_ordered(ppr, pbdr, PBDR_AFTER)

    for _ in range(3):
        p = doc.add_paragraph()
        fmt_para(p, WD_ALIGN_PARAGRAPH.CENTER, 0, LINE, 0, 0)
    p = doc.add_paragraph()
    fmt_para(p, WD_ALIGN_PARAGRAPH.CENTER, 0, LINE, 0, 0)
    set_font(p.add_run(COVER["date"]), SONG, TNR, 14.0)
    p = doc.add_paragraph()
    fmt_para(p, WD_ALIGN_PARAGRAPH.CENTER, 0, LINE, 0, 0)
    set_font(p.add_run("教务处制"), SONG, SONG, 14.0)


def split_title(title: str, per_line: int = 14):
    if len(title) <= per_line:
        return [title]
    mid = len(title) // 2
    best = min(range(8, len(title) - 6), key=lambda k: abs(k - mid) + (0 if title[k] in "的与和及" else 3))
    return [title[:best], title[best:]]


def build_declaration(doc):
    p = doc.add_paragraph()
    fmt_para(p, WD_ALIGN_PARAGRAPH.CENTER, 0, LINE, LINE, LINE)
    set_font(p.add_run("西京学院原创性声明"), HEI, HEI, 16.0)

    for text in DECLARATION:
        p = doc.add_paragraph()
        fmt_para(p, WD_ALIGN_PARAGRAPH.LEFT, 28.0, LINE, 6, 6)
        p.paragraph_format.line_spacing = 1.5
        set_font(p.add_run(text), SONG, TNR, 14.0)

    for _ in range(2):
        p = doc.add_paragraph()
        fmt_para(p, WD_ALIGN_PARAGRAPH.LEFT, 0, LINE, 6, 6)

    for label in ("论文作者签名：", "指导教师签名："):
        p = doc.add_paragraph()
        fmt_para(p, WD_ALIGN_PARAGRAPH.LEFT, 28.0, LINE, 18, 18)
        p.paragraph_format.line_spacing = 3.0
        set_font(p.add_run(label), SONG, TNR, 14.0)

    p = doc.add_paragraph()
    fmt_para(p, WD_ALIGN_PARAGRAPH.RIGHT, 0, LINE, 18, 0)
    set_font(p.add_run("签名日期：      年    月    日"), SONG, TNR, 14.0)


def build_abstract(doc, paras, keywords, title="摘    要"):
    p = doc.add_paragraph()
    fmt_para(p, WD_ALIGN_PARAGRAPH.CENTER, 0, LINE, LINE, LINE)
    set_font(p.add_run(title), HEI, HEI, 16.0)
    for text in paras:
        p = doc.add_paragraph()
        ascii_only = is_mostly_ascii(text)
        fmt_para(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 21.0 if ascii_only else 24.0, LINE, 0, 0)
        add_body_text(p, text, SONG, 12.0, TNR)
    if keywords:
        p = doc.add_paragraph()
        fmt_para(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 24.0, LINE, 6, 0)
        label, _, rest = keywords.partition("：")
        set_font(p.add_run(label + "："), HEI, HEI, 12.0)
        set_font(p.add_run(rest), HEI, HEI, 12.0)


def add_toc(doc, entries):
    """生成**静态**目录：每行「标题 + 点线 + 页码」，不依赖 Word 更新域。

    页码由 tools/build_toc.py 先从导出的 PDF 里量出来再回填（两遍生成），
    所以打开就是完整目录，不需要按 F9。制表位右对齐点线 pos=8958 沿用模板原值。
    """
    p = doc.add_paragraph()
    fmt_para(p, WD_ALIGN_PARAGRAPH.CENTER, 0, LINE, LINE, LINE)
    set_font(p.add_run("目    录"), HEI, HEI, 16.0)

    tabs_after = ("w:suppressAutoHyphens", "w:kinsoku", "w:wordWrap", "w:overflowPunct",
                  "w:topLinePunct", "w:autoSpaceDE", "w:autoSpaceDN", "w:bidi",
                  "w:adjustRightInd", "w:snapToGrid", "w:spacing", "w:ind")

    for entry in entries:
        level = int(entry.get("level", 1))
        p = doc.add_paragraph()
        fmt_para(p, WD_ALIGN_PARAGRAPH.LEFT, 0, LINE, 3, 3,
                 left=0.0 if level == 1 else 21.0)
        ppr = p._p.get_or_add_pPr()
        tabs = OxmlElement("w:tabs")
        tab = OxmlElement("w:tab")
        tab.set(qn("w:val"), "right")
        tab.set(qn("w:leader"), "dot")
        tab.set(qn("w:pos"), "8958")
        tabs.append(tab)
        insert_ordered(ppr, tabs, tabs_after)

        set_font(p.add_run(entry.get("text", "")), HEI if level == 1 else SONG, SONG, 12.0)
        p.add_run().add_tab()
        set_font(p.add_run(str(entry.get("page", ""))), SONG, TNR, 12.0)


def chapter_title_text(text: str) -> str:
    """「第 1 章 绪论」→「1 绪论」；模板要求数字与文字间空一格。"""
    m = re.match(r"^第\s*(\d+)\s*章\s*(.*)$", text)
    if m:
        return f"{m.group(1)} {m.group(2).strip()}"
    m = re.match(r"^附录\s*([A-Z])\s*(.*)$", text)
    if m:
        return f"附录 {m.group(1)} {m.group(2).strip()}".strip()
    return text


def build_body(doc, blocks, base_dir: Path):
    """渲染正文块；返回时已包含参考文献/致谢/附录。"""
    first_chapter = True
    for kind, payload in blocks:
        if kind == "h2":
            text = payload
            if text.startswith("第") and "章" in text:
                p = doc.add_paragraph()
                fmt_para(p, WD_ALIGN_PARAGRAPH.CENTER, 0, LINE, 24, 24)
                p.paragraph_format.keep_with_next = True
                set_font(p.add_run(chapter_title_text(text)), HEI, HEI, 16.0)
                ppr = p._p.get_or_add_pPr()
                lvl = OxmlElement("w:outlineLvl")
                lvl.set(qn("w:val"), "0")
                insert_ordered(ppr, lvl, OUTLINE_AFTER)
                first_chapter = False
                continue
            p = doc.add_paragraph()
            fmt_para(p, WD_ALIGN_PARAGRAPH.CENTER, 0, LINE, 24, 24)
            set_font(p.add_run(chapter_title_text(text)), HEI, HEI, 16.0)
            ppr = p._p.get_or_add_pPr()
            lvl = OxmlElement("w:outlineLvl")
            lvl.set(qn("w:val"), "0")
            insert_ordered(ppr, lvl, OUTLINE_AFTER)
            continue
        if kind == "h3":
            p = doc.add_paragraph()
            fmt_para(p, WD_ALIGN_PARAGRAPH.LEFT, 0, LINE, 12, 6)
            p.paragraph_format.keep_with_next = True
            set_font(p.add_run(payload), HEI, HEI, 14.0)
            ppr = p._p.get_or_add_pPr()
            lvl = OxmlElement("w:outlineLvl")
            lvl.set(qn("w:val"), "1")
            insert_ordered(ppr, lvl, OUTLINE_AFTER)
            continue
        if kind == "h4":
            p = doc.add_paragraph()
            fmt_para(p, WD_ALIGN_PARAGRAPH.LEFT, 0, LINE, 6, 3)
            set_font(p.add_run(payload), HEI, HEI, 12.0)
            ppr = p._p.get_or_add_pPr()
            lvl = OxmlElement("w:outlineLvl")
            lvl.set(qn("w:val"), "2")
            insert_ordered(ppr, lvl, OUTLINE_AFTER)
            continue
        if kind == "para":
            if TABLE_CAPTION.match(payload):
                p = doc.add_paragraph()
                fmt_para(p, WD_ALIGN_PARAGRAPH.CENTER, 0, LINE, 6, 3)
                p.paragraph_format.keep_with_next = True
                add_body_text(p, payload, SONG, 10.5)
                continue
            p = doc.add_paragraph()
            fmt_para(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 24.0, LINE, 0, 0)
            add_body_text(p, payload, SONG, 12.0)
            continue
        if kind == "list":
            p = doc.add_paragraph()
            fmt_para(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 24.0, LINE, 0, 0)
            add_body_text(p, payload, SONG, 12.0)
            continue
        if kind == "quote":
            p = doc.add_paragraph()
            fmt_para(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 24.0, LINE, 0, 0)
            add_body_text(p, payload, SONG, 10.5)
            for run in p.runs:
                run.font.color.rgb = None
            continue
        if kind == "code":
            for line in payload:
                p = doc.add_paragraph()
                fmt_para(p, WD_ALIGN_PARAGRAPH.LEFT, 0, 12.0, 0, 0)
                run = p.add_run(line if line else " ")
                set_font(run, SONG, "Consolas", 9.0)
            p = doc.add_paragraph()
            fmt_para(p, WD_ALIGN_PARAGRAPH.LEFT, 0, 6.0, 0, 0)
            continue
        if kind == "table":
            three_line_table(doc, payload)
            p = doc.add_paragraph()
            fmt_para(p, WD_ALIGN_PARAGRAPH.LEFT, 0, 8.0, 0, 0)
            continue
        if kind == "image":
            alt, rel = payload
            img_path = (base_dir / rel).resolve()
            p = doc.add_paragraph()
            fmt_para(p, WD_ALIGN_PARAGRAPH.CENTER, 0, None, 6, 0)
            # Normal 样式是固定行距 22 磅，会把内嵌图片裁成一条缝，这里改回单倍行距
            p.paragraph_format.line_spacing = 1.0
            if img_path.exists():
                p.add_run().add_picture(str(img_path), width=Cm(14.5))
            else:
                set_font(p.add_run(f"[缺图：{rel}]"), SONG, TNR, 10.5)
            cap = doc.add_paragraph()
            fmt_para(cap, WD_ALIGN_PARAGRAPH.CENTER, 0, LINE, 0, 6)
            set_font(cap.add_run(alt), SONG, TNR, 10.5)
            continue
        if kind == "h1":
            continue
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description="按西京学院论文模板排版生成 docx")
    ap.add_argument("--src", required=True, help="Markdown 源文件")
    ap.add_argument("--out", required=True, help="输出 docx 路径")
    ap.add_argument("--toc", help="目录条目 JSON（[{level,text,page}]）；不给则自动从标题生成空页码目录")
    args = ap.parse_args()

    src = Path(args.src).resolve()
    base_dir = src.parent
    blocks = parse_markdown(src)

    title = ""
    for kind, payload in blocks:
        if kind == "h1":
            title = payload
            break
    COVER["title"] = title

    # 目录条目：优先用外部 JSON（带页码），否则按标题自动生成（页码留空）
    if args.toc:
        toc_entries = json.loads(Path(args.toc).read_text(encoding="utf-8"))
    else:
        toc_entries = []
        for kind, payload in blocks:
            if kind == "h2" and not payload.startswith("摘要") \
                    and not payload.lower().startswith("abstract"):
                toc_entries.append({"level": 1, "text": chapter_title_text(payload), "page": ""})
            elif kind == "h3":
                toc_entries.append({"level": 2, "text": payload, "page": ""})

    # 切分：摘要 / ABSTRACT / 正文 / 参考文献 / 附录
    abstract_paras, abstract_kw = [], ""
    en_paras, en_kw = [], ""
    body, refs, appendix = [], [], []
    mode = "skip"
    for kind, payload in blocks:
        if kind == "h1":
            continue
        if kind == "h2":
            if payload.startswith("摘要"):
                mode = "abstract"
                continue
            if payload.lower().startswith("abstract"):
                mode = "en"
                continue
            if payload.startswith("参考文献"):
                mode = "refs"
                continue
            if payload.startswith("附录"):
                mode = "appendix"
            else:
                mode = "body"
        if mode == "abstract":
            if payload.startswith("关键词"):
                abstract_kw = payload
            elif kind == "para":
                abstract_paras.append(payload)
        elif mode == "en":
            if payload.lower().startswith("keywords"):
                en_kw = payload
            elif kind == "para":
                en_paras.append(payload)
        elif mode == "refs":
            if kind == "para" and re.match(r"^\[\d+\]", payload):
                refs.append(payload)
        elif mode == "appendix":
            appendix.append((kind, payload))
        else:
            body.append((kind, payload))

    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.7)
    sec.bottom_margin = Cm(2.7)
    sec.left_margin = Cm(2.5)
    sec.right_margin = Cm(2.5)
    sec.header_distance = Cm(1.5)
    sec.footer_distance = Cm(2.2)
    define_styles(doc)
    clear_header_footer(sec)

    # ---- 封面
    build_cover(doc, title)

    # ---- 声明页
    s2 = doc.add_section(WD_SECTION.NEW_PAGE)
    s2.page_width, s2.page_height = Cm(21.0), Cm(29.7)
    s2.top_margin, s2.bottom_margin = Cm(2.54), Cm(2.54)
    s2.left_margin, s2.right_margin = Cm(3.0), Cm(2.2)
    s2.header_distance, s2.footer_distance = Cm(1.5), Cm(2.2)
    style_header(s2, "声    明")
    build_declaration(doc)

    # ---- 摘要 / ABSTRACT / 目录
    s3 = doc.add_section(WD_SECTION.NEW_PAGE)
    s3.page_width, s3.page_height = Cm(21.0), Cm(29.7)
    s3.top_margin, s3.bottom_margin = Cm(2.54), Cm(2.54)
    s3.left_margin, s3.right_margin = Cm(3.0), Cm(2.2)
    s3.header_distance, s3.footer_distance = Cm(1.5), Cm(2.2)
    style_header(s3, title)
    style_footer_number(s3, "upperRoman", 1)
    build_abstract(doc, abstract_paras, abstract_kw, "摘    要")
    doc.add_page_break()
    build_abstract(doc, en_paras, en_kw, "ABSTRACT")
    doc.add_page_break()
    add_toc(doc, toc_entries)

    # ---- 正文
    s4 = doc.add_section(WD_SECTION.NEW_PAGE)
    s4.page_width, s4.page_height = Cm(21.0), Cm(29.7)
    s4.top_margin, s4.bottom_margin = Cm(2.54), Cm(2.54)
    s4.left_margin, s4.right_margin = Cm(3.0), Cm(2.2)
    s4.header_distance, s4.footer_distance = Cm(1.5), Cm(2.2)
    style_header(s4, title, double_line=True)
    style_footer_number(s4, "decimal", 1)

    build_body(doc, body, base_dir)

    # ---- 参考文献
    doc.add_page_break()
    p = doc.add_paragraph()
    fmt_para(p, WD_ALIGN_PARAGRAPH.CENTER, 0, LINE, 24, 24)
    set_font(p.add_run("参考文献"), HEI, HEI, 16.0)
    ppr = p._p.get_or_add_pPr()
    lvl = OxmlElement("w:outlineLvl")
    lvl.set(qn("w:val"), "0")
    insert_ordered(ppr, lvl, OUTLINE_AFTER)
    for entry in refs:
        p = doc.add_paragraph()
        fmt_para(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 0, LINE, 0, 0, left=21.0)
        p.paragraph_format.first_line_indent = Pt(-21.0)
        add_body_text(p, entry, SONG, 12.0)

    # ---- 致谢
    doc.add_page_break()
    p = doc.add_paragraph()
    fmt_para(p, WD_ALIGN_PARAGRAPH.CENTER, 0, LINE, 24, 24)
    set_font(p.add_run("致    谢"), HEI, HEI, 16.0)
    ppr = p._p.get_or_add_pPr()
    lvl = OxmlElement("w:outlineLvl")
    lvl.set(qn("w:val"), "0")
    insert_ordered(ppr, lvl, OUTLINE_AFTER)
    for text in (
        "（此处补写致谢：感谢指导教师在选题、方案设计与论文撰写过程中的指导，"
        "感谢学院各位老师在开题与中期检查中提出的修改意见，感谢同学与家人在毕业设计期间的支持与帮助。约 300—500 字。）",
    ):
        p = doc.add_paragraph()
        fmt_para(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 24.0, LINE, 0, 0)
        set_font(p.add_run(text), SONG, SONG, 12.0)

    # ---- 附录
    if appendix:
        doc.add_page_break()
        build_body(doc, appendix, base_dir)

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    paras = len(doc.paragraphs)
    tables = len(doc.tables)
    pics = len(doc.inline_shapes)
    print(f"已生成 {out}")
    print(f"段落 {paras}，表格 {tables}，图片 {pics}，大小 {out.stat().st_size:,} B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

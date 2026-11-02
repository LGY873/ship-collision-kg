# -*- coding: utf-8 -*-
"""生成标注用的 Excel 工作簿（含模型预填），人工在 Excel 里改。

用法：
    python tools/make_annotation_workbook.py --corpus data/corpus/corpus_us_seed_split.jsonl \
        --run-id preannot --out data/gold/标注工作簿.xlsx
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import DATA, iter_csv, read_jsonl, setup_logging

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

FONT = "微软雅黑"
HEAD_FILL = PatternFill("solid", fgColor="2F5597")
TITLE_FILL = PatternFill("solid", fgColor="1F3864")
BAND = PatternFill("solid", fgColor="F7F9FC")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def style_sheet(ws, headers, widths, title):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    c = ws["A1"]
    c.value = title
    c.font = Font(name=FONT, size=12, bold=True, color="FFFFFF")
    c.fill = TITLE_FILL
    c.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[1].height = 26
    for i, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=i, value=h)
        cell.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        cell.fill = HEAD_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A3"
    ws.auto_filter.ref = f"A2:{get_column_letter(len(headers))}2"


def main():
    ap = argparse.ArgumentParser(description="生成标注工作簿")
    ap.add_argument("--corpus", default=str(DATA / "corpus" / "corpus_us_seed_split.jsonl"))
    ap.add_argument("--run-id", default="preannot")
    ap.add_argument("--out", default=str(DATA / "gold" / "标注工作簿.xlsx"))
    ap.add_argument("--splits", default="dev,test")
    args = ap.parse_args()

    logger = setup_logging("make_book", DATA / "logs" / "make_book.log")
    keep = set(args.splits.split(","))
    docs = [d for d in read_jsonl(args.corpus) if d.get("split") in keep]
    docs.sort(key=lambda d: (d.get("split"), d.get("accident_no")))
    logger.info("待标注文档 %d 篇（%s）", len(docs), args.splits)

    tri_path = DATA / "runs" / args.run_id / "triples.jsonl"
    preds = {}
    if tri_path.exists():
        preds = {r["doc_id"]: r for r in read_jsonl(tri_path)}
    logger.info("已预标注 %d 篇", len(preds))

    wb = Workbook()

    # ---------- 说明 ----------
    ws = wb.active
    ws.title = "说明"
    ws["A1"] = "标注说明（先读这一页）"
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color="1F3864")
    lines = [
        "",
        "1. 你只需要改三张表里的内容，不要改表头、不要改 doc_id。",
        "2. 【文档】页：列出要标的 67 篇，已标完的把“状态”改成 已完成。",
        "3. 【实体】页：一行一个实体。实体原文必须逐字来自该篇正文（可复制粘贴）。",
        "   - 模型抽错的：把“实体类型”改对，或整行删掉",
        "   - 模型漏掉的：在最下面新增一行，填 doc_id、类型、原文",
        "   - 实体类型只能是：Accident / Ship / Person / Environment / Equipment / Organization / Consequence",
        "4. 【关系】页：一行一条关系，头尾填“实体原文”，必须和【实体】页里同一篇的某一行完全一致。",
        "   - 关系类型见第 4 行开始的对照表",
        "   - 证据句复制原文中支持这条关系的句子，不要自己改写",
        "5. 拿不准的实体类型，宁愿删掉，也不要瞎填——评分只看你确认过的。",
        "6. 全部改完保存，然后告诉我，我一键转成标准标注文件。",
        "",
        "关系类型对照（头类型 -> 尾类型）：",
    ]
    for i, text in enumerate(lines, 2):
        ws.cell(row=i, column=1, value=text).font = Font(name=FONT, size=10)
    rels = [
        ("involves_ship", "Accident -> Ship", "事故涉及哪条船"),
        ("collided_with", "Ship -> Ship", "两船相撞"),
        ("occurred_at", "Accident -> Environment", "事故发生在哪片水域"),
        ("affected_by", "Accident -> Environment", "受什么天气/水流影响"),
        ("caused_by_person", "Accident -> Person", "人的失误导致事故"),
        ("caused_by_equipment", "Accident -> Equipment", "设备故障导致事故"),
        ("caused_by_org", "Accident -> Organization", "公司管理导致事故"),
        ("led_to", "Accident -> Consequence", "事故造成什么后果"),
        ("crewed_by", "Ship -> Person", "船上配了谁"),
        ("operated_by", "Ship -> Organization", "船属于哪家公司"),
        ("equipped_with", "Ship -> Equipment", "船上装了什么设备"),
        ("involved_person", "Accident -> Person", "被事故波及的人（伤亡者）"),
    ]
    start = len(lines) + 2
    for i, (a, b, c) in enumerate(rels, start):
        ws.cell(row=i, column=1, value=a).font = Font(name=FONT, size=10)
        ws.cell(row=i, column=2, value=b).font = Font(name=FONT, size=10)
        ws.cell(row=i, column=3, value=c).font = Font(name=FONT, size=10)
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 40

    # ---------- 文档 ----------
    ws = wb.create_sheet("文档")
    style_sheet(ws, ["doc_id", "事故号", "日期", "船名", "划分", "正文长度", "预标注", "状态"],
                [24, 18, 12, 40, 8, 10, 10, 10], "要标注的文档清单（共 %d 篇）" % len(docs))
    for r, d in enumerate(docs, 3):
        has = "有" if d["doc_id"] in preds else "无"
        vals = [d["doc_id"], d.get("accident_no", ""), d.get("date", ""),
                " | ".join(d.get("vessels", []))[:60], d.get("split", ""),
                d.get("n_chars", 0), has, "未开始"]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.font = Font(name=FONT, size=9.5)
            cell.border = BORDER
            if r % 2 == 1:
                cell.fill = BAND
        if not has == "有":
            ws.cell(row=r, column=7).fill = PatternFill("solid", fgColor="FFE699")

    # ---------- 实体 ----------
    ws = wb.create_sheet("实体")
    style_sheet(ws, ["doc_id", "实体类型", "实体原文（逐字来自正文）", "备注"],
                [24, 14, 70, 26], "实体表：一行一个实体")
    r = 3
    for d in docs:
        p = preds.get(d["doc_id"])
        if not p:
            continue
        for e in p.get("entities", []):
            vals = [d["doc_id"], e.get("type", ""), e.get("text", ""), ""]
            for c, v in enumerate(vals, 1):
                cell = ws.cell(row=r, column=c, value=v)
                cell.font = Font(name=FONT, size=9.5)
                cell.border = BORDER
                cell.alignment = Alignment(vertical="top", wrap_text=(c == 3))
            r += 1

    # ---------- 关系 ----------
    ws = wb.create_sheet("关系")
    style_sheet(ws, ["doc_id", "头实体原文", "关系类型", "尾实体原文", "证据句（原文照抄）", "备注"],
                [24, 34, 22, 34, 60, 18], "关系表：一行一条关系")
    r = 3
    for d in docs:
        p = preds.get(d["doc_id"])
        if not p:
            continue
        for rel in p.get("relations", []):
            vals = [d["doc_id"], rel.get("head_text", ""), rel.get("relation", ""),
                    rel.get("tail_text", ""), rel.get("evidence", ""), ""]
            for c, v in enumerate(vals, 1):
                cell = ws.cell(row=r, column=c, value=v)
                cell.font = Font(name=FONT, size=9.5)
                cell.border = BORDER
                cell.alignment = Alignment(vertical="top", wrap_text=(c in (2, 4, 5)))
            r += 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    logger.info("已生成 %s", out)
    logger.info("实体行 %d，关系行 %d",
                wb["实体"].max_row - 2, wb["关系"].max_row - 2)


if __name__ == "__main__":
    main()

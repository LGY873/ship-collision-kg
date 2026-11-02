# -*- coding: utf-8 -*-
"""S1-1 / S1-2：把三份 Excel 合成一张“事故级”种子表。

用法：
    python src/crawl/build_seed.py \
        --us "C:/Users/18191/Desktop/美国海事汇总(1).xlsx" \
        --uk "C:/Users/18191/Desktop/英国海事(1).xlsx" \
        --out data/seed/seed.csv

要点：
  * 按“编码（美）/ 事故编号（英）”聚合，一行一事故，多船收进 vessels 列表；
  * 事故类型归一成 9 类枚举，并标记碰撞等级 A（严格 collision）/ B（碰撞相关）；
  * 日期、经纬度做范围校验，异常置空而不报错；
  * 默认只保留碰撞相关（研究边界），--all 可输出全部事故。
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import (DATA, ensure_dir, normalize_id, parse_date, parse_dms,
                    safe_filename, setup_logging, write_csv)

from openpyxl import load_workbook

TYPE_MAP = [
    (("collision", "allision", "contact", "breakaway"), "collision"),
    (("grounding", "stranding", "aground"), "grounding"),
    (("fire", "explosion"), "fire_explosion"),
    (("flood", "founder", "sinking", "sank"), "flooding"),
    (("capsiz", "listing", "melted"), "capsize"),
    (("man overboard",), "man_overboard"),
    (("injur", "fatal", "death"), "injury"),
]

COLLISION_WORDS = ("collision", "allision", "contact", "breakaway")


def map_type(raw: str) -> str:
    s = (raw or "").lower()
    if not s.strip():
        return "other"
    for keys, name in TYPE_MAP:
        if any(k in s for k in keys):
            return name
    return "other"


def collision_tier(raw: str) -> str:
    """A = 严格船-船碰撞；B = 碰撞相关（含触碰固定物）；'' = 非碰撞。"""
    s = (raw or "").lower().strip()
    if not s:
        return ""
    if s == "collision":
        return "A"
    if any(w in s for w in COLLISION_WORDS):
        return "B"
    return ""


def load_sheet(path: str):
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return [], []
    header = [str(h).strip() if h is not None else f"col{i}" for i, h in enumerate(rows[0])]
    body = [r for r in rows[1:] if any(v not in (None, "") for v in r)]
    return header, body


def col_index(header, name, default=None):
    """取第一个同名列（合并表里可能重复出现）。"""
    for i, h in enumerate(header):
        if h == name:
            return i
    return default


def cell(row, idx):
    if idx is None or idx >= len(row):
        return None
    v = row[idx]
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def build_table(path: str, source: str, logger):
    header, body = load_sheet(path)
    idx = {k: col_index(header, k) for k in
           ("编码", "事故编号", "IMO", "船舶名字", "时间", "地点", "天气", "水文",
            "经度", "维度", "事故类型", "风险影响因素", "其他影响因素", "结果")}

    groups = OrderedDict()
    for r in body:
        # 两份文件里“编码”都是事故级分组键（同一事故的多船共享一个编码），
        # 因此统一用编码聚合；编码缺失时才退回事故编号。
        key = cell(r, idx["编码"])
        key = str(int(key)) if isinstance(key, float) else str(key or "")
        if not key:
            key = normalize_id(cell(r, idx["事故编号"]))
        if not key:
            continue
        g = groups.setdefault(key, {"rows": []})
        g["rows"].append(r)

    records = []
    for key, g in groups.items():
        rows = g["rows"]
        first = rows[0]
        vessels, imos = [], []
        for r in rows:
            v = cell(r, idx["船舶名字"])
            if v and v not in vessels:
                vessels.append(str(v))
            imo = cell(r, idx["IMO"])
            if imo and str(imo) not in imos:
                imos.append(str(imo))

        raw_type = cell(first, idx["事故类型"]) or ""
        acc_no = normalize_id(cell(first, idx["事故编号"]))
        nos = {normalize_id(cell(r, idx["事故编号"])) for r in rows}
        nos.discard("")
        conflict = 1 if len(nos) > 1 else 0
        t = map_type(raw_type)
        tier = collision_tier(raw_type)
        risk = [str(cell(r, idx["风险影响因素"])) for r in rows if cell(r, idx["风险影响因素"])]
        other = [str(cell(r, idx["其他影响因素"])) for r in rows if idx.get("其他影响因素") is not None
                 and cell(r, idx["其他影响因素"])]
        outcome = cell(first, idx["结果"])

        rec = {
            "accident_key": f"{source}_{key}",
            "source": source,
            "country": source,
            "accident_no": acc_no,
            "accident_no_raw": str(cell(first, idx["事故编号"]) or ""),
            "accident_file": safe_filename(acc_no or f"{source}_{key}"),
            "vessels": vessels,
            "n_vessels": len(vessels),
            "imo": imos[0] if imos else "",
            "date_raw": str(cell(first, idx["时间"]) or ""),
            "date": parse_date(cell(first, idx["时间"])) or "",
            "location": str(cell(first, idx["地点"]) or ""),
            "lat": parse_dms(cell(first, idx["维度"]), "lat") or "",
            "lon": parse_dms(cell(first, idx["经度"]), "lon") or "",
            "accident_type_raw": raw_type,
            "accident_type": t,
            "collision_tier": tier,
            "risk_factors": " | ".join(dict.fromkeys(risk)),
            "other_factors": " | ".join(dict.fromkeys(other)),
            "outcome": str(outcome or ""),
            "weather": str(cell(first, idx["天气"]) or ""),
            "hydro": str(cell(first, idx["水文"]) or ""),
            "report_url": "",
            "priority": 1 if tier == "A" else (2 if tier == "B" else 3),
            "has_pdf": 0,
            "text_len": 0,
            "id_conflict": conflict,
            "notes": "",
        }
        records.append(rec)

    logger.info("%s: %d 行 -> %d 起事故", source, len(body), len(records))
    return records


FIELDS = ["accident_key", "source", "country", "accident_no", "accident_no_raw",
          "accident_file", "vessels", "n_vessels", "imo", "date_raw", "date",
          "location", "lat", "lon", "accident_type_raw", "accident_type",
          "collision_tier", "risk_factors", "other_factors", "outcome",
          "weather", "hydro", "report_url", "priority", "has_pdf", "text_len", "id_conflict", "notes"]


def main():
    ap = argparse.ArgumentParser(description="三份 Excel -> 事故级种子表")
    ap.add_argument("--us", required=True, help="美国海事汇总 xlsx")
    ap.add_argument("--uk", required=True, help="英国海事 xlsx")
    ap.add_argument("--out", default=str(DATA / "seed" / "seed.csv"))
    ap.add_argument("--all", action="store_true", help="保留全部事故（默认只留碰撞相关）")
    args = ap.parse_args()

    logger = setup_logging("build_seed", DATA / "logs" / "build_seed.log")
    records = []
    records += build_table(args.us, "US", logger)
    records += build_table(args.uk, "UK", logger)

    logger.info("合并后事故总数：%d", len(records))
    if not args.all:
        records = [r for r in records if r["collision_tier"]]
        logger.info("碰撞相关事故：%d", len(records))

    records.sort(key=lambda r: (r["country"], r["date"] or "9999", r["accident_key"]))

    for r in records:
        r["vessels"] = "|".join(r["vessels"])

    ensure_dir(Path(args.out).parent)
    n = write_csv(args.out, records, FIELDS)

    a = sum(1 for r in records if r["collision_tier"] == "A")
    b = sum(1 for r in records if r["collision_tier"] == "B")
    us = sum(1 for r in records if r["country"] == "US")
    uk = sum(1 for r in records if r["country"] == "UK")
    dated = sum(1 for r in records if r["date"])
    geo = sum(1 for r in records if r["lat"] != "")
    logger.info("写出 %s：%d 行（US %d / UK %d；A 级 %d / B 级 %d）", args.out, n, us, uk, a, b)
    logger.info("日期解析成功 %d/%d；经纬度有效 %d/%d", dated, n, geo, n)


if __name__ == "__main__":
    main()

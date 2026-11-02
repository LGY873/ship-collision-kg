# -*- coding: utf-8 -*-
"""公共工具：路径、日志、JSONL 读写、编号规范化、日期与经纬度解析。

所有文件读写都显式使用 UTF-8（Windows 下尤其重要）。
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONFIG = ROOT / "configs"

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

YEAR_MIN, YEAR_MAX = 1990, 2026


def ensure_dir(path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def setup_logging(name: str, logfile=None) -> logging.Logger:
    """同时输出到控制台与文件；强制 UTF-8，避免 Windows GBK 报错。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%H:%M:%S")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    if logfile:
        ensure_dir(Path(logfile).parent)
        fh = logging.FileHandler(logfile, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path, rows) -> int:
    """原子写入（先写 .tmp 再替换），避免中途崩溃留下半个文件。"""
    ensure_dir(Path(path).parent)
    tmp = f"{path}.tmp"
    n = 0
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    os.replace(tmp, path)
    return n


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    ensure_dir(Path(path).parent)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff\u00a0"), None)


def normalize_id(value) -> str:
    """事故编号规范化：去不可见字符、压缩空格、统一大写、统一 NO 写法。"""
    if value is None:
        return ""
    s = str(value).translate(_INVISIBLE).strip()
    s = re.sub(r"[\u2010-\u2015\u2212]", "-", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"^(no|NO|No)\.?\s*", "NO ", s)
    return s.upper().strip()


def safe_filename(value: str, maxlen: int = 60) -> str:
    """把事故编号变成合法文件名：NO 12/2018 -> NO_12_2018。"""
    s = normalize_id(value) or "unknown"
    s = re.sub(r'[\\/:*?"<>|]', "_", s)
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:maxlen]


def _mk_date(y, m, d):
    try:
        y, m, d = int(y), int(m), int(d)
        if not (YEAR_MIN <= y <= YEAR_MAX):
            return None
        if not (1 <= m <= 12 and 1 <= d <= 31):
            return None
        return date(y, m, d).isoformat()
    except Exception:
        return None


def parse_date(raw) -> str | None:
    """从各种写法的日期串里抽出 ISO 日期。

    支持：
      2015/5/30 0755 central daylight time
      2017-10-31, 2125 (UTC+2)
      31 October 2017
      At 02461 on 1 March 2018
    """
    if not raw:
        return None
    s = str(raw)
    m = re.search(r"(\d{4})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})", s)
    if m:
        out = _mk_date(m.group(1), m.group(2), m.group(3))
        if out:
            return out
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})", s)
    if m and m.group(2).lower() in MONTHS:
        return _mk_date(m.group(3), MONTHS[m.group(2).lower()], m.group(1))
    m = re.search(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", s)
    if m and m.group(1).lower() in MONTHS:
        return _mk_date(m.group(3), MONTHS[m.group(1).lower()], m.group(2))
    return None


_DMS = re.compile(
    r"(\d{1,3})\s*[°ºo]\s*([0-9]+(?:\.[0-9]+)?)?\s*['′]?\s*([NSEWnsew])?"
)
_DMS_SPACE = re.compile(r"^\s*(\d{1,3})\s+([0-9]+(?:\.[0-9]+)?)\s*([NSEWnsew])?\s*$")


def parse_dms(raw, kind: str) -> float | None:
    """把 90°18.7' W / 042 37.4 E / 34º14.27'S 转成十进制度。kind: lat|lon"""
    if raw is None or str(raw).strip() == "":
        return None
    s = str(raw).translate(_INVISIBLE).strip()
    m = _DMS.search(s) or _DMS_SPACE.match(s)
    if not m:
        try:
            v = float(s.replace(",", "."))
            limit = 90.0 if kind == "lat" else 180.0
            return v if abs(v) <= limit else None
        except Exception:
            return None
    deg = float(m.group(1))
    minute = float(m.group(2)) if m.group(2) else 0.0
    hemi = (m.group(3) or "").upper()
    val = deg + minute / 60.0
    if hemi in ("S", "W"):
        val = -val
    limit = 90.0 if kind == "lat" else 180.0
    if abs(val) > limit:
        return None
    return round(val, 5)


def iter_csv(path):
    import csv
    with open(path, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def write_csv(path, rows, fieldnames) -> int:
    import csv
    ensure_dir(Path(path).parent)
    n = 0
    try:
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow(r)
                n += 1
    except PermissionError as e:
        raise PermissionError(
            f"无法写入 {path}：文件可能正被 Excel/WPS 打开，或被杀毒软件占用。"
            f"请关闭该文件后重试。原始错误：{e}") from e
    return n

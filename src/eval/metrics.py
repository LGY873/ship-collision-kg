# -*- coding: utf-8 -*-
"""评测指标：实体级 / 关系级的 P/R/F1（严格与宽松两套口径）。

匹配规则：
  实体  严格：类型 + 原文大小写敏感完全一致
        宽松：类型 + 归一化文本一致（小写、去冠词标点）
  关系  严格：头尾实体严格匹配 + 关系类型一致
        宽松：头尾实体宽松匹配 + 关系类型一致
"""
from __future__ import annotations

import re
from collections import defaultdict


def norm_text(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[\u2018\u2019]", "'", s)
    s = re.sub(r"^[^a-z0-9]+", "", s)
    s = re.sub(r"^the\s+|^a\s+|^an\s+", "", s)
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff\.\-/ ]+", "", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s


def entity_set(items, strict: bool):
    out = set()
    for e in items:
        t = (e.get("text") or "").strip()
        if not t:
            continue
        key = t if strict else norm_text(t)
        out.add((e.get("type"), key))
    return out


def relation_set(items, strict: bool):
    id2text = {}
    for e in items.get("entities", []):
        t = (e.get("text") or "").strip()
        id2text[e.get("id")] = t if strict else norm_text(t)
    out = set()
    for r in items.get("relations", []):
        h, tl = id2text.get(r.get("head")), id2text.get(r.get("tail"))
        if h and tl and r.get("relation"):
            out.add((h, r["relation"], tl))
    return out


def counts(gold, pred):
    tp = len(gold & pred)
    return tp, len(pred) - tp, len(gold) - tp


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


class Accumulator:
    def __init__(self):
        self.tp = self.fp = self.fn = 0
        self.by_type = defaultdict(lambda: [0, 0, 0])

    def add(self, gold, pred, by="*"):
        tp, fp, fn = counts(gold, pred)
        slot = self.by_type[by]
        slot[0] += tp
        slot[1] += fp
        slot[2] += fn
        if by == "*":          # 只有总体计数才累加到微平均，避免按类型统计时重复计数
            self.tp += tp
            self.fp += fp
            self.fn += fn

    def result(self):
        p, r, f = prf(self.tp, self.fp, self.fn)
        return {"tp": self.tp, "fp": self.fp, "fn": self.fn,
                "p": round(p, 4), "r": round(r, 4), "f1": round(f, 4)}

    def macro(self):
        vals = [prf(*v)[2] for k, v in self.by_type.items() if k != "*" and sum(v) > 0]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

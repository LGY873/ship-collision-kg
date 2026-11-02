# -*- coding: utf-8 -*-
"""评测指标：实体级 / 关系级的 P/R/F1（严格 / 宽松 / 部分重叠 三套口径）。

匹配规则：
  实体  严格：类型 + 原文大小写敏感完全一致
        宽松：类型 + 归一化文本一致（小写、去冠词标点）
        部分：类型相同且归一化文本互相包含（或相似度 ≥ 0.8），一篇内一对一贪心配对
  关系  严格：头尾实体严格匹配 + 关系类型一致
        宽松：头尾实体宽松匹配 + 关系类型一致
        部分：先按「部分」口径把预测实体对齐到标注实体，再看关系类型与端点是否一致
"""
from __future__ import annotations

import random
import re
from collections import defaultdict
from difflib import SequenceMatcher


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


def _similar(a: str, b: str) -> float:
    """两个归一化文本的相似度，取三种视角里最高的一个。

    1. 完全相同 → 1.0
    2. 字符级包含 → 短串长度 / 长串长度
    3. 词级包含 → 短串的词有多少比例出现在长串里（处理 propeller 与
       single fixed-pitch right-hand-turning propeller 这类粒度差异）
    4. 序列相似度兜底
    """
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    scores = [SequenceMatcher(None, a, b).ratio()]
    if a in b or b in a:
        scores.append(min(len(a), len(b)) / max(len(a), len(b)))
    ta, tb = a.split(), b.split()
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if short:
        long_set = set(long_)
        scores.append(sum(1 for w in short if w in long_set) / len(short))
    return max(scores)


def align_entities(gold_items, pred_items, min_sim: float = 0.8):
    """一篇内把预测实体一对一配对到标注实体。

    「部分重叠」口径的基础：类型必须相同，归一化文本相似度 ≥ min_sim。
    贪心按相似度从高到低配对，保证一对一（同一标注实体不会被两个预测重复认领）。
    返回 {pred_id: gold_id}。
    """
    golds = [(e.get("id"), e.get("type"), norm_text(e.get("text")))
             for e in gold_items if (e.get("text") or "").strip()]
    preds = [(e.get("id"), e.get("type"), norm_text(e.get("text")))
             for e in pred_items if (e.get("text") or "").strip()]
    cand = []
    for pi, (_, ptype, ptext) in enumerate(preds):
        for gi, (_, gtype, gtext) in enumerate(golds):
            if ptype != gtype:
                continue
            sim = _similar(ptext, gtext)
            if sim >= min_sim:
                cand.append((sim, pi, gi))
    cand.sort(key=lambda x: (-x[0], x[1], x[2]))
    used_p, used_g, mapping = set(), set(), {}
    for _, pi, gi in cand:
        if pi in used_p or gi in used_g:
            continue
        used_p.add(pi)
        used_g.add(gi)
        mapping[preds[pi][0]] = golds[gi][0]
    return mapping


def partial_counts(gold_items, pred_items, min_sim: float = 0.8):
    """实体级「部分重叠」计数：tp = 配对成功的实体数。"""
    mapping = align_entities(gold_items, pred_items, min_sim)
    n_gold = sum(1 for e in gold_items if (e.get("text") or "").strip())
    n_pred = sum(1 for e in pred_items if (e.get("text") or "").strip())
    tp = len(mapping)
    return tp, n_pred - tp, n_gold - tp


def relation_partial_sets(gold, pred, min_sim: float = 0.8):
    """关系级「部分重叠」：先把预测端点映射到标注实体，再比关系三元组。

    端点没配对上的关系不能静默丢弃（那会把精确率刷高），而是保留成
    带 `#p<id>` 前缀的伪节点，必然落在 FP 里。
    """
    mapping = align_entities(gold.get("entities", []), pred.get("entities", []), min_sim)
    ptext = {e.get("id"): norm_text(e.get("text")) for e in pred.get("entities", [])}
    gtri = set()
    for r in gold.get("relations", []):
        h, t = r.get("head"), r.get("tail")
        if h and t and r.get("relation"):
            gtri.add((h, r["relation"], t))
    ptri = set()
    for r in pred.get("relations", []):
        rel = r.get("relation")
        h, t = r.get("head"), r.get("tail")
        if not rel or not h or not t:
            continue
        hk = mapping.get(h) or f"#p{h}:{ptext.get(h, '')}"
        tk = mapping.get(t) or f"#p{t}:{ptext.get(t, '')}"
        ptri.add((hk, rel, tk))
    return gtri, ptri


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
        self.add_counts(tp, fp, fn, by)

    def add_counts(self, tp, fp, fn, by="*"):
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


def bootstrap_ci(per_doc, n_boot=2000, alpha=0.05, seed=42):
    """按文档重采样求 P/R/F1 的置信区间（gold 只有 20 篇，点估计不够严谨）。

    per_doc: [(tp, fp, fn), ...] 每篇一篇
    返回 {"p": (lo, hi), "r": (lo, hi), "f1": (lo, hi)}
    """
    if not per_doc:
        return {}
    rng = random.Random(seed)
    idx = range(len(per_doc))
    samples = {"p": [], "r": [], "f1": []}
    for _ in range(n_boot):
        tp = fp = fn = 0
        for i in (rng.choice(idx) for _ in idx):
            a, b, c = per_doc[i]
            tp += a
            fp += b
            fn += c
        p, r, f = prf(tp, fp, fn)
        samples["p"].append(p)
        samples["r"].append(r)
        samples["f1"].append(f)
    out = {}
    for k, vals in samples.items():
        vals.sort()
        lo = vals[int(alpha / 2 * (len(vals) - 1))]
        hi = vals[int((1 - alpha / 2) * (len(vals) - 1))]
        out[k] = (round(lo, 4), round(hi, 4))
    return out

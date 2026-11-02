# -*- coding: utf-8 -*-
"""S5-4：抽取结果后处理（JSON 修复 -> 校验 -> 对齐 -> 归一 -> 约束 -> 去重）。

用法：
    python src/llm/postprocess.py --run-id p1_qwen7b_dev
    python src/llm/postprocess.py --run-id p1_qwen7b_dev --corpus data/corpus/corpus_fields_split.jsonl
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import DATA, ROOT, read_json, read_jsonl, setup_logging, write_jsonl
from llm.validate import load_schema, validate

RUNS = DATA / "runs"
FENCE = re.compile(r"^\s*```(?:json)?|```\s*$", re.I)

# 模型偶尔写出本体的近义关系名，直接映射回本体
REL_ALIAS = {
    "involved_ship": "involves_ship",
    "ship_involved": "involves_ship",
    "caused_by_ship": "caused_by_equipment",
}


def _close_brackets(s: str) -> str:
    """把被截断的 JSON 补齐括号：扫描到哪算哪，按栈补 ] 和 }。"""
    stack, in_str, esc = [], False, False
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
    tail = ""
    if in_str:
        tail += '"'
    for ch in reversed(stack):
        tail += "}" if ch == "{" else "]"
    return s + tail


def _repair_truncated(s: str):
    """从后往前找最后一个能闭合的位置，逐个尝试。"""
    cut_points = [i for i, ch in enumerate(s) if ch == "}"]
    for pos in reversed(cut_points[-40:]):
        cand = _close_brackets(s[: pos + 1])
        cand = re.sub(r",\s*([}\]])", r"\1", cand)
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict) and obj.get("entities") is not None:
                return obj
        except Exception:
            continue
    return None


def parse_json(raw: str):
    """尽力把模型输出解析成 JSON；失败抛 ValueError。"""
    s = FENCE.sub("", raw or "").strip()
    body = s[s.find("{"): s.rfind("}") + 1] if "{" in s else s
    for candidate in (s, body):
        try:
            return json.loads(candidate)
        except Exception:
            pass
    fixed = re.sub(r",\s*([}\]])", r"\1", body)
    try:
        return json.loads(fixed)
    except Exception:
        pass
    repaired = _repair_truncated(s)
    if repaired is not None:
        return repaired
    raise ValueError("unparseable JSON (even after repair)")


def norm_text(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[\u2018\u2019]", "'", s)
    s = re.sub(r"[\u201c\u201d]", '"', s)
    s = re.sub(r"^[^a-z0-9]+", "", s)
    s = re.sub(r"^the\s+|^a\s+|^an\s+", "", s)
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff\.\-/ ]+", "", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s


def find_in_text(needle: str, haystack_norm: str, sentences: list[str]) -> tuple[bool, float]:
    """返回 (是否原文中存在, 最佳相似度)。"""
    n = norm_text(needle)
    if not n:
        return False, 0.0
    if n in haystack_norm:
        return True, 1.0
    if len(n) < 8:
        return False, 0.0
    best = 0.0
    for s in sentences[:400]:
        if not s:
            continue
        r = difflib.SequenceMatcher(None, n, norm_text(s)).ratio()
        if r > best:
            best = r
            if best >= 0.95:
                break
    return best >= 0.9, best


AUTHORITY_WORDS = ("national transportation safety board", "ntsb", "maib",
                   "safety board", "transportation safety board",
                   "marine accident investigation")


def synth_accident(doc: dict, text_norm: str) -> dict:
    """从文档元数据合成 Accident 节点。

    为什么需要：模型经常把第一艘船当作句子的主语，于是所有事故级关系都被挂到
    Ship 上、撞 domain/range 检查全部丢弃（实测 21 条关系只留下 1 条）。事故号、
    日期、地点这些其实在语料元数据里就有，直接补一个 Accident 节点比丢掉关系划算。
    节点带 synthesized=True，评测时可按需要排除。
    """
    no = (doc.get("accident_no") or "").strip()
    text = no or (doc.get("accident_key") or "accident")
    attrs = {
        "accident_no": no,
        "type": doc.get("accident_type") or "",
        "date": doc.get("date") or "",
        "country": doc.get("country") or "",
        "location": doc.get("location") or "",
        "severity": doc.get("collision_tier") or "",
    }
    aligned = bool(no) and norm_text(no) in text_norm
    return {"id": "", "type": "Accident", "text": text, "text_norm": norm_text(text),
            "attributes": {k: v for k, v in attrs.items() if v},
            "aligned": aligned, "align_ratio": 1.0 if aligned else 0.0,
            "synthesized": True}


def is_authority(ent: dict) -> bool:
    """调查机构不是事故参与方，即使模型抽出来也要丢掉。"""
    if ent.get("type") != "Organization":
        return False
    name = (ent.get("text") or "").lower()
    return any(w in name for w in AUTHORITY_WORDS)


def main():
    ap = argparse.ArgumentParser(description="后处理")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--corpus", default=str(DATA / "corpus" / "corpus_us_seed_split.jsonl"))
    ap.add_argument("--out", default="")
    ap.add_argument("--min-evidence-ratio", type=float, default=0.85)
    ap.add_argument("--drop-low-evidence", action="store_true",
                    help="证据命中率低于阈值的关系直接丢弃（默认只打标记，便于论文对比）")
    ap.add_argument("--no-synth-accident", action="store_true",
                    help="不从文档元数据补 Accident 节点（用于消融对比）")
    args = ap.parse_args()

    run_dir = RUNS / args.run_id
    logger = setup_logging(f"post.{args.run_id}", run_dir / "post.log")
    schema = load_schema(ROOT / "schemas" / "extraction.schema.json")
    onto = read_json(ROOT / "ontology" / "ontology.json")

    docs = {r["doc_id"]: r for r in read_jsonl(args.corpus)}
    files = sorted((run_dir / "raw").glob("*.json"))
    logger.info("待处理 %d 篇", len(files))

    out_rows, error_rows = [], []
    stats = {"json_ok": 0, "schema_ok": 0, "ent_total": 0, "ent_aligned": 0,
             "rel_total": 0, "rel_kept": 0, "rel_evidence_ok": 0,
             "rel_repaired": 0, "acc_synth": 0}

    for f in files:
        rec = read_json(f)
        doc = docs.get(rec["doc_id"])
        if doc is None:
            error_rows.append({"doc_id": rec["doc_id"], "stage": "corpus", "detail": "not found"})
            continue
        try:
            obj = parse_json(rec.get("raw", ""))
            stats["json_ok"] += 1
        except ValueError as e:
            error_rows.append({"doc_id": rec["doc_id"], "stage": "json", "detail": str(e)})
            continue

        errs = validate(obj, schema)
        if errs:
            error_rows.append({"doc_id": rec["doc_id"], "stage": "schema",
                               "detail": "; ".join(errs[:3])})
        else:
            stats["schema_ok"] += 1

        text = doc.get("text", "")
        text_norm = norm_text(text)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]

        # ---- 实体 ----
        entities, id_map, seen = [], {}, {}
        for e in obj.get("entities", []):
            etype = e.get("type")
            etext = (e.get("text") or "").strip()
            if etype not in onto["entities"] or not etext:
                error_rows.append({"doc_id": rec["doc_id"], "stage": "entity_type",
                                   "detail": f"{etype}:{etext[:60]}"})
                continue
            aligned, ratio = find_in_text(etext, text_norm, sentences)
            stats["ent_total"] += 1
            if aligned:
                stats["ent_aligned"] += 1
            key = (etype, norm_text(etext))
            if key in seen:
                id_map[e.get("id")] = seen[key]
                continue
            ent = {"id": f"e{len(entities) + 1}", "type": etype, "text": etext,
                   "text_norm": norm_text(etext),
                   "attributes": e.get("attributes") or {},
                   "aligned": aligned, "align_ratio": round(ratio, 3)}
            entities.append(ent)
            seen[key] = ent["id"]
            id_map[e.get("id") or f"e{len(entities)}"] = ent["id"]

        # 丢掉调查机构（NTSB/MAIB 等）
        authority_ids = {e["id"] for e in entities if is_authority(e)}
        if authority_ids:
            id_map = {k: v for k, v in id_map.items() if v not in authority_ids}
            entities = [e for e in entities if e["id"] not in authority_ids]

        # ---- 事故节点：模型没给就从元数据补 ----
        acc = next((e for e in entities if e["type"] == "Accident"), None)
        acc_synth = False
        if acc is None and not args.no_synth_accident:
            acc = synth_accident(doc, text_norm)
            acc["id"] = f"e{len(entities) + 1}"
            entities.append(acc)
            acc_synth = True
            stats["acc_synth"] += 1

        # ---- 关系 ----
        by_id = {e["id"]: e for e in entities}
        acc_id = acc["id"] if acc else None
        relations, rel_seen = [], set()
        for r in obj.get("relations", []):
            hid, tid = id_map.get(r.get("head")), id_map.get(r.get("tail"))
            rel = REL_ALIAS.get((r.get("relation") or "").strip(), (r.get("relation") or "").strip())
            ev = (r.get("evidence") or "").strip()
            stats["rel_total"] += 1
            if not hid or not tid or rel not in onto["relations"] or hid == tid:
                error_rows.append({"doc_id": rec["doc_id"], "stage": "relation",
                                   "detail": f"{r.get('head')}-{rel}->{r.get('tail')}"})
                continue
            spec = onto["relations"][rel]
            repaired = False
            if by_id[hid]["type"] not in spec["domain"] or by_id[tid]["type"] not in spec["range"]:
                # 修复规则：事故级关系被模型挂到了参与方（Ship/Person…）身上，
                # 但尾实体类型合法 → 把 head 换成事故节点，而不是整条丢掉。
                if (acc_id and hid != acc_id and tid != acc_id
                        and spec["domain"] == ["Accident"]
                        and by_id[tid]["type"] in spec["range"]
                        and by_id[hid]["type"] in ("Ship", "Person", "Organization", "Environment")):
                    hid = acc_id
                    repaired = True
                    stats["rel_repaired"] += 1
                else:
                    error_rows.append({"doc_id": rec["doc_id"], "stage": "domain_range",
                                       "detail": f"{by_id[hid]['type']}-{rel}->{by_id[tid]['type']}"})
                    continue
            ev_ok, ev_ratio = find_in_text(ev, text_norm, sentences)
            if ev_ratio >= args.min_evidence_ratio:
                stats["rel_evidence_ok"] += 1
            elif args.drop_low_evidence:
                error_rows.append({"doc_id": rec["doc_id"], "stage": "evidence",
                                   "detail": f"{rel} ratio={ev_ratio:.2f}"})
                continue
            key = (hid, rel, tid)
            if key in rel_seen:
                continue
            rel_seen.add(key)
            factor = ""
            for cls, cspec in onto.get("factor_classes", {}).items():
                if rel in cspec["relations"]:
                    factor = cls
            relations.append({"head": hid, "head_text": by_id[hid]["text"],
                              "relation": rel,
                              "tail": tid, "tail_text": by_id[tid]["text"],
                              "evidence": ev, "evidence_ok": ev_ok,
                              "evidence_ratio": round(ev_ratio, 3),
                              "repaired": repaired,
                              "factor_class": factor})
            stats["rel_kept"] += 1

        out_rows.append({
            "doc_id": rec["doc_id"],
            "accident_no": doc.get("accident_no"),
            "source": doc.get("country"),
            "accident_type": doc.get("accident_type"),
            "collision_tier": doc.get("collision_tier"),
            "split": doc.get("split"),
            "model": rec.get("model"),
            "strategy": rec.get("strategy"),
            "accident": obj.get("accident", {}),
            "accident_synth": acc_synth,
            "entities": entities,
            "relations": relations,
            "n_entities": len(entities),
            "n_relations": len(relations),
            "json_ok": True,
            "schema_ok": not errs,
        })

    out_path = Path(args.out or run_dir / "triples.jsonl")
    write_jsonl(out_path, out_rows)
    if error_rows:
        write_jsonl(run_dir / "errors.jsonl", error_rows)

    n = max(1, len(files))
    logger.info("完成 %d 篇：JSON 合法 %.1f%%  通过 schema %.1f%%",
                len(out_rows), 100.0 * stats["json_ok"] / n, 100.0 * stats["schema_ok"] / n)
    logger.info("实体 %d 个，原文对齐 %.1f%%；关系保留 %d/%d（其中事故 head 修复 %d 条），证据命中 %.1f%%",
                stats["ent_total"],
                100.0 * stats["ent_aligned"] / max(1, stats["ent_total"]),
                stats["rel_kept"], stats["rel_total"], stats["rel_repaired"],
                100.0 * stats["rel_evidence_ok"] / max(1, stats["rel_total"]))
    logger.info("补充 Accident 节点的文档 %d 篇", stats["acc_synth"])
    logger.info("结果：%s；错误记录：%s", out_path, run_dir / "errors.jsonl")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""离线回归测试：不连模型、不连数据库，验证链路上的关键约束。

覆盖的坑（每一条都曾经真的把流程弄坏过）：
  T1 分节与抽取：MAIB/CN 排版要能识别；cause 必须在输入里；截断落在句末
  T2 JSON 修复：代码块包裹、被 max_tokens 截断的输出都要能救回来
  T3 后处理：模型不给 Accident 节点时从元数据补齐；事故级关系挂错 head 要能修复
  T4 图谱导出：节点带属性（props）；Person 不按 role 合并；Accident 用事故号做 gid
  T5 评测：gold 里有、模型没跑的文档要计成 FN

用法：
    python tools/smoke_test.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
RUNS = ROOT / "data" / "runs"
TMP_RUN = "smoke_tmp"
FAILED: list[str] = []


def ok(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  [OK]   {name}")
    else:
        print(f"  [FAIL] {name} {detail}")
        FAILED.append(name)


def call(script: str, *args: str) -> subprocess.CompletedProcess:
    r = subprocess.run([PY, str(ROOT / script), *args], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stdout[-1500:])
        print(r.stderr[-1500:])
    return r


def t1_segment() -> None:
    print("T1 分节与抽取")
    sys.path.insert(0, str(ROOT / "src" / "prep"))
    from segment import extract_for_extraction, split_sections  # noqa: E402

    text = "\n".join([
        "SYNOPSIS",
        "A short summary of the collision between two vessels.",
        "SECTION 1 - FACTUAL INFORMATION",
        "The vessel was on passage in clear weather. " * 600,
        "SECTION 2 - ANALYSIS",
        "The watchkeeper did not keep a proper lookout. " * 600,
        "SECTION 3 - CONCLUSIONS",
        "The collision was avoidable. " * 100,
        "3.2 Causes",
        "The collision occurred because the watchkeeper was inattentive and the"
        " vessel was not keeping a proper lookout at the time.",
    ])
    secs = split_sections(text)
    ok("MAIB 排版能分节", secs.get("sectioned") is True and "cause" in secs,
       f"分到 {[k for k in secs if not k.startswith('_')]}")
    out = extract_for_extraction(secs, max_chars=8000)
    ok("抽取输入包含事故原因", "## CAUSE" in out and "watchkeeper" in out)
    ok("抽取输入不超过预算", len(out) <= 8000, f"len={len(out)}")
    ok("截断落在句末", out.rstrip().endswith((".", "!", "?")), repr(out[-40:]))

    # 分节失败时也要有内容（旧版对中文报告会给出空串）
    plain = split_sections("一、事故概况\n某轮与某轮发生碰撞。" * 300)
    out2 = extract_for_extraction(plain, max_chars=2000)
    ok("无分节时回退到全文", len(out2) > 500, f"len={len(out2)}")


def t2_parse_json() -> None:
    print("T2 JSON 修复")
    sys.path.insert(0, str(ROOT / "src"))
    from llm.postprocess import parse_json  # noqa: E402

    ok("代码块包裹", parse_json('```json\n{"entities": []}\n```') == {"entities": []})
    ok("尾逗号", parse_json('{"entities": [],}') == {"entities": []})
    truncated = json.dumps({"entities": [{"id": f"e{i}", "type": "Ship", "text": f"v{i}"}
                                         for i in range(8)]})[:-30]
    obj = parse_json(truncated)
    ok("截断输出可修复", isinstance(obj, dict) and bool(obj.get("entities")))


def t3_postprocess() -> None:
    print("T3 后处理（事故节点补齐 + 关系修复）")
    work = Path(tempfile.mkdtemp(prefix="smoke_"))
    corpus = work / "corpus.jsonl"
    doc_text = ("Collision accident report NO TEST001. The vessels ALPHA and BETA collided"
                " in dense fog. The master of ALPHA was inattentive. The weather was poor.")
    corpus.write_text(json.dumps({
        "doc_id": "t1", "split": "test", "accident_no": "TEST001",
        "country": "US", "accident_type": "collision", "collision_tier": "1",
        "date": "2020-01-02", "location": "Test Strait", "text": doc_text,
        "sectioned": True, "lang": "en"}, ensure_ascii=False) + "\n", encoding="utf-8")

    run_dir = RUNS / TMP_RUN
    shutil.rmtree(run_dir, ignore_errors=True)
    (run_dir / "raw").mkdir(parents=True)
    raw = {"doc_id": "t1", "model": "fake", "strategy": "p1", "raw": json.dumps({
        "entities": [
            {"id": "e1", "type": "Ship", "text": "ALPHA", "attributes": {"name": "ALPHA"}},
            {"id": "e2", "type": "Environment", "text": "dense fog", "attributes": {}},
            {"id": "e3", "type": "Person", "text": "master of ALPHA", "attributes": {"role": "master"}},
        ],
        "relations": [
            {"head": "e1", "relation": "affected_by", "tail": "e2",
             "evidence": "collided in dense fog"},
            {"head": "e1", "relation": "caused_by_person", "tail": "e3",
             "evidence": "The master of ALPHA was inattentive"},
        ]}, ensure_ascii=False), "error": ""}
    (run_dir / "raw" / "t1.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    r = call("src/llm/postprocess.py", "--run-id", TMP_RUN, "--corpus", str(corpus))
    ok("后处理可跑通", r.returncode == 0)
    rows = [json.loads(line) for line in
            (run_dir / "triples.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    doc = rows[0]
    acc = [e for e in doc["entities"] if e["type"] == "Accident"]
    ok("补齐 Accident 节点", len(acc) == 1 and acc[0]["text"] == "TEST001")
    acc_id = acc[0]["id"] if acc else ""
    repaired = [r for r in doc["relations"] if r.get("repaired")]
    ok("事故级关系挂错 head 被修复",
       len(repaired) == 2 and all(r["head"] == acc_id for r in repaired),
       f"repaired={len(repaired)}")

    r = call("src/kg/build_nodes.py", "--runs", TMP_RUN, "--out-dir", str(work / "kg"))
    ok("导出 CSV 可跑通", r.returncode == 0)
    import csv
    # write_csv 用 utf-8-sig（Excel 友好），读的时候必须同样编码，否则首列名带 BOM
    with open(work / "kg" / "nodes.csv", encoding="utf-8-sig", newline="") as f:
        nodes = list(csv.DictReader(f))
    acc_row = [n for n in nodes if n["label"] == "Accident"]
    ok("Accident 用事故号做 gid", acc_row and acc_row[0]["gid"] == "Accident:test001",
       acc_row[0]["gid"] if acc_row else "no accident node")
    ok("节点属性落在 props 列", bool(acc_row) and "accident_no" in acc_row[0]["props"],
       acc_row[0]["props"][:80] if acc_row else "")
    persons = [n for n in nodes if n["label"] == "Person"]
    ok("Person 不按 role 合并", len(persons) == 1 and persons[0]["gid"] == "Person:master_of_alpha",
       [p["gid"] for p in persons])


def t5_evaluate() -> None:
    print("T4 评测（FN 口径）")
    work = Path(tempfile.mkdtemp(prefix="smoke_eval_"))
    gold = work / "gold.jsonl"
    gold.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in [
        {"doc_id": "t1", "split": "test", "country": "US", "entities": [
            {"id": "e1", "type": "Accident", "text": "TEST001"},
            {"id": "e2", "type": "Ship", "text": "ALPHA"}], "relations": []},
        {"doc_id": "t2", "split": "test", "country": "US", "entities": [
            {"id": "e1", "type": "Accident", "text": "TEST002"}], "relations": []},
    ]) + "\n", encoding="utf-8")

    run_dir = RUNS / TMP_RUN
    (run_dir / "triples.jsonl").write_text(json.dumps({
        "doc_id": "t1", "country": "US",
        "entities": [{"id": "e1", "type": "Accident", "text": "TEST001"},
                     {"id": "e2", "type": "Ship", "text": "ALPHA"}],
        "relations": []}, ensure_ascii=False) + "\n", encoding="utf-8")

    r = call("src/eval/evaluate.py", "--run-id", TMP_RUN, "--gold", str(gold), "--split", "test")
    ok("评测可跑通", r.returncode == 0)
    out = json.loads((run_dir / f"{TMP_RUN}_eval.json").read_text(encoding="utf-8"))
    ok("未预测的 gold 文档计入 FN", out["n_docs"] == 2, f"n_docs={out['n_docs']}")
    ent = [m for m in out["metrics"] if m["level"] == "entity" and m["match"] == "strict"][0]
    ok("召回被 FN 拉低（不是 1.0）", ent["r"] < 1.0 and ent["fn"] >= 1, str(ent))


def main() -> int:
    print(f"项目根目录：{ROOT}")
    for fn in (t1_segment, t2_parse_json, t3_postprocess, t5_evaluate):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            print(f"  [FAIL] {fn.__name__} 抛异常：{e}")
            FAILED.append(fn.__name__)
    shutil.rmtree(RUNS / TMP_RUN, ignore_errors=True)
    print()
    if FAILED:
        print(f"失败 {len(FAILED)} 项：{FAILED}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())

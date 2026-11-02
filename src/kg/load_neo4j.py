# -*- coding: utf-8 -*-
"""S6-2：把 nodes.csv / rels.csv 导入 Neo4j。

前置：pip install neo4j；Neo4j 5.x 已启动（默认 bolt://localhost:7687）。
环境变量：NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD

用法：
    python src/kg/load_neo4j.py --nodes data/kg/nodes.csv --rels data/kg/rels.csv
    python src/kg/load_neo4j.py --reset          # 先清空再导入（谨慎）
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import DATA, setup_logging

LABELS = ["Accident", "Ship", "Person", "Environment", "Equipment", "Organization", "Consequence"]
BATCH = 500


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def main():
    ap = argparse.ArgumentParser(description="导入 Neo4j")
    ap.add_argument("--nodes", default=str(DATA / "kg" / "nodes.csv"))
    ap.add_argument("--rels", default=str(DATA / "kg" / "rels.csv"))
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()

    logger = setup_logging("load_neo4j", DATA / "logs" / "load_neo4j.log")
    try:
        from neo4j import GraphDatabase  # type: ignore
    except ImportError:
        logger.error("未安装 neo4j 驱动：pip install neo4j")
        return

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    pwd = os.environ.get("NEO4J_PASSWORD", "neo4j12345")
    driver = GraphDatabase.driver(uri, auth=(user, pwd))

    with driver.session() as s:
        s.run("RETURN 1")
        logger.info("已连接 %s", uri)
        if args.reset:
            s.run("MATCH (n) DETACH DELETE n")
            logger.warning("已清空数据库")

        # 约束（Neo4j 5 语法）
        for label in LABELS:
            s.run(f"CREATE CONSTRAINT {label.lower()}_gid IF NOT EXISTS "
                  f"FOR (n:{label}) REQUIRE n.gid IS UNIQUE")
        s.run("CREATE INDEX acc_no IF NOT EXISTS FOR (a:Accident) ON (a.accident_no)")
        logger.info("约束与索引就绪")

        # 节点：按 label 分批 MERGE。
        # 本体里定义的 7 类属性存在 nodes.csv 的 props 列（JSON），必须一并导入，
        # 否则 Accident 的日期/严重度、Ship 的 IMO/船旗在图上全丢，q3/q5 这类查询直接查空。
        rows = list(read_csv(args.nodes))

        def _flat(props_json: str) -> dict:
            """Neo4j 节点属性只能是标量，dict/list 一律转成 JSON 字符串。"""
            try:
                d = json.loads(props_json or "{}")
            except Exception:  # noqa: BLE001
                return {}
            out = {}
            for k, v in (d or {}).items():
                if v in (None, "", [], {}):
                    continue
                out[k] = v if isinstance(v, (str, int, float, bool)) else json.dumps(v, ensure_ascii=False)
            return out

        for label in LABELS:
            batch = [r for r in rows if r["label"] == label]
            keys = sorted({k for r in batch for k in _flat(r.get("props", ""))})
            extra = "".join(f", n.`{k}` = row.`{k}`" for k in keys)
            for i in range(0, len(batch), BATCH):
                chunk = batch[i:i + BATCH]
                s.run(
                    f"UNWIND $rows AS row "
                    f"MERGE (n:{label} {{gid: row.gid}}) "
                    f"SET n.name = row.name, n.n_docs = toInteger(row.n_docs), "
                    f"    n.source_docs = row.source_docs" + extra,
                    rows=[{"gid": r["gid"], "name": r["name"], "n_docs": r["n_docs"],
                           "source_docs": r["source_docs"], **_flat(r.get("props", ""))}
                          for r in chunk],
                )
            logger.info("节点 %-12s %d（属性字段 %d 个）", label, len(batch), len(keys))

        # 关系：按类型分批
        rels = list(read_csv(args.rels))
        by_rel = {}
        for r in rels:
            by_rel.setdefault(r["rel"], []).append(r)
        for rel, batch in by_rel.items():
            for i in range(0, len(batch), BATCH):
                chunk = batch[i:i + BATCH]
                s.run(
                    f"UNWIND $rows AS row "
                    f"MATCH (h {{gid: row.head}}) MATCH (t {{gid: row.tail}}) "
                    f"MERGE (h)-[r:`{rel}`]->(t) "
                    f"SET r.source_doc = row.source_doc, r.accident_no = row.accident_no, "
                    f"    r.model = row.model, r.run_id = row.run_id, "
                    f"    r.confidence = toFloat(row.confidence), r.evidence = row.evidence",
                    rows=[{"head": r["head"], "tail": r["tail"], "source_doc": r["source_doc"],
                           "accident_no": r["accident_no"], "model": r["model"],
                           "run_id": r["run_id"], "confidence": r["confidence"],
                           "evidence": r["evidence"]} for r in chunk],
                )
            logger.info("关系 %-22s %d", rel, len(batch))

        counts = s.run(
            "MATCH (n) RETURN count(n) AS nodes, "
            "sum(CASE WHEN n:Accident THEN 1 ELSE 0 END) AS accidents").single()
        rc = s.run("MATCH ()-[r]->() RETURN count(r) AS rels").single()
        logger.info("导入完成：节点 %d（事故 %d），关系 %d",
                    counts["nodes"], counts["accidents"], rc["rels"])

    driver.close()


if __name__ == "__main__":
    main()

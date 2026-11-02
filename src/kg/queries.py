# -*- coding: utf-8 -*-
"""S6-3：8 条分析查询。既能直接跑，也能当论文与答辩的查询脚本。

用法：
    python src/kg/queries.py --list
    python src/kg/queries.py --run q1 --limit 20
    python src/kg/queries.py --run q8 --param DCA15LM023
"""
from __future__ import annotations

import argparse
import os

QUERIES = {
    "q1": {
        "title": "高频致因因素 Top 20",
        "cypher": """
MATCH (a:Accident)-[r]->(f)
WHERE type(r) IN ['caused_by_person','caused_by_equipment','caused_by_org','affected_by']
RETURN labels(f)[0] AS factor_type, f.name AS factor,
       type(r) AS relation, count(DISTINCT a) AS n
ORDER BY n DESC LIMIT $limit
""",
        "note": "按事故数去重计数，避免同一事故多船重复计数",
    },
    "q2": {
        "title": "因素共现（同一事故中同时出现的因素对）",
        "cypher": """
MATCH (a:Accident)-[:caused_by_person|affected_by|caused_by_equipment|caused_by_org]->(f1)
MATCH (a)-[:caused_by_person|affected_by|caused_by_equipment|caused_by_org]->(f2)
WHERE f1.gid < f2.gid
RETURN f1.name AS f1, f2.name AS f2, count(DISTINCT a) AS co_occur
ORDER BY co_occur DESC LIMIT $limit
""",
        "note": "找“叠加风险”组合，可画共现网络",
    },
    "q3": {
        "title": "国别差异：事故数与因素类型分布",
        "cypher": """
MATCH (a:Accident)-[r]->(f)
WHERE a.country IS NOT NULL AND a.country <> ''
RETURN a.country AS country, type(r) AS relation,
       count(DISTINCT a) AS accidents, count(*) AS edges
ORDER BY country, edges DESC LIMIT $limit
""",
        "note": "a.country 来自 nodes.csv 的 props，只在 load_neo4j 导入属性后才有值",
    },
    "q4": {
        "title": "船型—事故类型关联",
        "cypher": """
MATCH (a:Accident)-[:involves_ship]->(s:Ship)
RETURN coalesce(s.ship_type, 'unknown') AS ship_type,
       coalesce(a.type, 'unknown') AS accident_type,
       count(DISTINCT a) AS accidents, count(*) AS n
ORDER BY n DESC LIMIT $limit
""",
        "note": "ship_type / a.type 都来自 props 属性，需要属性导入生效",
    },
    "q5": {
        "title": "时间趋势",
        "cypher": """
MATCH (a:Accident)
WHERE a.date IS NOT NULL AND a.date <> ''
WITH a, substring(a.date, 0, 4) AS year
WHERE year =~ '[0-9][0-9][0-9][0-9]'
OPTIONAL MATCH (a)-[:led_to]->(c:Consequence)
RETURN year, count(DISTINCT a) AS accidents, count(c) AS consequences
ORDER BY year LIMIT $limit
""",
        "note": "按 Accident.date 取年份，不再从 name 前 4 位猜",
    },
    "q6": {
        "title": "节点中心性（度）",
        "cypher": """
MATCH (n)-[r]-()
WHERE NOT n:Accident
RETURN labels(n)[0] AS label, n.name AS name, count(r) AS degree
ORDER BY degree DESC LIMIT $limit
""",
        "note": "哪些因素处在风险网络中心",
    },
    "q7": {
        "title": "两跳路径：事故 -> 因素 -> 后果",
        "cypher": """
MATCH p=(a:Accident)-[:caused_by_person|affected_by|caused_by_equipment|caused_by_org]->(f)
        -[]->(c:Consequence)
RETURN p LIMIT $limit
""",
        "note": "用于“因素—后果”传导链示意",
    },
    "q8": {
        "title": "单事故子图（案例展示）",
        "cypher": """
MATCH p=(a:Accident {gid: $param})-[*1..2]-(x)
RETURN p LIMIT $limit
""",
        "note": "答辩演示：点开一条边看 source_doc 与 evidence",
    },
}


def main():
    ap = argparse.ArgumentParser(description="分析查询")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--run", choices=list(QUERIES))
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--param", default="",
                    help="q8 用的事故 gid；留空则自动挑第一个 Accident")
    args = ap.parse_args()

    if args.list or not args.run:
        for k, q in QUERIES.items():
            print(f"{k}  {q['title']}\n    {q['note']}")
        return

    q = QUERIES[args.run]
    print(f"# {q['title']}\n{q['cypher'].strip()}\n")
    try:
        from neo4j import GraphDatabase  # type: ignore
    except ImportError:
        print("（未安装 neo4j 驱动，以上仅为查询语句）")
        return

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    pwd = os.environ.get("NEO4J_PASSWORD", "neo4j12345")
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    with driver.session() as s:
        param = args.param
        if not param:
            # 默认参数写死一个不存在的事故号是旧 bug；改成从库里取
            rec = s.run("MATCH (a:Accident) RETURN a.gid AS gid LIMIT 1").single()
            param = rec["gid"] if rec else ""
            if param:
                print(f"（自动选用事故：{param}）")
        rows = list(s.run(q["cypher"], limit=args.limit, param=param))
        for r in rows:
            print(dict(r))
        print(f"共 {len(rows)} 行")
    driver.close()


if __name__ == "__main__":
    main()

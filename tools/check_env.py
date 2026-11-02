# -*- coding: utf-8 -*-
"""环境自检：一条命令看清“还差什么”。建议每次换机器先跑一遍。

    python tools/check_env.py
"""
from __future__ import annotations

import json
import os
import socket
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

OK, BAD, WARN = "[OK]  ", "[FAIL]", "[WARN]"


def check_python():
    v = sys.version_info
    ok = (3, 10) <= (v.major, v.minor) < (3, 13)
    print(f"{OK if ok else WARN} Python {v.major}.{v.minor}.{v.micro}"
          + ("" if ok else "（建议 3.10/3.11）"))


def check_imports():
    mods = [("openpyxl", True), ("pdfplumber", False), ("fitz", False),
            ("neo4j", False), ("pandas", False), ("matplotlib", False)]
    for name, required in mods:
        try:
            __import__(name)
            print(f"{OK} 依赖 {name}")
        except ImportError:
            tag = BAD if required else WARN
            print(f"{tag} 依赖 {name} 未安装" + ("" if required else "（可选，装不上可跳过）"))


def check_files():
    need = [
        (ROOT / "ontology" / "ontology.json", True),
        (ROOT / "schemas" / "extraction.schema.json", True),
        (ROOT / "data" / "seed" / "seed.csv", True),
        (ROOT / "data" / "corpus" / "corpus_fields_split.jsonl", False),
        (ROOT / "data" / "gold" / "gold.jsonl", False),
    ]
    for p, required in need:
        if p.exists():
            size = p.stat().st_size
            print(f"{OK} {p.relative_to(ROOT)}  ({size:,} B)")
        else:
            print(f"{BAD if required else WARN} 缺少 {p.relative_to(ROOT)}")


def check_seed():
    p = ROOT / "data" / "seed" / "seed.csv"
    if not p.exists():
        return
    import csv
    with open(p, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    a = sum(1 for r in rows if r.get("collision_tier") == "A")
    print(f"{OK} 种子表 {len(rows)} 起（严格碰撞 {a} 起）")
    if len(rows) < 200:
        print(f"{WARN} 种子数量偏少，检查 Excel 路径与过滤条件")


def check_ollama():
    url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=3) as r:
            data = json.loads(r.read().decode())
        names = [m.get("name", "") for m in data.get("models", [])]
        print(f"{OK} Ollama 可访问，已安装 {len(names)} 个模型")
        for n in names[:8]:
            print(f"       - {n}")
    except Exception as e:  # noqa: BLE001
        print(f"{WARN} Ollama 不可访问（{url}）：{e}")


def check_neo4j():
    host, port = "127.0.0.1", 7687
    try:
        with socket.create_connection((host, port), timeout=3):
            print(f"{OK} Neo4j 端口 {port} 可连接")
    except Exception:  # noqa: BLE001
        print(f"{WARN} Neo4j 端口 {port} 未监听（没启动可忽略）")


if __name__ == "__main__":
    print("=" * 60)
    print("ship-collision-kg 环境自检")
    print("=" * 60)
    check_python()
    print("-" * 60)
    check_imports()
    print("-" * 60)
    check_files()
    check_seed()
    print("-" * 60)
    check_ollama()
    check_neo4j()
    print("=" * 60)

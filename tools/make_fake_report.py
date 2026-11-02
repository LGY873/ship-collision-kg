# -*- coding: utf-8 -*-
"""造一份“假报告”用于在没有 PDF 的情况下测试解析/清洗/分节。

    python tools/make_fake_report.py --doc-id <seed 的 accident_file>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.common import DATA, ensure_dir, iter_csv  # noqa: E402

SAMPLE = """NO 12/2018
Marine Accident Investigation Branch
Page 1 of 12

SYNOPSIS
At about 0246 on 1 March 2018, the bulk carrier {ship} dragged her anchor in the
River Humber and collided with the moored vessel {ship2}. No one was injured,
but both vessels suffered structural damage. The investigation found that
insufficient anchor cable had been deployed for the tidal range.

1. FACTUAL INFORMATION
1.1 Narrative
The vessel arrived at the anchorage at 2100. The wind was easterly force 8 to 9
with moderate seas, and the visibility was good. The pilot remained on board.
The anchor was let go with 4 shackles in water depth of 14 m.

Figure 1: Track of the vessel

2. ANALYSIS
2.1 The dragging of the anchor
The tidal stream was north-westerly at 2.7 kts. The master had not allowed for
the predicted spring tide, and the anchor cable was too short. The crew did not
monitor the anchor position using the available GPS alarms.

2.2 Lookout and communication
The bridge team did not maintain a proper lookout, and no one warned the
moored vessel before the contact occurred.

3. CONCLUSIONS
3.1 The collision occurred because {ship} dragged her anchor.
3.2 Contributing factors were the short anchor cable and the lack of monitoring.

4. RECOMMENDATIONS
4.1 The company should review its anchoring procedures.

This report is not intended to establish liability.

References
1. IMO Resolution A.601(15)
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc-id", default="")
    ap.add_argument("--out", default=str(DATA / "pdf" / "uk"))
    args = ap.parse_args()

    rows = list(iter_csv(DATA / "seed" / "seed.csv"))
    row = None
    for r in rows:
        if r["accident_file"] == args.doc_id:
            row = r
            break
    if row is None:
        row = next(r for r in rows if r["country"] == "UK")
    vessels = [v for v in row["vessels"].split("|") if v] or ["Vessel A", "Vessel B"]
    text = SAMPLE.format(ship=vessels[0], ship2=vessels[1] if len(vessels) > 1 else "Vessel B")
    out_dir = ensure_dir(Path(args.out))
    p = out_dir / f"{row['accident_file']}.txt"
    p.write_text(text, encoding="utf-8")
    print(f"{p}  ({len(text)} 字符)  对应 {row['accident_no']}")


if __name__ == "__main__":
    main()

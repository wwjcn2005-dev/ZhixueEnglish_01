# -*- coding: utf-8 -*-
"""P1-09-E: does a deterministic same-slot substitution filter shrink the candidate pool
enough to be usable, and does it still cover the real alternatives? (No AI calls.)

Writes slot_filter_probe.json
"""

import collections
import json
import os
import re
import sqlite3

BASE = r"D:\ZhixueEnglish"
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    cp = sqlite3.connect("file:" + CP.replace("\\", "/") + "?mode=ro", uri=True)
    cp.row_factory = sqlite3.Row
    blocks = [(r["block_id"], r["text_raw"] or "") for r in
              cp.execute("SELECT block_id, text_raw FROM content_block")]

    def slot(pattern, scope_blocks=None):
        rx = re.compile(pattern, re.I)
        hits = collections.Counter()
        for bid, t in (scope_blocks or blocks):
            for m in rx.finditer(t):
                hits[m.group(1).lower()] += 1
        return hits

    patterns = {
        "with his X": r"with his ([a-z]+)",
        "a X on the blackboard": r"a ([a-z]+) on the blackboard",
        "X on the blackboard": r"([a-z]+) on the blackboard",
        "X with his friends": r"([a-z]+) with his friends",
        "his X": r"his ([a-z]+)",
        "a X kind of music": r"a ([a-z]+) kind of music",
        "play the X": r"play(?:s|ed)? the ([a-z]+)",
    }
    out = {"stage": "P1-09-E", "ai_calls": 0, "slot_patterns": {},
           "note": "同槽位代入：把题目空位前后的字面片段当模板，在全教材正文里找同位置出现过的词。"
                   "完全确定性，不需要新依赖。"}
    for name, pat in patterns.items():
        hits = slot(pat)
        out["slot_patterns"][name] = {"candidate_count": len(hits),
                                      "top": hits.most_common(15)}

    # targeted question: do the two designed alternatives appear in a same-slot occurrence?
    checks = {
        "FIX-C1_students": ("with his ([a-z]+)", "students", "with his ___"),
        "FIX-C1_grandpa": ("with his ([a-z]+)", "grandpa", "with his ___"),
        "FIX-C2_word": (r"a ([a-z]+) on the blackboard", "word", "a ___ on the blackboard"),
        "FIX-C2_name": (r"a ([a-z]+) on the blackboard", "name", "a ___ on the blackboard"),
    }
    out["targeted_checks"] = {}
    for k, (pat, target, desc) in checks.items():
        hits = slot(pat)
        out["targeted_checks"][k] = {
            "slot": desc, "target": target, "in_same_slot_pool": target in hits,
            "occurrences": hits.get(target, 0),
            "pool_size": len(hits),
            "pool_top": hits.most_common(12)}

    with open(os.path.join(HERE, "slot_filter_probe.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    for name, v in out["slot_patterns"].items():
        print("%-26s candidates=%-4d %s" % (name, v["candidate_count"], v["top"][:8]))
    print()
    for k, v in out["targeted_checks"].items():
        print("%-18s slot=%-26s target=%-9s in_pool=%-5s occurrences=%d pool=%d"
              % (k, v["slot"], v["target"], v["in_same_slot_pool"], v["occurrences"],
                 v["pool_size"]))
    cp.close()


if __name__ == "__main__":
    main()

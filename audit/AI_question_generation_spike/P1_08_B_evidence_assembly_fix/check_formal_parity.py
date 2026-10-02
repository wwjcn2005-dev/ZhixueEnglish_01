"""只读：验证修正模块与正式层 web/content.py 的正文归属规则一致。"""
import os
import sqlite3
import sys

BASE = r"D:\ZhixueEnglish"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(BASE, "web"))
import evidence_assembly as EA  # noqa: E402

CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")

import content as C  # noqa: E402  （正式层模块，只读复用）

c = sqlite3.connect("file:" + CP + "?mode=ro", uri=True)
c.row_factory = sqlite3.Row

units = list(C.list_units(CP))
print("正式层 list_units:", [(u["unit_code"], u["slug"]) for u in units])
print()

ok_range = ok_subset = ok_strict = True
uid_of = {r["unit_code"]: r["unit_id"] for r in c.execute("select unit_id, unit_code from unit")}
for u in units:
    if u["unit_code"] == "Appendix":
        continue
    res = C.unit_text_sections(u["slug"], CP)
    if not res:
        print("  %-10s 正式层无正文" % u["unit_code"])
        continue
    formal = {}
    for sec in res["sections"]:
        formal[sec["section_key"]] = {b["block_id"] for b in sec["blocks"]}
    mine, mine_strict = {}, {}
    for r in c.execute("select section_id, section_key from section where unit_id=?",
                       (uid_of[u["unit_code"]],)):
        mine[r["section_key"]] = {b["block_id"] for b in EA.blocks_of_section(c, r["section_id"])}
        mine_strict[r["section_key"]] = {
            b["block_id"] for b in EA.blocks_of_section(c, r["section_id"], strict_text_rule=True)}
    for k in sorted(set(formal) | set(mine)):
        f, m, ms = formal.get(k, set()), mine.get(k, set()), mine_strict.get(k, set())
        if f - m:
            ok_subset = False
            print("  [LOST] %-8s %-22s 正式层有而修正缺失：%s"
                  % (u["unit_code"], k, sorted(f - m)[:3]))
        if f != ms:
            ok_strict = False
            print("  [STRICT-DIFF] %-8s %-22s 正式=%d 严格模式=%d 仅正式=%s 仅严格=%s"
                  % (u["unit_code"], k, len(f), len(ms), sorted(f - ms)[:2], sorted(ms - f)[:2]))
    print("  %-10s 比对完成：%d 个 Section" % (u["unit_code"], len(set(formal) | set(mine))))
c.close()
print()
print("归属规则一致性（正式层 blocks ⊆ 修正模块默认输出）:", ok_subset)
print("严格模式与正式层逐 block 一致:", ok_strict)

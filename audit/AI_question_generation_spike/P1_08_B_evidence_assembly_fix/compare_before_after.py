"""P1-08-B · 修复前后对照（只读）。输出 before_after_comparison.json。"""
import json
import os
import sqlite3
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import evidence_assembly as EA  # noqa: E402

BASE = r"D:\ZhixueEnglish"
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
RUNS = os.path.join(BASE, "audit", "AI_question_generation_spike",
                    "P1_05_real_validation", "runs")
LESSON_UNITS = ("FLTRP-EN-7A-2022CUR:STARTER", "FLTRP-EN-7A-2022CUR:U1",
                "FLTRP-EN-7A-2022CUR:U2", "FLTRP-EN-7A-2022CUR:U3",
                "FLTRP-EN-7A-2022CUR:U4", "FLTRP-EN-7A-2022CUR:U5",
                "FLTRP-EN-7A-2022CUR:U6")

c = sqlite3.connect("file:" + CP + "?mode=ro", uri=True)
c.row_factory = sqlite3.Row
ranges = EA.section_page_ranges(c)
old = EA.blocks_by_activity_only(c)

per_section = []
tot_old = tot_new = tot_added = 0
empty_filtered = 0
for sid in sorted(ranges):
    new = EA.blocks_of_section(c, sid)
    new_ids = {b["block_id"] for b in new}
    old_list = old.get(sid, [])
    old_ids = {b["block_id"] for b in old_list}
    added = new_ids - old_ids
    removed_nonempty = [b["block_id"] for b in old_list
                        if b["block_id"] not in new_ids
                        and (b.get("text_raw") or "").strip() != ""]
    empty_filtered += sum(1 for b in old_list if (b.get("text_raw") or "").strip() == ""
                          and b["block_id"] not in new_ids)
    is_lesson = sid.rsplit(":", 1)[0] in LESSON_UNITS
    per_section.append({
        "section_id": sid, "is_lesson_unit": is_lesson,
        "page_range": list(ranges[sid]),
        "pages_without_activity": sorted(set(range(ranges[sid][0], ranges[sid][1] + 1))
                                         - {a["pdf_page"] for a in EA.activities_of_section(c, sid)
                                            if a["pdf_page"]}),
        "blocks_old": len(old_ids), "blocks_new": len(new_ids),
        "blocks_added": len(added), "removed_nonempty": removed_nonempty})
    if is_lesson:
        tot_old += len(old_ids)
        tot_new += len(new_ids)
        tot_added += len(added)

# Case 1 前后
u1ui = "FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS"
ev = EA.build_section_evidence(c, u1ui)
case1 = {
    "section_id": u1ui,
    "page_range": list(ranges[u1ui]),
    "pages_before": sorted({a["pdf_page"] for a in EA.activities_of_section(c, u1ui)
                            if a["pdf_page"]}),
    "pages_after": EA.pages_of_section(c, u1ui),
    "blocks_before": len({b["block_id"] for b in old.get(u1ui, [])}),
    "blocks_after": len({b["block_id"] for b in ev["blocks"]}),
    "p22_blocks_before": 0,
    "p22_blocks_after": len([b for b in ev["blocks"] if b["page_id"].endswith(":P22")]),
    "p22_block_ids_after": [b["block_id"] for b in ev["blocks"] if b["page_id"].endswith(":P22")],
    "p22_activities": [a for a in EA.activities_of_section(c, u1ui) if a["pdf_page"] == 22],
    "duplicate_blocks": ev["stats"]["blocks"] - ev["stats"]["blocks_unique"],
    "pages_without_activity": ev["stats"]["pages_without_activity"],
}

# P1-06 fixture context：修复后新增了哪些 block
ctx_files = {"S1": "01_Unit2_UNDERSTANDING_IDEAS_context.json",
             "S2": "03_Unit1_UNDERSTANDING_IDEAS_context.json",
             "S3": "04_Unit5_UNDERSTANDING_IDEAS_context.json",
             "S4": "05_Starter_GET_READY_context.json"}
fixture = {}
for tag, f in ctx_files.items():
    with open(os.path.join(RUNS, f), encoding="utf-8") as fh:
        ctx = json.load(fh)
    sid = ctx["textbook_position"]["section_id"]
    new_ids = {b["block_id"] for b in EA.blocks_of_section(c, sid)}
    old_ids = {b["block_id"] for b in ctx["textbook_blocks"]}
    added = sorted(new_ids - old_ids)
    fixture[tag] = {
        "section_id": sid,
        "context_blocks_before": len(old_ids),
        "blocks_after": len(new_ids),
        "blocks_added_by_fix": len(added),
        "added_pages": sorted({b.split(":")[1] for b in added}),
        "added_sample": added[:5],
        "fixture_blocks_all_present": old_ids <= new_ids,
    }
c.close()

doc = {
    "stage": "P1-08-B", "mode": "before_after_comparison", "ai_calls": 0,
    "old_rule": "page -> section 仅来自 activity",
    "new_rule": "Section 页码范围（unit 内 pdf_page_start 排序推出）+ activity 页，按 block_id 去重",
    "lesson_units_totals": {"blocks_old": tot_old, "blocks_new": tot_new, "blocks_added": tot_added},
    "empty_text_blocks_filtered_by_new_rule": empty_filtered,
    "per_section": per_section,
    "case1_unit1_p17_pdf22": case1,
    "p1_06_fixture_impact": fixture,
}
with open(os.path.join(HERE, "before_after_comparison.json"), "w", encoding="utf-8") as fh:
    json.dump(doc, fh, ensure_ascii=False, indent=1)

print("课内 Section（Starter+U1-U6）block 总数：旧 %d → 新 %d（补回 %d）"
      % (tot_old, tot_new, tot_added))
print("新规则过滤掉的纯空白 block:", empty_filtered)
print()
print("CASE1 U1 UI：页 %s -> %s | block %d -> %d | P22 block 0 -> %d | 重复 %d"
      % (case1["pages_before"], case1["pages_after"], case1["blocks_before"],
         case1["blocks_after"], case1["p22_blocks_after"], case1["duplicate_blocks"]))
print()
print("P1-06 fixture 影响：")
for tag, v in fixture.items():
    print("  %s section=%-46s %3d -> %3d (+%d) 新增页=%s"
          % (tag, v["section_id"].split(":", 1)[1], v["context_blocks_before"],
             v["blocks_after"], v["blocks_added_by_fix"], v["added_pages"]))

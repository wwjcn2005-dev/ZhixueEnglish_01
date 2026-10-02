"""P1-08-B 只读侦察：量化 Activity 反推页面正文造成的正文丢失。不修改任何文件。

(a) 页面属于某 Section 页码范围但无 Activity，旧逻辑丢正文（真缺陷）；
(b) 页面不属于任何 Section 范围（封面/前言/附录/单元扉页），本就不进 Section 上下文。
输出 recon_facts.json + 控制台摘要。
"""
import json
import os
import sqlite3
from collections import Counter, defaultdict

BASE = r"D:\ZhixueEnglish"
HERE = os.path.dirname(os.path.abspath(__file__))
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
RUNS = os.path.join(BASE, "audit", "AI_question_generation_spike",
                    "P1_05_real_validation", "runs")

c = sqlite3.connect("file:" + CP + "?mode=ro", uri=True)
c.row_factory = sqlite3.Row

page2sec_old = defaultdict(set)
for r in c.execute("select distinct pdf_page, section_id from activity"):
    page2sec_old[r["pdf_page"]].add(r["section_id"])

units = {r["unit_id"]: dict(r) for r in c.execute("select * from unit")}
secs = [dict(r) for r in c.execute("select * from section order by unit_id, pdf_page_start")]
by_unit = defaultdict(list)
for s in secs:
    by_unit[s["unit_id"]].append(s)
sec_range = {}
for uid, rows in by_unit.items():
    rows.sort(key=lambda x: x["pdf_page_start"])
    u_end = units[uid]["pdf_page_end"]
    for i, s in enumerate(rows):
        end = (rows[i + 1]["pdf_page_start"] - 1) if i + 1 < len(rows) else u_end
        sec_range[s["section_id"]] = (s["pdf_page_start"], end)

pdf2sec_new = defaultdict(set)
for sid, ab in sec_range.items():
    for p in range(ab[0], ab[1] + 1):
        pdf2sec_new[p].add(sid)

pages = {r["page_id"]: dict(r) for r in c.execute("select * from page")}
blocks = defaultdict(list)
for r in c.execute("select block_id, page_id, block_kind, reading_order, text_raw from content_block"):
    blocks[r["page_id"]].append(dict(r))
SKIP_KIND = {"footer_text"}

sec_diff = []
for s in secs:
    sid = s["section_id"]
    old = {p for p, ss in page2sec_old.items() if sid in ss}
    new = set(range(sec_range[sid][0], sec_range[sid][1] + 1))
    if old != new:
        sec_diff.append({"section_id": sid, "old_pages": sorted(old),
                         "new_pages": sorted(new), "missing_pages": sorted(new - old)})

defect_lost = []
outside = []
for pid, bs in blocks.items():
    pg = pages[pid]["pdf_page"]
    for b in bs:
        if b["block_kind"] in SKIP_KIND:
            continue
        if pg in pdf2sec_new:
            if not page2sec_old.get(pg):
                defect_lost.append({"page_id": pid, "pdf_page": pg,
                                    "textbook_page": pages[pid]["textbook_page"],
                                    "block_id": b["block_id"], "kind": b["block_kind"],
                                    "text": (b["text_raw"] or "").replace("\n", " ")[:120],
                                    "sections_new": sorted(pdf2sec_new[pg])})
        else:
            outside.append({"page_id": pid, "pdf_page": pg})

p22 = pages["FLTRP-EN-7A-2022CUR:P22"]
act22 = [dict(r) for r in c.execute("select activity_id, section_id, activity_number, textbook_page from activity where pdf_page=22")]
b22 = [b for b in blocks["FLTRP-EN-7A-2022CUR:P22"] if b["block_kind"] not in SKIP_KIND]
case1 = {
    "page_id": p22["page_id"], "pdf_page": p22["pdf_page"],
    "textbook_page": p22["textbook_page"], "page_role": p22["page_role"],
    "text_chars": p22["text_chars"], "review_status": p22["review_status"],
    "activity_count": len(act22), "activities": act22,
    "content_block_count": len(b22),
    "blocks": [{"block_id": b["block_id"], "kind": b["block_kind"],
                "text": (b["text_raw"] or "").replace("\n", " ")[:110]} for b in b22],
    "old_attribution": sorted(page2sec_old.get(22, [])),
    "new_attribution": sorted(pdf2sec_new.get(22, [])),
}

ctx_files = {"S1": "01_Unit2_UNDERSTANDING_IDEAS_context.json",
             "S2": "03_Unit1_UNDERSTANDING_IDEAS_context.json",
             "S3": "04_Unit5_UNDERSTANDING_IDEAS_context.json",
             "S4": "05_Starter_GET_READY_context.json"}
fixture_cov = {}
for tag, f in ctx_files.items():
    j = json.load(open(os.path.join(RUNS, f), encoding="utf-8"))
    pgs = sorted({b["block_id"].split(":")[1] for b in j["textbook_blocks"]})
    fixture_cov[tag] = {"context_blocks": len(j["textbook_blocks"]), "pages_in_context": pgs}

c.close()
facts = {
    "stage": "P1-08-B", "mode": "read_only_recon", "ai_calls": 0,
    "old_rule": "page -> section 仅来自 activity（page2sec 由 select distinct pdf_page, section_id from activity 构造）",
    "new_rule": "Section 页码范围 = 该 unit 内按 pdf_page_start 排序后的 [start, next_start-1]，末节到 unit 末尾",
    "sections_total": len(secs),
    "sections_with_page_diff": len(sec_diff),
    "section_page_diffs": sec_diff,
    "defect_lost_blocks": len(defect_lost),
    "defect_lost_pages": sorted({d["pdf_page"] for d in defect_lost}),
    "defect_lost_by_section": dict(Counter(s for d in defect_lost for s in d["sections_new"])),
    "defect_lost_detail": defect_lost,
    "outside_any_section_blocks": len(outside),
    "case1_unit1_p17_pdf22": case1,
    "p1_06_context_coverage": fixture_cov,
}
with open(os.path.join(HERE, "recon_facts.json"), "w", encoding="utf-8") as fh:
    json.dump(facts, fh, ensure_ascii=False, indent=1)

print("Section 总数:", len(secs), "| 页集合有差异:", len(sec_diff))
print("真缺陷被丢弃的 block 数:", len(defect_lost), "| 涉及页:", facts["defect_lost_pages"])
print("不属于任何 Section 范围的 block 数（非缺陷）:", len(outside))
print()
print("CASE1  Unit 1 教材第17页 / PDF22")
keys = ["page_id", "pdf_page", "textbook_page", "page_role", "text_chars",
        "review_status", "activity_count", "content_block_count",
        "old_attribution", "new_attribution"]
for k in keys:
    print("  %-20s %s" % (k, case1[k]))
print("  blocks:")
for b in case1["blocks"]:
    print("    %-34s %-14s | %s" % (b["block_id"].split(":")[-1], b["kind"], b["text"][:70]))
print()
print("P1-06 fixture context 覆盖（旧逻辑产物）")
for tag, v in fixture_cov.items():
    print("  %s blocks=%-3d pages=%s" % (tag, v["context_blocks"], v["pages_in_context"]))

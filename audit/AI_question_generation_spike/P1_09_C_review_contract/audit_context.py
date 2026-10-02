# -*- coding: utf-8 -*-
"""P1-09-C read-only mechanism audit: what textbook information a question can reach today.

No AI call. No write to any database. Uses the P1-08-B corrected evidence-assembly module
to rebuild full Section context from contentpack (read-only).

Writes: offline_context_probe.json
"""

import json
import os
import sqlite3
import sys

BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
P1_08_B = os.path.join(SPIKE, "P1_08_B_evidence_assembly_fix")
sys.path.insert(0, P1_08_B)
import evidence_assembly as EA  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CHARS_PER_TOKEN = 3.074   # measured in P1-09-A from 4 real P1-06 requests

SAMPLES = ["AIQ:BD59C5958D45", "AIQ:04CC9B1CF690", "AIQ:6ECD02B9D381", "AIQ:879007FA4FC7",
           "AIQ:7EAC0ED29A0A", "AIQ:1B3AF72923C4", "AIQ:1BA260727793", "AIQ:120FFEECA78F",
           "AIQ:75AAEBFE06DF", "AIQ:B6463523F9E5"]

PROBE_TERMS = ["art festival", "festival", "rain", "Canada", "colour", "colour is it",
               "ready", "hobby", "erhu"]


def ro(path):
    con = sqlite3.connect("file:" + path.replace("\\", "/") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def main():
    lib, cp = ro(LIB), ro(CP)
    ranges = EA.section_page_ranges(cp)
    section_cache = {}
    rows = []

    for qid in SAMPLES:
        q = dict(lib.execute(
            "SELECT question_id, question_type, question_text, options_json, correct_answer,"
            " section_id, activity_id, page, unit_id FROM ai_question WHERE question_id=?",
            (qid,)).fetchone())
        ev = [dict(e) for e in lib.execute(
            "SELECT ordinal, evidence_block_id, evidence_quote, is_primary FROM question_evidence"
            " WHERE question_id=? ORDER BY ordinal", (qid,))]
        lo = [dict(e) for e in lib.execute(
            "SELECT item_id, is_primary FROM question_learning_object WHERE question_id=?"
            " ORDER BY is_primary DESC", (qid,))]

        sid = q["section_id"]
        if sid not in section_cache:
            pack = EA.build_section_evidence(cp, sid)
            section_cache[sid] = pack
        pack = section_cache[sid]
        blocks = pack["blocks"]
        acts = pack["activities"]
        act_block_ids = {}
        for r in cp.execute(
                "SELECT activity_id, block_id FROM activity_content WHERE activity_id IN"
                " (SELECT activity_id FROM activity WHERE section_id=?)", (sid,)):
            act_block_ids.setdefault(r["activity_id"], set()).add(r["block_id"])

        # locate the evidence blocks inside the section, then take the activity-sized neighbourhood
        idx = {b["block_id"]: i for i, b in enumerate(blocks)}
        primary_ids = [e["evidence_block_id"] for e in ev]
        positions = [idx[b] for b in primary_ids if b in idx]
        window = []
        if positions:
            lo_i, hi_i = max(0, min(positions) - 2), min(len(blocks), max(positions) + 3)
            window = [{"block_id": b["block_id"], "pdf_page": b["pdf_page"],
                       "textbook_page": b["textbook_page"], "text": b["text"][:300]}
                      for b in blocks[lo_i:hi_i]]

        # which blocks mention the probe terms (this is how we find missing context)
        term_hits = {}
        for t in PROBE_TERMS:
            hit = [b["block_id"] for b in blocks if t.lower() in (b["text"] or "").lower()]
            if hit:
                term_hits[t] = hit

        # minimal vs extended size (program-side estimate, characters)
        minimal = json.dumps({
            "question": q["question_text"], "options": json.loads(q["options_json"] or "null"),
            "answer": q["correct_answer"],
            "evidence_quote": ev[0]["evidence_quote"] if ev else "",
        }, ensure_ascii=False)
        # L2: evidence-block level -> full text of the evidence block(s) + the blocks of the
        # question's own activity + immediate neighbours
        ev_full = [{"block_id": b["block_id"], "textbook_page": b["textbook_page"], "text": b["text"]}
                   for b in blocks if b["block_id"] in set(primary_ids)]
        act_blocks = [b for b in blocks if b["block_id"] in act_block_ids.get(q["activity_id"], set())]
        neighbour = []
        for p in positions:
            for j in (p - 1, p + 1):
                if 0 <= j < len(blocks):
                    neighbour.append(blocks[j])
        seen_ids, l2_blocks = set(), []
        for b in ev_full + [{"block_id": x["block_id"], "textbook_page": x["textbook_page"],
                            "text": x["text"]} for x in act_blocks + neighbour]:
            if b["block_id"] in seen_ids:
                continue
            seen_ids.add(b["block_id"])
            l2_blocks.append(b)
        l2_blocks.sort(key=lambda b: b["block_id"])
        standard = json.dumps({
            "question": q["question_text"], "options": json.loads(q["options_json"] or "null"),
            "answer": q["correct_answer"],
            "activity_instruction": next((a["instruction"] for a in acts
                                          if a["activity_id"] == q["activity_id"]), None),
            "blocks": l2_blocks,
        }, ensure_ascii=False)
        extended = json.dumps({
            "question": q["question_text"], "options": json.loads(q["options_json"] or "null"),
            "answer": q["correct_answer"],
            "section_blocks": [{"block_id": b["block_id"], "textbook_page": b["textbook_page"],
                                "text": b["text"]} for b in blocks],
        }, ensure_ascii=False)

        rows.append({
            "question_id": qid,
            "question_type": q["question_type"],
            "section_id": sid,
            "activity_id": q["activity_id"],
            "textbook_page": q["page"],
            "answer": q["correct_answer"],
            "question_library_side": {
                "question_rows": 1,
                "evidence_rows": len(ev),
                "evidence_block_ids": primary_ids,
                "evidence_quotes": [e["evidence_quote"] for e in ev],
                "learning_object_rows": len(lo),
                "learning_object_ids": [x["item_id"] for x in lo],
            },
            "contentpack_side": {
                "section_page_range_pdf": list(ranges[sid]),
                "section_pages_pdf": pack["pages"],
                "section_block_count": pack["stats"]["blocks"],
                "section_activity_count": pack["stats"]["activities"],
                "section_activity_numbers": [a["activity_number"] for a in acts],
                "evidence_block_pages_without_activity": pack["stats"]["pages_without_activity"],
            },
            "evidence_block_neighbourhood": window,
            "term_hits_in_section": term_hits,
            "context_size_chars": {"minimal_single_quote": len(minimal),
                                   "evidence_block_level": len(standard),
                                   "extended_full_section": len(extended)},
            "context_size_tokens_est": {
                "minimal_single_quote": round(len(minimal) / CHARS_PER_TOKEN),
                "evidence_block_level": round(len(standard) / CHARS_PER_TOKEN),
                "extended_full_section": round(len(extended) / CHARS_PER_TOKEN)},
            "evidence_quote_is_substring_of_block": all(
                (e["evidence_quote"] or "") in
                next((b["text"] for b in blocks if b["block_id"] == e["evidence_block_id"]), "")
                for e in ev),
            "full_evidence_block_texts": [
                {"block_id": b["block_id"], "textbook_page": b["textbook_page"],
                 "chars": len(b["text"]), "text": b["text"]}
                for b in blocks if b["block_id"] in set(primary_ids)],
        })

    out = {
        "stage": "P1-09-C", "ai_calls": 0, "chars_per_token": CHARS_PER_TOKEN,
        "note": "Section 上下文由 P1-08-B 修正后的 evidence_assembly 模块从 contentpack 只读重建；"
                "未修改任何正式数据。",
        "questions": rows,
    }
    with open(os.path.join(HERE, "offline_context_probe.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    for r in rows:
        cs = r["context_size_chars"]
        print("%-20s %-14s ev=%s blocks=%s  L1=%stok L2=%stok L3=%stok  quote_substr=%s"
              % (r["question_id"], r["question_type"],
                 r["question_library_side"]["evidence_rows"],
                 r["contentpack_side"]["section_block_count"],
                 r["context_size_tokens_est"]["minimal_single_quote"],
                 r["context_size_tokens_est"]["evidence_block_level"],
                 r["context_size_tokens_est"]["extended_full_section"],
                 r["evidence_quote_is_substring_of_block"]))
    print()
    print("== term hits for AIQ:6ECD02B9D381 context ==")
    for r in rows:
        if r["question_id"] == "AIQ:6ECD02B9D381":
            print(json.dumps(r["term_hits_in_section"], ensure_ascii=False, indent=1))
            print("neighbourhood:")
            for b in r["evidence_block_neighbourhood"]:
                print("   ", b["block_id"], "p", b["textbook_page"], "|", b["text"][:110])
    lib.close()
    cp.close()


if __name__ == "__main__":
    main()

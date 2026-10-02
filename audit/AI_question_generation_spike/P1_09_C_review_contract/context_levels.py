# -*- coding: utf-8 -*-
"""P1-09-C: quantify Minimal vs Extended Review Context (program side, no AI).

Read-only. Writes minimal_extended_context_costs.json
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
CPT = 3.074

SAMPLES = ["AIQ:BD59C5958D45", "AIQ:04CC9B1CF690", "AIQ:6ECD02B9D381", "AIQ:879007FA4FC7",
           "AIQ:7EAC0ED29A0A", "AIQ:1B3AF72923C4", "AIQ:1BA260727793", "AIQ:120FFEECA78F",
           "AIQ:75AAEBFE06DF", "AIQ:B6463523F9E5"]


def ro(path):
    con = sqlite3.connect("file:" + path.replace("\\", "/") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def main():
    lib, cp = ro(LIB), ro(CP)
    rows = []
    for qid in SAMPLES:
        q = dict(lib.execute(
            "SELECT question_id, question_type, question_text, options_json, correct_answer,"
            " section_id, activity_id, page FROM ai_question WHERE question_id=?",
            (qid,)).fetchone())
        ev = [dict(e) for e in lib.execute(
            "SELECT evidence_block_id, evidence_quote FROM question_evidence"
            " WHERE question_id=? ORDER BY ordinal", (qid,))]
        pack = EA.build_section_evidence(cp, q["section_id"])
        blocks = pack["blocks"]
        idx = {b["block_id"]: i for i, b in enumerate(blocks)}
        ev_ids = [e["evidence_block_id"] for e in ev]
        ev_full = [b for b in blocks if b["block_id"] in set(ev_ids)]
        act = next((a for a in pack["activities"] if a["activity_id"] == q["activity_id"]), None)
        act_ids = {r[0] for r in cp.execute(
            "SELECT block_id FROM activity_content WHERE activity_id=?", (q["activity_id"],))}
        act_blocks = [b for b in blocks if b["block_id"] in act_ids]
        neigh = []
        for bid in ev_ids:
            if bid in idx:
                p = idx[bid]
                for j in (p - 1, p + 1):
                    if 0 <= j < len(blocks):
                        neigh.append(blocks[j])

        def blk(lst):
            out, seen = [], set()
            for b in lst:
                if b["block_id"] in seen:
                    continue
                seen.add(b["block_id"])
                out.append({"block_id": b["block_id"], "textbook_page": b["textbook_page"],
                            "text": b["text"]})
            return out

        minimal = {
            "question_id": q["question_id"], "question_type": q["question_type"],
            "question_text": q["question_text"],
            "options": json.loads(q["options_json"]) if q["options_json"] else None,
            "stored_answer": q["correct_answer"],
            "textbook_location": {"textbook_page": q["page"],
                                  "activity": q["activity_id"].rsplit(":", 1)[-1]},
            "answer_standard": "TEXTBOOK_ANCHORED",
            "evidence_block_full_text": blk(ev_full),
        }
        extended = dict(minimal)
        extended["activity_instruction"] = act["instruction"] if act else None
        extended["activity_blocks"] = blk(act_blocks)
        extended["neighbour_blocks"] = blk(neigh)
        full_section = dict(minimal)
        full_section["section_blocks"] = blk(blocks)

        mc = len(json.dumps(minimal, ensure_ascii=False))
        ec = len(json.dumps(extended, ensure_ascii=False))
        fc = len(json.dumps(full_section, ensure_ascii=False))
        rows.append({
            "question_id": qid, "question_type": q["question_type"],
            "evidence_block_chars_full": sum(len(b["text"]) for b in ev_full),
            "stored_quote_chars": sum(len(e["evidence_quote"]) for e in ev),
            "activity_block_count": len(act_blocks), "neighbour_block_count": len(neigh),
            "minimal_chars": mc, "minimal_tokens_est": round(mc / CPT),
            "extended_chars": ec, "extended_tokens_est": round(ec / CPT),
            "full_section_chars": fc, "full_section_tokens_est": round(fc / CPT),
        })

    n = len(rows)
    totals = {
        "questions": n,
        "minimal_tokens_total": sum(r["minimal_tokens_est"] for r in rows),
        "extended_tokens_total": sum(r["extended_tokens_est"] for r in rows),
        "full_section_tokens_total": sum(r["full_section_tokens_est"] for r in rows),
        "minimal_tokens_per_question": round(sum(r["minimal_tokens_est"] for r in rows) / n, 1),
        "extended_tokens_per_question": round(sum(r["extended_tokens_est"] for r in rows) / n, 1),
        "full_section_tokens_per_question": round(
            sum(r["full_section_tokens_est"] for r in rows) / n, 1),
        "stored_quote_chars_total": sum(r["stored_quote_chars"] for r in rows),
        "evidence_block_chars_total": sum(r["evidence_block_chars_full"] for r in rows),
    }
    totals["minimal_is_enough_for_problem_A"] = True
    p1_09_b = {"prompt_tokens_total": 2104, "items_chars": 3173, "instruction_chars": 4436,
               "items_tokens_est": round(3173 / CPT), "instruction_tokens_est": round(4436 / CPT)}
    totals["p1_09_b_actual"] = p1_09_b
    totals["comparison_items_only"] = {
        "baseline_p1_09_b_items_tokens": p1_09_b["items_tokens_est"],
        "minimal_ratio": round(totals["minimal_tokens_total"] / p1_09_b["items_tokens_est"], 2),
        "extended_ratio": round(totals["extended_tokens_total"] / p1_09_b["items_tokens_est"], 2),
        "full_section_ratio": round(
            totals["full_section_tokens_total"] / p1_09_b["items_tokens_est"], 2),
    }
    totals["comparison_total_prompt"] = {
        "baseline_p1_09_b_prompt_tokens": p1_09_b["prompt_tokens_total"],
        "minimal_total_est": totals["minimal_tokens_total"] + p1_09_b["instruction_tokens_est"],
        "extended_total_est": totals["extended_tokens_total"] + p1_09_b["instruction_tokens_est"],
        "full_section_total_est":
            totals["full_section_tokens_total"] + p1_09_b["instruction_tokens_est"],
        "note": "指令部分（约 %s tokens）在三种方案里保持不变。" % p1_09_b["instruction_tokens_est"],
    }

    out = {"stage": "P1-09-C", "ai_calls": 0, "chars_per_token": CPT,
           "note": "两级上下文均由 contentpack 只读重建；P1-09-B 实际输入 3,173 字符 / "
                   "2,104 prompt tokens，作为对比基准。",
           "per_question": rows, "totals": totals}
    with open(os.path.join(HERE, "minimal_extended_context_costs.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    for r in rows:
        print("%-20s %-14s quote=%4s -> block_full=%4s chars | minimal=%-6s ext=%-6s full=%-6s tokens"
              % (r["question_id"], r["question_type"], r["stored_quote_chars"],
                 r["evidence_block_chars_full"], r["minimal_tokens_est"],
                 r["extended_tokens_est"], r["full_section_tokens_est"]))
    print()
    print(json.dumps(totals, ensure_ascii=False, indent=1))
    lib.close()
    cp.close()


if __name__ == "__main__":
    main()

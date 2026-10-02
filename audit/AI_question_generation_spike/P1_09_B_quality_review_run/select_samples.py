# -*- coding: utf-8 -*-
"""P1-09-B: select real samples from question_library.db and build the blind AI input.

Read-only on question_library.db. Writes:
  sample_selection.json  -- experimenter side (ids, categories, ground-truth labels)
  input_snapshot.json    -- exactly what is sent to the review model (blind input)

The blind input contains ONLY: question_id, question_type, question_text, options,
answer, textbook evidence (page / activity / quote) and the grade-7 context.
It never contains the generation explanation, validator PASS/FAIL, known-issue labels,
the generation prompt, or any generation-time model reasoning.
"""

import hashlib
import json
import os
import sqlite3

BASE = r"D:\ZhixueEnglish"
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
HERE = os.path.dirname(os.path.abspath(__file__))

# question_id -> (coverage bucket, ground-truth label class, ground-truth note)
# label classes: KNOWN_NORMAL / RECORDED_RISK / CONFIRMED_PROBLEM
SAMPLES = [
    ("AIQ:BD59C5958D45", "A_known_normal", "KNOWN_NORMAL",
     "P1-08-C 人工审核通过并 ACTIVE；答案 band 在教材原句逐字命中，四个选项均为教材 BOLD 核心词"),
    ("AIQ:04CC9B1CF690", "A_known_normal", "KNOWN_NORMAL",
     "P1-09-A 明显合格样本；答案为教材 BOLD 核心词，题干为完整句"),
    ("AIQ:6ECD02B9D381", "A_known_normal", "KNOWN_NORMAL",
     "P1-09-A 阅读理解正常样本；difficulty=medium，answer_support=VERIFIABLE_REPHRASE"),
    ("AIQ:879007FA4FC7", "A_known_normal", "KNOWN_NORMAL",
     "P1-09-A 阅读理解正常样本；答案为教材原句中的地点短语"),
    ("AIQ:7EAC0ED29A0A", "A_known_normal", "KNOWN_NORMAL",
     "P1-09-A judge 样本（True）；教材原句直接支持"),
    ("AIQ:1B3AF72923C4", "B_low_value_mechanical", "CONFIRMED_PROBLEM",
     "P1-08-C 已人工驳回（reason_code=LOW_VALUE）；审核记录同时记录题干单独看不唯一（happy/fine 等）"),
    ("AIQ:1BA260727793", "B_low_value_mechanical", "RECORDED_RISK",
     "P1-09-A C2/C4：双空挖空的语篇标记词片段，mechanical_rewrite=True"),
    ("AIQ:120FFEECA78F", "C_answer_uniqueness_risk", "RECORDED_RISK",
     "P1-09-A C3：程序判 EXACT，但单看题干任意颜色都成立"),
    ("AIQ:75AAEBFE06DF", "D_distractor_risk", "RECORDED_RISK",
     "P1-09-A C5：干扰项 traditional/electric/weak 均为教材 BOLD 核心形容词且语法成立"),
    ("AIQ:B6463523F9E5", "D_distractor_risk", "RECORDED_RISK",
     "P1-09-A C5：干扰项 sugar/oxygen/food 在其他语境下对树木同样成立"),
]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main():
    con = sqlite3.connect("file:" + LIB.replace("\\", "/") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    selection, items, before = [], [], {}
    for qid, bucket, label, note in SAMPLES:
        r = cur.execute(
            "SELECT question_id, question_type, question_text, options_json, correct_option,"
            " correct_answer, page, activity_id, section_id, unit_id, difficulty"
            " FROM ai_question WHERE question_id=?", (qid,)).fetchone()
        if r is None:
            raise SystemExit("sample not found in library: " + qid)
        q = dict(r)
        options = json.loads(q["options_json"]) if q["options_json"] else None
        ev = [dict(e) for e in cur.execute(
            "SELECT evidence_block_id, evidence_quote FROM question_evidence"
            " WHERE question_id=? ORDER BY ordinal", (qid,))]
        if not ev:
            raise SystemExit("sample has no evidence: " + qid)

        # ---- experimenter-side record (never sent to the model)
        selection.append({
            "question_id": qid, "coverage_bucket": bucket,
            "ground_truth_label": label, "ground_truth_note": note,
            "question_type": q["question_type"], "lifecycle_status": None,
            "evidence_block_ids": [e["evidence_block_id"] for e in ev],
        })
        # ---- blind input (this is the ONLY thing the reviewer sees)
        items.append({
            "question_id": qid,
            "question_type": q["question_type"],
            "question_text": q["question_text"],
            "options": options,
            "answer": q["correct_answer"],
            "textbook_position": "教材第 %s 页 · Activity %s"
                                 % (q["page"], q["activity_id"].rsplit(":", 1)[-1]),
            "textbook_evidence": ev[0]["evidence_quote"],
        })
        before[qid] = {
            "question_text": q["question_text"], "options_json": q["options_json"],
            "correct_answer": q["correct_answer"], "correct_option": q["correct_option"],
            "lifecycle_status": cur.execute(
                "SELECT lifecycle_status FROM ai_question WHERE question_id=?",
                (qid,)).fetchone()[0],
            "active": cur.execute("SELECT active FROM ai_question WHERE question_id=?",
                                 (qid,)).fetchone()[0],
            "question_event_count": cur.execute(
                "SELECT COUNT(*) FROM question_event WHERE question_id=?", (qid,)).fetchone()[0],
        }

    # fill in lifecycle for the experimenter record
    for s in selection:
        s["lifecycle_status"] = before[s["question_id"]]["lifecycle_status"]

    con.close()

    blind = {
        "grade_context": "外研版初中英语 七年级上册（初一第一学期）",
        "review_version": "P1-09-B-v1",
        "items": items,
    }
    selection_doc = {
        "stage": "P1-09-B",
        "source": LIB,
        "source_sha256": sha256_file(LIB),
        "sample_count": len(SAMPLES),
        "coverage": {
            "A_known_normal": sum(1 for s in selection if s["coverage_bucket"] == "A_known_normal"),
            "B_low_value_mechanical": sum(1 for s in selection
                                          if s["coverage_bucket"] == "B_low_value_mechanical"),
            "C_answer_uniqueness_risk": sum(1 for s in selection
                                            if s["coverage_bucket"] == "C_answer_uniqueness_risk"),
            "D_distractor_risk": sum(1 for s in selection
                                     if s["coverage_bucket"] == "D_distractor_risk"),
            "question_types": sorted({s["question_type"] for s in selection}),
        },
        "label_class_counts": {
            "KNOWN_NORMAL": sum(1 for s in selection if s["ground_truth_label"] == "KNOWN_NORMAL"),
            "RECORDED_RISK": sum(1 for s in selection
                                 if s["ground_truth_label"] == "RECORDED_RISK"),
            "CONFIRMED_PROBLEM": sum(1 for s in selection
                                     if s["ground_truth_label"] == "CONFIRMED_PROBLEM"),
        },
        "note": "ground_truth_label 是实验人员依据 P1-08-C / P1-09-A 既有证据得出的对照标签，"
                "不是新的 AI 判断；这些标签只在 AI 返回之后用于对照，绝不进入 AI 输入。",
        "samples": selection,
        "before_state": before,
    }
    with open(os.path.join(HERE, "sample_selection.json"), "w", encoding="utf-8") as fh:
        json.dump(selection_doc, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, "input_snapshot.json"), "w", encoding="utf-8") as fh:
        json.dump(blind, fh, ensure_ascii=False, indent=2)

    print("samples:", len(SAMPLES))
    print("coverage:", json.dumps(selection_doc["coverage"], ensure_ascii=False))
    print("labels  :", json.dumps(selection_doc["label_class_counts"], ensure_ascii=False))
    print("blind input chars:", len(json.dumps(blind, ensure_ascii=False)))
    for it in items:
        print("  %-20s %-14s %s" % (it["question_id"], it["question_type"],
                                    (it["question_text"] or "")[:52]))


if __name__ == "__main__":
    main()

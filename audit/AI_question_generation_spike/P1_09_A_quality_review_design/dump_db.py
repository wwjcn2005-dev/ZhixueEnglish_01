# -*- coding: utf-8 -*-
"""P1-09-A exploratory read-only dump of question_library.db."""

import json
import sqlite3

DB = r"D:\ZhixueEnglish\structured\ai\question_library.db"


def main():
    con = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    print("== lifecycle ==")
    for r in cur.execute(
            "SELECT lifecycle_status, COUNT(*) n FROM ai_question GROUP BY 1 ORDER BY 1"):
        print("  ", r[0], r[1])
    print("== events ==")
    for r in cur.execute(
            "SELECT event_type, COUNT(*) n FROM question_event GROUP BY 1 ORDER BY 1"):
        print("  ", r[0], r[1])

    print("\n== questions (21) ==")
    qs = cur.execute("""
        SELECT q.question_id, q.question_type, q.section_id, q.activity_id, q.page,
               q.question_text, q.options_json, q.correct_option, q.correct_answer,
               q.explanation, q.difficulty, q.lifecycle_status, q.stale, q.stale_reason,
               q.validator_version, q.needs_human_review
        FROM ai_question q ORDER BY q.section_id, q.activity_id, q.question_id
    """).fetchall()
    for r in qs:
        print("-" * 100)
        print(r["question_id"], "|", r["question_type"], "|", r["lifecycle_status"],
              "| stale", r["stale"], r["stale_reason"], "| pg", r["page"],
              "|", r["section_id"].split(":")[-1], r["activity_id"].split(":")[-1])
        print("   Q  :", r["question_text"])
        print("   OPT:", r["options_json"], " correct_option=", r["correct_option"])
        print("   ANS:", repr(r["correct_answer"]), "| difficulty", r["difficulty"],
              "| needs_human", r["needs_human_review"])
        print("   EXPL:", r["explanation"])
        for e in cur.execute(
                "SELECT ordinal, evidence_block_id, evidence_quote, is_primary"
                " FROM question_evidence WHERE question_id=? ORDER BY ordinal", (r["question_id"],)):
            print("   EV%d : %s | %r" % (e["ordinal"], e["evidence_block_id"], e["evidence_quote"]))
        for l in cur.execute(
                "SELECT item_id, is_primary FROM question_learning_object"
                " WHERE question_id=? ORDER BY is_primary DESC, item_id", (r["question_id"],)):
            print("   LO  :", l["item_id"], "(primary)" if l["is_primary"] else "")
        for v in cur.execute(
                "SELECT validator_version, validation_result, answer_support_type, note"
                " FROM question_validation WHERE question_id=?", (r["question_id"],)):
            print("   VAL :", v["validator_version"], v["validation_result"],
                  v["answer_support_type"], "|", v["note"])

    print("\n== schema (tables/triggers) ==")
    for r in cur.execute(
            "SELECT type, name FROM sqlite_master WHERE type IN ('table','trigger') ORDER BY type, name"):
        print("  ", r[0], r[1])
    con.close()


if __name__ == "__main__":
    main()

"""P1-04 · 把「因 validator 规则变化而不再合规」的存量题标记为 stale。

背景：problem B 使 `fill` 携带 options 成为结构不合格。
P1-03 入库的 AIQ:7EBCDBC29563（fill + options + correct_option）因此不再满足新规则。

本脚本**只做派生字段修正**（P1-04 §六 明确允许）：
  * 设置 stale=1 / stale_reason='VALIDATOR_CHANGED' / stale_since
  * 追加一条 append-only 的 MARKED_STALE 事件
**绝不修改**：question_text / options / correct_option / correct_answer / explanation /
evidence / question_fingerprint / lifecycle_status。
"""
import datetime
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import validator_v3 as V3  # noqa: E402

LIB = os.path.join(r"D:\ZhixueEnglish", "structured", "ai", "question_library.db")
TS = "2026-09-17T19:10:00+08:00"
BUSINESS_FIELDS = ["question_text", "options_json", "correct_option", "correct_answer",
                   "explanation", "question_fingerprint", "lifecycle_status",
                   "unit_id", "section_id", "activity_id", "page"]


def main():
    conn = sqlite3.connect(LIB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    rows = [dict(r) for r in conn.execute(
        "select q.*, v.answer_support_type, v.validation_result from ai_question q "
        "left join question_validation v on v.question_id=q.question_id and v.version=q.version "
        "order by q.question_id")]
    before = {r["question_id"]: {k: r[k] for k in BUSINESS_FIELDS} for r in rows}

    marked = []
    for r in rows:
        q = {"type": r["question_type"], "question": r["question_text"],
             "options": json.loads(r["options_json"]) if r["options_json"] else None,
             "correct_option": r["correct_option"], "answer": r["correct_answer"]}
        ok, reason = V3.type_rules(q)
        if ok or r["stale"] == 1:
            continue
        conn.execute(
            "UPDATE ai_question SET stale=1, stale_reason='VALIDATOR_CHANGED', stale_since=?, "
            "updated_at=? WHERE question_id=? AND version=?",
            (TS, TS, r["question_id"], r["version"]))
        conn.execute(
            "INSERT INTO question_event (event_id, question_id, version, event_type, from_status,"
            " to_status, event_at, actor, actor_kind, note) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("AIEV:%s:STALE1" % r["question_id"].split(":")[1], r["question_id"], r["version"],
             "MARKED_STALE", r["lifecycle_status"], r["lifecycle_status"], TS,
             "validator_v3", "machine",
             "P1-04: fill 结构规则收紧（fill 不得携带 options/correct_option）；原因：%s" % reason))
        marked.append({"question_id": r["question_id"], "version": r["version"],
                       "reason": reason, "lifecycle_unchanged": r["lifecycle_status"]})
    conn.commit()

    # 复核：业务内容未变
    after = {r["question_id"]: {k: r[k] for k in BUSINESS_FIELDS}
             for r in (dict(x) for x in conn.execute("select * from ai_question"))}
    changed = [qid for qid in before if before[qid] != after[qid]]
    out = {"marked_at": TS, "marked": marked, "business_fields_changed": changed,
           "result": "PASS" if not changed else "FAIL"}
    with open(os.path.join(HERE, "stale_marking.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

    print("标记为 stale 的题：%s" % [m["question_id"] for m in marked])
    print("业务内容发生变化的题：%s" % changed)
    conn.close()
    return 0 if not changed else 1


if __name__ == "__main__":
    raise SystemExit(main())

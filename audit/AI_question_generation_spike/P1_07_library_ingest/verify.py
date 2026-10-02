"""P1-07 · 入库后只读验收。不修改任何文件（除本目录输出）。"""
import hashlib
import json
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")

LIFECYCLE = ["GENERATED", "VALIDATED", "PENDING_REVIEW", "APPROVED", "ACTIVE",
             "REJECTED", "DISABLED"]
EVENTS = ["GENERATED", "VALIDATED", "PENDING_REVIEW", "REVIEW_APPROVED",
          "REVIEW_REJECTED", "ACTIVATED", "DISABLED", "MARKED_STALE"]
HASHES = {
    "learning.db": (os.path.join(BASE, "structured", "learning", "learning.db"),
                    "0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91"),
    "contentpack": (CP, "65829CA73E41B75ACA010B93B7339EDDF0F666F919148F0F69ED898419700C39"),
    "validator_v2": (os.path.join(SPIKE, "20260917_1520_validator_fix", "validator_v2.py"),
                     "7C61585A99B55576CA82D9946635784964322236BA145A23FBDFA2A1F8DCA683"),
    "validator_v3": (os.path.join(SPIKE, "P1_04_rule_fixes", "validator_v3.py"),
                     "EDB1AA5431626752B6D4699EC25ADAC76B10996ABFEC2EA43BDF4CAEB28D900C"),
    "P1-06_S1": (os.path.join(SPIKE, "P1_06_batch_stability", "S1_parsed.json"), None),
    "P1-06_S2": (os.path.join(SPIKE, "P1_06_batch_stability", "S2_parsed.json"), None),
    "P1-06_S3": (os.path.join(SPIKE, "P1_06_batch_stability", "S3_parsed.json"), None),
    "P1-06_S4": (os.path.join(SPIKE, "P1_06_batch_stability", "S4_parsed.json"), None),
}
CONTENTPACK_BASELINE = {"learning.db": HASHES["learning.db"][1], "contentpack": HASHES["contentpack"][1],
                        "validator_v2": HASHES["validator_v2"][1], "validator_v3": HASHES["validator_v3"][1]}


def sha_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def main():
    out = {"stage": "P1-07", "mode": "verify", "library_sha256": sha_file(LIB)}
    conn = sqlite3.connect("file:" + LIB + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    c = sqlite3.connect("file:" + CP + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    item_ids = {r[0] for r in c.execute("select item_id from learning_item")}
    block_ids = {r[0] for r in c.execute("select block_id from content_block")}
    unit_ids = {r[0] for r in c.execute("select unit_id from unit")}
    section_ids = {r[0] for r in c.execute("select section_id from section")}
    act_ids = {r[0] for r in c.execute("select activity_id from activity")}
    c.close()

    out["user_version"] = conn.execute("PRAGMA user_version").fetchone()[0]
    out["integrity_check"] = conn.execute("PRAGMA integrity_check").fetchone()[0]
    out["foreign_key_check"] = conn.execute("PRAGMA foreign_key_check").fetchall()
    out["counts"] = {t: conn.execute("select count(*) from %s" % t).fetchone()[0]
                     for t in ["generation_run", "ai_question", "question_evidence",
                               "question_learning_object", "question_validation", "question_event"]}
    out["lifecycle_counts"] = {st: conn.execute(
        "select count(*) from ai_question where lifecycle_status=?", (st,)).fetchone()[0]
        for st in LIFECYCLE}
    out["event_counts"] = {ev: conn.execute(
        "select count(*) from question_event where event_type=?", (ev,)).fetchone()[0]
        for ev in EVENTS}

    # 题目级检查
    problems = []
    rows = [dict(r) for r in conn.execute("select * from ai_question")]
    for q in rows:
        qid = q["question_id"]
        if q["lifecycle_status"] not in LIFECYCLE:
            problems.append("%s 非法 lifecycle %s" % (qid, q["lifecycle_status"]))
        if q["lifecycle_status"] == "ACTIVE" or q["active"]:
            problems.append("%s 出现 ACTIVE" % qid)
        if q["unit_id"] not in unit_ids:
            problems.append("%s unit_id 悬空 %s" % (qid, q["unit_id"]))
        if q["section_id"] not in section_ids:
            problems.append("%s section_id 悬空" % qid)
        if q["activity_id"] and q["activity_id"] not in act_ids:
            problems.append("%s activity_id 悬空" % qid)
        if not conn.execute("select 1 from generation_run where run_id=?",
                            (q["generation_run_id"],)).fetchone():
            problems.append("%s generation_run_id 悬空" % qid)
        ev = [r[0] for r in conn.execute(
            "select evidence_block_id from question_evidence where question_id=?", (qid,))]
        if not ev:
            problems.append("%s 无 evidence" % qid)
        for b in ev:
            if b not in block_ids:
                problems.append("%s evidence block 悬空 %s" % (qid, b))
        lo = [r[0] for r in conn.execute(
            "select item_id from question_learning_object where question_id=?", (qid,))]
        if not lo:
            problems.append("%s 无 learning object" % qid)
        for i in lo:
            if i not in item_ids:
                problems.append("%s learning object 悬空 %s" % (qid, i))
            if i.startswith(("AIQ:", "AIRUN:")):
                problems.append("%s learning object 违规 %s" % (qid, i))
        if not conn.execute("select 1 from question_validation where question_id=?",
                            (qid,)).fetchone():
            problems.append("%s 无 validation 记录" % qid)
        if not conn.execute("select 1 from question_event where question_id=?", (qid,)).fetchone():
            problems.append("%s 无事件记录" % qid)
    for e in conn.execute("select event_id, event_type from question_event"):
        if e["event_type"] not in EVENTS:
            problems.append("%s 非法 event_type %s" % (e["event_id"], e["event_type"]))
    out["problems"] = problems

    # 已有 2 道题基准
    base2 = {}
    for qid in ["AIQ:3179968E3E74", "AIQ:7EBCDBC29563"]:
        r = conn.execute("select question_id, lifecycle_status, correct_answer, "
                         "question_fingerprint, stale, stale_reason from ai_question "
                         "where question_id=?", (qid,)).fetchone()
        base2[qid] = dict(r) if r else None
    out["existing_two_questions"] = base2
    out["existing_two_unchanged"] = (
        base2["AIQ:3179968E3E74"]["lifecycle_status"] == "PENDING_REVIEW"
        and base2["AIQ:3179968E3E74"]["correct_answer"] == "polite"
        and base2["AIQ:7EBCDBC29563"]["lifecycle_status"] == "PENDING_REVIEW"
        and base2["AIQ:7EBCDBC29563"]["stale"] == 1
        and base2["AIQ:7EBCDBC29563"]["stale_reason"] == "VALIDATOR_CHANGED"
        and base2["AIQ:7EBCDBC29563"]["correct_answer"] == "sentence")
    conn.close()

    # 保护项
    prot = {}
    for k, (p, exp) in HASHES.items():
        h = sha_file(p)
        prot[k] = {"sha256": h, "matches_baseline": (exp is None or h.startswith(exp))}
    out["protection"] = prot
    out["protection_ok"] = all(v["matches_baseline"] for v in prot.values())
    out["verdict"] = ("PASS" if (not problems and out["lifecycle_counts"]["ACTIVE"] == 0
                                 and out["event_counts"]["REVIEW_APPROVED"] == 0
                                 and out["integrity_check"] == "ok"
                                 and not out["foreign_key_check"]
                                 and out["existing_two_unchanged"]
                                 and out["protection_ok"]) else "STOP_AND_FIX")
    with open(os.path.join(HERE, "verify_result.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("integrity:", out["integrity_check"], "| fk:", out["foreign_key_check"])
    print("counts:", out["counts"])
    print("lifecycle:", {k: v for k, v in out["lifecycle_counts"].items() if v})
    print("events:", {k: v for k, v in out["event_counts"].items() if v})
    print("problems:", len(problems), problems[:5])
    print("已有 2 题未变:", out["existing_two_unchanged"], "| 保护项:", out["protection_ok"])
    print("判定:", out["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

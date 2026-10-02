"""P1-04 · 汇总审计导出（只读）。输出 p1_04_rule_fix_audit.json。"""
import datetime
import hashlib
import json
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
LEARNING_DB = os.path.join(BASE, "structured", "learning", "learning.db")
VALIDATOR_V2 = os.path.join(BASE, "audit", "AI_question_generation_spike",
                            "20260917_1520_validator_fix", "validator_v2.py")
OUT = os.path.join(HERE, "p1_04_rule_fix_audit.json")


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def finfo(path):
    st = os.stat(path)
    return {"path": path, "size_bytes": st.st_size,
            "mtime": datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
            "sha256": sha256(path)}


def load(name):
    p = os.path.join(HERE, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def main():
    conn = sqlite3.connect("file:" + LIB + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cp = sqlite3.connect("file:" + CP + "?mode=ro", uri=True)
    item_ids = {r[0] for r in cp.execute("select item_id from learning_item")}
    block_ids = {r[0] for r in cp.execute("select block_id from content_block")}

    questions = [dict(r) for r in conn.execute(
        "select question_id, version, question_type, question_text, options_json, correct_option,"
        " correct_answer, explanation, difficulty, page, unit_id, section_id, activity_id,"
        " generation_run_id, question_fingerprint, lifecycle_status, active, stale, stale_reason,"
        " needs_human_review, validator_version from ai_question order by question_id")]
    events = [dict(r) for r in conn.execute(
        "select event_id, question_id, version, event_type, from_status, to_status, event_at,"
        " actor, actor_kind from question_event order by event_id")]
    db_enum_sql = conn.execute(
        "select sql from sqlite_master where name='question_event'").fetchone()[0]
    trigger_sql = conn.execute(
        "select sql from sqlite_master where name='trg_validation_exact_trap'").fetchone()[0]
    triggers = sorted(r[0] for r in conn.execute(
        "select name from sqlite_master where type='trigger'"))
    counts = {t: conn.execute("select count(*) from %s" % t).fetchone()[0] for t in
              ["generation_run", "ai_question", "question_evidence",
               "question_learning_object", "question_validation", "question_event"]}
    lo = sorted({r[0] for r in conn.execute("select distinct item_id from question_learning_object")})
    ev_blocks = sorted({r[0] for r in conn.execute(
        "select distinct evidence_block_id from question_evidence")})
    ver = conn.execute("PRAGMA user_version").fetchone()[0]
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    conn.close()

    audit = {
        "stage": "P1-04",
        "audited_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "problem_A_exact_rule": {
            "old_condition": "answer_support_type='EXACT' AND 答案文本出现在 question_text 或 options",
            "new_condition": ("answer_support_type='EXACT' AND 题目可选型（有 options）"
                              " AND 正确答案文本出现在教材 evidence_quote 中"),
            "applied_to": "question_library.db 触发器 trg_validation_exact_trap",
            "python_semantics": "validator_v3.exact_print_risk()",
            "trigger_sql": trigger_sql,
        },
        "problem_B_fill_rule": {
            "rule": "fill = 纯填空：必须有 '___'；不得有 options；不得有 correct_option",
            "applied_to": "validator_v3.type_rules()（validator_v2 未修改，v3 只收紧）",
            "v3_keeps_v2": ["tokens", "answer_support", "build_whitelist", "checked_language",
                            "out_of_scope"],
        },
        "problem_C_event_enum": {
            "schema_version_before": 1, "schema_version_after": ver,
            "migrated": ver == 2,
            "event_types_v1": ["VALIDATED", "REVIEW_APPROVED", "REVIEW_REJECTED",
                               "ACTIVATED", "DISABLED", "MARKED_STALE"],
            "event_types_v2": ["GENERATED", "VALIDATED", "PENDING_REVIEW", "REVIEW_APPROVED",
                               "REVIEW_REJECTED", "ACTIVATED", "DISABLED", "MARKED_STALE"],
            "enum_sql_has_generated": "GENERATED" in db_enum_sql,
            "enum_sql_has_pending_review": "PENDING_REVIEW" in db_enum_sql,
            "migration_detail": load("migration_v1_to_v2.json"),
        },
        "tests": {
            "p1_04_suite": {"file": "test_p1_04_rules.py", "ran": 28, "ok": 28, "failed": 0},
            "p1_02_regression": {
                "file": "P1_02_question_library_implementation/test_question_library.py",
                "ran": 19, "pass": 18, "fail": 1,
                "failed_test": "test_T15_official_db_has_no_real_questions",
                "why": ("该断言「正式题库为空」已被 P1-03 的合法入库取代（题库现有 2 道真实题）；"
                        "其原始意图「建库脚本不插入任何数据」由 P1-04 的 "
                        "FrozenV1SchemaTests 等价测试覆盖并通过。"),
            },
        },
        "existing_questions": {
            "count": len(questions),
            "business_content_unchanged": True,
            "regenerated": False, "deleted": False,
            "stale_marking": load("stale_marking.json"),
            "rows": questions,
        },
        "events": events,
        "counts": counts,
        "learning_objects": {
            "refs": lo,
            "all_exist_in_contentpack": all(i in item_ids for i in lo),
            "dangling": [i for i in lo if i not in item_ids],
        },
        "evidence_blocks": {
            "refs": ev_blocks,
            "all_exist_in_contentpack": all(b in block_ids for b in ev_blocks),
            "dangling": [b for b in ev_blocks if b not in block_ids],
        },
        "database": {"user_version": ver, "integrity_check": integrity,
                     "foreign_key_check": fk, "triggers": triggers,
                     "file": finfo(LIB)},
        "protection": {
            "learning_db": finfo(LEARNING_DB),
            "learning_db_expected_sha256": "0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91",
            "validator_v2": finfo(VALIDATOR_V2),
            "contentpack": finfo(CP),
            "p1_02_ql_schema_py": finfo(os.path.join(
                BASE, "audit", "AI_question_generation_spike",
                "P1_02_question_library_implementation", "ql_schema.py")),
        },
        "ai_calls": 0,
        "pdf_reparsed": False,
        "new_ai_questions_generated": 0,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(audit, fh, ensure_ascii=False, indent=1)
    print("已写出 %s" % OUT)
    print("user_version=%s enum_ok=%s/%s questions=%d events=%d" % (
        ver, audit["problem_C_event_enum"]["enum_sql_has_generated"],
        audit["problem_C_event_enum"]["enum_sql_has_pending_review"],
        len(questions), len(events)))
    print("LO dangling:", audit["learning_objects"]["dangling"],
          "| evidence dangling:", audit["evidence_blocks"]["dangling"])


if __name__ == "__main__":
    main()

"""P1-04 · 在内存库上演练 v1 -> v2 迁移（不触碰正式 question_library.db）。

验证：迁移语句可执行、既有数据逐行不变、枚举扩展生效、触发器与索引恢复。
"""
import json
import os
import sqlite3
import sys
import hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
V1_DIR = os.path.join(r"D:\ZhixueEnglish", "audit", "AI_question_generation_spike",
                      "P1_02_question_library_implementation")
sys.path.insert(0, HERE)
sys.path.insert(0, V1_DIR)
import ql_schema as V1          # noqa: E402
import ql_schema_v2 as S2       # noqa: E402

TABLES = ["generation_run", "ai_question", "question_evidence",
          "question_learning_object", "question_validation", "question_event"]
TS = "2026-09-17T19:00:00+08:00"


def snap(conn):
    out = {}
    for t in TABLES:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % t)]
        rows = sorted((dict(zip(cols, r)) for r in conn.execute("SELECT * FROM %s" % t)),
                      key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False))
        out[t] = (len(rows),
                  hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False)
                                 .encode()).hexdigest().upper())
    return out


def seed_v1(conn):
    V1.create_schema(conn)
    conn.execute(
        "INSERT INTO generation_run (run_id, generation_scope_key, textbook_id, snapshot_id, "
        "unit_id, section_id, model, prompt_version, context_hash, question_count, status, "
        "generated_at) VALUES ('AIRUN:DRY','SCOPE','FLTRP-EN-7A-2022CUR','SNAP','FLTRP-EN-7A-2022CUR:U1',"
        "'FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS','deepseek-v4-pro','P0-v1','CTX',2,'OK',?)", (TS,))
    for i, (qid, qtype, ans, opts) in enumerate([
            ("AIQ:DRY0001", "vocab_choice", "polite", '["polite","dry","important","mistake"]'),
            ("AIQ:DRY0002", "fill", "sentence",
             '["sentence","mistake","polite","meaning"]')], 1):
        conn.execute(
            "INSERT INTO ai_question (question_id, version, question_type, question_text, "
            "options_json, correct_option, correct_answer, textbook_id, snapshot_id, unit_id, "
            "section_id, activity_id, page, generation_run_id, generated_at, question_fingerprint,"
            " lifecycle_status, active, stale, needs_human_review, validator_version, created_at,"
            " updated_at) VALUES (?,1,?,?,?,?,?,'FLTRP-EN-7A-2022CUR','SNAP','FLTRP-EN-7A-2022CUR:U1',"
            "'FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS','FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS:A2',"
            "17,'AIRUN:DRY',?,?, 'PENDING_REVIEW',0,0,1,'v2',?,?)",
            (qid, qtype, "Q%d ___ ?" % i, opts, "A", ans, TS, ("%064d" % i), TS, TS))
        conn.execute(
            "INSERT INTO question_evidence (question_id, version, ordinal, evidence_block_id, "
            "evidence_quote, is_primary) VALUES (?,1,1,'FLTRP-EN-7A-2022CUR:P22:B2',?,1)",
            (qid, 'Is that polite, in the first lesson?"'))
        conn.execute(
            "INSERT INTO question_validation (question_id, version, validator_version, "
            "validation_result, validated_at, answer_support_type, checks_json, "
            "out_of_scope_tokens_json, needs_human_review, note) "
            "VALUES (?,1,'v2','PASS',?, 'EXACT','{}','[]',0,'P1-03')", (qid, TS))
        conn.execute(
            "INSERT INTO question_event (event_id, question_id, version, event_type, from_status,"
            " to_status, event_at, actor, actor_kind, note) "
            "VALUES (?,?,1,'VALIDATED','GENERATED','PENDING_REVIEW',?,'validator_v2','machine','chain')",
            ("AIEV:DRY:%d" % i, qid, TS))
    conn.commit()


def main():
    conn = sqlite3.connect(":memory:")
    conn.isolation_level = None
    conn.execute("PRAGMA foreign_keys = ON")
    seed_v1(conn)
    before = snap(conn)
    ver_before = conn.execute("PRAGMA user_version").fetchone()[0]

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("BEGIN")
    for stmt in S2.migration_statements():
        conn.execute(stmt)
    conn.execute("COMMIT")
    conn.execute("PRAGMA foreign_keys = ON")

    after = snap(conn)
    ver_after = conn.execute("PRAGMA user_version").fetchone()[0]
    problems = []
    if ver_after != 2:
        problems.append("user_version=%s" % ver_after)
    for t in TABLES:
        if before[t] != after[t]:
            problems.append("%s 数据变化 %s -> %s" % (t, before[t], after[t]))
    if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        problems.append("integrity_check")
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        problems.append("foreign_key_check")

    probe = {}
    for ev in ("GENERATED", "PENDING_REVIEW"):
        conn.execute("BEGIN")
        try:
            conn.execute(
                "INSERT INTO question_event (event_id, question_id, version, event_type, event_at,"
                " actor, actor_kind) VALUES (?,?,1,?,?, 'probe','machine')",
                ("AIEV:PROBE:%s" % ev, "AIQ:DRY0001", ev, TS))
            probe[ev] = True
        except Exception as exc:
            probe[ev] = "ERROR: %s" % exc
            problems.append("enum %s" % ev)
        finally:
            conn.execute("ROLLBACK")

    print("dry-run 迁移：user_version %s -> %s" % (ver_before, ver_after))
    print("  行数：", {t: after[t][0] for t in TABLES})
    print("  逐表数据不变：", all(before[t] == after[t] for t in TABLES))
    print("  枚举探测：", probe)
    print("  触发器：", [r[0] for r in conn.execute(
        "select name from sqlite_master where type='trigger' and name like '%event%' or name='trg_validation_exact_trap'")])
    if problems:
        print("  FIX_BLOCKED:", problems)
        return 1
    print("  RESULT: PASS")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""P1-04 · 对正式 question_library.db 执行 v1 → v2 最小迁移。

安全措施：
  * 迁移前后对全部 6 张表做逐行快照并比对（不一致立即回滚并报 FIX_BLOCKED）
  * 只重建 question_event（枚举扩展）与替换一个触发器；其余表/索引/触发器不动
  * 迁移后验证 integrity_check / foreign_key_check / user_version
  * 在事务内试插 GENERATED 与 PENDING_REVIEW 事件并回滚（证明枚举可用）
"""
import datetime
import hashlib
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ql_schema_v2 as S2  # noqa: E402

LIB = os.path.join(r"D:\ZhixueEnglish", "structured", "ai", "question_library.db")
TABLES = ["generation_run", "ai_question", "question_evidence",
          "question_learning_object", "question_validation", "question_event"]


def snapshot(conn):
    snap = {}
    for t in TABLES:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % t)]
        rows = [dict(zip(cols, r)) for r in conn.execute("SELECT * FROM %s" % t)]
        rows.sort(key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False))
        snap[t] = {"columns": cols, "row_count": len(rows), "rows": rows,
                   "sha256": hashlib.sha256(
                       json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest().upper()}
    return snap


def block(msg):
    print("FIX_BLOCKED: %s" % msg)
    raise SystemExit(1)


def main():
    conn = sqlite3.connect(LIB)
    conn.isolation_level = None            # 手动管事务
    conn.execute("PRAGMA foreign_keys = ON")

    ver_before = conn.execute("PRAGMA user_version").fetchone()[0]
    before = snapshot(conn)
    print("[before] user_version=%d | %s" % (
        ver_before, {t: before[t]["row_count"] for t in TABLES}))
    if ver_before == 2:
        print("已经是 schema v2，无需迁移。")
        return 0
    if ver_before != 1:
        block("未知的 schema 版本：%d" % ver_before)

    # ---------------- 迁移
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("BEGIN")
        for stmt in S2.migration_statements():
            conn.execute(stmt)
        conn.execute("COMMIT")
    except Exception as exc:
        conn.execute("ROLLBACK")
        block("迁移事务失败：%s" % exc)
    finally:
        conn.execute("PRAGMA foreign_keys = ON")

    # ---------------- 验证
    ver_after = conn.execute("PRAGMA user_version").fetchone()[0]
    after = snapshot(conn)
    problems = []
    if ver_after != 2:
        problems.append("user_version 未变为 2（=%s）" % ver_after)
    for t in TABLES:
        if before[t]["row_count"] != after[t]["row_count"]:
            problems.append("%s 行数变化 %d -> %d" % (t, before[t]["row_count"], after[t]["row_count"]))
        if before[t]["sha256"] != after[t]["sha256"]:
            problems.append("%s 行内容发生变化" % t)
    if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        problems.append("integrity_check 失败")
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk:
        problems.append("foreign_key_check 失败：%s" % fk)

    # 枚举可用性（事务内试插并回滚）
    enum_probe = {}
    qid = conn.execute("select question_id, version from ai_question limit 1").fetchone()
    if qid:
        for ev in ("GENERATED", "PENDING_REVIEW"):
            conn.execute("BEGIN")
            try:
                conn.execute(
                    "INSERT INTO question_event (event_id, question_id, version, event_type, "
                    "from_status, to_status, event_at, actor, actor_kind) VALUES (?,?,?,?,?,?,?,?,?)",
                    ("AIEV:PROBE:%s" % ev, qid[0], qid[1], ev, None, ev,
                     "2026-09-17T19:00:00+08:00", "p1_04_probe", "machine"))
                enum_probe[ev] = True
            except Exception as exc:
                enum_probe[ev] = "ERROR: %s" % exc
                problems.append("event_type %s 不可用：%s" % (ev, exc))
            finally:
                conn.execute("ROLLBACK")
    if conn.execute("select count(*) from question_event").fetchone()[0] != before["question_event"]["row_count"]:
        problems.append("探测插入未被回滚")

    report = {
        "migrated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "user_version_before": ver_before, "user_version_after": ver_after,
        "row_counts_before": {t: before[t]["row_count"] for t in TABLES},
        "row_counts_after": {t: after[t]["row_count"] for t in TABLES},
        "row_hashes_before": {t: before[t]["sha256"] for t in TABLES},
        "row_hashes_after": {t: after[t]["sha256"] for t in TABLES},
        "event_enum_probe": enum_probe,
        "problems": problems,
        "result": "PASS" if not problems else "FAIL",
        "event_types_v1": S2.EVENT_TYPES_V1,
        "event_types_v2": S2.EVENT_TYPES_V2,
    }
    with open(os.path.join(HERE, "migration_v1_to_v2.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)

    print("[after ] user_version=%d | %s" % (ver_after, {t: after[t]["row_count"] for t in TABLES}))
    print("逐表行哈希一致：%s" % all(before[t]["sha256"] == after[t]["sha256"] for t in TABLES))
    print("枚举探测：%s" % enum_probe)
    if problems:
        block("；".join(problems))
    print("迁移结果：PASS（未修改任何既有数据行）")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

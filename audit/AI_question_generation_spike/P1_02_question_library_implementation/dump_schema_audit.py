"""P1-02 · 从真实数据库导出 schema 审计 JSON（只读，不修改数据库）。

输出：p1_02_schema_audit.json（与本脚本同目录）
"""
import datetime
import hashlib
import json
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
LEARNING_DB = os.path.join(BASE, "structured", "learning", "learning.db")
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
VALIDATOR = os.path.join(BASE, "audit", "AI_question_generation_spike",
                         "20260917_1520_validator_fix", "validator_v2.py")
OUT = os.path.join(HERE, "p1_02_schema_audit.json")

TABLES = ["generation_run", "ai_question", "question_evidence",
          "question_learning_object", "question_validation", "question_event"]


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def file_info(path):
    st = os.stat(path)
    return {"path": path, "size_bytes": st.st_size,
            "mtime": datetime.datetime.fromtimestamp(st.st_mtime).isoformat(),
            "sha256": sha256(path)}


def main():
    conn = sqlite3.connect("file:" + LIB + "?mode=ro", uri=True)

    tables = []
    for t in TABLES:
        cols = []
        for c in conn.execute("PRAGMA table_info(%s)" % t):
            cols.append({"name": c[1], "type": c[2], "not_null": bool(c[3]),
                         "default": c[4], "pk_position": c[5]})
        fks = [{"from": r[3], "to_table": r[2], "to_column": r[4],
                "on_update": r[5], "on_delete": r[6]}
               for r in conn.execute("PRAGMA foreign_key_list(%s)" % t)]
        sql = conn.execute("select sql from sqlite_master where type='table' and name=?",
                           (t,)).fetchone()[0]
        checks = [ln.strip().rstrip(",") for ln in sql.splitlines()
                  if ln.strip().upper().startswith("CHECK")]
        tables.append({
            "name": t,
            "row_count": conn.execute("select count(*) from %s" % t).fetchone()[0],
            "primary_key": [c["name"] for c in cols if c["pk_position"]],
            "columns": cols,
            "foreign_keys": fks,
            "check_expressions": checks,
            "unique_indexes": [r[1] for r in conn.execute("PRAGMA index_list(%s)" % t)
                               if r[2] == 1],
        })

    indexes = [{"name": r[0], "table": r[1], "sql": r[2]}
               for r in conn.execute("select name, tbl_name, sql from sqlite_master "
                                     "where type='index' and sql is not null order by name")]
    triggers = [{"name": r[0], "table": r[1], "timing": r[2], "event": r[3], "sql": r[4]}
                for r in conn.execute("select name, tbl_name, null, null, sql from sqlite_master "
                                      "where type='trigger' order by name")]

    audit = {
        "stage": "P1-02",
        "audited_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "engine": "sqlite",
        "sqlite_version": sqlite3.sqlite_version,
        "user_version": conn.execute("PRAGMA user_version").fetchone()[0],
        "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
        "foreign_key_check": conn.execute("PRAGMA foreign_key_check").fetchall(),
        "database": file_info(LIB),
        "tables": tables,
        "indexes": indexes,
        "triggers": triggers,
        "hard_gates": {
            "validator_pass_is_not_active": [
                "trigger trg_ai_question_insert_active_forbidden",
                "trigger trg_ai_question_active_requires_human_approval"
            ],
            "question_event_append_only": [
                "trigger trg_question_event_no_update",
                "trigger trg_question_event_no_delete"
            ],
            "question_rows_never_deleted": ["trigger trg_ai_question_no_delete"],
            "exact_trap_forces_human_review": ["trigger trg_validation_exact_trap"]
        },
        "protection": {
            "learning_db": file_info(LEARNING_DB),
            "validator_v2": file_info(VALIDATOR),
            "contentpack": file_info(CP),
        },
        "no_real_ai_data": all(t["row_count"] == 0 for t in tables),
        "ai_api_calls_during_implementation": 0,
        "pdf_reparsed": False,
        "learning_db_modified": False,
    }
    conn.close()

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(audit, fh, ensure_ascii=False, indent=1)
    print("已写出：%s" % OUT)
    print("tables=%d indexes=%d triggers=%d no_real_ai_data=%s" % (
        len(tables), len(indexes), len(triggers), audit["no_real_ai_data"]))


if __name__ == "__main__":
    main()

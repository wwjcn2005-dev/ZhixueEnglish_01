#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-06-B1.13 学习层独立数据库初始化（最小实现、幂等）

用途：按 P1-06-B1.12 冻结的 Schema，创建独立的学习数据库 learning.db
      （5 张业务表 + 1 张 schema_migration 表 + 6 个业务索引）。

硬约束：
  1. 幂等：PRAGMA user_version >= 1 时不做任何修改（不重建、不删数据）
  2. 不覆盖、不删除既有 learning.db 及其数据
  3. 不触碰 contentpack（不 ATTACH / 不复制 / 无跨库 FK）
  4. 不插入任何业务数据（不创建默认 Learner、不写测试数据）
  5. 仅使用 Python 标准库；不联网、不调用 AI
  6. DDL 在一个事务内完成；失败整体回滚并清理本次新建的空库文件

用法：
  python structured/learning/init_learning_db.py
"""

from __future__ import annotations

import hashlib
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(r"D:\ZhixueEnglish")
DB_PATH = BASE / "structured" / "learning" / "learning.db"
SCHEMA_VERSION = 1

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE learner (
      learner_id   TEXT PRIMARY KEY,
      display_name TEXT NOT NULL,
      status       TEXT NOT NULL DEFAULT 'active',
      created_at   TEXT NOT NULL,
      updated_at   TEXT
    )
    """,
    """
    CREATE TABLE learning_task (
      task_id      TEXT PRIMARY KEY,
      learner_id   TEXT NOT NULL REFERENCES learner(learner_id) ON DELETE RESTRICT ON UPDATE CASCADE,
      goal_id      TEXT,
      task_kind    TEXT NOT NULL,
      status       TEXT NOT NULL DEFAULT 'active',
      textbook_id  TEXT NOT NULL,
      created_at   TEXT NOT NULL,
      started_at   TEXT,
      completed_at TEXT,
      title        TEXT
    )
    """,
    "CREATE INDEX idx_learning_task_learner ON learning_task(learner_id, status, created_at)",
    """
    CREATE TABLE task_item (
      task_id    TEXT NOT NULL REFERENCES learning_task(task_id) ON DELETE CASCADE ON UPDATE CASCADE,
      item_id    TEXT NOT NULL,
      ordinal    INTEGER,
      created_at TEXT,
      PRIMARY KEY (task_id, item_id)
    )
    """,
    "CREATE INDEX idx_task_item_item ON task_item(item_id)",
    """
    CREATE TABLE learning_record (
      record_id     TEXT PRIMARY KEY,
      learner_id    TEXT NOT NULL REFERENCES learner(learner_id) ON DELETE RESTRICT ON UPDATE CASCADE,
      task_id       TEXT NOT NULL REFERENCES learning_task(task_id) ON DELETE RESTRICT ON UPDATE CASCADE,
      item_id       TEXT NOT NULL,
      activity_type TEXT NOT NULL,
      result        TEXT,
      response_raw  TEXT,
      attempt_no    INTEGER NOT NULL DEFAULT 1,
      hints_used    INTEGER NOT NULL DEFAULT 0,
      textbook_id   TEXT NOT NULL,
      snapshot_id   TEXT,
      created_at    TEXT NOT NULL
    )
    """,
    "CREATE INDEX idx_record_learner_time ON learning_record(learner_id, created_at)",
    "CREATE INDEX idx_record_learner_item_time ON learning_record(learner_id, item_id, created_at)",
    "CREATE INDEX idx_record_task ON learning_record(task_id)",
    """
    CREATE TABLE mastery_state (
      learner_id        TEXT NOT NULL REFERENCES learner(learner_id) ON DELETE RESTRICT ON UPDATE CASCADE,
      item_id           TEXT NOT NULL,
      mastery_level     TEXT NOT NULL DEFAULT 'unknown',
      evidence_count    INTEGER NOT NULL DEFAULT 0,
      correct_count     INTEGER NOT NULL DEFAULT 0,
      last_result       TEXT,
      last_practiced_at TEXT,
      review_needed     INTEGER NOT NULL DEFAULT 0,
      updated_at        TEXT NOT NULL,
      PRIMARY KEY (learner_id, item_id)
    )
    """,
    "CREATE INDEX idx_mastery_review ON mastery_state(learner_id, review_needed)",
    """
    CREATE TABLE schema_migration (
      version     INTEGER PRIMARY KEY,
      applied_at  TEXT NOT NULL,
      description TEXT,
      sql_sha256  TEXT
    )
    """,
]

DDL_TEXT = ";\n".join(s.strip() for s in SCHEMA_STATEMENTS) + ";"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if not DB_PATH.parent.exists():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    existed_before = DB_PATH.exists()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current >= SCHEMA_VERSION:
        tables = sorted(r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
        print("ALREADY_INITIALIZED user_version=%d tables=%s" % (current, ",".join(tables)))
        conn.close()
        return 0

    try:
        conn.execute("BEGIN IMMEDIATE")
        for stmt in SCHEMA_STATEMENTS:
            conn.execute(stmt)
        conn.execute(
            "INSERT INTO schema_migration(version, applied_at, description, sql_sha256) VALUES(?,?,?,?)",
            (SCHEMA_VERSION, now_iso(), "P1-06-B1.13 initial learning schema (frozen by B1.12)",
             hashlib.sha256(DDL_TEXT.encode("utf-8")).hexdigest()))
        conn.execute("PRAGMA user_version = %d" % SCHEMA_VERSION)
        conn.commit()
    except Exception as exc:  # 回滚 + 清理本次新建的空库
        conn.rollback()
        tables = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0]
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.close()
        if not existed_before and tables == 0 and version == 0:
            DB_PATH.unlink(missing_ok=True)
        print("FAILED: %s" % exc)
        return 2

    tables = sorted(r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
    indexes = sorted(r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"))
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    fk = len(conn.execute("PRAGMA foreign_key_check").fetchall())
    counts = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in tables}
    conn.close()

    print("=" * 70)
    print("P1-06-B1.13 learning.db 初始化完成")
    print("path          : %s" % DB_PATH)
    print("user_version  : %d" % version)
    print("tables (%d)   : %s" % (len(tables), ", ".join(tables)))
    print("indexes (%d)  : %s" % (len(indexes), ", ".join(indexes)))
    print("integrity     : %s ｜ foreign_key_check: %d" % (integrity, fk))
    print("row counts    : %s" % counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())

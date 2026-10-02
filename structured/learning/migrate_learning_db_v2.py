#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-07-C1 学习库最小迁移：v1 → v2（新增 learning_session 表）

新增内容（仅此一项）：
  - learning_session（P1-04 §23 定义的 LearningSession 落地）
      session_id / learner_id / started_at / ended_at / entry_point
      + task_id（P1-07-C1 §五 要求的 Session → Task 关联，唯一新增字段）
  - idx_learning_session_learner(learner_id, started_at)

约束：
  1. 幂等：PRAGMA user_version >= 2 时不做任何修改
  2. 迁移前自动备份 learning.db（备份文件已存在则不覆盖）
  3. 事务内完成（DDL + schema_migration 记录 + user_version），失败整体回滚
  4. 不改动既有 6 张表（learner / learning_task / task_item / learning_record /
     mastery_state / schema_migration 的既有列与数据），不删除历史数据
  5. 不触碰 contentpack（不 ATTACH、不复制、无跨库 FK）
  6. 仅使用 Python 标准库

用法：
  python structured/learning/migrate_learning_db_v2.py
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(r"D:\ZhixueEnglish")
DB_PATH = BASE / "structured" / "learning" / "learning.db"
BACKUP_PATH = BASE / "structured" / "learning" / "learning.db.bak-v1"
TARGET_VERSION = 2

MIGRATION_STATEMENTS = [
    """
    CREATE TABLE learning_session (
      session_id  TEXT PRIMARY KEY,
      learner_id  TEXT NOT NULL REFERENCES learner(learner_id) ON DELETE RESTRICT ON UPDATE CASCADE,
      started_at  TEXT NOT NULL,
      ended_at    TEXT,
      entry_point TEXT NOT NULL,
      task_id     TEXT NOT NULL REFERENCES learning_task(task_id) ON DELETE RESTRICT ON UPDATE CASCADE
    )
    """,
    "CREATE INDEX idx_learning_session_learner ON learning_session(learner_id, started_at)",
]

SQL_TEXT = ";\n".join(s.strip() for s in MIGRATION_STATEMENTS) + ";"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if not DB_PATH.exists():
        print("STOP: learning.db 不存在：%s" % DB_PATH)
        return 2

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current >= TARGET_VERSION:
        tables = sorted(r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
        print("ALREADY_MIGRATED user_version=%d tables=%s" % (current, ",".join(tables)))
        conn.close()
        return 0
    if current != 1:
        conn.close()
        print("STOP: 预期 user_version=1，实际 %d（不由本脚本处理）" % current)
        return 2

    # 迁移前备份（不覆盖已有备份）
    backed_up = None
    if not BACKUP_PATH.exists():
        shutil.copyfile(DB_PATH, BACKUP_PATH)
        backed_up = str(BACKUP_PATH)

    try:
        conn.execute("BEGIN IMMEDIATE")
        for stmt in MIGRATION_STATEMENTS:
            conn.execute(stmt)
        conn.execute(
            "INSERT INTO schema_migration(version, applied_at, description, sql_sha256) VALUES(?,?,?,?)",
            (TARGET_VERSION, now_iso(),
             "P1-07-C1 add learning_session (LearningSession per P1-04 §23 + task link)",
             hashlib.sha256(SQL_TEXT.encode("utf-8")).hexdigest()))
        conn.execute("PRAGMA user_version = %d" % TARGET_VERSION)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        conn.close()
        print("FAILED: %s" % exc)
        return 2

    tables = sorted(r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
    indexes = sorted(r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"))
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    fk = len(conn.execute("PRAGMA foreign_key_check").fetchall())
    fks = [(t, r[2], r[3], r[6]) for t in ("learning_session",)
           for r in conn.execute("PRAGMA foreign_key_list(%s)" % t)]
    counts = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in tables}
    conn.close()

    print("=" * 70)
    print("P1-07-C1 learning.db 迁移完成：v1 → v2")
    print("path        : %s" % DB_PATH)
    print("backup      : %s" % (backed_up or "（已存在，未覆盖）"))
    print("user_version: %d" % version)
    print("tables (%d) : %s" % (len(tables), ", ".join(tables)))
    print("indexes (%d): %s" % (len(indexes), ", ".join(indexes)))
    print("session FK  : %s" % fks)
    print("integrity   : %s ｜ foreign_key_check: %d" % (integrity, fk))
    print("row counts  : %s" % counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""P1-04 · question_library schema v2（在 v1 之上的最小增量，不重写 5 张表）。

v2 相对 v1 只有两处改动：
  A. `trg_validation_exact_trap` 触发条件修正
     —— 由「答案出现在题干/选项中」改为
        「题目可选型 + 正确答案文本本身出现在教材 evidence_quote 中」
  C. `question_event.event_type` 枚举补充 `GENERATED` / `PENDING_REVIEW`

其余 5 张表、全部索引、全部其他触发器**完全沿用 v1 定义**（直接 import，不复制）。
v1 的 ql_schema.py 保持原样不动。
"""
import os
import sys

V1_DIR = os.path.join(r"D:\ZhixueEnglish", "audit", "AI_question_generation_spike",
                      "P1_02_question_library_implementation")
if V1_DIR not in sys.path:
    sys.path.insert(0, V1_DIR)
import ql_schema as v1  # noqa: E402

SCHEMA_VERSION = 2

TABLE_NAMES = list(v1.TABLE_NAMES)

EVENT_TYPES_V1 = ["VALIDATED", "REVIEW_APPROVED", "REVIEW_REJECTED",
                  "ACTIVATED", "DISABLED", "MARKED_STALE"]
EVENT_TYPES_V2 = ["GENERATED", "VALIDATED", "PENDING_REVIEW", "REVIEW_APPROVED",
                  "REVIEW_REJECTED", "ACTIVATED", "DISABLED", "MARKED_STALE"]

# ------------------------------------------------------------------ C) question_event 枚举扩展
QUESTION_EVENT_DDL_V2 = """
    CREATE TABLE question_event (
      event_id    TEXT PRIMARY KEY,
      question_id TEXT NOT NULL,
      version     INTEGER NOT NULL,
      event_type  TEXT NOT NULL CHECK (event_type IN
                   ('GENERATED','VALIDATED','PENDING_REVIEW','REVIEW_APPROVED',
                    'REVIEW_REJECTED','ACTIVATED','DISABLED','MARKED_STALE')),
      from_status TEXT,
      to_status   TEXT,
      event_at    TEXT NOT NULL,
      actor       TEXT NOT NULL CHECK (length(trim(actor)) > 0),
      actor_kind  TEXT NOT NULL CHECK (actor_kind IN ('machine','human')),
      reason_code TEXT CHECK (reason_code IS NULL OR reason_code IN
                   ('TEXTBOOK_MISMATCH','AMBIGUOUS_ANSWER','BAD_DISTRACTOR',
                    'OUT_OF_SCOPE','LOW_VALUE','OTHER')),
      note        TEXT,
      FOREIGN KEY (question_id, version)
        REFERENCES ai_question(question_id, version) ON DELETE RESTRICT ON UPDATE CASCADE,
      CHECK (event_type <> 'REVIEW_APPROVED' OR actor_kind = 'human'),
      CHECK (event_type <> 'REVIEW_REJECTED' OR actor_kind = 'human'),
      CHECK (event_type <> 'REVIEW_REJECTED' OR reason_code IS NOT NULL)
    )
"""


def _quote_norm_sql(col):
    """把 evidence_quote 归一化为可比较的文本（只做引号统一 + 转小写）。

    SQLite 没有通用正则，这里刻意保持简单：P1-04 的 EXACT 判定以
    Python 侧 exact_print_risk() 为权威语义，触发器做同一语义的保守近似。
    """
    return ("lower(replace(replace(replace(replace(%s,"
            " char(8220), '\"'), char(8221), '\"'),"
            " char(8217), char(39)), char(8216), char(39)))" % col)


# ------------------------------------------------------------------ A) EXACT 特殊复核触发器修正
EXACT_TRIGGER_V2 = """
    CREATE TRIGGER trg_validation_exact_trap
    AFTER INSERT ON question_validation
    WHEN NEW.answer_support_type = 'EXACT'
     AND EXISTS (
       SELECT 1
         FROM ai_question q
         JOIN question_evidence e
           ON e.question_id = q.question_id AND e.version = q.version
        WHERE q.question_id = NEW.question_id
          AND q.version = NEW.version
          AND q.options_json IS NOT NULL
          AND instr(%s, lower(q.correct_answer)) > 0
     )
    BEGIN
      UPDATE question_validation
         SET needs_human_review = 1
       WHERE question_id = NEW.question_id
         AND version = NEW.version
         AND validator_version = NEW.validator_version;
      UPDATE ai_question
         SET needs_human_review = 1,
             updated_at = NEW.validated_at
       WHERE question_id = NEW.question_id
         AND version = NEW.version;
    END
""" % _quote_norm_sql("e.evidence_quote")


def _strip_v1(name, items):
    """从 v1 的语句列表中剔除将要被 v2 替换的语句。"""
    keys = {"question_event": "CREATE TABLE question_event",
            "exact_trigger": "trg_validation_exact_trap"}[name]
    return [s for s in items if keys not in s]


DDL_V2 = _strip_v1("question_event", v1.DDL) + [QUESTION_EVENT_DDL_V2]
INDEXES_V2 = list(v1.INDEXES)
TRIGGERS_V2 = _strip_v1("exact_trigger", v1.TRIGGERS) + [EXACT_TRIGGER_V2]


def create_schema_v2(conn):
    """在空库上直接建出 v2 schema（供测试使用）。"""
    conn.execute("PRAGMA foreign_keys = ON")
    for stmt in DDL_V2:
        conn.execute(stmt)
    for stmt in INDEXES_V2:
        conn.execute(stmt)
    for stmt in TRIGGERS_V2:
        conn.execute(stmt)
    conn.execute("PRAGMA user_version = %d" % SCHEMA_VERSION)


# ------------------------------------------------------------------ 迁移（v1 库 → v2 库）
TMP_TABLE = "question_event__v2_tmp"

QUESTION_EVENT_DDL_V2_TMP = QUESTION_EVENT_DDL_V2.replace(
    "CREATE TABLE question_event (", "CREATE TABLE %s (" % TMP_TABLE)

EVENT_COLUMNS = ["event_id", "question_id", "version", "event_type", "from_status",
                 "to_status", "event_at", "actor", "actor_kind", "reason_code", "note"]


def migration_statements():
    """返回按顺序执行的迁移语句（调用方负责 foreign_keys 与事务）。"""
    cols = ", ".join(EVENT_COLUMNS)
    return [
        # 1) 先摘掉挂在旧表上的触发器与索引；
        #    ai_question 上的 lifecycle 触发器也引用了 question_event，必须先摘后恢复
        "DROP TRIGGER trg_question_event_no_update",
        "DROP TRIGGER trg_question_event_no_delete",
        "DROP TRIGGER trg_ai_question_active_requires_human_approval",
        "DROP INDEX idx_question_event_q",
        "DROP INDEX idx_question_event_type",
        # 2) 重建 question_event（枚举扩展），逐行原样复制
        QUESTION_EVENT_DDL_V2_TMP,
        "INSERT INTO %s (%s) SELECT %s FROM question_event" % (TMP_TABLE, cols, cols),
        "DROP TABLE question_event",
        "ALTER TABLE %s RENAME TO question_event" % TMP_TABLE,
        # 3) 恢复索引（与 v1 完全同名同列）
        "CREATE INDEX idx_question_event_q ON question_event(question_id, version, event_at)",
        "CREATE INDEX idx_question_event_type ON question_event(event_type, event_at)",
        # 4) 恢复 append-only 触发器（与 v1 语义一致）
        """
        CREATE TRIGGER trg_question_event_no_update
        BEFORE UPDATE ON question_event
        BEGIN
          SELECT RAISE(ABORT, 'question_event is append-only: UPDATE is forbidden');
        END
        """,
        """
        CREATE TRIGGER trg_question_event_no_delete
        BEFORE DELETE ON question_event
        BEGIN
          SELECT RAISE(ABORT, 'question_event is append-only: DELETE is forbidden');
        END
        """,
        # 5) 恢复 ai_question 的生命周期硬门槛触发器（与 v1 语义完全一致）
        """
        CREATE TRIGGER trg_ai_question_active_requires_human_approval
        BEFORE UPDATE OF lifecycle_status ON ai_question
        WHEN NEW.lifecycle_status = 'ACTIVE'
         AND NOT EXISTS (
           SELECT 1 FROM question_event e
            WHERE e.question_id = NEW.question_id
              AND e.version = NEW.version
              AND e.event_type = 'REVIEW_APPROVED'
              AND e.actor_kind = 'human'
         )
        BEGIN
          SELECT RAISE(ABORT, 'ACTIVE requires a human REVIEW_APPROVED event');
        END
        """,
        # 6) 替换 EXACT 特殊复核触发器
        "DROP TRIGGER trg_validation_exact_trap",
        EXACT_TRIGGER_V2,
        # 7) schema 版本
        "PRAGMA user_version = %d" % SCHEMA_VERSION,
    ]

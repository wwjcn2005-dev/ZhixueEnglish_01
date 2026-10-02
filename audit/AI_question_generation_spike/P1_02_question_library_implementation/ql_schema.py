"""P1-02 · AI Question Library 最小数据库 schema（6 表）。

只实现 P1-01 定义的 6 张核心表；不包含 prompt / model / reviewer / analytics 等表。
本模块只提供 DDL 与键计算函数，不包含任何业务写入逻辑，也不产生任何题目数据。
"""
import hashlib
import re
import sqlite3

SCHEMA_VERSION = 1

DDL = [
    # ---------------------------------------------------------------- 1) generation_run
    """
    CREATE TABLE generation_run (
      run_id                TEXT PRIMARY KEY,
      generation_scope_key  TEXT NOT NULL,
      textbook_id           TEXT NOT NULL,
      snapshot_id           TEXT,
      unit_id               TEXT,
      section_id            TEXT,
      activity_id           TEXT,
      model                 TEXT,
      prompt_version        TEXT,
      context_hash          TEXT,
      provider              TEXT,
      context_ref           TEXT,
      raw_response_ref      TEXT,
      requested_max         INTEGER CHECK (requested_max IS NULL OR requested_max >= 0),
      max_tokens            INTEGER CHECK (max_tokens IS NULL OR max_tokens > 0),
      finish_reason         TEXT,
      usage_json            TEXT CHECK (usage_json IS NULL OR json_valid(usage_json)),
      elapsed_ms            INTEGER CHECK (elapsed_ms IS NULL OR elapsed_ms >= 0),
      question_count        INTEGER NOT NULL DEFAULT 0 CHECK (question_count >= 0),
      status                TEXT NOT NULL DEFAULT 'OK'
                            CHECK (status IN ('OK','TRUNCATED','API_ERROR','INSUFFICIENT_EVIDENCE')),
      insufficient_evidence INTEGER NOT NULL DEFAULT 0 CHECK (insufficient_evidence IN (0,1)),
      error                 TEXT,
      note                  TEXT,
      generated_at          TEXT NOT NULL,
      CHECK (insufficient_evidence = 0 OR status = 'INSUFFICIENT_EVIDENCE')
    )
    """,
    # ---------------------------------------------------------------- 2) ai_question
    """
    CREATE TABLE ai_question (
      question_id          TEXT NOT NULL,
      version              INTEGER NOT NULL CHECK (version >= 1),
      question_type        TEXT NOT NULL
                           CHECK (question_type IN ('fill','vocab_choice','reading_choice','reading_judge')),
      question_text        TEXT NOT NULL CHECK (length(trim(question_text)) > 0),
      options_json         TEXT CHECK (options_json IS NULL OR json_valid(options_json)),
      correct_option       TEXT,
      correct_answer       TEXT NOT NULL CHECK (length(trim(correct_answer)) > 0),
      explanation          TEXT,
      difficulty           TEXT CHECK (difficulty IS NULL OR difficulty IN ('easy','medium')),
      textbook_id          TEXT NOT NULL,
      snapshot_id          TEXT,
      unit_id              TEXT NOT NULL,
      section_id           TEXT NOT NULL,
      activity_id          TEXT,
      page                 INTEGER CHECK (page IS NULL OR page > 0),
      generation_run_id    TEXT NOT NULL
                           REFERENCES generation_run(run_id) ON DELETE RESTRICT ON UPDATE CASCADE,
      generated_at         TEXT NOT NULL,
      question_fingerprint TEXT NOT NULL CHECK (length(question_fingerprint) = 64),
      lifecycle_status     TEXT NOT NULL
                           CHECK (lifecycle_status IN ('GENERATED','VALIDATED','PENDING_REVIEW',
                                                       'APPROVED','ACTIVE','REJECTED','DISABLED')),
      active               INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0,1)),
      disabled_reason      TEXT,
      stale                INTEGER NOT NULL DEFAULT 0 CHECK (stale IN (0,1)),
      stale_reason         TEXT CHECK (stale_reason IS NULL OR stale_reason IN
                                       ('EVIDENCE_CHANGED','PROMPT_CHANGED',
                                        'MODEL_CHANGED','VALIDATOR_CHANGED')),
      stale_since          TEXT,
      validator_version    TEXT,
      needs_human_review   INTEGER NOT NULL DEFAULT 0 CHECK (needs_human_review IN (0,1)),
      created_at           TEXT NOT NULL,
      updated_at           TEXT NOT NULL,
      PRIMARY KEY (question_id, version),
      CHECK ((lifecycle_status = 'ACTIVE' AND active = 1)
             OR (lifecycle_status <> 'ACTIVE' AND active = 0)),
      CHECK (stale = 1 OR stale_reason IS NULL),
      CHECK (stale = 0 OR stale_reason IS NOT NULL)
    )
    """,
    # ---------------------------------------------------------------- 3) question_evidence
    """
    CREATE TABLE question_evidence (
      question_id       TEXT NOT NULL,
      version           INTEGER NOT NULL,
      ordinal           INTEGER NOT NULL CHECK (ordinal >= 1),
      evidence_block_id TEXT NOT NULL CHECK (length(trim(evidence_block_id)) > 0),
      evidence_quote    TEXT NOT NULL CHECK (length(trim(evidence_quote)) > 0),
      is_primary        INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
      PRIMARY KEY (question_id, version, ordinal),
      FOREIGN KEY (question_id, version)
        REFERENCES ai_question(question_id, version) ON DELETE CASCADE ON UPDATE CASCADE
    )
    """,
    # ---------------------------------------------------------------- 4) question_learning_object
    """
    CREATE TABLE question_learning_object (
      question_id TEXT NOT NULL,
      version     INTEGER NOT NULL,
      item_id     TEXT NOT NULL CHECK (length(trim(item_id)) > 0),
      is_primary  INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
      PRIMARY KEY (question_id, version, item_id),
      FOREIGN KEY (question_id, version)
        REFERENCES ai_question(question_id, version) ON DELETE CASCADE ON UPDATE CASCADE,
      CHECK (item_id NOT LIKE 'AIQ:%' AND item_id NOT LIKE 'AIRUN:%')
    )
    """,
    # ---------------------------------------------------------------- 5) question_validation
    """
    CREATE TABLE question_validation (
      question_id              TEXT NOT NULL,
      version                  INTEGER NOT NULL,
      validator_version        TEXT NOT NULL CHECK (length(trim(validator_version)) > 0),
      validation_result        TEXT NOT NULL CHECK (validation_result IN ('PASS','FAIL')),
      validated_at             TEXT NOT NULL,
      answer_support_type      TEXT NOT NULL CHECK (answer_support_type IN
                                 ('EXACT','VERIFIABLE_REFERENCE','VERIFIABLE_REPHRASE','UNSUPPORTED')),
      checks_json              TEXT CHECK (checks_json IS NULL OR json_valid(checks_json)),
      out_of_scope_tokens_json TEXT CHECK (out_of_scope_tokens_json IS NULL
                                           OR json_valid(out_of_scope_tokens_json)),
      needs_human_review       INTEGER NOT NULL DEFAULT 0 CHECK (needs_human_review IN (0,1)),
      note                     TEXT,
      PRIMARY KEY (question_id, version, validator_version),
      FOREIGN KEY (question_id, version)
        REFERENCES ai_question(question_id, version) ON DELETE CASCADE ON UPDATE CASCADE,
      CHECK (validation_result <> 'PASS'
             OR answer_support_type IN ('EXACT','VERIFIABLE_REFERENCE','VERIFIABLE_REPHRASE'))
    )
    """,
    # ---------------------------------------------------------------- 6) question_event
    """
    CREATE TABLE question_event (
      event_id    TEXT PRIMARY KEY,
      question_id TEXT NOT NULL,
      version     INTEGER NOT NULL,
      event_type  TEXT NOT NULL CHECK (event_type IN
                   ('VALIDATED','REVIEW_APPROVED','REVIEW_REJECTED',
                    'ACTIVATED','DISABLED','MARKED_STALE')),
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
    """,
]

# -------------------------------------------------------------------- 索引与唯一约束
INDEXES = [
    "CREATE INDEX idx_generation_run_scope ON generation_run(generation_scope_key)",
    "CREATE INDEX idx_generation_run_target ON generation_run(section_id, activity_id)",
    "CREATE INDEX idx_generation_run_time ON generation_run(generated_at)",
    # 同一指纹只允许存在一条题目记录（T9 / T13 的结构性保证）
    "CREATE UNIQUE INDEX uq_ai_question_fingerprint ON ai_question(question_fingerprint)",
    "CREATE INDEX idx_ai_question_scope ON ai_question(section_id, activity_id, lifecycle_status, stale)",
    "CREATE INDEX idx_ai_question_lifecycle ON ai_question(lifecycle_status)",
    "CREATE INDEX idx_ai_question_stale ON ai_question(stale, stale_reason)",
    "CREATE INDEX idx_ai_question_run ON ai_question(generation_run_id)",
    "CREATE INDEX idx_question_evidence_block ON question_evidence(evidence_block_id)",
    "CREATE INDEX idx_qlo_item ON question_learning_object(item_id)",
    "CREATE INDEX idx_validation_result ON question_validation(validation_result)",
    "CREATE INDEX idx_validation_support ON question_validation(answer_support_type)",
    "CREATE INDEX idx_question_event_q ON question_event(question_id, version, event_at)",
    "CREATE INDEX idx_question_event_type ON question_event(event_type, event_at)",
]

TABLE_NAMES = ["generation_run", "ai_question", "question_evidence",
               "question_learning_object", "question_validation", "question_event"]

# -------------------------------------------------------------------- 触发器
TRIGGERS = [
    # 生命周期事件是 append-only：不允许 UPDATE，也不允许 DELETE
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
    # 题目不可删除（历史必须可追溯；下线用 DISABLED）
    """
    CREATE TRIGGER trg_ai_question_no_delete
    BEFORE DELETE ON ai_question
    BEGIN
      SELECT RAISE(ABORT, 'ai_question rows may not be deleted; use DISABLED instead');
    END
    """,
    # 硬门槛一：新插入的题不允许直接是 ACTIVE
    """
    CREATE TRIGGER trg_ai_question_insert_active_forbidden
    BEFORE INSERT ON ai_question
    WHEN NEW.lifecycle_status = 'ACTIVE'
    BEGIN
      SELECT RAISE(ABORT, 'validator PASS is not enough: a question cannot be inserted as ACTIVE');
    END
    """,
    # 硬门槛二：只有存在“人工 REVIEW_APPROVED 事件”才允许转为 ACTIVE
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
    # EXACT 陷阱：answer 文本同样出现在题干/选项中时，强制置 needs_human_review = 1
    """
    CREATE TRIGGER trg_validation_exact_trap
    AFTER INSERT ON question_validation
    WHEN NEW.answer_support_type = 'EXACT'
     AND EXISTS (
       SELECT 1 FROM ai_question q
        WHERE q.question_id = NEW.question_id
          AND q.version = NEW.version
          AND ( instr(lower(q.question_text), lower(q.correct_answer)) > 0
                OR ( q.options_json IS NOT NULL
                     AND instr(lower(q.options_json), lower(q.correct_answer)) > 0 ) )
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
    """,
]


def create_schema(conn: sqlite3.Connection) -> None:
    """在给定连接上创建 6 表 + 索引 + 触发器（不写入任何题目数据）。"""
    conn.execute("PRAGMA foreign_keys = ON")
    for stmt in DDL:
        conn.execute(stmt)
    for stmt in INDEXES:
        conn.execute(stmt)
    for stmt in TRIGGERS:
        conn.execute(stmt)
    conn.execute("PRAGMA user_version = %d" % SCHEMA_VERSION)


# -------------------------------------------------------------------- 键计算（与 P1-01 修正方案一致）
_WS = re.compile(r"\s+")


def norm_text(text: str) -> str:
    """归一化：去首尾空白、折叠空白、统一引号、转小写。"""
    s = (text or "")
    for a, b in (("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'), ("\u201d", '"')):
        s = s.replace(a, b)
    return _WS.sub(" ", s).strip().lower()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def generation_scope_key(section_id: str, activity_id, prompt_version: str,
                         context_hash: str) -> str:
    """批次级复用键：hash(section_id, activity_id, prompt_version, context_hash)。

    刻意不含 question_type —— 一次调用会同时产出多种题型。
    """
    payload = "\u0001".join([norm_text(section_id), norm_text(activity_id or ""),
                             norm_text(prompt_version), norm_text(context_hash)])
    return _sha256(payload)


def question_fingerprint(section_id: str, activity_id, question_type: str,
                         question_text: str, evidence_quote: str) -> str:
    """题级指纹：hash(section_id, activity_id, question_type,
    norm(question_text), norm(evidence_quote))。

    刻意不含 prompt_version / model —— 被驳回的题不得换提示词换马甲重进。
    """
    payload = "\u0001".join([norm_text(section_id), norm_text(activity_id or ""),
                             norm_text(question_type), norm_text(question_text),
                             norm_text(evidence_quote)])
    return _sha256(payload)

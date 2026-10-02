-- P1-09-A 设计草案（DESIGN ONLY，未执行、未接入 question_library.db）
-- 目的：为"AI 英语质量复核"预留一个纯增量、append-only 的落点。
-- 原则：
--   1) 只新增一张表 + 两个 append-only 触发器；不修改任何既有表、列、触发器、索引；
--   2) 不新增 event_type，AI 复核不得进入 question_event（否则会与人工审核事件混淆）；
--   3) 不改动 lifecycle 语义：PENDING_REVIEW -> human REVIEW_APPROVED -> APPROVED
--      -> explicit ACTIVATED -> ACTIVE 完全不变；
--   4) suggested_decision 只是建议，任何 CHECK 都不允许它写成 APPROVED / ACTIVE。

PRAGMA user_version = 3;   -- 版本推进示意；本轮不执行

CREATE TABLE question_ai_review (
      review_id            TEXT NOT NULL,          -- 例如 AIRV:<review_run_id>:<question_fingerprint12>
      question_id          TEXT NOT NULL,
      version              INTEGER NOT NULL,
      review_run_id        TEXT NOT NULL,          -- 一次批量复核的账目 ID
      reviewer_model       TEXT NOT NULL,
      reviewer_provider    TEXT,
      prompt_version       TEXT NOT NULL,          -- 复核提示词版本（与生成 prompt 分开编号）
      review_context_hash  TEXT NOT NULL,          -- 复核时实际看到的输入指纹
      reviewed_at          TEXT NOT NULL,

      suggested_decision   TEXT NOT NULL CHECK (suggested_decision IN
                             ('suggest_approve','suggest_fix','suggest_reject')),
      english_correct      TEXT NOT NULL CHECK (english_correct IN ('ok','issue')),
      answer_unique        TEXT NOT NULL CHECK (answer_unique IN ('unique','ambiguous')),
      naturalness          TEXT NOT NULL CHECK (naturalness IN ('natural','awkward')),
      learning_value       TEXT NOT NULL CHECK (learning_value IN ('high','medium','low')),
      distractor_quality   TEXT NOT NULL CHECK (distractor_quality IN
                             ('good','acceptable','poor','n/a')),
      grade_fit            TEXT NOT NULL CHECK (grade_fit IN ('ok','too_easy','too_hard')),
      short_reason         TEXT NOT NULL CHECK (length(trim(short_reason)) > 0),
      confidence           REAL CHECK (confidence IS NULL
                                       OR (confidence >= 0 AND confidence <= 1)),

      PRIMARY KEY (review_id),
      UNIQUE (question_id, version, review_run_id),
      FOREIGN KEY (question_id, version)
        REFERENCES ai_question(question_id, version)
        ON DELETE RESTRICT ON UPDATE CASCADE
    );

-- 说明：n/a 只允许出现在非选择题上。SQLite 的 CHECK 不允许子查询，
--       因此这条约束必须用触发器表达，而不是 CHECK。
CREATE TRIGGER trg_ai_review_distractor_na_only_nonselectable
    BEFORE INSERT ON question_ai_review
    WHEN NEW.distractor_quality = 'n/a'
     AND (SELECT question_type FROM ai_question q
           WHERE q.question_id = NEW.question_id AND q.version = NEW.version)
         IN ('vocab_choice','reading_choice')
    BEGIN
      SELECT RAISE(ABORT, 'selectable question must report distractor_quality');
    END;

CREATE TRIGGER trg_ai_review_no_update
    BEFORE UPDATE ON question_ai_review
    BEGIN
      SELECT RAISE(ABORT, 'question_ai_review is append-only: UPDATE is forbidden');
    END;

CREATE TRIGGER trg_ai_review_no_delete
    BEFORE DELETE ON question_ai_review
    BEGIN
      SELECT RAISE(ABORT, 'question_ai_review is append-only: DELETE is forbidden');
    END;

-- 可选：与 generation_run 同构的复核账目表（第一阶段可以先用内联 provenance 列，不建此表）
-- CREATE TABLE ai_review_run (
--       review_run_id       TEXT PRIMARY KEY,
--       scope_key           TEXT NOT NULL,
--       section_id          TEXT,
--       reviewer_model      TEXT NOT NULL,
--       prompt_version      TEXT NOT NULL,
--       review_context_hash TEXT NOT NULL,
--       question_count      INTEGER NOT NULL DEFAULT 0,
--       requested_max       INTEGER,
--       finish_reason       TEXT,
--       usage_json          TEXT CHECK (usage_json IS NULL OR json_valid(usage_json)),
--       elapsed_ms          INTEGER,
--       status              TEXT NOT NULL CHECK (status IN ('OK','TRUNCATED','API_ERROR')),
--       reviewed_at         TEXT NOT NULL
--     );

-- 不升级 schema 时的等价落点（P1-09-B 推荐先用这条）：
--   structured/ai/quality_review/<review_run_id>.json
--   { "review_run_id": ..., "reviewer_model": ..., "prompt_version": ...,
--     "review_context_hash": ..., "reviewed_at": ...,
--     "reviews": [ { ...与 question_ai_review 同构的字段...,
--                    "question_fingerprint": "<64 hex>" } ] }
--   读取方必须校验 question_fingerprint 与 DB 一致，避免"意见挂到错误题目上"。
--   该结构刻意与 question_ai_review 同构：未来升级 v3 时是"搬进表"，不是重新设计。

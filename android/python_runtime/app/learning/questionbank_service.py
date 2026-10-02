#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""本地教材题库 · 只读查询服务（questionbank.db）

题库：`structured/questionbank/questionbank.db`（由 `builder/build_questionbank_v01.py` 确定性生成，AI 调用 = 0）
学习证据：仍在 `structured/learning/learning.db`，本模块**不读写** learning.db。

对外提供后续 APP / 出题层需要的查询：
  * 按 Unit / domain / question_type 取题
  * 取题目的教材 evidence（question_asset）
  * 判断是否可自动评分（answer_status=RELIABLE 且 answer_kind 属于确定性类型）
  * 待 AI 补足池（supplement_task）
  * 只读完整性自检
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DB_PATH = BASE / "structured" / "questionbank" / "questionbank.db"

RELIABLE = "RELIABLE"
NO_RELIABLE_SOURCE = "NO_RELIABLE_SOURCE"
DETERMINISTIC_KINDS = ("option_key", "exact", "normalized", "check_items")
AI_TASK_STATUS = "AI_SUPPLEMENT_REQUIRED"


def connect(path=None) -> sqlite3.Connection:
    """只读连接（mode=ro）。"""
    conn = sqlite3.connect("file:%s?mode=ro" % Path(path or DB_PATH).as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn, sql, args=()) -> list:
    return [dict(r) for r in conn.execute(sql, args)]


def summary(path=None) -> dict:
    conn = connect(path)
    try:
        out = {"questions": conn.execute("SELECT COUNT(*) FROM question").fetchone()[0]}
        for col, key in (("origin", "by_origin"), ("domain", "by_domain"),
                         ("question_type", "by_type"), ("answer_status", "by_answer_status"),
                         ("unit_code", "by_unit")):
            out[key] = {r[0]: r[1] for r in conn.execute(
                "SELECT %s, COUNT(*) FROM question GROUP BY %s ORDER BY 2 DESC" % (col, col))}
        out["auto_gradeable"] = conn.execute(
            "SELECT COUNT(*) FROM question WHERE answer_status=? AND answer_kind IN (%s)"
            % ",".join("?" * len(DETERMINISTIC_KINDS)),
            (RELIABLE,) + DETERMINISTIC_KINDS).fetchone()[0]
        out["supplement_tasks"] = conn.execute("SELECT COUNT(*) FROM supplement_task").fetchone()[0]
        out["generation_runs"] = _rows(conn, "SELECT * FROM generation_run ORDER BY started_at")
        return out
    finally:
        conn.close()


def questions_for_unit(unit_code: str, domain=None, question_type=None,
                       auto_gradeable_only=False, limit=None, path=None) -> list:
    sql = "SELECT * FROM question WHERE unit_code=?"
    args = [unit_code]
    if domain:
        sql += " AND domain=?"
        args.append(domain)
    if question_type:
        sql += " AND question_type=?"
        args.append(question_type)
    if auto_gradeable_only:
        sql += " AND answer_status=? AND answer_kind IN (%s)" % ",".join("?" * len(DETERMINISTIC_KINDS))
        args.append(RELIABLE)
        args.extend(DETERMINISTIC_KINDS)
    sql += " ORDER BY question_type, question_id"
    if limit:
        sql += " LIMIT %d" % int(limit)
    conn = connect(path)
    try:
        return [_decode(r) for r in _rows(conn, sql, tuple(args))]
    finally:
        conn.close()


def _decode(row: dict) -> dict:
    for field in ("prompt_json", "options_json", "answer_json"):
        key = field.replace("_json", "")
        row[key] = None
        if row.get(field):
            try:
                row[key] = json.loads(row[field])
            except ValueError:
                row[key] = None
    return row


def get_question(question_id: str, path=None) -> dict:
    conn = connect(path)
    try:
        rows = _rows(conn, "SELECT * FROM question WHERE question_id=?", (question_id,))
        if not rows:
            return {}
        q = _decode(rows[0])
        q["assets"] = _rows(conn, "SELECT asset_kind, asset_id, role, evidence_quote "
                                  "FROM question_asset WHERE question_id=?", (question_id,))
        return q
    finally:
        conn.close()


def evidence_for(question_id: str, path=None) -> list:
    conn = connect(path)
    try:
        return _rows(conn, "SELECT asset_kind, asset_id, role, evidence_quote "
                           "FROM question_asset WHERE question_id=? ORDER BY role", (question_id,))
    finally:
        conn.close()


def can_auto_grade(question) -> bool:
    """能否由确定性规则判分（题库内的答案与规则必须齐全）。"""
    if isinstance(question, str):
        question = get_question(question)
    if not question or question.get("answer_status") != RELIABLE:
        return False
    if question.get("answer_kind") not in DETERMINISTIC_KINDS:
        return False
    answer = question.get("answer")
    if question.get("answer_kind") == "option_key":
        options = question.get("options") or []
        return bool(answer and answer.get("key") and any(o.get("key") == answer.get("key")
                                                        for o in options))
    return bool(answer and (answer.get("text") or answer.get("items")))


def supplement_pool(status=AI_TASK_STATUS, path=None) -> list:
    conn = connect(path)
    try:
        return _rows(conn, "SELECT * FROM supplement_task WHERE status=? ORDER BY kind, unit_code", (status,))
    finally:
        conn.close()


def integrity_report(path=None) -> dict:
    """只读自检：题型/答案/证据/引用/重复。返回 {:ok, :problems, :summary}。"""
    conn = connect(path)
    problems = []
    try:
        qids = [r[0] for r in conn.execute("SELECT question_id FROM question")]
        if not qids:
            problems.append("题库为空")
        dup = conn.execute("SELECT content_hash, COUNT(*) c FROM question GROUP BY content_hash "
                           "HAVING c > 1").fetchall()
        if dup:
            problems.append("存在重复 content_hash：%d 组" % len(dup))
        missing_ev = conn.execute(
            "SELECT COUNT(*) FROM question q WHERE NOT EXISTS (SELECT 1 FROM question_asset a "
            "WHERE a.question_id=q.question_id AND a.role='primary')").fetchone()[0]
        if missing_ev:
            problems.append("缺 primary evidence：%d 题" % missing_ev)
        missing_ans = conn.execute(
            "SELECT COUNT(*) FROM question WHERE answer_status=? AND (answer_json IS NULL "
            "OR answer_json IN ('', 'null'))", (RELIABLE,)).fetchone()[0]
        if missing_ans:
            problems.append("RELIABLE 但无答案：%d 题" % missing_ans)
        fake = conn.execute("SELECT COUNT(*) FROM question WHERE answer_status<>? AND answer_json "
                            "IS NOT NULL", (RELIABLE,)).fetchone()[0]
        if fake:
            problems.append("无可靠来源却有答案（伪造风险）：%d 题" % fake)
        # P4 起：允许 AI_GENERATED 题目进入正式题库，但必须可追溯（教材/音频证据 + AI 来源证据），
        # 否则视为无证据的 AI 内容，一律拦截。
        bad_ai = conn.execute(
            "SELECT COUNT(*) FROM question q WHERE q.origin='AI_GENERATED' AND ("
            " NOT EXISTS (SELECT 1 FROM question_asset a WHERE a.question_id=q.question_id "
            "             AND a.role IN ('primary','audio_source'))"
            " OR NOT EXISTS (SELECT 1 FROM question_asset a WHERE a.question_id=q.question_id "
            "                AND a.asset_kind IN ('ai_distractor_cache','ai_generation_run')))"
        ).fetchone()[0]
        if bad_ai:
            problems.append("AI_GENERATED 题缺少教材证据或 AI 来源证据：%d 题" % bad_ai)
        return {"ok": not problems, "problems": problems, "summary": summary(path)}
    finally:
        conn.close()

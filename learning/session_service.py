#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-07-C1 最小学习会话服务（LearningSession）

职责（严格限定）：
  Session 生命周期 + Session 与 Task 的组织关系。

链路：
  教材资源 → 调用方主动选择 → LearningSession → LearningTask → TaskItem
           → LearningRecord（经现有 record_learning_event）→ MasteryState →（C2-A）当前错误/薄弱池

复用现有实现（不复制逻辑）：
  - learning/learning_service.py：create_task / get_task / list_task_items / record_learning_event / get_learner …
  - learning/resource_pool_service.py：当前错误/薄弱池（只读，闭环验证用）

P1-04 已定义的 LearningSession 逻辑字段（严格复用其语义与 entry_point 枚举）：
  session_id / learner_id / started_at / ended_at / entry_point
本实现**唯一新增**的字段是 `task_id`（P1-07-C1 §五 要求的 Session → Task 关联）；
entry_point 枚举不扩展：unit / section / activity / vocabulary / listening / reading。

本模块不实现：UI / Activity / Question / 题库 / 判题 / AI / 推荐 / 复习排程 / Mastery 算法。
"""

from __future__ import annotations

import os

import sqlite3
from pathlib import Path

import learning_service as svc

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
DEFAULT_LEARNING_DB = BASE / "structured" / "learning" / "learning.db"
DEFAULT_CONTENTPACK_DB = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"

#: P1-04 §23 已冻结的 entry_point 枚举（不新增）
ENTRY_POINTS = ("unit", "section", "activity", "vocabulary", "listening", "reading")
#: 会话默认创建 learn 任务（review 由孩子主动发起，属 B1.14 冻结的既有规则）
DEFAULT_TASK_KIND = "learn"


def connect_learning_db(path=DEFAULT_LEARNING_DB) -> sqlite3.Connection:
    """打开 learning.db（与 C1 一致：显式事务、foreign_keys=ON）。"""
    return svc.connect_learning_db(path)


# --------------------------------------------------------------------------
# 内部校验
# --------------------------------------------------------------------------

def _owned_session(conn, session_id, learner_id=None) -> dict:
    row = conn.execute("SELECT * FROM learning_session WHERE session_id=?", (session_id,)).fetchone()
    if row is None:
        raise svc.NotFoundError("Session 不存在：%s" % session_id)
    session = dict(row)
    if learner_id is not None and session["learner_id"] != learner_id:
        raise svc.ValidationError(
            "Session 不属于该 Learner（session.learner_id=%s）" % session["learner_id"])
    return session


def _resolve_textbook_for_items(cp, item_ids, textbook_id):
    """textbook_id 判定：未提供则从教材库解析；提供则必须与所有 item 一致（§十.5）。"""
    resolved = textbook_id
    for item_id in item_ids:
        row = cp.execute("SELECT textbook_id FROM learning_item WHERE item_id=?", (item_id,)).fetchone()
        if row is None:
            raise svc.NotFoundError("item_id 不存在于当前教材库：%s" % item_id)
        if resolved is None:
            resolved = row["textbook_id"]
        elif row["textbook_id"] != resolved:
            raise svc.ValidationError(
                "textbook_id(%s) 与 item(%s) 所属教材(%s) 不匹配" % (resolved, item_id, row["textbook_id"]))
    return resolved


# --------------------------------------------------------------------------
# Session 服务
# --------------------------------------------------------------------------

def create_learning_session(conn, learner_id, entry_point, item_ids, textbook_id=None,
                            task_kind=DEFAULT_TASK_KIND, session_id=None, started_at=None,
                            contentpack_path=DEFAULT_CONTENTPACK_DB, task_id=None) -> dict:
    """创建学习会话：Session + 对应 Task/TaskItem。

    由调用方主动发起并提供 item_ids（不自动选题、不自动从资源池生成内容）。
    一致性：先经现有 create_task() 创建 Task（其自身为独立事务），再插入 Session；
    若 Session 插入失败，则执行补偿清理（删除本次新建的、且尚无任何 Record 的 Task 与 TaskItem），
    保证不留下孤立 Session 或孤立 Task（不重构既有 create_task 的事务实现）。
    """
    if entry_point not in ENTRY_POINTS:
        raise svc.ValidationError("entry_point 必须是 %s 之一" % (ENTRY_POINTS,))
    if not item_ids or not isinstance(item_ids, (list, tuple)):
        raise svc.ValidationError("创建学习会话至少需要 1 个 item_id")
    if task_kind not in svc.TASK_KINDS:
        raise svc.ValidationError("task_kind 必须是 %s 之一" % (svc.TASK_KINDS,))

    svc.get_learner(conn, learner_id)                       # learner 必须存在

    cp = svc.connect_contentpack_db(contentpack_path)
    try:
        resolved_textbook = _resolve_textbook_for_items(cp, list(item_ids), textbook_id)
    finally:
        cp.close()

    task = svc.create_task(conn, learner_id, task_kind, list(item_ids), resolved_textbook,
                           task_id=task_id, created_at=started_at)

    sid = session_id or svc.new_id("S")
    ts = started_at or svc.now_iso()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO learning_session(session_id, learner_id, started_at, ended_at, entry_point, task_id) "
            "VALUES(?,?,?,NULL,?,?)", (sid, learner_id, ts, entry_point, task["task_id"]))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        _compensate_task(conn, task["task_id"])
        raise
    return get_learning_session(conn, sid)


def _compensate_task(conn, task_id):
    """补偿清理：仅当该 Task 尚无任何 LearningRecord 时，删除其 TaskItem 与 Task 本身。"""
    try:
        conn.execute("BEGIN IMMEDIATE")
        records = conn.execute("SELECT COUNT(*) FROM learning_record WHERE task_id=?",
                               (task_id,)).fetchone()[0]
        if records == 0:
            conn.execute("DELETE FROM task_item WHERE task_id=?", (task_id,))
            conn.execute("DELETE FROM learning_task WHERE task_id=?", (task_id,))
            conn.execute("COMMIT")
        else:
            conn.execute("ROLLBACK")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass


def get_learning_session(conn, session_id, learner_id=None) -> dict:
    return _owned_session(conn, session_id, learner_id)


def list_learning_sessions(conn, learner_id) -> list:
    rows = conn.execute(
        "SELECT * FROM learning_session WHERE learner_id=? ORDER BY started_at, session_id",
        (learner_id,)).fetchall()
    return [dict(r) for r in rows]


def end_learning_session(conn, session_id, learner_id=None, ended_at=None) -> dict:
    session = _owned_session(conn, session_id, learner_id)
    if session["ended_at"] is not None:
        raise svc.ConflictError("Session 已结束：%s（ended_at=%s）" % (session_id, session["ended_at"]))
    ts = ended_at or svc.now_iso()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE learning_session SET ended_at=? WHERE session_id=?", (ts, session_id))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return get_learning_session(conn, session_id, learner_id)


def get_session_task(conn, session_id, learner_id=None) -> dict:
    session = _owned_session(conn, session_id, learner_id)
    return svc.get_task(conn, session["task_id"])


def list_session_items(conn, session_id, learner_id=None) -> list:
    session = _owned_session(conn, session_id, learner_id)
    return svc.list_task_items(conn, session["task_id"])


def record_session_event(conn, session_id, item_id, activity_type, result=None, response_raw=None,
                         hints_used=0, snapshot_id=None, created_at=None, learner_id=None,
                         contentpack_path=DEFAULT_CONTENTPACK_DB) -> dict:
    """会话内记录一次学习行为：**完全委托**现有 record_learning_event()（不复制任何校验/写入逻辑）。"""
    session = _owned_session(conn, session_id, learner_id)
    return svc.record_learning_event(conn, session["learner_id"], session["task_id"], item_id,
                                     activity_type, result=result, response_raw=response_raw,
                                     hints_used=hints_used, snapshot_id=snapshot_id,
                                     created_at=created_at, contentpack_path=contentpack_path)

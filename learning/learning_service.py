#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-06-C1 学习层最小业务服务（Learning Layer minimal service）

范围（严格按 B1.12 / B1.14 / B1.15 冻结设计）：

    Learner → LearningTask → TaskItem → LearningRecord → MasteryState

硬约束：
  1. 教材库（contentpack v5）**只读**：本模块绝不写入 contentpack
  2. 学习数据只写 learning.db；跨库字段（item_id / goal_id / textbook_id / snapshot_id）仅逻辑引用
  3. LearningRecord append-only：只提供插入，不提供 update / delete
  4. 一次学习事件 = 一个事务：INSERT learning_record + UPSERT mastery_state，失败整体回滚
  5. 不实现 Mastery 算法（不改变 mastery_level 的升级/降级规则）、不实现 Review 算法
  6. AI 调用 = 0（本模块不导入任何网络/AI 库，无任何外部调用）
  7. 不新增表、不新增字段、不修改 Schema

使用：
    from learning_service import connect_learning_db, create_learner, create_task, ...
"""

from __future__ import annotations

import os

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
DEFAULT_LEARNING_DB = BASE / "structured" / "learning" / "learning.db"
DEFAULT_CONTENTPACK_DB = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"

# P1-06-B1.15 §19 冻结的 9 种学习行为（保持不变、不删除、不改变语义）
ACTIVITY_TYPES = ("recognize", "read", "understand", "listen", "repeat",
                  "spell", "substitute", "produce", "review")
# P1-08-C1 §六 追加的最小学习行为（**仅新增**；既有 9 值继续有效）
BEHAVIOR_EXTENSION = ("study", "practice")
ACTIVITY_TYPES = ACTIVITY_TYPES + BEHAVIOR_EXTENSION
RESULTS = ("correct", "incorrect", "partial", "done", "skipped")
EVIDENCE_RESULTS = ("correct", "incorrect", "partial", "done")   # skipped / NULL 不计入
TASK_KINDS = ("learn", "review")
TASK_STATUSES = ("active", "completed", "dropped")
LEARNER_STATUSES = ("active", "inactive")
MASTERY_LEVELS = ("unknown", "learning", "familiar", "stable")


class LearningServiceError(Exception):
    """业务服务错误基类。"""


class ValidationError(LearningServiceError):
    """输入或业务规则校验失败（不写库）。"""


class NotFoundError(LearningServiceError):
    """引用对象不存在。"""


class ConflictError(LearningServiceError):
    """状态冲突（如任务已 completed / dropped）。"""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return "%s%s" % (prefix, uuid.uuid4().hex.upper())


def connect_learning_db(path=DEFAULT_LEARNING_DB) -> sqlite3.Connection:
    """打开 learning.db（自动提交模式；事务由本模块显式管理）。"""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.isolation_level = None          # 显式事务
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def connect_contentpack_db(path=DEFAULT_CONTENTPACK_DB) -> sqlite3.Connection:
    """打开教材库（**只读**）。"""
    conn = sqlite3.connect("file:%s?mode=ro" % Path(path).as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------------------------------
# 校验辅助
# --------------------------------------------------------------------------

def _require_text(value, field, allow_empty=False):
    if value is None or not isinstance(value, str):
        raise ValidationError("%s 必须为字符串" % field)
    if not allow_empty and not value.strip():
        raise ValidationError("%s 不能为空" % field)
    return value


def _contentpack_item(cp, item_id):
    row = cp.execute(
        "SELECT item_id, textbook_id FROM learning_item WHERE item_id=?", (item_id,)).fetchone()
    if row is None:
        raise NotFoundError("item_id 不存在于当前教材库：%s" % item_id)
    return row


def _active_snapshot(cp, textbook_id):
    row = cp.execute(
        "SELECT snapshot_id FROM parse_snapshot WHERE textbook_id=? AND is_active=1 "
        "ORDER BY build_finished_at DESC LIMIT 1", (textbook_id,)).fetchone()
    return row["snapshot_id"] if row else None


def _resolve_textbook(cp, textbook_id):
    row = cp.execute("SELECT textbook_id FROM textbook_edition WHERE textbook_id=?", (textbook_id,)).fetchone()
    if row is None:
        raise NotFoundError("textbook_id 不存在于当前教材库：%s" % textbook_id)
    return row["textbook_id"]


# --------------------------------------------------------------------------
# Learner
# --------------------------------------------------------------------------

def create_learner(conn, display_name, learner_id=None, created_at=None) -> dict:
    """创建 Learner（显式创建；不允许物理删除）。"""
    name = _require_text(display_name, "display_name").strip()
    lid = learner_id or new_id("L")
    ts = created_at or now_iso()
    try:
        conn.execute("BEGIN IMMEDIATE")
        exists = conn.execute("SELECT 1 FROM learner WHERE learner_id=?", (lid,)).fetchone()
        if exists:
            raise ConflictError("learner_id 已存在：%s" % lid)
        conn.execute(
            "INSERT INTO learner(learner_id, display_name, status, created_at, updated_at) "
            "VALUES(?,?,?,?,NULL)", (lid, name, "active", ts))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return get_learner(conn, lid)


def get_learner(conn, learner_id) -> dict:
    row = conn.execute("SELECT * FROM learner WHERE learner_id=?", (learner_id,)).fetchone()
    if row is None:
        raise NotFoundError("Learner 不存在：%s" % learner_id)
    return dict(row)


# --------------------------------------------------------------------------
# LearningTask
# --------------------------------------------------------------------------

def create_task(conn, learner_id, task_kind, item_ids, textbook_id, goal_id=None,
                title=None, task_id=None, created_at=None,
                contentpack_path=DEFAULT_CONTENTPACK_DB) -> dict:
    """创建任务（Task + ≥1 TaskItem，同一事务）。"""
    if task_kind not in TASK_KINDS:
        raise ValidationError("task_kind 必须是 %s 之一" % (TASK_KINDS,))
    if not item_ids or not isinstance(item_ids, (list, tuple)):
        raise ValidationError("创建任务至少需要 1 个 item_id")
    _require_text(textbook_id, "textbook_id")
    tid = task_id or new_id("T")
    ts = created_at or now_iso()

    cp = connect_contentpack_db(contentpack_path)
    try:
        _resolve_textbook(cp, textbook_id)
        for item_id in item_ids:
            _contentpack_item(cp, item_id)
    finally:
        cp.close()

    get_learner(conn, learner_id)          # learner 必须存在

    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO learning_task(task_id, learner_id, goal_id, task_kind, status, "
            "textbook_id, created_at, started_at, completed_at, title) "
            "VALUES(?,?,?,?,?,?,?,NULL,NULL,?)",
            (tid, learner_id, goal_id, task_kind, "active", textbook_id, ts, title))
        for i, item_id in enumerate(item_ids, start=1):
            conn.execute(
                "INSERT INTO task_item(task_id, item_id, ordinal, created_at) VALUES(?,?,?,?)",
                (tid, item_id, i, ts))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return get_task(conn, tid)


def get_task(conn, task_id) -> dict:
    row = conn.execute("SELECT * FROM learning_task WHERE task_id=?", (task_id,)).fetchone()
    if row is None:
        raise NotFoundError("Task 不存在：%s" % task_id)
    return dict(row)


def _set_task_status(conn, task_id, new_status, completed_at=None):
    task = get_task(conn, task_id)
    if task["status"] != "active":
        raise ConflictError("Task 当前状态为 %s，不能变更为 %s" % (task["status"], new_status))
    ts = completed_at or now_iso()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE learning_task SET status=?, completed_at=? WHERE task_id=?",
                     (new_status, ts, task_id))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return get_task(conn, task_id)


def complete_task(conn, task_id, completed_at=None) -> dict:
    """由明确的业务调用触发（不自动完成）。"""
    return _set_task_status(conn, task_id, "completed", completed_at)


def drop_task(conn, task_id, completed_at=None) -> dict:
    """孩子主动放弃该计划。"""
    return _set_task_status(conn, task_id, "dropped", completed_at)


# --------------------------------------------------------------------------
# TaskItem
# --------------------------------------------------------------------------

def add_task_item(conn, task_id, item_id, ordinal=None, created_at=None,
                  contentpack_path=DEFAULT_CONTENTPACK_DB) -> dict:
    task = get_task(conn, task_id)
    if task["status"] != "active":
        raise ConflictError("Task 状态为 %s，TaskItem 只读" % task["status"])
    cp = connect_contentpack_db(contentpack_path)
    try:
        _contentpack_item(cp, item_id)
    finally:
        cp.close()
    ts = created_at or now_iso()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO task_item(task_id, item_id, ordinal, created_at) VALUES(?,?,?,?)",
            (task_id, item_id, ordinal, ts))
        conn.execute("COMMIT")
    except sqlite3.IntegrityError as exc:
        conn.execute("ROLLBACK")
        raise ConflictError("TaskItem 已存在（%s, %s）：%s" % (task_id, item_id, exc))
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {"task_id": task_id, "item_id": item_id, "ordinal": ordinal, "created_at": ts}


def remove_task_item(conn, task_id, item_id) -> int:
    """删除 TaskItem（不影响历史 Record）。"""
    task = get_task(conn, task_id)
    if task["status"] != "active":
        raise ConflictError("Task 状态为 %s，TaskItem 只读" % task["status"])
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute("DELETE FROM task_item WHERE task_id=? AND item_id=?", (task_id, item_id))
        removed = cur.rowcount
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return removed


def list_task_items(conn, task_id) -> list:
    rows = conn.execute(
        "SELECT task_id, item_id, ordinal, created_at FROM task_item WHERE task_id=? "
        "ORDER BY (ordinal IS NULL), ordinal, item_id", (task_id,)).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# LearningRecord + MasteryState（核心：同一事务）
# --------------------------------------------------------------------------

def _validate_event(conn, cp, learner_id, task_id, item_id, activity_type, result,
                    response_raw, hints_used):
    if activity_type not in ACTIVITY_TYPES:
        raise ValidationError("activity_type 必须是 %s 之一" % (ACTIVITY_TYPES,))
    if result is not None and result not in RESULTS:
        raise ValidationError("result 必须是 %s 或 NULL" % (RESULTS,))
    if not isinstance(hints_used, int) or isinstance(hints_used, bool) or hints_used < 0:
        raise ValidationError("hints_used 必须为非负整数")
    if response_raw is not None and not isinstance(response_raw, str):
        raise ValidationError("response_raw 必须是字符串或 NULL（第一阶段仅文本）")

    get_learner(conn, learner_id)
    task = get_task(conn, task_id)
    if task["learner_id"] != learner_id:
        raise ValidationError("Task 不属于该 Learner")
    if task["status"] != "active":
        raise ConflictError("Task 状态为 %s，不允许继续产生学习记录" % task["status"])
    in_task = conn.execute(
        "SELECT 1 FROM task_item WHERE task_id=? AND item_id=?", (task_id, item_id)).fetchone()
    if not in_task:
        raise ValidationError("item_id 不是该 Task 的 TaskItem：%s" % item_id)
    text = _contentpack_item(cp, item_id)
    if text["textbook_id"] != task["textbook_id"]:
        raise ValidationError("item 所属教材与 Task 教材不一致")
    return task


def _next_attempt_no(conn, learner_id, task_id, item_id, activity_type) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(attempt_no), 0) AS m FROM learning_record "
        "WHERE learner_id=? AND task_id=? AND item_id=? AND activity_type=?",
        (learner_id, task_id, item_id, activity_type)).fetchone()
    return int(row["m"]) + 1


def _upsert_mastery(conn, learner_id, item_id, result, practiced_at):
    """按 B1.15 最小规则更新掌握状态派生缓存（不含任何算法）。"""
    counts = 1 if result in EVIDENCE_RESULTS else 0
    corrects = 1 if result == "correct" else 0
    row = conn.execute(
        "SELECT mastery_level, evidence_count, correct_count FROM mastery_state "
        "WHERE learner_id=? AND item_id=?", (learner_id, item_id)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO mastery_state(learner_id, item_id, mastery_level, evidence_count, "
            "correct_count, last_result, last_practiced_at, review_needed, updated_at) "
            "VALUES(?,?,'unknown',?,?,?,?,0,?)",
            (learner_id, item_id, counts, corrects,
             result if counts else None, practiced_at if counts else None, practiced_at))
        return
    if counts:
        conn.execute(
            "UPDATE mastery_state SET evidence_count=evidence_count+?, "
            "correct_count=correct_count+?, last_result=?, last_practiced_at=?, updated_at=? "
            "WHERE learner_id=? AND item_id=?",
            (counts, corrects, result, practiced_at, practiced_at, learner_id, item_id))
    # result 为 skipped / NULL：仅写 Record，不改变掌握派生字段（updated_at 也不变）


def record_learning_event(conn, learner_id, task_id, item_id, activity_type,
                          result=None, response_raw=None, hints_used=0,
                          snapshot_id=None, created_at=None,
                          contentpack_path=DEFAULT_CONTENTPACK_DB) -> dict:
    """记录一次真实学习行为：INSERT LearningRecord + UPSERT MasteryState（同一事务）。"""
    cp = connect_contentpack_db(contentpack_path)
    try:
        task = _validate_event(conn, cp, learner_id, task_id, item_id, activity_type,
                               result, response_raw, hints_used)
        snap = snapshot_id or _active_snapshot(cp, task["textbook_id"])
    finally:
        cp.close()

    # 空字符串不保存（第一阶段：无文本响应保存 NULL）
    raw = response_raw if (isinstance(response_raw, str) and response_raw.strip()) else None
    ts = created_at or now_iso()
    record_id = new_id("R")

    try:
        conn.execute("BEGIN IMMEDIATE")
        attempt_no = _next_attempt_no(conn, learner_id, task_id, item_id, activity_type)
        conn.execute(
            "INSERT INTO learning_record(record_id, learner_id, task_id, item_id, activity_type, "
            "result, response_raw, attempt_no, hints_used, textbook_id, snapshot_id, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (record_id, learner_id, task_id, item_id, activity_type, result, raw, attempt_no,
             hints_used, task["textbook_id"], snap, ts))
        _upsert_mastery(conn, learner_id, item_id, result, ts)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    return {"record": get_record(conn, record_id), "mastery": get_mastery(conn, learner_id, item_id)}


def get_record(conn, record_id) -> dict:
    row = conn.execute("SELECT * FROM learning_record WHERE record_id=?", (record_id,)).fetchone()
    if row is None:
        raise NotFoundError("Record 不存在：%s" % record_id)
    return dict(row)


def list_records(conn, learner_id=None, task_id=None, item_id=None) -> list:
    sql = "SELECT * FROM learning_record"
    where, params = [], []
    for field, value in (("learner_id", learner_id), ("task_id", task_id), ("item_id", item_id)):
        if value is not None:
            where.append("%s=?" % field)
            params.append(value)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at, record_id"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_mastery(conn, learner_id, item_id):
    row = conn.execute("SELECT * FROM mastery_state WHERE learner_id=? AND item_id=?",
                       (learner_id, item_id)).fetchone()
    return dict(row) if row else None


# 说明：本模块**不提供** update_record / delete_record（LearningRecord append-only）。

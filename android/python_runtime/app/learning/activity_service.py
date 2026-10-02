#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-07-C2 最小 LearningActivity 模型与消费接口（**只读派生投影，不新增数据库表**）

定位（P1-07-C2）：
    LearningTask → TaskItem → **LearningActivity** → 教材资源（contentpack，逻辑引用）

为什么本阶段**不新增表**：
  - `docs/P1-04_教材内容数据模型设计_V1.md` **没有定义学习层 LearningActivity**
    （P1-04 中的 `activity_id` 全部指教材结构 Activity：`<section_id>:A<number>`，属 L1 教材层）；
  - 唯一的 LearningActivity 线索是 `audit/P1-06-B1.10…md` 的设计提案（列为 P1），
    且 `audit/P1-06-B1.11…md` 明确“第一阶段无 Activity 实体 / 活动语义由 activity_type 表达”；
  - 因此按 P1-07-C2 §十二：**优先不要新增数据库表** → 本阶段把 LearningActivity 实现为
    由 `task_item` + contentpack 推导的**只读投影**（派生实体，不持久化）。

字段来源（不新造命名体系）：
  activity_id    ← 派生键 "<task_id>|<item_id>"（组合 TaskItem 主键；不持久化）
  activity_type  ← 复用 contentpack `learning_item.item_type` 取值
                   （vocabulary / phrase / sentence_pattern，与 C2-A 的 resource_type 同一命名）
  resource_id    ← 教材资源身份（= learning_item.item_id）
  resource_type  ← 同 activity_type（contentpack 既有取值）
  task_id / item_id / ordinal / textbook_id ← learning_task / task_item（既有列）

**P1-04 未定义、故本阶段未实现的字段**（在实施报告中明确列出，不猜测）：
  source_kind / prompt_ref / options_ref / answer_key_ref / status / 任何 AI / mastery /
  review / question / difficulty / score / UI 状态字段。

边界：
  - 只读：不写 learning.db、不写 contentpack、不复制教材正文（投影中不含任何正文/释义/音标）
  - 不调用 AI、不联网
"""

from __future__ import annotations

import os

from pathlib import Path

import learning_service as svc

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
DEFAULT_LEARNING_DB = BASE / "structured" / "learning" / "learning.db"
DEFAULT_CONTENTPACK_DB = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"

#: 第一阶段允许的教材学习资源类型（= contentpack learning_item.item_type 现有取值）
RESOURCE_TYPES = ("vocabulary", "phrase", "sentence_pattern")


def connect_learning_db(path=DEFAULT_LEARNING_DB):
    return svc.connect_learning_db(path)


def check_resource_type(resource_type):
    """校验资源类型合法（第一阶段仅三类教材资源；未来 Question/Reading/Listening 需另行评审）。"""
    if resource_type not in RESOURCE_TYPES:
        raise svc.ValidationError("resource_type 必须属于 %s 之一，当前为 %r"
                                  % (RESOURCE_TYPES, resource_type))
    return resource_type


def _activity_id(task_id, item_id) -> str:
    """派生活动键（不持久化）：TaskItem 主键的组合形式。"""
    return "%s|%s" % (task_id, item_id)


def resolve_activity(conn, task_id, item_id, contentpack_path=DEFAULT_CONTENTPACK_DB) -> dict:
    """根据 TaskItem（task_id + item_id）解析出该执行位置的 LearningActivity（只读投影）。

    校验（P1-07-C2 §十四）：
      1. TaskItem 存在
      2. 教材资源存在于 contentpack
      3. resource_type 合法（三类之一）
      4. resource_id 与 contentpack 资源一致（按 item_id 查得）
      5. textbook_id 一致（Task 与资源同教材）
      6. 不跨教材错误引用
      7. 不写 contentpack
      8. 不复制教材正文（投影不含任何正文/释义字段）
    """
    ti = conn.execute("SELECT task_id, item_id, ordinal FROM task_item WHERE task_id=? AND item_id=?",
                      (task_id, item_id)).fetchone()
    if ti is None:
        raise svc.NotFoundError("TaskItem 不存在：task_id=%s item_id=%s" % (task_id, item_id))

    task = svc.get_task(conn, task_id)

    cp = svc.connect_contentpack_db(contentpack_path)
    try:
        row = cp.execute("SELECT item_id, item_type, textbook_id FROM learning_item WHERE item_id=?",
                         (item_id,)).fetchone()
    finally:
        cp.close()
    if row is None:
        raise svc.NotFoundError("教材资源不存在于当前 contentpack：%s" % item_id)

    check_resource_type(row["item_type"])
    if row["textbook_id"] != task["textbook_id"]:
        raise svc.ValidationError(
            "跨教材引用：Task.textbook_id=%s，资源 textbook_id=%s（item_id=%s）"
            % (task["textbook_id"], row["textbook_id"], item_id))

    return {
        "activity_id": _activity_id(task_id, item_id),
        "activity_type": row["item_type"],          # 复用 contentpack item_type 取值
        "resource_id": row["item_id"],              # = learning_item.item_id（逻辑引用）
        "resource_type": row["item_type"],
        "item_id": row["item_id"],
        "task_id": task_id,
        "ordinal": ti["ordinal"],
        "textbook_id": task["textbook_id"],
        "task_status": task["status"],
        "trace": {"source": "contentpack.learning_item",
                  "contentpack": "v5",
                  "item_id": row["item_id"],
                  "textbook_id": row["textbook_id"]},
    }


def list_task_activities(conn, task_id, contentpack_path=DEFAULT_CONTENTPACK_DB) -> list:
    """列出该 Task 的全部 LearningActivity（按 TaskItem.ordinal 稳定排序）。"""
    items = svc.list_task_items(conn, task_id)
    return [resolve_activity(conn, task_id, it["item_id"], contentpack_path) for it in items]

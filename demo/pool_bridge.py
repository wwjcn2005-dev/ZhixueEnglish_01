#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""正式巩固池 → Demo 自主练习（只读衔接）

只做一件事：把正式 `resource_pool_service.list_current_issue_pool()` 的结果，
转换成本 Demo 已有的「巩固练习」入口行（`.ai-pt .plainrow`）；本阶段只接
`last_judged_activity_type == "produce"`（课文简答 / 表达）。

边界：
  * 只读：学习库一律 `mode=ro`，只调 `list_current_issue_pool`，不改规则、不写数据；
  * 教材信息不复制目录：Unit / Lesson / 题型一律来自既有 `web/exercises.get_exercise(item_id)`；
  * **Unit / Lesson 不取 pool 的 unit_code / section_key**（可能为 null），映射失败直接跳过；
  * 只读不建人：库里没有 active learner 就返回空列表（不创建学习者）。
"""

from __future__ import annotations

import os

import sys
from pathlib import Path

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
for _p in (str(BASE / "learning"), str(BASE / "web")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.dont_write_bytecode = True

import exercises as ex_mod               # noqa: E402  （只读教材目录）
import learning_service as svc           # noqa: E402
import resource_pool_service as pool     # noqa: E402

#: 正式库路径（测试可换成临时副本；正式运行只读）
LEARNING_DB = svc.DEFAULT_LEARNING_DB

#: 本阶段只接这一种行为（避免为其他 activity_type 猜页面映射）
SUPPORTED_ACTIVITY = "produce"
#: 一次最多展示几条正式巩固入口（沿用 Demo「少量入口」的展示习惯）
LIMIT = 3
#: 入口标题里的内容类型叫法（与现有 Demo 页面用词一致）
ENTRY_LABEL = "巩固练习 · 课文简答"
#: 结果 → 孩子看得懂的一行（沿用项目既有口径：incorrect=忘了、partial=有点模糊）
RESULT_TEXT = {"incorrect": "上次：忘了", "partial": "上次：有点模糊"}


def _learner_id(conn):
    """只读取现成 active learner（与 Demo 写入侧同一条选择规则：created_at 最早的一个）。"""
    row = conn.execute("SELECT learner_id FROM learner WHERE status='active' "
                       "ORDER BY created_at LIMIT 1").fetchone()
    return row["learner_id"] if row is not None else None


def _demo_unit(unit_code):
    """教材目录的 unit 文本（"Unit 1" / "Starter"）→ Demo unit（不猜：找不到就 None）。"""
    import server as demo_server                     # 延迟导入，避免与 server 循环导入
    want = (unit_code or "").strip().lower()
    for u in demo_server.units():
        if (u.get("unit_code") or "").strip().lower() == want:
            return u
    return None


def _demo_lesson(unit, section):
    """教材目录的 section 文本（"DEVELOPING_IDEAS"）→ Demo 课时（找不到就 None）。"""
    import server as demo_server
    key = (section or "").strip()
    if not key:
        return None
    lesson = demo_server.lesson_by_key(unit, key)
    return lesson if lesson and lesson.get("key") else None


def entry_for_item(item: dict):
    """一条正式池项目 → Demo 巩固入口（映射不成立返回 None，不造假入口）。"""
    item_id = (item or {}).get("item_id")
    if not item_id:
        return None
    if (item.get("last_judged_activity_type") or "") != SUPPORTED_ACTIVITY:
        return None
    textbook = ex_mod.get_exercise(item_id)           # 既有教材目录（只读）
    if not textbook:
        return None
    unit = _demo_unit(textbook.get("unit"))
    if unit is None:
        return None
    lesson = _demo_lesson(unit, textbook.get("section"))
    if lesson is None:
        return None
    return {
        "item_id": item_id,
        "unit_slug": unit["slug"],
        "lesson_key": lesson["key"],
        "label": ENTRY_LABEL,
        "desc": "%s · %s · %s" % (unit["unit_code"], lesson["title"],
                                  RESULT_TEXT.get(item.get("last_judged_result"), "上次：再看一次")),
        # produce → 复用现有课文简答页（不新建页面）
        "href": "/unit/%s/say?lesson=%s" % (unit["slug"], lesson["key"]),
    }


def formal_reinforce_entries(learning_db=None, limit=LIMIT) -> list:
    """正式巩固池（只读）→ Demo 巩固入口列表；任何异常都返回 []（页面照常）。"""
    db = Path(learning_db or LEARNING_DB)
    try:
        conn = pool.connect_learning_db(db)            # 内部即 mode=ro
        try:
            learner_id = _learner_id(conn)
            if not learner_id:
                return []
            items = pool.list_current_issue_pool(conn, learner_id)
        finally:
            conn.close()
        out, seen = [], set()
        for item in items:                             # 池已按 priority/时间稳定排序
            entry = entry_for_item(item)
            if not entry or entry["item_id"] in seen:
                continue
            seen.add(entry["item_id"])
            out.append(entry)
            if len(out) >= limit:
                break
        return out
    except Exception:                                  # noqa: BLE001 —— 无池数据/读失败都照常运行
        return []

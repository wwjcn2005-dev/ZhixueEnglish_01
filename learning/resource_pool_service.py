#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-06-C2-A 当前错误 / 当前薄弱资源池 —— 最小只读查询服务

职责：只读查询“孩子当前需要处理的资源”。

数据语义（严格沿用 P1-06-C2 冻结规则，不新增业务规则）：
  A 历史错误   = learning_record 中真实发生过的错误行为（append-only，永久保留）
  B 当前错误   = 该 (learner_id, item_id) 最近一条“参与判断”的记录为 incorrect
  C 当前薄弱   = 该 (learner_id, item_id) 最近一条“参与判断”的记录为 partial
  D 参与判断   = result ∈ {correct, incorrect, partial}
    忽略记录     = result ∈ {done, skipped, NULL}（既不加入，也不清除池资格）
  最近参与判断记录为 correct → 退出池（历史错误仍永久保留在 learning_record）

本模块：
  - 只执行 SELECT（绝不写库：无 INSERT / UPDATE / DELETE / DDL）
  - 不调用 AI / 不联网 / 不依赖任何模型
  - 不修改 learning.db 与 contentpack（contentpack 仅 mode=ro 读取用于展示字段）

关于字段命名（本项目实际模型 vs 任务书用语）：
  knowledge_id   → 本项目 = 教材资源身份 item_id（同时以 item_id 字段返回）
  knowledge_name → 教材资源 canonical_text（只读取自 contentpack）
  resource_type  → learning_item.item_type（vocabulary / phrase / sentence_pattern）
  subject/chapter→ 本项目无 subject/chapter 字段；以 textbook_id + unit_code + section_key
                   只读推导表达（无法解析时明确标记 unknown，不猜测）
  priority_score → 本项目**没有**该字段；本服务以“派生排序键”实现（见 PRIORITY_SCORE_NOTE），
                   仅用于稳定排序，不含新的学习规则
"""

from __future__ import annotations

import os

import sqlite3
from pathlib import Path

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
DEFAULT_LEARNING_DB = BASE / "structured" / "learning" / "learning.db"
DEFAULT_CONTENTPACK_DB = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"

#: 参与“当前池资格”判断的结果（P1-06-C2 §5.2 冻结）
JUDGED_RESULTS = ("correct", "incorrect", "partial")
#: 被忽略的结果：既不加入，也不清除池资格（P1-06-C2 §5.2 冻结）
IGNORED_RESULTS = ("done", "skipped", None)

CURRENT_ERROR = "current_error"      # 最近参与判断 = incorrect
CURRENT_WEAK = "current_weak"        # 最近参与判断 = partial

#: priority_score 说明（本轮新增的**排序键**，非学习规则；如需改口径由用户决定）
PRIORITY_SCORE_NOTE = (
    "priority_score 不是本项目既有字段，也不是新的学习规则；"
    "它是本只读服务的派生排序键：current_error=2、current_weak=1，"
    "仅用于稳定排序（priority_score DESC, last_judged_at DESC, item_id ASC）。"
)


def connect_learning_db(path=DEFAULT_LEARNING_DB) -> sqlite3.Connection:
    """只读打开 learning.db。"""
    conn = sqlite3.connect("file:%s?mode=ro" % Path(path).as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def connect_contentpack_db(path=DEFAULT_CONTENTPACK_DB) -> sqlite3.Connection:
    """只读打开教材库（仅用于展示字段：名称 / 类型 / 单元 / 小节）。"""
    conn = sqlite3.connect("file:%s?mode=ro" % Path(path).as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------------------------------
# 只读查询核心
# --------------------------------------------------------------------------

def _latest_judged_rows(conn, learner_id, textbook_id=None):
    """每个 (learner_id, item_id) 最近一条“参与判断”的记录（P1-06-C2 §5.2）。"""
    sql = """
        SELECT r.learner_id, r.item_id, r.result, r.created_at, r.record_id, r.textbook_id,
               r.activity_type
        FROM learning_record r
        WHERE r.learner_id = ?
          AND r.result IN ('correct','incorrect','partial')
          AND NOT EXISTS (
                SELECT 1 FROM learning_record x
                WHERE x.learner_id = r.learner_id AND x.item_id = r.item_id
                  AND x.result IN ('correct','incorrect','partial')
                  AND (x.created_at > r.created_at
                       OR (x.created_at = r.created_at AND x.record_id > r.record_id)))
    """
    params = [learner_id]
    if textbook_id is not None:
        sql += " AND r.textbook_id = ?"
        params.append(textbook_id)
    sql += " ORDER BY r.item_id"
    return conn.execute(sql, params).fetchall()


def _judged_stats(conn, learner_id, item_id):
    row = conn.execute(
        "SELECT COUNT(*) AS judged, "
        "       SUM(CASE WHEN result='incorrect' THEN 1 ELSE 0 END) AS incorrect_count, "
        "       SUM(CASE WHEN result='partial'   THEN 1 ELSE 0 END) AS partial_count, "
        "       SUM(CASE WHEN result='correct'   THEN 1 ELSE 0 END) AS correct_count "
        "FROM learning_record WHERE learner_id=? AND item_id=? "
        "AND result IN ('correct','incorrect','partial')", (learner_id, item_id)).fetchone()
    return {"judged_record_count": int(row["judged"] or 0),
            "incorrect_count": int(row["incorrect_count"] or 0),
            "partial_count": int(row["partial_count"] or 0),
            "correct_count": int(row["correct_count"] or 0)}


def _enrich_from_contentpack(cp, item_ids):
    """只读补充展示字段：名称 / 资源类型 / 教材 / 单元 / 小节。"""
    if not item_ids:
        return {}
    marks = ",".join("?" * len(item_ids))
    info = {}
    for row in cp.execute(
            "SELECT item_id, item_type, canonical_text, textbook_id FROM learning_item "
            "WHERE item_id IN (%s)" % marks, list(item_ids)):
        info[row["item_id"]] = {"knowledge_name": row["canonical_text"],
                                "resource_type": row["item_type"],
                                "textbook_id": row["textbook_id"]}
    pages = {}
    for row in cp.execute(
            "SELECT sr.item_id AS item_id, MIN(p.pdf_page) AS pdf_page FROM source_ref sr "
            "JOIN content_block b ON b.block_id = sr.source_id "
            "JOIN page p ON p.page_id = b.page_id "
            "WHERE sr.item_id IN (%s) GROUP BY sr.item_id" % marks, list(item_ids)):
        pages[row["item_id"]] = row["pdf_page"]
    for item_id, entry in info.items():
        page_no = pages.get(item_id)
        entry["unit_code"] = None
        entry["section_key"] = None
        if page_no is None:
            entry["unit_section_status"] = "unknown(no source page)"
            continue
        unit = cp.execute(
            "SELECT unit_id, unit_code FROM unit WHERE pdf_page_start <= ? AND pdf_page_end >= ? "
            "ORDER BY pdf_page_start DESC LIMIT 1", (page_no, page_no)).fetchone()
        if unit is None:
            entry["unit_section_status"] = "unknown(no unit for page %s)" % page_no
            continue
        entry["unit_code"] = unit["unit_code"]
        sec = cp.execute(
            "SELECT section_key FROM section WHERE unit_id = ? AND pdf_page_start <= ? "
            "ORDER BY pdf_page_start DESC LIMIT 1", (unit["unit_id"], page_no)).fetchone()
        entry["section_key"] = sec["section_key"] if sec else None
        entry["unit_section_status"] = "resolved" if sec else "unknown(no section)"
    return info


def list_current_issue_pool(conn, learner_id, textbook_id=None, contentpack_path=DEFAULT_CONTENTPACK_DB,
                            limit=None) -> list:
    """返回该 Learner **当前需要处理**的资源池（只读，稳定排序）。

    池资格：该 (learner_id, item_id) 最近一条“参与判断”的记录为 incorrect / partial。
    已由 correct 退出的项目不会返回；历史错误记录不会被返回为“当前错误”。
    """
    rows = _latest_judged_rows(conn, learner_id, textbook_id)
    items = []
    for r in rows:
        if r["result"] == "incorrect":
            issue_type = CURRENT_ERROR
            priority = 2
        elif r["result"] == "partial":
            issue_type = CURRENT_WEAK
            priority = 1
        else:                       # correct → 不在池中
            continue
        stats = _judged_stats(conn, learner_id, r["item_id"])
        items.append({
            "knowledge_id": r["item_id"],          # 本项目实际身份（教材资源 item_id）
            "item_id": r["item_id"],
            "knowledge_name": None,                # 由 contentpack 只读补充
            "resource_type": None,
            "textbook_id": r["textbook_id"],
            "unit_code": None,
            "section_key": None,
            "issue_type": issue_type,
            "status": issue_type,
            "priority_score": priority,
            "last_judged_result": r["result"],
            "last_judged_at": r["created_at"],
            "last_judged_record_id": r["record_id"],
            "last_judged_activity_type": r["activity_type"],
            "data_basis": {"source": "learning_record",
                           "rule": "P1-06-C2 §5.2（当前池资格规则）",
                           "judged_results": list(JUDGED_RESULTS),
                           "ignored_results": ["done", "skipped", None]},
            "data_sufficiency": "sufficient",
            **stats,
        })

    cp = connect_contentpack_db(contentpack_path)
    try:
        info = _enrich_from_contentpack(cp, [i["item_id"] for i in items])
    finally:
        cp.close()
    for item in items:
        entry = info.get(item["item_id"])
        if entry is None:
            item["data_sufficiency"] = "insufficient(item not in current contentpack)"
            continue
        item.update({k: entry[k] for k in ("knowledge_name", "resource_type", "textbook_id",
                                           "unit_code", "section_key")})
        if entry.get("unit_section_status") != "resolved":
            item["data_sufficiency"] = "partial(%s)" % entry.get("unit_section_status")

    # 稳定排序：priority_score DESC → last_judged_at DESC → item_id ASC
    # （三段稳定排序，等价于该复合键；避免依赖平台字符串比较差异）
    items.sort(key=lambda x: x["item_id"])
    items.sort(key=lambda x: x["last_judged_at"] or "", reverse=True)
    items.sort(key=lambda x: -x["priority_score"])
    return items[:limit] if limit else items


def summarize_pool(conn, learner_id, textbook_id=None, contentpack_path=DEFAULT_CONTENTPACK_DB) -> dict:
    """池汇总（只读）。"""
    pool = list_current_issue_pool(conn, learner_id, textbook_id, contentpack_path)
    return {
        "learner_id": learner_id,
        "textbook_id": textbook_id,
        "total": len(pool),
        "current_error_count": sum(1 for x in pool if x["issue_type"] == CURRENT_ERROR),
        "current_weak_count": sum(1 for x in pool if x["issue_type"] == CURRENT_WEAK),
        "has_data": len(pool) > 0,
        "data_insufficient_count": sum(1 for x in pool if x["data_sufficiency"] != "sufficient"),
        "priority_score_note": PRIORITY_SCORE_NOTE,
        "items": pool,
    }


def get_item_pool_status(conn, learner_id, item_id, contentpack_path=DEFAULT_CONTENTPACK_DB):
    """单条资源的当前池状态：None 表示不在当前池中（历史记录仍完整保留）。"""
    for item in list_current_issue_pool(conn, learner_id, None, contentpack_path):
        if item["item_id"] == item_id:
            return item
    return None

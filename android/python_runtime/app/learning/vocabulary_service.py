#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-09-C1 Vocabulary 最小学习消费链路

目标链路（只负责“消费已经选定的教材资源”）：

    孩子主动选一个核心 Vocabulary
      → Vocabulary 校验（核心/非核心）
      → LearningSession → LearningTask → TaskItem
      → LearningActivity（P1-07-C2 只读投影）
      → study / practice（P1-08-C1 行为协议）
      → LearningRecord（唯一写入口 record_learning_event）
      → MasteryState → 当前错误/薄弱池（C2-A 只读重算）

**核心 Vocabulary 的机器识别依据**（非猜测，均有既有数据支撑）：
  `learning_item.learning_requirement = 'CORE'`
  ← P1-06-B1.7-D 由来源级字重证据回填：
      `source_ref.textbook_emphasis = 'BOLD'`（字体 `FrutigerNextLTW1G-Medium`）
      对应 PLAIN / `FrutigerNextLTW1G-Regula` → `RECOGNITION`（认识即可，**不得进入核心链路**）。
  v5 实际分布：CORE 243 ｜ RECOGNITION 43 ｜ NEED_REVIEW 1（peaceful，来源冲突，**同样不进入核心链路**）。

边界：
  - 不自动选词、不自动生成计划、不引入打卡/积分/排行榜；调用方必须明确提供 item_id。
  - 不新增表/字段、不改 schema；Vocabulary 学习行为进入既有 learning_record。
  - 不复制 Record/Mastery 逻辑（完全委托 C1 / session_service / behavior_service）。
  - 不调用 AI、不联网、不写 contentpack（仅 mode=ro 读取）。
"""

from __future__ import annotations

import os

from pathlib import Path

import activity_service as act
import behavior_service as beh
import learning_service as svc
import session_service as ses

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
DEFAULT_CONTENTPACK_DB = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"

#: 核心 Vocabulary 的机器判据（教材加粗重点词）
CORE_REQUIREMENT = "CORE"
#: 非核心（认识即可）与待审（来源冲突）——均不得进入核心学习链路
NON_CORE_REQUIREMENTS = ("RECOGNITION", "NEED_REVIEW")


def _refs(cp, item_id) -> list:
    """来源级证据（只读）：字重 / 来源栏目 / 页码。"""
    rows = cp.execute(
        "SELECT source_ref_id, source_id, textbook_emphasis, emphasis_source_list, emphasis_evidence "
        "FROM source_ref WHERE item_id=? ORDER BY source_ref_id", (item_id,)).fetchall()
    out = []
    for r in rows:
        ev = {}
        try:
            import json as _json
            ev = _json.loads(r["emphasis_evidence"]) if r["emphasis_evidence"] else {}
        except Exception:
            ev = {}
        out.append({"source_ref_id": r["source_ref_id"], "source_id": r["source_id"],
                    "textbook_emphasis": r["textbook_emphasis"],
                    "emphasis_source_list": r["emphasis_source_list"],
                    "pdf_page": ev.get("pdf_page"), "textbook_page": ev.get("textbook_page"),
                    "font_name": ev.get("font_name")})
    return out


def get_vocabulary(item_id, contentpack_path=DEFAULT_CONTENTPACK_DB) -> dict:
    """读取一条 Vocabulary 教材资源（含核心/非核心判定与教材追溯信息）。"""
    if not item_id or not isinstance(item_id, str):
        raise svc.ValidationError("item_id 必须是非空字符串")
    cp = svc.connect_contentpack_db(contentpack_path)
    try:
        row = cp.execute(
            "SELECT item_id, item_type, canonical_text, display_text, meaning_zh, phonetic, "
            "part_of_speech, textbook_id, learning_requirement, requirement_conflict_status, "
            "review_status FROM learning_item WHERE item_id=?", (item_id,)).fetchone()
        if row is None:
            raise svc.NotFoundError("教材资源不存在：%s" % item_id)
        if row["item_type"] != "vocabulary":
            raise svc.ValidationError("该资源不是 Vocabulary（item_type=%s）：%s"
                                      % (row["item_type"], item_id))
        refs = _refs(cp, item_id)
    finally:
        cp.close()
    requirement = row["learning_requirement"]
    bold_refs = [r for r in refs if r["textbook_emphasis"] == "BOLD"]
    return {
        "item_id": row["item_id"],
        "item_type": row["item_type"],
        "canonical_text": row["canonical_text"],
        "display_text": row["display_text"],
        "meaning_zh": row["meaning_zh"],
        "phonetic": row["phonetic"],
        "part_of_speech": row["part_of_speech"],
        "textbook_id": row["textbook_id"],
        "learning_requirement": requirement,
        "requirement_conflict_status": row["requirement_conflict_status"],
        "review_status": row["review_status"],
        "is_core_vocabulary": requirement == CORE_REQUIREMENT,
        "textbook_emphasis": "BOLD" if bold_refs else (refs[0]["textbook_emphasis"] if refs else None),
        "emphasis_source_list": (bold_refs or refs or [{}])[0].get("emphasis_source_list"),
        "source_refs": refs,
        "trace": {"source": "contentpack.learning_item",
                  "contentpack": "v5",
                  "rule": "learning_requirement=CORE ⇐ source_ref.textbook_emphasis=BOLD（P1-06-B1.7-D）",
                  "item_id": row["item_id"],
                  "textbook_id": row["textbook_id"]},
    }


def is_core_vocabulary(item_id, contentpack_path=DEFAULT_CONTENTPACK_DB) -> bool:
    """是否为教材加粗重点词（= 可进入核心 Vocabulary 学习链路）。"""
    return get_vocabulary(item_id, contentpack_path)["is_core_vocabulary"]


def require_core_vocabulary(item_id, contentpack_path=DEFAULT_CONTENTPACK_DB) -> dict:
    """要求必须是核心 Vocabulary；否则明确拒绝进入核心链路。"""
    vocab = get_vocabulary(item_id, contentpack_path)
    if not vocab["is_core_vocabulary"]:
        raise svc.ValidationError(
            "非核心 Vocabulary（learning_requirement=%s），不允许进入核心 Vocabulary 学习链路：%s"
            % (vocab["learning_requirement"], item_id))
    return vocab


def start_vocabulary_study(conn, learner_id, item_id, entry_point="vocabulary",
                           contentpack_path=DEFAULT_CONTENTPACK_DB,
                           session_id=None, started_at=None) -> dict:
    """开始学习一个**已由调用方选定**的核心 Vocabulary（复用 Session/Task/TaskItem 链路）。"""
    vocab = require_core_vocabulary(item_id, contentpack_path)
    session = ses.create_learning_session(conn, learner_id, entry_point, [item_id],
                                          textbook_id=vocab["textbook_id"],
                                          session_id=session_id, started_at=started_at,
                                          contentpack_path=contentpack_path)
    activity = act.resolve_activity(conn, session["task_id"], item_id,
                                    contentpack_path=contentpack_path)
    return {"vocabulary": vocab, "session": session,
            "task": svc.get_task(conn, session["task_id"]), "activity": activity}


def record_vocabulary_study(conn, session_id, item_id, learner_id=None, result="done",
                            response_raw=None, hints_used=0, snapshot_id=None, created_at=None,
                            contentpack_path=DEFAULT_CONTENTPACK_DB) -> dict:
    """记录一次 Vocabulary study（委托 P1-08-C1 行为协议，不复制 Record 逻辑）。"""
    session = ses.get_learning_session(conn, session_id, learner_id)
    require_core_vocabulary(item_id, contentpack_path)
    return beh.record_study(conn, session["learner_id"], session["task_id"], item_id,
                            result=result, response_raw=response_raw, hints_used=hints_used,
                            snapshot_id=snapshot_id, created_at=created_at,
                            contentpack_path=contentpack_path)


def record_vocabulary_practice(conn, session_id, item_id, result=None, learner_id=None,
                               response_raw=None, hints_used=0, snapshot_id=None, created_at=None,
                               contentpack_path=DEFAULT_CONTENTPACK_DB) -> dict:
    """记录一次 Vocabulary practice（结果必须由调用方明确传入或由既有判断链路提供）。"""
    session = ses.get_learning_session(conn, session_id, learner_id)
    require_core_vocabulary(item_id, contentpack_path)
    return beh.record_practice(conn, session["learner_id"], session["task_id"], item_id,
                               result=result, response_raw=response_raw, hints_used=hints_used,
                               snapshot_id=snapshot_id, created_at=created_at,
                               contentpack_path=contentpack_path)

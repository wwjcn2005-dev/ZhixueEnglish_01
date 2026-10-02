#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""课文简答 → 模拟 AI 评价 → LearningRecord 的最小衔接（Spike，Demo 侧）

只做三件事（严格最小）：
  ① 把课文简答的**教材句子**映射到一条**真实教材 item**（映射不成立就放弃，绝不伪造）；
  ② 把模拟 AI 评价整理成结构化 JSON，写进既有 `learning_record.response_raw`；
  ③ 复用正式 `learning/` 写入接口落一条 LearningRecord（不直接 INSERT、不改 schema、不改规则）。

本次 AI 是**模拟**：`ai_called=false`，真实 API 调用 = 0
（评价内容复用 Demo 已有的确定性 `say_grading`，不联网、不调用模型）。

教材 item 的确定性映射规则（任一步不成立 → 返回 None）：
  1. 课文简答的句子 `uid` 必须是 contentpack 已登记的教材句子
     （`audio_sentence_annotation.sentence_uid`，即 P3-07 人工核验的那批）；
  2. 用该句子的 `activity` 文本 + `source_page` 的 PDF 页，在本 Unit 找到**唯一**教材 activity；
  3. 该 activity 经 `source_ref(source_type='activity')` 关联的 learning_item 必须**唯一**。

result 映射（本次 Spike 的确定性模拟映射，不是正式 AI 判定标准）：
  carries 且 complete 且 coverage >= 0.6 → correct
  carries（未达上面完整条件）           → partial
  not carries                           → incorrect
"""

from __future__ import annotations

import os

import json
import re
import sqlite3
import sys
from pathlib import Path

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
for _p in (str(BASE / "learning"), str(BASE / "web")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.dont_write_bytecode = True

import learning_service as svc          # noqa: E402
import session_service as ses           # noqa: E402

#: 正式库路径（测试可替换为临时副本，不改正式库）
LEARNING_DB = svc.DEFAULT_LEARNING_DB
CONTENTPACK = svc.DEFAULT_CONTENTPACK_DB

#: 「孩子根据教材要求做英文表达」→ 现有 activity_type 里语义最贴合的是 produce
ACTIVITY_TYPE = "produce"
ENTRY_POINT = "activity"

#: Demo 没有学习者身份；只有一个现成学习者时复用它，没有才新建（不重复建人）
DEMO_LEARNER_NAME = "演示学习者"

EVALUATION_TYPE = "ai_assisted_short_answer"
EVALUATION_SOURCE = "demo_deterministic_ai_simulation"


def _ro(path) -> sqlite3.Connection:
    conn = sqlite3.connect("file:%s?mode=ro" % Path(path).as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _norm(text) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _pdf_page(source_page):
    m = re.search(r"PDF\s*p(\d+)", source_page or "", re.I)
    return int(m.group(1)) if m else None


def _textbook_page(source_page):
    m = re.search(r"教材\s*p(\d+)", source_page or "")
    return int(m.group(1)) if m else None


def _unit_token(unit_code: str) -> str:
    """Demo 的 unit_code（`Starter` / `Unit 1`）→ contentpack section_id 的 unit 段（STARTER / U1）。"""
    code = (unit_code or "").strip()
    if code.lower() == "starter":
        return "STARTER"
    m = re.match(r"unit\s*(\d+)", code, re.I)
    return "U%s" % m.group(1) if m else ""


def resolve_item(task: dict, unit_code: str, contentpack_path=CONTENTPACK):
    """课文简答 → 真实教材 item（确定性、可追溯）。映射不成立返回 None。"""
    uid = (task or {}).get("uid")
    token = _unit_token(unit_code)
    if not uid or not token:
        return None
    cp = _ro(contentpack_path)
    try:
        ann = cp.execute("SELECT activity, source_page FROM audio_sentence_annotation "
                         "WHERE sentence_uid=?", (uid,)).fetchone()
        if ann is None:
            return None
        page = _pdf_page(ann["source_page"])
        acts = []
        for row in cp.execute("SELECT activity_id, section_id, instruction, pdf_page FROM activity"):
            parts = (row["section_id"] or "").split(":")
            if len(parts) < 3 or parts[1] != token:
                continue
            if page is not None and row["pdf_page"] != page:
                continue
            if _norm(row["instruction"]) != _norm(ann["activity"]):
                continue
            acts.append(row)
        if len(acts) != 1:
            return None
        items = cp.execute(
            "SELECT sr.item_id, li.item_type, li.canonical_text FROM source_ref sr "
            "JOIN learning_item li ON li.item_id = sr.item_id "
            "WHERE sr.source_type='activity' AND sr.source_id=?",
            (acts[0]["activity_id"],)).fetchall()
        if len(items) != 1:
            return None
        return {"item_id": items[0]["item_id"],
                "item_type": items[0]["item_type"],
                "textbook_text": items[0]["canonical_text"],
                "activity_id": acts[0]["activity_id"],
                "sentence_uid": uid,
                "pdf_page": page,
                "textbook_page": _textbook_page(ann["source_page"])}
    finally:
        cp.close()


def result_for(grading: dict) -> str:
    """模拟 AI 评价 → 现有三值 result（本次 Spike 的确定性映射）。"""
    if grading.get("carries") and grading.get("complete") and (grading.get("coverage") or 0) >= 0.6:
        return "correct"
    if grading.get("carries"):
        return "partial"
    return "incorrect"


def build_response_raw(task: dict, grading: dict, mapping: dict) -> str:
    """结构化评价（写进既有 response_raw；不塞进 summary 字符串）。"""
    payload = {
        "evaluation_type": EVALUATION_TYPE,
        "result": result_for(grading),
        "content": {"carries": bool(grading.get("carries")),
                    "complete": bool(grading.get("complete")),
                    "coverage": grading.get("coverage"),
                    "word_count": grading.get("word_count")},
        "language": {"hints": list(grading.get("hints") or []),
                     "rule_judgement": grading.get("rule_judgement") or ""},
        "textbook_basis": {
            "textbook_page": mapping.get("textbook_page"),
            "pdf_page": mapping.get("pdf_page"),
            "activity_id": mapping.get("activity_id"),
            "textbook_item": mapping.get("item_id"),
            "references": [
                {"kind": "textbook_item", "item_id": mapping.get("item_id"),
                 "item_type": mapping.get("item_type")},
                {"kind": "textbook_sentence", "sentence_uid": mapping.get("sentence_uid")},
            ],
        },
        "textbook_expressions": {"used": list(grading.get("used") or []),
                                 "missing": list(grading.get("missing") or []),
                                 "task_text": task.get("text")},
        "mastery": {"mark": grading.get("mark") or ""},
        "guidance": grading.get("advice") or "",
        "source": EVALUATION_SOURCE,
        "ai_called": False,
        "ai_status": grading.get("ai_status"),
    }
    return json.dumps(payload, ensure_ascii=False)


def _learner_id(conn) -> str:
    """Demo 没有学习者身份：复用现成 active 学习者，没有才新建（不重复建人）。"""
    row = conn.execute("SELECT learner_id FROM learner WHERE status='active' "
                       "ORDER BY created_at LIMIT 1").fetchone()
    if row is not None:
        return row["learner_id"]
    return svc.create_learner(conn, DEMO_LEARNER_NAME)["learner_id"]


def record_say(unit: dict, task: dict, grading: dict,
               learning_db=None, contentpack_path=None) -> dict:
    """把一次课文简答的模拟 AI 评价写进正式学习证据链（失败不影响页面）。"""
    cp_path = Path(contentpack_path or CONTENTPACK)
    db_path = Path(learning_db or LEARNING_DB)
    try:
        mapping = resolve_item(task, (unit or {}).get("unit_code"), cp_path)
    except Exception as exc:                       # noqa: BLE001 —— 只读映射失败：不写记录
        return {"status": "skipped", "reason": "mapping_error: %r" % (exc,)}
    if not mapping:
        return {"status": "skipped", "reason": "no_textbook_item"}

    result = result_for(grading)
    payload = build_response_raw(task, grading, mapping)
    conn = svc.connect_learning_db(db_path)
    try:
        learner_id = _learner_id(conn)
        session = ses.create_learning_session(conn, learner_id, ENTRY_POINT,
                                              [mapping["item_id"]],
                                              contentpack_path=cp_path)
        out = svc.record_learning_event(conn, learner_id, session["task_id"],
                                        mapping["item_id"], ACTIVITY_TYPE,
                                        result=result, response_raw=payload,
                                        contentpack_path=cp_path)
        ses.end_learning_session(conn, session["session_id"], learner_id)
        return {"status": "recorded", "learner_id": learner_id,
                "session_id": session["session_id"], "task_id": session["task_id"],
                "record_id": out["record"]["record_id"], "item_id": mapping["item_id"],
                "activity_type": ACTIVITY_TYPE, "result": result,
                "mastery": out["mastery"], "mapping": mapping}
    except Exception as exc:                       # noqa: BLE001 —— Spike：不因为写库失败打断页面
        return {"status": "error", "reason": "%r" % (exc,), "item_id": mapping["item_id"],
                "result": result}
    finally:
        conn.close()

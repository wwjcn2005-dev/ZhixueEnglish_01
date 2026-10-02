#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-6-B5 教材优先巩固建议服务（只读，只给建议，不执行）

严格遵循规范 V1.2 第二十二章第 6 条的优先顺序：

  1 回看原教材文本   2 重听官方音频   3 回到教材语法提示
  4 对照教材范文     5 重做原教材题   6 跨 Section 教材范围综合练习

AI 辅助练习：本阶段 **不实现**（返回 ai_assist=not_implemented）。

教材定位来源（全部为既有只读数据，不伪造）：
  * 练习 → `structured/exercises/exercise_catalog_v3.json`（unit/section/页码/官方音频）
  * 词汇 → contentpack 归属（unit）+ P2-4 附录词表页 + 逐词音频清单（🔊）
  * 语法 → P2-4 `textbook_content_relations_v2.json` 的 grammar_in 指针（教材原文 “Know more about … pNN”）

无法可靠定位时必须返回 requires_resource_mapping=True，并列出缺失原因；绝不生成虚假页码或音频 id。
建议只提供入口（link 或纯文本定位），必须由孩子主动点击。
"""

from __future__ import annotations

import os

import hashlib
import json
from pathlib import Path

import evidence_service as ev
import diagnosis_service as diag
import resource_pool_service as pool

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
DEFAULT_CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
CATALOG_V3 = BASE / "structured" / "exercises" / "exercise_catalog_v3.json"
STRUCTURE_V2 = BASE / "structured" / "textbook" / "textbook_structure_v2.json"
CONTENT_REL_V2 = BASE / "structured" / "textbook" / "textbook_content_relations_v2.json"
WORD_MANIFEST = BASE / "structured" / "audio" / "derived" / "word_audio_manifest.json"

TEXTBOOK_ID = "FLTRP-EN-7A-2022CUR"

_CACHE = {}


def _load(path, kind="json"):
    key = str(path)
    if key not in _CACHE:
        try:
            _CACHE[key] = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            _CACHE[key] = {}
    return _CACHE[key]


def _exercise(item_id: str):
    return (_load(CATALOG_V3).get("exercises") and
            next((e for e in _load(CATALOG_V3)["exercises"] if e["exercise_id"] == item_id), None))


def _exercise_key(item_id: str) -> str:
    return hashlib.sha256((item_id or "").encode("utf-8")).hexdigest()[:12]


def _unit_of_vocabulary(item_id: str, contentpack_path=DEFAULT_CONTENTPACK) -> str:
    """复用 web/content 的归属规则（只读）——与页面展示口径一致。"""
    try:
        import sys
        sys.path.insert(0, str(BASE / "web"))
        sys.dont_write_bytecode = True
        import content as content_mod
        cp = ev.connect_learning_db  # 占位，避免误用
        conn = content_mod._ro(contentpack_path)
        try:
            attr = content_mod._attribution(conn)
        finally:
            conn.close()
        return (attr.get(item_id) or {}).get("unit_code")
    except Exception:
        return None


def _word_audio_url(item_id: str):
    for unit in (_load(WORD_MANIFEST).get("units") or {}).values():
        for w in unit.get("words") or []:
            if w.get("item_id") == item_id:
                return w.get("url"), w.get("canonical_text")
    return None, None


def _appendix_words_page():
    for u in _load(STRUCTURE_V2).get("units", []):
        if u.get("kind") != "appendix":
            continue
        for s in u.get("sections", []):
            if s.get("section_key") == "WORDS_AND_EXPRESSIONS":
                return s.get("textbook_page_start"), s.get("pdf_page_start")
    return None, None


def _grammar_pointer(unit_code: str):
    for r in _load(CONTENT_REL_V2).get("grammar_in", []):
        if r.get("relation") == "grammar_in" and r.get("unit") == unit_code:
            return r
    return None


def suggest(conn, learner_id: str, item_id: str, rules: dict = None,
            contentpack_path=DEFAULT_CONTENTPACK, context_label: str = None) -> dict:
    """给出教材优先的巩固建议（只读；不执行任何动作）。

    context_label 可由调用方传入（例如“上次有点模糊”），用于解释建议原因；
    未传时使用诊断结论。无论诊断等级如何，只要教材定位可用就给出建议。
    """
    rules = rules or ev.load_rules()
    order = rules["intervention"]["textbook_first_order"]
    d = diag.diagnose(conn, learner_id, item_id, rules)
    reason = context_label or d["label"]
    ex = _exercise(item_id)
    missing = []
    anchors = {}
    unit_code = None
    resource_type = None
    display_text = None

    if ex:
        resource_type = "exercise"
        unit_code = ex.get("unit")
        display_text = ex.get("instruction")
        anchors["textbook"] = {
            "book": TEXTBOOK_ID, "unit": ex.get("unit"), "section": ex.get("section"),
            "textbook_page": ex.get("textbook_page"), "activity_no": ex.get("exercise_no"),
            "question_type": ex.get("question_type"),
        }
        anchors["reread_text"] = dict(anchors["textbook"],
                                      anchor="教材第 %s 页 · 练习 %s" % (ex.get("textbook_page"),
                                                                        ex.get("exercise_no")))
        anchors["redo_exercise"] = {"link": "/exercise/%s" % _exercise_key(item_id),
                                    "label": "重做这道教材原题"}
        if ex.get("audio_id"):
            anchors["replay_audio"] = {"audio_id": ex["audio_id"],
                                       "filename": ex.get("audio_filename"),
                                       "label": "重听这道题对应的教材官方录音（🎧）"}
    else:
        resource_type = "vocabulary_or_other"
        unit_code = _unit_of_vocabulary(item_id, contentpack_path)
        url, word = _word_audio_url(item_id)
        page, pdf = _appendix_words_page()
        display_text = word
        if unit_code and page:
            anchors["textbook"] = {"book": TEXTBOOK_ID, "unit": unit_code,
                                   "section": "WORDS_AND_EXPRESSIONS",
                                   "textbook_page": page,
                                   "anchor": "教材词表（Words and expressions）"}
            anchors["reread_text"] = dict(anchors["textbook"],
                                          anchor="教材第 %s 页 · 词表" % page)
        else:
            missing.append("unit_or_appendix_page")
        if url:
            anchors["replay_audio"] = {"word_audio_url": url,
                                       "label": "再听一次这个单词的发音（🔊）"}
        else:
            missing.append("word_audio")

    if unit_code:
        g = _grammar_pointer(unit_code)
        if g:
            anchors["grammar_pointer"] = {
                "topic": g.get("topic"),
                "appendix_textbook_page": g.get("appendices_page"),
                "label": "教材语法提示：%s（第 %s 页）" % (g.get("topic"),
                                                          g.get("appendices_page")),
            }
        anchors["cross_section_practice"] = {
            "unit": unit_code,
            "label": "本单元教材练习（跨板块）列表",
            "link": "/unit/%s/exercises" % str(unit_code).lower().replace(" ", ""),
        }

    type_labels = {
        "reread_text": "回看原教材文本",
        "replay_audio": "重听官方音频",
        "grammar_pointer": "回到教材语法提示",
        "model_text_review": "对照教材范文",
        "redo_exercise": "重做原教材题",
        "cross_section_practice": "跨板块教材范围练习",
    }
    suggestions = []
    for rank, t in enumerate(order, start=1):
        if t not in anchors:
            continue
        anchor = anchors[t]
        suggestions.append({
            "type": t, "rank": rank, "label": type_labels[t],
            "reason": "依据：%s" % reason,
            "anchor": anchor,
            "link": anchor.get("link"),
            "action": "child_click",          # 必须由孩子主动点击
        })
    return {
        "learner_id": learner_id,
        "item_id": item_id,
        "resource_type": resource_type,
        "display_text": display_text,
        "unit": unit_code,
        "diagnosis_level": d["level"],
        "diagnosis_label": d["label"],
        "pool_state": d.get("pool_state"),
        "reason": reason,
        "suggestions": suggestions,
        "requires_resource_mapping": bool(missing),
        "missing": missing,
        "textbook_first": True,
        "ai_assist": rules["intervention"]["ai_assist"],
        "auto_execute": False,
    }


def suggest_for_learner(conn, learner_id: str, rules: dict = None,
                        contentpack_path=DEFAULT_CONTENTPACK) -> list:
    """对当前需要关注的内容，逐条给出教材优先建议（只读）。"""
    rules = rules or ev.load_rules()
    seen, out = set(), []
    for d in diag.list_attention(conn, learner_id, rules):
        seen.add(d["item_id"])
        out.append(suggest(conn, learner_id, d["item_id"], rules, contentpack_path))
    # 冻结池里的内容（含孩子自评“有点模糊/忘了”）同样给出教材优先建议，仅作建议
    try:
        for item in pool.list_current_issue_pool(conn, learner_id,
                                                 contentpack_path=contentpack_path):
            if item["item_id"] in seen:
                continue
            label = ("上次忘了" if item.get("issue_type") == pool.CURRENT_ERROR
                     else "上次有点模糊")
            out.append(suggest(conn, learner_id, item["item_id"], rules, contentpack_path,
                               context_label=label))
    except Exception:
        pass
    return out

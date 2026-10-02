#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-09-C2 / P1-09-C3 / P1-10-C2 教材语言资源最小学习体验（本地页面）

目标：把 P1-09-C1 的后端能力，第一次变成孩子可以真正使用的“单个重点单词学习体验”，
在其后追加 P1-09-C3 的**最小 Recall（自我回忆判断）**环节，
并在 P1-10-C2 扩展到 **Phrase（Study + Recall）** 与 **Sentence Pattern（仅 Study）**。

页面内容（只用教材真实存在的信息）：
  单词（canonical_text）/ 音标（有才显示）/ 词性（有才显示）/ 中文释义（meaning_zh）/
  教材来源（来源栏目 + 教材印刷页）/ 「重点词」标签（来自教材加粗事实，不展示技术证据）
  Phrase：canonical_text + meaning_zh + **全部** source_ref 来源（来源栏目 + 印刷页）；
          音标/词性不存在 → 不显示；**不显示「重点词」标签**（Phrase 的 CORE 来自 Language notes，
          不是加粗字体证据，P1-10-C2 §十一）
  Sentence Pattern：只显示 display_text（`...` 形态，不显示 `{1}` 槽位模板）+ 教材来源；
          **只做 Study，不做 Recall / Practice**（P1-10-C2 §五）
学习动作：**「我学好了」** → record_vocabulary_study(result="done") → 进入 Recall 页面。
Recall（P1-09-C3）：先隐藏中文释义（可点「显示释义」查看，**不产生任何记录**），
  孩子自己回忆后自评：记得 → practice/correct；模糊 → practice/partial；忘了 → practice/incorrect
  → 结束 Session → 结果页显示自评状态（**自我判断，不是系统判分**）。

严格边界（P1-09-C2 §二/§三、P1-09-C3 §二~§二十一、P1-10-C2 §三~§十三）：
  - 不自动选词、不推荐、不自动进入下一个词、不生成计划；孩子必须自己输入/选择单词
  - 学习入口门禁一律用 `learning_requirement='CORE'`（**不是** review_status）：
      Vocabulary / Phrase：CORE 才可进入；Phrase 的 Recall 另需 `meaning_zh` 非空
      Sentence Pattern：仅 CORE 可进入 Study，且不进入 Recall
  - 不扩展 vocabulary_service，也不新增 phrase_service / sentence_pattern_service / generic service
    （P1-10-C2 §十二/§十三）：短语与句型在页面层做极薄编排，直接复用 session / activity /
    behavior / learning / 现有池规则
  - 不实现题目 / 客观判分 / 音频 / TTS / AI / 积分 / 打卡 / 排行榜 / 复习排程 / 掌握率算法
  - Recall 不新增 activity_type（继续用 practice），不新增表/字段，不改 schema
  - 一次点击只产生 **一条** practice 记录；显示释义、页面停留等一律不推断结果
  - contentpack 只读（mode=ro）；不展示 PDF 页码 / bbox / 字体 / 字号 / content_hash / source_ref_id
  - 学习行为只经 vocabulary_service → behavior_service → record_learning_event（唯一写入口）
  - 本页面仅监听 127.0.0.1（本机），不访问互联网；不调用 AI

设计复用：沿用项目现有工作台（workbench/review_workbench_v01.py）的本地服务模式与视觉样式
（同一套 CSS 变量 / 卡片 / 按钮 / 徽标），不新建第二套视觉系统。

用法：
  python D:\ZhixueEnglish\workbench\vocabulary_learning_v01.py [--port 8766] [--no-browser] [--db <learning.db>]
"""

from __future__ import annotations

import argparse
import html
import sqlite3
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(r"D:\ZhixueEnglish")
LEARNING_DB = BASE / "structured" / "learning" / "learning.db"
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
sys.path.insert(0, str(BASE / "learning"))
sys.dont_write_bytecode = True

import learning_service as svc            # noqa: E402
import behavior_service as beh            # noqa: E402
import resource_pool_service as pool      # noqa: E402
import session_service as ses             # noqa: E402
import vocabulary_service as voc          # noqa: E402

ENTRY_POINT = "vocabulary"

#: P1-10-C2：教材语言资源类型（与 contentpack `learning_item.item_type` 同名取值）
KIND_VOCABULARY = "vocabulary"
KIND_PHRASE = "phrase"
KIND_SENTENCE_PATTERN = "sentence_pattern"
KINDS = (KIND_VOCABULARY, KIND_PHRASE, KIND_SENTENCE_PATTERN)
KIND_LABELS = {KIND_VOCABULARY: "单词", KIND_PHRASE: "短语", KIND_SENTENCE_PATTERN: "句型"}

#: 学习入口门禁 = 教材学习资格（P1-10-C2 §七）；与人工审核状态 review_status 无关
CORE_REQUIREMENT = "CORE"

#: Session 入口：沿用 P1-04 §23 已冻结的 entry_point 取值，**不新增枚举**
#: （短语 / 句型来自教材单元材料，故沿用 "unit"；词汇沿用既有 "vocabulary"）
KIND_ENTRY_POINTS = {KIND_VOCABULARY: ENTRY_POINT, KIND_PHRASE: "unit",
                     KIND_SENTENCE_PATTERN: "unit"}

#: 搜索页示例（全部来自真实 contentpack 数据，不虚构）
KIND_EXAMPLES = {KIND_VOCABULARY: "ready", KIND_PHRASE: "of course",
                 KIND_SENTENCE_PATTERN: "One way is to..."}

#: 搜索结果类型不符时的提示（只说明真实原因，不含内部字段名）
KIND_HINTS = {KIND_VOCABULARY: "请检查拼写（只支持教材中的单词）。",
              KIND_PHRASE: "请检查拼写（只支持教材中的短语）。",
              KIND_SENTENCE_PATTERN: "请检查写法（只支持教材中的句型）。"}

#: P1-09-C3：只允许孩子自评的三个结果（映射到既有 LearningRecord 结果语义）
RECALL_CHOICES = (("correct", "记得"), ("partial", "模糊"), ("incorrect", "忘了"))
PRACTICE_RESULTS = tuple(value for value, _ in RECALL_CHOICES)

#: 结果 → 面向孩子的自评表述（底层枚举不变，只是显示措辞）
RESULT_LABELS = {"correct": "记得", "partial": "模糊", "incorrect": "忘了",
                 "done": "已记录", "skipped": "已跳过"}

#: 页面必须保持自评语义，不出现判分/掌握断言措辞
RECALL_NOTE = "回忆状态是你自己的判断，不是系统判分；系统只如实记录你选择的状态。"

#: P1-11-C2：当前需要再学（只读池）——池状态 → 面向孩子的自评表述（不新造学习规则）
ISSUE_ORDER = ("current_error", "current_weak")
ISSUE_TITLES = {"current_error": "当前错误", "current_weak": "当前薄弱"}
ISSUE_LABELS = {"current_error": "忘了", "current_weak": "模糊"}

#: 池只读提示：只陈述事实，不推荐、不安排、不承诺掌握
POOL_NOTE = ("这里只列出你最近一次回忆为「忘了」或「模糊」的内容。"
             "要不要再学、先学哪一个，都由你自己决定；系统不会替你安排顺序，也不会自动开始。")


# --------------------------------------------------------------------------
# 纯逻辑（可测试，不依赖 HTTP）
# --------------------------------------------------------------------------

def find_vocabulary_item_id(word, contentpack_path=CONTENTPACK):
    """按孩子输入的单词精确匹配（大小写不敏感）到教材词汇表中的条目。"""
    word = (word or "").strip()
    if not word:
        return None
    cp = svc.connect_contentpack_db(contentpack_path)
    try:
        row = cp.execute(
            "SELECT item_id FROM learning_item WHERE item_type='vocabulary' "
            "AND lower(canonical_text)=lower(?) ORDER BY item_id LIMIT 1", (word,)).fetchone()
    finally:
        cp.close()
    return row["item_id"] if row else None


def build_word_view(item_id, contentpack_path=CONTENTPACK) -> dict:
    """构造学习页面展示数据（只含教材真实信息；核心词以外的条目会被拒绝）。"""
    vocab = voc.require_core_vocabulary(item_id, contentpack_path)
    refs = vocab["source_refs"]
    bold = [r for r in refs if r["textbook_emphasis"] == "BOLD"] or refs
    main = bold[0] if bold else {}
    view = {
        "item_id": vocab["item_id"],
        "word": vocab["canonical_text"],
        "meaning_zh": vocab["meaning_zh"],
        "tag": "重点词",                      # 教材加粗事实的用户可读表达（不展示技术字段）
        "source_list": main.get("emphasis_source_list"),
        "textbook_page": main.get("textbook_page"),
    }
    # 有值才显示；无值不显示该行（不写“暂无/未知/N/A”）
    if vocab.get("phonetic"):
        view["phonetic"] = vocab["phonetic"]
    if vocab.get("part_of_speech"):
        view["part_of_speech"] = vocab["part_of_speech"]
    src = view["source_list"] or ""
    page = view["textbook_page"]
    view["source_label"] = ("%s · 第%s页" % (src, page)) if (src and page) else (src or None)
    view["item_type"] = KIND_VOCABULARY
    view["kind_label"] = KIND_LABELS[KIND_VOCABULARY]
    view["recall_available"] = True                    # 词汇页面始终有教材释义
    view["recall_label"] = "Vocabulary Recall"
    view["recall_hint"] = "先自己想一遍这个词的意思；想不起来也没关系。"
    view["switch_label"] = "换一个单词"
    view["restart_label"] = "再学一个单词"
    return view


def item_type_of(item_id, contentpack_path=CONTENTPACK) -> str:
    """item_id → 教材资源类型（单一事实来源：contentpack.learning_item.item_type）。"""
    if not item_id or not isinstance(item_id, str):
        raise svc.ValidationError("item_id 必须是非空字符串")
    cp = svc.connect_contentpack_db(contentpack_path)
    try:
        row = cp.execute("SELECT item_type FROM learning_item WHERE item_id=?", (item_id,)).fetchone()
    finally:
        cp.close()
    if row is None:
        raise svc.NotFoundError("教材资源不存在：%s" % item_id)
    return row["item_type"]


def _refs_from(cp, item_id) -> list:
    """条目级教材来源（只读）。页面只用来源栏目 / 印刷页，不展示内部 ID。"""
    out = []
    for r in cp.execute(
            "SELECT source_ref_id, source_id, textbook_emphasis, emphasis_source_list, "
            "quote_raw, emphasis_evidence FROM source_ref WHERE item_id=? ORDER BY source_ref_id",
            (item_id,)):
        ev = {}
        try:
            import json as _json
            ev = _json.loads(r["emphasis_evidence"]) if r["emphasis_evidence"] else {}
        except Exception:
            ev = {}
        out.append({"source_ref_id": r["source_ref_id"], "source_id": r["source_id"],
                    "textbook_emphasis": r["textbook_emphasis"],
                    "source_list": r["emphasis_source_list"], "quote_raw": r["quote_raw"],
                    "pdf_page": ev.get("pdf_page"), "textbook_page": ev.get("textbook_page")})
    return out


def source_lines(refs) -> list:
    """来源展示行（保留**全部**来源，去重后稳定排序；P1-10-C2 §十）。"""
    seen, out = set(), []
    for r in refs or []:
        listed = (r.get("source_list") or "").strip()
        if not listed:
            continue
        page = r.get("textbook_page")
        label = ("%s · 第%s页" % (listed, page)) if page else listed
        if label not in seen:
            seen.add(label)
            out.append(label)
    return out


def _load_item(item_id, item_type, contentpack_path) -> dict:
    """读取一条教材资源并做类型门禁（不写入 contentpack）。"""
    cp = svc.connect_contentpack_db(contentpack_path)
    try:
        row = cp.execute(
            "SELECT item_id, item_type, canonical_text, display_text, meaning_zh, phonetic, "
            "part_of_speech, textbook_id, learning_requirement, requirement_conflict_status, "
            "review_status FROM learning_item WHERE item_id=?", (item_id,)).fetchone()
        if row is None:
            raise svc.NotFoundError("教材资源不存在：%s" % item_id)
        if row["item_type"] != item_type:
            raise svc.ValidationError("该资源不是%s（item_type=%s）：%s"
                                      % (KIND_LABELS[item_type], row["item_type"], item_id))
        refs = _refs_from(cp, item_id)
    finally:
        cp.close()
    return {"item_id": row["item_id"], "item_type": row["item_type"],
            "canonical_text": row["canonical_text"], "display_text": row["display_text"],
            "meaning_zh": row["meaning_zh"], "phonetic": row["phonetic"],
            "part_of_speech": row["part_of_speech"], "textbook_id": row["textbook_id"],
            "learning_requirement": row["learning_requirement"],
            "requirement_conflict_status": row["requirement_conflict_status"],
            "review_status": row["review_status"], "source_refs": refs}


def get_phrase(item_id, contentpack_path=CONTENTPACK) -> dict:
    """读取 Phrase（门禁：learning_requirement='CORE'）。"""
    item = _load_item(item_id, KIND_PHRASE, contentpack_path)
    if item["learning_requirement"] != CORE_REQUIREMENT:
        raise svc.ValidationError(
            "该短语不是教材重点短语（learning_requirement=%s），本阶段不进入短语学习入口：%s"
            % (item["learning_requirement"], item_id))
    return item


def get_sentence_pattern(item_id, contentpack_path=CONTENTPACK) -> dict:
    """读取 Sentence Pattern（门禁：learning_requirement='CORE'）。"""
    item = _load_item(item_id, KIND_SENTENCE_PATTERN, contentpack_path)
    if item["learning_requirement"] != CORE_REQUIREMENT:
        raise svc.ValidationError(
            "该句型不是教材重点句型（learning_requirement=%s），本阶段不进入句型学习入口：%s"
            % (item["learning_requirement"], item_id))
    return item


def phrase_recall_available(phrase) -> bool:
    """Phrase 的 Recall 门禁（P1-10-C2 §三）：CORE **且** meaning_zh 非空。"""
    if not phrase:
        return False
    if phrase.get("learning_requirement") != CORE_REQUIREMENT:
        return False
    return bool((phrase.get("meaning_zh") or "").strip())


def find_phrase_item_id(text, contentpack_path=CONTENTPACK):
    """按孩子输入的短语精确匹配（大小写不敏感）到教材短语条目。"""
    text = (text or "").strip()
    if not text:
        return None
    cp = svc.connect_contentpack_db(contentpack_path)
    try:
        row = cp.execute(
            "SELECT item_id FROM learning_item WHERE item_type='phrase' AND "
            "(lower(canonical_text)=lower(?) OR lower(display_text)=lower(?)) "
            "ORDER BY item_id LIMIT 1", (text, text)).fetchone()
    finally:
        cp.close()
    return row["item_id"] if row else None


def _normalize_pattern_text(text) -> str:
    """仅用于查找的归一化（不修改数据）：大小写、首尾空白、弯引号 → 直引号。"""
    return (text or "").strip().lower().replace("\u2019", "'").replace("\u2018", "'")


def find_sentence_pattern_item_id(text, contentpack_path=CONTENTPACK):
    """按孩子输入的句型匹配 display_text / canonical_text（大小写与直/弯引号等价）。"""
    want = _normalize_pattern_text(text)
    if not want:
        return None
    cp = svc.connect_contentpack_db(contentpack_path)
    try:
        rows = cp.execute(
            "SELECT item_id, canonical_text, display_text FROM learning_item "
            "WHERE item_type='sentence_pattern' ORDER BY item_id").fetchall()
    finally:
        cp.close()
    for r in rows:
        if want in (_normalize_pattern_text(r["display_text"]),
                    _normalize_pattern_text(r["canonical_text"])):
            return r["item_id"]
    return None


def build_phrase_view(item_id, contentpack_path=CONTENTPACK) -> dict:
    """Phrase 学习/Recall 页面展示数据（只含教材真实字段，无音标/词性/「重点词」标签）。"""
    phrase = get_phrase(item_id, contentpack_path)
    lines = source_lines(phrase["source_refs"])
    return {
        "item_id": phrase["item_id"],
        "item_type": KIND_PHRASE,
        "kind_label": KIND_LABELS[KIND_PHRASE],
        "word": phrase["canonical_text"],
        "meaning_zh": phrase["meaning_zh"],
        "source_lines": lines,
        "source_label": " ｜ ".join(lines) if lines else None,
        "recall_available": phrase_recall_available(phrase),
        "recall_label": "Phrase Recall",
        "recall_hint": "先自己想一遍这个短语的意思；想不起来也没关系。",
        "switch_label": "换一个短语",
        "restart_label": "再学一个短语",
        "no_recall_note": "这个短语在教材里没有中文释义，本次只记录学习，不做回忆自评。",
    }


def build_sentence_pattern_view(item_id, contentpack_path=CONTENTPACK) -> dict:
    """Sentence Pattern 学习页面展示数据（只用 display_text；本阶段不做 Recall）。

    P1-10-C2 §九：本阶段**不展示** `quote_raw` —— 唯一 CORE 句型的原文引用被教材内容块
    边界截断（已知问题），展示残缺片段对学习无益；因此不实现展示层清洗，也不改数据。
    """
    pattern = get_sentence_pattern(item_id, contentpack_path)
    lines = source_lines(pattern["source_refs"])
    return {
        "item_id": pattern["item_id"],
        "item_type": KIND_SENTENCE_PATTERN,
        "kind_label": KIND_LABELS[KIND_SENTENCE_PATTERN],
        "word": pattern["display_text"] or pattern["canonical_text"],
        "meaning_zh": None,                    # 51/52 无释义，唯一一条格式异常 → 不展示（§五/§八）
        "source_lines": lines,
        "source_label": " ｜ ".join(lines) if lines else None,
        "recall_available": False,             # 本阶段句型不做 Recall / Practice
        "recall_label": "Sentence Pattern",
        "switch_label": "换一个句型",
        "restart_label": "再学一个句型",
        "no_recall_note": "句型本阶段只做学习浏览，不做回忆自评。",
    }


def build_view(item_id, contentpack_path=CONTENTPACK) -> dict:
    """按资源类型分派展示数据构造（Vocabulary / Phrase / Sentence Pattern）。"""
    kind = item_type_of(item_id, contentpack_path)
    if kind == KIND_VOCABULARY:
        return build_word_view(item_id, contentpack_path)
    if kind == KIND_PHRASE:
        return build_phrase_view(item_id, contentpack_path)
    if kind == KIND_SENTENCE_PATTERN:
        return build_sentence_pattern_view(item_id, contentpack_path)
    raise svc.ValidationError("本阶段不支持的资源类型：%s" % kind)


# --------------------------------------------------------------------------
# P1-11-C2：当前需要再学（只读消费 resource_pool_service，不新造池规则）
# --------------------------------------------------------------------------

def find_learner_by_name(conn, name):
    """按名字**只读**查找既有 Learner（不创建；池页面属只读视图）。"""
    name = (name or "").strip()
    if not name:
        return None
    row = conn.execute(
        "SELECT learner_id FROM learner WHERE display_name=? AND status='active' "
        "ORDER BY created_at LIMIT 1", (name,)).fetchone()
    return row["learner_id"] if row else None


def build_pool_view(conn, learner_id, contentpack_path=CONTENTPACK) -> dict:
    """当前错误 / 当前薄弱列表（**只读**；规则与排序完全来自 resource_pool_service）。

    池语义（资格判定 / priority_score / last_judged_at / 稳定排序）**不在此重实现、不重新排序**；
    本函数只做两件事：
      1. 按 `item_id → contentpack.learning_item` 解析真实教材内容（P1-11-C2 §十六），
         并**仍然经过原有的 CORE 学习门禁**（§十五：来自池不等于跳过 learning_requirement）；
      2. 只保留页面要展示的字段（不把记录 ID / hash / 快照等内部字段带到页面）。
    分组只改变版面顺序（当前错误在前），组内顺序完全保留 Service 返回顺序。
    """
    rows = pool.list_current_issue_pool(conn, learner_id, contentpack_path=contentpack_path)
    grouped = {key: [] for key in ISSUE_ORDER}
    for row in rows:
        item_id = row.get("item_id")
        entry = {
            "item_id": item_id,                        # 仅用于表单回传 item_id（不显示给孩子）
            "text": None, "phonetic": None, "part_of_speech": None, "meaning_zh": None,
            "kind": row.get("resource_type") or "",
            "kind_label": KIND_LABELS.get(row.get("resource_type") or "", ""),
            "last_label": RESULT_LABELS.get(row.get("last_judged_result"),
                                            row.get("last_judged_result") or ""),
            "action_available": False,
            "unavailable_note": None,
        }
        try:
            view = build_view(item_id, contentpack_path)        # 内含 CORE 门禁
            entry.update({"text": view["word"], "phonetic": view.get("phonetic"),
                          "part_of_speech": view.get("part_of_speech"),
                          "meaning_zh": view.get("meaning_zh"),
                          "kind": view["item_type"],
                          "kind_label": KIND_LABELS.get(view["item_type"], ""),
                          "action_available": True})
        except svc.LearningServiceError:
            # 安全回退：能显示教材文本就显示，不能就不臆测；绝不显示内部 ID，也不删除池数据
            entry["text"] = row.get("knowledge_name")
            entry["unavailable_note"] = "这项内容当前不能从这个入口再次学习。"
        grouped.setdefault(row.get("issue_type"), []).append(entry)
    sections = [{"issue_type": key, "title": ISSUE_TITLES[key], "items": grouped[key]}
                for key in ISSUE_ORDER if grouped.get(key)]
    return {"sections": sections,
            "total": sum(len(section["items"]) for section in sections)}


# --------------------------------------------------------------------------
# 页面渲染（沿用工作台的样式体系）
# --------------------------------------------------------------------------

STYLE = """
  :root{--bg:#f6f7f9;--card:#fff;--line:#e3e6ea;--text:#1f2328;--muted:#6b7280;
        --ok:#1a7f37;--rej:#b42318;--warn:#9a6700;--blue:#0969da;}
  *{box-sizing:border-box}
  body{margin:0;font:14px/1.6 -apple-system,Segoe UI,Microsoft YaHei,sans-serif;color:var(--text);background:var(--bg)}
  header{background:#fff;border-bottom:1px solid var(--line);padding:10px 16px}
  header h1{margin:0;font-size:16px}
  .meta{color:var(--muted);font-size:12px}
  main{padding:12px;display:flex;justify-content:center}
  .panel{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:18px;width:100%;max-width:560px}
  .badge{font-size:11px;padding:1px 6px;border-radius:10px;border:1px solid var(--line);background:#fafbfc;color:var(--muted)}
  .badge.core{background:#eef7ee;color:#1a7f37;border-color:#cfe8cf}
  h2{font-size:30px;margin:6px 0 2px;text-align:center;letter-spacing:.01em}
  .phon{text-align:center;color:var(--muted);font-family:ui-monospace,Consolas,monospace}
  .pos{text-align:center;color:var(--muted)}
  .mean{text-align:center;font-size:20px;margin:14px 0 6px}
  hr{border:0;border-top:1px solid var(--line);margin:18px 0}
  .src{color:var(--muted);font-size:13px}
  .src b{color:var(--text)}
  .btns{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px;justify-content:center}
  button{font:inherit;padding:7px 14px;border-radius:6px;border:1px solid var(--line);background:#fff;cursor:pointer}
  button.pri{background:#0969da;color:#fff;border-color:#0969da}
  .center{text-align:center}
  input{font:inherit;width:100%;padding:6px;border:1px solid var(--line);border-radius:6px}
  .field{margin:10px 0}
  .field label{display:block;color:var(--muted);font-size:13px;margin-bottom:4px}
  .banner{background:#fff8e5;border:1px solid #f0d999;color:#7a5b00;padding:6px 10px;border-radius:6px;margin:0 0 12px;font-size:13px}
  .err{background:#fdf2f2;border:1px solid #f3c9c9;color:#b42318;padding:6px 10px;border-radius:6px;margin:0 0 12px;font-size:13px}
  .stat{border:1px solid var(--line);border-radius:6px;padding:8px 10px;background:#fcfcfd;margin-top:8px;font-size:13px}
  .sect{font-size:15px;margin:16px 0 4px}
  .item{border:1px solid var(--line);border-radius:6px;padding:8px 10px;background:#fcfcfd;margin-top:8px}
  .item .w{font-size:18px;font-weight:600}
  .item form{margin-top:6px}
"""


def page(title, body) -> str:
    return ("<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            "<title>%s</title>\n<style>%s</style>\n</head>\n<body>\n"
            "<header><h1>教材语言资源学习</h1>"
            "<div class=\"meta\">教材是主线 · 孩子自己选择要学的内容 · 不使用 AI · 不自动选词</div></header>\n"
            "<main>%s</main>\n</body></html>\n" % (html.escape(title), STYLE, body))


def render_search_page(error=None, name_default="", word_default="", kind_default=KIND_VOCABULARY) -> str:
    err = '<div class="err">%s</div>' % html.escape(error) if error else ""
    kind_default = kind_default if kind_default in KINDS else KIND_VOCABULARY
    options = "\n      ".join(
        '<option value="%s"%s>%s</option>' % (k, " selected" if k == kind_default else "",
                                              html.escape(KIND_LABELS[k])) for k in KINDS)
    body = """<div class="panel">
  <div class="banner">请自己输入你要学的内容并选择类型。系统不会替你挑选单词，也不会自动进入下一条。</div>
  %s
  <form method="post" action="/start" autocomplete="off">
    <div class="field"><label for="name">你的名字</label>
      <input id="name" name="name" value="%s" placeholder="请输入名字" required></div>
    <div class="field"><label for="kind">要学的内容类型</label>
      <select id="kind" name="kind">
      %s
      </select></div>
    <div class="field"><label for="word">要学的单词 / 短语 / 句型</label>
      <input id="word" name="word" value="%s" placeholder="例如 %s" required></div>
    <div class="btns"><button class="pri" type="submit">开始学习</button></div>
  </form>
</div>
<div class="panel" style="margin-top:12px">
  <div class="banner">当前需要再学——查看你上一次回忆为「忘了」或「模糊」的词。系统只列出事实，学不学由你自己决定。</div>
  <form method="post" action="/pool" autocomplete="off">
    <div class="field"><label for="pool_name">你的名字</label>
      <input id="pool_name" name="name" value="%s" placeholder="请输入名字" required></div>
    <div class="btns"><button type="submit">看看我需要再学的词</button></div>
  </form>
</div>""" % (err, html.escape(name_default), options, html.escape(word_default),
              html.escape(KIND_EXAMPLES[kind_default]), html.escape(name_default))
    return page("教材语言资源学习", body)


def render_pool_page(name, view=None, notice=None, error=None) -> str:
    """当前需要再学（P1-11-C2）：只读展示当前错误 / 当前薄弱，孩子自己选择是否再学。"""
    err = '<div class="err">%s</div>' % html.escape(error) if error else ""
    note = '<div class="banner">%s</div>' % html.escape(notice) if notice else ""
    view = view or {"sections": [], "total": 0}
    if view["total"]:
        counts = " ｜ ".join("%s %d 条" % (section["title"], len(section["items"]))
                             for section in view["sections"])
        blocks = ['<div class="stat">共 %d 条：%s</div>' % (view["total"], html.escape(counts))]
        for section in view["sections"]:
            label = ISSUE_LABELS.get(section["issue_type"], "")
            blocks.append('<div class="sect">%s（上次回忆：%s）</div>'
                          % (html.escape(section["title"]), html.escape(label)))
            for item in section["items"]:
                lines = ['<div class="w">%s</div>'
                         % html.escape(item["text"] or "（这项教材内容当前无法显示）")]
                if item.get("phonetic"):
                    lines.append('<div class="phon" style="text-align:left">%s</div>'
                                 % html.escape(item["phonetic"]))
                if item.get("part_of_speech") or item.get("meaning_zh"):
                    pos = ("%s. " % item["part_of_speech"]) if item.get("part_of_speech") else ""
                    lines.append('<div>%s</div>'
                                 % html.escape("%s%s" % (pos, item.get("meaning_zh") or "")))
                meta = "上次：%s" % item["last_label"]
                if item["kind_label"]:
                    meta = "%s ｜ %s" % (item["kind_label"], meta)
                lines.append('<div class="meta">%s</div>' % html.escape(meta))
                if item["action_available"]:
                    lines.append("""<form method="post" action="/start">
      <input type="hidden" name="name" value="%s">
      <input type="hidden" name="item_id" value="%s">
      <div class="btns" style="margin-top:6px"><button class="pri" type="submit">再学这个词</button></div>
    </form>""" % (html.escape(name), html.escape(item["item_id"] or "")))
                elif item.get("unavailable_note"):
                    lines.append('<div class="meta">%s</div>' % html.escape(item["unavailable_note"]))
                blocks.append('<div class="item">%s</div>' % "\n      ".join(lines))
        body_block = "\n  ".join(blocks)
    else:
        body_block = ('<div class="stat">当前没有需要再学的词。</div>'
                      '<div class="meta" style="margin-top:8px">'
                      '这里只显示最近一次回忆为「忘了」或「模糊」的词；'
                      '没有这样的词时，这里就是空的。</div>')
    body = """<div class="panel">
  <div class="meta center">%s · 当前需要再学</div>
  %s
  %s
  <div class="banner" style="margin-top:12px">%s</div>
  %s
  <div class="btns" style="margin-top:16px">
    <a href="/"><button type="button">回首页</button></a>
  </div>
</div>""" % (html.escape(name or "你"), err, note, html.escape(POOL_NOTE), body_block)
    return page("当前需要再学", body)


def render_word_page(view, session_id, learner_id, learner_name, notice=None) -> str:
    lines = ['<h2>%s</h2>' % html.escape(view["word"])]
    if view.get("phonetic"):
        lines.append('<div class="phon">%s</div>' % html.escape(view["phonetic"]))
    if view.get("part_of_speech"):
        lines.append('<div class="pos">%s.</div>' % html.escape(view["part_of_speech"]))
    if view.get("meaning_zh"):
        lines.append('<div class="mean">%s</div>' % html.escape(view["meaning_zh"]))
    if view.get("tag"):
        # 「重点词」只用于 Vocabulary（教材加粗事实）；Phrase/SP 一律不显示（P1-10-C2 §十一）
        lines.append('<div class="center"><span class="badge core">%s</span></div>'
                     % html.escape(view["tag"]))
    lines.append("<hr>")
    lines.append('<div class="src">教材来源<br><b>%s</b></div>' % html.escape(view["source_label"] or "—"))
    note = '<div class="banner">%s</div>' % html.escape(notice) if notice else ""
    body = """<div class="panel">
  <div class="meta center">%s · 本次学习</div>
  %s
  %s
  <form method="post" action="/study">
    <input type="hidden" name="session_id" value="%s">
    <input type="hidden" name="learner_id" value="%s">
    <input type="hidden" name="item_id" value="%s">
    <div class="btns"><button class="pri" type="submit">我学好了</button></div>
  </form>
  <div class="btns"><a href="/"><button type="button">%s</button></a></div>
  <div class="meta center" style="margin-top:12px">学习完成由你自己决定；系统不会自动记录、不会自动进入下一条。</div>
</div>""" % (html.escape(learner_name), note, "\n  ".join(lines),
              html.escape(session_id), html.escape(learner_id), html.escape(view["item_id"]),
              html.escape(view.get("switch_label") or "换一个单词"))
    return page(view["word"], body)


def render_recall_page(view, session_id, learner_id, learner_name, reveal=False, notice=None) -> str:
    """Recall 页（P1-09-C3 / P1-10-C2）：先隐藏中文释义；显示释义不产生记录。"""
    label = view.get("recall_label") or "Vocabulary Recall"
    lines = ['<h2>%s</h2>' % html.escape(view["word"])]
    if view.get("phonetic"):
        lines.append('<div class="phon">%s</div>' % html.escape(view["phonetic"]))
    if view.get("part_of_speech"):
        lines.append('<div class="pos">%s.</div>' % html.escape(view["part_of_speech"]))
    lines.append('<div class="meta center" style="margin-top:6px">'
                 '%s</div>' % html.escape(view.get("recall_hint")
                                          or "先自己想一遍它的意思；想不起来也没关系。"))
    lines.append("<hr>")
    if reveal:
        lines.append('<div class="mean">%s</div>' % html.escape(view["meaning_zh"] or ""))
        lines.append('<div class="meta center">教材释义已显示</div>')
        reveal_block = ('<div class="stat">查看释义只是帮你核对，'
                        '不会产生任何学习记录。</div>')
    else:
        reveal_block = """<form method="post" action="/recall">
    <input type="hidden" name="session_id" value="%s">
    <input type="hidden" name="learner_id" value="%s">
    <input type="hidden" name="item_id" value="%s">
    <div class="btns"><button type="submit">显示释义</button></div>
  </form>""" % (html.escape(session_id), html.escape(learner_id), html.escape(view["item_id"]))
    choice_buttons = "\n      ".join(
        '<button type="submit" name="result" value="%s">%s</button>' % (html.escape(value), html.escape(label))
        for value, label in RECALL_CHOICES)
    note = '<div class="banner">%s</div>' % html.escape(notice) if notice else ""
    body = """<div class="panel">
  <div class="meta center">%s · %s</div>
  %s
  %s
  %s
  <hr>
  <div class="center">你现在回忆得怎么样？</div>
  <form method="post" action="/practice">
    <input type="hidden" name="session_id" value="%s">
    <input type="hidden" name="learner_id" value="%s">
    <input type="hidden" name="item_id" value="%s">
    <div class="btns">
      %s
    </div>
  </form>
  <div class="meta center" style="margin-top:12px">%s</div>
</div>""" % (html.escape(learner_name), html.escape(label), note, "\n  ".join(lines), reveal_block,
              html.escape(session_id), html.escape(learner_id), html.escape(view["item_id"]),
              choice_buttons, html.escape(RECALL_NOTE))
    return page("%s · %s" % (label, view["word"]), body)


def render_result_page(view, record, mastery, learner_name, practice_record=None, notice=None) -> str:
    label = RESULT_LABELS.get((practice_record or {}).get("result"))
    mastery_line = "学习证据 0 次（不代表掌握）"
    if mastery:
        last = RESULT_LABELS.get(mastery["last_result"], mastery["last_result"] or "—")
        mastery_line = ("学习证据 %s 次（不代表掌握） ｜ 其中判为「记得」 %s 次 ｜ 最近一次记录：%s"
                        % (mastery["evidence_count"], mastery["correct_count"], last))
    recall_stat = ('<div class="stat">回忆：%s（practice · %s）</div>'
                   % (html.escape(label), html.escape(practice_record["result"]))
                   ) if (practice_record and label) else ""
    recall_note = ('<div class="meta center" style="margin-top:8px">%s</div>'
                   % html.escape(RECALL_NOTE)) if practice_record else ""
    notice_block = '<div class="banner">%s</div>' % html.escape(notice) if notice else ""
    mean_block = ('<div class="mean">%s</div>' % html.escape(view["meaning_zh"])
                  ) if view.get("meaning_zh") else ""
    body = """<div class="panel">
  <div class="meta center">%s · 本次学习</div>
  %s
  <h2>%s</h2>
  %s
  <hr>
  <div class="stat">本次学习：已记录（study · done）</div>
  %s
  <div class="stat">%s</div>
  %s
  <div class="src" style="margin-top:12px">教材来源<br><b>%s</b></div>
  <div class="btns">
    <a href="/"><button type="button" class="pri">%s</button></a>
  </div>
  <form method="post" action="/pool" style="margin-top:12px">
    <input type="hidden" name="name" value="%s">
    <div class="btns"><button type="submit">看看我还需要再学的词</button></div>
  </form>
  <div class="meta center" style="margin-top:12px">本次学习到此结束。是否继续学习由你自己决定。</div>
</div>""" % (html.escape(learner_name), notice_block, html.escape(view["word"]),
              mean_block, recall_stat, html.escape(mastery_line),
              recall_note, html.escape(view["source_label"] or "—"),
              html.escape(view.get("restart_label") or "再学一个单词"),
              html.escape(learner_name))
    return page(view["word"], body)


# --------------------------------------------------------------------------
# HTTP 服务（仅本机 127.0.0.1）
# --------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    db_path = LEARNING_DB
    contentpack_path = CONTENTPACK

    def _send(self, code, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _html(self, text, code=200):
        self._send(code, text.encode("utf-8"), "text/html; charset=utf-8")

    def _conn(self):
        return svc.connect_learning_db(self.db_path)

    def _form(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._html(render_search_page())
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        form = self._form()
        if path == "/start":
            return self._start(form)
        if path == "/study":
            return self._study(form)
        if path == "/recall":
            return self._recall(form)
        if path == "/practice":
            return self._practice(form)
        if path == "/pool":
            return self._pool(form)
        self._send(404, b"not found", "text/plain; charset=utf-8")

    # ---- 明确的业务动作 -------------------------------------------------
    def _resolve_learner(self, conn, name):
        """按名字复用既有 Learner；不存在则显式创建（名字由用户输入并提交）。"""
        row = conn.execute(
            "SELECT learner_id FROM learner WHERE display_name=? AND status='active' "
            "ORDER BY created_at LIMIT 1", (name,)).fetchone()
        if row:
            return row["learner_id"]
        return svc.create_learner(conn, name)["learner_id"]

    def _pool(self, form):
        """P1-11-C2：当前需要再学（**只读**：不创建 Learner、不写任何记录）。"""
        name = (form.get("name") or "").strip()
        if not name:
            return self._html(render_pool_page("", error="请填写你的名字。"), 400)
        conn = self._conn()
        try:
            learner_id = find_learner_by_name(conn, name)
            if learner_id is None:
                return self._html(render_pool_page(
                    name, notice="还没有找到“%s”的学习记录——先学一个词，这里就会出现需要再学的词。"
                                 % name))
            view = build_pool_view(conn, learner_id, self.contentpack_path)
            self._html(render_pool_page(name, view=view))
        finally:
            conn.close()

    def _start(self, form):
        name = (form.get("name") or "").strip()
        word = (form.get("word") or "").strip()
        kind = (form.get("kind") or KIND_VOCABULARY).strip()
        item_id = (form.get("item_id") or "").strip()
        if item_id:
            # P1-11-C2 §十四/§十六：从「当前需要再学」点进来——按 item_id 解析教材内容，
            # 孩子不需要重新输入单词；仍然经过原有 CORE 学习门禁（§十五）。
            return self._start_from_item(name, item_id)
        if kind not in KINDS:
            return self._html(render_search_page("请选择要学的内容类型。", name, word, kind), 400)
        if not name or not word:
            return self._html(render_search_page("请填写你的名字和要学的内容。", name, word, kind), 400)
        if kind == KIND_VOCABULARY:
            item_id = find_vocabulary_item_id(word, self.contentpack_path)
        elif kind == KIND_PHRASE:
            item_id = find_phrase_item_id(word, self.contentpack_path)
        else:
            item_id = find_sentence_pattern_item_id(word, self.contentpack_path)
        if item_id is None:
            return self._html(render_search_page(
                "教材%s表中没有找到“%s”。%s" % (KIND_LABELS[kind], word, KIND_HINTS[kind]),
                name, word, kind), 404)
        conn = self._conn()
        try:
            try:
                view = build_view(item_id, self.contentpack_path)      # 门禁在构造内（CORE）
            except svc.LearningServiceError:
                if kind == KIND_VOCABULARY:
                    message = "“%s”不是教材重点词（认识即可的词），第一版只支持重点词。" % word
                else:
                    message = ("“%s”不是教材重点%s（学习要求不是重点），本阶段只支持教材重点%s。"
                               % (word, KIND_LABELS[kind], KIND_LABELS[kind]))
                return self._html(render_search_page(
                    message, name, word, kind), 400)
            self._begin_study(conn, name, item_id, view)
        finally:
            conn.close()

    def _start_from_item(self, name, item_id):
        """池入口：按 item_id 直接进入既有 Vocabulary 学习流程（复用同一套 Session/Task/Activity）。"""
        if not name:
            return self._html(render_pool_page("", error="请填写你的名字。"), 400)
        conn = self._conn()
        try:
            try:
                view = build_view(item_id, self.contentpack_path)       # CORE 门禁不被绕过
            except svc.LearningServiceError:
                pool_view = build_pool_view(conn, find_learner_by_name(conn, name) or "",
                                            self.contentpack_path)
                return self._html(render_pool_page(
                    name, view=pool_view,
                    notice="这项内容当前不能从这个入口再次学习（它不是教材重点内容）。"))
            self._begin_study(conn, name, item_id, view)
        finally:
            conn.close()

    def _begin_study(self, conn, name, item_id, view):
        """创建 Session（+Task+TaskItem）并渲染学习页——两条入口共用同一段流程。"""
        learner_id = self._resolve_learner(conn, name)
        if view["item_type"] == KIND_VOCABULARY:
            started = voc.start_vocabulary_study(conn, learner_id, item_id,
                                                 entry_point=ENTRY_POINT,
                                                 contentpack_path=self.contentpack_path)
            session_id = started["session"]["session_id"]
        else:
            session = ses.create_learning_session(
                conn, learner_id, KIND_ENTRY_POINTS[view["item_type"]], [item_id],
                contentpack_path=self.contentpack_path)
            session_id = session["session_id"]
        self._html(render_word_page(view, session_id, learner_id, name))

    def _study(self, form):
        session_id = form.get("session_id") or ""
        learner_id = form.get("learner_id") or ""
        item_id = form.get("item_id") or ""
        conn = self._conn()
        try:
            session = ses.get_learning_session(conn, session_id, learner_id)
            view = build_view(item_id, self.contentpack_path)
            if view["item_type"] == KIND_VOCABULARY:
                out = voc.record_vocabulary_study(conn, session["session_id"], item_id,
                                                  learner_id=learner_id, result="done",
                                                  contentpack_path=self.contentpack_path)
            else:
                out = beh.record_study(conn, learner_id, session["task_id"], item_id,
                                       result="done", contentpack_path=self.contentpack_path)
            learner = svc.get_learner(conn, learner_id)
            if view.get("recall_available"):
                # P1-09-C3 §十一：Session 必须覆盖 Recall，**此处不结束会话**
                self._recall_page(conn, item_id, session["session_id"], learner_id, learner,
                                  reveal=False)
            else:
                # Phrase 无释义 / Sentence Pattern：本阶段不进 Recall，Study 后结束本次学习
                ses.end_learning_session(conn, session["session_id"], learner_id)
                self._html(render_result_page(
                    view, out["record"], svc.get_mastery(conn, learner_id, item_id),
                    learner["display_name"], notice=view.get("no_recall_note")))
        except svc.LearningServiceError as exc:
            self._html(render_search_page("本次学习未能记录：%s" % exc), 400)
        finally:
            conn.close()

    def _recall_page(self, conn, item_id, session_id, learner_id, learner, reveal=False, notice=None):
        """渲染 Recall 页（只读展示；不写任何学习记录）。"""
        view = build_view(item_id, self.contentpack_path)
        self._html(render_recall_page(view, session_id, learner_id, learner["display_name"],
                                      reveal=reveal, notice=notice))

    def _recall(self, form):
        """「显示释义」——纯粹展示动作，不产生 LearningRecord，也不产生 practice。"""
        session_id = form.get("session_id") or ""
        learner_id = form.get("learner_id") or ""
        item_id = form.get("item_id") or ""
        conn = self._conn()
        try:
            session = ses.get_learning_session(conn, session_id, learner_id)
            view = build_view(item_id, self.contentpack_path)
            if not view.get("recall_available"):
                return self._html(render_search_page("本次学习不做回忆自评。"), 400)
            learner = svc.get_learner(conn, learner_id)
            self._recall_page(conn, item_id, session["session_id"], learner_id, learner, reveal=True)
        except svc.LearningServiceError as exc:
            self._html(render_search_page("本次学习未能继续：%s" % exc), 400)
        finally:
            conn.close()

    def _practice(self, form):
        """孩子自评（记得 / 模糊 / 忘了）→ 恰好一条 practice 记录 → 结束 Session → 结果页。"""
        session_id = form.get("session_id") or ""
        learner_id = form.get("learner_id") or ""
        item_id = form.get("item_id") or ""
        result = (form.get("result") or "").strip()
        if result not in PRACTICE_RESULTS:
            return self._html(render_search_page("请点击「记得 / 模糊 / 忘了」中的一个。"), 400)
        conn = self._conn()
        try:
            session = ses.get_learning_session(conn, session_id, learner_id)
            view = build_view(item_id, self.contentpack_path)
            if view["item_type"] not in (KIND_VOCABULARY, KIND_PHRASE) or not view.get("recall_available"):
                return self._html(render_search_page("本次学习不做回忆自评。"), 400)
            learner = svc.get_learner(conn, learner_id)
            if session["ended_at"] is not None:
                # 重复提交（例如刷新页面）：只读重放，不再写入第二条记录
                practice = conn.execute(
                    "SELECT result FROM learning_record WHERE task_id=? AND item_id=? "
                    "AND activity_type='practice' ORDER BY created_at DESC, record_id DESC LIMIT 1",
                    (session["task_id"], item_id)).fetchone()
                if practice is None:
                    return self._html(render_search_page("本次学习已经结束。"), 400)
                return self._html(render_result_page(
                    view, {"result": "done"}, svc.get_mastery(conn, learner_id, item_id),
                    learner["display_name"], practice_record=dict(practice)))
            if view["item_type"] == KIND_VOCABULARY:
                out = voc.record_vocabulary_practice(conn, session["session_id"], item_id,
                                                     result=result, learner_id=learner_id,
                                                     contentpack_path=self.contentpack_path)
            else:
                out = beh.record_practice(conn, learner_id, session["task_id"], item_id,
                                          result=result, contentpack_path=self.contentpack_path)
            ses.end_learning_session(conn, session["session_id"], learner_id)
            mastery = svc.get_mastery(conn, learner_id, item_id)
            self._html(render_result_page(view, {"result": "done"}, mastery,
                                          learner["display_name"], practice_record=out["record"]))
        except svc.LearningServiceError as exc:
            self._html(render_search_page("本次回忆未能记录：%s" % exc), 400)
        finally:
            conn.close()

    def log_message(self, fmt, *args):
        pass


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="教材语言资源最小学习体验（本机页面）")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--db", default=str(LEARNING_DB), help="learning.db 路径（默认正式库）")
    args = ap.parse_args()

    Handler.db_path = Path(args.db)
    Handler.contentpack_path = CONTENTPACK
    if not Handler.db_path.exists():
        print("STOP: learning.db 不存在:", Handler.db_path)
        return 2
    if not CONTENTPACK.exists():
        print("STOP: contentpack v5 不存在:", CONTENTPACK)
        return 2

    url = "http://127.0.0.1:%d/" % args.port
    print("learning.db :", Handler.db_path)
    print("contentpack :", CONTENTPACK, "（只读）")
    print("打开:", url)
    print("说明：只支持教材重点内容（CORE）——单词 / 短语（Study+Recall）/ 句型（仅 Study）；"
          "不自动选词；不使用 AI；仅监听本机 127.0.0.1")
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as srv:
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())

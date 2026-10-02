#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P5 正式题库 → 学习调用层（只读筛选 + 复用既有学习服务写入）

职责（只做这一条链路，不重新设计任何已有机制）：

    questionbank → 候选题 → 学习范围（Unit） → 学习证据过滤 → 确定性排序
                → LearningSession（复用 session_service）
                → 作答判分 → LearningRecord（复用 learning_service）
                → mastery / pool（既有服务，只读）

严格边界：
  * **只读** questionbank.db 与 contentpack；不修改任何 schema / 正式数据；
  * 写入学习证据一律经既有 `learning_service.record_learning_event`（本模块不直接 INSERT）；
  * 学习证据的 item_id 必须是真实 contentpack `learning_item`：
    解析不到时**不伪造**，题目仍可被调用，但不产生 LearningRecord / mastery；
  * 排序确定性：无随机；同一会话内默认不重复同一 question_id；question_id 作为兜底键；
  * Unit 范围：本课检测 / 听音辨意 / 音标写词 / 跟读 = 当前 Unit；
               自主练习 = Starter + 已学连续前缀 + 当前 Unit（**绝不进入未来 Unit**）；
  * 候选默认过滤：`quality_status='PASS'` 且 `answer_status='RELIABLE'`；
  * 不调用 AI、不联网、不安装依赖。
"""

from __future__ import annotations

import json
import os
import re
import threading
import sqlite3
import sys
import unicodedata
from pathlib import Path

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
for _p in (str(BASE / "learning"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.dont_write_bytecode = True

import learning_service as svc            # noqa: E402
import questionbank_service as qb         # noqa: E402
import session_service as ses             # noqa: E402
import resource_pool_service as pool      # noqa: E402
import mastery_service as mastery         # noqa: E402
import evidence_resolver_service as _evidence_resolver   # noqa: E402  J1：题目 → 教材证据包

DEFAULT_LEARNING_DB = svc.DEFAULT_LEARNING_DB
DEFAULT_QUESTIONBANK = qb.DB_PATH
DEFAULT_CONTENTPACK = svc.DEFAULT_CONTENTPACK_DB
#: P8-Read-B：正式跟读资源池登记文件（只读追加源，不改变题库题源行为）
DEFAULT_SHADOWING_POOL = BASE / "structured" / "audio" / "resources" / "shadowing_pool_v1.json"
TEXTBOOK_ID = "FLTRP-EN-7A-2022CUR"

#: 六个入口（与产品总纲 V2.0 顺序一致；键沿用 Demo 既有 step key）
ENTRIES = ("read", "listen", "wordform", "check", "text", "practice")
ENTRY_ALIASES = {"跟读练习": "read", "听音辨意": "listen", "词形练习": "wordform",
                 "本课检测": "check", "听读课文": "text", "自主练习": "practice",
                 # 以下为 2026-09-30 合并前的旧入口名 → 统一归到 wordform（兼容）
                 "音标写词": "wordform", "词形变化": "wordform",
                 "phonetic": "wordform", "form": "wordform",
                 "vocab": "wordform"}
#: 听音辨意的模式（产品总纲 V2.0 §5.1；「听音写词」已删除，不得再作为独立入口/模块/开发目标）
MODES = ("word", "sentence")
#: 「词形练习」的内部模式（2026-09-30 合并：音标写词默认 + 词形变化）
WORDFORM_MODES = ("phonetic", "form")

#: 入口 → 允许的 question_type（None = 全部正式题型）
LISTEN_MODE_TYPES = {
    "word": ("vocab_listen_write",),
    "sentence": ("sentence_listen_choice", "sentence_listen_write",
                 "listen_choice", "listen_fill", "listening_choice"),
    # 「听音阅读」模式已于 2026-09-30 正式删除（当前无正式资源、无保留意义）。
}
#: 词形练习 → 各模式的允许 question_type
WORDFORM_MODE_TYPES = {
    "phonetic": ("vocab_phonetic_write", "phonetics_symbol_write"),
    "form": ("vocab_word_form",),
}
ENTRY_TYPES = {
    "read": (),                                     # 官方题库没有 repeat 型题目 → 只提供跟读素材
    "listen": tuple(dict.fromkeys(sum(LISTEN_MODE_TYPES.values(), ()))),
    # 词形练习（2026-09-30 合并）：模式 phonetic = 原「音标写词」；模式 form = 原「词形变化」
    "wordform": tuple(dict.fromkeys(sum(WORDFORM_MODE_TYPES.values(), ()))),
    # 听读课文：正文 + 官方音频，不走题目池（显隐由 formal_entries 特判）
    "text": (),
    "check": ("vocab_meaning_choice", "sentence_listen_write", "sentence_listen_choice",
              "reading_choice", "phrase_meaning_choice", "phonetics_sound_choice",
              "phonetics_symbol_write", "vocab_word_form", "vocab_context_choice",
              "textbook_native"),
    "practice": None,
}
#: 入口 → session_service 既有 entry_point 枚举（unit/section/activity/vocabulary/listening/reading）
ENTRY_POINT = {"read": "activity", "listen": "listening",
               # 2026-09-30：原 phonetic / form 合并为 wordform（旧 key 保留兼容）
               "wordform": "vocabulary", "phonetic": "vocabulary",
               "form": "vocabulary", "check": "unit", "practice": "unit"}
#: 入口 → 作答记录使用的 activity_type（只用既有 11 值）
ENTRY_ACTIVITY_TYPE = {"read": "repeat", "listen": "listen",
                       # 2026-09-30：合并后 wordform 的默认活动类型；造句型仍按题型映射
                       "wordform": "spell",
                       "phonetic": "spell", "form": "substitute",
                       "check": "recognize", "practice": "practice"}

#: reason 有限集合 + 资源池优先级（池优先级沿用 resource_pool_service）
REASONS = ("current_error", "current_weak", "not_started", "new", "mastered_skip")
REASON_PRIORITY = {"current_error": 0, "current_weak": 1, "not_started": 2,
                   "new": 3, "mastered_skip": 4}
UNIT_ORDER = ("Starter", "Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "Unit 6")
RESULTS = ("correct", "incorrect", "partial", "done")


# --------------------------------------------------------------------------- 基础设施

def connect_learning_db(path=DEFAULT_LEARNING_DB) -> sqlite3.Connection:
    """读写打开学习库（与既有服务同一实现；只读场景见 `connect_learning_db_ro`）。"""
    return svc.connect_learning_db(path)


def connect_learning_db_ro(path=DEFAULT_LEARNING_DB) -> sqlite3.Connection:
    conn = sqlite3.connect("file:%s?mode=ro" % Path(path).as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def connect_questionbank(path=DEFAULT_QUESTIONBANK) -> sqlite3.Connection:
    return qb.connect(path)


def connect_contentpack(path=DEFAULT_CONTENTPACK) -> sqlite3.Connection:
    return svc.connect_contentpack_db(path)


# --------------------------------------------------------------------------- J1：题目 → 教材证据包
#: J1（2026-09-29）：把题库的题关联到 `textbook_evidence_map_v1.json` 的证据包。
#: 实现全部在 `learning/evidence_resolver_service.py`（纯只读、粒度感知）；
#: 这里只做**薄转发**，让 `web/` 层继续只依赖本模块（与既有约定一致）。

def resolve_question_evidence(question, packages=None,
                              contentpack_path=DEFAULT_CONTENTPACK) -> dict:
    """题目 → {granularity, package, package_question_id, resolved_via, candidates}。

    详见 `evidence_resolver_service.resolve_question_evidence` 的文档；**只读**，不写任何库。
    """
    return _evidence_resolver.resolve_question_evidence(
        question, packages=packages, contentpack_path=contentpack_path)


def evidence_count_for_gate(resolution, granularity=None) -> int:
    """证据条数的上报口径（activity → 实际计数；section → 强制 1；否则 0）。"""
    return _evidence_resolver.evidence_count_for_gate(resolution, granularity)


#: P1（性能）：contentpack 只读连接的**线程局部复用**。
#: 实测背景：一次首页渲染会调用 `evidence_item_for()` 约 521 次，每次都新建连接；
#: cProfile 显示单次首页渲染开 671 次连接（Windows 893ms / 设备 4073ms）。
#: ThreadingHTTPServer 是"每请求一线程"且线程会被复用，因此用线程局部即可在同一请求内
#: 复用同一个**只读**连接；mode=ro 不持有写事务，跨请求复用安全，不产生脏读或锁竞争。
_LOCAL = threading.local()


def _ro_contentpack(path=DEFAULT_CONTENTPACK):
    """取本线程复用的 contentpack 只读连接（路径变化时自动重开）。

    调用方**不要**关闭返回的连接——它由本线程持有并复用。
    """
    key = str(path)
    conn = getattr(_LOCAL, "contentpack", None)
    if conn is None or getattr(_LOCAL, "contentpack_key", None) != key:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        conn = connect_contentpack(path)
        _LOCAL.contentpack = conn
        _LOCAL.contentpack_key = key
    return conn


def normalize_answer(text) -> str:
    """答案归一化 —— **与既有 `_same_word`（Demo 侧原规则）逐字等价**的实现：

    转小写 → 统一撇号 → 非字母数字（保留撇号与空格）替换为空格 → 压缩空白 → 去首尾空白。
    正式 learning 层不得依赖 `demo/`，因此该规则在本模块内实现，语义不放大也不缩小。
    """
    t = unicodedata.normalize("NFC", str(text or "")).lower()
    t = t.replace("\u2019", "'").replace("\u2018", "'")
    t = re.sub(r"[^a-z0-9' ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def same_answer(given, want) -> bool:
    """文本答案比较：与既有 `_same_word` 同语义（空答案不算正确，不做拼写纠错）。"""
    want_norm = normalize_answer(want)
    if not want_norm:
        return False
    return normalize_answer(given) == want_norm


def normalize_entry(entry) -> str:
    key = (entry or "").strip()
    key = ENTRY_ALIASES.get(key, key.lower())
    if key not in ENTRIES:
        raise ValueError("未知入口：%s（允许：%s）" % (entry, "/".join(ENTRIES)))
    return key


def allowed_types(entry, mode=None) -> tuple:
    """入口（＋内部模式）→ 允许的 question_type。

    `listen` 的 mode ∈ {word, sentence}；`wordform` 的 mode ∈ {phonetic, form}（默认 phonetic）。
    """
    key = normalize_entry(entry)
    if key == "listen":
        if mode in (None, ""):
            # 与 p5_mode_bar 的默认展示保持一致：无 mode 时使用 word。
            mode = "word"
        if mode not in LISTEN_MODE_TYPES:
            raise ValueError("未知听音辨意模式：%s（允许：%s）" % (mode, "/".join(MODES)))
        return LISTEN_MODE_TYPES[mode]
    if key == "wordform":
        if mode in (None, ""):
            mode = "phonetic"                      # 默认打开音标写词
        if mode not in WORDFORM_MODE_TYPES:
            raise ValueError("未知词形练习模式：%s（允许：%s）"
                             % (mode, "/".join(WORDFORM_MODES)))
        return WORDFORM_MODE_TYPES[mode]
    if mode not in (None, ""):
        raise ValueError("只有听音辨意（listen）/ 词形练习（wordform）支持 mode 参数")
    return ENTRY_TYPES[key] if ENTRY_TYPES[key] is not None else ()


# --------------------------------------------------------------------------- 学习范围

def _unit_index(unit_code):
    return UNIT_ORDER.index(unit_code) if unit_code in UNIT_ORDER else None


def item_unit(cp, item_id):
    """教材 item → Unit（只用既有正式关系，两条路径，均不猜测）：

    ① source_ref(activity) → activity → section → unit
    ② source_ref(content_block) → content_block.page_id → 教材印刷页 → unit 页区间
    """
    if not item_id:
        return None
    row = cp.execute(
        "SELECT u.unit_code FROM source_ref sr "
        "JOIN activity a ON a.activity_id = sr.source_id "
        "JOIN section s ON s.section_id = a.section_id "
        "JOIN unit u ON u.unit_id = s.unit_id "
        "WHERE sr.item_id = ? AND sr.source_type='activity' LIMIT 1", (item_id,)).fetchone()
    if row:
        return row["unit_code"]
    row = cp.execute(
        "SELECT p.textbook_page FROM source_ref sr "
        "JOIN content_block cb ON cb.block_id = sr.source_id "
        "JOIN page p ON p.page_id = cb.page_id "
        "WHERE sr.item_id = ? AND sr.source_type='content_block' AND p.textbook_page IS NOT NULL "
        "ORDER BY p.textbook_page LIMIT 1", (item_id,)).fetchone()
    if not row:
        return None
    tb = row["textbook_page"]
    for u in cp.execute("SELECT unit_code, textbook_page_start AS s, textbook_page_end AS e "
                        "FROM unit WHERE unit_code <> 'Appendix'"):
        if u["s"] and u["e"] and u["s"] <= tb <= u["e"]:
            return u["unit_code"]
    return None


# --------------------------------------------------------------------------- Section 级学习进度（P6-B-9）

APPENDIX_UNIT = "Appendix"


def section_index(cp) -> dict:
    """只读 Section 归属索引（供 `locate_section()` / `item_teaching_sections()` 复用）。

    规则与既有正式实现**同源**（不新建第二套映射算法）：
      * `resource_pool_service._enrich_from_contentpack()`：pdf 页 → unit 页区间 →
        该 unit 内 `section.pdf_page_start <= 页` 的最后一条 Section；
      * `web/content._section_bounds()`：同一页区间的另一种表达（Section 起始页排序）。
    Appendix 不是教学 Unit，其 Section 不参与学习进度。

    入参 `cp` 必须是已打开的 **只读** contentpack 连接（`connect_contentpack()`）。
    """
    units = [dict(r) for r in cp.execute(
        "SELECT unit_id, unit_code, pdf_page_start, pdf_page_end FROM unit "
        "WHERE unit_code <> ? ORDER BY pdf_page_start", (APPENDIX_UNIT,))]
    sections = {}
    sections_by_id = {}
    for r in cp.execute(
            "SELECT s.section_id, s.section_key, s.pdf_page_start, u.unit_code, u.unit_id "
            "FROM section s JOIN unit u ON u.unit_id = s.unit_id "
            "ORDER BY s.unit_id, s.pdf_page_start"):
        row = dict(r)
        sections.setdefault(row["unit_id"], []).append(row)
        sections_by_id[row["section_id"]] = row
    return {
        "units": units,
        "sections": sections,
        "sections_by_id": sections_by_id,
        "activities": {r["activity_id"]: r["section_id"]
                       for r in cp.execute("SELECT activity_id, section_id FROM activity")},
        "blocks": {r["block_id"]: r["pdf_page"] for r in cp.execute(
            "SELECT cb.block_id, p.pdf_page FROM content_block cb "
            "JOIN page p ON p.page_id = cb.page_id")},
    }


def locate_section(pdf_page, index: dict):
    """pdf 页 → (unit_code, section_key)；Appendix 页或无归属页返回 None（不猜测）。"""
    if pdf_page is None:
        return None
    for u in index["units"]:
        lo = u["pdf_page_start"] or 0
        hi = u["pdf_page_end"] or 10 ** 6
        if lo <= pdf_page <= hi:
            best = None
            for s in index["sections"].get(u["unit_id"], []):
                if (s["pdf_page_start"] or 0) <= pdf_page:
                    best = s
                else:
                    break
            return (u["unit_code"], best["section_key"]) if best else None
    return None


def item_teaching_sections(item_id, cp, index: dict) -> set:
    """教材 item → **候选教学 Section 集合**（与 `item_unit()` 同源的三条正式路径）：

      ① `source_ref(activity)` → `activity.section_id` → `section` → `unit`
      ② `source_ref(content_block)` → `content_block.page_id` → `page.pdf_page`
      ③ `source_ref(textbook_page)` → `source_id`（`…:P<页码>`）→ pdf 页

    返回去重集合；无法定位的引用不计入；Appendix 位置不计入（Unit 级资源）。
    """
    if not item_id:
        return set()
    out = set()
    for r in cp.execute("SELECT source_type, source_id FROM source_ref WHERE item_id = ?",
                        (item_id,)):
        stype, sid = r["source_type"], r["source_id"]
        if stype == "activity":
            sec = index["sections_by_id"].get(index["activities"].get(sid))
            if sec and sec["unit_code"] != APPENDIX_UNIT:
                out.add((sec["unit_code"], sec["section_key"]))
        elif stype == "content_block":
            loc = locate_section(index["blocks"].get(sid), index)
            if loc:
                out.add(loc)
        elif stype == "textbook_page":
            m = re.search(r"P(\d+)", str(sid) or "")
            loc = locate_section(int(m.group(1)) if m else None, index)
            if loc:
                out.add(loc)
    return out


def learned_sections(learner_id, learning_db=DEFAULT_LEARNING_DB,
                     contentpack_path=DEFAULT_CONTENTPACK, conn=None) -> set:
    """**已学 Section 集合**（动态推导，零新增字段）：{(unit_code, section_key)}。

    * 事实来源：`learning_record`（该学习者全部记录，不看 result/activity_type）＋ contentpack 正式关系；
    * 只收录**可唯一定位到某一教学 Section** 的 item：
      - Unit 级资源（词表 / 短语 / 附录语言运用等，只有附录页位置）**不进入**本集合；
      - 若某 item 同时指向多个教学 Section（当前正式数据为 0 条），为保证确定性与不猜测，**不收录**；
    * 语义：该 Section **曾发生过有效学习行为**；**不表示已掌握**（掌握见 `mastery_state` / `evidence_service`）；
    * 只读：不写 learning.db、不新增表 / 字段 / 迁移。
    """
    if not learner_id:
        return set()
    owns_conn = conn is None
    conn = conn or connect_learning_db_ro(learning_db)
    try:
        item_ids = [r["item_id"] for r in conn.execute(
            "SELECT DISTINCT item_id FROM learning_record WHERE learner_id = ?", (learner_id,))]
    finally:
        if owns_conn:
            conn.close()
    if not item_ids:
        return set()
    cp = connect_contentpack(contentpack_path)
    try:
        index = section_index(cp)
        out = set()
        for item_id in item_ids:
            secs = item_teaching_sections(item_id, cp, index)
            if len(secs) == 1:
                out |= secs
        return out
    finally:
        cp.close()


def learned_prefix_from_evidence(conn, learner_id, contentpack_path=DEFAULT_CONTENTPACK) -> tuple:
    """已学教材范围 = **Starter + 到最远已学 Unit 的连续前缀**（由正式学习证据重算，不读 Cookie）。

    证据来源：learning_record 里的 item_id（唯一正式学习行为记录）。

    注意（P6-B-9）：这是既有 Unit 级口径，**不再作为自主练习的正式范围来源**；
    Section 级进度见本模块 `learned_sections()`。其它功能若仍在使用它，保持不变。
    """
    rows = conn.execute("SELECT DISTINCT item_id FROM learning_record WHERE learner_id=?",
                        (learner_id,)).fetchall()
    cp = connect_contentpack(contentpack_path)
    try:
        far = -1
        for r in rows:
            idx = _unit_index(item_unit(cp, r["item_id"]))
            if idx is not None and idx > far:
                far = idx
    finally:
        cp.close()
    if far < 0:
        return ()
    return tuple(UNIT_ORDER[:far + 1])


def unit_scope(entry, current_unit, learned_prefix=()) -> tuple:
    """入口 → 允许出现的 Unit 集合（绝不包含未来 Unit）。"""
    key = normalize_entry(entry)
    cur_idx = _unit_index(current_unit)
    if cur_idx is None:
        raise ValueError("current_unit 非法：%s（允许：%s）" % (current_unit, "/".join(UNIT_ORDER)))
    if key != "practice":
        return (current_unit,)
    units = ["Starter"]
    for u in learned_prefix or ():
        if u in UNIT_ORDER and _unit_index(u) <= cur_idx and u not in units:
            units.append(u)
    if current_unit not in units:
        units.append(current_unit)
    return tuple(sorted(units, key=_unit_index))


# --------------------------------------------------------------------------- 题目 → 证据 item

def _exercise_item_for_activity(cp, activity_id):
    if not activity_id:
        return None
    row = cp.execute("SELECT item_id FROM source_ref WHERE source_type='activity' AND source_id=? "
                     "ORDER BY item_id LIMIT 1", (activity_id,)).fetchone()
    return row["item_id"] if row else None


def evidence_item_for(question, contentpack_path=DEFAULT_CONTENTPACK, qb_path=DEFAULT_QUESTIONBANK):
    """题目 → 学习证据 item（真实 contentpack learning_item）。解析不到返回 None，绝不猜测。

    顺序：① source_item_id → ② activity_id → exercise item
          → ③ content_block → page → activity → exercise item → ④ 多候选按 Unit 消歧
    """
    q = question if isinstance(question, dict) else qb.get_question(question, path=qb_path)
    if not q:
        return None
    # P1：复用本线程的只读连接（不关闭）；避免每题一次 connect（实测单次首页 521 次）
    cp = _ro_contentpack(contentpack_path)
    try:
        def _valid(item_id):
            if not item_id:
                return None
            row = cp.execute("SELECT item_id FROM learning_item WHERE item_id=?", (item_id,)).fetchone()
            return row["item_id"] if row else None

        item = _valid(q.get("source_item_id"))
        if item:
            return item
        item = _valid(_exercise_item_for_activity(cp, q.get("activity_id")))
        if item:
            return item
        blocks = [a["asset_id"] for a in
                  qb.evidence_for(q["question_id"], path=qb_path) if a["asset_kind"] == "content_block"]
        # `source_item_id` 有时是 content_block（例如 Phonetics 题），一并作为块证据使用
        src = q.get("source_item_id")
        if src and cp.execute("SELECT 1 FROM content_block WHERE block_id=?", (src,)).fetchone():
            blocks.append(src)
        if not blocks:
            return None
        pages = [int(r["page_id"].split(":P")[1]) for b in blocks
                 for r in [cp.execute("SELECT page_id FROM content_block WHERE block_id=?", (b,)).fetchone()]
                 if r is not None]
        cand = []
        for p in dict.fromkeys(pages):
            for r in cp.execute("SELECT activity_id FROM activity WHERE pdf_page=?", (p,)):
                it = _valid(_exercise_item_for_activity(cp, r["activity_id"]))
                if it and it not in cand:
                    cand.append(it)
        if len(cand) == 1:
            return cand[0]
        if len(cand) > 1:                                   # ④ 按 Unit 消歧
            same_unit = [c for c in cand if item_unit(cp, c) == q.get("unit_code")]
            if len(same_unit) == 1:
                return same_unit[0]
        return None
    finally:
        pass          # P1：连接由 _ro_contentpack 复用，此处**不关闭**


# --------------------------------------------------------------------------- 候选与排序

def _row_filters(q):
    """题目正式性过滤（默认口径，不因稀缺而放宽）。

    ai_eval 例外（2026-09-29 修正）：`answer_kind == "ai_eval"` 的题**设计上就没有可靠答案**
    （`answer_json = None`、`answer_status = NO_RELIABLE_SOURCE`），其判分本应走 **AI 批改路径**
    而不是规则比对。把它按 "answer_status == RELIABLE" 排除属于**逻辑错误**（把"走 AI 批改的题"
    当成"无答案的坏题"），故此处按 `answer_kind` 精确放行。

    安全性：判据用 `answer_kind`（不是 `answer_status`），实测二者完全不相交——
    `answer_status = NO_RELIABLE_SOURCE` 仅含 `ai_eval`(241) 与 `self_assess`(276)，
    因此**不会**顺带放行 `self_assess`（孩子自评题，不走 AI 批改）。
    可达性仍由各入口的 `allowed_types()` 独立决定：`ai_eval` 的 `question_type` 全为
    `textbook_native`，仅出现在 `check` 白名单内，故其它入口天然取不到，无需额外限制。
    """
    if q.get("quality_status") != "PASS":
        return False
    if q.get("answer_kind") == "ai_eval":
        return True                                  # 无可靠答案 → 走 AI 批改，不是坏题
    return q.get("answer_status") == "RELIABLE"


def _pool_state(conn, learner_id):
    if not learner_id:
        return {}
    return {i["item_id"]: i["issue_type"] for i in pool.list_current_issue_pool(conn, learner_id)}


def _mastery_state(conn, learner_id, item_id):
    if not learner_id or not item_id:
        return None
    return mastery.evaluate(conn, learner_id, item_id)


def _item_has_record(conn, learner_id, item_id):
    if not learner_id or not item_id:
        return False
    row = conn.execute("SELECT 1 FROM learning_record WHERE learner_id=? AND item_id=? LIMIT 1",
                       (learner_id, item_id)).fetchone()
    return row is not None


def select_questions(entry, current_unit, learner_id=None, mode=None, focus=None, limit=None,
                     learned_prefix=None, learning_db=DEFAULT_LEARNING_DB,
                     questionbank_path=DEFAULT_QUESTIONBANK, contentpack_path=DEFAULT_CONTENTPACK,
                     conn=None) -> list:
    """候选题（确定性排序，返回 [{question, reason, evidence_item_id, priority, ...}]）。

    过滤顺序：入口允许题型 → focus 缩放 → Unit 范围 → 正式性（PASS/RELIABLE）
              → 证据排序（error > weak > not_started > new > mastered_skip）。
    """
    key = normalize_entry(entry)
    types = list(allowed_types(key, mode))
    if focus:
        if types and focus not in types:
            return []
        types = [focus] if not types else [t for t in types if t == focus]
    if key in ("read", "form") and not types:
        return []                                        # 无正式题型：不造题
    if key == "practice" and not types:
        types = list({r["question_type"] for r in
                      qb.connect(questionbank_path).execute(
                          "SELECT DISTINCT question_type FROM question "
                          "WHERE quality_status='PASS' AND answer_status='RELIABLE'")})

    owns_conn = conn is None
    conn = conn or connect_learning_db_ro(learning_db)
    try:
        if learned_prefix is None and learner_id:
            learned_prefix = learned_prefix_from_evidence(conn, learner_id, contentpack_path)
        units = unit_scope(key, current_unit, learned_prefix or ())
        pool_map = _pool_state(conn, learner_id)
        cands = []
        for unit in units:
            for q in qb.questions_for_unit(unit, path=questionbank_path):
                if q["question_type"] not in types:
                    continue
                if not _row_filters(q):
                    continue
                item = evidence_item_for(q, contentpack_path, questionbank_path)
                if item and pool_map.get(item) == pool.CURRENT_ERROR:
                    reason = "current_error"
                elif item and pool_map.get(item) == pool.CURRENT_WEAK:
                    reason = "current_weak"
                elif item and not _item_has_record(conn, learner_id, item):
                    reason = "not_started"
                elif item:
                    st = _mastery_state(conn, learner_id, item)
                    reason = "mastered_skip" if (st and st["stable"]) else "new"
                else:
                    reason = "new"                        # 无证据 item：可调用，但不产生掌握证据
                cands.append({
                    "question_id": q["question_id"], "unit_code": q["unit_code"],
                    "question_type": q["question_type"], "reason": reason,
                    "priority": REASON_PRIORITY[reason], "evidence_item_id": item,
                    "question": q,
                })
        cands.sort(key=lambda c: (c["priority"], _unit_index(c["unit_code"]) or 0,
                                  c["question_type"], c["question_id"]))
        return cands[:limit] if limit else cands
    finally:
        if owns_conn:
            conn.close()


def shadowing_pool_entries(pool_path=DEFAULT_SHADOWING_POOL) -> list:
    """正式跟读资源池（P8-Read-B 登记文件，只读）。

    文件缺失/不可解析时返回空列表 —— 既有跟读行为完全不受影响。
    """
    try:
        data = json.loads(Path(pool_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for e in data.get("entries") or []:
        if not e.get("text") or e.get("start_ms") is None or e.get("end_ms") is None:
            continue
        out.append({"resource_id": e.get("resource_id"), "unit_code": e.get("unit_code"),
                    "audio_url": e.get("audio_url") or "/audio/official/%s.mp3" % e.get("audio_code"),
                    "start_ms": int(e["start_ms"]), "end_ms": int(e["end_ms"]),
                    "segment_id": e.get("segment_id"), "text": e.get("text"),
                    "content_block": e.get("content_block"),
                    "verification_status": e.get("verification_status"),
                    "served_by": e.get("served_by"), "pool_role": e.get("pool_role")})
    return out


def shadowing_materials(current_unit, limit=None, questionbank_path=DEFAULT_QUESTIONBANK,
                        shadowing_pool_path=DEFAULT_SHADOWING_POOL, section_key=None,
                        contentpack_path=DEFAULT_CONTENTPACK) -> list:
    """跟读素材：正式题库里**已有官方音频区间**的句子题 + 正式跟读资源池（同句不重复供给）。

    P8-Read-B 起追加读取 `structured/audio/resources/shadowing_pool_v1.json`：
      * 题库题源部分行为与返回顺序完全不变（既有 143 条仍然是前 143 条）；
      * 资源池条目按教材句归一化文本去重，已在题源里出现的句子不再重复返回；
      * 没有登记文件时等价于原行为。

    P6-B-11b：新增**可选** `section_key`（不传 → 行为与上面完全一致，向后兼容）——
    只保留**当前 `(unit_code, section_key)`** 的 Section 级跟读 / 阅读资源：
      * 题库题源按 `question.section_key` 精确命中；
      * 资源池条目按 `content_block → page.pdf_page → section` 定位（与
        `item_teaching_sections()` 同一套正式来源，不新建第二套映射）；
      * 定位不到明确 Section 的一律不返回 —— **不 fallback 到整个 Unit、其他 Section
        或其他题型**；当前 Section 确实没有资源时就是空池。
    """
    idx = None
    if section_key:
        cp = connect_contentpack(contentpack_path)
        try:
            idx = section_index(cp)
        finally:
            cp.close()
    out = []
    served_keys = set()
    for q in qb.questions_for_unit(current_unit, path=questionbank_path):
        if q["question_type"] not in ("sentence_listen_write", "sentence_listen_choice"):
            continue
        p = q.get("prompt") or {}
        if not p.get("audio_url") or p.get("start_ms") is None:
            continue
        if idx is not None and (q.get("section_key") or "") != section_key:
            continue
        ans = q.get("answer") or {}
        out.append({"question_id": q["question_id"], "unit_code": q["unit_code"],
                    "audio_url": p["audio_url"], "start_ms": p["start_ms"], "end_ms": p["end_ms"],
                    "segment_id": p.get("segment_id"), "text": ans.get("text"),
                    "sentence_uid": p.get("sentence_uid"),
                    "evidence_item_id": evidence_item_for(q, qb_path=questionbank_path)})
        served_keys.add(normalize_answer(ans.get("text")))
        if limit and len(out) >= limit:
            break
    for e in shadowing_pool_entries(shadowing_pool_path):
        if e["unit_code"] != current_unit:
            continue
        if idx is not None and locate_section(idx["blocks"].get(e.get("content_block")),
                                              idx) != (current_unit, section_key):
            continue
        if normalize_answer(e["text"]) in served_keys:      # 同一教材句不重复供给
            continue
        served_keys.add(normalize_answer(e["text"]))
        out.append({"question_id": e["resource_id"], "unit_code": e["unit_code"],
                    "audio_url": e["audio_url"], "start_ms": e["start_ms"], "end_ms": e["end_ms"],
                    "segment_id": e["segment_id"], "text": e["text"],
                    "sentence_uid": e["resource_id"],
                    "content_block": e["content_block"],
                    "source": "shadowing_pool",
                    "verification_status": e["verification_status"],
                    "evidence_item_id": None})
        if limit and len(out) >= limit:
            break
    return out


# --------------------------------------------------------------------------- 会话与作答

def start_practice_session(entry, current_unit, learner_id, mode=None, focus=None, limit=None,
                           learning_db=DEFAULT_LEARNING_DB, questionbank_path=DEFAULT_QUESTIONBANK,
                           contentpack_path=DEFAULT_CONTENTPACK):
    """建会话：复用 session_service（Session → Task → TaskItem），不新建任何 schema。

    只有能解析到真实教材 item 的候选才会成为 task_item（不伪造 item）。
    """
    key = normalize_entry(entry)
    cands = select_questions(key, current_unit, learner_id, mode=mode, focus=focus, limit=limit,
                             learning_db=learning_db, questionbank_path=questionbank_path,
                             contentpack_path=contentpack_path)
    item_ids, seen = [], set()
    for c in cands:
        if c["evidence_item_id"] and c["evidence_item_id"] not in seen:
            seen.add(c["evidence_item_id"])
            item_ids.append(c["evidence_item_id"])
    conn = connect_learning_db(learning_db)
    try:
        session = None
        if item_ids:
            session = ses.create_learning_session(conn, learner_id, ENTRY_POINT[key], item_ids,
                                                  contentpack_path=contentpack_path)
        return {"entry": key, "unit_scope": unit_scope(key, current_unit,
                                                       learned_prefix_from_evidence(
                                                           conn, learner_id, contentpack_path)),
                "session": session, "questions": cands,
                "task_item_count": len(item_ids),
                "questions_without_evidence_item":
                    [c["question_id"] for c in cands if not c["evidence_item_id"]]}
    finally:
        conn.close()


def grade_answer(question, picked):
    """判分（只用既有可靠规则）：option_key 精确比较；文本用归一化比较。

    P6-A / V1.3 §七·9：`answer_kind == "ai_eval"` 的题**没有可靠答案事实**
    （questionbank 里 answer_status = NO_RELIABLE_SOURCE，answer_json 为空）。
    规范要求「不存在可靠答案事实时：**不判分**，状态进入 NEEDS_REVIEW」——
    因此这里直接返回 `("needs_review", None)`，**不再落入文本比较分支**。
    修正前该分支会令 want=None -> normalize_answer(picked) 或 same_answer(picked, None)
    -> **恒返回 incorrect**（实测 4/4 题、4 种输入全部 incorrect）——即"永远答错"。
    `needs_review` **不是** RESULTS 成员（RESULTS 只含 correct/incorrect/partial/done），
    也不会被写入 learning_record —— 见 record_answer 的早返回。
    """
    if question.get("answer_kind") == "ai_eval":
        return "needs_review", None
    answer = (question.get("answer") or {})
    kind = question.get("answer_kind")
    if kind == "option_key":
        want = answer.get("key")
        if picked is None:
            return "incorrect", None
        got = str(picked).strip()
        options = question.get("options") or []
        if got.lower() not in [o["key"] for o in options]:
            for o in options:                                 # 允许直接传选项文本
                if normalize_answer(o["text"]) == normalize_answer(got):
                    got = o["key"]
                    break
        return ("correct" if got == want else "incorrect"), got
    want = answer.get("text")
    # 音标类答案含 IPA 符号：既有 ASCII 归一化会把符号清空，因此改用"符号精确比较"
    # （只在既有规则无法表达时使用，属该题型的必要补充，不是第二套通用归一化）。
    if want and not normalize_answer(want):
        def _sym(t):
            t = str(t or "").strip().replace("[", "/").replace("]", "/").replace("\uff0f", "/")
            return re.sub(r"\s+", "", t)
        return ("correct" if _sym(picked) == _sym(want) else "incorrect"), None
    if not normalize_answer(picked):
        return "incorrect", None
    return ("correct" if same_answer(picked, want) else "incorrect"), None


def session_served_question_ids(conn, session_id, learner_id=None) -> set:
    """会话内已出现过的 question_id（从既有 LearningRecord.response_raw 反读，不新建状态表）。"""
    session = ses.get_learning_session(conn, session_id, learner_id)
    rows = conn.execute("SELECT response_raw FROM learning_record WHERE task_id=?",
                        (session["task_id"],)).fetchall()
    out = set()
    for r in rows:
        try:
            payload = json.loads(r["response_raw"] or "{}")
        except ValueError:
            continue
        qid = payload.get("question_id")
        if qid:
            out.add(qid)
    return out


def record_answer(session_id, question_id, picked, learner_id=None, force_result=None,
                  hints_used=0, activity_type=None, learning_db=DEFAULT_LEARNING_DB,
                  questionbank_path=DEFAULT_QUESTIONBANK, contentpack_path=DEFAULT_CONTENTPACK):
    """作答 → 判分 → LearningRecord（只经既有 learning_service 写入）。

    * 能解析到真实教材 item → 写 LearningRecord（result ∈ correct/incorrect/partial/done）；
    * 解析不到（112 题）→ **不写任何记录**（既有写入接口要求真实 contentpack item，
      不伪造 item、不产生 mastery），只把判分结果返回给调用方。
    """
    q = qb.get_question(question_id, path=questionbank_path)
    if not q:
        return {"recorded": False, "reason": "question_not_found", "question_id": question_id}
    result, normalized_pick = grade_answer(q, picked)
    if result == "needs_review":
        # V1.3 §七·9：NEEDS_REVIEW 是**题目状态**，不是学习结果 ——
        # 不写 LearningRecord、不产生 mastery（"发生过作答行为"而非"判过对错"）。
        return {"recorded": False, "reason": "needs_review", "question_id": question_id,
                "result": "needs_review", "evidence_item_id": None, "response_raw": None,
                "note": "该题没有可靠答案事实（answer_kind=ai_eval）：暂不判分，等待 AI 批改"}
    if force_result is not None:
        if force_result not in RESULTS:
            raise ValueError("result 必须是 %s 之一" % (RESULTS,))
        result = force_result
    item = evidence_item_for(q, contentpack_path, questionbank_path)
    payload = json.dumps({"question_id": question_id, "question_type": q["question_type"],
                          "unit_code": q["unit_code"], "picked": None if picked is None else str(picked),
                          "normalized_pick": normalized_pick, "result": result,
                          "evidence_item_id": item, "source": "p4_questionbank"}, ensure_ascii=False)
    if not item:
        return {"recorded": False, "reason": "no_evidence_item", "question_id": question_id,
                "result": result, "evidence_item_id": None, "response_raw": payload,
                "note": "该题暂无正式教材 item 归属：可作答，但不产生 LearningRecord/mastery"}
    conn = connect_learning_db(learning_db)
    try:
        session = ses.get_learning_session(conn, session_id, learner_id)
        task_items = {r["item_id"] for r in svc.list_task_items(conn, session["task_id"])}
        if item not in task_items:                   # 该题不在本会话的 task 里：不写、不报错
            return {"recorded": False, "reason": "item_not_in_session_task",
                    "question_id": question_id, "result": result, "evidence_item_id": item,
                    "response_raw": payload,
                    "note": "该题的教材 item 不属于本会话 TaskItem；请用本会话候选中的题作答"}
        act = activity_type or ENTRY_ACTIVITY_TYPE_BY_TYPE.get(q["question_type"], "practice")
        if act not in svc.ACTIVITY_TYPES:
            raise ValueError("activity_type 必须是 %s 之一" % (svc.ACTIVITY_TYPES,))
        out = svc.record_learning_event(conn, session["learner_id"], session["task_id"], item,
                                        act, result=result, response_raw=payload,
                                        hints_used=hints_used, contentpack_path=contentpack_path)
        return {"recorded": True, "session_id": session_id, "question_id": question_id,
                "result": result, "evidence_item_id": item, "activity_type": act,
                "record": out["record"], "mastery": out["mastery"], "response_raw": payload}
    finally:
        conn.close()


def record_shadowing(session_id, question_id, learner_id=None, learning_db=DEFAULT_LEARNING_DB,
                     questionbank_path=DEFAULT_QUESTIONBANK, contentpack_path=DEFAULT_CONTENTPACK,
                     evidence_item_id=None):
    """跟读完成：`activity_type='repeat'` + `result='done'`（**不产生判断证据**）。

    `done` 在既有 evidence_service 规则下不是有效判断证据（`EVIDENCE_RESULTS` 不含 done），
    因此不会把"跟读完成"当成 correct/incorrect 掌握证据；不需要 item 归属时也不写记录
    （不伪造 item）。

    2026-10-01 新增 `evidence_item_id`（可选）：
      跟读**词**池的 `question_id` 是合成 id（`word:<hash>`）**不在题库**，
      此时 `record_answer` 第一步就 `question_not_found` ⇒ 跟读永远写不进记录。
      调用方（app）已从候选池拿到该词的**真实 learning_item id**，直接传进来即可。
      走本支路时**仍然**执行 `record_answer` 的两条关键校验：
        ① item 必须属于本会话的 TaskItem；② item 教材必须与会话教材一致。
      任一不满足即**不写**（返回 recorded=False），与既有语义一致 —— 不伪造。
    """
    if evidence_item_id:
        conn = connect_learning_db(learning_db)
        try:
            session = ses.get_learning_session(conn, session_id, learner_id)
            task_items = {r["item_id"] for r in svc.list_task_items(conn, session["task_id"])}
            if evidence_item_id not in task_items:
                return {"recorded": False, "reason": "item_not_in_session_task",
                        "question_id": question_id, "evidence_item_id": evidence_item_id,
                        "note": "该词的教材 item 不属于本会话 TaskItem"}
            payload = json.dumps({"question_id": question_id, "picked": None,
                                  "result": "done", "evidence_item_id": evidence_item_id,
                                  "source": "p5_read_shadowing"}, ensure_ascii=False)
            out = svc.record_learning_event(conn, session["learner_id"], session["task_id"],
                                            evidence_item_id, "repeat", result="done",
                                            response_raw=payload,
                                            contentpack_path=contentpack_path)
            return {"recorded": True, "session_id": session_id, "question_id": question_id,
                    "result": "done", "evidence_item_id": evidence_item_id,
                    "activity_type": "repeat", "record": out["record"],
                    "mastery": out["mastery"], "response_raw": payload}
        finally:
            conn.close()
    return record_answer(session_id, question_id, picked=None, learner_id=learner_id,
                         force_result="done", activity_type="repeat", learning_db=learning_db,
                         questionbank_path=questionbank_path, contentpack_path=contentpack_path)


def next_question(session_id, entry, current_unit, learner_id=None, mode=None, focus=None,
                  allow_repeat_on_evidence=True, served_question_ids=None,
                  learning_db=DEFAULT_LEARNING_DB,
                  questionbank_path=DEFAULT_QUESTIONBANK, contentpack_path=DEFAULT_CONTENTPACK):
    """会话内确定性推进：同一 question_id 默认不重复；错题/薄弱题可按既有证据规则重新进入。

    "已出现过"的题 = 调用方传入的 `served_question_ids`（同一次会话里已返回给孩子的题）
    ∪ 既有 LearningRecord.response_raw 里能读到的 question_id（已作答的题）。
    本模块不新增任何会话状态表。
    """
    conn = connect_learning_db_ro(learning_db)
    try:
        served = session_served_question_ids(conn, session_id, learner_id)
        if served_question_ids:
            served = set(served) | set(served_question_ids)
        cands = select_questions(entry, current_unit, learner_id, mode=mode, focus=focus,
                                learning_db=learning_db, questionbank_path=questionbank_path,
                                contentpack_path=contentpack_path, conn=conn)
        for c in cands:
            if c["question_id"] not in served:
                return c
            if allow_repeat_on_evidence and c["reason"] in ("current_error", "current_weak"):
                return c
        return None
    finally:
        conn.close()


#: 题型 → activity_type（既有 11 值；入口缺省值见 ENTRY_ACTIVITY_TYPE）
ENTRY_ACTIVITY_TYPE_BY_TYPE = {
    "vocab_listen_write": "listen", "vocab_meaning_choice": "recognize",
    "vocab_phonetic_write": "spell", "vocab_word_form": "substitute",
    "vocab_context_choice": "recognize",
    "sentence_listen_write": "listen", "sentence_listen_choice": "listen",
    "listen_choice": "listen", "listen_fill": "listen", "listening_choice": "listen",
    "reading_choice": "read", "phrase_meaning_choice": "recognize",
    "phonetics_sound_choice": "recognize", "phonetics_symbol_write": "spell",
    "textbook_native": "understand",
}

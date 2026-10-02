#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-12-C3-C1 正式 Web UI —— 只读内容读取层

职责：为正式 Web UI 提供**只读**的展示数据。

  - 教材信息与资源数量：读 contentpack v5（`mode=ro`，绝不写入）
  - 学习者与"需要再学"：读 learning.db（**只读连接**，绝不写入、绝不产生学习记录）

边界（P1-12-C3-C1 §八）：
  - 不重写、不复制 learning/ 下任何冻结业务逻辑；
  - 需要业务判定时直接调用现有 service（例如 resource_pool_service 的只读池）；
  - 本模块**没有任何写操作**，也不产生学习记录。
"""

from __future__ import annotations

import os

import json
import sqlite3
import re
import sys
from pathlib import Path

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
LEARNING_DB = BASE / "structured" / "learning" / "learning.db"
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"

sys.path.insert(0, str(BASE / "learning"))
sys.dont_write_bytecode = True


def _ro(path) -> sqlite3.Connection:
    """只读连接（正式数据一律 mode=ro）。"""
    conn = sqlite3.connect("file:%s?mode=ro" % Path(path).as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_textbook(contentpack_path=CONTENTPACK) -> dict:
    """教材基本信息 + 真实资源数量（全部来自 contentpack v5，不硬编码业务事实）。"""
    cp = _ro(contentpack_path)
    try:
        tb = cp.execute(
            "SELECT textbook_id, publisher, title, grade, volume, curriculum_standard, "
            "edition_label FROM textbook_edition LIMIT 1").fetchone()
        counts = {
            "unit": cp.execute("SELECT COUNT(*) FROM unit").fetchone()[0],
            "section": cp.execute("SELECT COUNT(*) FROM section").fetchone()[0],
            "activity": cp.execute("SELECT COUNT(*) FROM activity").fetchone()[0],
            "item": cp.execute("SELECT COUNT(*) FROM learning_item").fetchone()[0],
            "vocabulary": cp.execute(
                "SELECT COUNT(*) FROM learning_item WHERE item_type='vocabulary'").fetchone()[0],
            "phrase": cp.execute(
                "SELECT COUNT(*) FROM learning_item WHERE item_type='phrase'").fetchone()[0],
            "sentence_pattern": cp.execute(
                "SELECT COUNT(*) FROM learning_item WHERE item_type='sentence_pattern'"
            ).fetchone()[0],
            "vocabulary_core": cp.execute(
                "SELECT COUNT(*) FROM learning_item WHERE item_type='vocabulary' "
                "AND learning_requirement='CORE'").fetchone()[0],
        }
    finally:
        cp.close()
    return {"textbook": dict(tb) if tb else None, "counts": counts}


def list_learners(learning_db=LEARNING_DB) -> list:
    """本机已有学习者（只读；正式库为空时返回空列表）。"""
    conn = _ro(learning_db)
    try:
        return [dict(r) for r in conn.execute(
            "SELECT learner_id, display_name FROM learner WHERE status='active' "
            "ORDER BY created_at, learner_id")]
    finally:
        conn.close()


def read_pool_summary(learner_id, learning_db=LEARNING_DB,
                      contentpack_path=CONTENTPACK) -> dict:
    """"需要再学"汇总（只读）：直接复用冻结的 resource_pool_service，不复制任何池规则。"""
    import resource_pool_service as pool
    conn = pool.connect_learning_db(learning_db)          # 该模块内部即 mode=ro
    try:
        return pool.summarize_pool(conn, learner_id, contentpack_path=contentpack_path)
    finally:
        conn.close()


def home_context(learning_db=LEARNING_DB, contentpack_path=CONTENTPACK,
                 learner_id=None) -> dict:
    """首页上下文：教材信息 + 需要再学 + 最近学过。

    P1-13-C1（C4-08）：**优先使用传入的当前学习者**（来自 Cookie）。
    若没有当前学习者，则如实显示空状态——**不猜测**数据库里的其它学习者，
    也不创建任何学习者。
    """
    textbook = read_textbook(contentpack_path)
    learners = list_learners(learning_db)
    pool = {"current_error_count": 0, "current_weak_count": 0, "total": 0}
    learner_name = None
    if learner_id:
        for learner in learners:
            if learner["learner_id"] == learner_id:
                learner_name = learner["display_name"]
                summary = read_pool_summary(learner_id, learning_db, contentpack_path)
                pool = {"current_error_count": summary.get("current_error_count", 0),
                        "current_weak_count": summary.get("current_weak_count", 0),
                        "total": summary.get("total", 0)}
                break
    return {
        "textbook": textbook["textbook"],
        "counts": textbook["counts"],
        "learner_count": len(learners),
        "learner_name": learner_name,
        "pool": pool,
        # 最近学过：正式库为空时为 0（不伪造数据；只读查询接口属后续阶段）
        "recent_count": 0,
    }


# ---------------------------------------------------------------------------
# P1-12-C3-C2 教材导航：教材中心 → Unit → 资源列表（全部只读）
# ---------------------------------------------------------------------------

#: 正式产品的三种教材语言资源（顺序即页面展示顺序）
RESOURCE_KINDS = (("vocabulary", "词汇"), ("phrase", "短语"),
                  ("sentence-pattern", "句型"))
RESOURCE_KIND_ITEM_TYPE = {"vocabulary": "vocabulary", "phrase": "phrase",
                           "sentence-pattern": "sentence_pattern"}


# ---------------------------------------------------------------- P2-6-F-1 教材正文（只读）

#: 正文页排除的块（页眉 / 页脚 / 侧栏不出现在正文里）
_TEXT_SKIP_ROLE = ("footer", "sidebar")
_TEXT_SKIP_KIND = ("footer_text", "sidebar_tip")


def unit_text_sections(slug, contentpack_path=CONTENTPACK):
    """教材正文（Dialogue / Text / Reading）：按 Unit → Section 确定性读取（只读）。

    规则（P2-6-F-1 / V1.2.1 六·8）：
      * 只读 contentpack `content_block`，不改写教材原文；
      * 板块归属只用「section 起始页 + 单元页范围」这一确定性依据；
      * 页眉 / 页脚 / 侧栏不进入正文；
      * 不做活动级切分（同页跨活动的精确切分属于 NEEDS_REVIEW，见 P2-6-F-0-A）。
    """
    unit = get_unit(slug, contentpack_path)
    if not unit:
        return None
    cp = _ro(contentpack_path)
    try:
        urow = cp.execute(
            "SELECT unit_id, unit_code, title, pdf_page_start, pdf_page_end, "
            "textbook_page_start, textbook_page_end FROM unit WHERE unit_code=?",
            (unit["unit_code"],)).fetchone()
        if urow is None:
            return None
        secs = cp.execute(
            "SELECT section_id, title, section_key, pdf_page_start, textbook_page_start "
            "FROM section WHERE unit_id=? ORDER BY pdf_page_start", (urow["unit_id"],)).fetchall()
        if not secs:
            return None
        start, end = urow["pdf_page_start"] or 1, urow["pdf_page_end"] or 999
        bounds = [s["pdf_page_start"] or start for s in secs] + [end + 1]
        pages = list(range(start, end + 1))
        marks = ",".join("?" * len(pages))
        rows = cp.execute(
            "SELECT block_id, page_id, block_kind, layout_role, reading_order, text_raw "
            "FROM content_block WHERE page_id IN (%s) ORDER BY page_id, reading_order" % marks,
            ["FLTRP-EN-7A-2022CUR:P%d" % p for p in pages]).fetchall()
    finally:
        cp.close()

    by_page = {}
    for r in rows:
        text = (r["text_raw"] or "").strip()
        if not text:
            continue
        if r["layout_role"] in _TEXT_SKIP_ROLE or r["block_kind"] in _TEXT_SKIP_KIND:
            continue
        if re.fullmatch(r"[\d\s\W]{0,6}", text) or re.fullmatch(r"[A-Za-z]{1,8}", text):
            continue                      # 活动号 / 图片标签等排版标记
        try:
            pageno = int(r["page_id"].rsplit("P", 1)[-1])
        except ValueError:
            continue
        by_page.setdefault(pageno, []).append(
            {"block_id": r["block_id"], "kind": r["block_kind"], "text": text})

    sections = []
    for i, s in enumerate(secs):
        lo, hi = bounds[i], bounds[i + 1] - 1
        blocks = []
        for p in range(lo, hi + 1):
            blocks.extend(by_page.get(p, []))
        if not blocks:
            continue
        sections.append({"section_id": s["section_id"], "title": s["title"],
                         "section_key": s["section_key"],
                         "page_start": lo, "page_end": hi, "blocks": blocks})
    return {"unit_code": urow["unit_code"], "title": urow["title"],
            "textbook_page_start": urow["textbook_page_start"],
            "textbook_page_end": urow["textbook_page_end"],
            "sections": sections,
            "block_count": sum(len(s["blocks"]) for s in sections)}


# ---------------------------------------------------------------- Phase 1 教材音频热点（只读）

EXERCISE_CATALOG_V3 = BASE / "structured" / "exercises" / "exercise_catalog_v3.json"

_SENT_QUOTE_MAP = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
                   "\u2013": "-", "\u2014": "-", "\u00a0": " "}


def normalize_sentence(text: str) -> str:
    """只读比对用的确定性归一化（引号/空白），不修改任何教材原文。"""
    out = "".join(_SENT_QUOTE_MAP.get(ch, ch) for ch in (text or ""))
    return re.sub(r"\s+", " ", out).strip()


def _section_bounds(secs, pdf_start, pdf_end):
    """把 section 起始页转成 [start, end] 区间（确定性，只用 contentpack 的页范围）。"""
    starts = [s["pdf_page_start"] or pdf_start for s in secs]
    out = []
    for i, s in enumerate(secs):
        lo = starts[i]
        hi = (starts[i + 1] - 1) if i + 1 < len(starts) else pdf_end
        out.append((lo, hi, s["section_key"]))
    return out


def unit_audio_resources(unit_code: str, contentpack_path=CONTENTPACK) -> dict:
    """Phase 1：教材原文音频热点所需的只读数据（不写任何表、不猜时间、不改教材）。

    句子级（正式）：contentpack `audio_sentence_annotation` 中 status='VERIFIED'
    且 start_ms / end_ms 有效的句子 —— 直接作为跟读资源入口。
    活动级（回退）：`structured/exercises/exercise_catalog_v3.json` 中
    audio_status='CONFIRMED' 的教材活动音频（整段，不是句子切分）。
    """
    empty = {"unit_code": unit_code, "sentences": [], "activities": []}
    cp = _ro(contentpack_path)
    try:
        urow = cp.execute(
            "SELECT unit_id, unit_code, pdf_page_start, pdf_page_end FROM unit "
            "WHERE unit_code=?", (unit_code,)).fetchone()
        if urow is None:
            return empty
        secs = cp.execute(
            "SELECT section_key, pdf_page_start FROM section WHERE unit_id=? "
            "ORDER BY pdf_page_start", (urow["unit_id"],)).fetchall()
        page_map = {r["textbook_page"]: r["pdf_page"] for r in cp.execute(
            "SELECT pdf_page, textbook_page FROM page WHERE textbook_page IS NOT NULL")}
        rows = cp.execute(
            "SELECT sentence_uid, audio_id, activity, source_page, sentence_text, "
            "start_ms, end_ms, sentence_index FROM audio_sentence_annotation "
            "WHERE status='VERIFIED' AND start_ms IS NOT NULL AND end_ms IS NOT NULL "
            "AND unit=? ORDER BY audio_id, start_ms, sentence_index", (unit_code,)).fetchall()
    finally:
        cp.close()

    pdf_start = urow["pdf_page_start"] or 1
    pdf_end = urow["pdf_page_end"] or pdf_start
    bounds = _section_bounds(secs, pdf_start, pdf_end)

    def section_of(pdf_page):
        for lo, hi, key in bounds:
            if pdf_page is not None and lo <= pdf_page <= hi:
                return key
        return None

    def page_of(source_page):
        m = re.search(r"PDF\s*p(\d+)", source_page or "", re.I)
        if m:
            return int(m.group(1))
        m = re.search(r"p(\d+)", source_page or "")
        if m:
            return page_map.get(int(m.group(1)))
        return None

    sentences = []
    for r in rows:
        code = (r["audio_id"] or "").split(":")[-1].upper()
        pdf_page = page_of(r["source_page"])
        sentences.append({
            "sentence_uid": r["sentence_uid"], "audio_code": code,
            "audio_url": "/audio/official/%s.mp3" % code,
            "text": r["sentence_text"], "norm": normalize_sentence(r["sentence_text"]),
            "start_ms": int(r["start_ms"]), "end_ms": int(r["end_ms"]),
            # Demo V2：段落点读需要判断“同一活动内序号是否连续”
            "sentence_index": r["sentence_index"],
            "source_page": r["source_page"], "activity": r["activity"],
            "pdf_page": pdf_page, "section_key": section_of(pdf_page)})

    activities = []
    try:
        catalog = json.loads(Path(EXERCISE_CATALOG_V3).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        catalog = {}
    for a in (catalog.get("activities") or []):
        if a.get("unit") != unit_code or not a.get("audio_id"):
            continue
        if a.get("audio_status") != "CONFIRMED":
            continue
        code = str(a["audio_id"]).split(":")[-1].upper()
        activities.append({
            "activity_id": a.get("activity_id"), "audio_code": code,
            "audio_url": "/audio/official/%s.mp3" % code,
            "activity_no": a.get("activity_no"), "instruction": a.get("instruction") or "",
            "pdf_page": a.get("pdf_page"), "textbook_page": a.get("textbook_page"),
            "section_key": a.get("section")})
    return {"unit_code": unit_code, "sentences": sentences, "activities": activities}


# ------------------------------------------------ 教材正文展示范围（只读；P6-B-12 最小整改）

#: 只有该状态的官方音频 alignment 才能作为教材正文的展示依据（V1.1 §7A / V1.3 §29·13）
TEXT_DISPLAY_STATUSES = ("VERIFIED",)


def _blocks_by_section(unit_code: str, block_ids, contentpack_path=CONTENTPACK) -> dict:
    """把 block_id 按 contentpack 的 Section 页范围归组（只读；与 unit_text_sections 同一口径）。

    只用正式 ID 与页范围，不做文本匹配：block_id → page.pdf_page → section 页区间。
    """
    if not block_ids:
        return {}
    cp = _ro(contentpack_path)
    try:
        urow = cp.execute(
            "SELECT unit_id, pdf_page_start, pdf_page_end FROM unit WHERE unit_code=?",
            (unit_code,)).fetchone()
        if urow is None:
            return {}
        secs = cp.execute(
            "SELECT section_key, pdf_page_start FROM section WHERE unit_id=? "
            "ORDER BY pdf_page_start", (urow["unit_id"],)).fetchall()
        if not secs:
            return {}
        ids = sorted(block_ids)
        pages = {}
        chunk = 500
        for i in range(0, len(ids), chunk):
            part = ids[i:i + chunk]
            marks = ",".join("?" * len(part))
            for r in cp.execute(
                    "SELECT b.block_id, p.pdf_page FROM content_block b "
                    "JOIN page p ON p.page_id = b.page_id WHERE b.block_id IN (%s)" % marks,
                    part):
                pages[r["block_id"]] = r["pdf_page"]
    finally:
        cp.close()
    bounds = _section_bounds(secs, urow["pdf_page_start"] or 1, urow["pdf_page_end"] or 999)
    out = {}
    for block_id in ids:
        page = pages.get(block_id)
        if page is None:
            continue
        for lo, hi, key in bounds:
            if lo <= page <= hi:
                out.setdefault(key, set()).add(block_id)
                break
    return {key: frozenset(value) for key, value in out.items()}


def audio_covered_block_ids(unit_code: str, contentpack_path=CONTENTPACK,
                            statuses=TEXT_DISPLAY_STATUSES) -> dict:
    """教材正文展示范围（只读）：官方音频 alignment 中 status=VERIFIED 的 content_block。

    返回 {section_key: frozenset(block_id)}，供教材原文页只展示"能与官方音频可靠对应"的正文。

    边界（P6-B-12 最小整改）：
      * 数据来源只有 structured/audio/resources/audio_resource_v1.json
        （经 learning.audio_resource_service 只读读取；不改数据、不新增结构、不写回 JSON）；
      * 只认 segment 明确给出的 text_resource_id（== content_block.block_id），
        不做文本模糊匹配、不重算 ASR / alignment；
      * 默认只取 VERIFIED；PARTIAL / NEED_MANUAL_CONFIRMATION / 无映射一律不作为正文展示依据；
      * 活动级 CONFIRMED 音频（exercise_catalog_v3）不参与本判断，也不能反向证明某块有对应；
      * 取不到任何 VERIFIED 块时返回空 dict —— 调用方按"空 Section"处理，不猜测、不补齐。
    """
    import audio_resource_service as ars          # learning/（content 顶部已把该目录加入 sys.path）

    wanted = tuple(str(s).upper() for s in (statuses or ()))
    if not wanted:
        return {}
    covered = set()
    for res in ars.list_resources():
        if (res.get("unit_code") or "") != unit_code:
            continue
        for seg in res.get("segments") or []:
            if seg.get("text_resource_kind") != "content_block":
                continue
            if (seg.get("status") or "").upper() not in wanted:
                continue
            block_id = seg.get("text_resource_id")
            if block_id:
                covered.add(block_id)
    return _blocks_by_section(unit_code, covered, contentpack_path)


def textbook_pages(contentpack_path=CONTENTPACK) -> dict:
    """PDF 页 → 教材印刷页 的映射（只读；用于原书点读页显示页码）。"""
    cp = _ro(contentpack_path)
    try:
        return {r["pdf_page"]: r["textbook_page"]
                for r in cp.execute("SELECT pdf_page, textbook_page FROM page "
                                    "WHERE textbook_page IS NOT NULL")}
    finally:
        cp.close()


def kind_label(kind: str) -> str:
    for key, label in RESOURCE_KINDS:
        if key == kind:
            return label
    return ""


def unit_slug(unit_code: str) -> str:
    """URL 用的单元标识（由教材自身的 unit_code 派生，非数据库内部 ID）。"""
    return re.sub(r"[^a-z0-9]+", "", (unit_code or "").lower())


def list_units(contentpack_path=CONTENTPACK) -> list:
    """教材真实单元列表，按教材自然顺序（印刷页码由小到大）稳定排序。"""
    cp = _ro(contentpack_path)
    try:
        rows = cp.execute(
            "SELECT unit_id, unit_code, title, pdf_page_start, pdf_page_end, "
            "textbook_page_start, textbook_page_end FROM unit "
            "ORDER BY pdf_page_start, unit_id").fetchall()
    finally:
        cp.close()
    return [{"slug": unit_slug(r["unit_code"]), "unit_code": r["unit_code"],
             "title": r["title"], "textbook_page_start": r["textbook_page_start"],
             "textbook_page_end": r["textbook_page_end"],
             # Demo V1.2：原书点读需要 PDF 页范围（同一张表里已有的真实数据）
             "pdf_page_start": r["pdf_page_start"],
             "pdf_page_end": r["pdf_page_end"]} for r in rows]


def get_unit(slug, contentpack_path=CONTENTPACK):
    """按 slug 取一个单元（不存在返回 None）。"""
    slug = (slug or "").strip().lower()
    for unit in list_units(contentpack_path):
        if unit["slug"] == slug:
            return unit
    return None


def list_units_with_sections(contentpack_path=CONTENTPACK) -> list:
    """教材真实目录（Unit → Section）：**全部真实 Section，不做任何题库过滤**。

    只读 contentpack：`unit` + `section`（`section.unit_id → unit.unit_id`），
    Section 按教材页顺序（`pdf_page_start`）排列；不重解析 PDF、不新增目录数据。
    用途：首页「当前课时」选择器（Unit 作分组标题，Section 作可选项）。
    """
    cp = _ro(contentpack_path)
    try:
        unit_rows = [dict(r) for r in cp.execute(
            "SELECT unit_id, unit_code, title, pdf_page_start, pdf_page_end, "
            "textbook_page_start, textbook_page_end FROM unit "
            "ORDER BY pdf_page_start, unit_id")]
        sections = {}
        for r in cp.execute(
                "SELECT unit_id, section_id, section_key, title, pdf_page_start, "
                "textbook_page_start FROM section "
                "ORDER BY unit_id, pdf_page_start, section_key"):
            sections.setdefault(r["unit_id"], []).append(
                {"section_id": r["section_id"], "section_key": r["section_key"],
                 "title": r["title"] or r["section_key"],
                 "pdf_page_start": r["pdf_page_start"],
                 "textbook_page_start": r["textbook_page_start"]})
    finally:
        cp.close()
    out = []
    for u in unit_rows:
        out.append({"slug": unit_slug(u["unit_code"]), "unit_code": u["unit_code"],
                    "title": u["title"],
                    "pdf_page_start": u["pdf_page_start"], "pdf_page_end": u["pdf_page_end"],
                    "textbook_page_start": u["textbook_page_start"],
                    "textbook_page_end": u["textbook_page_end"],
                    "sections": sections.get(u["unit_id"], [])})
    return out


def _attribution(cp) -> dict:
    """把每个学习资源归属到一个单元（**规则可追溯，不伪造关系**）：

    1. 优先：词表条目文本尾部的**印刷页码**（教材词表里每个词条后面印的页码）
       —— 用它映射到该页所在的单元；证据 = 页码 + 来源栏目（Words and expressions / A–Z）。
    2. 否则：来源内容块所在的 **PDF 页** → 该页所在单元；证据 = PDF 页 + 来源栏目。

    两条规则都只使用真实字段与教材自身的页范围，不构造任何 Activity → 资源关系。

    P2-1-C1（C1-03）：额外返回 `order` = **教材印刷词表顺序**（Words and expressions 词表页的
    `content_block.reading_order`，以 `(pdf_page, reading_order)` 表示），供列表按教材顺序排列；
    无法取得该证据的条目 `order = None`（页面回退到原有排序）。
    """
    units = cp.execute(
        "SELECT unit_code, pdf_page_start, pdf_page_end, textbook_page_start, "
        "textbook_page_end FROM unit ORDER BY pdf_page_start").fetchall()

    def by_textbook_page(page):
        for u in units:
            if (u["textbook_page_start"] or 0) <= page <= (u["textbook_page_end"] or 0):
                return u["unit_code"]
        return None

    def by_pdf_page(page):
        for u in units:
            if (u["pdf_page_start"] or 0) <= page <= (u["pdf_page_end"] or 0):
                return u["unit_code"]
        return None

    page_of_block = {r["block_id"]: r["pdf_page"] for r in cp.execute(
        "SELECT b.block_id, p.pdf_page FROM content_block b JOIN page p ON p.page_id=b.page_id")}
    order_of_block = {
        r["block_id"]: (r["pdf_page"], r["reading_order"] if r["reading_order"] is not None else 0)
        for r in cp.execute(
            "SELECT b.block_id, p.pdf_page, b.reading_order FROM content_block b "
            "JOIN page p ON p.page_id=b.page_id")}

    out = {}
    for r in cp.execute("SELECT item_id FROM learning_item ORDER BY item_id"):
        item_id = r["item_id"]
        refs = cp.execute(
            "SELECT source_id, quote_raw, emphasis_source_list FROM source_ref "
            "WHERE item_id=? ORDER BY source_ref_id", (item_id,)).fetchall()
        # 教材印刷词表顺序（P2-1-C1 §五）：只认 Words and expressions 词表页
        printed_orders = [order_of_block[ref["source_id"]] for ref in refs
                          if ref["source_id"] in order_of_block
                          and ref["emphasis_source_list"] == "Words and expressions"]
        printed = []
        for ref in refs:
            m = re.search(r"(\d{1,3})\s*$", (ref["quote_raw"] or "").strip())
            if m:
                printed.append((int(m.group(1)), ref["emphasis_source_list"]))
        if printed:
            page = max(p for p, _ in printed)
            lists = sorted({lst for _, lst in printed if lst})
            out[item_id] = {"unit_code": by_textbook_page(page),
                            "basis": "教材印刷页", "page": page,
                            "evidence": "、".join(lists) or None,
                            "order": min(printed_orders) if printed_orders else None}
            continue
        pdf_pages = [page_of_block.get(ref["source_id"]) for ref in refs]
        pdf_pages = [p for p in pdf_pages if p]
        lists = sorted({ref["emphasis_source_list"] for ref in refs
                        if ref["emphasis_source_list"]})
        out[item_id] = {"unit_code": by_pdf_page(min(pdf_pages)) if pdf_pages else None,
                        "basis": "教材来源页", "page": min(pdf_pages) if pdf_pages else None,
                        "evidence": "、".join(lists) or None,
                        "order": min(printed_orders) if printed_orders else None}
    return out


def unit_resource_counts(contentpack_path=CONTENTPACK) -> dict:
    """每个单元 × 每种资源的真实数量（由 _attribution 计算，不是硬编码）。"""
    cp = _ro(contentpack_path)
    try:
        attribution = _attribution(cp)
        rows = cp.execute(
            "SELECT item_id, item_type FROM learning_item").fetchall()
    finally:
        cp.close()
    counts = {}
    for r in rows:
        code = (attribution.get(r["item_id"]) or {}).get("unit_code")
        for kind, item_type in RESOURCE_KIND_ITEM_TYPE.items():
            if r["item_type"] == item_type and code:
                counts.setdefault(code, {}).setdefault(kind, 0)
                counts[code][kind] += 1
    return counts


def unit_of_item(item_id, contentpack_path=CONTENTPACK):
    """某条学习资源所属单元（复用 C3-C2 的可追溯归属规则；无法归属返回 None）。"""
    cp = _ro(contentpack_path)
    try:
        info = _attribution(cp).get(item_id) or {}
    finally:
        cp.close()
    code = info.get("unit_code")
    if not code:
        return None
    for unit in list_units(contentpack_path):
        if unit["unit_code"] == code:
            return unit
    return None


def list_unit_resources(slug, kind, contentpack_path=CONTENTPACK):
    """某个单元下某类资源的浏览列表（只读；稳定排序：教材页码 → 词条）。"""
    unit = get_unit(slug, contentpack_path)
    if unit is None or kind not in RESOURCE_KIND_ITEM_TYPE:
        return None
    item_type = RESOURCE_KIND_ITEM_TYPE[kind]
    cp = _ro(contentpack_path)
    try:
        attribution = _attribution(cp)
        rows = cp.execute(
            "SELECT item_id, canonical_text, display_text, phonetic, part_of_speech, "
            "meaning_zh, learning_requirement FROM learning_item WHERE item_type=? "
            "ORDER BY canonical_text", (item_type,)).fetchall()
        items, unmapped = [], 0
        for r in rows:
            info = attribution.get(r["item_id"]) or {}
            if info.get("unit_code") != unit["unit_code"]:
                if info.get("unit_code") is None:
                    unmapped += 1
                continue
            text = r["canonical_text"]
            if item_type == "sentence_pattern" and r["display_text"]:
                text = r["display_text"]            # 句型对孩子的展示形态（含 … 槽位）
            items.append({
                "item_id": r["item_id"],
                "text": text,
                "phonetic": r["phonetic"] or None,
                "part_of_speech": r["part_of_speech"] or None,
                "meaning": r["meaning_zh"] or None,
                "can_study": r["learning_requirement"] == "CORE",
                "requirement": r["learning_requirement"],   # 仅供页面选择说明文字（不渲染原值）
                "basis": info.get("basis"),
                "page": info.get("page"),
                "order": info.get("order"),
            })
    finally:
        cp.close()
    # P2-1-C1（C1-03）：Vocabulary 按**教材印刷词表顺序**排列；无词表顺序证据时回退到
    # 原有的（印刷页号, 词形）排序。短语 / 句型维持原有排序。
    if item_type == "vocabulary":
        items.sort(key=lambda x: (x["order"] or (9999, 9999), x["text"]))
    else:
        items.sort(key=lambda x: ((x["page"] if x["page"] is not None else 9999), x["text"]))
    return {"unit": unit, "kind": kind, "label": kind_label(kind),
            "items": items, "unmapped_count": unmapped,
            "total_in_textbook": len(rows)}


def printed_word_order(contentpack_path=CONTENTPACK) -> dict:
    """教材印刷词表顺序：{item_id: (pdf_page, reading_order)}（P2-1-C1 §五 / sort 口径单一来源）。"""
    cp = _ro(contentpack_path)
    try:
        return {iid: info["order"] for iid, info in _attribution(cp).items()
                if info.get("order")}
    finally:
        cp.close()

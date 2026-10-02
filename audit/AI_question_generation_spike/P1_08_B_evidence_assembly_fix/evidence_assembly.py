"""P1-08-B · 教材证据组装层（修正版参考实现，只读 contentpack）。

修正的机制缺陷：
    旧逻辑：page → section **只**来自 activity（页面没有 Activity ⇒ 该页正文被丢弃）
    新逻辑：**正文归属首先由教材正文自身的数据关系决定**——
            Section 页码范围 = 该 unit 内按 pdf_page_start 排序后的 [start, next_start-1]（末节到 unit 末尾）
            Activity 只用于「这个任务需要哪些证据」，不再作为「这一页有没有正文」的判据

对外 API：
    section_page_ranges(conn)                 -> {section_id: (start_pdf, end_pdf)}
    pages_of_section(conn, section_id)        -> 有序 pdf 页列表（页码区间 ∪ 该 section 的 activity 页）
    blocks_of_section(conn, section_id)       -> 去重、按 (pdf_page, reading_order) 排序的 block 列表
    activities_of_section(conn, section_id)   -> 该 section 的 activity 列表（任务级证据范围）
    build_section_evidence(conn, section_id)  -> 完整证据包（含统计）
    blocks_by_activity_only(conn)             -> **旧逻辑复现**，仅用于前后对照与回归，不用于生产

内容过滤（与正式层 `web/content.py::unit_text_sections` 的关系）：
    * 归属规则**完全一致**：section 起始页 + unit 页范围；
    * 默认（`strict_text_rule=False`）只排除页眉/页脚与空文本——
      这是 AI 证据层原有的内容范围（含侧栏提示等），保证「不丢正文」优先；
    * `strict_text_rule=True` 时额外套用正式层的内容过滤
      （排除 layout_role ∈ {footer, sidebar}、block_kind ∈ {footer_text, sidebar_tip}，
       以及纯排版标记），此时结果与正式层**逐 block 一致**。

本模块只读数据库；不写入、不修改任何数据。
"""
import re
from collections import defaultdict

# 与 web/content.py 一致的正式层内容过滤常量（此处复刻并在测试中做等价性校验）
FORMAL_SKIP_ROLE = ("footer", "sidebar")
FORMAL_SKIP_KIND = ("footer_text", "sidebar_tip")
_LAYOUT_MARKER = re.compile(r"[\d\s\W]{0,6}\Z")
_SHORT_LATIN = re.compile(r"[A-Za-z]{1,8}\Z")


def _rows(conn, sql, args=()):
    return [dict(r) for r in conn.execute(sql, args)]


def section_page_ranges(conn):
    """Section 页码范围（**不依赖 activity**）。"""
    units = {r["unit_id"]: dict(r) for r in _rows(conn, "select * from unit")}
    secs = _rows(conn, "select * from section order by unit_id, pdf_page_start")
    by_unit = defaultdict(list)
    for s in secs:
        by_unit[s["unit_id"]].append(s)
    out = {}
    for uid, rows in by_unit.items():
        rows.sort(key=lambda x: x["pdf_page_start"])
        unit_end = units[uid]["pdf_page_end"]
        for i, s in enumerate(rows):
            end = rows[i + 1]["pdf_page_start"] - 1 if i + 1 < len(rows) else unit_end
            out[s["section_id"]] = (s["pdf_page_start"], max(end, s["pdf_page_start"]))
    return out


def activities_of_section(conn, section_id):
    return _rows(conn, "select activity_id, activity_number, pdf_page, textbook_page, "
                       "instruction, kind from activity where section_id=? "
                       "order by activity_number", (section_id,))


def pages_of_section(conn, section_id, ranges=None):
    """页码区间 ∪ 该 Section 的 activity 页；有序、去重。"""
    ranges = ranges or section_page_ranges(conn)
    if section_id not in ranges:
        raise KeyError("unknown section_id: %s" % section_id)
    start, end = ranges[section_id]
    pages = set(range(start, end + 1))
    for a in activities_of_section(conn, section_id):
        if a["pdf_page"]:
            pages.add(a["pdf_page"])
    return sorted(pages)


def blocks_of_section(conn, section_id, ranges=None, include_footer=False,
                      strict_text_rule=False):
    """该 Section 的全部正文 block：按页码归属取回，去重（block_id），按 (pdf_page, reading_order) 排序。

    去重以 content_block 的稳定主键 block_id 为准（不依赖字符串比较）。
    """
    pages = set(pages_of_section(conn, section_id, ranges))
    rows = _rows(conn, "select b.block_id, b.page_id, p.pdf_page, p.textbook_page, "
                       "b.block_kind, b.layout_role, b.reading_order, b.text_raw "
                       "from content_block b join page p on p.page_id=b.page_id "
                       "order by p.pdf_page, b.reading_order")
    seen, out = set(), []
    for r in rows:
        if r["pdf_page"] not in pages:
            continue
        if not include_footer and r["block_kind"] == "footer_text":
            continue
        if strict_text_rule:
            if r["layout_role"] in FORMAL_SKIP_ROLE or r["block_kind"] in FORMAL_SKIP_KIND:
                continue
            t = (r["text_raw"] or "").strip()
            if _LAYOUT_MARKER.match(t) or _SHORT_LATIN.match(t):
                continue
        if r["block_id"] in seen:
            continue
        seen.add(r["block_id"])
        text = (r["text_raw"] or "").replace("\n", " ").strip()
        if not text:
            continue
        r["text"] = text
        out.append(r)
    out.sort(key=lambda x: (x["pdf_page"], x["reading_order"] or 0))
    return out


def build_section_evidence(conn, section_id, include_footer=False, strict_text_rule=False):
    """完整证据包（教材定位 + 正文 + 活动 + 统计）。"""
    ranges = section_page_ranges(conn)
    sec = _rows(conn, "select * from section where section_id=?", (section_id,))
    if not sec:
        raise KeyError("unknown section_id: %s" % section_id)
    sec = sec[0]
    acts = activities_of_section(conn, section_id)
    bl = blocks_of_section(conn, section_id, ranges, include_footer, strict_text_rule)
    return {
        "section": sec,
        "unit_id": sec["unit_id"],
        "page_range": ranges[section_id],
        "pages": pages_of_section(conn, section_id, ranges),
        "activities": acts,
        "blocks": bl,
        "stats": {
            "pages": len(pages_of_section(conn, section_id, ranges)),
            "activities": len(acts),
            "blocks": len(bl),
            "blocks_unique": len({b["block_id"] for b in bl}),
            "pages_without_activity": sorted(
                set(pages_of_section(conn, section_id, ranges))
                - {a["pdf_page"] for a in acts if a["pdf_page"]}),
        },
    }


# ------------------------------------------------------------------ 旧逻辑（仅用于对照/回归）
def page_to_section_by_activity(conn):
    m = defaultdict(set)
    for r in conn.execute("select distinct pdf_page, section_id from activity"):
        m[r["pdf_page"]].add(r["section_id"])
    return m


def blocks_by_activity_only(conn, include_footer=False):
    """复现旧逻辑：page → section 仅来自 activity。返回 {section_id: [block,...]}。"""
    page2sec = page_to_section_by_activity(conn)
    out = defaultdict(list)
    for r in _rows(conn, "select b.block_id, b.page_id, p.pdf_page, p.textbook_page, "
                         "b.block_kind, b.reading_order, b.text_raw "
                         "from content_block b join page p on p.page_id=b.page_id "
                         "order by p.pdf_page, b.reading_order"):
        if not include_footer and r["block_kind"] == "footer_text":
            continue
        for sid in page2sec.get(r["pdf_page"], ()):
            r2 = dict(r)
            r2["text"] = (r["text_raw"] or "").replace("\n", " ").strip()
            out[sid].append(r2)
    return out

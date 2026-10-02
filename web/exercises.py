#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-2 教材练习层（只读 + 规则判分）

数据来源（全部只读，均为正式教材推导）：
  * `structured/exercises/exercise_catalog.json`：教材练习目录（活动 + 页码 + 官方音频 + 匹配证据）
  * contentpack v5：`sub_question`（教材理解题）、`learning_item`（教材词表）

职责：
  * 列出某个单元的教材练习；
  * 组装一个练习的作答内容：
      - 教材理解题（同一页的 sub_question）→ 简答（规则预检 + AI 批改入口）
      - 教材词表练习 → 看中文写单词（规则判分）
      - 其余教材练习 → 自评（孩子自己的判断，不伪造正确答案）
  * 规则判分（选择题/拼写/固定答案）。AI 只作为简答题的分析入口，本阶段不实际调用。

边界：不写 learning.db（记录一律交给冻结服务）；不调用 AI；不联网。
"""

from __future__ import annotations

import os

import json
import re
import sys
from pathlib import Path

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
EX_DIR = BASE / "structured" / "exercises"
CATALOG_V2 = EX_DIR / "exercise_catalog_v2.json"
CATALOG_V1 = EX_DIR / "exercise_catalog.json"
#: P2-3 起以证据链重建的目录为准；缺失时回退到 P2-2 目录（只读兼容）
CATALOG = CATALOG_V2 if CATALOG_V2.exists() else CATALOG_V1
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"

#: 教材真实题型的显示名（不暴露内部枚举）
QUESTION_LABELS = {
    "choice": "选择", "fill": "填空", "match": "匹配", "judge": "判断",
    "order": "排序", "short_answer": "简答", "speaking": "口语", "writing": "写作",
    "reflection": "单元反思", "listening": "听力", "other": "练习",
}

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True
import content as content_mod          # noqa: E402

#: 教材练习类型 → 孩子看到的短标签（不暴露内部枚举）
TYPE_LABELS = {
    "listening": "听力",
    "reading": "阅读",
    "writing": "写作",
    "speaking": "口语",
    "grammar": "语法",
    "vocabulary": "词汇",
    "other": "练习",
}

#: 教材练习类型 → 学习行为（learning_service.ACTIVITY_TYPES 既有 9 值，不新增）
TYPE_BEHAVIOR = {
    "listening": "listen",
    "reading": "read",
    "writing": "produce",
    "speaking": "repeat",
    "grammar": "understand",
    "vocabulary": "recognize",
    "other": "understand",
}


def load_catalog(path=CATALOG) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {"exercises": [], "counts_by_unit": {}}


def exercises_of_unit(unit_code: str, path=CATALOG) -> list:
    items = [e for e in load_catalog(path).get("exercises", []) if e["unit"] == unit_code]
    return sorted(items, key=lambda e: (e["section"], e["exercise_no"] or 0))


def get_exercise(exercise_id: str, path=CATALOG):
    for e in load_catalog(path).get("exercises", []):
        if e["exercise_id"] == exercise_id:
            return e
    return None


def exercise_key(exercise_id: str) -> str:
    import hashlib
    return hashlib.sha256((exercise_id or "").encode("utf-8")).hexdigest()[:12]


def find_by_key(key: str, path=CATALOG):
    key = (key or "").strip().lower()
    for e in load_catalog(path).get("exercises", []):
        if exercise_key(e["exercise_id"]) == key:
            return e
    return None


def audio_url(exercise) -> str | None:
    code = (exercise.get("audio_id") or "").split(":")[-1]
    return "/audio/official/%s.mp3" % code if code else None


# ---------------------------------------------------------------- 题目组装

# ============================================================================
# P2-6-F-1 / F-2 / F-4 教材结构修正层（2026-09-13）
#
# 依据 V1.2.1：
#   六·8 教材文字—音频—上下文—Question 严谨锚定：只用教材事实，不做推断
#   七·3 原题型必须尽可能还原：不得把教材原任务降级成“完成 / 未完成”
#   七·9 答案事实原则：本轮没有可靠答案 → 不生成 answer、不做正式判分
#
# 所有修正都来自教材事实（contentpack content_block 原文 + 教材原页几何：
# 活动号标注的 y 区间、印刷书写线），不做语义推断、不引入 AI。
# ============================================================================

STRUCTURE_VERSION = "P2-6-F-1/F-2/F-4"

#: 已确认的页眉 / 页脚 / 侧栏噪声（P2-6-F-0 §7.1）——不得进入选项
NOISE_OPTION_TEXTS = frozenset({
    "great teacher",                        # Unit 1 p19 页面小标题
    "new start 19",                         # Unit 1 p19 页脚
    "new start 23",                         # Unit 1 p23 页脚
    "new start 15",                         # Unit 1 p15 页脚
    "pun is a word with more than one",     # Unit 5 p82 Learning to think 侧栏
})

#: 可确定性修复的空位数量（P2-6-F-0 §7.3）
#: 证据 = 教材印刷书写线 / 表格结构 / 正文编号空位（均为教材原页确定事实）
BLANK_FIX = {
    "FLTRP-EN-7A-2022CUR:X:88C641F5FA05": (6, "P14 教材印刷书写线 6 条（y=515.2 / 533.2×3 / 551.2 / 569.2）"),
    "FLTRP-EN-7A-2022CUR:X:F21C9E2036F7": (6, "P20 教材表格 3 列 × 3 行；第 1 行为示例，第 2/3 行共 6 个空格"),
    "FLTRP-EN-7A-2022CUR:X:2CA1B9F43CB3": (6, "P32 Mia 回信印刷书写线 6 条（y=227.2 / 251.2 / 296.2 / 320.2 / 347.2 / 365.2）"),
    "FLTRP-EN-7A-2022CUR:X:24C80DAE6FAE": (6, "P40 教材印刷书写线 6 条（y=263.2×2 / 281.2×2 / 299.2×2）"),
    "FLTRP-EN-7A-2022CUR:X:6BB271F5F101": (3, "P88 教材印刷书写线 3 条（y=191.2 / 209.2 / 227.2）"),
    "FLTRP-EN-7A-2022CUR:X:5BCC4D6DC928": (3, "P104 教材印刷书写线 3 条（y=263.2 / 299.2 / 317.2）"),
    "FLTRP-EN-7A-2022CUR:X:AC02902827A8": (9, "教材原题 ➊➋➌ + 选项清单；原 UI 上限 8 造成截断，按教材事实恢复 9"),
    "FLTRP-EN-7A-2022CUR:X:41B8D362116C": (9, "P40 正文 9 处编号空位（1–9）；原 UI 上限 8 造成截断"),
    "FLTRP-EN-7A-2022CUR:X:0AD8920218D8": (9, "P95 表格印刷书写线 9 条（y=150.2×2 / 210.2×2 / 270.2 / 288.2 / 366.2×2 / 402.2）"),
}

#: 练习 → 教材原题材料块（contentpack block_id）。
#: Starter A9 / A10 属于 P2-6-F-4 几何重建：
#:   活动号 9 的标注 bbox y=232.62–247.11；活动号 10 的标注 bbox y=430.64–444.41；
#:   词框块 P10:B14 位于 y=250.0–410.2（落在 A9 区间）→ 归属 A9；
#:   对话块 P10:B5–B13 位于 y=449.1–625.6（落在 A10 区间）→ 归属 A10。
#:   旧 text_references 把 A10 的对话块记到了 A9，这里按教材原页几何修正。
EXERCISE_MATERIAL = {
    "FLTRP-EN-7A-2022CUR:X:ED3C7BD7A9AA": {          # Starter GET_READY A9（Match the words…）
        "activity_id": "FLTRP-EN-7A-2022CUR:STARTER:GET_READY:A9",
        "blocks": ["FLTRP-EN-7A-2022CUR:P10:B1", "FLTRP-EN-7A-2022CUR:P10:B14"],
        "review": []},
    "FLTRP-EN-7A-2022CUR:X:1C4143922B1C": {          # Starter GET_READY A10（Listen and choose.）
        "activity_id": "FLTRP-EN-7A-2022CUR:STARTER:GET_READY:A10",
        "blocks": ["FLTRP-EN-7A-2022CUR:P10:B15",
                   "FLTRP-EN-7A-2022CUR:P10:B5", "FLTRP-EN-7A-2022CUR:P10:B6",
                   "FLTRP-EN-7A-2022CUR:P10:B7", "FLTRP-EN-7A-2022CUR:P10:B8",
                   "FLTRP-EN-7A-2022CUR:P10:B9", "FLTRP-EN-7A-2022CUR:P10:B10",
                   "FLTRP-EN-7A-2022CUR:P10:B11", "FLTRP-EN-7A-2022CUR:P10:B12",
                   "FLTRP-EN-7A-2022CUR:P10:B13"],
        "review": ["教材原题只说“听录音并选择”；本页词框的归属需人工核验"
                   "（P2-6-F-0-A N-01），本轮只记录作答、不做判分"]},
    "FLTRP-EN-7A-2022CUR:X:7ABB5256D7ED": {          # Starter KNOW_YOUR_SCHOOL A2（Read and tick…）
        "activity_id": "FLTRP-EN-7A-2022CUR:STARTER:KNOW_YOUR_SCHOOL:A2",
        "blocks": ["FLTRP-EN-7A-2022CUR:P12:B0", "FLTRP-EN-7A-2022CUR:P12:B1"],
        "review": []},
    "FLTRP-EN-7A-2022CUR:X:8D3E1E4E1B31": {          # Unit 1 A6（Circle the correct words.）
        "activity_id": "FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS:A6",
        "blocks": ["FLTRP-EN-7A-2022CUR:P24:B4"], "review": []},
    "FLTRP-EN-7A-2022CUR:X:3DCE713706DE": {          # Unit 1 A7（Read the passage and circle…）
        "activity_id": "FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS:A7",
        "blocks": ["FLTRP-EN-7A-2022CUR:P24:B7", "FLTRP-EN-7A-2022CUR:P24:B13",
                   "FLTRP-EN-7A-2022CUR:P24:B8", "FLTRP-EN-7A-2022CUR:P24:B9",
                   "FLTRP-EN-7A-2022CUR:P24:B10", "FLTRP-EN-7A-2022CUR:P24:B11",
                   "FLTRP-EN-7A-2022CUR:P24:B12"],
        "review": []},
    "FLTRP-EN-7A-2022CUR:X:BEF04AA1DF4C": {          # Unit 1 A4（教材不是选择题）
        "activity_id": "FLTRP-EN-7A-2022CUR:U1:DEVELOPING_IDEAS:A4",
        "blocks": ["FLTRP-EN-7A-2022CUR:P28:B10"],
        "review": ["教材原题是结对口语任务，不是选择题；本轮按教材原要求呈现"]},
    "FLTRP-EN-7A-2022CUR:X:74BDDE140FAE": {          # Unit 3 A3（Read and tick.）
        "activity_id": "FLTRP-EN-7A-2022CUR:U3:UNDERSTANDING_IDEAS:A3",
        "blocks": ["FLTRP-EN-7A-2022CUR:P55:B3"], "review": []},
    "FLTRP-EN-7A-2022CUR:X:C2D62A46BE36": {          # Unit 4 A2（judge：F / O）
        "activity_id": "FLTRP-EN-7A-2022CUR:U4:DEVELOPING_IDEAS:A2",
        "blocks": ["FLTRP-EN-7A-2022CUR:P75:B0"],
        "review": ["每个空填什么、每句是 F 还是 O，需要听官方音频后人工核验"]},
    "FLTRP-EN-7A-2022CUR:X:36ECBA5AD565": {          # Unit 6 A1（Tick the words…）
        "activity_id": "FLTRP-EN-7A-2022CUR:U6:UNDERSTANDING_IDEAS:A1",
        "blocks": ["FLTRP-EN-7A-2022CUR:P101:B8", "FLTRP-EN-7A-2022CUR:P101:B9",
                   "FLTRP-EN-7A-2022CUR:P101:B10", "FLTRP-EN-7A-2022CUR:P101:B14"],
        "review": []},
    # 空位数量修正的 6 条 fill：补上教材原题材料，让孩子看到真正的空位
    "FLTRP-EN-7A-2022CUR:X:88C641F5FA05": {"blocks": ["FLTRP-EN-7A-2022CUR:P14:B3"], "review": []},
    "FLTRP-EN-7A-2022CUR:X:24C80DAE6FAE": {"blocks": ["FLTRP-EN-7A-2022CUR:P40:B20"], "review": []},
    "FLTRP-EN-7A-2022CUR:X:6BB271F5F101": {"blocks": ["FLTRP-EN-7A-2022CUR:P88:B3"], "review": []},
    "FLTRP-EN-7A-2022CUR:X:5BCC4D6DC928": {"blocks": ["FLTRP-EN-7A-2022CUR:P104:B16"], "review": []},
    "FLTRP-EN-7A-2022CUR:X:F21C9E2036F7": {          # Unit 1 Starting out A2（表格）
        "blocks": ["FLTRP-EN-7A-2022CUR:P20:B5", "FLTRP-EN-7A-2022CUR:P20:B15",
                   "FLTRP-EN-7A-2022CUR:P20:B7", "FLTRP-EN-7A-2022CUR:P20:B9",
                   "FLTRP-EN-7A-2022CUR:P20:B11", "FLTRP-EN-7A-2022CUR:P20:B13"],
        "review": ["教材原题是表格填空（3 列 × 3 行，第 1 行为示例）；本轮按 6 个空格呈现"]},
    "FLTRP-EN-7A-2022CUR:X:2CA1B9F43CB3": {          # Unit 1 Reading for writing A5（Mia 回信）
        "blocks": ["FLTRP-EN-7A-2022CUR:P32:B12", "FLTRP-EN-7A-2022CUR:P32:B13",
                   "FLTRP-EN-7A-2022CUR:P32:B14", "FLTRP-EN-7A-2022CUR:P32:B15",
                   "FLTRP-EN-7A-2022CUR:P32:B16", "FLTRP-EN-7A-2022CUR:P32:B17",
                   "FLTRP-EN-7A-2022CUR:P32:B18", "FLTRP-EN-7A-2022CUR:P32:B19",
                   "FLTRP-EN-7A-2022CUR:P32:B20"],
        "review": ["教材原题是补全回信（印刷书写线 6 条）；本轮按 6 个空呈现"]},
}

#: 本页教材词框（页级教材内容；A10 的选项来源，归属待人工核验）
PAGE_WORD_BOX = {
    "FLTRP-EN-7A-2022CUR:X:1C4143922B1C": {
        "block_id": "FLTRP-EN-7A-2022CUR:P10:B14",
        "review": "教材原页词框；与同页 A9 相邻，A10 的选项来源需人工核验（P2-6-F-0-A N-01）"},
}

_BLOCK_CACHE = {}


def _blocks(block_ids, contentpack_path=CONTENTPACK) -> list:
    """按 block_id 读取教材原文块（只读；保持传入顺序；不改写教材原文）。"""
    ids = [b for b in (block_ids or []) if b]
    if not ids:
        return []
    key = (str(contentpack_path), tuple(ids))
    if key in _BLOCK_CACHE:
        return _BLOCK_CACHE[key]
    cp = content_mod._ro(contentpack_path)
    try:
        marks = ",".join("?" * len(ids))
        rows = {r["block_id"]: r for r in cp.execute(
            "SELECT block_id, page_id, block_kind, layout_role, reading_order, text_raw "
            "FROM content_block WHERE block_id IN (%s)" % marks, ids)}
    finally:
        cp.close()
    out = []
    for bid in ids:
        r = rows.get(bid)
        if r is None:
            continue
        text = (r["text_raw"] or "").strip()
        if text:
            out.append({"block_id": bid, "page_id": r["page_id"], "kind": r["block_kind"],
                        "role": r["layout_role"], "order": r["reading_order"], "text": text})
    _BLOCK_CACHE[key] = out
    return out


def textbook_material(exercise, contentpack_path=CONTENTPACK):
    """教材原题材料（只引用教材原页内容块，不改写教材原文）。"""
    spec = EXERCISE_MATERIAL.get(exercise.get("exercise_id"))
    if not spec:
        return None
    blocks = _blocks(spec.get("blocks"), contentpack_path)
    if not blocks:
        return None
    return {"activity_id": spec.get("activity_id"), "blocks": blocks,
            "text": "\n".join(b["text"] for b in blocks),
            "source": "contentpack content_block（教材原页原文）",
            "review": list(spec.get("review") or [])}


def _checkbox_items(text: str) -> list:
    """教材 ☐ 勾选清单 → 条目（第一个 ☐ 之前是题干，不算条目）。"""
    text = re.sub(r"\s*others:", " ☐ others:", text or "")
    parts = [p.strip() for p in text.split("☐")]
    out = []
    for p in parts[1:]:
        p = re.sub(r"\s+", " ", p).strip()
        if len(p) >= 2:
            out.append(p)
    return out


_SLASH_PAIR = re.compile(
    r"([A-Za-z][A-Za-z’'\-]*(?:\s+[A-Za-z][A-Za-z’'\-]*)?)\s*/\s*([A-Za-z][A-Za-z’'\-]*)")


def _slash_pairs(text: str) -> list:
    """教材正文里的 "A / B" 内联选择 → [(left, right), …]。"""
    return [(m.group(1).strip(), m.group(2).strip()) for m in _SLASH_PAIR.finditer(text or "")]


def page_word_box(exercise, contentpack_path=CONTENTPACK):
    """教材本页词框（页级教材内容）。返回 {block_id, items, review} 或 None。"""
    spec = PAGE_WORD_BOX.get(exercise.get("exercise_id"))
    if not spec:
        return None
    blocks = _blocks([spec["block_id"]], contentpack_path)
    if not blocks:
        return None
    items = [re.sub(r"^[\d\s]+", "", i) for i in _checkbox_items(blocks[0]["text"])]
    items = [i for i in items if i]
    if not items:
        return None
    return {"block_id": spec["block_id"], "items": items, "review": spec.get("review")}


def textbook_options(exercise, contentpack_path=CONTENTPACK) -> list:
    """教材选项：只使用教材原文可确定的结构，并剔除已确认噪声。"""
    qtype = exercise.get("question_type")
    material = textbook_material(exercise, contentpack_path)
    if material and qtype in ("choice", "judge"):
        if qtype == "judge":
            return [{"label": "F", "text": "F（fact 事实）"}, {"label": "O", "text": "O（opinion 观点）"}]
        text = "\n".join(b["text"] for b in material["blocks"])
        items = _checkbox_items(text)
        if items:
            return [{"label": str(i + 1), "text": t} for i, t in enumerate(items)]
    opts = [o for o in (exercise.get("options") or []) if len(o.get("text", "")) >= 2]
    lower_noise = {n.lower() for n in NOISE_OPTION_TEXTS}
    return [o for o in opts if (o.get("text") or "").strip().lower() not in lower_noise]


def blank_count(exercise) -> int:
    """空位数量：已确认修正优先；其余保持目录字段（8 的上限只用于未修正记录）。"""
    fix = BLANK_FIX.get(exercise.get("exercise_id"))
    if fix:
        return int(fix[0])
    return min(max(int(exercise.get("blanks") or 0), 1), 8)


def _inline_blanks(text: str, n: int):
    """把教材原文里的印刷空位（连续空白）变成 n 个空。数量不符时返回 None。"""
    if not text:
        return None
    gaps = list(re.finditer(r"(?<=\S)[ \u3000]{2,}(?=\S)", text))
    if len(gaps) != n:
        return None
    parts, last = [], 0
    for i, m in enumerate(gaps):
        parts.append({"text": text[last:m.start()]})
        parts.append({"blank": i + 1})
        last = m.end()
    parts.append({"text": text[last:]})
    return parts


def _inline_choices(text: str):
    """把教材正文里的 "A / B" 内联选择拆成可作答片段。"""
    pairs = list(_SLASH_PAIR.finditer(text or ""))
    if not pairs:
        return None
    parts, last = [], 0
    for i, m in enumerate(pairs):
        parts.append({"text": text[last:m.start()]})
        parts.append({"choice": i + 1, "options": [m.group(1).strip(), m.group(2).strip()]})
        last = m.end()
    parts.append({"text": text[last:]})
    return parts


def _structure_v2() -> dict:
    """P2-4 教材结构（只读；P2-6-F-4 活动锚点）。"""
    path = BASE / "structured" / "textbook" / "textbook_structure_v2.json"
    key = ("__structure__", str(path))
    if key in _BLOCK_CACHE:
        return _BLOCK_CACHE[key]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    _BLOCK_CACHE[key] = data
    return data


def resolve_activity_id(exercise):
    """练习 → 教材活动锚点：目录字段优先，其次按 (unit, section, 题号) 解析。"""
    if exercise.get("activity_id"):
        return exercise["activity_id"]
    for u in _structure_v2().get("units", []):
        if u.get("unit_code") != exercise.get("unit"):
            continue
        for s in u.get("sections", []):
            if s.get("section_key") != exercise.get("section"):
                continue
            for a in s.get("activities", []):
                if a.get("activity_no") == exercise.get("exercise_no"):
                    return a.get("activity_id")
    return None


def _block_activity_map() -> dict:
    """教材内容块 → 活动（P2-4 text_references + A9/A10 修正；只用于题目锚定）。"""
    path = BASE / "structured" / "textbook" / "textbook_content_relations_v2.json"
    key = ("__block_act__", str(path))
    if key in _BLOCK_CACHE:
        return _BLOCK_CACHE[key]
    mapping = {}
    try:
        rel = json.loads(path.read_text(encoding="utf-8"))
        for r in rel.get("text_references", []):
            mapping.setdefault(r["to"], set()).add(r["from"])
    except Exception:
        pass
    for bid in ("FLTRP-EN-7A-2022CUR:P10:B1", "FLTRP-EN-7A-2022CUR:P10:B14"):
        mapping[bid] = {"FLTRP-EN-7A-2022CUR:STARTER:GET_READY:A9"}
    for bid in ("FLTRP-EN-7A-2022CUR:P10:B15", "FLTRP-EN-7A-2022CUR:P10:B5",
                "FLTRP-EN-7A-2022CUR:P10:B6", "FLTRP-EN-7A-2022CUR:P10:B7",
                "FLTRP-EN-7A-2022CUR:P10:B8", "FLTRP-EN-7A-2022CUR:P10:B9",
                "FLTRP-EN-7A-2022CUR:P10:B10", "FLTRP-EN-7A-2022CUR:P10:B11",
                "FLTRP-EN-7A-2022CUR:P10:B12", "FLTRP-EN-7A-2022CUR:P10:B13"):
        mapping[bid] = {"FLTRP-EN-7A-2022CUR:STARTER:GET_READY:A10"}
    _BLOCK_CACHE[key] = mapping
    return mapping


def _split_sub_questions(text: str) -> list:
    """教材理解题的原始文本常把多问拼在一起（"…?2 What …"）→ 拆成多条。"""
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return []
    parts = re.split(r"(?<=[?.!])\s*(?=\d\s*[A-Z])", text)
    out = []
    for p in parts:
        p = re.sub(r"^\d+\s*", "", p).strip()
        if len(p) > 4:
            out.append(p)
    return out


def sub_questions_for_activity(exercise, contentpack_path=CONTENTPACK) -> list:
    """教材理解题：按**活动锚点**取题（不再按页取题，避免同页跨活动串题）。

    P2-6-F-4：contentpack 里 sub_question.activity_id 为空，因此按
    「题面文本 → 教材内容块 → 活动」这条确定性链路锚定（P2-6-F-0 实测 13/13 可定位）；
    无法唯一锚定到本活动时**不返回题目**（宁可少题，不串题）。
    """
    activity_id = resolve_activity_id(exercise)
    if not activity_id:
        return []
    cp = content_mod._ro(contentpack_path)
    try:
        rows = cp.execute("SELECT sub_question_id, pdf_page, text_raw FROM sub_question "
                          "WHERE pdf_page=? ORDER BY ordinal", (exercise.get("pdf_page"),)).fetchall()
        blocks = cp.execute("SELECT block_id, text_raw FROM content_block WHERE page_id=?",
                            ("FLTRP-EN-7A-2022CUR:P%s" % exercise.get("pdf_page"),)).fetchall()
    finally:
        cp.close()
    if not rows:
        return []
    amap = _block_activity_map()

    def _norm(s):
        return re.sub(r"[^a-z0-9]", "", (s or "").lower())

    out = []
    for r in rows:
        needle = _norm(r["text_raw"])
        if not needle:
            continue
        owners = set()
        for b in blocks:
            if needle in _norm(b["text_raw"]):
                owners |= set(amap.get(b["block_id"]) or ())
        if owners != {activity_id}:
            continue
        out.extend(_split_sub_questions(r["text_raw"]))
    return out[:3]


def sub_questions(pdf_page: int, contentpack_path=CONTENTPACK) -> list:
    """兼容旧接口：按页取题（历史测试用；正式链路用 sub_questions_for_activity）。"""
    cp = content_mod._ro(contentpack_path)
    try:
        rows = cp.execute("SELECT ordinal, text_raw FROM sub_question WHERE pdf_page=? "
                          "ORDER BY ordinal", (pdf_page,)).fetchall()
    finally:
        cp.close()
    out = []
    for r in rows:
        out.extend(_split_sub_questions(r["text_raw"]))
    return out[:3]


def word_list_of_unit(unit_code: str, contentpack_path=CONTENTPACK) -> list:
    """本单元教材词表（按教材印刷顺序）。"""
    cp = content_mod._ro(contentpack_path)
    try:
        attribution = content_mod._attribution(cp)
        rows = cp.execute(
            "SELECT item_id, canonical_text, meaning_zh, phonetic, learning_requirement "
            "FROM learning_item WHERE item_type='vocabulary'").fetchall()
    finally:
        cp.close()
    out = []
    for r in rows:
        info = attribution.get(r["item_id"]) or {}
        if info.get("unit_code") != unit_code or not info.get("order"):
            continue
        if not (r["meaning_zh"] or "").strip():
            continue
        out.append({"item_id": r["item_id"], "word": r["canonical_text"],
                    "meaning": r["meaning_zh"], "phonetic": r["phonetic"],
                    "requirement": r["learning_requirement"], "order": info["order"]})
    out.sort(key=lambda x: x["order"])
    return out


def _legacy_build_questions(exercise, contentpack_path=CONTENTPACK) -> dict:
    """一个练习的作答内容。

    P2-3：优先按**教材真实题型**呈现（选择 / 填空 / 匹配 / 判断 / 排序 / 简答），
    并把教材原题结构（instruction + 教材项目 / 选项 / 空格数）一起交给页面；
    教材未提供可核对的答案来源时，不伪造答案，交由孩子自行核对（self-check 语义）。

    返回 {"kind", "questions", "items", "options", "blanks", "note", "textbook": {...}}
    """
    etype = exercise.get("type")
    unit = exercise.get("unit")
    qtype = exercise.get("question_type") or "other"
    items = list(exercise.get("check_items") or [])
    options = [o for o in (exercise.get("options") or []) if len(o.get("text", "")) >= 2]
    blanks = int(exercise.get("blanks") or 0)
    textbook = {"instruction": exercise.get("instruction"),
                "question_type": qtype,
                "question_label": QUESTION_LABELS.get(qtype, "练习"),
                "items": items, "options": options, "blanks": blanks,
                "textbook_page": exercise.get("textbook_page"),
                "audio_confirmed": bool(exercise.get("audio_id"))}

    base = {"kind": "self_check", "questions": [], "items": items, "options": options,
            "blanks": blanks, "textbook": textbook,
            "note": "这是教材上的练习。做完之后，由你自己判断做得怎么样。"}

    # 1) 教材词表练习（P2-2 起既有能力，保留）：教材原题 + 本单元词表自测
    #    答案来自教材词表，可规则判分；教材原题结构同时交给页面显示。
    if etype == "vocabulary":
        words = word_list_of_unit(unit, contentpack_path)
        picked = [w for w in words if w["requirement"] == "CORE"][:4] or words[:4]
        if picked:
            base.update({
                "kind": "spelling",
                "questions": [{"no": i + 1, "meaning": w["meaning"], "answer": w["word"],
                               "phonetic": w["phonetic"], "item_id": w["item_id"]}
                              for i, w in enumerate(picked)],
                "note": "教材原题在教材上完成；下面的自测答案来自本单元教材词表。"})
            return base

    # 2) 教材选择题 / 判断题：教材给选项就按选项作答，否则按教材原题自行核对
    if qtype in ("choice", "judge"):
        if options:
            base.update({"kind": "choice",
                         "questions": [{"no": 1, "options": options}]})
            base["note"] = "按教材原题作答；教材没有提供可核对的答案，做完自己核对。"
            return base
        return base

    # 3) 教材填空题：保留教材空格数量
    if qtype == "fill":
        n = min(max(blanks, 1), 8)
        base.update({"kind": "fill",
                     "questions": [{"no": i + 1} for i in range(n)],
                     "note": "按教材原题把空格填完；教材没有给出答案，做完自己核对。"})
        return base

    # 4) 教材匹配 / 排序题：保留教材列出的项目（右侧图片类不在数据内，不猜测）
    if qtype in ("match", "order"):
        base.update({"kind": "match",
                     "note": "匹配 / 排序请对照教材完成；这里列出教材上的项目。"})
        return base

    # 5) 教材理解题（同一页的 sub_question）→ 简答
    if etype in ("reading", "listening") or qtype == "short_answer":
        qs = sub_questions(exercise["pdf_page"], contentpack_path)
        if not qs and qtype == "short_answer" and exercise.get("instruction"):
            # 教材指令本身就是这道题的问句（例如 “Read and answer. What …?”）
            qs = [exercise["instruction"]]
        if qs:
            base.update({"kind": "short_answer",
                         "questions": [{"no": i + 1, "text": q} for i, q in enumerate(qs)],
                         "note": "用教材里的信息回答；答完可以自己再改一遍。"})
            return base

    # 6) 其余教材练习 → 自评（不伪造正确答案）
    return base


# ---------------------------------------------------------------- 判分

def _normalize_answer(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _legacy_grade(exercise, questions: dict, form: dict) -> dict:
    """规则判分（选择题/拼写/固定答案）；简答走 AI 批改入口（本阶段只做规则预检）。"""
    kind = questions["kind"]

    if kind == "spelling":
        details, correct = [], 0
        for q in questions["questions"]:
            given = (form.get("q%d" % q["no"]) or "").strip()
            ok = _normalize_answer(given) == _normalize_answer(q["answer"])
            correct += 1 if ok else 0
            details.append({"no": q["no"], "meaning": q["meaning"], "given": given,
                            "answer": q["answer"], "correct": ok})
        total = len(questions["questions"])
        result = "correct" if correct == total else ("partial" if correct else "incorrect")
        return {"kind": kind, "result": result, "correct": correct, "total": total,
                "details": details,
                "summary": "写对 %d / %d 个" % (correct, total)}

    if kind == "short_answer":
        from ai_grading import analyze_short_answer     # 本地模块，不联网
        details = []
        answered = 0
        for q in questions["questions"]:
            given = (form.get("q%d" % q["no"]) or "").strip()
            if given:
                answered += 1
            details.append({"no": q["no"], "question": q["text"], "given": given,
                            "analysis": analyze_short_answer(q["text"], given)})
        total = len(questions["questions"])
        choice = (form.get("self_check") or "").strip()
        if answered == 0 and choice in ("done", "partial", "skipped"):
            # 孩子没有写答案、但明确表示做完了/还想再看一遍：按孩子自己的判断记录
            result = choice
        else:
            result = "done" if answered == total else ("partial" if answered else "skipped")
        return {"kind": kind, "result": result, "answered": answered, "total": total,
                "details": details,
                "summary": "已作答 %d / %d 题" % (answered, total)}

    if kind in ("choice", "fill", "match"):
        # 教材未提供可核对的答案来源（answer_status=NO_RELIABLE_SOURCE）：
        # 记录孩子自己的作答，但不伪造正误；结果由孩子自己判断。
        details = []
        answered = 0
        for q in questions.get("questions") or []:
            given = (form.get("q%d" % q["no"]) or "").strip()
            if given:
                answered += 1
            details.append({"no": q["no"], "given": given})
        for idx, item in enumerate(questions.get("items") or [], start=1):
            given = (form.get("m%d" % idx) or "").strip()
            if given:
                answered += 1
            details.append({"no": idx, "given": given, "item": item})
        choice = (form.get("self_check") or "").strip()
        mapping = {"done": ("done", "我完成了这次练习"),
                   "partial": ("partial", "还想再看一遍"),
                   "skipped": ("skipped", "这次先跳过")}
        result, label = mapping.get(choice, ("done", "我完成了这次练习"))
        return {"kind": kind, "result": result, "label": label, "details": details,
                "answered": answered,
                "answer_status": "NO_RELIABLE_SOURCE",
                "summary": label}

    # 自评
    choice = (form.get("self_check") or "").strip()
    mapping = {"done": ("done", "我完成了这次练习"),
               "partial": ("partial", "还想再看一遍"),
               "skipped": ("skipped", "这次先跳过")}
    result, label = mapping.get(choice, ("done", "我完成了这次练习"))
    return {"kind": kind, "result": result, "label": label, "details": [],
            "summary": label}


# ---------------------------------------------------------------------------
# P2-6-F-2：教材练习的正式结构（读取层实现）
#
#   * 教材原题按原题型呈现（choice / fill / match / short_answer）
#   * 词汇自测作为**独立能力**保留，不再替换教材原题（V1.2.1 七·3）
#   * 没有可靠答案事实 → 不生成 answer，不做正式判分（V1.2.1 七·9）
# ---------------------------------------------------------------------------

def _review_notes(exercise, material, box) -> list:
    """待人工核验的事项（只写进数据与页面提示，不写进正式教材事实）。"""
    notes = list((material or {}).get("review") or [])
    if box and box.get("review"):
        notes.append(box["review"])
    if exercise.get("question_type") == "order":
        notes.append("教材原题依赖图片顺序，图片不在数据内；本轮按教材原题列出项目")
    return notes


def build_questions(exercise, contentpack_path=CONTENTPACK) -> dict:
    """教材练习的作答结构（P2-6-F-2）。"""
    etype = exercise.get("type")
    unit = exercise.get("unit")
    qtype = exercise.get("question_type") or "other"
    items = list(exercise.get("check_items") or [])
    material = textbook_material(exercise, contentpack_path)
    box = page_word_box(exercise, contentpack_path)
    if box:
        options = [{"label": (chr(ord("a") + i) if i < 26 else str(i + 1)), "text": t}
                   for i, t in enumerate(box["items"])]
    else:
        options = textbook_options(exercise, contentpack_path)
    blanks = blank_count(exercise)
    mtext = material["text"] if material else ""
    review = _review_notes(exercise, material, box)
    fix = BLANK_FIX.get(exercise.get("exercise_id"))
    instruction = exercise.get("instruction") or ""

    textbook = {"instruction": exercise.get("instruction"),
                "question_type": qtype,
                "question_label": QUESTION_LABELS.get(qtype, "练习"),
                "items": items, "options": options, "blanks": blanks,
                "textbook_page": exercise.get("textbook_page"),
                "audio_confirmed": bool(exercise.get("audio_id")),
                "answer_status": exercise.get("answer_status") or "NO_RELIABLE_SOURCE",
                "blank_evidence": fix[1] if fix else None,
                "options_review": bool(box),
                "options_source": ("教材本页词框 %s" % box["block_id"]) if box else
                                  ("教材原页 ☐ 清单" if material and qtype in ("choice", "judge")
                                   else "教材目录字段")}

    out = {"kind": "self_check", "questions": [], "items": items, "options": options,
           "blanks": blanks, "textbook": textbook, "material": material,
           "page_word_box": box, "review": review, "answer_available": False,
           "structure_version": STRUCTURE_VERSION, "textbook_task": None,
           "vocab_selftest": None, "note": "这是教材上的练习。"}

    # 1) 词汇自测：既有能力保留（独立呈现，不再替换教材原题）
    if etype == "vocabulary":
        words = word_list_of_unit(unit, contentpack_path)
        picked = [w for w in words if w["requirement"] == "CORE"][:4] or words[:4]
        if picked:
            out["vocab_selftest"] = {
                "kind": "spelling",
                "questions": [{"no": i + 1, "meaning": w["meaning"], "answer": w["word"],
                               "phonetic": w["phonetic"], "item_id": w["item_id"]}
                              for i, w in enumerate(picked)],
                "note": "这是本单元教材词表的自测，和上面的教材原题是两件事。"}

    # 2) 教材原题型（V1.2.1 七·3：不得降级成“完成 / 未完成”）
    task = None
    if qtype in ("choice", "judge"):
        inline_choices = _inline_choices(mtext) if (not options and qtype == "choice" and mtext) else None
        if options or inline_choices:
            task = {"kind": "choice", "options": options, "multi": "tick" in instruction.lower(),
                    "inline_choices": inline_choices,
                    # 判断题每个空一个 F/O；教材本页词框（A10）每个空从词框里选一个
                    "groups": max(blanks, 1) if (qtype == "judge" or box) else 1,
                    "select": bool(box)}
    elif qtype == "fill":
        task = {"kind": "fill", "blanks": blanks,
                "inline": _inline_blanks(mtext, blanks) if mtext else None}
    elif qtype in ("match", "order"):
        task = {"kind": "match", "items": items}
    else:
        qs = sub_questions_for_activity(exercise, contentpack_path)
        if not qs and qtype == "short_answer" and instruction:
            qs = [instruction]
        if qs:
            task = {"kind": "short_answer", "questions": qs}

    if task:
        out["textbook_task"] = task
        if task["kind"] == "choice":
            out["kind"] = "choice"
            if task.get("inline_choices"):
                out["questions"] = [{"no": seg["choice"],
                                     "options": [{"label": "a", "text": seg["options"][0]},
                                                 {"label": "b", "text": seg["options"][1]}]}
                                    for seg in task["inline_choices"] if "choice" in seg]
            else:
                out["questions"] = [{"no": 1, "field": "t1", "options": options}] if options else []
            out["note"] = ("这是教材上的练习。按教材原题作答；教材没有提供可核对的答案，"
                           "本轮只记录你的作答，不做判分。")
        elif task["kind"] == "fill":
            out["kind"] = "fill"
            out["questions"] = [{"no": i + 1, "field": "t%d" % (i + 1)} for i in range(blanks)]
            out["note"] = ("这是教材上的练习。把教材上的空格填完；教材没有给出答案，"
                           "本轮只记录你的作答，不做判分。")
        elif task["kind"] == "match":
            out["kind"] = "match"
            out["questions"] = [{"no": i + 1, "field": "m%d" % (i + 1), "item": it}
                                for i, it in enumerate(items)]
            out["note"] = "这是教材上的练习。按教材原题完成；本轮只记录你的作答，不做判分。"
        elif task["kind"] == "short_answer":
            out["kind"] = "short_answer"
            out["questions"] = [{"no": i + 1, "text": q} for i, q in enumerate(task["questions"])]
            out["note"] = "用教材里的信息回答；答完可以自己再改一遍。"

    # 3) 词汇型练习：主表单仍是既有词汇自测（能力保留），教材原题在上方单独呈现
    if out["vocab_selftest"]:
        out["kind"] = "spelling"
        out["questions"] = out["vocab_selftest"]["questions"]
        out["note"] = "教材原题在上面；下面的自测来自本单元教材词表。"
    return out


def _textbook_details(questions, form) -> list:
    details = []
    for q in questions.get("questions") or []:
        field = q.get("field") or ("q%d" % q["no"])
        given = (form.get(field) or "").strip()
        detail = {"no": q["no"], "given": given, "field": field}
        if q.get("item"):
            detail["item"] = q["item"]
        details.append(detail)
    return details


def grade(exercise, questions: dict, form: dict) -> dict:
    """教材练习的作答记录（P2-6-F-2）。

    本轮没有可靠答案事实（V1.2.1 七·9）：教材原题只记录孩子的作答，不做正式判分；
    词汇自测仍按教材词表做确定性规则判分（既有能力保留）。
    """
    kind = questions.get("kind")
    if kind == "spelling":
        details, correct = [], 0
        for q in questions["questions"]:
            given = (form.get("q%d" % q["no"]) or "").strip()
            ok = _normalize_answer(given) == _normalize_answer(q["answer"])
            correct += 1 if ok else 0
            details.append({"no": q["no"], "meaning": q["meaning"], "given": given,
                            "answer": q["answer"], "correct": ok})
        total = len(questions["questions"])
        result = "correct" if correct == total else ("partial" if correct else "incorrect")
        return {"kind": kind, "result": result, "correct": correct, "total": total,
                "details": details, "answer_available": True,
                "textbook_details": _textbook_details(questions, form),
                "summary": "写对 %d / %d 个" % (correct, total)}

    if kind == "short_answer":
        from ai_grading import analyze_short_answer     # 本地模块，不联网
        details, answered = [], 0
        for q in questions["questions"]:
            given = (form.get("q%d" % q["no"]) or "").strip()
            if given:
                answered += 1
            details.append({"no": q["no"], "question": q["text"], "given": given,
                            "analysis": analyze_short_answer(q["text"], given)})
        total = len(questions["questions"])
        choice = (form.get("self_check") or "").strip()
        if answered == 0 and choice in ("done", "partial", "skipped"):
            result = choice
        else:
            result = "done" if answered == total else ("partial" if answered else "skipped")
        return {"kind": kind, "result": result, "answered": answered, "total": total,
                "details": details, "answer_available": False,
                "summary": "已作答 %d / %d 题" % (answered, total)}

    # choice / fill / match：只有作答事实，没有答案事实 → 不判分
    details = _textbook_details(questions, form)
    answered = sum(1 for d in details if d.get("given"))
    return {"kind": kind, "result": "done", "details": details, "answered": answered,
            "answer_available": False, "answer_status": "NO_RELIABLE_SOURCE",
            "label": "已记录你的作答",
            "summary": "已记录你的作答（教材没有提供可核对的答案，本轮不做判分）"}

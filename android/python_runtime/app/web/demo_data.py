#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""全功能 Demo V1 演示数据层（Demo View Model / Demo Data Provider）

边界（严格遵守最高指导原则 V1.3 / 产品与 UI 架构总纲 V2.0）：

* **零写入**：本模块不连接 learning.db，不创建任何学习记录、掌握状态或会话。
* **零 AI**：全部演示内容都是模块内静态文案，不调用任何外部服务。
* **不伪造能力**：这里只模拟「最近学习记录 / 学习时长 / 掌握状态 / 薄弱点 /
  AI 分析 / AI 建议 / 进展 / 一次练习结果」——这些都是 Demo V1 明示允许的演示数据。
* **不伪造教材事实**：演示练习题只使用真实教材内容（教材原文句子、教材词表释义、
  教材句型），参考答案可由教材内容本身验证；页面上明确标注为「演示题」，
  不伪装成教材答案。
* **不伪造语音评分**：跟读只记录「已完成一次跟读」这类事实，不产生任何分数。

页面上的演示信息统一带「演示数据」标记，且说明「不是真实学习记录，不会写入学习库」。
演示模式由 `DEMO_MODE` 控制，页面不依赖它做业务判断（真正的数据保护在服务层）。
"""

from __future__ import annotations

import base64
import datetime
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
for _p in (str(BASE / "learning"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.dont_write_bytecode = True

import json as _json
import study_call_service as scs          # noqa: E402  P6-A：正式学习调用层（唯一题目/状态来源）

#: Demo V1 演示模式开关（仅影响演示数据层自身）
DEMO_MODE = True

#: 孩子可见的演示标记（克制使用：只在演示数据块顶部出现一次）
DEMO_LABEL = "演示数据"

#: 演示数据的统一说明（诚实边界，避免被误读为真实学习记录）
DEMO_NOTE = "以下是演示数据，用来完整展示这个页面的样子；它不会写入你的学习记录。"

#: 当前演示单元
DEMO_UNIT_CODE = "Unit 1"
DEMO_UNIT_SLUG = "unit1"


# ---------------------------------------------------------------------------
# 三、学习证据与学习进度（演示数据；不代表掌握程度）
# ---------------------------------------------------------------------------

#: 当前值得关注（演示薄弱点）
#  text         孩子看到的内容
#  note         它是什么（教材重点词 / 教材句子里的表达）
#  basis        教材依据（真实来源，可核对）
#  link         回到教材的入口（尽量落到真实页面）
#  last         上次的自我判断（演示）
ATTENTION = (
    {"text": "nervous", "note": "教材重点词",
     "basis": "教材 Unit 1 词汇表",
     "link": "/unit/%s/resources/vocabulary" % DEMO_UNIT_SLUG,
     "last": "上次有点模糊"},
    {"text": "make good use of", "note": "教材句子里的表达",
     "basis": "Unit 1 · 教材句子（已人工核验的句子级音频）",
     "link": "/unit/%s/text" % DEMO_UNIT_SLUG,
     "last": "上次忘了"},
    {"text": "share some thoughts", "note": "教材句子里的表达",
     "basis": "Unit 1 · 教材句子（已人工核验的句子级音频）",
     "link": "/unit/%s/text" % DEMO_UNIT_SLUG,
     "last": "上次有点模糊"},
)

# ---------------------------------------------------------------------------
# 四、Demo V1.1：课堂同步结构（当前课堂 / AI 诊断 / 今日特训 / 我的进展）
# ---------------------------------------------------------------------------

#: 当前真实教材（只读事实，来自 contentpack）
BOOK_SHORT = "七年级上册"
BOOK_LONG = "外研社《义务教育教科书·英语 七年级上册》（2022 年课程标准修订）"

#: 演示学习时长
WEEK_MINUTES = 32
TODAY_MINUTES = 8

#: 真实教材层级说明（V1.1 设计文档 §2.1）：
#: 教材不存在 Module 层级，因此课堂位置只有“教材册次 → 单元”两级。
HIERARCHY_NOTE = "教材按 Unit 编排"


def classroom(unit_code: str, unit_title: str, pages: str = "",
              sentence_audio_count: int = 0) -> dict:
    """首页「当前课堂」：课堂位置 + 本周学习时间（课堂位置来自真实教材数据）。"""
    return {
        "book": BOOK_SHORT,
        "book_long": BOOK_LONG,
        "unit_code": unit_code,
        "unit_title": unit_title,
        "pages": pages,
        "week_minutes": WEEK_MINUTES,
        "today_minutes": TODAY_MINUTES,
        "week_line": "本周已学习 %d 分钟" % WEEK_MINUTES,
        "hierarchy_note": HIERARCHY_NOTE,
        "sentence_audio_count": sentence_audio_count,
    }


#: ---------------------------------------------------------------------------
#: Demo V1.1 修正：AI 随堂助教 = 章节内容分析 + 章节学习状态驱动
#: ---------------------------------------------------------------------------
#: 设计要点（对应任务书 §六–§十四）：
#:   * AI 文案与建议由「当前章节的真实教材内容」+「本机该章节的学习状态」确定性推导，
#:     不是三个固定字符串，也不按访问次数轮换；
#:   * 没有学习行为时只说“这一章应该学什么”，不评价孩子；
#:   * 学习状态只能被学习行为（跟读 / 练习 / 课文点读）改变，
#:     打开页面、刷新、切换章节都不会改变；
#:   * 状态按章节隔离，互不污染；
#:   * 全程不调用 AI、不写 learning.db。

#: 章节学习环节（顺序即训练顺序；key 只用于本机演示状态，孩子看不到）
DEMO_STEPS = (
    ("vocabulary", "单词跟读"),
    ("phrase", "短语练习"),
    ("reading", "课文点读与阅读"),
    ("listening", "听力练习"),
    ("shadowing", "句子跟读"),
)
DEMO_STEP_KEYS = tuple(key for key, _ in DEMO_STEPS)
DEMO_STEP_LABELS = dict(DEMO_STEPS)

#: 每个环节巩固时要提醒的一句话（由环节性质决定，不随章节变化）
STEP_HINT = {
    "vocabulary": "可以再听一遍标准音，跟着读一次",
    "phrase": "可以再练一次这一课的表达，会更稳",
    "reading": "建议回到课文再读一遍",
    "listening": "可以用教材原声再听一次",
    "shadowing": "可以挑一句教材原句再录一遍",
}


# ---------------------------------------------------------------------------
# 第二版 Demo：今天学什么 / 段落点读 / AI助教 / 跟读结果（演示数据）
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# P6-A：正式首页六入口（冻结口径）—— 状态与可见性全部由正式学习调用层决定
# ---------------------------------------------------------------------------

#: 正式六入口（产品与UI架构总纲 V2.0 §5.1 固定顺序）
ENTRY_ORDER_FORMAL = (
    ("read", "跟读练习", "e-word", "mic"),
    ("listen", "听音辨意", "e-quiz", "headphones"),
    ("wordform", "词形练习", "e-phrase", "book"),
    ("check", "本课检测", "e-quiz", "check"),
    ("text", "听读课文", "e-word", "book"),
    ("practice", "自主练习", "e-phrase", "pen"),
)
#: 不进入六项学习功能入口的非教学 Block（V1.3 第二十九章 §15·3：Appendix 不是普通教学 Unit）
NON_TEACHING_UNITS = ("Appendix",)


#: 入口学习状态（2026-10-01 UI-7 第 2 件）。
STATUS_NOT_STARTED = "未开始"
STATUS_IN_PROGRESS = "正在进行"
STATUS_DONE = "已完成"

#: 状态需要按 **Unit** 判断的入口（Unit 级题型，没有 Section 归属）
UNIT_LEVEL_STATUS_ENTRIES = ("wordform",)

#: **「已完成」口径（2026-10-01 用户裁定）**：该入口/Section 的候选池**覆盖率 ≥ 80%**
#: 即算「已完成」——**不再要求全对**（原来要求"全覆盖 + 全对"，实际数据下几乎不可能达成）。
#: 只在这里定义一次；首页六入口状态与单元中心课时进度**同源**使用。
STATUS_DONE_COVERAGE = 0.8

#: **题型 → 孩子看得懂的中文名**（单元中心二期，2026-10-01）
#: 15 种 `question_type` 全覆盖；用词与既有入口/模式标签一致（不新造名词）。
QUESTION_TYPE_LABELS = {
    "textbook_native": "课文理解",
    "vocab_meaning_choice": "词义选择",
    "vocab_listen_write": "听音写词",
    "vocab_phonetic_write": "音标写词",
    "phonetics_symbol_write": "音标写词",
    "phonetics_sound_choice": "听音辨音",
    "vocab_word_form": "词形变化",
    "vocab_context_choice": "语境选词",
    "phrase_meaning_choice": "短语辨义",
    "sentence_listen_write": "听句写句",
    "sentence_listen_choice": "听句选句",
    "listening_choice": "听辨选择",
    "listen_choice": "听辨选择",
    "listen_fill": "听音填空",
    "reading_choice": "阅读选择",
}

#: **题型分类（D-1，教学依据 = "记忆提取" vs "规则/意义加工"）**
#: * **背诵类**：答案要求逐字/逐音还原，答错基本是"没记住"⇒ AI **只给统计 + 一句意见**；
#: * **理解类**：答错可能源于规则没掌握 / 语境没读懂 ⇒ AI **可讲"错在哪、该怎么做"**。
#: 边界：词义/短语/语音选择形态是"选择"，但本质是**再认（记忆）**⇒ 归背诵；
#: `vocab_context_choice` 是"在句子语境里选词"，要理解语境 ⇒ 归理解。
CATEGORY_RECITE = "背诵"
CATEGORY_COMPREHEND = "理解"
QUESTION_TYPE_CATEGORY = {
    "vocab_phonetic_write": CATEGORY_RECITE,
    "vocab_listen_write": CATEGORY_RECITE,
    "sentence_listen_write": CATEGORY_RECITE,
    "phonetics_symbol_write": CATEGORY_RECITE,
    "vocab_meaning_choice": CATEGORY_RECITE,
    "phrase_meaning_choice": CATEGORY_RECITE,
    "phonetics_sound_choice": CATEGORY_RECITE,
    "vocab_word_form": CATEGORY_COMPREHEND,
    "vocab_context_choice": CATEGORY_COMPREHEND,
    "textbook_native": CATEGORY_COMPREHEND,
    "reading_choice": CATEGORY_COMPREHEND,
    "listening_choice": CATEGORY_COMPREHEND,
    "sentence_listen_choice": CATEGORY_COMPREHEND,
    "listen_choice": CATEGORY_COMPREHEND,
    "listen_fill": CATEGORY_COMPREHEND,
}

#: **题干字段白名单**：只把这些 `prompt_json` 字段给 AI。
#: **剔除**：`audio_url` / `segment_id` / `start_ms` / `end_ms` / `generation_run_id` /
#: `resource_identity` / `evidence_block_id` / `audio_source_code` / `sentence_uid` /
#: `question_origin` / `distractor_origin` / `in_contentpack_activity` / `evidence_class`。
MISTAKE_PROMPT_FIELDS = ("instruction", "text", "phonetic", "phonetic_symbol",
                         "base", "part_of_speech", "blank_count")
#: 错题明细每条**只允许**这些键（防内部字段外泄）
MISTAKE_FIELDS = ("point", "category", "where", "prompt", "picked", "answer",
                  "wrong_times")
#: 错题明细上限（D-1 裁定：最多 5 条）
MISTAKE_MAX = 5

#: **入口 → 它实际覆盖的知识点名**（单元中心二期·A 修补，2026-10-01）
#: 为什么需要：入口名与知识点名**是两套命名体系**（"单词听辨"练的是"听音写词"这类题），
#: 只按名字相同匹配会让绝大部分入口永远不参与排序。
#: 依据：`scs.allowed_types(entry, mode)` 与六入口定义（**题型范围**，非新造规则）。
ENTRY_POINT_LABELS = {
    ("wordform", "phonetic"): ("音标写词", "听音辨音"),
    ("wordform", "form"): ("词形变化",),
    ("listen", "word"): ("听音写词", "词义选择"),
    ("listen", "sentence"): ("听句写句", "听句选句"),
    ("check", ""): ("课文理解", "词义选择", "听音写词", "音标写词", "词形变化",
                    "语境选词", "短语辨义", "阅读选择", "听辨选择", "听音填空"),
    ("read", "word"): (),
    ("practice", ""): (),          # 跨 Section 综合，不绑定单一知识点
}

#: **程度词（只 3 个）**。判定完全照 `mastery_rules_v1.json → stable.*`，
#: **不读 `mastery_state.mastery_level`**（实测 7/7 全是 unknown，读它没意义）。
#: **显示层程度词（四档，2026-10-01 二期·A 裁定）**——只看"练了几题 + 答对多少"，
#: 不用"跨天 / 跨题型"的严门槛（那套太严，实际会长期停在"还不太熟"，孩子看不到进展）。
LEVEL_NOT_PRACTICED = "还没练"
LEVEL_PRACTICING = "还在练"
LEVEL_GOOD = "练得不错"
LEVEL_NEED_MORE = "还要多练"
#: 兼容旧名（内部判定仍会用到"是否需复习"的概念）
LEVEL_LEARNING = LEVEL_PRACTICING
LEVEL_FAMILIAR = LEVEL_GOOD

#: **显示层档位门槛**（集中定义）
DISPLAY_PRACTICING_MAX = 4        # 1–4 题 → 还在练
DISPLAY_GOOD_MIN_PRACTICED = 5    # ≥5 题才谈"练得不错 / 还要多练"
DISPLAY_GOOD_MIN_ACCURACY = 70    # 答对率 ≥70% → 练得不错；否则 → 还要多练

#: **程度词"更弱档"顺序**（二期·B 同名合并用）：合并两个同名知识点时取**更弱**的那档。
LEVEL_WEAKER_ORDER = (LEVEL_NOT_PRACTICED, LEVEL_PRACTICING, LEVEL_NEED_MORE, LEVEL_GOOD)

#: **入口分槽**（二期·B 按钮分槽）：专项入口 = 针对某一类知识点的练习；
#: 综合入口 = 覆盖多类知识点的检测/练习。补一补只从专项取。
SPECIALIST_ENTRIES = ("wordform", "listen", "read")
COMPREHENSIVE_ENTRIES = ("check", "practice")

#: 门槛（与 mastery_rules_v1.json 的 stable.* 一致；集中定义，便于以后随规则文件调整）
MASTERY_MIN_EVIDENCE = 3         # minimum_valid_evidence
MASTERY_MIN_TASK_TYPES = 2       # minimum_task_types
MASTERY_MIN_NATURAL_DAYS = 2     # minimum_natural_days
MASTERY_RECENT_WINDOW = 3        # recent_attempt_window
MASTERY_RECENT_CORRECT = 2       # recent_correct_minimum

#: **AI 学情分析门槛**（规格第四节）：练题数 < 此值不调 AI，显示"再练几题就能看到分析啦"
ANALYZE_MIN_PRACTICED = 10
ANALYZE_MIN_PER_POINT = 3        # 单知识点不足此题数时，优缺点强制为空


def _evidence_progress(item_ids, learner_id, learning_db) -> tuple:
    """(已产生证据的条目数, 是否全对) —— 按 **learning_item id** 查 `learning_record`。

    为什么按 item_id 而不是 question_id：`learning_record.item_id` 的语义是
    **learning_item id**（实测：与 `question.question_id` 交集 = 0，与 `question.source_item_id`
    交集 = 7）⇒ question → item 的映射必须在**题库侧**完成（由 `app.entry_questions` 做），
    本模块只在**学习库内**查证据（单库操作，不跨库 JOIN）。

    只读；读不到一律返回 (0, False)（= 未开始），不抛错、不写库。
    """
    ids = [q for q in dict.fromkeys(item_ids or []) if q]
    if not ids or not learner_id:
        return 0, False
    try:
        conn = scs.connect_learning_db_ro(learning_db)
    except Exception:                                  # noqa: BLE001
        return 0, False
    try:
        marks = ",".join("?" * len(ids))
        rows = list(conn.execute(
            "SELECT DISTINCT item_id, result FROM learning_record "
            "WHERE item_id IN (%s) AND learner_id = ?" % marks,
            tuple(ids) + (learner_id,)))
    except Exception:                                  # noqa: BLE001 —— 读不到按"未开始"
        return 0, False
    finally:
        conn.close()
    answered = len({r[0] for r in rows if r[0]})
    wrong = {r[0] for r in rows if r[0] and (r[1] or "") not in ("correct", "done")}
    return answered, (answered >= len(ids) and not wrong)


def entry_status_text(entry_key: str, count: int) -> str:
    """**旧口径（保留兼容）**：候选资源数文案。

    2026-10-01（UI-7 第 2 件）起，首页六入口改用 `entry_learning_status()`；
    本函数保留给仍需要"候选数"口径的调用方 / 测试，不再由首页使用。
    """
    return "候选 %d 项" % int(count) if entry_key == "read" else "候选 %d 题" % int(count)


def entry_learning_status(question_ids, learner_id, learning_db,
                          total: int = 0, item_ids=None) -> str:
    """**新口径（UI-7 第 2 件）**：未开始 / 正在进行 / 已完成。

    * `question_ids`：该入口**当前课时（或 Unit）候选池**的 question_id 集合；
    * `item_ids`：与之对应的 **learning_item id** 集合（证据按此查；缺省时退回用
      `question_ids` 试查 —— 兼容只关心条数的调用方）；
    * `total`：候选池大小（外部已算好时可直接给）；
    * 判定（2026-10-01 改口径）：无证据 → 未开始；**覆盖率 ≥ STATUS_DONE_COVERAGE（80%）
      → 已完成**（**不再要求全对**）；否则 → 正在进行。
    """
    ids = [q for q in dict.fromkeys(question_ids or []) if q]
    iids = [i for i in dict.fromkeys(item_ids or []) if i]
    n = int(total or len(ids) or len(iids) or 0)
    if n <= 0:
        return STATUS_NOT_STARTED
    answered, _all_right = _evidence_progress(iids or ids, learner_id, learning_db)
    if answered <= 0:
        return STATUS_NOT_STARTED
    if n > 0 and answered >= n * STATUS_DONE_COVERAGE:
        return STATUS_DONE
    return STATUS_IN_PROGRESS


def formal_entries(unit_code: str, unit_slug: str, learner_id: str, pool,
                   modes=None, non_teaching_units=NON_TEACHING_UNITS,
                   learning_db=None, section_key: str = "",
                   entry_questions=None) -> list:
    """正式六入口（P6-B-12-FIX S1）：显隐与文案按**当前 Section 的真实可调用资源**判定。

    * `pool(entry, mode) -> list`：**必须**由调用方传入，且必须是**功能页同一条池函数**
      （`app._p5_items`）——保证「主页入口显隐」与「次页实际资源池」完全一致，不以 Unit 总量代替；
    * 多模式入口（read / listen）：任一模式有真实资源即显示该入口，文案取各模式候选数之和；
      单模式入口（phonetic / form / check / practice）：池为空即不显示；
    * `non_teaching_units`（默认 Appendix）：**显式**不进入六项功能入口——不调用教学 Unit 专属池，
      **不依赖异常被吞掉**来实现隐藏（V1.3 §15·3）；
    * 池函数抛错时**不在此处吞掉**：异常向上抛出，由调用方记录并暴露（异常应可被发现）。

    2026-10-01（UI-7 第 2 件）：`status` 由「候选数」改为**学习状态**（未开始 / 正在进行 /
    已完成）。判据 = 该入口**候选池对应的题目集合**在 `learning_record` 里的证据覆盖情况：
      * `entry_questions(key)` 需由调用方传入（返回该入口的 question_id 集合；缺省时退化为
        「没有证据」= 未开始，不会误报）；
      * `learning_db` 为学习库路径（只读打开；读取失败按未开始，不抛错、不写库）；
      * **词形变化（wordform）按 Unit 判断**（`UNIT_LEVEL_STATUS_ENTRIES`）。
    """
    if unit_code in tuple(non_teaching_units or ()):
        return []
    modes = dict(modes or {})
    out = []
    for key, label, cls, ico in ENTRY_ORDER_FORMAL:
        if key == "text":
            # 「听读课文」= /unit/<slug>/text：正文 + 官方音频，**不走题目池**。
            # 显隐由调用方通过 modes["text"] 显式表达（非题目资源，不能用题目数判定）。
            avail = int(modes.get("text", (0,))[0] or 0)
            if avail <= 0:
                continue
            # 「听读课文」不是题目池：它没有"作答证据"，状态只可能有「未开始 / 已完成」两态，
            # 判据 = 该 Unit 是否有可读正文（有则该入口已可用）。保持与题目型入口同一套标签，
            # 不引入第四个状态、不伪造"进行中"。
            out.append({"key": key, "label": label, "cls": cls, "icon": ico,
                        "href": "/unit/%s/text" % unit_slug,
                        "status": (STATUS_DONE if avail > 0 else STATUS_NOT_STARTED),
                        "status_kind": "text",
                        "text_sections": int(avail),
                        "done": avail > 0})
            continue
        entry_modes = tuple(modes.get(key) or ("",))
        total = sum(len(pool(key, mode) or []) for mode in entry_modes)
        if total <= 0:
            continue
        # 学习状态（UI-7 第 2 件）：按入口候选池的题目集合查证据覆盖。
        qids, iids = [], []
        if callable(entry_questions):
            try:
                got = list(entry_questions(key, unit_code, section_key) or [])
            except Exception as exc:                   # noqa: BLE001 —— 取不到就按"未开始"
                print("[web] 入口题目集合读取失败（%s）：%r" % (key, exc))
                got = []
            # 兼容两种返回：question_id 字符串 / {"question_id","item_id"} 字典。
            for g in got:
                if isinstance(g, dict):
                    if g.get("question_id"):
                        qids.append(g["question_id"])
                    if g.get("item_id"):
                        iids.append(g["item_id"])
                elif g:
                    qids.append(g)
        status = entry_learning_status(qids, learner_id, learning_db,
                                       total=total, item_ids=iids)
        out.append({"key": key, "label": label, "cls": cls, "icon": ico,
                    "href": "/unit/%s/p5/%s" % (unit_slug, key),
                    "status": status, "status_kind": "questions",
                    "question_total": int(total), "done": status == STATUS_DONE})
    return out


def parse_state(raw: str) -> dict:
    """解析本机演示学习状态（只接受已知章节与已知环节，越界内容直接忽略）。"""
    out = {}
    for chunk in (raw or "").split("|"):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        slug, _, steps = chunk.partition(":")
        slug = slug.strip().lower()
        if not slug or len(slug) > 24 or not all(c.isalnum() or c in "-_" for c in slug):
            continue
        picked = {}
        for item in steps.split(","):
            item = item.strip()
            if not item:
                continue
            key, _, value = item.partition("=")
            key = key.strip()
            if key not in DEMO_STEP_KEYS:
                continue
            picked[key] = "partial" if value.strip() == "partial" else "done"
        if picked:
            out[slug] = picked
    return out


def dump_state(state: dict) -> str:
    """把演示学习状态编码为本机 Cookie 值（按固定顺序，便于稳定比较）。"""
    chunks = []
    for slug in sorted(state or {}):
        picked = state[slug] or {}
        items = []
        for key in DEMO_STEP_KEYS:
            if key in picked:
                items.append(key if picked[key] == "done" else key + "=partial")
        if items:
            chunks.append("%s:%s" % (slug, ",".join(items)))
    return "|".join(chunks)


def steps_of(state: dict, slug: str) -> dict:
    """当前章节的学习状态（其它章节的状态不会出现在这里）。"""
    return dict((state or {}).get(slug) or {})


# ---------------------------------------------------------------------------
# 错题池（演示，本机 Cookie）：只是「学习证据」，不是新的产品中心
#
# 允许表达的最小信息：题号 / 章节 / 题型 / 正确答案 / 孩子答案 / 错误次数 /
# 最近错误时间 / 后续是否答对。全部只存在孩子的浏览器里（Cookie），
# 不写正式 learning.db，不做自动布置、不做排行榜、不做积分。
# ---------------------------------------------------------------------------

WRONG_POOL_LIMIT = 12


def _pool_int(value, low: int = 0, high: int = 99) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return low


def parse_pool(raw: str) -> dict:
    """解析本机错题池（损坏 / 越界内容一律忽略，不猜测）。"""
    out = {}
    if not raw:
        return out
    try:
        pad = "=" * (-len(raw) % 4)
        blob = base64.urlsafe_b64decode((raw + pad).encode("ascii"))
        rows = json.loads(blob.decode("utf-8"))
    except Exception:
        return out
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        qid = str(row.get("qid") or "").strip()[:64]
        if not qid:
            continue
        out[qid] = {
            "qid": qid,
            "unit": str(row.get("unit") or "")[:24],
            "kind": str(row.get("kind") or "")[:24],
            "correct": str(row.get("correct") or "")[:80],
            "answer": str(row.get("answer") or "")[:80],
            "count": _pool_int(row.get("count"), 1, 99),
            "last": _pool_int(row.get("last"), 0, 2 ** 31),
            "fixed": bool(row.get("fixed")),
        }
    return out


def dump_pool(pool: dict) -> str:
    """把错题池编码为本机 Cookie 值（按 qid 排序，便于稳定比较）。"""
    rows = []
    for qid in sorted(pool or {}):
        e = pool[qid]
        rows.append({"qid": e["qid"], "unit": e["unit"], "kind": e["kind"],
                     "correct": e["correct"], "answer": e["answer"],
                     "count": _pool_int(e.get("count"), 1, 99),
                     "last": _pool_int(e.get("last"), 0, 2 ** 31),
                     "fixed": bool(e.get("fixed"))})
    blob = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    return base64.urlsafe_b64encode(blob.encode("utf-8")).decode("ascii").rstrip("=")


def note_answer(pool: dict, entry: dict, ok: bool, at: int = 0) -> dict:
    """记录一次作答结果：答错 → 进池 / 次数 +1；答对且已在池里 → 标记「已改对」。"""
    qid = str((entry or {}).get("qid") or "").strip()[:64]
    if not qid:
        return pool
    when = _pool_int(at, 0, 2 ** 31)
    row = pool.get(qid)
    if row is None:
        if ok:
            return pool                     # 没做错过、这次也对了 → 不需要记录
        row = {"qid": qid, "unit": str(entry.get("unit") or "")[:24],
               "kind": str(entry.get("kind") or "")[:24],
               "correct": str(entry.get("correct") or "")[:80],
               "answer": str(entry.get("answer") or "")[:80],
               "count": 1, "last": when, "fixed": False}
        pool[qid] = row
    elif ok:
        row["fixed"] = True                 # 重新做对了 → 状态改善
        row["last"] = when
        row["answer"] = str(entry.get("answer") or "")[:80]
    else:
        row["count"] = _pool_int(row.get("count", 1) + 1, 1, 99)
        row["last"] = when
        row["fixed"] = False
        row["answer"] = str(entry.get("answer") or "")[:80]
        row["correct"] = str(entry.get("correct") or row.get("correct") or "")[:80]
    if len(pool) > WRONG_POOL_LIMIT:        # 只保留最近的若干条，Cookie 不会被撑爆
        order = sorted(pool, key=lambda k: pool[k].get("last", 0))
        for qid in order[:len(pool) - WRONG_POOL_LIMIT]:
            pool.pop(qid, None)
    return pool


def pool_pending(pool: dict, unit: str = "") -> dict:
    """还没改对的错题（可按章节过滤）：用来让孩子以后主动练习时再遇到它们。"""
    return {qid: e for qid, e in (pool or {}).items()
            if not e.get("fixed") and (not unit or e.get("unit") == unit)}


def stage_of(steps: dict) -> str:
    """学习阶段：未开始 / 已开始 / 正在巩固 / 基本覆盖（不产生掌握分数）。"""
    done = [k for k in DEMO_STEP_KEYS if steps.get(k) == "done"]
    partial = [k for k in DEMO_STEP_KEYS if steps.get(k) == "partial"]
    if not done and not partial:
        return "not_started"
    if len(done) >= len(DEMO_STEP_KEYS):
        return "mostly_stable"
    if len(done) + len(partial) >= 3:
        return "consolidating"
    return "started"


#: 章节内容主题（只读摘要：由教材单元标题与内容概括，不评价孩子）
UNIT_THEME = {
    "Starter": "认识新学校、自我介绍和开学准备",
    "Unit 1": "新学期、新学校生活和时间安排",
    "Unit 2": "兴趣、音乐和课余活动",
    "Unit 3": "家庭与家人",
    "Unit 4": "节日与庆祝",
    "Unit 5": "植物与自然",
    "Unit 6": "动物与朋友",
    "Appendix": "教材附录（词汇表与句型汇总）",
}


def chapter_ai(unit_code: str, focus: dict, steps: dict) -> dict:
    """按「章节真实内容 + 本机学习状态」推导 AI 随堂助教内容（Demo V1.2：最多 3 项）。

    focus: {"key_points": [(text, note), ...], ...}
           —— 全部来自当前章节真实教材内容（app 层装配，已按价值排序）。
    steps: {"vocabulary": "done"/"partial", ...} —— 只包含当前章节。

    产品原则（V1.2 §五 / §六）：
      * 没有学习证据时**只告诉孩子最值得先学的 3 个知识点**，不分类、不统计、不解释整章结构；
      * 有学习证据之后才说“现在学得怎么样”，最多仍然只显示 3 项；
      * 不评价孩子，不产生虚假分数。
    """
    stage = stage_of(steps)
    theme = UNIT_THEME.get(unit_code) or "这一单元"
    done_labels = [DEMO_STEP_LABELS[k] for k in DEMO_STEP_KEYS if steps.get(k) == "done"]
    left_labels = [DEMO_STEP_LABELS[k] for k in DEMO_STEP_KEYS if steps.get(k) != "done"]
    key_points = [{"text": t, "note": n} for t, n in (focus.get("key_points") or [])][:3]

    if stage == "not_started":
        diagnosis = [
            "这一单元主要围绕%s展开。" % theme,
            "先把课文、重点词汇和核心表达熟悉起来，再做针对性练习。",
        ]
        list_title = "这一章最值得先学的 %d 个" % len(key_points) if key_points else ""
        items = key_points
    else:
        if done_labels:
            head = "你已经完成了 %s 的%s。" % (unit_code, "、".join(done_labels))
        else:
            head = "你已经开始学习 %s。" % unit_code
        if stage == "mostly_stable":
            diagnosis = [head,
                         "这节内容整体已经覆盖，可以挑一个想再练的，也可以先结束今天学习。"]
            list_title = "可以再练一次"
            items = key_points
        else:
            diagnosis = [head, "整体基础不错，" + _left_sentence(left_labels)]
            items = _left_items(steps, left_labels)[:3]
            list_title = "还有 %d 个地方值得再巩固" % len(items) if items else ""
    return {
        "stage": stage,
        "unit_code": unit_code,
        "diagnosis": diagnosis,
        "list_title": list_title,
        "items": items,
        "note": "这是演示诊断，不是真实 AI 判断；也没有调用 AI。",
    }


def _left_sentence(left_labels) -> str:
    """把"还需要巩固的环节"写成人能读的一句话（不制造压力）。"""
    if not left_labels:
        return "可以再换一个角度练一遍。"
    if len(left_labels) <= 2:
        return "当前更值得继续巩固的是%s。" % "、".join(left_labels)
    return "当前更值得继续巩固的是%s等 %d 个环节。" % ("、".join(left_labels[:2]),
                                                len(left_labels))


def _left_items(steps: dict, left_labels) -> list:
    """已开始学习时：列出还没有练的环节 + 该环节的巩固提醒（最多 3 项）。"""
    items = []
    for key in DEMO_STEP_KEYS:
        state = steps.get(key)
        if state == "done":
            continue
        note = "已经接触过，可以再用一次" if state == "partial" else STEP_HINT[key]
        items.append({"text": DEMO_STEP_LABELS[key], "note": note})
    return items


#: 我的进展（家长可读；演示数据）。口语练习只给“次数”，不给分数。
#: Demo V1.1 修正：数值按章节给，切换章节必须看到不同章节的进展。
CHAPTER_PROGRESS = {
    "Starter": (
        ("课文理解", "92%", 92, "Starter 的自我介绍和课文已经比较熟"),
        ("句型语法", "75%", 75, "This is... / I like... 这些句型已经能用"),
        ("口语练习", "8 次", None, "本周完成 8 次跟读"),
    ),
    "Unit 1": (
        ("课文理解", "88%", 88, "本周 Unit 1 课文理解较稳定"),
        ("句型语法", "60%", 60, "部分句型还需要继续巩固"),
        ("口语练习", "6 次", None, "本周完成 6 次跟读"),
    ),
    "Unit 2": (
        ("课文理解", "62%", 62, "Unit 2 的课文读过一遍，还在熟悉"),
        ("句型语法", "45%", 45, "这一章的句型刚接触"),
        ("口语练习", "3 次", None, "本周完成 3 次跟读"),
    ),
    "Unit 3": (
        ("课文理解", "35%", 35, "Unit 3 的课文刚开始读"),
        ("句型语法", "25%", 25, "这一章的句型还没有系统练过"),
        ("口语练习", "1 次", None, "本周完成 1 次跟读"),
    ),
    "Unit 4": (
        ("课文理解", "12%", 12, "这一章学校还没开始，先作为预习了解"),
        ("句型语法", "8%", 8, "这一章学校还没开始"),
        ("口语练习", "0 次", None, "这一章还没有跟读记录"),
    ),
    "Unit 5": (
        ("课文理解", "10%", 10, "这一章学校还没开始，先作为预习了解"),
        ("句型语法", "5%", 5, "这一章学校还没开始"),
        ("口语练习", "0 次", None, "这一章还没有跟读记录"),
    ),
    "Unit 6": (
        ("课文理解", "8%", 8, "这一章学校还没开始，先作为预习了解"),
        ("句型语法", "5%", 5, "这一章学校还没开始"),
        ("口语练习", "0 次", None, "这一章还没有跟读记录"),
    ),
    "Appendix": (
        ("课文理解", "—", None, "附录不是课文单元，可以按需查阅"),
        ("句型语法", "—", None, "附录里是词汇表和句型汇总"),
        ("口语练习", "0 次", None, "附录没有跟读内容"),
    ),
}

PROGRESS_PLAIN = ("口语练习只记录“练了几次”，不判断发音好坏；"
                  "系统的正式评价需要真实学习证据。")


def parent_progress(unit_code: str = DEMO_UNIT_CODE) -> dict:
    """当前章节的三个进展维度（演示数据；不同章节给不同数值）。"""
    triple = CHAPTER_PROGRESS.get(unit_code) or CHAPTER_PROGRESS[DEMO_UNIT_CODE]
    keys = ("text", "grammar", "speaking")
    rows = []
    for key, (label, value, percent, note) in zip(keys, triple):
        rows.append({"key": key, "label": label, "value": value,
                     "percent": percent, "note": note})
    return {"unit_code": unit_code, "rows": rows, "note": PROGRESS_PLAIN,
            "demo_note": DEMO_NOTE}


# ---------------------------------------------------------------------------
# 五、训练环节（全部基于真实教材内容；参考答案都可由教材内容核对）
# ---------------------------------------------------------------------------

def sentence_pool(sections, min_len: int = 28, max_len: int = 150) -> list:
    """从教材正文里取出可读的课文句子（只读派生，不改写教材文本一个字）。

    只用 block_kind == 'dialogue' 的正文块，排除题干 / 指令 / 页眉页脚，
    并过滤掉明显的碎片（例如以小写字母开头的残句）。
    """
    out = []
    for sec in sections or []:
        for block in sec.get("blocks") or []:
            if block.get("kind") != "dialogue":
                continue
            for piece in re.split(r"(?<=[.!?])\s+", block.get("text") or ""):
                text = piece.strip()
                if not (min_len <= len(text) <= max_len):
                    continue
                if len(text.split()) < 6:
                    continue
                if not (text[0].isupper() or text[0] in "\u201c\"'\u2018"):
                    continue
                out.append({"text": text, "section": sec.get("section_key") or ""})
    return out


def _mcq(correct: str, distractors, at: int = 0):
    """选择题：返回 (options, 正确选项字母)。

    正确答案的位置按题号轮换（不是永远 a），但完全由输入决定、可复现。
    """
    pool = [correct] + [d for d in distractors]
    pos = at % len(pool)
    pool.insert(pos, pool.pop(0))
    opts = [(chr(ord("a") + i), text) for i, text in enumerate(pool)]
    return opts, opts[pos][0]


def build_vocab_drill(words: list, limit: int = 4) -> list:
    """听音辨词：题目来自真实词表释义与官方逐词音频。

    words: [{"text","meaning","phonetic","pos","key","audio_url"}]
    参考答案可由教材词表核对（选择题的干扰项也都是同一课真实词条的释义）。
    """
    pool = [w for w in words if w.get("text") and w.get("meaning")]
    if len(pool) < 3:
        return []
    items = []
    for idx, word in enumerate(pool[:limit]):
        others = [w for w in pool if w["text"] != word["text"]]
        if idx % 2 == 0 or not word.get("audio_url"):
            # 意思选择：正确释义 + 同一课另外两个真实释义
            distractors = [w["meaning"] for w in others][:2]
            if len(distractors) < 2:
                continue
            opts, answer = _mcq(word["meaning"], distractors, idx)
            items.append({"no": len(items) + 1, "kind": "choice", "label": "看单词选意思",
                          "prompt": "%s 是什么意思？" % word["text"],
                          "phonetic": word.get("phonetic") or "",
                          "pos": word.get("pos") or "",
                          "options": opts, "answer": answer,
                          "why": "教材词表里 %s 的意思是“%s”。" % (word["text"], word["meaning"])})
        else:
            # 听音选词：正确答案就是这条官方逐词音频对应的词
            distractor_words = [w["text"] for w in others][:2]
            if len(distractor_words) < 2:
                continue
            opts, answer = _mcq(word["text"], distractor_words, idx)
            items.append({"no": len(items) + 1, "kind": "choice", "label": "听发音选单词",
                          "prompt": "听一听，选出你听到的单词。",
                          "audio": word.get("audio_url") or "",
                          "options": opts, "answer": answer,
                          "why": "这条发音就是教材词表里的 %s。" % word["text"]})
    return items


#: Unit 1 教材句子里出现的表达（真实教材原句，用于短语/阅读练习）
SENTENCE_EXPRESSIONS = (
    {"text": "make good use of", "uid": "P3-07:AU11-B05", "meaning": "好好利用"},
    {"text": "share some thoughts", "uid": "P3-07:AU13-DLG-08", "meaning": "分享一些想法"},
    {"text": "try your best", "uid": "P3-07:AU13-LTR-12", "meaning": "尽你最大的努力"},
)


def build_phrase_drill(phrases: list, sentences: list, expressions=SENTENCE_EXPRESSIONS,
                       meaning_pool=(), unit_code: str = "Unit 1") -> list:
    """短语练习：教材词表短语 + 教材原句里的表达。

    phrases:    [{"text","meaning"}]（真实词表短语）
    sentences:  [{"text","uid"}]（该单元真实教材句子）
    expressions: 教材原句里抽出的表达（答案来自原句本身）
    """
    items = []
    usable_phrases = [p for p in phrases if p.get("meaning")]
    meanings = [p["meaning"] for p in usable_phrases]
    fallback = [m for m in meaning_pool if m and m not in meanings]
    for idx, phrase in enumerate(usable_phrases[:2]):
        others = [m for m in meanings if m != phrase["meaning"]]
        others += [m for m in fallback if m != phrase["meaning"]]
        others = others[:2]
        if len(others) < 2:
            break
        opts, answer = _mcq(phrase["meaning"], others, idx + 1)
        items.append({"no": len(items) + 1, "kind": "choice", "label": "短语意思",
                      "prompt": "%s 是什么意思？" % phrase["text"],
                      "options": opts, "answer": answer,
                      "why": "教材词表里 %s 的意思是“%s”。" % (phrase["text"],
                                                        phrase["meaning"])})
    sent_by_uid = {s.get("uid"): s for s in sentences}
    usable = [e for e in expressions if sent_by_uid.get(e["uid"])]
    for expr in usable[:2]:
        sent = sent_by_uid[expr["uid"]]
        blanked = _blank_out(sent["text"], expr["text"])
        if not blanked:
            continue
        others = [e["text"] for e in usable if e["text"] != expr["text"]]
        if len(others) < 2:
            others = [e["text"] for e in expressions if e["text"] != expr["text"]]
        if len(others) < 2:
            continue
        opts, answer = _mcq(expr["text"], others[:2], len(items))
        items.append({"no": len(items) + 1, "kind": "choice", "label": "句子填空",
                      "prompt": "补全句子：%s" % blanked,
                      "options": opts, "answer": answer,
                      "why": "教材原句是：%s" % sent["text"]})
    items = items[:2]
    # 造句（书面表达）：答案用教材里的表达本身核对，不编造标准答案
    if usable and len(items) < 3:
        expr = usable[0]
        items.append({"no": len(items) + 1, "kind": "text", "label": "造句",
                      "prompt": "用 %s 写一句你自己的句子。" % expr["text"],
                      "placeholder": "用英语写一句",
                      "accepts": [expr["text"]],
                      "why": "教材里 %s 的意思是“%s”，先把句子写完整。" % (expr["text"],
                                                                  expr["meaning"])})
    return items[:3]


def _blank_out(sentence: str, expression: str):
    """把教材原句里的表达挖空（大小写不敏感定位，不改写原文其余部分）。"""
    low, low_expr = sentence.lower(), expression.lower()
    pos = low.find(low_expr)
    if pos < 0:
        return ""
    return sentence[:pos] + "______" + sentence[pos + len(expression):]


#: Unit 1 课文理解题（题干与答案都能由教材课文本身核对）
READING_COMPREHENSION = {
    "Unit 1": (
        {"prompt": "课文中，Dad 和 Mum 把小学（primary school）比作什么？",
         "options": ["一个小池塘", "一条大河", "大海"],
         "answer": "a",
         "why": "课文里写的是 Primary school is like a small pool."},
        {"prompt": "课文中说，初中（junior high）像什么？",
         "options": ["一条河", "一个小池塘", "一座山"],
         "answer": "a",
         "why": "课文里写的是 But junior high is like a river."},
        {"prompt": "信里的 Mia 明天要去哪里？",
         "options": ["上初中的第一天", "回到小学", "去公园"],
         "answer": "a",
         "why": "课文里问的是 your first day in junior high tomorrow。"},
    ),
}

#: 阅读练习的简短回答（同样可以由教材课文本身核对；答案在课文原句里）
READING_SHORT_ANSWER = {
    "Unit 1": {"prompt": "课文中把小学（primary school）比作什么？用英语写出来。",
               "placeholder": "用英语写一个词或短语",
               "accepts": ["pool"],
               "why": "课文里写的是 Primary school is like a small pool."},
}


def build_reading_drill(unit_code: str, unit_text: str, sentences: list,
                        other_sentences: list, limit: int = 3) -> list:
    """阅读练习：全部落在这一课的真实教材文本上。

    * 内容理解题：题干与答案都能由教材课文核对（只对已人工整理的课文使用）；
    * 定位题：哪一句真的出现在这一课的课文里（干扰项取自其它单元的教材句子，
      并逐条确认它们确实不在本课课文里）。
    """
    # 课文理解题改由固定入库的题库提供（demo_content.READING_EXTRA，教材原句核对），
    # 这里只保留数据驱动的「回到课文里找」与「简短回答」两类。
    items = []
    pool = [s for s in sentences if s.get("text") and len(s["text"]) > 18]
    others = [s["text"] for s in other_sentences
              if s.get("text") and len(s["text"]) > 18
              and s["text"].lower() not in (unit_text or "").lower()]
    if pool and len(others) >= 2:
        for s in pool:
            if len(items) >= limit:
                break
            if s["text"].lower() not in (unit_text or "").lower():
                continue
            opts, answer = _mcq(s["text"], others[:2], len(items))
            items.append({"no": len(items) + 1, "kind": "choice", "label": "回到课文里找",
                          "prompt": "下面哪一句真的出现在这一课的课文里？",
                          "options": opts, "answer": answer,
                          "why": "这一句就是这一课课文里的原句。"})
            break
    items = items[:limit]
    short = READING_SHORT_ANSWER.get(unit_code)
    if short:
        items.append({"no": len(items) + 1, "kind": "text", "label": "简短回答",
                      "prompt": short["prompt"], "placeholder": short["placeholder"],
                      "accepts": short["accepts"], "why": short["why"]})
    return items


def build_listening_drill(sentences: list, limit: int = 2) -> list:
    """听力练习：只用已人工核验的句子级音频；答案就是那段音频对应的教材原句。"""
    pool = [s for s in sentences if s.get("text") and s.get("start_ms") is not None]
    if len(pool) < 3:
        return []
    items = []
    for idx, s in enumerate(pool[:limit]):
        others = [x["text"] for x in pool if x["text"] != s["text"]][:2]
        if len(others) < 2:
            break
        opts, answer = _mcq(s["text"], others, idx)
        items.append({"no": len(items) + 1, "kind": "choice", "label": "听句子选内容",
                      "prompt": "点上面的播放，选出你听到的那一句。",
                      "audio": "/audio/official/%s.mp3" % s["audio_code"],
                      "audio_start": s["start_ms"], "audio_end": s["end_ms"],
                      "options": opts, "answer": answer,
                      "why": "这一段音频就是教材原句：%s" % s["text"]})
    return items


# ---------------------------------------------------------------------------
# 单元中心（学情分析页）二期：聚合 + 程度词现算
# ---------------------------------------------------------------------------

def _day_of(ts) -> str:
    """ISO 时间戳 → 日期（用于 minimum_natural_days 判定）。"""
    return (str(ts or "")[:10]) or ""


def level_word_display(practiced, correct) -> str:
    """**显示层程度词（四档）**：只看练习量与答对率。

    * 0 题 → 「还没练」
    * 1–4 题 → 「还在练」
    * ≥5 题且答对率 ≥70% → 「练得不错」
    * ≥5 题且答对率 <70% → 「还要多练」

    与 `mastery_level_word()` **完全解耦**：后者照 `mastery_rules_v1.json → stable.*`
    做**内部判定**（例如"是否需复习"），**不直接决定孩子看到的词**。
    """
    n = int(practiced or 0)
    if n <= 0:
        return LEVEL_NOT_PRACTICED
    if n <= DISPLAY_PRACTICING_MAX:
        return LEVEL_PRACTICING
    acc = int(round(100.0 * int(correct or 0) / n))
    return LEVEL_GOOD if acc >= DISPLAY_GOOD_MIN_ACCURACY else LEVEL_NEED_MORE


def order_practice_entries(entries, points):
    """④ 按钮排序：**按知识点答对率升序**（最需要补的排前面）。

    * `points`：`unit_center_data()` 产出的知识点列表（含 `name`/`practiced`/`correct`）；
    * `entries`：候选入口（含 `label`/`entry`/`mode`）；
    * 匹配规则：入口的 `label` 命中知识点 `name` ⇒ 该入口的"答对率"就取那个知识点的；
      **练过 ≥1 题才参与排序**；没匹配到的入口排在后面（保持原顺序）；
    * **都不足时**（没有任何入口匹配到练过的知识点）⇒ 原样返回 `entries[:2]`（退回固定顺序）。
    """
    acc = {}
    for p in points or []:
        name = p.get("name") or ""
        if int(p.get("practiced") or 0) >= 1 and name:
            n = int(p.get("practiced") or 0)
            acc[name] = int(round(100.0 * int(p.get("correct") or 0) / n))
    if not acc:
        return list(entries or [])[:2]

    def entry_accuracy(e):
        """该入口"最需要补"的程度：取它覆盖的知识点里**答对率最低**的那个。

        先按 `ENTRY_POINT_LABELS` 的**显式映射**取覆盖集合；取不到就退回**同名匹配**
        （兼容以后新加入口）。返回 None 表示该入口没有任何练过的知识点可比 ⇒ 不参与排序。
        """
        covers = ENTRY_POINT_LABELS.get((e.get("entry") or "", e.get("mode") or ""))
        if covers is None:
            covers = ((e.get("label") or ""),)
        rates = [acc[n] for n in covers if n in acc]
        return min(rates) if rates else None

    entries = list(entries or [])
    indexed = list(enumerate(entries))
    ranked = []                                        # [(答对率, 原顺序, 入口)]
    for idx, e in indexed:
        a = entry_accuracy(e)
        if a is not None:
            ranked.append((a, idx, e))
    if not ranked:
        ranked = [(None, idx, e) for idx, e in indexed]

    def is_specialist(e):
        return (e.get("entry") or "") in SPECIALIST_ENTRIES

    def is_comprehensive(e):
        return (e.get("entry") or "") in COMPREHENSIVE_ENTRIES

    def low_first(items):
        """按 (答对率升序, 原顺序) 排；答对率为 None（无数据可比）的排后面。"""
        return sorted(items, key=lambda x: (x[0] is None, x[0] if x[0] is not None else 0, x[1]))

    # **分槽**（二期·B）：
    #   补一补 = 专项入口里答对率最低的；专项都不足时**退回综合入口**；
    #   练一练 = 从剩余入口里取（**可含综合入口**）。
    spec = low_first([x for x in ranked if is_specialist(x[2])])
    comp = low_first([x for x in ranked if not is_specialist(x[2])])
    picked = []
    if spec:
        picked.append(spec.pop(0)[2])
    if not picked and comp:                            # 专项都不足 ⇒ 退回综合
        picked.append(comp.pop(0)[2])
    rest = low_first(spec + comp)
    while rest and len(picked) < 2:
        picked.append(rest.pop(0)[2])
    if len(picked) < 2:                                # 仍不足：按原顺序补齐
        # 注意：`indexed` 是 `enumerate()` 产出的 **(下标, 入口) 二元组**，
        # 不能按三元解包（实测踩过 `ValueError: not enough values to unpack`）。
        for _idx, e in indexed:
            if e not in picked:
                picked.append(e)
            if len(picked) >= 2:
                break
    return picked[:2]


def analyze_payload(ctx: dict) -> dict:
    """**AI 学情分析的输入 JSON**（单元中心二期·C-1，键名与规格完全一致）。

    规格要点（只喂孩子能理解的维度，**不喂内部 key**）：
      * `unit_name` / `unit_code`：教材原名；
      * `total_questions_practiced` / `total_questions_correct`：整单元计数；
      * `knowledge_points[]`：**只含练过的**，用中文名 + `practiced`/`correct`/`accuracy`；
      * `learned_sections[]` / `unlearned_sections[]`：教材原名；
      * `practice_entries[]`：孩子能点进去的入口（**AI 只能从这里挑建议**）。
    **门槛**：`total_questions_practiced < ANALYZE_MIN_PRACTICED` 时由调用方不下发。
    """
    return {
        "unit_name": ctx.get("unit_name") or "",
        "unit_code": ctx.get("unit_code") or "",
        "total_questions_practiced": int(ctx.get("total_practiced") or 0),
        "total_questions_correct": int(ctx.get("total_correct") or 0),
        "knowledge_points": [
            {"name": p.get("name") or "",
             "category": p.get("category") or CATEGORY_COMPREHEND,
             "practiced": int(p.get("practiced") or 0),
             "correct": int(p.get("correct") or 0),
             "accuracy": int(p.get("accuracy") or 0)}
            for p in (ctx.get("points") or [])],
        # D-1：错题明细（只含理解类，≤5 条）；每条**只允许 MISTAKE_FIELDS 里的键**
        "mistakes": [{k: m.get(k) for k in MISTAKE_FIELDS}
                     for m in (ctx.get("mistakes") or [])],
        "learned_sections": list(ctx.get("learned_sections") or []),
        "unlearned_sections": list(ctx.get("unlearned_sections") or []),
        "practice_entries": [
            {"label": e.get("label") or "", "entry": e.get("entry") or "",
             "mode": e.get("mode") or ""}
            for e in (ctx.get("practice_entries") or [])],
    }


def mastery_level_word(practiced, correct, days, task_types, recent_results) -> str:
    """**程度词现算**（照 `mastery_rules_v1.json → stable.*`，不读 mastery_level）。

    * `practiced`：该知识点的证据条数（去重后）；
    * `correct`：其中 `result='correct'` 的条数；
    * `days`：这些证据覆盖的**不同自然日**数；
    * `task_types`：这些证据覆盖的**不同活动类型**数；
    * `recent_results`：最近的作答结果（新的在前）。

    达到全部门槛 → 「比较熟了」；有证据但不达 → 「还不太熟」；无证据 → 「还没练过」。
    """
    if int(practiced or 0) <= 0:
        return LEVEL_NOT_PRACTICED
    recent = list(recent_results or [])[:MASTERY_RECENT_WINDOW]
    recent_ok = len([r for r in recent if r == "correct"])
    stable = (int(practiced) >= MASTERY_MIN_EVIDENCE
              and int(task_types or 0) >= MASTERY_MIN_TASK_TYPES
              and int(days or 0) >= MASTERY_MIN_NATURAL_DAYS
              and recent_ok >= MASTERY_RECENT_CORRECT)
    return LEVEL_FAMILIAR if stable else LEVEL_LEARNING


def unit_center_data(unit_code, unit_title, unit_slug, sections_all,
                     learner_id, learning_db, questionbank_path=None,
                     questionbank_conn=None) -> dict:
    """单元中心二期聚合（**只读**）：顶部一句话 + 知识点程度 + 练习入口 + AI 门槛。

    * 题目 → 证据的映射在**题库侧**完成（`question.source_item_id` 才是
      `learning_record.item_id` 的语义）；证据只在**学习库内**按 item_id 查。
    * **只统计"可产生证据"的题**（`source_item_id` 非空）—— 没有它永远练不出来。
    * `question_points` 只返回**练过的**；未练过的单独放 `not_practiced`（页面折叠区）。
    """
    import sqlite3 as _sq

    qrows = []
    try:
        own = questionbank_conn is None
        qc = questionbank_conn or _sq.connect(
            "file:%s?mode=ro" % str(questionbank_path).replace("\\", "/"), uri=True)
        try:
            cols = ("question_id", "question_type", "section_key", "source_item_id",
                    "prompt_json", "options_json", "answer_json", "answer_kind")
            qrows = [dict(zip(cols, r)) for r in qc.execute(
                "SELECT question_id, question_type, section_key, source_item_id, "
                "prompt_json, options_json, answer_json, answer_kind "
                "FROM question WHERE unit_code=?", (unit_code,))]
        finally:
            if own:
                qc.close()
    except Exception as exc:                           # noqa: BLE001
        print("[demo] 单元中心题库读取失败：%r" % (exc,))

    # 证据：一次读完该 learner 的全部 (item_id, result, created_at, activity_type)
    ev = {}
    order = []
    if learner_id:
        try:
            lc = scs.connect_learning_db_ro(learning_db)
            try:
                # D-1：同时取 `response_raw`，解析出**孩子填的答案**（`picked`），
                # 供错题明细使用；`ev` 的值为 4 元组 `(result, created_at, activity_type, picked)`
                # —— 只取前三项的调用方（`stat()` / `_evidence_progress`）不受影响。
                for iid, res, ts, act, raw_resp in lc.execute(
                        "SELECT item_id, result, created_at, activity_type, response_raw "
                        "FROM learning_record WHERE learner_id=? ORDER BY created_at", (learner_id,)):
                    if not iid:
                        continue
                    picked = None
                    if raw_resp:
                        try:
                            _d = _json.loads(raw_resp)
                            if isinstance(_d, dict):
                                picked = _d.get("picked")
                        except Exception:              # noqa: BLE001 —— 解析不了就当没有
                            picked = None
                    ev.setdefault(iid, []).append((res or "", ts, act or "", picked))
                    order.append(iid)
            finally:
                lc.close()
        except Exception as exc:                       # noqa: BLE001
            print("[demo] 单元中心学习库读取失败：%r" % (exc,))

    # 按题型聚合（只算可产生证据的题）
    by_type = {}
    for r in qrows:
        iid = r.get("source_item_id")
        if not iid:
            continue
        by_type.setdefault(r.get("question_type") or "", set()).add((r["question_id"], iid))

    points, not_practiced = [], []
    total_practiced = total_correct = 0
    for qtype, pairs in by_type.items():
        label = QUESTION_TYPE_LABELS.get(qtype) or qtype
        seen, ok, days, acts, recent = 0, 0, set(), set(), []
        for _qid, iid in sorted(pairs):
            recs = ev.get(iid)
            if not recs:
                continue
            seen += 1
            results = [x[0] for x in recs]
            if "correct" in results:
                ok += 1
            for _rec in recs:
                # 兼容 3 元组（旧）与 4 元组（D-1 起带 `picked`）
                days.add(_day_of(_rec[1] if len(_rec) > 1 else ""))
                acts.add(_rec[2] if len(_rec) > 2 else "")
            recent.extend(reversed(results))
        if seen <= 0:
            not_practiced.append({"name": label})
            continue
        total_practiced += seen
        total_correct += ok
        # `level` = **显示层**（练习量 + 答对率）；`needs_review` = **内部判定**（严门槛）
        points.append({"name": label, "practiced": seen, "correct": ok,
                       "accuracy": int(round(100.0 * ok / seen)),
                       "level": level_word_display(seen, ok),
                       "category": QUESTION_TYPE_CATEGORY.get(qtype, CATEGORY_COMPREHEND),
                       "types": [qtype],       # 内部题型 key（合并时累加；**不下发给 AI**）
                       "needs_review": mastery_level_word(
                           seen, ok, len(days), len(acts), recent) != LEVEL_GOOD})
    # 二期·B：**按中文名合并同名知识点**（例如 `vocab_phonetic_write` 与
    # `phonetics_symbol_write` 都叫"音标写词"⇒ 合并成一行）：
    #   练题数 / 答对数**相加**；程度词取**更弱**的那档（对合并后的口径重新现算）。
    merged = {}
    for p in points:
        cur = merged.get(p["name"])
        if cur is None:
            merged[p["name"]] = dict(p)
        else:
            cur["practiced"] += p["practiced"]
            cur["correct"] += p["correct"]
            cur["types"] = list(dict.fromkeys((cur.get("types") or []) + (p.get("types") or [])))
            if p.get("category") == CATEGORY_COMPREHEND:
                cur["category"] = CATEGORY_COMPREHEND   # 合并后含理解类 ⇒ 整条按理解（好给具体意见）
            if LEVEL_WEAKER_ORDER.index(p["level"]) < LEVEL_WEAKER_ORDER.index(cur["level"]):
                cur["level"] = p["level"]
            cur["needs_review"] = cur["needs_review"] or p["needs_review"]
    for name, cur in merged.items():
        seen, ok = cur["practiced"], cur["correct"]
        cur["accuracy"] = int(round(100.0 * ok / seen)) if seen else 0
        # 合并后按**总量**重算显示档位（更符合"这一类整体练得怎么样"）
        cur["level"] = level_word_display(seen, ok)
    points = list(merged.values())
    # 页面顺序：**答对率低的排前面**（最需要补的先看到）；并列时按练习量降序、再按名字。
    points.sort(key=lambda x: (x["accuracy"], -x["practiced"], x["name"]))
    not_practiced = sorted({p["name"] for p in not_practiced} - set(merged))

    # 已学 / 未学课时（教材原名；"已学" = 该 Section 有证据）
    learned, unlearned = [], []
    for s in sections_all or []:
        key, title = s.get("section_key") or "", s.get("title") or s.get("section_key") or ""
        has = any(ev.get(iid) for q, iid in
                  [(r["question_id"], r.get("source_item_id")) for r in qrows
                   if (r.get("section_key") or "") == key and r.get("source_item_id")])
        (learned if has else unlearned).append(title)

    mistakes = _mistake_detail(unit_code, ev, qrows)
    return {"unit_code": unit_code, "unit_name": unit_title, "unit_slug": unit_slug,
            "total_practiced": total_practiced, "total_correct": total_correct,
            "points": points, "not_practiced": not_practiced,
            "mistakes": mistakes,
            "learned_sections": learned, "unlearned_sections": unlearned,
            "ready_for_ai": total_practiced >= ANALYZE_MIN_PRACTICED,
            "min_practiced": ANALYZE_MIN_PRACTICED}


def _mistake_detail(unit_code, ev, qrows, limit=None):
    """**错题明细聚合（D-1，只读）**：还原"孩子答错的**理解类**题"的作答事实。

    为什么不复用现成函数：`flow.need_relearn()` 只到**词条级**（无题干 / 无孩子答案 /
    无正确答案），`app._wrong_pool()` 是 Demo 用的 Cookie 池 —— 都不做"按题还原作答"。

    * `ev`：`{item_id: [(result, created_at, activity_type, picked), ...]}`（调用方一次读完）；
    * **只取理解类**（照 `QUESTION_TYPE_CATEGORY`）、`result IN ('incorrect','partial')`；
    * **对不上题的记录直接跳过**（不猜、不伪造，只计入总量）；
    * 每条带：中文题型 `point` / `category` / 所在课时 `where`（`section_key` 为空则用
      `unit_code` 兜底）/ 题干 `prompt`（白名单字段）/ 孩子答案 `picked` / 正确答案 `answer`；
    * 排序：**同一知识点重复错优先**，其次**最近优先**；最多 `limit`（默认 `MISTAKE_MAX`）条。
    """
    limit = MISTAKE_MAX if limit is None else int(limit)
    rows = []
    for r in qrows:
        iid = r.get("source_item_id")
        qid = r.get("question_id")
        if not iid or not qid:
            continue                                    # 对不上题：跳过（不进明细）
        qtype = r.get("question_type") or ""
        if QUESTION_TYPE_CATEGORY.get(qtype, CATEGORY_COMPREHEND) != CATEGORY_COMPREHEND:
            continue                                    # 背诵类：只给统计，不进明细
        recs = ev.get(iid) or []
        bad = [x for x in recs if len(x) > 0 and x[0] in ("incorrect", "partial")]
        if not bad:
            continue
        bad.sort(key=lambda x: str(x[1] if len(x) > 1 else ""), reverse=True)   # 最近优先
        picked = next((x[3] for x in bad if len(x) > 3 and x[3] not in (None, "")), None)
        prompt = {}
        try:
            raw_p = _json.loads(r.get("prompt_json") or "{}")
            if isinstance(raw_p, dict):
                prompt = {k: raw_p[k] for k in MISTAKE_PROMPT_FIELDS
                          if raw_p.get(k) is not None}
        except Exception:                               # noqa: BLE001
            prompt = {}
        answer = None
        try:
            a = _json.loads(r.get("answer_json") or "null")
            if isinstance(a, dict):
                answer = a.get("text") or a.get("key")
            elif a is not None:
                answer = a
        except Exception:                               # noqa: BLE001
            answer = None
        where = (r.get("section_key") or "").strip() or (unit_code or "").strip()
        rows.append({"point": QUESTION_TYPE_LABELS.get(qtype) or qtype,
                     "category": CATEGORY_COMPREHEND,
                     "where": where,
                     "prompt": prompt,
                     "picked": picked,
                     "answer": answer,
                     "_repeat": len(bad),
                     "_ts": str(bad[0][1] if len(bad[0]) > 1 else "")})
    # 排序：重复错次数降序 → 时间降序（最近）→ 题型名
    # **讲不透的条目不进明细**：`picked` 与 `answer` 同时为空 ⇒ AI 拿到也说不具体
    # （实测 `textbook_native`/`ai_eval` 就是这种：无 `answer_json`，作答走 `answers` 结构）。
    # 它们仍计入总量统计，只是不占明细名额。
    rows = [w for w in rows if w.get("picked") not in (None, "") or w.get("answer") not in (None, "")]
    rows.sort(key=lambda x: (-int(x["_repeat"]), x["_ts"], x["point"]), reverse=True)
    out = []
    for w in rows[:limit]:
        item = {k: w.get(k) for k in MISTAKE_FIELDS}
        item["wrong_times"] = int(w.get("_repeat") or 1)   # 公开的"错了多少次"
        out.append(item)
    return out

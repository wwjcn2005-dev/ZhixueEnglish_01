#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-12-C3-C3 正式 Web UI —— Vocabulary 学习闭环编排层

本模块只做**编排**，不复制任何业务规则：

    Vocabulary 资源
      → vocabulary_service（CORE 门禁 + Session/Task/TaskItem 创建 + 行为记录）
      → session_service（Session 生命周期、归属校验）
      → behavior_service（study / practice 行为协议）
      → learning_service（LearningRecord / Mastery，唯一写入口）
      → resource_pool_service（当前错误 / 当前薄弱，只读）

边界：
  - 不新增 activity_type（继续使用 study / practice）；
  - 不新增任何表 / 字段（learning.db schema 不变）；
  - 不自行写 learning_record、不自行计算 attempt_no / Mastery / 池状态；
  - 不调用 AI、不联网、不做音频播放与语音合成。
"""

from __future__ import annotations

import os

import sys
import hashlib
from pathlib import Path

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
sys.path.insert(0, str(BASE / "learning"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True

import content as content_mod          # noqa: E402
import diagnosis_service as diag       # noqa: E402  （P2-6-B：只读诊断）
import intervention_service as interv  # noqa: E402  （P2-6-B：教材优先建议）
import learning_service as svc         # noqa: E402
import learning_object_service as lo_svc  # noqa: E402  （P2-6-D-1：LO 只读派生）
import logging                          # noqa: E402
import resource_pool_service as pool   # noqa: E402
import session_service as ses          # noqa: E402
import vocabulary_service as voc       # noqa: E402

#: 三个自评选项（孩子语言 → 冻结的 practice 结果语义）；顺序即展示顺序
CHOICES = (("remember", "我记得", "correct"),
           ("fuzzy", "有点模糊", "partial"),
           ("forgot", "忘了", "incorrect"))
CHOICE_RESULTS = {key: result for key, _, result in CHOICES}
RESULT_LABELS = {result: label for _, label, result in CHOICES}

#: P1-13-C1：列表用学习状态（内部键 → 孩子看到的文字）。
#: 状态是"信息"，不是"评价"：不含掌握 / 分数 / 等级语义。
STATUS_LABELS = {"error": "上次忘了", "weak": "上次有点模糊",
                 "studied": "已学", "unseen": "未学"}

#: P2-1-C1（C1-01 / C1-04）：
#:   * 教材黑体本身就是"重点"标记 —— 白体词只以普通字重显示，不再加解释性标签；
#:   * 暂时没有学习入口的内容也不显示任何内部数据治理语言
#:     （"教材确认""审核""NEED_REVIEW"一律不出现在孩子端）。
#: 因此本模块不再向页面提供"不可学习原因"文案。


def learner_exists(learner_id, learning_db=content_mod.LEARNING_DB) -> bool:
    """只读确认 Cookie 里的学习者是否真实存在（不存在则不猜测、不创建）。"""
    if not learner_id:
        return False
    conn = pool.connect_learning_db(learning_db)          # 该模块内部即 mode=ro
    try:
        return conn.execute("SELECT 1 FROM learner WHERE learner_id=? AND status='active'",
                            (learner_id,)).fetchone() is not None
    finally:
        conn.close()


def item_status_map(learner_id, item_ids, learning_db=content_mod.LEARNING_DB,
                    contentpack_path=content_mod.CONTENTPACK) -> dict:
    """列表用学习状态（**只读**）：一次池查询 + 一次 mastery 批量查询。

    优先级（严格按 P1-13-C1 §五）：
        current_error → current_weak → mastery 学习证据 → 未学
    返回值：{item_id: "error" | "weak" | "studied" | "unseen"}

    边界：不调用任何写入函数（不产生 LearningRecord / Session / Task），
          不修改 mastery_state 与资源池，不调用 AI。
    """
    ids = [i for i in dict.fromkeys(item_ids or []) if i]
    out = {i: "unseen" for i in ids}
    if not learner_id or not ids:
        return out
    conn = pool.connect_learning_db(learning_db)
    try:
        for item in pool.list_current_issue_pool(conn, learner_id,
                                                 contentpack_path=contentpack_path):
            if item["item_id"] in out:
                out[item["item_id"]] = ("error" if item["issue_type"] == pool.CURRENT_ERROR
                                        else "weak")
        marks = ",".join("?" * len(ids))
        rows = conn.execute(
            "SELECT item_id FROM mastery_state WHERE learner_id=? AND evidence_count > 0 "
            "AND item_id IN (%s)" % marks, [learner_id] + ids)
        for row in rows:
            if out.get(row["item_id"]) == "unseen":
                out[row["item_id"]] = "studied"
    finally:
        conn.close()
    return out


def status_label(status) -> str:
    return STATUS_LABELS.get(status or "", "")


#: 首页「最近学过」最多展示条数（P1-13-C3-G1；只陈述事实，不做任何评价）
RECENT_LIMIT = 5


def recent_studied(learner_id, learning_db=content_mod.LEARNING_DB,
                   contentpack_path=content_mod.CONTENTPACK, limit=RECENT_LIMIT) -> list:
    """首页「最近学过」：只读读取该学习者最近学习过的 Vocabulary。

    数据来源（全部为已有数据）：
      - `mastery_state.last_practiced_at`：由冻结服务在真实学习结果产生时维护；
      - contentpack 的真实教材文本（单词 / 音标 / 词性 / 中文释义）。
    排序：`last_practiced_at DESC`（在 SQL 层完成并 LIMIT，最多 5 条；同刻按 item_id 稳定）。

    边界：不写库、不创建 learner/记录、不猜测学习者为他人、不调用 AI。
    """
    if not learner_id:
        return []
    conn = pool.connect_learning_db(learning_db)          # 该模块内部即 mode=ro
    try:
        rows = conn.execute(
            "SELECT item_id, last_practiced_at FROM mastery_state "
            "WHERE learner_id=? AND evidence_count > 0 AND last_practiced_at IS NOT NULL "
            "ORDER BY last_practiced_at DESC, item_id ASC LIMIT ?",
            (learner_id, int(limit))).fetchall()
    finally:
        conn.close()
    if not rows:
        return []
    cp = content_mod._ro(contentpack_path)
    try:
        out = []
        for row in rows:
            item = cp.execute(
                "SELECT canonical_text, phonetic, part_of_speech, meaning_zh FROM learning_item "
                "WHERE item_id=? AND item_type='vocabulary'", (row["item_id"],)).fetchone()
            if item is None:
                continue                      # 非 Vocabulary / 不在当前教材 → 不展示，不臆测
            out.append({"item_id": row["item_id"], "key": item_key(row["item_id"]),
                        "word": item["canonical_text"],
                        "phonetic": item["phonetic"] or None,
                        "part_of_speech": item["part_of_speech"] or None,
                        "meaning": item["meaning_zh"] or None,
                        "last_practiced_at": row["last_practiced_at"]})
    finally:
        cp.close()
    return out


def item_key(item_id: str) -> str:
    """面向页面的公开短键（由 item_id 派生）。

    页面上只出现这个短键，**不出现任何数据库内部 ID**（P1-12-C3-C3 §十八/§三十五）。
    """
    return hashlib.sha256((item_id or "").encode("utf-8")).hexdigest()[:12]


def find_item_by_key(key: str, contentpack_path=content_mod.CONTENTPACK):
    """按公开短键找回真实的 vocabulary item_id（找不到返回 None）。"""
    key = (key or "").strip().lower()
    if not key:
        return None
    cp = content_mod._ro(contentpack_path)
    try:
        rows = [r["item_id"] for r in cp.execute(
            "SELECT item_id FROM learning_item WHERE item_type='vocabulary' ORDER BY item_id")]
    finally:
        cp.close()
    for item_id in rows:
        if item_key(item_id) == key:
            return item_id
    return None


def resolve_learner(conn, name):
    """按名字复用既有 Learner；没有则创建（沿用项目当前最小身份机制）。"""
    name = (name or "").strip()
    if not name:
        raise svc.ValidationError("请填写你的名字")
    row = conn.execute(
        "SELECT learner_id FROM learner WHERE display_name=? AND status='active' "
        "ORDER BY created_at LIMIT 1", (name,)).fetchone()
    if row:
        return row["learner_id"]
    return svc.create_learner(conn, name)["learner_id"]


def learner_name(conn, learner_id):
    return svc.get_learner(conn, learner_id)["display_name"]


def vocabulary_view(item_id, contentpack_path=content_mod.CONTENTPACK) -> dict:
    """学习页面需要的真实词汇数据（CORE 门禁由 require_core_vocabulary 保证）。

    返回：单词 / 音标 / 词性 / 释义 / 教材出处（单元 + 栏目 + 印刷页）。
    """
    vocab = voc.require_core_vocabulary(item_id, contentpack_path)   # 非 CORE 直接拒绝
    refs = vocab.get("source_refs") or []
    main = refs[0] if refs else {}
    unit = content_mod.unit_of_item(item_id, contentpack_path)
    # C4-06：把"出自哪个单元"与"词表栏目 + 词表页"拆成两个语义明确的值
    unit_label = None
    if unit:
        unit_label = " · ".join(x for x in (unit.get("unit_code"), unit.get("title")) if x)
    list_label = None
    if main.get("emphasis_source_list"):
        list_label = main["emphasis_source_list"]
        if main.get("textbook_page"):
            list_label = "%s · 第 %s 页" % (list_label, main["textbook_page"])
    return {
        "item_id": vocab["item_id"],
        "word": vocab["canonical_text"],
        "phonetic": vocab.get("phonetic") or None,
        "part_of_speech": vocab.get("part_of_speech") or None,
        "meaning": vocab.get("meaning_zh") or None,
        "source_unit_label": unit_label,          # 出自：单元（真实教材单元数据）
        "source_list_label": list_label,          # 词表：栏目 · 词表页（真实 source_ref 数据）
        "source_text": " · ".join(p for p in (unit_label, list_label) if p) or None,
        "unit": unit,
    }


def start_study(conn, learner_id, item_id, contentpack_path=content_mod.CONTENTPACK) -> dict:
    """开始一次 Vocabulary 学习（entry_point=vocabulary，复用冻结链路）。"""
    return voc.start_vocabulary_study(conn, learner_id, item_id, entry_point="vocabulary",
                                      contentpack_path=contentpack_path)


def session_of(conn, session_id, learner_id=None) -> dict:
    return ses.get_learning_session(conn, session_id, learner_id)


def record_study(conn, session_id, item_id, learner_id,
                 contentpack_path=content_mod.CONTENTPACK) -> dict:
    """「我看完了」→ study / done（委托冻结服务）。"""
    return voc.record_vocabulary_study(conn, session_id, item_id, learner_id=learner_id,
                                       result="done", contentpack_path=contentpack_path)


def record_choice(conn, session_id, item_id, learner_id, choice,
                  contentpack_path=content_mod.CONTENTPACK) -> dict:
    """三选一 → 恰好一条 practice 记录（映射在 CHOICES 中定义，不新增 activity_type）。"""
    if choice not in CHOICE_RESULTS:
        raise svc.ValidationError("请选择「我记得 / 有点模糊 / 忘了」中的一个")
    return voc.record_vocabulary_practice(conn, session_id, item_id,
                                          result=CHOICE_RESULTS[choice],
                                          learner_id=learner_id,
                                          contentpack_path=contentpack_path)


def end_session(conn, session_id, learner_id) -> dict:
    return ses.end_learning_session(conn, session_id, learner_id)


def latest_practice_result(conn, task_id, item_id):
    """重复提交时只读回放：取该 Task 下这条资源最近一次 practice 结果（不写库）。"""
    row = conn.execute(
        "SELECT result FROM learning_record WHERE task_id=? AND item_id=? "
        "AND activity_type='practice' ORDER BY created_at DESC, record_id DESC LIMIT 1",
        (task_id, item_id)).fetchone()
    return row["result"] if row else None


def need_relearn(conn, learner_id, contentpack_path=content_mod.CONTENTPACK) -> dict:
    """「需要再学」：只读复用 resource_pool_service，不自行判断池状态。

    分组沿用冻结池语义：current_error → 上次忘了；current_weak → 上次有点模糊。
    """
    items = pool.list_current_issue_pool(conn, learner_id, contentpack_path=contentpack_path)
    groups = {"forgot": [], "fuzzy": []}
    others = 0
    for item in items:
        if item.get("resource_type") != "vocabulary":
            others += 1
            continue
        info = {"item_id": item["item_id"], "text": item.get("knowledge_name"),
                "meaning": None, "phonetic": None, "part_of_speech": None}
        try:
            detail = voc.get_vocabulary(item["item_id"], contentpack_path)
            info.update({"text": detail["canonical_text"],
                         "phonetic": detail.get("phonetic") or None,
                         "part_of_speech": detail.get("part_of_speech") or None,
                         "meaning": detail.get("meaning_zh") or None})
        except svc.LearningServiceError:
            pass                       # 资源不在当前 contentpack：保留真实文本，不臆造
        key = "forgot" if item.get("issue_type") == pool.CURRENT_ERROR else "fuzzy"
        info["key"] = item_key(item["item_id"])
        groups[key].append(info)
    return {"groups": groups,
            "forgot_count": len(groups["forgot"]),
            "fuzzy_count": len(groups["fuzzy"]),
            "other_type_count": others}


def textbook_review_suggestions(conn, learner_id,
                                contentpack_path=content_mod.CONTENTPACK) -> list:
    """P2-6-B6：教材优先巩固建议（只读，只给建议，孩子点击才进入）。

    复用 P2-6-B5 intervention_service：建议顺序严格按 V1.2（回看教材 → 重听音频 →
    语法提示 → 范文 → 重做原题 → 跨板块练习）；不自动跳转、不自动播放、不调用 AI。
    """
    out = []
    try:
        for s in interv.suggest_for_learner(conn, learner_id,
                                            contentpack_path=contentpack_path):
            items = [{"label": x["label"], "link": x.get("link"), "type": x["type"],
                      "anchor_text": _anchor_text(x.get("anchor") or {})}
                     for x in s["suggestions"]]
            if not items:
                continue
            out.append({"item_id": s["item_id"], "reason": s.get("reason"),
                        "text": s.get("display_text"),
                        "unit": s.get("unit"),
                        "requires_resource_mapping": s.get("requires_resource_mapping"),
                        "missing": s.get("missing") or [],
                        "suggestions": items})
    except Exception:
        return []                      # 建议失败不影响页面（只读增强，不阻塞）
    return out


def _anchor_text(anchor: dict) -> str:
    """把教材定位渲染成孩子能读的一行；缺字段时如实省略，不伪造。"""
    if anchor.get("anchor"):
        return str(anchor["anchor"])
    bits = []
    if anchor.get("unit"):
        bits.append(str(anchor["unit"]))
    if anchor.get("section"):
        bits.append(str(anchor["section"]))
    if anchor.get("textbook_page"):
        bits.append("第 %s 页" % anchor["textbook_page"])
    if anchor.get("audio_id"):
        bits.append("官方录音 %s" % str(anchor["audio_id"]).split(":")[-1])
    if anchor.get("word_audio_url"):
        bits.append("单词发音")
    if anchor.get("topic"):
        bits.append("语法提示：%s" % anchor["topic"])
    return " · ".join(bits)


def lo_review_section(conn, learner_id, contentpack_path=content_mod.CONTENTPACK) -> dict:
    """P2-6-D-2：`/review` 的「教材学习建议」数据（只读，字段最小化）。

    调用 D-1 冻结接口 `learning_object_service.needs_attention()`，**不复制其规则**
    （LO 映射 / Evidence 去重 / Mastery / Diagnosis / Suggestion 全部由 D-1 计算）。

    边界：只读（无写库）、不改学习状态、不调用 AI、无自动行为。
    异常降级：D-1 抛错时返回 `available=False` + 空列表，不影响 /review 其余内容，
    并以项目现有 logging 风格记录一条 warning（便于诊断，不吞异常语义）。
    """
    try:
        raw = lo_svc.needs_attention(conn, learner_id, contentpack_path)
    except Exception as exc:                       # noqa: BLE001 —— 最小保护，不扩大影响面
        logging.getLogger("zhixue.web").warning("LO review section 降级：%r", exc)
        return {"available": False, "items": [], "reason": "lo_service_unavailable"}

    items = []
    for entry in raw:
        diag_info = entry.get("diagnosis") or {}
        master = entry.get("mastery") or {}
        sug = entry.get("suggestion") or {}
        tips = []
        for s in sug.get("suggestions") or []:
            tips.append({"label": s.get("label"),
                         "anchor_text": _anchor_text(s.get("anchor") or {}),
                         "link": s.get("link"),
                         "type": s.get("type")})
        items.append({
            "learning_object_id": entry.get("learning_object_id"),
            "object_type": entry.get("object_type"),
            "title": sug.get("display_text") or entry.get("learning_object_id"),
            "mastery_display_text": master.get("display_text"),
            "mastery_stable": bool(master.get("stable")),
            "diagnosis_label": diag_info.get("label"),
            "diagnosis_level": diag_info.get("level"),
            "suggestions": tips,
            "auto_execute": False,
            "child_decides": "建议仅供孩子选择；系统不自动执行、不跳转、不播放",
        })
    return {"available": True, "items": items}

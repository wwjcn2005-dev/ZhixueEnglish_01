#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-6-D-1 Learning Object 只读派生业务层

实现（全部只读、确定性、零 AI、零数据库写入）：

    教材事实 → Learning Object → LO Evidence → LO Mastery → LO Diagnosis
            → Textbook-first Suggestion

设计依据（冻结输入）：
  * P2-6-C-2 Learning Object 语义、稳定 ID、R1–R6 映射规则
  * P2-6-C-3 Consolidation Action（本阶段 DEFERRED，不实现）
  * P2-6-C-4 全链路设计评审（无阻塞；复用既有 P2-6-B 服务）
  * P2-6-C-4-A 音频边界（Audio=Resource，播放≠Evidence，不做任何音频改动）
  * P2-6-D-0 实施前就绪检查（N-1 pool_state 可为 None；N-2 object_type 显式；
    N-3 不依赖会话级去重）

边界：
  * 只执行 SELECT；不写 learning.db；不建表；不修改任何冻结文件；
  * LO / Evidence / Diagnosis / Suggestion 均为读时派生的结果，不落库；
  * 不调用 AI、不联网、不使用时间/随机数参与 ID 生成。
"""

from __future__ import annotations

import os

import hashlib
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
sys.path.insert(0, str(BASE / "learning"))
sys.dont_write_bytecode = True

import diagnosis_service as diag          # noqa: E402  （复用，不修改）
import evidence_service as ev             # noqa: E402  （复用，不修改）
import intervention_service as interv     # noqa: E402  （复用，不修改）
import mastery_service as mastery         # noqa: E402  （复用，不修改）

CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
CATALOG_V3 = BASE / "structured" / "exercises" / "exercise_catalog_v3.json"
QUESTION_REL = BASE / "structured" / "exercises" / "exercise_question_relations_v3.json"
RULES = BASE / "structured" / "learning" / "mastery_rules_v1.json"

TEXTBOOK_ID = "FLTRP-EN-7A-2022CUR"

#: LO 类型（C-2 冻结；Grammar 为 DEFERRED，不产出）
LO_TYPES = ("VOCAB", "PHRASE", "PATTERN", "LISTENING", "READING", "WRITING")
ITEM_TYPE_TO_LO = {"vocabulary": "VOCAB", "phrase": "PHRASE",
                   "sentence_pattern": "PATTERN"}

ObjectType = "learning_object"

_CACHE = {}


# --------------------------------------------------------------------------
# 纯函数：规范化 / canonical key / LO ID（确定性，无 IO、无时间、无随机）
# --------------------------------------------------------------------------

def normalize_lexeme(text: str) -> str:
    """教材词条规范化：NFC + 小写 + 折叠空白 + 去词尾标点；保留词内连字符与撇号。"""
    t = unicodedata.normalize("NFC", (text or "")).strip().lower()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[.,;:!?]+$", "", t).strip()
    return t


def canonical_lex_key(kind: str, lexeme: str, pos: str = "", sense: str = "") -> str:
    """词条类 canonical key（C-2 §13）。sense 当前恒空（教材 288 词面唯一）。"""
    return "lex|%s|%s|%s|%s|%s" % (TEXTBOOK_ID, kind, normalize_lexeme(lexeme),
                                   (pos or "").strip().lower(), (sense or "").strip().lower())


def canonical_task_key(kind: str, unit: str, section: str, ref) -> str:
    """任务类 canonical key：LISTENING/WRITING 用活动号；READING 用教材页。"""
    if kind == "READING":
        return "read|%s|%s|%s|%s" % (TEXTBOOK_ID, unit, section, ref)
    prefix = "listen" if kind == "LISTENING" else "write"
    return "%s|%s|%s|%s|%s" % (prefix, TEXTBOOK_ID, unit, section, ref)


def lo_id(lo_type: str, canonical_key: str) -> str:
    """`LO:<textbook>:<TYPE>:<sha256(canonical)[:12]>`（确定性、与 DB 主键解耦）。"""
    if lo_type not in LO_TYPES:
        raise ValueError("未知 LO 类型：%r（Grammar 为 DEFERRED，不产出）" % (lo_type,))
    digest = hashlib.sha256(canonical_key.encode("utf-8")).hexdigest()[:12].upper()
    return "LO:%s:%s:%s" % (TEXTBOOK_ID, lo_type, digest)


# --------------------------------------------------------------------------
# 只读数据加载
# --------------------------------------------------------------------------

def _load(path):
    key = str(path)
    if key not in _CACHE:
        _CACHE[key] = json.loads(Path(path).read_text(encoding="utf-8"))
    return _CACHE[key]


def connect_contentpack(path=CONTENTPACK) -> sqlite3.Connection:
    conn = sqlite3.connect("file:%s?mode=ro" % Path(path).as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def exercises() -> list:
    return _load(CATALOG_V3).get("exercises", [])


def _question_index() -> dict:
    out = {}
    for q in _load(QUESTION_REL).get("questions", []):
        out.setdefault(q.get("activity_id"), []).append(q)
    return out


def _text_reference_index() -> dict:
    """activity_id → 是否存在教材文本依赖（R3 证据）。"""
    out = {}
    try:
        rel = _load(BASE / "structured" / "textbook" / "textbook_content_relations_v2.json")
    except Exception:
        return out
    for r in rel.get("text_references", []):
        if r.get("to"):
            out.setdefault(r.get("from"), 0)
            out[r.get("from")] += 1
    return out


# --------------------------------------------------------------------------
# D-1：Vocabulary / Phrase / Pattern → 全局 LO（一个教材词条 = 一个 LO）
# --------------------------------------------------------------------------

def vocabulary_lo_map(contentpack_path=CONTENTPACK) -> dict:
    """{item_id: {...}}：每个教材词条 → 一个确定性全局 LO（不按 Unit/Activity 重复）。"""
    cp = connect_contentpack(contentpack_path)
    try:
        rows = [dict(r) for r in cp.execute(
            "SELECT item_id, item_type, canonical_text, part_of_speech FROM learning_item "
            "WHERE item_type IN ('vocabulary','phrase','sentence_pattern') ORDER BY item_id")]
    finally:
        cp.close()
    out = {}
    for r in rows:
        kind = ITEM_TYPE_TO_LO[r["item_type"]]
        ck = canonical_lex_key(kind, r["canonical_text"], r["part_of_speech"] or "")
        out[r["item_id"]] = {
            "learning_object_id": lo_id(kind, ck),
            "lo_type": kind,
            "canonical_key": ck,
            "lexeme": normalize_lexeme(r["canonical_text"]),
            "text": r["canonical_text"],
            "item_id": r["item_id"],
            "object_type": ObjectType,
        }
    return out


def _lexeme_index(contentpack_path=CONTENTPACK) -> dict:
    """规范化词面 → {LO 条目, 教材归属单元, 学习要求}（教材词面唯一）。

    单元归属复用 `web/content._attribution`（与页面展示同一口径，只读）；
    R4/R5 需要"本单元 + CORE"两个教材事实共同成立，缺一不可。
    """
    idx = {}
    try:
        sys.path.insert(0, str(BASE / "web"))
        import content as content_mod
        cp = content_mod._ro(contentpack_path)
        try:
            attr = content_mod._attribution(cp)
            reqs = {r["item_id"]: r["learning_requirement"] for r in cp.execute(
                "SELECT item_id, learning_requirement FROM learning_item")}
        finally:
            cp.close()
    except Exception:
        attr, reqs = {}, {}
    for item_id, info in vocabulary_lo_map(contentpack_path).items():
        info = dict(info)
        info["unit_code"] = (attr.get(item_id) or {}).get("unit_code")
        info["requirement"] = reqs.get(item_id)
        idx.setdefault(info["lexeme"], info)
    return idx


# --------------------------------------------------------------------------
# D-1：Exercise → LO（C-2 §9 的 R1–R6，确定性；不能确定 → unmapped）
# --------------------------------------------------------------------------

def exercise_lo_map(contentpack_path=CONTENTPACK) -> dict:
    """{exercise_id: {...}}；status ∈ {mapped, unmapped}；绝不为覆盖率强行归属。"""
    qidx = _question_index()
    tidx = _text_reference_index()
    lex = _lexeme_index(contentpack_path)
    out = {}
    for e in exercises():
        act = e.get("activity_id")
        qs = qidx.get(act, [])
        lo_ids, rule, reason = [], None, ""
        unit, section, no = e.get("unit"), e.get("section"), e.get("exercise_no")
        if e.get("listening_icon") or e.get("audio_required"):
            ck = canonical_task_key("LISTENING", unit, section, "A%s" % no)
            lo_ids, rule = [lo_id("LISTENING", ck)], "R1_listening_task"
            reason = "带教材耳机图标/官方音频 → 一个教材听力任务 = 一个 Listening LO"
        elif e.get("question_type") == "writing":
            ck = canonical_task_key("WRITING", unit, section, "A%s" % no)
            lo_ids, rule = [lo_id("WRITING", ck)], "R2_writing_task"
            reason = "教材写作任务 → Writing LO"
        elif (e.get("question_type") in ("short_answer", "choice", "judge", "order",
                                         "match", "fill")
              and section in ("UNDERSTANDING_IDEAS", "READING_FOR_WRITING")
              and tidx.get(act)):
            ck = canonical_task_key("READING", unit, section, e.get("textbook_page"))
            lo_ids, rule = [lo_id("READING", ck)], "R3_reading_text"
            reason = "阅读理解/短答且教材存在文本依赖 → Reading LO"
        else:
            words = []
            for q in qs:
                words.extend(q.get("related_vocabulary") or [])
            core = []
            for w in dict.fromkeys(words):
                info = lex.get(normalize_lexeme(w))
                if (info and info["lo_type"] == "VOCAB"
                        and info.get("unit_code") == unit
                        and info.get("requirement") == "CORE"):
                    core.append(info)
            if len(core) == 1:
                lo_ids, rule = [core[0]["learning_object_id"]], "R4_single_core_vocab"
                reason = "本单元唯一 CORE 词候选 → Vocabulary LO（%s）" % core[0]["lexeme"]
            elif len(core) >= 2:
                lo_ids, rule = [c["learning_object_id"] for c in core], "R5_multi_core_vocab"
                reason = "多个 CORE 词候选 → 共享证据给 %d 个 Vocabulary LO" % len(core)
        status = "mapped" if lo_ids else "unmapped"
        if status == "unmapped":
            reason = ("教材语义不足以确定归属（无听力/写作/阅读文本证据且无 CORE 词候选）"
                      if not qs else "该练习无可用映射证据（保持 unmapped，不猜）")
        out[e["exercise_id"]] = {
            "exercise_id": e["exercise_id"], "unit": unit, "section": section,
            "exercise_no": no, "question_type": e.get("question_type"),
            "status": status, "lo_ids": lo_ids, "rule": rule, "reason": reason,
            "in_contentpack_activity": bool(act),
        }
    return out


def mapping_coverage(contentpack_path=CONTENTPACK) -> dict:
    """诚实报告映射覆盖率（只用于报告，不驱动强行映射）。"""
    m = exercise_lo_map(contentpack_path)
    mapped = sum(1 for v in m.values() if v["status"] == "mapped")
    total = len(m)
    by_rule = {}
    for v in m.values():
        by_rule[v["rule"] or "unmapped"] = by_rule.get(v["rule"] or "unmapped", 0) + 1
    return {"exercises_total": total, "mapped_count": mapped,
            "unmapped_count": total - mapped,
            "coverage_ratio": round(mapped / total, 4) if total else 0.0,
            "by_rule": by_rule,
            "note": "coverage 仅用于诚实报告；不得为提升覆盖率而强行归属"}


# --------------------------------------------------------------------------
# D-2 / D-3：LO Evidence（复用 item 级有效证据 + 第二层 LO 去重）
# --------------------------------------------------------------------------

def _item_to_los(contentpack_path=CONTENTPACK) -> dict:
    """{item_id: [lo_id, ...]}（词条类 + 练习类）。"""
    idx = {item_id: [info["learning_object_id"]]
           for item_id, info in vocabulary_lo_map(contentpack_path).items()}
    for ex_id, info in exercise_lo_map(contentpack_path).items():
        if info["lo_ids"]:
            idx[ex_id] = list(info["lo_ids"])
    return idx


def lo_evidence(conn, learner_id: str, contentpack_path=CONTENTPACK,
                rules: dict = None) -> dict:
    """派生 LO 级证据集合：{lo_id: {...与 evidence_service 同构的字段 + provenance}}。

    第一层去重由 `evidence_service.collect_evidence()` 完成（item+日+类型）；
    本函数追加第二层：`learner + LO + 自然日 + task_type` 只计 1 条独立证据，
    但**保留全部来源 item/record 作为 provenance**（一条证据 + 多 LO 引用，不复制证据）。
    """
    rules = rules or ev.load_rules()
    item_los = _item_to_los(contentpack_path)
    items = [r["item_id"] for r in conn.execute(
        "SELECT DISTINCT item_id FROM learning_record WHERE learner_id=?", (learner_id,))]
    buckets = {}
    for item_id in items:
        los = item_los.get(item_id)
        if not los:
            continue
        item_ev = ev.collect_evidence(conn, learner_id, item_id, rules)
        for e in item_ev["evidence"]:
            for lo in los:
                buckets.setdefault(lo, []).append(dict(e, item_id=item_id))

    out = {}
    for lo, evidences in buckets.items():
        groups = {}
        for e in evidences:
            groups.setdefault((e["evidence_date"], e["task_type"]), []).append(e)
        independent, suppressed = [], 0
        for key, members in groups.items():
            ordered = sorted(members, key=lambda x: (x["created_at"], x["source_record_id"]))
            chosen = dict(ordered[-1])
            chosen["sources"] = [{"record_id": m["source_record_id"], "item_id": m["item_id"],
                                  "created_at": m["created_at"], "result": m["result"]}
                                 for m in ordered]
            chosen["deduped_from"] = [m["source_record_id"] for m in ordered[:-1]]
            suppressed += len(ordered) - 1
            independent.append(chosen)
        independent.sort(key=lambda x: (x["created_at"], x["source_record_id"]))
        out[lo] = {
            "learning_object_id": lo, "object_type": ObjectType,
            "evidence_count": len(independent),
            "evidence": independent,
            "suppressed_count": suppressed,
            "natural_days": sorted({e["evidence_date"] for e in independent}),
            "task_types": sorted({e["task_type"] for e in independent}),
            "recent_results": [e["result"] for e in independent[-rules["stable"]
                                                               ["recent_attempt_window"]:]],
            "item_ids": sorted({s["item_id"] for e in independent for s in e["sources"]}),
            "source_record_ids": sorted({s["record_id"] for e in independent
                                         for s in e["sources"]}),
            "invalid": [], "not_evaluable": [],
        }
    return out


# --------------------------------------------------------------------------
# D-4 / D-5：LO Mastery / LO Diagnosis（复用既有服务，零修改）
# --------------------------------------------------------------------------

def lo_mastery(conn, learner_id: str, lo_id_value: str, contentpack_path=CONTENTPACK,
               rules: dict = None, lo_evidences: dict = None) -> dict:
    rules = rules or ev.load_rules()
    evd = (lo_evidences or lo_evidence(conn, learner_id, contentpack_path, rules)).get(
        lo_id_value) or {"evidence_count": 0, "evidence": [], "task_types": [],
                         "natural_days": [], "recent_results": [], "suppressed_count": 0}
    res = mastery.evaluate(conn, learner_id, lo_id_value, rules, evidence=evd)
    res.update({"object_type": ObjectType, "learning_object_id": lo_id_value,
                "display_text": mastery.display_text(res),
                "evidence_count": evd["evidence_count"],
                "task_types": evd["task_types"], "natural_days": evd["natural_days"],
                "source_record_ids": evd.get("source_record_ids", [])})
    return res


def lo_diagnosis(conn, learner_id: str, lo_id_value: str, contentpack_path=CONTENTPACK,
                 rules: dict = None, lo_evidences: dict = None) -> dict:
    rules = rules or ev.load_rules()
    evd = (lo_evidences or lo_evidence(conn, learner_id, contentpack_path, rules)).get(
        lo_id_value) or {"evidence_count": 0, "evidence": [], "task_types": [],
                         "natural_days": [], "recent_results": [], "suppressed_count": 0}
    res = diag.diagnose(conn, learner_id, lo_id_value, rules, evidence=evd)
    res.update({"object_type": ObjectType, "learning_object_id": lo_id_value,
                "pool_state": res.get("pool_state"),
                "pool_note": "LO 级诊断的 pool_state 允许为 None（D-0 N-1）："
                             "item 级池事实需由调用方另行读取"})
    return res


def lo_suggestion(conn, learner_id: str, lo_id_value: str, contentpack_path=CONTENTPACK,
                  rules: dict = None, context_label: str = None) -> dict:
    """教材优先建议：以 LO 的代表 item 复用 `intervention_service.suggest()`。"""
    rules = rules or ev.load_rules()
    lo_type = lo_id_value.split(":")[2] if lo_id_value.count(":") >= 2 else ""
    rep = None
    if lo_type in ("VOCAB", "PHRASE", "PATTERN"):
        for item_id, info in vocabulary_lo_map(contentpack_path).items():
            if info["learning_object_id"] == lo_id_value:
                rep = item_id
                break
    else:
        for ex_id, info in exercise_lo_map(contentpack_path).items():
            if lo_id_value in (info["lo_ids"] or []):
                rep = ex_id
                break
    if rep is None:
        return {"learning_object_id": lo_id_value, "object_type": ObjectType,
                "suggestions": [], "auto_execute": False,
                "requires_resource_mapping": True,
                "missing": ["representative_item"], "reason": "找不到可定位的教材来源"}
    res = interv.suggest(conn, learner_id, rep, rules, contentpack_path, context_label)
    res.update({"object_type": ObjectType, "learning_object_id": lo_id_value,
                "auto_execute": False,
                "child_decides": "建议仅供孩子选择；系统不自动执行、不跳转、不播放"})
    return res


# --------------------------------------------------------------------------
# 组合视图（读时派生；不持久化）
# --------------------------------------------------------------------------

def needs_attention(conn, learner_id: str, contentpack_path=CONTENTPACK,
                    rules: dict = None) -> list:
    """所有"需要关注"的 LO：附 mastery / diagnosis / suggestion（只读派生）。"""
    rules = rules or ev.load_rules()
    evs = lo_evidence(conn, learner_id, contentpack_path, rules)
    out = []
    for lo in sorted(evs):
        d = lo_diagnosis(conn, learner_id, lo, contentpack_path, rules, evs)
        if d["level"] == diag.LEVEL_NONE:
            continue
        out.append({"learning_object_id": lo, "object_type": ObjectType,
                    "diagnosis": d,
                    "mastery": lo_mastery(conn, learner_id, lo, contentpack_path, rules, evs),
                    "suggestion": lo_suggestion(conn, learner_id, lo, contentpack_path,
                                                rules, d["label"])})
    return out


def summary(conn, learner_id: str, contentpack_path=CONTENTPACK) -> dict:
    """一次调用给出 D-1 全链路结果（供报告与验收使用）。"""
    rules = ev.load_rules()
    evs = lo_evidence(conn, learner_id, contentpack_path, rules)
    return {
        "learner_id": learner_id,
        "coverage": mapping_coverage(contentpack_path),
        "lo_counts": {
            "vocab_phrase_pattern": len(vocabulary_lo_map(contentpack_path)),
            "with_evidence": len(evs),
        },
        "evidence": {lo: {"evidence_count": v["evidence_count"],
                          "task_types": v["task_types"],
                          "natural_days": v["natural_days"],
                          "suppressed_count": v["suppressed_count"],
                          "item_ids": v["item_ids"]} for lo, v in evs.items()},
        "mastery": {lo: lo_mastery(conn, learner_id, lo, contentpack_path, rules, evs)
                    for lo in sorted(evs)},
        "attention": needs_attention(conn, learner_id, contentpack_path, rules),
    }


if __name__ == "__main__":      # 只读自检：不写库、不调用 AI
    conn = ev.connect_learning_db()
    try:
        print("coverage:", json.dumps(mapping_coverage(), ensure_ascii=False))
        for row in conn.execute("SELECT learner_id FROM learner"):
            s = summary(conn, row["learner_id"])
            print("learner:", row["learner_id"][-8:])
            print("  LO with evidence:", s["lo_counts"]["with_evidence"])
            for lo, m in s["mastery"].items():
                print("   %-42s %-12s %s" % (lo, m["state"], m["display_text"]))
    finally:
        conn.close()

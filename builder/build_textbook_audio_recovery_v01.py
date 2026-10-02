#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P4-02 · 官方音频补全教材资源（TEXTBOOK_AUDIO_RECOVERED，AI 调用 = 0）

只做一件事：把**教材印刷体挖空/省略、但官方音频里确实已经说出**的信息恢复出来，
写成正式教材资源记录。恢复内容来自官方音频，不是 AI 创作，因此身份是：

    TEXTBOOK_NATIVE          教材页面直接存在的内容
    TEXTBOOK_AUDIO_RECOVERED 教材页面挖空/不完整，但官方音频明确说出的内容  ← 本脚本产出
    AI_GENERATED             AI 真正创造、教材与音频中都不存在的内容（本脚本不产出）

承载模型（§6：不新建第二套体系）
  复用现有教材活动资源目录 `exercise_catalog_v3.json` 的同一 schema，输出下一版本
  `exercise_catalog_v4.json`：
    * 既有字段逐字保留（`questions[].text` = 教材原始印刷文本，含挖空原样不动）；
    * 用既有来源状态字段 `answer_status` 表达新身份
      （`TEXTBOOK_AUDIO_RECOVERED` / `NEED_REVIEW`；未处理活动保持 `NO_RELIABLE_SOURCE`）；
    * 新增最小字段 `recovered`（恢复文本 + 位置 + 音频/句段/文本块证据 + 置信度 + 方法 + run）。

证据链（回答"这段内容确实在官方音频里吗？"）
    官方 MP3(audio_id) → ASR 词级时间（既有 evidence，不重跑）→ 精确 start_ms/end_ms
    → 该音频 VERIFIED segment（audio_resource_v1，只读）→ 教材 content_block

恢复方法（确定性，复用既有证据）
  1. 教材印刷 token ↔ 音频词流 token 做序列比对（difflib.SequenceMatcher）；
  2. 只在"印刷体确实对上的区间之内"取音频多出来的内容（区间外的朗读指令/页码提示不算）；
  3. 印刷体写 "(a / b)" 选择对时，音频实际说出的那个 = 恢复值（SELECT）；
  4. 短插入且紧邻教材印制的空号 = 挖空补全（BLANK_FILL）；
     成段的音频内容（印刷体整段没有）= AUDIO_TEXT（只作证据，单独标注状态）；
  5. 排序类活动：把教材印制的条目逐条在音频里定位，得到音频中的真实顺序（CONTENT_ORDER）；
  6. 无音频词级证据 / 无法定位 / 置信度不足 → NEED_REVIEW，不入正式资源。

运行：
  python builder\build_textbook_audio_recovery_v01.py --dry-run
  python builder\build_textbook_audio_recovery_v01.py --write
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
CATALOG_V3 = BASE / "structured" / "exercises" / "exercise_catalog_v3.json"
CATALOG_V4 = BASE / "structured" / "exercises" / "exercise_catalog_v4.json"
LAYER = BASE / "structured" / "audio" / "resources" / "audio_resource_v1.json"
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
ASR_DIR = BASE / "audit" / "P3-07_preview" / "asr"

RULE_SET = "P4-02-textbook-audio-recovery-v1"
RUN_ID = "TRR:P4-02:V1"
RECOVERED = "TEXTBOOK_AUDIO_RECOVERED"
NEED_REVIEW = "NEED_REVIEW"
TARGETS = ["AU02", "AU09", "AU12", "AU16", "AU18", "AU23", "AU30", "AU32", "AU33",
           "AU37", "AU39", "AU40", "AU43", "AU45"]
ANCHOR_NEAR_MS = 6000          # 恢复片段与同音频最近 VERIFIED 句段的最大可接受距离
SHORT_INSERT_MAX = 3           # 连续 ≤3 词的音频插入 → 视为挖空补全候选
ASR_VARIANT_RATIO = 0.6        # 插入段与相邻印刷段高度相似 → 判为 ASR 变体（不是挖空）
UNPRINTED_RATIO_MAX = 0.5      # 音频里超过一半内容印刷体没有 → 属"材料未印刷"，不是"挖空"


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _tok(raw: str) -> str:
    t = (raw or "").lower().replace("\u2019", "'")
    t = re.sub(r"[^a-z0-9'$.,]", "", t)
    return t.strip(".,")


def _tokens(text: str) -> list:
    return [t for t in (_tok(x) for x in re.findall(r"[A-Za-z][A-Za-z'\-]*|\d[\d,]*", text or "")) if t]


def _is_marker(t: str) -> bool:
    return bool(re.fullmatch(r"\d[\d,]*", t))


def _pairs(text: str) -> list:
    return [(m.start(), m.group(0), m.group(1).strip(), m.group(2).strip())
            for m in re.finditer(r"\(([^()/]+?)\s*/\s*([^()/]+?)\)", text or "")]


def _sentences(words: list) -> list:
    out, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r"[.!?]$", w["raw"]) or len(cur) >= 40:
            out.append({"start_ms": cur[0]["start_ms"], "end_ms": cur[-1]["end_ms"],
                        "text": " ".join(x["raw"] for x in cur)})
            cur = []
    if cur:
        out.append({"start_ms": cur[0]["start_ms"], "end_ms": cur[-1]["end_ms"],
                    "text": " ".join(x["raw"] for x in cur)})
    return out


def _digits(t: str) -> str:
    return re.sub(r"\D", "", t or "")


def _locate_context(words: list, ctx: list):
    """在音频词流里定位印刷体上下文（用于把选择对限制在对应位置附近）。"""
    if not ctx:
        return -1, 0.0
    best, score = -1, 0.0
    for k in range(0, max(1, len(words) - len(ctx) + 1)):
        r = difflib.SequenceMatcher(None, ctx, [w["tok"] for w in words[k:k + len(ctx)]],
                                    autojunk=False).ratio()
        if r > score:
            best, score = k, r
    return (best, round(score, 3)) if score >= 0.6 else (-1, round(score, 3))


def _hits_in(words: list, a: str, b: str, lo: int, hi: int, kind: str) -> dict:
    """在 [lo,hi) 词窗内找两个候选（支持数字序列合并匹配）。"""
    ta, tb = _tok(a), _tok(b)
    hits = {}
    for i in range(max(0, lo), min(len(words), hi)):
        if words[i]["tok"] == ta:
            hits.setdefault(a, (i, i, a, kind))
        elif words[i]["tok"] == tb:
            hits.setdefault(b, (i, i, b, kind))
    for target, label in ((_digits(a), a), (_digits(b), b)):
        if len(target) < 2 or label in hits:
            continue
        for i in range(max(0, lo), min(len(words), hi)):
            merged = ""
            for j in range(i, min(len(words), i + 3)):
                merged += _digits(words[j]["raw"])
                if merged == target:
                    hits.setdefault(label, (i, j, label, "digit_sequence"))
                    break
                if len(merged) >= len(target):
                    break
    return hits


def _match_option_pair(words: list, a: str, b: str, before_ctxs: list, after_ctxs: list):
    """印刷体选择对 (a / b)：空就在前后印刷词之间 → 只在该夹缝位置附近判定。"""
    zones, seen = [], set()
    for ctx in after_ctxs:                     # 空紧跟在 "空 → 后续印刷词" 的前面
        if not ctx:
            continue
        anchor, score = _locate_context(words, ctx)
        if anchor < 0 or score < 0.8:
            continue
        zone = (anchor - 4, anchor + 1)
        if zone not in seen:
            seen.add(zone)
            zones.append(zone)
    for ctx in before_ctxs:                    # 空紧跟在 "前置印刷词 → 空" 的后面
        if not ctx:
            continue
        anchor, score = _locate_context(words, ctx)
        if anchor < 0 or score < 0.8:
            continue
        zone = (anchor + len(ctx) - 1, anchor + len(ctx) + 3)
        if zone not in seen:
            seen.add(zone)
            zones.append(zone)
    hits = {}
    for lo, hi in zones:
        for label, h in _hits_in(words, a, b, lo, hi, "near_printed_context").items():
            hits.setdefault(label, h)
    if len(hits) == 1:
        return next(iter(hits.values()))
    if len(hits) >= 2:
        first = min(hits.values(), key=lambda x: x[0])
        return first[0], first[1], first[2], "ambiguous_both_present"
    whole = _hits_in(words, a, b, 0, len(words), "whole_audio_unique")
    if len(whole) == 1:
        return next(iter(whole.values()))
    if len(whole) >= 2:
        first = min(whole.values(), key=lambda x: x[0])
        return first[0], first[1], first[2], "ambiguous_both_present"
    return None


def _anchor(start_ms: int, end_ms: int, segs: list) -> tuple:
    """恢复片段 → VERIFIED segment 锚点（优先包含/重叠，其次最近）。"""
    inside = [s for s in segs if s["start_ms"] <= start_ms and end_ms <= s["end_ms"]]
    if inside:
        return inside[0]["segment_id"], "inside", 0
    over = [s for s in segs if s["start_ms"] < end_ms and start_ms < s["end_ms"]]
    if over:
        return over[0]["segment_id"], "overlap", 0
    best, dist = None, None
    for s in segs:
        d = min(abs(start_ms - s["end_ms"]), abs(s["start_ms"] - end_ms))
        if dist is None or d < dist:
            best, dist = s, d
    if best is not None and dist <= ANCHOR_NEAR_MS:
        return best["segment_id"], ("nearest_before" if best["end_ms"] <= start_ms
                                    else "nearest_after"), dist
    return None, "none", None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--detail", default="", help="逗号分隔的 AU，打印逐条恢复明细")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    cat = json.loads(CATALOG_V3.read_text(encoding="utf-8"))
    v3_text = {e["exercise_id"]: json.dumps(e.get("questions"), ensure_ascii=False)
               for e in cat["exercises"]}
    layer = json.loads(LAYER.read_text(encoding="utf-8"))
    by_audio = {r["audio_code"]: r for r in layer["audio_resources"]}
    all_seg_ids = {s["segment_id"] for r in layer["audio_resources"] for s in r["segments"]}
    cp = sqlite3.connect("file:%s?mode=ro" % CONTENTPACK.as_posix(), uri=True)
    valid_blocks = {r[0] for r in cp.execute("SELECT block_id FROM content_block")}
    valid_audio = {r[0] for r in cp.execute("SELECT audio_id FROM audio_asset")}

    by_code = {}
    for e in cat["exercises"]:
        code = (e.get("audio_id") or "").split(":")[-1]
        if code:
            by_code.setdefault(code, []).append(e)

    run = {"run_id": RUN_ID, "rule_set": RULE_SET, "method": "deterministic-audio-evidence-recovery",
           "model": "none", "ai_calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
           "generated_at": _now(),
           "sources": [{"path": str(p.relative_to(BASE)).replace("\\", "/"),
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                       for p in (CATALOG_V3, LAYER, CONTENTPACK)]}
    detail = {c for c in args.detail.split(",") if c}
    per_au = {}

    for code in TARGETS:
        res = by_audio.get(code)
        if not res:
            per_au[code] = {"status": "MISSING_AUDIO"}
            continue
        duration = res.get("duration_ms") or 0
        segs = [s for s in res["segments"]
                if s["status"] == "VERIFIED" and s["timing_kind"] == "exact" and s["start_ms"] is not None]
        asr = json.loads((ASR_DIR / (code + ".json")).read_text(encoding="utf-8"))
        words = [{"tok": _tok(w.get("word")), "raw": (w.get("word") or "").strip(),
                  "start_ms": w.get("start_ms"), "end_ms": w.get("end_ms")}
                 for w in (asr.get("words") or [])]
        words = [w for w in words if w["tok"]]
        atoks = [w["tok"] for w in words]
        ex_list = by_code.get(code) or []
        summary = {"status": NEED_REVIEW, "records": [], "verified_segments": len(segs)}

        for e in ex_list:
            printed = " ".join((q.get("text") or "") for q in (e.get("questions") or []))
            if not printed.strip():
                continue
            ptoks = _tokens(printed)
            cmp_toks = [None if _is_marker(t) else t for t in ptoks]
            kept = [t for t in cmp_toks if t]
            sm = difflib.SequenceMatcher(None, kept, atoks, autojunk=False)
            ops = sm.get_opcodes()
            # 印刷体真正对上的音频区间（区间外的朗读指令不算恢复内容）
            eq_j = [j for tag, i1, i2, j1, j2 in ops if tag == "equal" for j in range(j1, j2)]
            if not eq_j:
                summary["records"].append({"exercise_id": e["exercise_id"], "status": NEED_REVIEW,
                                           "reason": "印刷文本与音频词流无可靠对应"})
                continue
            j_lo, j_hi = min(eq_j), max(eq_j)
            marker_pos = [i for i, t in enumerate(cmp_toks) if t is None]
            has_pairs = bool(_pairs(printed))
            declared = e.get("blanks")
            # 音频中"印刷体确实对不上"的比例：低=挖空类；高=整段听力材料未印刷
            matched_j = {j for tag, i1, i2, j1, j2 in ops if tag == "equal" for j in range(j1, j2)}
            unprinted = len([j for j in range(len(words)) if j not in matched_j])
            unprinted_ratio = round(unprinted / max(1, len(words)), 3)
            blank_like = unprinted_ratio <= UNPRINTED_RATIO_MAX
            spans = []
            for tag, i1, i2, j1, j2 in ops:
                if tag == "replace" and j2 > j1:
                    pseg = " ".join(t for t in cmp_toks[i1:i2] if t)
                    aseg = " ".join(w["tok"] for w in words[j1:j2])
                    if difflib.SequenceMatcher(None, pseg, aseg, autojunk=False).ratio() >= ASR_VARIANT_RATIO:
                        continue                    # ASR 听写变体（如 Limong ≈ Li Meng），不是挖空
                if tag in ("insert", "replace") and j2 > j1:
                    j1c, j2c = max(j1, j_lo), min(j2, j_hi + 1)
                    if j2c <= j1c:
                        continue
                    run_words = words[j1c:j2c]
                    kind = ("BLANK_FILL" if (blank_like and not has_pairs
                                             and len(run_words) <= SHORT_INSERT_MAX) else "AUDIO_TEXT")
                    spans.append({"kind": kind,
                                  "recovered_text": " ".join(w["raw"] for w in run_words),
                                  "start_ms": run_words[0]["start_ms"],
                                  "end_ms": run_words[-1]["end_ms"],
                                  "asr_token_range": [j1c, j2c - 1],
                                  "near_printed_blank_marker": any(abs(m - i1) <= 4 for m in marker_pos)})
            for _, raw_pair, a, b in _pairs(printed):
                tail = re.split(r"\)", printed[printed.find(raw_pair) + len(raw_pair):], 1)[0]
                head = printed[:printed.find(raw_pair)]
                after = [[t for t in _tokens(tail)][:2], [t for t in _tokens(tail)][:1]]
                before = [[t for t in _tokens(head)][-2:], [t for t in _tokens(head)][-1:]]
                hit = _match_option_pair(words, a, b,
                                         [c for c in before if c], [c for c in after if c])
                if hit:
                    i, j, label, how = hit
                    spans.append({"kind": "SELECT", "recovered_text": label,
                                  "options_printed": [a, b], "start_ms": words[i]["start_ms"],
                                  "end_ms": words[j]["end_ms"], "asr_token_range": [i, j],
                                  "match_kind": how})
            # 排序类：把教材印制条目逐条在音频里定位，得到真实顺序
            if re.search(r"\border\b", (e.get("instruction") or ""), re.I) and e.get("check_items"):
                located = []
                missing = 0
                for item in e["check_items"]:
                    it = _tokens(item)
                    if not it:
                        continue
                    best, score = None, 0.0
                    for k in range(0, max(1, len(atoks) - len(it) + 1)):
                        r = difflib.SequenceMatcher(None, it, atoks[k:k + len(it)], autojunk=False).ratio()
                        if r > score:
                            best, score = k, r
                    if best is not None and score >= 0.75:
                        located.append({"text": item, "asr_index": best, "score": round(score, 3),
                                        "start_ms": words[best]["start_ms"],
                                        "end_ms": words[min(len(words) - 1, best + len(it) - 1)]["end_ms"]})
                    else:
                        missing += 1
                if located:
                    located.sort(key=lambda x: x["asr_index"])
                    spans.append({"kind": "CONTENT_ORDER",
                                  "recovered_text": " → ".join(x["text"] for x in located),
                                  "items": located,
                                  "items_declared": len(e["check_items"]), "items_unlocated": missing,
                                  "start_ms": located[0]["start_ms"], "end_ms": located[-1]["end_ms"],
                                  "asr_token_range": [located[0]["asr_index"], located[-1]["asr_index"]]})

            if not spans:
                continue
            for sp in spans:
                sid, how, dist = _anchor(sp["start_ms"], sp["end_ms"], segs)
                sp["source_segment_id"] = sid
                sp["segment_anchor"] = how
                sp["anchor_distance_ms"] = dist
                sp["source_text_block_ids"] = sorted(
                    {s["text_resource_id"] for s in segs
                     if s["segment_id"] == sid and s["text_resource_id"]})
                base = {"inside": 0.95, "overlap": 0.9, "nearest_before": 0.75,
                        "nearest_after": 0.75, "none": 0.4}[how]
                if sp.get("match_kind") == "digit_sequence":
                    base = max(base, 0.85)
                if sp.get("match_kind") == "ambiguous_both_present":
                    base = 0.4                      # 两个候选都在音频里 → 无法判定
                sp["numeric_risk"] = bool(_tokens(sp["recovered_text"])) and all(
                    _is_marker(t) for t in _tokens(sp["recovered_text"]))
                if sp["numeric_risk"] and sp["kind"] == "BLANK_FILL":
                    base -= 0.1                      # 纯数字靠 ASR 风险略高（记录风险标记）
                sp["confidence"] = round(max(0.0, base), 2)
                if sp["kind"] == "CONTENT_ORDER" and sp.get("items_unlocated"):
                    sp["confidence"] = round(min(sp["confidence"], 0.5), 2)   # 有条目定位不到 → 顺序不可靠
                sp["status"] = RECOVERED if (sid and sp["confidence"] >= 0.7) else NEED_REVIEW
            # 教材自己声明的空数 = 音频证据确认数 → 交叉验证，提升这组片段的置信度
            structural_pre = [s for s in spans
                              if s["kind"] in ("BLANK_FILL", "SELECT", "CONTENT_ORDER")]
            if declared is not None and structural_pre and len(structural_pre) == declared:
                for s in structural_pre:
                    if s.get("match_kind") != "ambiguous_both_present":
                        s["confidence"] = round(max(s["confidence"], 0.8), 2)
                        s["textbook_blank_count_confirmed"] = True
                        s["status"] = RECOVERED if s["source_segment_id"] else NEED_REVIEW
            structural = [s for s in spans if s["kind"] in ("BLANK_FILL", "SELECT", "CONTENT_ORDER")]
            audio_only = [s for s in spans if s["kind"] == "AUDIO_TEXT"]
            all_ok = bool(structural) and all(s["status"] == RECOVERED for s in structural)
            count_ok = (declared is None) or (len(structural) >= declared)
            ok = bool(structural) and all_ok and count_ok
            blob = "|".join([code, e["exercise_id"],
                             ";".join("%s@%s-%s" % (s["kind"], s["start_ms"], s["end_ms"]) for s in spans)])
            e["recovered"] = {
                "recovery_kind": ("CONTENT_ORDER" if any(s["kind"] == "CONTENT_ORDER" for s in spans)
                                  else "BLANK_FILL" if structural else "AUDIO_TEXT"),
                "original_text": printed,
                "recovered_text": " | ".join(s["recovered_text"] for s in spans),
                "spans": spans,
                "source_audio_id": res["audio_asset_id"],
                "audio_evidence": str((ASR_DIR / (code + ".json")).relative_to(BASE)).replace("\\", "/"),
                "evidence": "官方音频实际说出的内容（既有 ASR 词级时间 = alignment evidence）",
                "recovery_method": "printed↔spoken token alignment + option-pair / order locating",
                "generation_run_id": RUN_ID,
                "content_hash": hashlib.sha1(blob.encode("utf-8")).hexdigest(),
                "structural_spans": len(structural), "audio_text_spans": len(audio_only),
                "declared_blanks": declared,
                "audio_unprinted_ratio": unprinted_ratio,
                "activity_class": "BLANK_FILL" if blank_like else "UNPRINTED_AUDIO_MATERIAL",
                "blank_count_mismatch": bool(declared and len(structural) != declared),
                "unresolved_spans": [s["recovered_text"][:60] for s in structural
                                     if s["status"] != RECOVERED],
                "declared_blanks_unconfirmed": max(0, (declared or 0) - len(structural)),
            }
            e["answer_status"] = RECOVERED if ok else NEED_REVIEW
            e["answer_note"] = (
                "教材印刷体挖空/不完整处，官方音频已明确说出，恢复值来自音频证据（教材印刷原文保持不变）。"
                if ok else (
                    "音频证据确认的挖空数与教材声明不一致（教材 %s 空，音频确认 %s 处）→ 待人工复核。"
                    % (declared, len(structural)) if declared and len(structural) != declared else
                    "音频证据不足以完整可靠恢复（缺 VERIFIED segment 锚点 / 置信度不足 / "
                    "只有整段音频内容未印刷）→ 待人工复核。"))
            summary["records"].append({"exercise_id": e["exercise_id"], "status": e["answer_status"],
                                       "spans": [(s["kind"], s["recovered_text"][:40], s["confidence"])
                                                 for s in spans]})
            if ok:
                summary["status"] = RECOVERED
        per_au[code] = summary
        if code in detail:
            print("=" * 100)
            print(code, summary["status"], "| verified_segments:", len(segs))
            for rec in summary["records"]:
                print("  ", rec["exercise_id"], rec["status"])
                for s in rec.get("spans") or []:
                    print("      %-14s %-45s conf=%s" % (s[0], s[1], s[2]))

    rec_ex = [e for e in cat["exercises"] if e.get("recovered")]
    run["records"] = {
        "exercises_with_recovery": len(rec_ex),
        "recovered": sum(1 for e in rec_ex if e["answer_status"] == RECOVERED),
        "need_review": sum(1 for e in rec_ex if e["answer_status"] == NEED_REVIEW),
        "recovered_spans": sum(e["recovered"]["structural_spans"] for e in rec_ex),
        "audio_text_spans": sum(e["recovered"]["audio_text_spans"] for e in rec_ex),
        "spans_total": sum(len(e["recovered"]["spans"]) for e in rec_ex)}
    cat["rule_set"] = RULE_SET
    cat["generated_at"] = _now()
    cat["recovery_run"] = run
    cat["counts"] = dict(cat.get("counts") or {})
    cat["counts"]["audio_recovered"] = run["records"]["recovered"]
    cat["counts"]["audio_recovery_need_review"] = run["records"]["need_review"]
    run["per_audio"] = {
        code: {"status": s.get("status"), "verified_segments": s.get("verified_segments"),
               "records": len(s.get("records") or [])}
        for code, s in per_au.items()}

    # ---------------- 质量门禁
    problems = []
    hashes = [e["recovered"]["content_hash"] for e in rec_ex]
    if len(hashes) != len(set(hashes)):
        problems.append("content_hash 重复")
    for e in rec_ex:
        r = e["recovered"]
        if json.dumps(e.get("questions"), ensure_ascii=False) != v3_text[e["exercise_id"]]:
            problems.append("%s 教材印刷原文被改动" % e["exercise_id"])
        if r["source_audio_id"] not in valid_audio:
            problems.append("%s audio_id 无效" % e["exercise_id"])
        if (e.get("audio_id") or "").split(":")[-1] != r["source_audio_id"].split(":")[-1]:
            problems.append("%s audio_id 与活动不一致" % e["exercise_id"])
        for sp in r["spans"]:
            if sp["start_ms"] is None or sp["end_ms"] is None or sp["start_ms"] >= sp["end_ms"]:
                problems.append("%s 恢复片段时间非法" % e["exercise_id"])
            if not (0 <= sp["start_ms"] and sp["end_ms"] <= (by_audio[r["source_audio_id"].split(":")[-1]]["duration_ms"] or 0)):
                problems.append("%s 恢复片段超出音频时长" % e["exercise_id"])
            if sp.get("source_segment_id") and sp["source_segment_id"] not in all_seg_ids:
                problems.append("%s segment_id 无效" % e["exercise_id"])
            for b in sp.get("source_text_block_ids") or []:
                if b not in valid_blocks:
                    problems.append("%s text_block 无效" % e["exercise_id"])
            if not sp["recovered_text"].strip():
                problems.append("%s 恢复片段为空" % e["exercise_id"])
    for code, s in per_au.items():
        for rec in s.get("records") or []:
            pass

    print("run:", RUN_ID, "| ai_calls:", run["ai_calls"], "| model:", run["model"])
    for code in TARGETS:
        s = per_au.get(code) or {}
        print("  %-5s %-22s verified_seg=%-3s records=%d"
              % (code, s.get("status"), s.get("verified_segments", "-"), len(s.get("records") or [])))
    print("records:", run["records"])
    print("质检问题:", len(problems), problems[:5])
    if problems:
        print("STOP: 质检未通过，未写文件。")
        return 3
    if args.write and not args.dry_run:
        CATALOG_V4.write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
        print("写出 →", CATALOG_V4)
    else:
        print("（未写文件）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

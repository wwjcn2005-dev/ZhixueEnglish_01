#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""27 个 PARTIAL 官方活动音频 · 句级边界加工（P3-06 / P3-07 方法复用，AI 调用 = 0）

唯一目标：把当前 `alignment_status = PARTIAL` 的 27 个官方教材活动音频里、仍然只有
**粗时间窗**的句级段落（`alignment_method = p3_07_asr_word_window_match`），沿用 P3-07
已经验证过的边界方法继续加工成**可核对的时间边界**，写回正式音频资源层。

方法完全复用（不新设计算法）：
  * 匹配：`audit/P3-07_preview/match_and_select_preview.py` 的
    `tokens()` / word-window 匹配（`matched_candidates.json` 已存 word_start_idx / word_end_idx）。
  * 边界：`audit/P3-07_preview/deep_review_selected.py` 的
    `low_energy_runs()` + speech_start/speech_end 前后 1.2s/1.6s 低能量区搜索
    + 不越过前/后句 speech 的硬约束 + 回退规则 + 边界分类
    （GOOD_BOUNDARY / AUTO_RESOLVED / REAL_UNCERTAIN / NEXT_SENTENCE_INTRUSION / TRUNCATION_RISK）。

权威关系（不可动摇）：
    官方 MP3 → ASR 词级时间（仅作 alignment evidence） → 教材原文匹配 → 教材 text ID
    → start_ms / end_ms → 句/片段资源
  教材原文是“说什么”的唯一权威；ASR 转写永不写成正式文本。

处理范围（严格）：
  * 只处理 alignment_status == PARTIAL 的 27 个音频（21 VERIFIED / 6 Phonetics / 288 词 WAV 一律不动）；
  * 只有边界判定为 GOOD_BOUNDARY / AUTO_RESOLVED 的段落才升级为 exact + VERIFIED；
  * 其余保持原样（PARTIAL，保留原粗时间窗），只补边界证据。

输入（只读）：
  structured/audio/resources/audio_resource_v1.json
  audit/P3-07_preview/matched_candidates.json
  audit/P3-07_preview/audio_index.json
  audit/P3-07_preview/asr/AUxx.json

输出：
  structured/audio/resources/audio_resource_v1.json            （句级边界回填，其余字段不动）
  audit/P3-08_partial_sentence_boundary_report.json            （逐条加工证据，供复核）

运行（需要 PyAV，P3-07 当年的同环境）：
  D:\ZhixueEnglish\tools\faster_whisper_venv\Scripts\python.exe builder\build_audio_sentence_boundaries_v01.py
"""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

try:
    import av                                        # P3-07 同款解码路径（低能量区分析用）
except ImportError:                                  # pragma: no cover
    av = None

BASE = Path(__file__).resolve().parents[1]
LAYER = BASE / "structured" / "audio" / "resources" / "audio_resource_v1.json"
PREVIEW = BASE / "audit" / "P3-07_preview"
MATCHED = PREVIEW / "matched_candidates.json"
AUDIO_INDEX = PREVIEW / "audio_index.json"
ASR_DIR = PREVIEW / "asr"
REPORT = BASE / "audit" / "P3-08_partial_sentence_boundary_report.json"

ROUGH_METHOD = "p3_07_asr_word_window_match"
DEEP_METHOD = "p3_07_deep_review_boundary_pass"
BOUNDARY_PASS = ("GOOD_BOUNDARY", "AUTO_RESOLVED")
STEP = "builder/build_audio_sentence_boundaries_v01.py"


# ---------------------------------------------------------------- P3-07 同款工具函数
def tokens(text: str) -> list:
    """与 audit/P3-07_preview/deep_review_selected.py 完全一致的分词/归一化。"""
    text = (text or "").lower().replace("\u2019", "'")
    for a, b in {"i'm": "i am", "it's": "it is", "don't": "do not",
                 "we've": "we have", "that's": "that is", "let's": "let us",
                 "can't": "cannot", "couldn't": "could not",
                 "wouldn't": "would not"}.items():
        text = text.replace(a, b)
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", text)


def percentile(values, q):
    if not values:
        return 0
    a = sorted(values)
    return a[min(len(a) - 1, max(0, int((len(a) - 1) * q)))]


def low_energy_runs(audio_path: str) -> list:
    """与 P3-07 deep review 完全一致的低能量（静音）区间提取。"""
    with av.open(audio_path) as c:
        st = c.streams.audio[0]
        samples = []
        for frame in c.decode(st):
            arr = frame.to_ndarray()
            samples.extend((arr[0] if arr.ndim == 2 else arr).astype("float32").tolist())
        sr = st.rate
    frame = max(1, int(sr * 0.01))
    rms = []
    for i in range(0, len(samples), frame):
        chunk = samples[i:i + frame]
        if chunk:
            rms.append(math.sqrt(sum(x * x for x in chunk) / len(chunk)))
    threshold = max(0.006, percentile(rms, 0.20) * 1.8)
    runs, start = [], None
    for i, value in enumerate(rms):
        low = value <= threshold
        if low and start is None:
            start = i
        if ((not low) or i == len(rms) - 1) and start is not None:
            end = i + 1 if (low and i == len(rms) - 1) else i
            a, b = start * 10, end * 10
            if b - a >= 70:
                runs.append({"start_ms": a, "end_ms": b, "duration_ms": b - a})
            start = None
    return runs


def find_match(target: list, words: list):
    """P3-07 word window 匹配；返回 (score, start_idx, end_idx)。"""
    n = len(target)
    best = None
    for i in range(0, max(0, len(words) - n + 1)):
        score = SequenceMatcher(None, target, [w["tok"] for w in words[i:i + n]]).ratio()
        if best is None or score > best[0]:
            best = (score, i, i + n - 1)
    return best


def boundary_pass(row: dict, idx: int, rows: list, words: list,
                  duration_ms: int, runs: list) -> dict:
    """P3-07 deep review 边界规则（逐条复用，未新增判定标准）。"""
    target = tokens(row["textbook_text"])
    found = find_match(target, words)
    if found is None:                                # ASR 词数少于教材句：退用既有匹配窗口
        found = (row.get("match_score", 0), row["word_start_idx"], row["word_end_idx"])
    score, si, ei = found
    speech_start, speech_end = words[si]["start_ms"], words[ei]["end_ms"]
    prev_end = rows[idx - 1]["rough_end_ms"] if idx > 0 else 0
    next_start = rows[idx + 1]["rough_start_ms"] if idx + 1 < len(rows) else duration_ms

    before = [r for r in runs
              if r["end_ms"] <= speech_start + 120
              and r["end_ms"] > prev_end
              and r["start_ms"] >= max(0, prev_end - 30)]
    br = max(before, key=lambda r: r["end_ms"]) if before else None
    if br and speech_start - br["end_ms"] <= 1200:
        final_start = max(br["start_ms"], min(br["end_ms"], speech_start - 60))
        start_reason = "waveform_before_low_energy"
    else:
        final_start = max(prev_end, speech_start - 80)
        start_reason = "word_timestamp_fallback"

    after = [r for r in runs
             if r["start_ms"] >= speech_end - 120
             and r["start_ms"] < next_start
             and r["end_ms"] <= next_start + 120]
    ar = min(after, key=lambda r: r["start_ms"]) if after else None
    if ar and ar["start_ms"] - speech_end <= 1600:
        final_end = min(ar["end_ms"], max(ar["start_ms"], speech_end + 60), next_start - 30)
        if final_end < speech_end:
            final_end = speech_end
        end_reason = "waveform_after_low_energy"
    else:
        final_end = min(next_start - 30, speech_end + 120)
        if final_end < speech_end:
            final_end = speech_end
        end_reason = "word_timestamp_fallback"

    if final_start >= final_end:
        final_start, final_end = speech_start, max(speech_end, speech_start + 100)
        start_reason = end_reason = "invalid_interval_fallback"

    if final_end < speech_end or final_start > speech_start:
        status = "TRUNCATION_RISK"
    elif not br:
        status = "REAL_UNCERTAIN" if speech_start - prev_end < 80 else "GOOD_BOUNDARY"
    elif not ar or next_start <= speech_end + 80:
        status = "NEXT_SENTENCE_INTRUSION" if next_start <= speech_end + 80 else "AUTO_RESOLVED"
    else:
        status = "AUTO_RESOLVED"
    return {"match_score": round(score, 4), "word_start_idx": si, "word_end_idx": ei,
            "speech_start_ms": speech_start, "speech_end_ms": speech_end,
            "candidate_start_ms": int(round(final_start)), "candidate_end_ms": int(round(final_end)),
            "boundary_status": status, "boundary_confidence": ("HIGH" if status in BOUNDARY_PASS
                                                               else "BOUNDARY_UNCERTAIN"),
            "start_reason": start_reason, "end_reason": end_reason}


# ---------------------------------------------------------------- 主流程
def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if av is None:
        print("STOP: 缺少 PyAV（P3-07 低能量区分析依赖 av）。"
              "请用 tools/faster_whisper_venv/Scripts/python.exe 运行本脚本。")
        return 2

    layer = json.loads(LAYER.read_text(encoding="utf-8"))
    resources = layer["audio_resources"]
    partial = [r for r in resources if r.get("alignment_status") == "PARTIAL"]
    partial_codes = [r["audio_code"] for r in partial]
    print("PARTIAL 音频:", len(partial_codes), partial_codes)

    # 冻存“不该动”的部分，写完用于回比（21 VERIFIED + 6 Phonetics + 288 词段）
    frozen_before = {r["audio_code"]: json.dumps(r, ensure_ascii=False, sort_keys=True)
                     for r in resources if r["audio_code"] not in partial_codes}

    matched = json.loads(MATCHED.read_text(encoding="utf-8"))
    audio_index = {x["audio_num"]: x
                   for x in json.loads(AUDIO_INDEX.read_text(encoding="utf-8"))}
    by_audio: dict = defaultdict(list)
    for row in matched:
        if (row.get("match_confidence") in ("HIGH", "MEDIUM")
                and (row.get("rough_end_ms") or 0) > (row.get("rough_start_ms") or 0)):
            by_audio[row["audio_num"]].append(row)
    for rows in by_audio.values():
        rows.sort(key=lambda x: x["rough_start_ms"])

    asr_cache: dict = {}

    def asr_words(code: str) -> list:
        if code not in asr_cache:
            data = json.loads((ASR_DIR / (code + ".json")).read_text(encoding="utf-8"))
            words = []
            for w in data.get("words") or []:
                for tok in tokens(w.get("word", "")):
                    words.append({"tok": tok, "raw": w.get("word", ""),
                                  "start_ms": w.get("start_ms"), "end_ms": w.get("end_ms")})
            asr_cache[code] = words
        return asr_cache[code]

    runs_cache: dict = {}
    rows_report = []
    upgraded = kept = 0
    status_counts = Counter()
    used_asr = []

    for res in partial:
        code = res["audio_code"]
        rows = by_audio.get(code) or []
        if not rows:
            print("WARN: %s 无 P3-07 候选（保持 PARTIAL）" % code)
            continue
        words = asr_words(code)
        runs = runs_cache.setdefault(
            code, low_energy_runs(audio_index[code]["absolute_path"]))
        duration = int(audio_index[code]["duration_ms"])
        used_asr.append(code)

        by_sid = {s["alignment_evidence"].get("sentence_id"): s
                  for s in res["segments"] if s.get("alignment_method") == ROUGH_METHOD}

        for idx, row in enumerate(rows):
            seg = by_sid.get(row["sentence_id"])
            if seg is None:
                print("WARN: %s 段缺失 %s（跳过）" % (code, row["sentence_id"]))
                continue
            verdict = boundary_pass(row, idx, rows, words, duration, runs)
            status_counts[verdict["boundary_status"]] += 1
            original = {"start_ms": seg.get("start_ms"), "end_ms": seg.get("end_ms"),
                        "timing_kind": seg.get("timing_kind"), "status": seg.get("status")}
            evidence = dict(seg.get("alignment_evidence") or {})
            evidence.update({
                "speech_start_ms": verdict["speech_start_ms"],
                "speech_end_ms": verdict["speech_end_ms"],
                "boundary_status": verdict["boundary_status"],
                "boundary_confidence": verdict["boundary_confidence"],
                "boundary_start_reason": verdict["start_reason"],
                "boundary_end_reason": verdict["end_reason"],
                "boundary_candidate_start_ms": verdict["candidate_start_ms"],
                "boundary_candidate_end_ms": verdict["candidate_end_ms"],
                "boundary_method": "p3_07_deep_review_boundary",
                "asr_artifact": "audit/P3-07_preview/asr/%s.json" % code,
            })
            seg["alignment_evidence"] = evidence

            ok = (verdict["boundary_confidence"] == "HIGH"
                  and 0 <= verdict["candidate_start_ms"] < verdict["candidate_end_ms"] <= duration)
            if ok:
                seg["start_ms"] = verdict["candidate_start_ms"]
                seg["end_ms"] = verdict["candidate_end_ms"]
                seg["timing_kind"] = "exact"
                seg["alignment_method"] = DEEP_METHOD
                seg["status"] = "VERIFIED"
                seg["confidence"] = row.get("match_confidence") or "HIGH"
                upgraded += 1
            else:
                kept += 1
            rows_report.append({
                "audio_code": code, "unit_code": res["unit_code"],
                "sentence_id": row["sentence_id"], "segment_id": seg["segment_id"],
                "text_resource_id": seg["text_resource_id"],
                "textbook_text": row["textbook_text"], "asr_text": row["asr_text"],
                "match_confidence": row.get("match_confidence"),
                "match_score": verdict["match_score"],
                "original_start_ms": original["start_ms"], "original_end_ms": original["end_ms"],
                "original_status": original["status"],
                "speech_start_ms": verdict["speech_start_ms"],
                "speech_end_ms": verdict["speech_end_ms"],
                "final_start_ms": verdict["candidate_start_ms"],
                "final_end_ms": verdict["candidate_end_ms"],
                "boundary_status": verdict["boundary_status"],
                "start_reason": verdict["start_reason"], "end_reason": verdict["end_reason"],
                "result": "VERIFIED" if ok else "PARTIAL",
            })

        # ---- 资源级字段按既有规则重算（与 build_audio_resource_layer_v01.py 同规则）
        segs = res["segments"]
        exact = [s for s in segs if s["timing_kind"] == "exact" and s["text_resource_id"]]
        verified_ids = {s["text_resource_id"] for s in exact if s["status"] == "VERIFIED"}
        partial_ids = {s["text_resource_id"] for s in segs
                       if s["status"] == "PARTIAL" and s["text_resource_id"]}
        if any(s["status"] == "VERIFIED" for s in segs) and exact:
            res["alignment_status"] = "VERIFIED"
        elif partial_ids:
            res["alignment_status"] = "PARTIAL"
        elif segs:
            res["alignment_status"] = "NEED_MANUAL_CONFIRMATION"
        else:
            res["alignment_status"] = "NO_TEXT_MATCH"
        if exact:
            res["readiness"] = "READY_DETERMINISTIC"
        elif partial_ids:
            res["readiness"] = "READY_WITH_PROGRAM_PROCESSING"
        else:
            res["readiness"] = "NEEDS_TEXT_RELATION"
        res["confidence"] = ("HIGH" if res["alignment_status"] == "VERIFIED" else
                             "MEDIUM" if res["alignment_status"] == "PARTIAL" else "LOW")
        res["counts"]["exact_segments"] = len(exact)
        res["counts"]["partial_segments"] = sum(1 for s in segs if s["status"] == "PARTIAL")
        res["counts"]["text_blocks"] = len(verified_ids | partial_ids)

    # ---- 上游来源补充（新增时间证据出处；不改 schema）
    have = {s["path"] for s in layer.get("sources") or []}
    for code in used_asr:
        rel = "audit/P3-07_preview/asr/%s.json" % code
        if rel in have:
            continue
        digest = hashlib.sha256((ASR_DIR / (code + ".json")).read_bytes()).hexdigest()
        layer["sources"].append({"path": rel, "sha256": digest})
        have.add(rel)
    for rel, p in (("audit/P3-07_preview/audio_index.json", AUDIO_INDEX),):
        if rel not in have:
            layer["sources"].append({"path": rel,
                                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
            have.add(rel)
    layer["generated_by"] = "builder/build_audio_resource_layer_v01.py + " + STEP

    # ---- 最小验证（写盘前）
    problems = []
    ok_codes = {r["audio_code"] for r in resources}
    if len(resources) != 54 or len(ok_codes) != 54:
        problems.append("资源数/唯一性异常")
    seg_ids = [s["segment_id"] for r in resources for s in r["segments"]]
    if len(seg_ids) != len(set(seg_ids)):
        problems.append("segment_id 重复")
    for r in resources:
        dur = r.get("duration_ms") or 0
        for s in r["segments"]:
            # 与 learning/audio_resource_service.integrity_check 同口径：只约束 VERIFIED 段
            if s["status"] == "VERIFIED":
                if not s.get("text_resource_id"):
                    problems.append("%s VERIFIED 段无教材文本 ID" % r["audio_code"])
                if s.get("start_ms") is None or s.get("end_ms") is None:
                    problems.append("%s VERIFIED 段时间缺失" % r["audio_code"])
                elif not (0 <= s["start_ms"] < s["end_ms"] <= dur):
                    problems.append("%s 时间越界 %s-%s / %s"
                                    % (r["audio_code"], s["start_ms"], s["end_ms"], dur))
                if not s.get("alignment_evidence"):
                    problems.append("%s VERIFIED 段缺证据" % r["audio_code"])
        # 本次加工过的段必须有边界证据
        for s in r["segments"]:
            if s.get("alignment_method") == DEEP_METHOD:
                ev = s.get("alignment_evidence") or {}
                for k in ("speech_start_ms", "speech_end_ms", "boundary_status", "asr_artifact"):
                    if ev.get(k) in (None, ""):
                        problems.append("%s 加工段缺 %s" % (r["audio_code"], k))
                if s["status"] != "VERIFIED" or s["timing_kind"] != "exact":
                    problems.append("%s 加工段状态异常" % r["audio_code"])
    frozen_after = {r["audio_code"]: json.dumps(r, ensure_ascii=False, sort_keys=True)
                    for r in resources if r["audio_code"] not in partial_codes}
    changed_frozen = [c for c in frozen_before if frozen_before[c] != frozen_after.get(c)]
    if changed_frozen:
        problems.append("原有非 PARTIAL 资源被改动：%s" % changed_frozen)
    if problems:
        print("STOP: 写盘前验证未通过，未修改任何文件：")
        for p in problems[:20]:
            print("  -", p)
        return 3

    LAYER.write_text(json.dumps(layer, ensure_ascii=False, indent=1), encoding="utf-8")

    stat = Counter(r["alignment_status"] for r in resources)
    ready = Counter(r["readiness"] for r in resources)
    report = {
        "step": STEP,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "ai_calls": 0,
        "scope": {"partial_audios": partial_codes, "processed_audios": used_asr},
        "methods_reused": {
            "match": "audit/P3-07_preview/match_and_select_preview.py (word window / tokens)",
            "boundary": "audit/P3-07_preview/deep_review_selected.py (low-energy runs + speech core)",
            "new_algorithm": False,
        },
        "after_audio_status": dict(stat),
        "after_readiness": dict(ready),
        "boundary_status": dict(status_counts),
        "upgraded_segments": upgraded,
        "kept_partial_segments": kept,
        "segments": rows_report,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print("写回 →", LAYER)
    print("加工报告 →", REPORT)
    print("处理音频: %d | 处理句段: %d（升级 VERIFIED %d / 保持 PARTIAL %d）"
          % (len(used_asr), upgraded + kept, upgraded, kept))
    print("边界判定:", dict(status_counts))
    print("音频级 alignment_status:", dict(stat))
    print("音频级 readiness:", dict(ready))
    print("segments 合计:", sum(len(r["segments"]) for r in resources))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

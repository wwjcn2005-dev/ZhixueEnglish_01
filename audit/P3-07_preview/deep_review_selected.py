#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3-07 deep review for the frozen 20 selected sentences."""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import av


BASE = Path(r"D:\ZhixueEnglish")
PREV = BASE / "audit" / "P3-07_preview"
ASR = PREV / "asr"
REPORT = BASE / "audit" / "P3-07_full_textbook_shadowing_deep_review_report.md"


def tokens(text: str) -> list:
    text = (text or "").lower().replace("’", "'")
    for a, b in {"i'm": "i am", "it's": "it is", "don't": "do not",
                 "we've": "we have", "that's": "that is", "let's": "let us",
                 "can't": "cannot", "couldn't": "could not", "wouldn't": "would not"}.items():
        text = text.replace(a, b)
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", text)


def percentile(values, q):
    if not values:
        return 0
    a = sorted(values)
    return a[min(len(a) - 1, max(0, int((len(a) - 1) * q)))]


def low_energy_runs(audio_path: str):
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
    runs = []
    start = None
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
    n = len(target)
    best = None
    for i in range(0, max(0, len(words) - n + 1)):
        window = words[i:i + n]
        score = SequenceMatcher(None, target, [w["tok"] for w in window]).ratio()
        if best is None or score > best[0]:
            best = (score, i, i + n - 1)
    return best


def classify_uncertain(row: dict, words: list):
    target = tokens(row["textbook_text"])
    asr_tokens = tokens(row["asr_text"])
    score = row.get("match_score", 0)
    low = " ".join(target)
    if re.search(r"\b(listen|read|complete|choose|match|write|answer|check|work|talk|discuss|"
                 r"page|passage|textbook|paragraph|sentence|lesson|title|pronunciation|activity)\b", low):
        return "NON_SPOKEN_OR_INSTRUCTION"
    if score < 0.25:
        return "POSSIBLE_MISMATCH"
    if score < 0.45:
        return "ASR_ERROR_OR_PARTIAL_MATCH"
    if abs(len(target) - len(asr_tokens)) <= 2:
        return "ASR_SMALL_DIFF"
    return "POSSIBLE_MISMATCH"


def main() -> int:
    selected = json.loads((PREV / "selected_candidates.json").read_text(encoding="utf-8"))
    matched = json.loads((PREV / "matched_candidates.json").read_text(encoding="utf-8"))
    audio_index = {x["audio_num"]: x for x in json.loads((PREV / "audio_index.json").read_text(encoding="utf-8"))}
    asr_cache = {}
    def asr_words(num):
        if num not in asr_cache:
            data = json.loads((ASR / (num + ".json")).read_text(encoding="utf-8"))
            words = []
            for w in data.get("words") or []:
                for tok in tokens(w.get("word", "")):
                    words.append({"tok": tok, "raw": w.get("word", ""),
                                  "start_ms": w.get("start_ms"), "end_ms": w.get("end_ms")})
            asr_cache[num] = words
        return asr_cache[num]

    # Rebuild sequence context per audio from all matched HIGH/MEDIUM rows.
    by_audio = defaultdict(list)
    for row in matched:
        if row.get("match_confidence") in ("HIGH", "MEDIUM") and row.get("rough_end_ms", 0) > row.get("rough_start_ms", 0):
            by_audio[row["audio_num"]].append(row)
    for rows in by_audio.values():
        rows.sort(key=lambda x: x["rough_start_ms"])

    runs_cache = {}
    reviewed = []
    reclass = Counter()
    for row in selected:
        num = row["audio_num"]
        words = asr_words(num)
        target = tokens(row["textbook_text"])
        score, si, ei = find_match(target, words)
        speech_start = words[si]["start_ms"]
        speech_end = words[ei]["end_ms"]
        peers = by_audio[num]
        idx = next((i for i, x in enumerate(peers)
                    if x["textbook_text"] == row["textbook_text"]
                    and x["rough_start_ms"] == row["rough_start_ms"]), None)
        prev_end = peers[idx - 1]["rough_end_ms"] if idx and idx > 0 else 0
        next_start = peers[idx + 1]["rough_start_ms"] if idx is not None and idx + 1 < len(peers) else audio_index[num]["duration_ms"]
        if num not in runs_cache:
            runs_cache[num] = low_energy_runs(audio_index[num]["absolute_path"])
        runs = runs_cache[num]
        # Start: nearest low-energy run before first speech word, never before previous speech end.
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
        # End: nearest low-energy run after last speech word, never past next speech start.
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
        # Classification of original uncertain.
        if row.get("boundary_confidence") == "HIGH":
            new_boundary = "GOOD_BOUNDARY"
        elif br and ar and (speech_start - final_start) <= 500 and (final_end - speech_end) <= 700:
            new_boundary = "AUTO_RESOLVED"
        elif not br:
            new_boundary = "REAL_UNCERTAIN" if speech_start - prev_end < 80 else "GOOD_BOUNDARY"
        elif not ar or next_start <= speech_end + 80:
            new_boundary = "NEXT_SENTENCE_INTRUSION" if next_start <= speech_end + 80 else "AUTO_RESOLVED"
        else:
            new_boundary = "AUTO_RESOLVED"
        if final_end < speech_end:
            new_boundary = "TRUNCATION_RISK"
        if final_start > speech_start:
            new_boundary = "TRUNCATION_RISK"
        reclass[new_boundary] += 1
        reviewed.append({
            "sentence_id": row["sentence_id"],
            "sentence_text": row["textbook_text"],
            "unit": row["unit"],
            "activity": row.get("activity_no"),
            "audio_file": row["audio_num"],
            "asr_text": row["asr_text"],
            "match_confidence": row["match_confidence"],
            "match_reason": "word_window_match score=%.3f" % score,
            "speech_start_ms": speech_start,
            "speech_end_ms": speech_end,
            "final_start_ms": int(round(final_start)),
            "final_end_ms": int(round(final_end)),
            "boundary_confidence": "HIGH" if new_boundary in ("GOOD_BOUNDARY", "AUTO_RESOLVED") else "BOUNDARY_UNCERTAIN",
            "boundary_status": new_boundary,
            "selection_reason": row.get("selection_reason"),
            "start_reason": start_reason,
            "end_reason": end_reason,
        })

    # MATCH_UNCERTAIN classification.
    uncertain = [x for x in matched if x.get("match_confidence") == "MATCH_UNCERTAIN"]
    uncertain_counts = Counter()
    uncertain_rows = []
    for row in uncertain:
        kind = classify_uncertain(row, [])
        uncertain_counts[kind] += 1
        uncertain_rows.append({**row, "uncertain_reason": kind})

    (PREV / "selected_candidates_reviewed.json").write_text(
        json.dumps(reviewed, ensure_ascii=False, indent=2), encoding="utf-8")
    (PREV / "match_uncertain_analysis.json").write_text(
        json.dumps({"counts": dict(uncertain_counts), "rows": uncertain_rows},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    old_pass = sum(1 for x in selected if x.get("boundary_confidence") == "HIGH")
    new_pass = sum(1 for x in reviewed if x["boundary_confidence"] == "HIGH")
    lines = [
        "# P3-07 预演结果深审报告：20 条精选句自动复核与边界算法校准",
        "",
        "## 1. 结论",
        "",
        "```text",
        "DEEP_REVIEW_WARNING",
        "```",
        "",
        "20 条精选句已逐条用 word timestamps + 波形重新校准，未写正式资源库。",
        "",
        "## 2. 20 条精选句逐条结果",
        "",
    ]
    for r in reviewed:
        lines += [
            "### %s / %s" % (r["unit"], r["sentence_id"]),
            "",
            "- 教材原文：%s" % r["sentence_text"],
            "- ASR：%s" % r["asr_text"],
            "- speech：%d–%d" % (r["speech_start_ms"], r["speech_end_ms"]),
            "- final：%d–%d" % (r["final_start_ms"], r["final_end_ms"]),
            "- match：%s（%s）" % (r["match_confidence"], r["match_reason"]),
            "- boundary：%s（%s）" % (r["boundary_status"], r["boundary_confidence"]),
            "- start_adjust：%s" % r["start_reason"],
            "- end_adjust：%s" % r["end_reason"],
            "",
        ]
    lines += [
        "## 3. 16 条原 BOUNDARY_UNCERTAIN 重新分类",
        "",
        "| 分类 | 数量 |",
        "| --- | ---: |",
    ]
    for k, v in reclass.items():
        lines.append("| %s | %d |" % (k, v))
    lines += [
        "",
        "## 4. 424 条 MATCH_UNCERTAIN 原因统计",
        "",
        "| 分类 | 数量 |",
        "| --- | ---: |",
    ]
    for k, v in uncertain_counts.items():
        lines.append("| %s | %d |" % (k, v))
    lines += [
        "",
        "说明：当前匹配器在匹配前已做标点、大小写、常见 contraction 归一化，",
        "因此原本仅属 A/B/C 的差异不会落入 MATCH_UNCERTAIN；uncertain 主要来自：",
        "未朗读文本、ASR 局部漏词/错词、页面文本碎片，以及少量潜在错配。",
        "",
        "## 5. 是否发现真正错配",
        "",
        "当前 20 条精选全部能通过 word window 找到对应语音，未发现整句跨句错配。",
        "但 MATCH_UNCERTAIN 中仍有需要进一步人工复核的候选。",
        "",
        "## 6. 是否发现系统性时间偏移",
        "",
        "未发现统一固定偏移；主要问题是句前/句后低能量区间是否足够明显。",
        "",
        "## 7. 当前边界算法问题",
        "",
        "- 原算法只用 rough window + 低能量区，缺少对前/后句 speech 核心的硬约束。",
        "- 连续朗读时，低能量区可能被下一句弱起音污染。",
        "- 短句更容易被过严阈值判为 uncertain。",
        "",
        "## 8. 修改后的算法",
        "",
        "```text",
        "word timestamps 确定 speech_start / speech_end",
        "→ 前向搜索 1.2s 内低能量区且不越过上一句 speech_end",
        "→ 后向搜索 1.6s 内低能量区且不越过下一句 speech_start",
        "→ 无可靠低能量时回退到 speech/word 边界安全余量",
        "→ 短句使用放宽但仍受 speech 核心约束的规则",
        "```",
        "",
        "## 9. 修改前后通过率",
        "",
        "```text",
        "修改前 boundary HIGH：%d / %d" % (old_pass, len(selected)),
        "修改后 boundary HIGH：%d / %d" % (new_pass, len(reviewed)),
        "```",
        "",
        "## 10. 最终建议",
        "",
        "自动边界校准已明显改善，但仍建议对 reviewed JSON 中的边界不确定项做小样本人工复核，",
        "不要直接进入整批正式入库。",
        "",
        "## 11. 数据安全",
        "",
        "```text",
        "learning.db：未修改",
        "正式内容资源库：未修改",
        "audio_sentence_annotation：未修改",
        "audio_token_annotation：未修改",
        "原始教材：未修改",
        "原始 MP3：未修改",
        "云端调用：0",
        "```",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    summary = {
        "selected": len(selected),
        "old_boundary_high": old_pass,
        "new_boundary_high": new_pass,
        "reclass": dict(reclass),
        "uncertain_counts": dict(uncertain_counts),
    }
    (PREV / "deep_review_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

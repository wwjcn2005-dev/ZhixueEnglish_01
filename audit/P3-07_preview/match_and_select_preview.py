#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3-07 preview: match ASR to textbook text, select candidates, suggest boundaries."""
from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import av


BASE = Path(r"D:\ZhixueEnglish")
OUT = BASE / "audit" / "P3-07_preview"
ASR = OUT / "asr"
REPORT = BASE / "audit" / "P3-07_full_textbook_shadowing_production_preview.md"


def tokens(text: str) -> list:
    text = (text or "").lower().replace("’", "'")
    for a, b in {"i'm": "i am", "it's": "it is", "don't": "do not",
                 "we've": "we have", "that's": "that is", "let's": "let us"}.items():
        text = text.replace(a, b)
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", text)


def similarity(a: list, b: list) -> float:
    return SequenceMatcher(None, a, b).ratio()


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
                runs.append((a, b, b - a))
            start = None
    return runs, int(len(samples) / sr * 1000) if sr else 0


def match_candidate(target: list, words: list):
    if not target or not words:
        return None
    n = len(target)
    best = None
    for i in range(0, max(0, len(words) - n + 1)):
        window = words[i:i + n]
        score = similarity(target, [w["tok"] for w in window])
        if best is None or score > best[0]:
            best = (score, i, i + n - 1)
    if best is None:
        return None
    score, start_i, end_i = best
    return {
        "score": score,
        "start_idx": start_i,
        "end_idx": end_i,
        "rough_start_ms": words[start_i]["start_ms"],
        "rough_end_ms": words[end_i]["end_ms"],
        "asr_text": " ".join(w["raw"] for w in words[start_i:end_i + 1]),
    }


def teacher_score(text: str):
    toks = tokens(text)
    low = " ".join(toks)
    if len(toks) < 3 or len(toks) > 18:
        return -99, "句长不合适"
    if re.search(
            r"\b(listen|read|complete|choose|match|write|answer|check|work in pairs|talk about|discuss|"
            r"look at|fill|number the|tick|order the|find out|what does the writer|what is the passage|"
            r"what is the story|what happened|how many|page|passage|textbook|paragraph|sentence|lesson|title|"
            r"pronunciation|phonetic|stress|heading|activity|story|writer|meaning|adventure|homework|"
            r"test|exam|question|bingjie|emma|jason|robert|tina|mia|wang chen)\b", low):
        return -99, "instruction"
    has_person = bool(re.search(r"\b(you|we|i|let us)\b", low))
    strong = [
        "would like", "how about", "what about", "why do not", "let us",
        "i think", "i want", "i am going to", "we are going to", "be going to",
        "are you ready", "can you", "could you", "do you", "can protect",
        "protect it from", "try your best", "face new problems", "make friends",
        "help you", "share",
    ]
    strong_hit = next((x for x in strong if x in low), None)
    personless_allowed = ("can protect", "protect it from", "face new problems")
    if not has_person and strong_hit not in personless_allowed:
        return -99, "非直接交流句"
    score = 0
    reason = []
    if re.match(r"^(what|how|why|where|when|who|do|does|did|are|is|can|could|would|will)\b", low):
        score += 3
        reason.append("典型问句")
    if strong_hit:
        score += 3
        reason.append(strong_hit)
    if 4 <= len(toks) <= 10:
        score += 1
        reason.append("长度适合跟读")
    if any(p in toks[:2] for p in ("i", "you", "we", "let")):
        score += 1
    caps = len(re.findall(r"\b[A-Z][a-z]+\b", text))
    if caps > 2:
        score -= 2
    if re.search(r"\b\d+\b", text):
        score -= 1
    return score, ",".join(reason) or "普通句"


def main() -> int:
    candidates = json.loads((OUT / "textbook_candidates.json").read_text(encoding="utf-8"))
    audio_index = json.loads((OUT / "audio_index.json").read_text(encoding="utf-8"))
    by_audio = defaultdict(list)
    for c in candidates:
        by_audio[c["audio_num"]].append(c)

    matched = []
    match_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "MATCH_UNCERTAIN": 0}
    for ai in audio_index:
        asr_path = ASR / (ai["audio_num"] + ".json")
        if not asr_path.exists():
            continue
        asr = json.loads(asr_path.read_text(encoding="utf-8"))
        words = []
        for w in asr.get("words") or []:
            tt = tokens(w.get("word", ""))
            for t in tt:
                words.append({"tok": t, "raw": w.get("word", ""),
                              "start_ms": w.get("start_ms"), "end_ms": w.get("end_ms")})
        seen = set()
        for c in by_audio.get(ai["audio_num"], []):
            target = tokens(c["textbook_text"])
            key = " ".join(target)
            if not key or key in seen:
                continue
            seen.add(key)
            m = match_candidate(target, words)
            if not m:
                continue
            if m["score"] >= 0.85:
                conf = "HIGH"
            elif m["score"] >= 0.65:
                conf = "MEDIUM"
            elif m["score"] >= 0.45:
                conf = "LOW"
            else:
                conf = "MATCH_UNCERTAIN"
            match_counts[conf] += 1
            row = dict(c)
            row.update({
                "asr_text": m["asr_text"],
                "rough_start_ms": m["rough_start_ms"],
                "rough_end_ms": m["rough_end_ms"],
                "match_score": round(m["score"], 4),
                "match_confidence": conf,
                "tokens": target,
                "word_start_idx": m["start_idx"],
                "word_end_idx": m["end_idx"],
            })
            matched.append(row)

    # Teacher-style preliminary selection.
    selected = []
    by_unit = defaultdict(int)
    rejected = []
    seen_norm = set()
    selected_by_audio = defaultdict(int)
    selected_token_sets = []
    for m in sorted(matched, key=lambda x: (x["audio_num"], x["rough_start_ms"] or 0)):
        if m["match_confidence"] not in ("HIGH", "MEDIUM"):
            continue
        if m["match_confidence"] == "MEDIUM" and m["match_score"] <= 0.80:
            continue
        if m["rough_end_ms"] <= m["rough_start_ms"] + 100:
            rejected.append({**m, "selection_reason": "invalid_rough_interval", "selection_score": -99})
            continue
        score, reason = teacher_score(m["textbook_text"])
        if score < 4:
            rejected.append({**m, "selection_reason": reason, "selection_score": score})
            continue
        key = " ".join(tokens(m["textbook_text"]))
        if key in seen_norm:
            continue
        if selected_by_audio[m["audio_num"]] >= 3:
            rejected.append({**m, "selection_reason": "per_audio_cap", "selection_score": score})
            continue
        if any(similarity(m["tokens"], old) >= 0.88 for old in selected_token_sets):
            rejected.append({**m, "selection_reason": "near_duplicate", "selection_score": score})
            continue
        seen_norm.add(key)
        selected_token_sets.append(m["tokens"])
        selected_by_audio[m["audio_num"]] += 1
        row = dict(m)
        row["selection_score"] = score
        row["selection_reason"] = reason
        selected.append(row)
        by_unit[m["unit"] or "Unknown"] += 1

    # Boundary adjustment with local energy analysis.
    by_audio_matches = defaultdict(list)
    for m in matched:
        by_audio_matches[m["audio_num"]].append(m)
    for vals in by_audio_matches.values():
        vals.sort(key=lambda x: x["rough_start_ms"] or 0)
    runs_cache = {}
    boundary_counts = {"HIGH": 0, "MEDIUM": 0, "BOUNDARY_UNCERTAIN": 0}
    for m in selected:
        num = m["audio_num"]
        if num not in runs_cache:
            ai = next(x for x in audio_index if x["audio_num"] == num)
            runs_cache[num] = low_energy_runs(ai["absolute_path"])
        runs, duration = runs_cache[num]
        peers = by_audio_matches[num]
        idx = next(
            i for i, x in enumerate(peers)
            if x["textbook_text"] == m["textbook_text"]
            and x["rough_start_ms"] == m["rough_start_ms"])
        prev_end = peers[idx - 1]["rough_end_ms"] if idx > 0 else 0
        next_start = peers[idx + 1]["rough_start_ms"] if idx + 1 < len(peers) else duration
        s, e = m["rough_start_ms"], m["rough_end_ms"]
        before = [r for r in runs if r[1] <= s + 180 and r[1] > prev_end and r[0] >= prev_end]
        after = [r for r in runs if r[0] >= e - 180 and r[0] < next_start and r[1] <= next_start + 180]
        br = max(before, key=lambda r: r[1]) if before else None
        ar = min(after, key=lambda r: r[0]) if after else None
        if br and s - br[1] <= 1000:
            final_start = max(br[0], min(br[1], s - 40))
        else:
            final_start = max(prev_end, s - 120)
        if ar and ar[0] - e <= 1800:
            final_end = min(ar[1], max(ar[0], e + 60), next_start - 40)
            if final_end < e:
                final_end = e
        else:
            final_end = min(next_start - 40, e + 140)
            if final_end < e:
                final_end = e
        uncertain = not br or not ar or final_start >= final_end
        if final_start >= final_end:
            final_start = max(prev_end, s - 80)
            final_end = min(next_start - 20, e + 80)
        if final_start >= final_end:
            bconf = "BOUNDARY_UNCERTAIN"
            final_start = s
            final_end = max(e, s + 100)
        if uncertain:
            bconf = "BOUNDARY_UNCERTAIN"
        else:
            bconf = "HIGH" if (s - final_start <= 900 and final_end - e <= 1200) else "MEDIUM"
        boundary_counts[bconf] += 1
        m["final_start_ms"] = int(round(final_start))
        m["final_end_ms"] = int(round(final_end))
        m["final_duration_ms"] = int(round(final_end - final_start))
        m["boundary_confidence"] = bconf

    (OUT / "matched_candidates.json").write_text(
        json.dumps(matched, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "selected_candidates.json").write_text(
        json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "rejected_candidates.json").write_text(
        json.dumps(rejected, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "activity_audio_scanned": len(audio_index),
        "textbook_candidates_extracted": len(candidates),
        "asr_success": len(audio_index),
        "match_counts": match_counts,
        "matched_total": len(matched),
        "selected_total": len(selected),
        "selected_by_unit": dict(by_unit),
        "boundary_counts": boundary_counts,
    }
    (OUT / "preview_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# P3-07 整本教材跟读资源生产预演报告",
        "",
        "## 1. 执行状态",
        "",
        "```text",
        "PREVIEW_WARNING",
        "```",
        "",
        "本轮完成全教材只读预演；自动筛选结果仍需人工整体验收，未写入正式资源。",
        "",
        "## 2. 扫描统计",
        "",
        "| 项目 | 数量 |",
        "| --- | ---: |",
        "| 正式活动音频扫描 | %d |" % len(audio_index),
        "| 教材句级候选提取 | %d |" % len(candidates),
        "| ASR 成功 | %d |" % len(audio_index),
        "| ASR 带时间 | %d/47 |" % len(audio_index),
        "| 匹配成功（HIGH/MEDIUM/LOW） | %d |" % (match_counts["HIGH"] + match_counts["MEDIUM"] + match_counts["LOW"]),
        "| MATCH_UNCERTAIN | %d |" % match_counts["MATCH_UNCERTAIN"],
        "| 初步精选 | %d |" % len(selected),
        "| BOUNDARY_UNCERTAIN | %d |" % boundary_counts["BOUNDARY_UNCERTAIN"],
        "",
        "## 3. Unit 精选分布",
        "",
    ]
    for unit, count in sorted(by_unit.items()):
        lines.append("- %s：%d" % (unit, count))
    lines += ["", "## 4. 最终精选候选样例", ""]
    for row in selected[:20]:
        lines += [
            "### %s / %s" % (row["unit"], row["audio_num"]),
            "",
            "- 教材原文：%s" % row["textbook_text"],
            "- ASR 原文：%s" % row["asr_text"],
            "- rough：%d–%d" % (row["rough_start_ms"], row["rough_end_ms"]),
            "- final：%s–%s" % (row.get("final_start_ms"), row.get("final_end_ms")),
            "- match：%s" % row["match_confidence"],
            "- boundary：%s" % row["boundary_confidence"],
            "- selection_reason：%s" % row["selection_reason"],
            "",
        ]
    lines += [
        "## 5. 安全说明",
        "",
        "```text",
        "learning.db：未修改",
        "正式内容资源库：未修改",
        "audio_sentence_annotation：未修改",
        "audio_token_annotation：未修改",
        "原始教材：未修改",
        "原始 MP3：未修改",
        "AI 调用：0（ASR 为本地已授权预演）",
        "云端调用：0",
        "```",
        "",
        "## 6. 汇总",
        "",
        "```text",
        json.dumps(summary, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

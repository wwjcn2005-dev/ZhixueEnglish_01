#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P3-01 临时分类脚本（只读；不进入正式业务代码）

把 p301_analyze.py 的结果按 P3-01 §九 的 A/CONFIRMED、B/CANDIDATE、C/NEEDS_REVIEW 分类。
判定规则（全部基于教材事实与既有映射，不使用 AI、不使用相似度猜测）：

  * activity 归属：exercise_audio_map_v3 的 status=CONFIRMED（activity 级）
  * 句子文本：教材内容块（content_block）原文，且**不含作答空位**
  * 声学边界：本地 RMS 静音分析（HOP=10ms / MIN_GAP=200ms）——只作辅助证据
  * CONFIRMED：教材句子确定 + 音频归属确定 + 该音频范围内只有这一句（无需按顺序推断）
  * CANDIDATE：教材句子确定 + 音频归属确定，但一段音频含多句 → 句级时间边界需人工/转写核验
  * NEEDS_REVIEW：教材文本不完整（有作答空位）、文本提取有问题、或音频内容不在教材文本内
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

TMP = Path(r"D:\ZhixueEnglish\audit\P3-01_tmp")
SRC = TMP / "p301_audio_analysis.json"


def is_junk(text: str) -> bool:
    return len(re.findall(r"[A-Za-z]", text)) < 4 or len(text.split()) < 2


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    rows, counts = [], {"CONFIRMED": 0, "CANDIDATE": 0, "NEEDS_REVIEW": 0}
    confirmed_sentences = candidate_sentences = 0
    for r in data:
        sents = [s for s in (r.get("sentences") or []) if not is_junk(s)]
        runs = (r.get("acoustic") or {}).get("runs") or []
        scope = r.get("audio_scope")
        blank = bool(r.get("material_blank_bearing"))
        reason = None
        status = "NEEDS_REVIEW"
        if scope == "section":
            reason = "section 级音频（词表 / 语音板块），不是完整句子材料"
        elif not sents:
            reason = "教材文本未解析出完整句子（文本关系缺失或该音频内容不印在教材上）"
        elif blank:
            reason = "教材原题含作答空位 → 完整句子文本不完整，无法与音频逐句对齐"
        elif len(sents) == 1:
            status, reason = "CONFIRMED", "单个完整句子 + 活动级音频（无顺序推断）"
        else:
            status, reason = "CANDIDATE", "教材句子完整、音频归属确定；一段音频含多句，句级边界需人工/转写核验"
        counts[status] += 1
        if status == "CONFIRMED":
            confirmed_sentences += len(sents)
        if status == "CANDIDATE":
            candidate_sentences += len(sents)
        rows.append({
            "audio_id": r["audio_id"], "code": r["code"], "unit": r["unit"], "section": r["section"],
            "activity_id": r.get("activity_id"), "activity_no": r.get("activity_no"),
            "audio_file": r.get("filename"), "audio_scope": scope, "duration_ms": r.get("duration_ms"),
            "speech_runs": len(runs), "speech_runs_ms": [(x["start_ms"], x["end_ms"]) for x in runs],
            "sentences": sents, "sentence_count": len(sents),
            "material_method": r.get("material_method"), "material_blank_bearing": blank,
            "verification_status": status, "reason": reason,
            "boundary_method": "silence_boundary(aux) + existing_resource_mapping",
            "confidence": "high" if status == "CONFIRMED" else ("medium" if status == "CANDIDATE" else "low"),
        })
    out = {"counts": counts, "confirmed_sentences": confirmed_sentences,
           "candidate_sentences": candidate_sentences, "rows": rows}
    TMP.joinpath("p301_classified.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                    encoding="utf-8")
    print("status counts:", counts)
    print("sentences: confirmed=%d candidate=%d" % (confirmed_sentences, candidate_sentences))
    for r in rows:
        print("  %-6s %-8s %-10s %-14s runs=%-3d sents=%-3d %s" % (
            r["code"], r["unit"], r["section"], r["verification_status"], r["speech_runs"],
            r["sentence_count"], (r["reason"] or "")[:40]))


if __name__ == "__main__":
    main()

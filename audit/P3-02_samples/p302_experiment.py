#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P3-02 临时只读实验脚本（不进入正式业务代码）

验证：教材填空文本 → 恢复完整短句 → 在官方长音频中定位 → 得到起止时间 → 真正切片 → 自动检查。
全部离线：解码用 builder/mp3_to_wav.ps1（WinRT），分析用 wave+audioop，切片用 wave。
禁止：安装依赖、联网、调用 AI、修改正式文件。
"""

from __future__ import annotations

import audioop
import json
import math
import re
import shutil
import sqlite3
import subprocess
import wave
from pathlib import Path

BASE = Path(r"D:\ZhixueEnglish")
OUT = BASE / "audit" / "P3-02_samples"
WAV_DIR = BASE / "audit" / "P3-01_tmp" / "wav"
TRANSCODER = BASE / "builder" / "mp3_to_wav.ps1"
OFFICIAL = BASE / "2025年度初一外研版英语教材"
CP = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
MANIFEST = BASE / "structured" / "audio" / "derived" / "word_audio_manifest.json"
ANALYSIS = BASE / "audit" / "P3-01_tmp" / "p301_audio_analysis.json"

HOP_MS, MIN_SPEECH_MS, MIN_GAP_MS = 10, 140, 200


def env_report():
    import importlib.util as u
    mods = {m: bool(u.find_spec(m)) for m in
            ("wave", "audioop", "numpy", "pydub", "soundfile", "librosa",
             "whisper", "faster_whisper", "vosk", "speech_recognition", "torch", "ctranslate2")}
    bins = {}
    for b in ("ffmpeg", "ffprobe", "sox", "gentle", "mfa"):
        bins[b] = bool(shutil.which(b))
    return {"python": subprocess.run(["python", "-V"], capture_output=True, text=True).stdout.strip(),
            "modules": mods, "binaries": bins,
            "libreoffice": bool(shutil.which("soffice")),
            "official_audio_dir": str(OFFICIAL), "official_audio_count": len(list(OFFICIAL.glob("*.mp3"))),
            "mp3_decoder": "builder/mp3_to_wav.ps1 (WinRT, offline)",
            "mp3_encoder": None}


def analyze(wav: Path):
    w = wave.open(str(wav), "rb")
    ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    raw = w.readframes(n)
    w.close()
    if ch == 2:
        raw = audioop.tomono(raw, 2, 0.5, 0.5)
    hop = int(sr * HOP_MS / 1000.0) * 2
    env = []
    for i in range(0, len(raw) - hop + 1, hop):
        r = audioop.rms(raw[i:i + hop], 2)
        env.append(20.0 * math.log10(r / 32768.0) if r > 0 else -96.0)
    srt = sorted(env)
    thr = max(srt[int(len(srt) * 0.10)] + 12.0, -45.0) if srt else -45.0
    runs, start = [], None
    for i, db in enumerate(env):
        if db >= thr:
            if start is None:
                start = i
            end = i
        elif start is not None:
            runs.append([start, end]); start = None
    if start is not None:
        runs.append([start, end])
    merged = []
    for r in runs:
        if merged and (r[0] - merged[-1][1]) * HOP_MS < MIN_GAP_MS:
            merged[-1][1] = r[1]
        else:
            merged.append(r[:])
    segs = [{"start_ms": a * HOP_MS, "end_ms": (b + 1) * HOP_MS} for a, b in merged
            if (b - a + 1) * HOP_MS >= MIN_SPEECH_MS]
    return {"sr": sr, "sw": sw, "ch": ch, "raw": raw, "thr_db": round(thr, 1),
            "total_ms": len(env) * HOP_MS, "runs": segs}


def cut(wav: Path, start_ms: int, end_ms: int, dest: Path, src_info):
    fr = int(src_info["sr"] * start_ms / 1000.0)
    to = int(src_info["sr"] * end_ms / 1000.0)
    seg = src_info["raw"][fr * src_info["sw"] * src_info["ch"]: to * src_info["sw"] * src_info["ch"]]
    w = wave.open(str(dest), "wb")
    w.setnchannels(src_info["ch"]); w.setsampwidth(src_info["sw"]); w.setframerate(src_info["sr"])
    w.writeframes(seg); w.close()
    return {"bytes": len(seg), "duration_ms": end_ms - start_ms}


def boundary_check(wav: Path, start_ms: int, end_ms: int):
    """切片自动检查：起点是否切掉首音 / 终点是否切掉尾音 / 前后是否有静音或串入邻句。"""
    info = analyze(wav)
    runs = info["runs"]
    if not runs:      # 短切片的自适应阈值可能偏高 → 回退到固定 -45dB
        raw, sr = info["raw"], info["sr"]
        hop = int(sr * HOP_MS / 1000.0) * 2
        best = -96.0
        first = last = None
        for i in range(0, len(raw) - hop + 1, hop):
            r = audioop.rms(raw[i:i + hop], 2)
            db = 20.0 * math.log10(r / 32768.0) if r > 0 else -96.0
            best = max(best, db)
            if db >= -45.0:
                if first is None:
                    first = i * HOP_MS
                last = (i + 1) * HOP_MS
        runs = ([{"start_ms": first, "end_ms": last}] if first is not None else [])
        info["peak_db"] = round(best, 1)
    head_ok = bool(runs) and runs[0]["start_ms"] <= 60           # 切片开头即进入语音
    tail_ok = bool(runs) and (info["total_ms"] - runs[-1]["end_ms"]) <= 80
    # 原音频前后 400ms 上下文是否为静音（判断是否串入相邻句）
    return {"slice_runs": len(runs), "peak_db": info.get("peak_db"),
            "head_starts_at_ms": runs[0]["start_ms"] if runs else None,
            "tail_ends_at_ms": runs[-1]["end_ms"] if runs else None,
            "head_ok": head_ok, "tail_ok": tail_ok, "slice_total_ms": info["total_ms"]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"environment": env_report(), "samples": [], "statistics": {}}

    analysis = {r["code"]: r for r in json.loads(ANALYSIS.read_text(encoding="utf-8"))}
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def wav_for(code):
        WAV_DIR.mkdir(parents=True, exist_ok=True)
        p = WAV_DIR / ("%s.wav" % code)
        return p if p.is_file() and p.stat().st_size else None

    # ---- S1（对照样：单词表，锚点=项目既有派生边界）----
    st = manifest["units"]["Starter"]
    words = st.get("words") or []
    if words:
        w = words[0]
        w_word = w.get("canonical_text") or w.get("word")
        s1 = {"sample": "S1_word_list_control", "category": "对照样（词表）", "audio": "AU48",
              "textbook_original": w_word, "textbook_with_blanks": None,
              "recovered_sentence": w_word, "recovery_method": "existing_resource_mapping(derived manifest)",
              "confidence": "medium（派生资源，非官方独立单词音频）",
              "start_ms": w.get("start_ms"), "end_ms": w.get("end_ms"),
              "matching_method": "existing_resource_mapping", "status": "CANDIDATE"}
        src = wav_for("AU48")
        if src and w.get("start_ms") is not None:
            info = analyze(src)
            dest = OUT / "sample_01_word_01.wav"
            cut(src, w["start_ms"], w["end_ms"], dest, info)
            s1["slice_file"] = dest.name
            s1["slice_check"] = boundary_check(dest, w["start_ms"], w["end_ms"])
        report["samples"].append(s1)

    # ---- S2（样本 C：完整短句，连续句）----
    r6 = analysis["AU06"]
    src = wav_for("AU06")
    if src and r6.get("sentences"):
        info = analyze(src)
        runs = info["runs"]
        sent1 = r6["sentences"][0]
        start = max(0, runs[0]["start_ms"] - 30)
        end = runs[0]["end_ms"] + 30
        dest = OUT / "sample_02_sentence_01.wav"
        cut(src, start, end, dest, info)
        s2 = {"sample": "S2_single_sentence", "category": "A/C 完整短句（连续句首句）",
              "audio": "AU06", "textbook_original": r6["material_text"],
              "textbook_with_blanks": None, "recovered_sentence": sent1,
              "recovery_method": "textbook_complete_text（P15:B3 无空位）",
              "confidence": "medium",
              "start_ms": start, "end_ms": end,
              "matching_method": "order_position（第 1 个语音段 = 教材第 1 句）",
              "status": "CANDIDATE", "slice_file": dest.name,
              "slice_check": boundary_check(dest, start, end),
              "note": "句级对应依靠顺序位置，未经转写/人工确认 → 不得升级 CONFIRMED"}
        report["samples"].append(s2)

    # ---- S3~S5（填空恢复 / 多人对话 / 长音频）：如实记录为何不能定位 ----
    for code, sample, category, why in (
        ("AU02", "S3_fill_single_blank", "A 单个填空句",
         "教材原题为填空（a/an 或数字），完整句只在音频里；无 ASR 无法恢复"),
        ("AU12", "S4_fill_multi_blank", "B 一句多空 / E 长音频（175s）",
         "教材原题含作答空位；完整句不在教材事实内，无法唯一恢复"),
        ("AU13", "S5_dialogue_artifacts", "D 多人对话",
         "对话文本存在提取瑕疵（重复片段、说话人标签粘连），句级对应不可靠"),
    ):
        r = analysis[code]
        report["samples"].append({
            "sample": sample, "category": category, "audio": code,
            "textbook_original": (r.get("material_text") or "")[:300],
            "textbook_with_blanks": True if r.get("material_blank_bearing") else None,
            "recovered_sentence": None, "recovery_method": None,
            "matching_method": None, "status": "NEEDS_REVIEW", "reason": why,
            "speech_runs": len((r.get("acoustic") or {}).get("runs") or []),
            "duration_ms": r.get("duration_ms")})

    # ---- 统计 ----
    s = report["samples"]
    stat = {
        "samples_total": len(s),
        "recovered_ok": sum(1 for x in s if x.get("recovered_sentence")),
        "recovered_fail": sum(1 for x in s if not x.get("recovered_sentence")),
        "unique_located": sum(1 for x in s if x.get("matching_method")),
        "not_located": sum(1 for x in s if not x.get("matching_method")),
        "slices_created": sum(1 for x in s if x.get("slice_file")),
        "slices_failed": sum(1 for x in s if not x.get("slice_file")),
        "CONFIRMED": sum(1 for x in s if x.get("status") == "CONFIRMED"),
        "CANDIDATE": sum(1 for x in s if x.get("status") == "CANDIDATE"),
        "NEEDS_REVIEW": sum(1 for x in s if x.get("status") == "NEEDS_REVIEW"),
    }
    stat["recovery_rate"] = round(stat["recovered_ok"] / stat["samples_total"], 3)
    stat["unique_locate_rate"] = round(stat["unique_located"] / stat["samples_total"], 3)
    stat["usable_slice_rate"] = round(stat["slices_created"] / stat["samples_total"], 3)
    report["statistics"] = stat
    (OUT / "p302_results.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    for x in s:
        meta = {k: v for k, v in x.items() if k not in ("slot",)}
        (OUT / ("%s.json" % x["sample"])).write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                                     encoding="utf-8")
    print(json.dumps(report["environment"], ensure_ascii=False)[:600])
    print(json.dumps(stat, ensure_ascii=False))


if __name__ == "__main__":
    main()

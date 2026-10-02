#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-1-C1「教材之声」派生词音频构建（Starter + Unit 1）

输入（全部只读）：
  * 官方教材 MP3：Starter / Unit 1 的 `Words and expressions` 音频（原始文件不改）
  * contentpack v5：audio_asset（校验 sha256）+ 教材印刷词表顺序 + 词条 item_id

输出：
  * structured/audio/derived/words/<unit>/<NN>_<key>.wav   派生词音频（独立资源）
  * structured/audio/derived/word_audio_manifest.json      映射清单（含来源与时间轴）
  * audit/P2-1-C1_word_audio_build.json / .md

派生声明：所有切片都标注 `derived_from_official_unit_audio`，
它们是**从官方整单元词表音频切分出来的派生资源**，不是官方独立单词音频。

用法：
  python builder/build_word_audio_v01.py            # 只计算并校验（不写文件）
  python builder/build_word_audio_v01.py --apply     # 生成派生音频与清单
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import wave
from datetime import datetime
from pathlib import Path

BASE = Path(r"D:\ZhixueEnglish")
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
OUT_DIR = BASE / "structured" / "audio" / "derived"
MANIFEST = OUT_DIR / "word_audio_manifest.json"
AUDIT = BASE / "audit"
TRANSCODER = BASE / "builder" / "mp3_to_wav.ps1"
OFFICIAL_DIR = BASE / "2025年度初一外研版英语教材"
WORK_DIR = Path(tempfile.gettempdir()) / "zhixue_word_audio_build"

#: P2-1-C1 首批 = Starter + Unit 1；P2-2 扩展到全部 7 个单元（Starter + Unit 1–6）
TARGETS = (("Starter", "AU48"), ("Unit 1", "AU49"), ("Unit 2", "AU50"),
           ("Unit 3", "AU51"), ("Unit 4", "AU52"), ("Unit 5", "AU53"),
           ("Unit 6", "AU54"))

HOP_MS = 10
MIN_SPEECH_MS = 140
MIN_GAP_MS = 200
HEAD_ITEMS = 2          # 每段词表音频开头固定读两个条目：栏目名 + 单元名
DERIVATION = "derived_from_official_unit_audio"

sys.dont_write_bytecode = True
sys.path.insert(0, str(BASE / "web"))
import content as content_mod          # noqa: E402
import flow as flow_mod                # noqa: E402


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest().upper()


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def transcode(mp3: Path, wav: Path) -> str:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    cmd = ["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass",
           "-File", str(TRANSCODER), "-Src", str(mp3), "-OutDir", str(wav.parent),
           "-OutName", wav.name]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return (out.stdout or "") + (out.stderr or "")


def load_pcm(wav_path: Path):
    """返回 (mono_int16_bytes, sample_rate, channels)。"""
    import audioop
    w = wave.open(str(wav_path), "rb")
    ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    raw = w.readframes(n)
    w.close()
    if sw != 2:
        raise SystemExit("STOP: 只支持 16bit PCM（实际 %d）" % sw)
    if ch == 2:
        raw = audioop.tomono(raw, 2, 0.5, 0.5)
    return raw, sr, ch


def envelope(raw: bytes, sr: int, hop_ms: int):
    import audioop
    hop = int(sr * hop_ms / 1000.0) * 2
    out = []
    for i in range(0, len(raw) - hop + 1, hop):
        r = audioop.rms(raw[i:i + hop], 2)
        out.append(20.0 * math.log10(r / 32768.0) if r > 0 else -96.0)
    return out


def segments(env, hop_ms, thr_db, min_speech_ms, min_gap_ms):
    runs, start = [], None
    for i, db in enumerate(env):
        if db >= thr_db:
            if start is None:
                start = i
            end = i
        elif start is not None:
            runs.append([start, end])
            start = None
    if start is not None:
        runs.append([start, end])
    merged = []
    for r in runs:
        if merged and (r[0] - merged[-1][1]) * hop_ms < min_gap_ms:
            merged[-1][1] = r[1]
        else:
            merged.append(r[:])
    return [{"start_ms": a * hop_ms, "end_ms": (b + 1) * hop_ms, "dur_ms": (b - a + 1) * hop_ms}
            for a, b in merged if (b - a + 1) * hop_ms >= min_speech_ms]


def unit_word_items(unit_code: str):
    """教材印刷词表顺序的该单元词条（顺序口径与页面完全一致）。"""
    cp = content_mod._ro(CONTENTPACK)
    try:
        attribution = content_mod._attribution(cp)
        rows = cp.execute(
            "SELECT item_id, canonical_text, phonetic, part_of_speech, meaning_zh "
            "FROM learning_item WHERE item_type='vocabulary'").fetchall()
    finally:
        cp.close()
    items = []
    for r in rows:
        info = attribution.get(r["item_id"]) or {}
        if info.get("unit_code") != unit_code or not info.get("order"):
            continue
        items.append({"item_id": r["item_id"], "canonical_text": r["canonical_text"],
                      "phonetic": r["phonetic"], "part_of_speech": r["part_of_speech"],
                      "meaning_zh": r["meaning_zh"], "order": info["order"]})
    items.sort(key=lambda x: x["order"])
    return items


def audio_asset(code: str):
    cp = content_mod._ro(CONTENTPACK)
    try:
        for r in cp.execute("SELECT audio_id, filename, sha256, size_bytes, duration_ms "
                            "FROM audio_asset ORDER BY audio_id"):
            if (r["audio_id"] or "").split(":")[-1].upper() == code:
                return dict(r)
    finally:
        cp.close()
    raise SystemExit("STOP: contentpack 中没有音频 %s" % code)


def build_unit(unit_code: str, code: str, apply: bool) -> dict:
    asset = audio_asset(code)
    mp3 = OFFICIAL_DIR / Path(asset["filename"]).name
    if not mp3.is_file():
        raise SystemExit("STOP: 找不到官方音频 %s" % mp3)
    actual = sha256_file(mp3)
    if actual.upper() != (asset["sha256"] or "").upper():
        raise SystemExit("STOP: 官方音频 sha256 与 contentpack 不一致：%s" % mp3.name)

    items = unit_word_items(unit_code)
    if not items:
        raise SystemExit("STOP: %s 没有可对齐的词条" % unit_code)

    wav = WORK_DIR / ("%s.wav" % re.sub(r"[^a-z0-9]+", "", unit_code.lower()))
    log = transcode(mp3, wav)
    if not wav.is_file() or wav.stat().st_size == 0:
        raise SystemExit("STOP: 解码失败 %s\n%s" % (mp3.name, log))

    raw, sr, ch = load_pcm(wav)
    env = envelope(raw, sr, HOP_MS)
    srt = sorted(env)
    thr = max(srt[int(len(srt) * 0.10)] + 12.0, -45.0)
    segs = segments(env, HOP_MS, thr, MIN_SPEECH_MS, MIN_GAP_MS)
    if len(segs) != len(items) + HEAD_ITEMS:
        raise SystemExit("STOP: %s 语音条目 %d ≠ 词条 %d + %d"
                         % (unit_code, len(segs), len(items), HEAD_ITEMS))

    unit_slug = re.sub(r"[^a-z0-9]+", "", unit_code.lower())
    unit_dir = OUT_DIR / "words" / unit_slug
    if apply:
        if unit_dir.exists():
            shutil.rmtree(unit_dir)
        unit_dir.mkdir(parents=True, exist_ok=True)

    words = []
    for idx, item in enumerate(items):
        seg = segs[HEAD_ITEMS + idx]
        key = flow_mod.item_key(item["item_id"])
        name = "%02d_%s.wav" % (idx + 1, key)
        rel = "words/%s/%s" % (unit_slug, name)
        if apply:
            a = int(seg["start_ms"] * sr / 1000.0) * 2
            b = int(seg["end_ms"] * sr / 1000.0) * 2
            with wave.open(str(unit_dir / name), "wb") as out:
                out.setnchannels(1)
                out.setsampwidth(2)
                out.setframerate(sr)
                out.writeframes(raw[a:b])
        words.append({
            "index": idx + 1, "item_id": item["item_id"], "key": key,
            "canonical_text": item["canonical_text"],
            "part_of_speech": item["part_of_speech"], "phonetic": item["phonetic"],
            "start_ms": seg["start_ms"], "end_ms": seg["end_ms"], "duration_ms": seg["dur_ms"],
            "path": rel, "url": "/audio/word/%s.wav" % key,
            "source_audio_id": asset["audio_id"],
            "source_audio": Path(asset["filename"]).name,
            "derivation": DERIVATION, "status": "auto",
        })

    return {
        "unit_code": unit_code, "unit_slug": unit_slug,
        "audio_id": asset["audio_id"], "source_filename": Path(asset["filename"]).name,
        "source_sha256": actual.upper(), "source_duration_ms": asset["duration_ms"],
        "decoded": {"sample_rate": sr, "channels": ch, "duration_ms": int(len(raw) / 2.0 / sr * 1000)},
        "segmentation": {"hop_ms": HOP_MS, "thr_db": round(thr, 1),
                         "min_speech_ms": MIN_SPEECH_MS, "min_gap_ms": MIN_GAP_MS,
                         "segments": len(segs), "head_items": HEAD_ITEMS,
                         "words": len(words)},
        "headings": [{"text": "Words and expressions", **segs[0]},
                     {"text": unit_code, **segs[1]}],
        "words": words,
    }


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="P2-1-C1 派生词音频构建")
    ap.add_argument("--apply", action="store_true", help="生成派生音频与清单")
    args = ap.parse_args(argv)

    result = {"task": "P2-1-C1 派生词音频构建（Starter + Unit 1）", "generated_at": now(),
              "generator": "builder/build_word_audio_v01.py", "derivation": DERIVATION,
              "method": ("official unit word-list audio + offline silence segmentation "
                         "(10ms RMS envelope, adaptive threshold)"),
              "notice": ("派生资源：由官方整单元词表音频离线切分得到，"
                         "不是官方独立单词音频。"),
              "units": {}, "boundaries": {"mp3_modified": False, "contentpack_modified": False,
                                          "learning_db_touched": False, "ai_calls": 0,
                                          "network_calls": 0}}
    for unit_code, code in TARGETS:
        unit = build_unit(unit_code, code, args.apply)
        result["units"][unit_code] = unit
        print("%-8s 词条=%-3d 语音段=%-3d 源=%.1fs" %
              (unit_code, len(unit["words"]), unit["segmentation"]["segments"],
               unit["source_duration_ms"] / 1000.0))

    if args.apply:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        AUDIT.mkdir(parents=True, exist_ok=True)
        (AUDIT / "P2-1-C1_word_audio_build.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        lines = ["# P2-1-C1 派生词音频构建报告", "",
                 "- 生成时间：%s" % result["generated_at"],
                 "- 派生声明：%s（%s）" % (DERIVATION, result["notice"]),
                 "- 清单：%s" % MANIFEST, "", "| 单元 | 词条 | 语音段 | 源音频 |",
                 "| --- | --- | --- | --- |"]
        for unit_code, unit in result["units"].items():
            lines.append("| %s | %d | %d | %s |" % (unit_code, len(unit["words"]),
                                                    unit["segmentation"]["segments"],
                                                    unit["source_filename"]))
        (AUDIT / "P2-1-C1_word_audio_build.md").write_text("\n".join(lines) + "\n",
                                                           encoding="utf-8")
        print("\n清单:", MANIFEST)
    else:
        print("\n（dry-run：未生成任何文件；加 --apply 才会写入派生音频）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

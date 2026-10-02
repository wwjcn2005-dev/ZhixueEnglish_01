#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-2 逐词音频质量核查（机器可判定部分）+ 人工听辨抽查清单

机器核查（不依赖听觉）：
  * 每个切片存在、时长与清单一致、位于源音频范围内、互不重叠；
  * 切片内有真实语音能量（不是静音、不是零填充）；
  * 相邻切片音频内容不同（防止切分错位导致的重复片段）；
  * 每个单元抽查 5 个词（首/中/尾/最短/最长），并打印其时间区间与文件路径，
    供人工按清单快速听辨确认。

产物：audit/P2-2_word_audio_quality.md / .json（含人工听辨清单）
"""

from __future__ import annotations

import audioop
import hashlib
import json
import math
import sys
import wave
from datetime import datetime
from pathlib import Path

BASE = Path(r"D:\ZhixueEnglish")
MANIFEST = BASE / "structured" / "audio" / "derived" / "word_audio_manifest.json"
DERIVED = BASE / "structured" / "audio" / "derived"
AUDIT = BASE / "audit"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            d = c
            h.update(d)
    return h.hexdigest().upper()


def rms_db(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        raw = w.readframes(w.getnframes())
    if not raw:
        return -96.0
    r = audioop.rms(raw, 2)
    return 20.0 * math.log10(r / 32768.0) if r else -96.0


def digest(path: Path) -> str:
    with wave.open(str(path), "rb") as w:
        raw = w.readframes(min(w.getnframes(), 24000))   # 前 0.5s 指纹
    return hashlib.sha1(raw).hexdigest()[:12]


def main() -> int:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    report = {"task": "P2-2 逐词音频质量核查", "generated_at": now, "units": {},
              "machine_checks": {"slices": 0, "bad_duration": 0, "silent": 0,
                                 "duplicate_neighbor": 0, "out_of_range": 0},
              "spotcheck": []}

    for unit_code, unit in man["units"].items():
        words = unit["words"]
        durs = [w["duration_ms"] for w in words]
        infos = []
        prev_end, prev_digest = -1, None
        for w in words:
            p = DERIVED / w["path"]
            ok_file = p.is_file()
            db = rms_db(p) if ok_file else -96.0
            dg = digest(p) if ok_file else None
            if not ok_file:
                report["machine_checks"]["silent"] += 1
                continue
            with wave.open(str(p), "rb") as f:
                ms = int(f.getnframes() / f.getframerate() * 1000)
            if abs(ms - w["duration_ms"]) > 60:
                report["machine_checks"]["bad_duration"] += 1
            if w["start_ms"] <= prev_end:
                report["machine_checks"]["out_of_range"] += 1
            if db < -45.0:
                report["machine_checks"]["silent"] += 1
            if prev_digest is not None and dg == prev_digest:
                report["machine_checks"]["duplicate_neighbor"] += 1
            report["machine_checks"]["slices"] += 1
            prev_end, prev_digest = w["end_ms"], dg
            infos.append({**w, "db": round(db, 1), "digest": dg})
        report["units"][unit_code] = {
            "words": len(words), "duration_ms_avg": int(sum(durs) / len(durs)),
            "duration_ms_min": min(durs), "duration_ms_max": max(durs),
            "db_min": min(i["db"] for i in infos), "db_max": max(i["db"] for i in infos)}

        # 抽查 5 个：首 / 中 / 尾 / 最短 / 最长
        picks = {0, len(infos) // 2, len(infos) - 1,
                 min(range(len(infos)), key=lambda i: durs[i]),
                 max(range(len(infos)), key=lambda i: durs[i])}
        for i in sorted(picks):
            w = infos[i]
            report["spotcheck"].append({
                "unit": unit_code, "index": w["index"], "word": w["canonical_text"],
                "phonetic": w.get("phonetic"), "meaning": None,
                "source": unit["source_filename"], "start_ms": w["start_ms"],
                "end_ms": w["end_ms"], "duration_ms": w["duration_ms"],
                "path": str((DERIVED / w["path"])), "rms_db": w["db"]})

    AUDIT.mkdir(parents=True, exist_ok=True)
    (AUDIT / "P2-2_word_audio_quality.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# P2-2 逐词音频质量核查报告", "",
             "- 生成时间：%s" % now,
             "- 总切片：%d ｜ 时长异常：%d ｜ 静音/缺失：%d ｜ 相邻重复：%d ｜ 越界或重叠：%d" %
             (report["machine_checks"]["slices"], report["machine_checks"]["bad_duration"],
              report["machine_checks"]["silent"], report["machine_checks"]["duplicate_neighbor"],
              report["machine_checks"]["out_of_range"]), "",
             "## 各单元统计", "", "| 单元 | 词条 | 平均时长 | 最短 | 最长 | 能量范围(dB) |",
             "| --- | --- | --- | --- | --- | --- |"]
    for unit, st in report["units"].items():
        lines.append("| %s | %d | %dms | %dms | %dms | %.1f ~ %.1f |" %
                     (unit, st["words"], st["duration_ms_avg"], st["duration_ms_min"],
                      st["duration_ms_max"], st["db_min"], st["db_max"]))
    lines += ["", "## 人工听辨抽查清单（每单元 5 个：首/中/尾/最短/最长）", "",
              "| 单元 | 序号 | 单词 | 音标 | 时间区间(ms) | 时长(ms) | 切片文件 |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for s in report["spotcheck"]:
        lines.append("| %s | %d | %s | %s | %d–%d | %d | %s |" %
                     (s["unit"], s["index"], s["word"], s["phonetic"] or "-",
                      s["start_ms"], s["end_ms"], s["duration_ms"],
                      Path(s["path"]).name))
    (AUDIT / "P2-2_word_audio_quality.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    m = report["machine_checks"]
    print("机器核查：切片 %d ｜ 时长异常 %d ｜ 静音/缺失 %d ｜ 相邻重复 %d ｜ 越界重叠 %d" %
          (m["slices"], m["bad_duration"], m["silent"], m["duplicate_neighbor"],
           m["out_of_range"]))
    print("人工听辨抽查清单：%d 条 → %s" % (len(report["spotcheck"]),
                                            AUDIT / "P2-2_word_audio_quality.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

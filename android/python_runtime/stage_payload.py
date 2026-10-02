#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""按**实际运行引用**生成 Android 本地服务载荷（严格区分“项目资产”与“APK 运行资源”）。

产品基线：正式 Web `web/app.py`（127.0.0.1:8770），由 `service/main.py` 启动。

进入载荷（逐项都有运行期引用，来源见括号）：
  * web/*.py             正式 Web（含 app.py 入口）+ 共享模块（含 reading_map 运行期 import 的 pdf_pages）
  * learning/*.py        正式学习服务（含 P5 study_call_service / questionbank_service）
  * official_audio.zip   54 个官方教材 MP3（短名 zip；原始文件名最长 148 B，进不了 p4a 的 ustar tar）
                         → 首次运行时由 service/main.py 解包回 `<ZX_ROOT>/<官方教材目录>/`，
                           即 web/audio.py::resolve_official_audio() 期望的正式路径
  * structured/contentpack/v5/*.sqlite                  （content/audio/exercises/learning 全部依赖）
  * structured/learning/learning.clean-seed.db          （P6-B-2C：仅作首次播种的 clean seed；
                                                        运行时 state DB 在 <files>/state/learning.db）
  * structured/learning/mastery_rules_v1.json           （mastery/evidence/learning_object）
  * structured/questionbank/questionbank.db             （P5 select_questions / shadowing_materials）
  * structured/audio/resources/shadowing_pool_v1.json   （P8-Read-B 正式跟读资源池）
  * structured/textbook/textbook_content_relations_v2.json（exercises / intervention / LO）
  * structured/exercises/exercise_catalog{,_v2,_v3}.json（exercises/content）
  * structured/exercises/exercise_question_relations_v3.json（learning_object）
  * structured/textbook/textbook_structure_v2.json      （exercises/intervention）
  * structured/audio/derived/word_audio_manifest.json   （audio：/audio/word/*）
  * structured/audio/derived/words/**（288 个 wav，全部被 manifest 引用，0 个孤儿）
  * audit/P3-07_preview/**                              （reading_map.natural_blocks）
  * audit/P3-06_au06_verified_sentences.json            （server.sentence_assets 第 2 优先级）
  * service/main.py                                     （p4a 服务入口）

明确**不进入**载荷（仍完整保留在项目里，不删除、不移动、不重生成）：
  * demo/**  —— 历史 Demo 不是正式产品基线（正式入口是 web/app.py）
  * 教材源目录里除 54 个 MP3 以外的一切（教材 PDF 等）—— 只打包这 54 个 MP3
  * 教材 PDF —— 六入口不渲染原书页
  * structured/ai/textbook_evidence_map_v1.json —— 仅离线生成期使用（运行期只读缓存，缺失时按“无证据”优雅降级）
  * structured 下未被运行时代码引用的 JSON / 备份（*.bak-*）/ 初始化与迁移脚本
  * test_*、spike/full/revalidate 报告、docs/、builder/、parser/、workbench/、models/、android/

用法（Windows）：
    python J:\ZhixueEnglish_01\android\python_runtime\stage_payload.py
产物：
    J:\ZhixueEnglish_01\android\python_runtime\app\   （p4a 的 --private 目录）
"""

from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]      # 由脚本位置相对推导，不硬编码盘符
PAYLOAD_ROOT = Path(__file__).resolve().parent / "app"

#: 只复制这些目录下的 .py（排除 test_*.py 与开发脚本）
#: P6-B-2C：正式基线是 web/app.py + learning/，demo/ 不再进入正式载荷
CODE_DIRS = ("learning",)
SKIP_NAMES = ("run_ai_distractor_full.py", "run_ai_distractor_spike.py")

#: 正式 Web 运行时模块（app.py 为入口；其余为 web 层共享模块）
WEB_FILES = (
    "app.py", "content.py", "audio.py", "exercises.py", "flow.py", "reading_map.py",
    "ai_grading.py", "demo_content.py", "demo_data.py", "ui.py",
    "pdf_pages.py",          # reading_map.natural_blocks() 运行期 import
)

#: structured 运行期实际引用的文件（相对 structured/）
STRUCTURED_FILES = (
    "contentpack/v5/FLTRP-EN-7A-2022CUR.sqlite",
    "learning/learning.clean-seed.db",      # P6-B-2C：seed 进载荷；运行时库在 <files>/state/learning.db
    "learning/mastery_rules_v1.json",
    "questionbank/questionbank.db",
    "audio/resources/shadowing_pool_v1.json",
    # 2026-09-30：听读课文正文（reading_segments：句级文本 + 时间 + 来源）
    "audio/resources/audio_resource_v1.json",
    "exercises/exercise_catalog.json",
    "exercises/exercise_catalog_v2.json",
    "exercises/exercise_catalog_v3.json",
    "exercises/exercise_question_relations_v3.json",
    "textbook/textbook_content_relations_v2.json",
    "textbook/textbook_structure_v2.json",
    "audio/derived/word_audio_manifest.json",
)

#: structured 运行期实际引用的目录（words 下 288 个 wav 全部被 manifest 引用）
STRUCTURED_DIRS = ("audio/derived/words",)

#: audit 运行期实际引用（P3-07_preview 整目录 + P3-06 已核验句子）
AUDIT_ITEMS = (
    "P3-07_preview",
    "P3-06_au06_verified_sentences.json",
)

#: 官方教材音频（54 个 MP3）：以短名 zip 进载荷，首次运行时解包回原始目录名
OFFICIAL_AUDIO_ZIP = PAYLOAD_ROOT / "official_audio.zip"
OFFICIAL_AUDIO_COUNT = 54
OFFICIAL_AUDIO_DIR_PREFIX = "2025"


def _fresh(path: Path) -> Path:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()
    return path


def copy_code(relative_dir: str) -> int:
    src_dir = PROJECT_ROOT / relative_dir
    dst_dir = _fresh(PAYLOAD_ROOT / relative_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in sorted(src_dir.glob("*.py")):
        if path.name.startswith("test_") or path.name in SKIP_NAMES:
            continue
        shutil.copy2(path, dst_dir / path.name)
        count += 1
    return count


def copy_web_shared() -> int:
    dst_dir = _fresh(PAYLOAD_ROOT / "web")
    dst_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for name in WEB_FILES:
        src = PROJECT_ROOT / "web" / name
        if not src.exists():
            print("  ! 缺失（跳过）:", src)
            continue
        shutil.copy2(src, dst_dir / name)
        count += 1
    return count


def copy_structured() -> int:
    count = 0
    for rel in STRUCTURED_FILES:
        src = PROJECT_ROOT / "structured" / rel
        if not src.exists():
            print("  ! 缺失（跳过）:", src)
            continue
        dst = PAYLOAD_ROOT / "structured" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        count += 1
    for rel in STRUCTURED_DIRS:
        src = PROJECT_ROOT / "structured" / rel
        if not src.exists():
            print("  ! 缺失（跳过）:", src)
            continue
        dst = _fresh(PAYLOAD_ROOT / "structured" / rel)
        shutil.copytree(src, dst)
        count += sum(1 for _ in dst.rglob("*") if _.is_file())
    return count


def copy_audit() -> int:
    count = 0
    for rel in AUDIT_ITEMS:
        src = PROJECT_ROOT / "audit" / rel
        if not src.exists():
            print("  ! 缺失（跳过）:", src)
            continue
        dst = _fresh(PAYLOAD_ROOT / "audit" / rel)
        if src.is_dir():
            shutil.copytree(src, dst)
            count += sum(1 for _ in dst.rglob("*") if _.is_file())
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            count += 1
    return count


def copy_service() -> int:
    src = Path(__file__).resolve().parent / "service"
    dst = _fresh(PAYLOAD_ROOT / "service")
    shutil.copytree(src, dst)
    return len(list(dst.rglob("*")))


def pack_official_audio():
    """把官方教材目录里的 54 个 MP3 打成 `official_audio.zip`（短名，路径 = <官方目录>/<原文件名>）。

    为什么用 zip：p4a 的 private.tar 是 **ustar**（100 B name 限制），而官方 MP3 文件名最长 148 B，
    直接放进载荷会失败/被破坏；zip 支持长文件名与 UTF-8，运行时由 service/main.py 解包回原路径。
    只打包这 54 个 MP3 —— 目录内其它文件（教材 PDF 等）一律不进载荷。
    返回 (打包数量, zip 字节数)。
    """
    src_dir = None
    for cand in sorted(PROJECT_ROOT.iterdir()):
        if not cand.is_dir() or not cand.name.startswith(OFFICIAL_AUDIO_DIR_PREFIX):
            continue
        if len(list(cand.glob("*.mp3"))) == OFFICIAL_AUDIO_COUNT:
            src_dir = cand
            break
    if src_dir is None:
        print("  ! 未找到含 %d 个 MP3 的官方教材目录（official_audio.zip 未生成）" % OFFICIAL_AUDIO_COUNT)
        return 0, 0

    mp3_files = sorted(src_dir.glob("*.mp3"))
    out = _fresh(OFFICIAL_AUDIO_ZIP)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:
        for f in mp3_files:
            zf.write(f, arcname="%s/%s" % (src_dir.name, f.name))     # 原始目录名 + 原始文件名
    return len(mp3_files), out.stat().st_size


def main() -> int:
    print("staging payload →", PAYLOAD_ROOT)
    PAYLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    # 清掉上一版遗留：保证“上一轮打过、这一轮不该打”的文件不会残留进 APK
    # P6-B-2C：demo/ 已退出正式载荷，必须一并清掉上一轮的残留
    for stale_dir in ("structured", "audit", "demo"):
        _fresh(PAYLOAD_ROOT / stale_dir)
    for stale in PAYLOAD_ROOT.iterdir():
        if stale.is_dir() and stale.name.startswith("2025"):
            shutil.rmtree(stale)
    # official_audio.zip 由本次 staging 重新生成（pack_official_audio）；
    # official_audio.version 是设备端运行期标记，不属于载荷内容，残留一律清掉。
    for stale in ("official_audio.version",):
        p = PAYLOAD_ROOT / stale
        if p.exists():
            p.unlink()

    total = 0
    for relative in CODE_DIRS:
        n = copy_code(relative)
        print("  %-14s %d 个 .py" % (relative + "/", n))
        total += n
    total += copy_web_shared()
    print("  %-14s %d 个 .py（含 app.py 入口）" % ("web/", len(WEB_FILES)))
    n = copy_structured()
    print("  %-14s %d 个文件（按运行引用）" % ("structured/", n))
    total += n
    n = copy_audit()
    print("  %-14s %d 个文件（P3-07_preview + P3-06）" % ("audit/", n))
    total += n
    n_audio, audio_bytes = pack_official_audio()
    print("  %-14s %d 个官方 MP3（zip %.1f MB）" % ("official/", n_audio, audio_bytes / 1024 / 1024))
    total += n_audio
    copy_service()
    print("  %-14s 入口" % "service/")

    size = sum(p.stat().st_size for p in PAYLOAD_ROOT.rglob("*") if p.is_file())
    files = sum(1 for p in PAYLOAD_ROOT.rglob("*") if p.is_file())
    print("完成：%d 个文件 / %.1f MB" % (files, size / 1024 / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())

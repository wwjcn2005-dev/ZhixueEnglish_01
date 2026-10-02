#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P6-B-12 验收：`/unit/<slug>/text` 只展示"能与官方音频可靠对应（VERIFIED）"的教材正文

正式依据：V1.1 §7A / V1.3 §29·13 / V2.0 §5.2 / AGENTS §9

覆盖：
  1 VERIFIED 对应块进入正文
  2 无 VERIFIED 对应的正文块不进入正文
  3 PARTIAL 不进入正文（VERIFIED != PARTIAL）
  4 空 Section 正常（Section 结构仍在 + 明确空态 + 不 500）
  5 Section 顺序不变
  6 同一 Section 内块顺序不变（原教材顺序）
  7 活动级 CONFIRMED 音频不受影响
  8 句级热点 / 官方音频播放不受影响
  9 正式资产零写入（contentpack / audio_resource_v1.json / learning.db / questionbank.db）

只读：测试只用 %TEMP% 下的 learning.db 副本；正式资产全程只读并在前后校验 SHA256。
AI 调用 0。运行：python D:\ZhixueEnglish\web\test_p6b12_text_verified_scope.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import app as web_app                     # noqa: E402
import content as content_mod             # noqa: E402
import ui                                 # noqa: E402

BASE = HERE.parent
AUDIO_LAYER = BASE / "structured" / "audio" / "resources" / "audio_resource_v1.json"
QUESTIONBANK = BASE / "structured" / "questionbank" / "questionbank.db"

#: Unit 1 的样本块（P6-B-12 审计已确认）
KEPT_BLOCK = "FLTRP-EN-7A-2022CUR:P22:B0"          # 有 VERIFIED content_block 段
KEPT_TEXT = "Our English teacher Ms Chen writes the sentence on the blackboard"
REMOVED_BLOCK = "FLTRP-EN-7A-2022CUR:P21:B12"      # 无任何对应段（印刷标题）
REMOVED_TEXT = "The first lesson"
PARTIAL_ONLY_BLOCK = "FLTRP-EN-7A-2022CUR:P28:B21"  # 只有 PARTIAL 段
PARTIAL_ONLY_TEXT = "There are so many tasks."

UNIT1_SECTIONS = ("STARTING_OUT", "UNDERSTANDING_IDEAS", "DEVELOPING_IDEAS",
                  "READING_FOR_WRITING", "PRESENTING_IDEAS", "REFLECTION")
UNIT1_EMPTY_SECTIONS = ("STARTING_OUT", "PRESENTING_IDEAS", "REFLECTION")
EMPTY_HINT = "这一节暂时没有可以边听边看的课文。"


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def layer_block_statuses() -> dict:
    """资源层里每个 content_block 出现过的 segment 状态集合（只读）。"""
    layer = json.loads(AUDIO_LAYER.read_text(encoding="utf-8"))
    out = {}
    for res in layer.get("audio_resources") or []:
        for seg in res.get("segments") or []:
            if seg.get("text_resource_kind") != "content_block":
                continue
            out.setdefault(seg.get("text_resource_id"), set()).add(seg.get("status"))
    return out


class TextVerifiedScopeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.assets = {name: sha256_file(p) for name, p in (
            ("learning.db", content_mod.LEARNING_DB),
            ("questionbank.db", QUESTIONBANK),
            ("contentpack", content_mod.CONTENTPACK),
            ("audio_resource_v1.json", AUDIO_LAYER))}
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p6b12_"))
        cls.tmp_db = cls.tmpdir / "learning.db"
        shutil.copyfile(content_mod.LEARNING_DB, cls.tmp_db)
        web_app.Handler.learning_db = cls.tmp_db
        web_app.Handler.contentpack_path = content_mod.CONTENTPACK
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=5)
        shutil.rmtree(cls.tmpdir, ignore_errors=True)
        for name, p in (("learning.db", content_mod.LEARNING_DB),
                        ("questionbank.db", QUESTIONBANK),
                        ("contentpack", content_mod.CONTENTPACK),
                        ("audio_resource_v1.json", AUDIO_LAYER)):
            assert sha256_file(p) == cls.assets[name], "%s 被修改" % name

    def _get(self, path):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path),
                                        timeout=60) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")

    # ---------------- 1 VERIFIED 块进入正文 ----------------
    def test_01_verified_block_is_shown(self):
        covered = content_mod.audio_covered_block_ids("Unit 1", content_mod.CONTENTPACK)
        self.assertIn(KEPT_BLOCK, covered.get("UNDERSTANDING_IDEAS", frozenset()),
                      "有 VERIFIED 对应的块必须进入展示集合")
        status, body = self._get("/unit/unit1/text")
        self.assertEqual(status, 200)
        self.assertIn(KEPT_TEXT, body)

    # ---------------- 2 无对应的块不进入正文 ----------------
    def test_02_unmapped_block_is_hidden(self):
        covered = content_mod.audio_covered_block_ids("Unit 1", content_mod.CONTENTPACK)
        flat = set().union(*covered.values()) if covered else set()
        self.assertNotIn(REMOVED_BLOCK, flat, "无任何音频对应的块不得进入展示集合")
        status, body = self._get("/unit/unit1/text")
        self.assertEqual(status, 200)
        self.assertNotIn(REMOVED_TEXT, body, "无可靠对应的正文不得出现在页面上")

    # ---------------- 3 PARTIAL != VERIFIED ----------------
    def test_03_partial_never_counts_as_verified(self):
        statuses = layer_block_statuses().get(PARTIAL_ONLY_BLOCK) or set()
        self.assertIn("PARTIAL", statuses)
        self.assertNotIn("VERIFIED", statuses, "该块只有 PARTIAL 段，不得混入 VERIFIED")
        verified_only = content_mod.audio_covered_block_ids("Unit 1", content_mod.CONTENTPACK)
        flat_v = set().union(*verified_only.values()) if verified_only else set()
        self.assertNotIn(PARTIAL_ONLY_BLOCK, flat_v)
        both = content_mod.audio_covered_block_ids(
            "Unit 1", content_mod.CONTENTPACK, statuses=("VERIFIED", "PARTIAL"))
        flat_both = set().union(*both.values()) if both else set()
        self.assertIn(PARTIAL_ONLY_BLOCK, flat_both,
                      "同一数据在放宽谓词后可命中 —— 说明差异来自 VERIFIED-only 口径")
        status, body = self._get("/unit/unit1/text")
        self.assertEqual(status, 200)
        self.assertNotIn(PARTIAL_ONLY_TEXT, body, "PARTIAL 正文不得进入正式展示")

    # ---------------- 4 空 Section 正常 ----------------
    def test_04_empty_sections_are_normal(self):
        status, body = self._get("/unit/unit1/text")
        self.assertEqual(status, 200, "空 Section 不得 500")
        for key in UNIT1_EMPTY_SECTIONS:
            label = ui.SECTION_LABELS.get(key)
            self.assertIn("<h2>%s</h2>" % label, body, "Section 结构必须保留：%s" % key)
        self.assertEqual(body.count(EMPTY_HINT), len(UNIT1_EMPTY_SECTIONS),
                         "每个空 Section 都要有明确空态")
        # Appendix：6 个 Section 全部为空，页面仍正常
        st2, body2 = self._get("/unit/appendix/text")
        self.assertEqual(st2, 200)
        self.assertEqual(body2.count(EMPTY_HINT), 6)
        self.assertIn("共 0 段教材原文", body2)

    # ---------------- 5 Section 顺序不变 ----------------
    def test_05_section_order_unchanged(self):
        status, body = self._get("/unit/unit1/text")
        self.assertEqual(status, 200)
        positions = []
        for key in UNIT1_SECTIONS:
            label = ui.SECTION_LABELS.get(key)
            idx = body.find("<h2>%s</h2>" % label)
            self.assertGreater(idx, -1, "缺少 Section：%s" % key)
            positions.append(idx)
        self.assertEqual(positions, sorted(positions), "Section 顺序必须与教材目录一致")

    # ---------------- 6 块顺序不变 ----------------
    def test_06_block_order_unchanged(self):
        covered = content_mod.audio_covered_block_ids("Unit 1", content_mod.CONTENTPACK)
        keep = covered.get("UNDERSTANDING_IDEAS", frozenset())
        data = content_mod.unit_text_sections("unit1", content_mod.CONTENTPACK)
        section = next(s for s in data["sections"] if s["section_key"] == "UNDERSTANDING_IDEAS")
        kept_texts = [b["text"] for b in section["blocks"] if b["block_id"] in keep]
        self.assertGreaterEqual(len(kept_texts), 2)
        status, body = self._get("/unit/unit1/text")
        self.assertEqual(status, 200)
        idxs = [body.find(t[:60]) for t in kept_texts]
        for i, idx in enumerate(idxs):
            self.assertGreater(idx, -1, "保留块缺失：%s" % kept_texts[i][:40])
        self.assertEqual(idxs, sorted(idxs), "保留下来的块必须保持原教材顺序")

    # ---------------- 7 活动级音频不受影响 ----------------
    def test_07_activity_audio_unaffected(self):
        acts = content_mod.unit_audio_resources("Unit 1", content_mod.CONTENTPACK)["activities"]
        self.assertTrue(acts)
        status, body = self._get("/unit/unit1/text")
        self.assertEqual(status, 200)
        self.assertEqual(body.count('data-start="0" data-end="">'), len(acts),
                         "CONFIRMED 活动级音频应全部保留（整段呈现）")
        self.assertIn("活动级音频（整段，未做句子切分）", body)
        for a in acts:
            self.assertIn('data-audio="%s" data-start="0"' % a["audio_code"], body)

    # ---------------- 8 句级热点 / 播放不受影响 ----------------
    def test_08_sentence_hotspot_unaffected(self):
        status, body = self._get("/unit/unit1/text")
        self.assertEqual(status, 200)
        self.assertIn('data-audio="AU13" data-start="13940" data-end="21021"', body,
                      "已核验句子级热点必须继续工作")
        self.assertIn("/audio/official/", body, "官方 MP3 播放链路不得改变")
        self.assertIn('class="hot-sent"', body)

    # ---------------- 9 正式资产零写入 ----------------
    def test_09_formal_assets_untouched(self):
        for name, p in (("learning.db", content_mod.LEARNING_DB),
                        ("questionbank.db", QUESTIONBANK),
                        ("contentpack", content_mod.CONTENTPACK),
                        ("audio_resource_v1.json", AUDIO_LAYER)):
            self.assertEqual(sha256_file(p), self.assets[name], "%s 被写入" % name)


if __name__ == "__main__":
    unittest.main(verbosity=2)

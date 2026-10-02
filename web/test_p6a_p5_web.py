#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P6-A 验收测试：正式 Web 接入 P5（study_call_service）

* 首页六入口 = 冻结口径（跟读练习/听音辨意/音标写词/词形变化/本课检测/自主练习）
* 题目来自正式题库（questionbank.db），经 study_call_service 选择与判分
* 作答 → 正式 LearningRecord（有教材 item 归属才记录；无归属不伪造）
* 全部读写只在 learning.db 临时副本上；正式库 SHA256 前后必须一致

运行：python D:\ZhixueEnglish\web\test_p6a_p5_web.py
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import app as web_app                     # noqa: E402
import content as content_mod             # noqa: E402
import study_call_service as scs          # noqa: E402
import learning_service as svc            # noqa: E402
import evidence_service as ev             # noqa: E402

FORMAL_LEARNING_DB = content_mod.LEARNING_DB
FORMAL_QUESTIONBANK = scs.DEFAULT_QUESTIONBANK
ENTRY_LABELS = ("跟读练习", "听音辨意", "音标写词", "本课检测", "自主练习")
LEGACY_LABELS = ("单词跟读", "听音辨词", "短语练习", "阅读练习", "听辨练习", "课文点读")


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class P6AWebTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p6a_web_"))
        cls.tmp_db = cls.tmpdir / "learning.db"
        shutil.copyfile(FORMAL_LEARNING_DB, cls.tmp_db)
        cls.learning_sha = _sha(FORMAL_LEARNING_DB)
        cls.qb_sha = _sha(FORMAL_QUESTIONBANK)
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
        # 正式库零修改
        assert _sha(FORMAL_LEARNING_DB) == cls.learning_sha, "正式 learning.db 被修改"
        assert _sha(FORMAL_QUESTIONBANK) == cls.qb_sha, "正式 questionbank.db 被修改"
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    # ---------------- 工具
    def _get(self, path):
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path),
                                    timeout=20) as r:
            return r.status, r.read().decode("utf-8")

    def _post(self, path, data: dict):
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def _records(self):
        conn = scs.connect_learning_db_ro(self.tmp_db)
        try:
            return [dict(r) for r in conn.execute(
                "SELECT record_id, item_id, activity_type, result, response_raw, created_at "
                "FROM learning_record ORDER BY created_at, record_id")]
        finally:
            conn.close()

    def _answer_of(self, q):
        if q["answer_kind"] == "option_key":
            return q["answer"]["key"]
        return q["answer"]["text"]

    # ---------------- 1 首页六入口（冻结口径 + 无资源隐藏）
    def test_01_home_entries_are_formal_six(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        rows = " ".join(re.findall(r'<a class="entryrow[^>]*>.*?</a>', body, re.S))
        self.assertTrue(rows, "首页必须有入口行")
        for label in ENTRY_LABELS:
            self.assertIn(label, rows, "首页缺少正式入口：%s" % label)
        for label in LEGACY_LABELS:
            self.assertNotIn(label, rows, "首页入口不得再用旧名称：%s" % label)
        # P7：词形变化已有正式资源（vocab_word_form）→ 入口按 P5 候选出现；
        # 入口显示仍由 P5 资源决定（无资源入口不出现）。
        self.assertIn("/p5/form", body)
        self.assertTrue(scs.select_questions("form", "Starter", None),
                        "Starter 应有正式词形题，首页才可能显示该入口")
        # 首页不得出现内部字段名（沿用既有约束）
        for leaked in ("current_error", "current_weak", "item_id", "session_id", "task_id"):
            self.assertNotIn(leaked, body, "首页不得出现内部字段：%s" % leaked)

    # ---------------- 2 入口 → P5 映射与题目来源
    def test_02_entry_pages_use_p5_questions(self):
        for entry, unit in (("listen", "Unit 1"), ("phonetic", "Unit 1"), ("check", "Unit 3")):
            cands = scs.select_questions(entry, unit, None)
            self.assertTrue(cands, "%s/%s 应有正式题" % (entry, unit))
            status, body = self._get("/unit/%s/p5/%s" % (unit.replace(" ", "").lower().replace("starter", "starter"), entry)
                                     if unit != "Starter" else "/unit/starter/p5/%s" % entry)
            self.assertEqual(status, 200)
            for c in cands[:3]:
                self.assertIn(c["question_id"], body, "页面题目必须来自 P5 候选")
            for c in cands:
                self.assertEqual(c["question"]["answer_status"], "RELIABLE")

    # ---------------- 3 正确答案 → 正式记录
    def test_03_correct_answer_writes_record(self):
        before = len(self._records())
        cands = scs.select_questions("phonetic", "Unit 1", None)
        target = next(c for c in cands if c["evidence_item_id"])
        q = target["question"]
        status, body = self._post("/unit/unit1/p5/phonetic/submit",
                                  {"q_%s" % target["question_id"]: self._answer_of(q),
                                   "name": "P6A测试甲"})
        self.assertEqual(status, 200)
        self.assertIn('class="qfb ok"', body, "答对必须给出正确反馈")
        rows = self._records()
        self.assertEqual(len(rows), before + 1)
        last = rows[-1]
        self.assertEqual(last["item_id"], target["evidence_item_id"])
        self.assertEqual(last["result"], "correct")
        self.assertIn(target["question_id"], last["response_raw"])

    # ---------------- 4 错误答案 → 记录 incorrect
    def test_04_wrong_answer_writes_incorrect(self):
        cands = scs.select_questions("phonetic", "Unit 1", None)
        target = next(c for c in cands if c["evidence_item_id"])
        status, body = self._post("/unit/unit1/p5/phonetic/submit",
                                  {"q_%s" % target["question_id"]: "zzz", "name": "P6A测试乙"})
        self.assertEqual(status, 200)
        self.assertIn('class="qfb again"', body, "答错必须给出回看反馈")
        rows = [r for r in self._records() if r["item_id"] == target["evidence_item_id"]]
        self.assertTrue(rows)
        self.assertEqual(rows[-1]["result"], "incorrect")

    # ---------------- 5 无 evidence item 的题：可作答、不伪造记录
    def test_05_no_evidence_item_is_not_recorded(self):
        cands = scs.select_questions("listen", "Unit 4", None)
        target = next((c for c in cands if not c["evidence_item_id"]), None)
        if target is None:
            self.skipTest("当前没有无教材归属的题")
        before = len(self._records())
        q = target["question"]
        status, body = self._post("/unit/unit4/p5/listen/submit",
                                  {"q_%s" % target["question_id"]: self._answer_of(q),
                                   "name": "P6A测试丙"})
        self.assertEqual(status, 200)
        self.assertEqual(len(self._records()), before, "无教材归属的题不得写入学习记录")

    # ---------------- 6 跟读：repeat + done，不作为判断证据
    def test_06_shadowing_records_done_only(self):
        mats = scs.shadowing_materials("Unit 1")
        m = next((x for x in mats if x["evidence_item_id"]), None)
        if m is None:
            self.skipTest("Unit 1 跟读素材没有可归属 item")
        status, body = self._get("/unit/unit1/p5/read")
        self.assertEqual(status, 200)
        self.assertIn("/unit/unit1/p5/read/submit", body, "跟读素材页必须能在本页完成")
        self.assertIn(m["question_id"], body)
        status, body = self._post("/unit/unit1/p5/read/submit",
                                  {"done_%s" % m["question_id"]: "1", "name": "P6A测试丁"})
        self.assertEqual(status, 200)
        rows = [r for r in self._records() if r["item_id"] == m["evidence_item_id"]]
        self.assertTrue(rows)
        self.assertEqual(rows[-1]["activity_type"], "repeat")
        self.assertEqual(rows[-1]["result"], "done")
        conn = scs.connect_learning_db_ro(self.tmp_db)
        try:
            evd = ev.collect_evidence(conn, rows[-1].get("learner_id") or
                                      self._learner_of(rows[-1]["record_id"]), m["evidence_item_id"])
        finally:
            conn.close()
        self.assertEqual(evd["evidence_count"], 0, "跟读完成不得成为判断证据")

    def _learner_of(self, record_id):
        conn = scs.connect_learning_db_ro(self.tmp_db)
        try:
            return conn.execute("SELECT learner_id FROM learning_record WHERE record_id=?",
                                (record_id,)).fetchone()["learner_id"]
        finally:
            conn.close()

    # ---------------- 7 自主练习：范围 = Starter + 已学前缀 + 当前 Unit（不含未来）
    def test_07_practice_scope_never_future(self):
        status, body = self._get("/unit/unit1/p5/practice")
        self.assertEqual(status, 200)
        cands = scs.select_questions("practice", "Unit 1", None)
        units = {c["unit_code"] for c in cands}
        self.assertTrue(units <= {"Starter", "Unit 1"}, units)
        for c in cands[:3]:
            self.assertIn(c["question_id"], body)

    # ---------------- 8 状态来自正式证据（不读 Cookie 学习状态）
    def test_08_status_from_formal_evidence(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        rows = " ".join(re.findall(r'<a class="entryrow[^>]*>.*?</a>', body, re.S))
        # P6-B-12-FIX（V1.3 §15·6）：入口文案统一为"候选资源数"口径（与功能页同一条池函数），
        # 不再把候选资源数 / 已完成数 / 未完成数混用同一标签。
        self.assertTrue(any(t in rows for t in ("候选", "还有", "继续", "已完成", "需要巩固")),
                        "入口状态必须由正式学习数据给出（当前口径：候选资源数）")
        self.assertNotIn("zx_demo", body)
        self.assertNotIn("演示数据", rows, "入口状态不得来自演示数据")


if __name__ == "__main__":
    unittest.main(verbosity=2)

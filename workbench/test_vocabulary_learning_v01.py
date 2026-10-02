#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-09-C2 / P1-09-C3 / P1-10-C2 教材语言资源最小学习体验测试（stdlib unittest，无新依赖）

覆盖：展示数据构造（只用教材真实字段 / 缺失字段不显示 / 不展示内部技术字段）、
核心词门禁、单词解析、页面渲染、以及**真实 HTTP 往返**
（GET / → POST /start → POST /study → Recall → POST /practice → 结果页；
含非重点词与不存在单词拒绝、显示释义不产生记录、自评三选各产生恰好一条记录、
重复提交不重复写入、自评措辞不出现判分用语）。

P1-10-C2 追加：Phrase（CORE 门禁 + Recall 需 meaning_zh + 全部来源展示 + Study/Recall 流程）
与 Sentence Pattern（仅 CORE + 仅 Study，不进入 Recall / Practice）。

所有写入都发生在 %TEMP% 的 learning.db 副本；正式 learning.db 与 contentpack 只读且不被污染。
"""

from __future__ import annotations

import hashlib
import re
import shutil
import sqlite3
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
sys.path.insert(0, str(HERE.parent / "learning"))
sys.dont_write_bytecode = True

import learning_service as svc              # noqa: E402
import behavior_service as beh              # noqa: E402
import resource_pool_service as pool        # noqa: E402
import session_service as ses               # noqa: E402
import vocabulary_learning_v01 as page      # noqa: E402


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


# 导入时冻结：用于证明测试未污染正式数据（HTTP 流程只写临时副本）
OFFICIAL_DB_SHA = sha256_file(page.LEARNING_DB)
CONTENTPACK_SHA = sha256_file(page.CONTENTPACK)


def _official_business_counts() -> dict:
    """P2-1-C1：正式 learning.db 的业务行数快照（导入时冻结）。"""
    conn = sqlite3.connect("file:%s?mode=ro" % page.LEARNING_DB.as_posix(), uri=True)
    try:
        return {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                for t in ("learner", "learning_session", "learning_task", "task_item",
                          "learning_record", "mastery_state")}
    finally:
        conn.close()


#: 正式库已包含真机真实学习数据，「业务表必须为 0 行」不再是有效基线。
OFFICIAL_DB_COUNTS = _official_business_counts()


class WordViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cp = svc.connect_contentpack_db(page.CONTENTPACK)
        cls.core = cp.execute("SELECT item_id FROM learning_item WHERE item_type='vocabulary' "
                              "AND learning_requirement='CORE' AND canonical_text='ready'").fetchone()["item_id"]
        r = cp.execute("SELECT item_id FROM learning_item WHERE item_type='vocabulary' "
                       "AND learning_requirement='CORE' AND (phonetic IS NULL OR phonetic='') "
                       "ORDER BY item_id LIMIT 1").fetchone()
        cls.core_no_phonetic = r["item_id"] if r else None
        r = cp.execute("SELECT item_id FROM learning_item WHERE item_type='vocabulary' "
                       "AND learning_requirement='CORE' AND part_of_speech IS NULL "
                       "ORDER BY item_id LIMIT 1").fetchone()
        cls.core_no_pos = r["item_id"] if r else None
        cls.recognition = cp.execute("SELECT item_id, canonical_text FROM learning_item "
                                     "WHERE item_type='vocabulary' AND learning_requirement='RECOGNITION' "
                                     "ORDER BY item_id LIMIT 1").fetchone()
        cls.needs_review = cp.execute("SELECT item_id FROM learning_item WHERE item_type='vocabulary' "
                                      "AND learning_requirement='NEED_REVIEW' LIMIT 1").fetchone()
        cp.close()

    # 1. 只使用教材真实字段，不展示内部技术字段
    def test_01_build_word_view(self):
        v = page.build_word_view(self.core, page.CONTENTPACK)
        self.assertEqual(v["word"], "ready")
        self.assertEqual(v["phonetic"], "/ˈredi/")
        self.assertEqual(v["part_of_speech"], "adj")
        self.assertEqual(v["meaning_zh"], "准备好做某事的")
        self.assertEqual(v["tag"], "重点词")
        self.assertEqual(v["source_list"], "Words and expressions")
        self.assertEqual(v["textbook_page"], 150)
        self.assertEqual(v["source_label"], "Words and expressions · 第150页")
        for k in ("pdf_page", "bbox", "font_name", "content_hash", "source_ref_id", "display_text",
                  "learning_requirement", "review_status", "textbook_emphasis", "item_id", "schemas"):
            if k == "item_id":
                continue          # item_id 仅用于页面表单回传，不作为展示字段（页面不渲染它）
            self.assertNotIn(k, v, "学习页面展示数据不得包含内部字段：%s" % k)
        self.assertNotIn("ready /ˈredi/ adj.", str(v.get("meaning_zh")))     # 不使用未整理的 display_text

    # 2. 缺失字段：不显示该行，也不写“暂无/未知/N/A”
    def test_02_missing_fields_are_omitted(self):
        if self.core_no_phonetic:
            v = page.build_word_view(self.core_no_phonetic, page.CONTENTPACK)
            self.assertNotIn("phonetic", v)
            self.assertNotIn("暂无", repr(v))
            self.assertNotIn("N/A", repr(v))
        if self.core_no_pos:
            v = page.build_word_view(self.core_no_pos, page.CONTENTPACK)
            self.assertNotIn("part_of_speech", v)

    # 3. 核心词门禁
    def test_03_only_core_allowed(self):
        with self.assertRaises(svc.ValidationError):
            page.build_word_view(self.recognition["item_id"], page.CONTENTPACK)
        if self.needs_review:
            with self.assertRaises(svc.ValidationError):
                page.build_word_view(self.needs_review["item_id"], page.CONTENTPACK)

    # 4. 单词解析（孩子输入）
    def test_04_resolve_word(self):
        self.assertEqual(page.find_vocabulary_item_id("ready", page.CONTENTPACK), self.core)
        self.assertEqual(page.find_vocabulary_item_id(" Ready ", page.CONTENTPACK), self.core)
        self.assertIsNone(page.find_vocabulary_item_id("notaword", page.CONTENTPACK))
        self.assertIsNone(page.find_vocabulary_item_id("", page.CONTENTPACK))
        # `junior high` 同时是 Vocabulary 词表条目（多词条目），可被解析：
        self.assertIsNotNone(page.find_vocabulary_item_id("junior high", page.CONTENTPACK))
        # 仅作为 Phrase 存在的表达（非词表条目）不应被解析为单词：
        self.assertIsNone(page.find_vocabulary_item_id("along the way", page.CONTENTPACK))

    # 5. 页面渲染
    def test_05_pages_render(self):
        search = page.render_search_page()
        for token in ("开始学习", "系统不会替你挑选单词", "要学的单词"):
            self.assertIn(token, search)
        view = page.build_word_view(self.core, page.CONTENTPACK)
        word_page = page.render_word_page(view, "S-TEST", "L-TEST", "小明")
        for token in ("ready", "/ˈredi/", "adj.", "准备好做某事的", "重点词",
                      "Words and expressions · 第150页", "我学好了", "换一个单词"):
            self.assertIn(token, word_page)
        for leaked in ("FrutigerNext", "bbox", "content_hash", "source_ref_id", "PDF"):
            self.assertNotIn(leaked, word_page)
        result = page.render_result_page(view, {"result": "done"}, {"evidence_count": 1,
                                    "correct_count": 0, "last_result": "done"}, "小明")
        self.assertIn("已记录（study · done）", result)
        # P2-6-B §十九：不得把证据次数展示为掌握等级
        self.assertIn("学习证据", result)
        self.assertIn("不代表掌握", result)
        self.assertNotIn("掌握状态", result)
        self.assertNotIn("掌握较稳定", result)


class RecallRenderTest(unittest.TestCase):
    """P1-09-C3 页面渲染（纯逻辑）：释义隐藏/显示、自评措辞、结果页复用。"""

    @classmethod
    def setUpClass(cls):
        cp = svc.connect_contentpack_db(page.CONTENTPACK)
        cls.core = cp.execute("SELECT item_id FROM learning_item WHERE item_type='vocabulary' "
                              "AND learning_requirement='CORE' AND canonical_text='ready'").fetchone()["item_id"]
        cp.close()
        cls.view = page.build_word_view(cls.core, page.CONTENTPACK)

    # C3-1 初始隐藏释义：Recall 页不得包含中文释义
    def test_01_meaning_hidden_until_revealed(self):
        hidden = page.render_recall_page(self.view, "S-TEST", "L-TEST", "小明", reveal=False)
        self.assertNotIn(self.view["meaning_zh"], hidden)
        self.assertIn("显示释义", hidden)
        self.assertIn("ready", hidden)
        self.assertIn("/ˈredi/", hidden)
        revealed = page.render_recall_page(self.view, "S-TEST", "L-TEST", "小明", reveal=True)
        self.assertIn(self.view["meaning_zh"], revealed)
        self.assertNotIn("显示释义", revealed)

    # C3-2 三个自评按钮：措辞是孩子自评，不是判分
    def test_02_self_assessment_choices(self):
        body = page.render_recall_page(self.view, "S-TEST", "L-TEST", "小明", reveal=True)
        for value, label in page.RECALL_CHOICES:
            self.assertIn('name="result" value="%s">%s<' % (value, label), body)
        self.assertIn("你现在回忆得怎么样？", body)
        self.assertEqual(page.PRACTICE_RESULTS, ("correct", "partial", "incorrect"))
        self.assertIn("practice", beh.BEHAVIOR_TYPES)       # 复用既有 practice
        self.assertNotIn("recall", beh.BEHAVIOR_TYPES)      # P1-09-C3 §五：不新增 recall 行为

    # C3-3 结果页：显示自评状态，且不得出现判分/掌握断言措辞
    def test_03_result_page_self_assessment_wording(self):
        for result, label in page.RECALL_CHOICES:
            body = page.render_result_page(self.view, {"result": "done"},
                                           {"evidence_count": 2, "correct_count": 1,
                                            "last_result": result}, "小明",
                                           practice_record={"result": result})
            self.assertIn("回忆：%s（practice · %s）" % (label, result), body)
            self.assertIn("已记录（study · done）", body)          # C2 结果页语义保留
            for forbidden in ("答对", "答错", "部分正确", "系统判定", "已掌握"):
                self.assertNotIn(forbidden, body,
                                 "Recall 结果文案不得出现判分/掌握断言措辞：%s" % forbidden)

    # C3-4 没有 practice 时仍复用 C2 结果页（向后兼容）
    def test_04_result_page_without_practice(self):
        body = page.render_result_page(self.view, {"result": "done"}, None, "小明")
        self.assertIn("已记录（study · done）", body)
        self.assertNotIn("回忆：", body)

    # C3-5 自评页不得泄漏内部技术字段
    def test_05_no_internal_fields_leaked(self):
        body = page.render_recall_page(self.view, "S-TEST", "L-TEST", "小明", reveal=True)
        for leaked in ("FrutigerNext", "bbox", "content_hash", "source_ref_id", "PDF", "textbook_emphasis"):
            self.assertNotIn(leaked, body)


class HttpFlowTest(unittest.TestCase):
    """真实 HTTP 往返（临时 learning.db 副本）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p109c2_http_"))
        cls.tmp_db = cls.tmpdir / "learning_test.db"
        shutil.copyfile(page.LEARNING_DB, cls.tmp_db)
        page.Handler.db_path = cls.tmp_db
        page.Handler.contentpack_path = page.CONTENTPACK
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), page.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=5)
        # Windows 上偶发文件句柄延迟释放：短暂重试，确保临时测试库被清理
        for _ in range(10):
            try:
                shutil.rmtree(cls.tmpdir)
                break
            except Exception:
                import time
                time.sleep(0.2)

    def _get(self, path):
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path), timeout=10) as r:
            return r.status, r.read().decode("utf-8")

    def _post(self, path, data):
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def test_01_open_page_writes_nothing(self):
        c = svc.connect_learning_db(self.tmp_db)
        before = {t: c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                  for t in ("learning_record", "learner", "learning_session")}
        c.close()
        st, body = self._get("/")
        self.assertEqual(st, 200)
        self.assertIn("开始学习", body)
        c = svc.connect_learning_db(self.tmp_db)
        # P2-1-C1：副本来自正式库（可能已含真实学习数据）→ 保护"打开页面不写入任何数据"
        after = {t: c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                 for t in ("learning_record", "learner", "learning_session")}
        c.close()
        self.assertEqual(after, before, "打开页面不得产生任何学习数据")

    def test_02_full_flow_start_and_study(self):
        st, body = self._post("/start", {"name": "小明", "word": "ready"})
        self.assertEqual(st, 200)
        self.assertIn("我学好了", body)
        sid = re.search(r'name="session_id" value="([^"]+)"', body).group(1)
        lid = re.search(r'name="learner_id" value="([^"]+)"', body).group(1)
        iid = re.search(r'name="item_id" value="([^"]+)"', body).group(1)
        self.assertTrue(sid.startswith("S") and lid.startswith("L") and iid.startswith("FLTRP-EN-7A-2022CUR:V:"))

        st, body = self._post("/study", {"session_id": sid, "learner_id": lid, "item_id": iid})
        self.assertEqual(st, 200)
        # P1-09-C3 §十 / §十一：「我学好了」进入 Recall，不直接结束本次学习
        self.assertIn("Vocabulary Recall", body)
        self.assertIn("你现在回忆得怎么样？", body)
        self.assertIn("显示释义", body)
        self.assertNotIn("准备好做某事的", body)          # 中文释义初始隐藏

        c = svc.connect_learning_db(self.tmp_db)
        # P2-1-C1：临时库副本可能已含真机真实学习数据 → 只断言"本次学习"新增的事实
        self.assertEqual([(r[0], r[1]) for r in c.execute(
            "SELECT r.activity_type, r.result FROM learning_record r JOIN learning_session s "
            "ON s.task_id=r.task_id WHERE s.session_id=?", (sid,))], [("study", "done")])
        self.assertEqual(c.execute("SELECT COUNT(*) FROM learner WHERE learner_id=?",
                                   (lid,)).fetchone()[0], 1)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM learning_session WHERE session_id=?",
                                   (sid,)).fetchone()[0], 1)
        self.assertEqual(c.execute("SELECT evidence_count FROM mastery_state WHERE learner_id=? "
                                   "AND item_id=?", (lid, iid)).fetchone()[0], 1)
        self.assertIsNone(c.execute("SELECT ended_at FROM learning_session WHERE session_id=?",
                                    (sid,)).fetchone()[0],
                          "进入 Recall 前不得结束 Session（P1-09-C3 §十一）")
        c.close()

        # 同名再次学习 → 复用既有 Learner（不重复创建）
        c = svc.connect_learning_db(self.tmp_db)
        learners_before = c.execute("SELECT COUNT(*) FROM learner").fetchone()[0]
        c.close()
        st, _ = self._post("/start", {"name": "小明", "word": "ready"})
        self.assertEqual(st, 200)
        c = svc.connect_learning_db(self.tmp_db)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM learner").fetchone()[0], learners_before,
                         "同名学习者必须复用，不得重复创建")
        c.close()

    def test_03_non_core_and_unknown_word_rejected(self):
        cp = svc.connect_contentpack_db(page.CONTENTPACK)
        rec_word = cp.execute("SELECT canonical_text FROM learning_item WHERE item_type='vocabulary' "
                              "AND learning_requirement='RECOGNITION' ORDER BY item_id LIMIT 1").fetchone()[0]
        cp.close()
        st, body = self._post("/start", {"name": "小明", "word": rec_word})
        self.assertEqual(st, 400)
        self.assertIn("不是教材重点词", body)
        st, body = self._post("/start", {"name": "小明", "word": "zzzznotaword"})
        self.assertEqual(st, 404)
        self.assertIn("没有找到", body)
        c = svc.connect_learning_db(self.tmp_db)
        # 被拒绝的请求不得为该非重点词产生 TaskItem 或学习记录
        cp = svc.connect_contentpack_db(page.CONTENTPACK)
        rec_item = cp.execute("SELECT item_id FROM learning_item WHERE item_type='vocabulary' "
                              "AND learning_requirement='RECOGNITION' ORDER BY item_id LIMIT 1").fetchone()["item_id"]
        cp.close()
        self.assertEqual(c.execute("SELECT COUNT(*) FROM task_item WHERE item_id=?",
                                   (rec_item,)).fetchone()[0], 0)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM learning_record WHERE item_id=?",
                                   (rec_item,)).fetchone()[0], 0)
        c.close()


class RecallFlowTest(unittest.TestCase):
    """P1-09-C3 Recall：/start → /study → Recall →（显示释义）→ /practice → 结果页。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p109c3_http_"))
        cls.tmp_db = cls.tmpdir / "learning_test.db"
        shutil.copyfile(page.LEARNING_DB, cls.tmp_db)
        page.Handler.db_path = cls.tmp_db
        page.Handler.contentpack_path = page.CONTENTPACK
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), page.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=5)
        for _ in range(10):
            try:
                shutil.rmtree(cls.tmpdir)
                break
            except Exception:
                import time
                time.sleep(0.2)

    def _get(self, path):
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path), timeout=10) as r:
            return r.status, r.read().decode("utf-8")

    def _post(self, path, data):
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def _conn(self):
        return svc.connect_learning_db(self.tmp_db)

    def _start_study(self, name, word="ready"):
        """完成 /start → /study，返回 (session_id, learner_id, item_id, recall_html)。"""
        st, body = self._post("/start", {"name": name, "word": word})
        self.assertEqual(st, 200, body)
        sid = re.search(r'name="session_id" value="([^"]+)"', body).group(1)
        lid = re.search(r'name="learner_id" value="([^"]+)"', body).group(1)
        iid = re.search(r'name="item_id" value="([^"]+)"', body).group(1)
        st, body = self._post("/study", {"session_id": sid, "learner_id": lid, "item_id": iid})
        self.assertEqual(st, 200)
        return sid, lid, iid, body

    def _records(self, c, **where):
        sql = "SELECT activity_type, result, attempt_no FROM learning_record"
        if where:
            sql += " WHERE " + " AND ".join("%s=?" % k for k in where)
            rows = c.execute(sql + " ORDER BY activity_type, attempt_no", tuple(where.values())).fetchall()
        else:
            rows = c.execute(sql + " ORDER BY activity_type, attempt_no").fetchall()
        return [tuple(r) for r in rows]

    # C3-HTTP-1 Recall 页不含释义；显示释义不产生任何记录
    def test_01_reveal_writes_nothing(self):
        sid, lid, iid, recall = self._start_study("小刚")
        self.assertIn("Vocabulary Recall", recall)
        self.assertNotIn("准备好做某事的", recall)
        c = self._conn()
        before = self._records(c, learner_id=lid)
        c.close()

        st, revealed = self._post("/recall", {"session_id": sid, "learner_id": lid, "item_id": iid})
        self.assertEqual(st, 200)
        self.assertIn("准备好做某事的", revealed)          # 孩子主动查看后才显示
        self.assertIn("记得", revealed)
        c = self._conn()
        self.assertEqual(self._records(c, learner_id=lid), before, "显示释义不得产生任何 LearningRecord")
        self.assertEqual(c.execute("SELECT ended_at FROM learning_session WHERE session_id=?",
                                   (sid,)).fetchone()[0], None)
        c.close()

    # C3-HTTP-2 自评 → 恰好一条 practice 记录 → 结束 Session → 结果页（自评措辞）
    def test_02_practice_records_once_and_ends_session(self):
        sid, lid, iid, _ = self._start_study("小红")
        st, body = self._post("/practice", {"session_id": sid, "learner_id": lid,
                                            "item_id": iid, "result": "correct"})
        self.assertEqual(st, 200)
        self.assertIn("回忆：记得（practice · correct）", body)
        self.assertIn("已记录（study · done）", body)
        for forbidden in ("答对", "答错", "部分正确", "系统判定", "已掌握"):
            self.assertNotIn(forbidden, body)
        c = self._conn()
        # 一次点击只产生一条判断记录（P1-09-C3 §二十一）
        self.assertEqual(self._records(c, learner_id=lid), [("practice", "correct", 1),
                                                            ("study", "done", 1)])
        self.assertIsNotNone(c.execute("SELECT ended_at FROM learning_session WHERE session_id=?",
                                       (sid,)).fetchone()[0])
        self.assertEqual(c.execute("SELECT COUNT(*) FROM learning_session WHERE learner_id=?",
                                   (lid,)).fetchone()[0], 1, "不得创建第二个 Session")
        # 既有 Mastery 派生规则照旧（self-assessment 计入证据；不新增掌握算法）
        m = c.execute("SELECT evidence_count, correct_count, mastery_level, last_result "
                      "FROM mastery_state WHERE learner_id=? AND item_id=?", (lid, iid)).fetchone()
        self.assertEqual(tuple(m), (2, 1, "unknown", "correct"))
        c.close()

    # C3-HTTP-3 partial → current_weak；incorrect → current_error（复用既有池规则）
    def test_03_pool_mapping(self):
        for word_index, (result, expected) in enumerate((("partial", "current_weak"),
                                                        ("incorrect", "current_error"))):
            with self.subTest(result=result):
                name = "小弱%d" % word_index if result == "partial" else "小错%d" % word_index
                sid, lid, iid, _ = self._start_study(name)
                st, body = self._post("/practice", {"session_id": sid, "learner_id": lid,
                                                    "item_id": iid, "result": result})
                self.assertEqual(st, 200)
                c = self._conn()
                issue = pool.list_current_issue_pool(c, lid)
                self.assertEqual([(x["item_id"], x["issue_type"]) for x in issue], [(iid, expected)],
                                 "C3 必须复用既有 Resource Pool 规则，不自建错误状态")
                c.close()

    # C3-HTTP-4 非法自评值被拒绝，且不写入任何记录
    def test_04_invalid_result_rejected(self):
        sid, lid, iid, _ = self._start_study("小非法")
        st, body = self._post("/practice", {"session_id": sid, "learner_id": lid,
                                            "item_id": iid, "result": "correct_answer"})
        self.assertEqual(st, 400)
        c = self._conn()
        self.assertEqual(self._records(c, learner_id=lid), [("study", "done", 1)])
        self.assertIsNone(c.execute("SELECT ended_at FROM learning_session WHERE session_id=?",
                                    (sid,)).fetchone()[0])
        c.close()

    # C3-HTTP-5 重复提交（刷新/回退重放）不得写入第二条判断记录
    def test_05_duplicate_submit_writes_no_second_record(self):
        sid, lid, iid, _ = self._start_study("小重复")
        payload = {"session_id": sid, "learner_id": lid, "item_id": iid, "result": "correct"}
        st1, body1 = self._post("/practice", payload)
        self.assertEqual(st1, 200)
        st2, body2 = self._post("/practice", payload)
        self.assertEqual(st2, 200)
        self.assertIn("回忆：记得（practice · correct）", body2)     # 只读重放，仍是同一条
        c = self._conn()
        self.assertEqual(self._records(c, learner_id=lid), [("practice", "correct", 1),
                                                            ("study", "done", 1)])
        c.close()


class SafetyTest(unittest.TestCase):
    def test_official_data_untouched(self):
        self.assertEqual(sha256_file(page.LEARNING_DB), OFFICIAL_DB_SHA,
                         "正式 learning.db 未被本次测试修改")
        self.assertEqual(sha256_file(page.CONTENTPACK), CONTENTPACK_SHA, "contentpack 未被修改")
        conn = sqlite3.connect("file:%s?mode=ro" % page.LEARNING_DB.as_posix(), uri=True)
        rows = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                for t in ("learner", "learning_session", "learning_task", "task_item",
                          "learning_record", "mastery_state")}
        conn.close()
        # P2-1-C1：正式库已含真机真实学习数据 → 保护"未被修改 / 未被删除"
        self.assertEqual(rows, OFFICIAL_DB_COUNTS,
                         "正式 learning.db 的真实学习数据不得被本次测试修改或删除")

    def test_no_ai_and_local_only(self):
        src = (HERE / "vocabulary_learning_v01.py").read_text(encoding="utf-8").lower()
        for token in ("openai", "deepseek", "ollama", "anthropic", "requests.",
                      "transformers", "torch", "tensorflow"):
            self.assertNotIn(token, src)
        self.assertIn('("127.0.0.1", args.port)', src)        # 仅监听本机
        self.assertNotIn("0.0.0.0", src)
        ls = (HERE.parent / "learning" / "learning_service.py").read_text(encoding="utf-8").lower()
        self.assertIn("mode=ro", ls)                          # 教材库只读


class PhraseRulesTest(unittest.TestCase):
    """P1-10-C2 Phrase 规则（只读真实数据）：CORE 门禁、Recall 门禁、来源展示、查找。"""

    @classmethod
    def setUpClass(cls):
        cls.cp = svc.connect_contentpack_db(page.CONTENTPACK)
        cls.core_phrases = [r["item_id"] for r in cls.cp.execute(
            "SELECT item_id FROM learning_item WHERE item_type='phrase' "
            "AND learning_requirement='CORE' ORDER BY item_id")]
        cls.recognition_phrase = cls.cp.execute(
            "SELECT item_id FROM learning_item WHERE item_type='phrase' "
            "AND learning_requirement='RECOGNITION' ORDER BY item_id LIMIT 1").fetchone()["item_id"]
        cls.core_pattern = cls.cp.execute(
            "SELECT item_id FROM learning_item WHERE item_type='sentence_pattern' "
            "AND learning_requirement='CORE' ORDER BY item_id LIMIT 1").fetchone()["item_id"]
        cls.review_pattern = cls.cp.execute(
            "SELECT item_id FROM learning_item WHERE item_type='sentence_pattern' "
            "AND learning_requirement='NEED_REVIEW' ORDER BY item_id LIMIT 1").fetchone()["item_id"]

    @classmethod
    def tearDownClass(cls):
        cls.cp.close()

    # C2-P-1 CORE 门禁 + Recall 门禁（CORE 且 meaning_zh 非空才可 Recall）
    def test_01_core_gate_and_recall_rule(self):
        self.assertTrue(self.core_phrases, "真实数据应存在 CORE Phrase")
        for item_id in self.core_phrases:
            v = page.build_phrase_view(item_id, page.CONTENTPACK)
            self.assertEqual(v["item_type"], "phrase")
            self.assertFalse(v["recall_available"],
                             "CORE 但无 meaning_zh 的短语本阶段不得进入 Recall（P1-10-C2 §三）")
        with self.assertRaises(svc.ValidationError):
            page.build_phrase_view(self.recognition_phrase, page.CONTENTPACK)
        # Recall 门禁规则（纯函数）
        self.assertTrue(page.phrase_recall_available(
            {"learning_requirement": "CORE", "meaning_zh": "有释义"}))
        self.assertFalse(page.phrase_recall_available(
            {"learning_requirement": "CORE", "meaning_zh": None}))
        self.assertFalse(page.phrase_recall_available(
            {"learning_requirement": "CORE", "meaning_zh": "   "}))
        self.assertFalse(page.phrase_recall_available(
            {"learning_requirement": "RECOGNITION", "meaning_zh": "有释义"}))
        self.assertFalse(page.phrase_recall_available(None))

    # C2-P-2 来源展示：不静默丢弃任何来源
    def test_02_all_sources_preserved(self):
        lines = page.source_lines(page._refs_from(self.cp, self.recognition_phrase))
        self.assertEqual(len(lines), 2, "短语在词表两处出现时必须全部展示：%s" % lines)
        self.assertTrue(all(("第" in line and "页" in line) for line in lines), lines)
        core_lines = page.source_lines(page._refs_from(self.cp, self.core_phrases[0]))
        self.assertEqual(len(core_lines), 1, "同一来源栏目 + 同一页应去重：%s" % core_lines)

    # C2-P-3 Phrase 展示数据不含内部字段、不含不存在的音标/词性、不含「重点词」标签
    def test_03_phrase_view_fields(self):
        v = page.build_phrase_view(self.core_phrases[0], page.CONTENTPACK)
        for forbidden in ("tag", "phonetic", "part_of_speech", "pdf_page", "bbox", "font_name",
                          "content_hash", "source_ref_id", "display_text",
                          "learning_requirement", "review_status", "textbook_emphasis"):
            self.assertNotIn(forbidden, v, "Phrase 展示数据不得包含：%s" % forbidden)

    # C2-P-4 短语查找（大小写不敏感；不认识的内容不臆测）
    def test_04_phrase_lookup(self):
        item_id = self.core_phrases[0]
        text = self.cp.execute("SELECT canonical_text FROM learning_item WHERE item_id=?",
                               (item_id,)).fetchone()["canonical_text"]
        self.assertEqual(page.find_phrase_item_id(text, page.CONTENTPACK), item_id)
        self.assertEqual(page.find_phrase_item_id(" " + text.upper() + " ", page.CONTENTPACK), item_id)
        self.assertIsNone(page.find_phrase_item_id("zzzz not a phrase", page.CONTENTPACK))
        self.assertIsNone(page.find_phrase_item_id("ready", page.CONTENTPACK))

    # C2-P-5 句型页面使用 display_text（`...` 形态），不展示 {n} 槽位模板
    def test_05_pattern_view_uses_display_text(self):
        v = page.build_sentence_pattern_view(self.core_pattern, page.CONTENTPACK)
        display = self.cp.execute("SELECT display_text FROM learning_item WHERE item_id=?",
                                  (self.core_pattern,)).fetchone()["display_text"]
        self.assertEqual(v["word"], display)
        self.assertIn("...", v["word"])
        self.assertNotIn("{1}", v["word"])
        self.assertFalse(v["recall_available"], "本阶段句型不进入 Recall")
        self.assertIsNone(v["meaning_zh"])
        self.assertTrue(v["source_lines"])
        for forbidden in ("pdf_page", "bbox", "content_hash", "source_ref_id", "display_text",
                          "learning_requirement", "review_status", "textbook_emphasis", "tag"):
            self.assertNotIn(forbidden, v)

    # C2-P-6 句型门禁：仅 CORE 可进入 Study
    def test_06_pattern_gate(self):
        self.assertIsNotNone(page.build_sentence_pattern_view(self.core_pattern, page.CONTENTPACK))
        with self.assertRaises(svc.ValidationError):
            page.build_sentence_pattern_view(self.review_pattern, page.CONTENTPACK)

    # C2-P-7 页面渲染：不含判分/回忆元素，不泄漏内部字段
    def test_07_render_wording(self):
        phrase = page.build_phrase_view(self.core_phrases[0], page.CONTENTPACK)
        phrase_html = page.render_word_page(phrase, "S-T", "L-T", "小明")
        self.assertIn("我学好了", phrase_html)
        self.assertIn("换一个短语", phrase_html)
        self.assertNotIn("重点词", phrase_html)
        for leaked in ("FrutigerNext", "bbox", "content_hash", "source_ref_id", "PDF",
                       "textbook_emphasis"):
            self.assertNotIn(leaked, phrase_html)
        pattern = page.build_sentence_pattern_view(self.core_pattern, page.CONTENTPACK)
        sp_html = page.render_word_page(pattern, "S-T", "L-T", "小明")
        self.assertIn("换一个句型", sp_html)
        self.assertNotIn("重点词", sp_html)
        self.assertNotIn("{1}", sp_html)
        for forbidden in ("答对", "答错", "部分正确", "系统判定", "已掌握", "回忆得怎么样"):
            self.assertNotIn(forbidden, sp_html, "句型 Study 页不得出现判分/回忆元素：%s" % forbidden)


class PhraseSentenceHttpTest(unittest.TestCase):
    """P1-10-C2 真实 HTTP 往返（临时 learning.db 副本）：短语 Study 与句型 Study。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p110c2_http_"))
        cls.tmp_db = cls.tmpdir / "learning_test.db"
        shutil.copyfile(page.LEARNING_DB, cls.tmp_db)
        page.Handler.db_path = cls.tmp_db
        page.Handler.contentpack_path = page.CONTENTPACK
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), page.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        cp = svc.connect_contentpack_db(page.CONTENTPACK)
        cls.core_phrase = cp.execute(
            "SELECT item_id, canonical_text FROM learning_item WHERE item_type='phrase' "
            "AND learning_requirement='CORE' ORDER BY item_id LIMIT 1").fetchone()
        cls.rec_phrase = cp.execute(
            "SELECT canonical_text FROM learning_item WHERE item_type='phrase' "
            "AND learning_requirement='RECOGNITION' ORDER BY item_id LIMIT 1").fetchone()[
                "canonical_text"]
        cls.core_pattern = cp.execute(
            "SELECT display_text FROM learning_item WHERE item_type='sentence_pattern' "
            "AND learning_requirement='CORE' LIMIT 1").fetchone()["display_text"]
        cls.review_pattern = cp.execute(
            "SELECT display_text FROM learning_item WHERE item_type='sentence_pattern' "
            "AND learning_requirement='NEED_REVIEW' ORDER BY item_id LIMIT 1").fetchone()[
                "display_text"]
        cp.close()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=5)
        for _ in range(10):
            try:
                shutil.rmtree(cls.tmpdir)
                break
            except Exception:
                import time
                time.sleep(0.2)

    def _post(self, path, data):
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def _conn(self):
        return svc.connect_learning_db(self.tmp_db)

    def _records(self, c, learner_id):
        return [tuple(r) for r in c.execute(
            "SELECT activity_type, result, attempt_no FROM learning_record WHERE learner_id=? "
            "ORDER BY activity_type, attempt_no", (learner_id,))]

    def _start(self, name, word, kind):
        return self._post("/start", {"name": name, "word": word, "kind": kind})

    # C2-H-1 短语 Study 入口门禁：CORE 可进入；RECOGNITION 拒绝；不存在拒绝
    def test_01_phrase_entry_gate(self):
        st, body = self._start("小短", self.core_phrase["canonical_text"], "phrase")
        self.assertEqual(st, 200)
        self.assertIn("我学好了", body)
        self.assertIn("换一个短语", body)
        self.assertNotIn("重点词", body)
        self.assertIn("教材来源", body)
        st, body = self._start("小短", self.rec_phrase, "phrase")
        self.assertEqual(st, 400)
        self.assertIn("不是教材重点短语", body)
        st, body = self._start("小短", "zzzz not a phrase", "phrase")
        self.assertEqual(st, 404)
        self.assertIn("没有找到", body)

    # C2-H-2 短语 Study：study·done、Session 结束、不产生 practice（无释义 → 不进入 Recall）
    def test_02_phrase_study_without_recall(self):
        st, body = self._start("小短2", self.core_phrase["canonical_text"], "phrase")
        self.assertEqual(st, 200)
        sid = re.search(r'name="session_id" value="([^"]+)"', body).group(1)
        lid = re.search(r'name="learner_id" value="([^"]+)"', body).group(1)
        iid = re.search(r'name="item_id" value="([^"]+)"', body).group(1)
        st, body = self._post("/study", {"session_id": sid, "learner_id": lid, "item_id": iid})
        self.assertEqual(st, 200)
        self.assertIn("已记录（study · done）", body)
        self.assertIn("不做回忆自评", body)
        self.assertNotIn("回忆：", body)
        self.assertNotIn("Vocabulary Recall", body)
        c = self._conn()
        self.assertEqual(self._records(c, lid), [("study", "done", 1)])
        self.assertIsNotNone(c.execute("SELECT ended_at FROM learning_session WHERE session_id=?",
                                       (sid,)).fetchone()[0], "无 Recall 时 Study 后应结束 Session")
        m = c.execute("SELECT evidence_count, correct_count, mastery_level FROM mastery_state "
                      "WHERE learner_id=? AND item_id=?", (lid, iid)).fetchone()
        self.assertEqual(tuple(m), (1, 0, "unknown"))
        self.assertEqual(pool.list_current_issue_pool(c, lid), [],
                         "study/done 不得进入当前错误/薄弱池")
        c.close()

    # C2-H-3 句型 Study：CORE 可进入；NEED_REVIEW 拒绝；只用 display_text；不产生 practice
    def test_03_sentence_pattern_study_only(self):
        st, body = self._start("小句", self.core_pattern, "sentence_pattern")
        self.assertEqual(st, 200)
        self.assertIn(self.core_pattern, body)
        self.assertNotIn("{1}", body)
        self.assertIn("换一个句型", body)
        self.assertNotIn("重点词", body)
        for forbidden in ("答对", "答错", "部分正确", "系统判定", "已掌握", "回忆得怎么样",
                          "记得", "模糊", "忘了"):
            self.assertNotIn(forbidden, body, "句型 Study 页不得出现回忆/判分元素：%s" % forbidden)
        sid = re.search(r'name="session_id" value="([^"]+)"', body).group(1)
        lid = re.search(r'name="learner_id" value="([^"]+)"', body).group(1)
        iid = re.search(r'name="item_id" value="([^"]+)"', body).group(1)
        st, body = self._post("/study", {"session_id": sid, "learner_id": lid, "item_id": iid})
        self.assertEqual(st, 200)
        self.assertIn("已记录（study · done）", body)
        c = self._conn()
        self.assertEqual(self._records(c, lid), [("study", "done", 1)])
        self.assertIsNotNone(c.execute("SELECT ended_at FROM learning_session WHERE session_id=?",
                                       (sid,)).fetchone()[0])
        self.assertEqual(pool.list_current_issue_pool(c, lid), [])
        c.close()
        st, _ = self._post("/recall", {"session_id": sid, "learner_id": lid, "item_id": iid})
        self.assertEqual(st, 400, "句型不得进入 Recall")
        st, _ = self._post("/practice", {"session_id": sid, "learner_id": lid,
                                         "item_id": iid, "result": "correct"})
        self.assertEqual(st, 400, "句型不得进入 Practice")
        c = self._conn()
        self.assertEqual(self._records(c, lid), [("study", "done", 1)])
        c.close()
        st, body = self._start("小句", self.review_pattern, "sentence_pattern")
        self.assertEqual(st, 400)
        self.assertIn("不是教材重点句型", body)

    # C2-H-4 类型隔离：词汇入口不认识短语；短语入口不认识单词
    def test_04_kind_isolation(self):
        st, _ = self._start("小隔", self.core_phrase["canonical_text"], "vocabulary")
        self.assertEqual(st, 404)
        st, _ = self._start("小隔", "ready", "phrase")
        self.assertEqual(st, 404)


class PoolViewTest(unittest.TestCase):
    """P1-11-C2 当前需要再学（只读池）：分组、措辞、只读渲染、首页/结果页入口。"""

    @staticmethod
    def _visible(body):
        """去掉 <style> 块（CSS 里的 100% 等不算页面文案）。"""
        return re.sub(r"(?s)<style>.*?</style>", "", body)

    def _row(self, item_id, text, kind, issue, result, at):
        return {"item_id": item_id, "knowledge_name": text, "resource_type": kind,
                "issue_type": issue, "last_judged_result": result, "last_judged_at": at}

    def _view(self, rows):
        """按 build_pool_view 的展示结构构造分组（用于纯渲染测试，不经 HTTP/DB）。"""
        grouped = {key: [] for key in page.ISSUE_ORDER}
        for row in rows:
            grouped.setdefault(row["issue_type"], []).append({
                "item_id": row["item_id"], "text": row["knowledge_name"],
                "phonetic": row.get("phonetic"), "part_of_speech": row.get("part_of_speech"),
                "meaning_zh": row.get("meaning_zh"),
                "kind": row["resource_type"],
                "kind_label": page.KIND_LABELS.get(row["resource_type"], ""),
                "last_label": page.RESULT_LABELS.get(row["last_judged_result"], ""),
                "action_available": row.get("action_available", True),
                "unavailable_note": None})
        return [{"issue_type": k, "title": page.ISSUE_TITLES[k], "items": grouped[k]}
                for k in page.ISSUE_ORDER if grouped.get(k)]

    # C2-A-1 分组顺序：先「当前错误」后「当前薄弱」
    def test_01_section_order(self):
        sections = self._view([
            self._row("i1", "weak", "vocabulary", "current_weak", "partial", "t2"),
            self._row("i2", "hold", "vocabulary", "current_error", "incorrect", "t1")])
        self.assertEqual([s["title"] for s in sections], ["当前错误", "当前薄弱"])
        self.assertEqual([s["items"][0]["text"] for s in sections], ["hold", "weak"])

    # C2-A-2 页面：列出词 + 上次自评措辞 + 「再学一次」表单复用 /start；不显示释义/内部字段
    def test_02_page_content_and_no_leak(self):
        sections = self._view([
            dict(self._row("i2", "hold", "vocabulary", "current_error", "incorrect", "t1"),
                 phonetic="/həʊld/", part_of_speech="v", meaning_zh="握住,抓住;抱住")])
        body = page.render_pool_page("小明", view={"sections": sections, "total": 1})
        self.assertIn("当前错误", body)
        self.assertIn("hold", body)
        self.assertIn("/həʊld/", body)                     # 真实音标（有则显示）
        self.assertIn("握住,抓住;抱住", body)                # 真实释义（有则显示）
        self.assertIn("上次：忘了", body)
        self.assertIn("再学这个词", body)
        self.assertIn('action="/start"', body)             # 复用既有入口
        self.assertIn('name="item_id" value="i2"', body)   # item_id → learning_item（§十六）
        self.assertNotIn('name="word"', body)              # 不需要孩子重新输入单词（§十四）
        for forbidden in ("source_ref_id", "content_hash", "snapshot_id", "bbox", "PDF",
                          "FrutigerNext", "current_error", "current_weak", "record_id",
                          "task_id"):
            self.assertNotIn(forbidden, body, "池页面不得泄漏内部字段/枚举：%s" % forbidden)

    # C2-A-3 空池提示 + 未找到学习记录的提示
    def test_03_empty_states(self):
        empty = page.render_pool_page("小明", view={"sections": [], "total": 0})
        self.assertIn("当前没有需要再学的词", empty)
        self.assertNotIn('action="/start"', empty, "空池不应出现「再学这个词」表单")
        for forbidden in ("恭喜", "奖励", "连胜", "完美", "100%", "已全部掌握", "全部掌握"):
            self.assertNotIn(forbidden, self._visible(empty),
                             "空状态不得使用游戏化/掌握断言文案：%s" % forbidden)
        unknown = page.render_pool_page("小明", notice="还没有找到“小明”的学习记录")
        self.assertIn("还没有找到", unknown)
        error = page.render_pool_page("", error="请填写你的名字。")
        self.assertIn("请填写你的名字。", error)

    # C2-A-4 首页与结果页都要有进入池的入口
    def test_04_entry_points(self):
        search = page.render_search_page()
        self.assertIn('action="/pool"', search)
        self.assertIn("看看我需要再学的词", search)
        self.assertIn("当前需要再学", search)
        view = page.build_word_view(self.item_id, page.CONTENTPACK)
        result = page.render_result_page(view, {"result": "done"}, None, "小明")
        self.assertIn('action="/pool"', result)
        self.assertIn("看看我还需要再学的词", result)
        self.assertIn('name="name" value="小明"', result)

    # C2-A-5 池内混合资源类型：短语也标出来源类型，并同样可「再学一次」
    def test_05_mixed_resource_types(self):
        sections = self._view([
            self._row("i1", "of course", "phrase", "current_weak", "partial", "t1"),
            self._row("i2", "hold", "vocabulary", "current_error", "incorrect", "t2")])
        body = page.render_pool_page("小明", view={"sections": sections, "total": 2})
        self.assertIn("短语", body)
        self.assertIn("单词", body)
        self.assertIn('name="item_id" value="i1"', body)
        self.assertIn('name="item_id" value="i2"', body)

    # C2-A-6 页面不得出现推荐/计划/游戏化文案（P1-11-C2 §十二/§二十）
    def test_06_no_recommendation_or_gamification_copy(self):
        sections = self._view([
            self._row("i2", "hold", "vocabulary", "current_error", "incorrect", "t1")])
        body = page.render_pool_page("小明", view={"sections": sections, "total": 1})
        for forbidden in ("系统推荐", "最应该学习", "AI 推荐", "AI推荐", "今日任务",
                          "下一步学习", "积分", "排行榜", "徽章", "打卡", "奖励", "连胜",
                          "已掌握"):
            self.assertNotIn(forbidden, self._visible(body),
                             "池页面不得出现推荐/计划/游戏化文案：%s" % forbidden)

    @classmethod
    def setUpClass(cls):
        cp = svc.connect_contentpack_db(page.CONTENTPACK)
        cls.item_id = cp.execute("SELECT item_id FROM learning_item WHERE item_type='vocabulary' "
                                 "AND canonical_text='weak'").fetchone()["item_id"]
        cp.close()


class PoolHttpTest(unittest.TestCase):
    """P1-11-C2 真实 HTTP：池只读、分组正确、孩子选择后复用 /start 闭环。"""

    WORD = "weak"

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p111c2_pool_"))
        cls.tmp_db = cls.tmpdir / "learning_test.db"
        shutil.copyfile(page.LEARNING_DB, cls.tmp_db)
        page.Handler.db_path = cls.tmp_db
        page.Handler.contentpack_path = page.CONTENTPACK
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), page.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=5)
        for _ in range(10):
            try:
                shutil.rmtree(cls.tmpdir)
                break
            except Exception:
                import time
                time.sleep(0.2)

    def _post(self, path, data):
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def _conn(self):
        return svc.connect_learning_db(self.tmp_db)

    def _counts(self):
        c = self._conn()
        out = {t: c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
               for t in ("learner", "learning_session", "learning_task", "task_item",
                         "learning_record", "mastery_state")}
        c.close()
        return out

    def _learn(self, name, word, result):
        """完整走一遍 /start → /study → /practice（返回 practice 结果页）。"""
        st, body = self._post("/start", {"name": name, "word": word, "kind": "vocabulary"})
        self.assertEqual(st, 200, body)
        sid = re.search(r'name="session_id" value="([^"]+)"', body).group(1)
        lid = re.search(r'name="learner_id" value="([^"]+)"', body).group(1)
        iid = re.search(r'name="item_id" value="([^"]+)"', body).group(1)
        st, recall = self._post("/study", {"session_id": sid, "learner_id": lid, "item_id": iid})
        self.assertEqual(st, 200)
        st, done = self._post("/practice", {"session_id": sid, "learner_id": lid,
                                            "item_id": iid, "result": result})
        self.assertEqual(st, 200)
        return lid, done

    # C2-B-1 池页只读：未知名字不创建 Learner，也不写任何业务行
    def test_01_pool_is_read_only(self):
        before = self._counts()
        st, body = self._post("/pool", {"name": "从没学过的孩子"})
        self.assertEqual(st, 200)
        self.assertIn("还没有找到", body)
        self.assertIn("当前没有需要再学的词", body)
        self.assertEqual(self._counts(), before, "池页面不得产生任何写入")
        # P2-1-C1：正式库已含真机真实学习数据 → 这里保护"池页面不新建任何学习者"
        c = self._conn()
        self.assertIsNone(c.execute("SELECT learner_id FROM learner WHERE display_name=?",
                                    ("从没学过的孩子",)).fetchone(),
                          "池页面不得新建学习者")
        c.close()
        st, body = self._post("/pool", {"name": ""})
        self.assertEqual(st, 400)
        self.assertIn("请填写你的名字", body)
        self.assertEqual(self._counts(), before)

    # C2-B-2 incorrect → 当前错误；partial → 当前薄弱；correct → 不在池中
    def test_02_pool_grouping(self):
        self._learn("小错", self.WORD, "incorrect")
        self._learn("小弱", self.WORD, "partial")
        self._learn("小对", self.WORD, "correct")
        st, body = self._post("/pool", {"name": "小错"})
        self.assertEqual(st, 200)
        self.assertIn("当前错误", body)
        self.assertIn("上次：忘了", body)
        self.assertNotIn("当前薄弱", body)
        self.assertIn("weak", body)
        self.assertIn("/wiːk/", body)                    # 真实音标（有则显示）
        self.assertIn("虚弱的不强壮的", body)              # 真实释义（有则显示，§九/§十二）
        st, body = self._post("/pool", {"name": "小弱"})
        self.assertIn("当前薄弱", body)
        self.assertIn("上次：模糊", body)
        self.assertNotIn("当前错误", body)
        st, body = self._post("/pool", {"name": "小对"})
        self.assertIn("当前没有需要再学的词", body)
        self.assertNotIn("上次：", body)

    # C2-B-2b 排序完全复用 Pool Service（不在 Workbench 重新排序，§二十三）
    def test_02b_order_comes_from_pool_service(self):
        c = self._conn()
        service_order = [(r["item_id"], r["issue_type"])
                         for r in pool.list_current_issue_pool(
                             c, c.execute("SELECT learner_id FROM learner WHERE display_name='小错'")
                             .fetchone()[0], contentpack_path=page.CONTENTPACK)]
        view = page.build_pool_view(
            c, c.execute("SELECT learner_id FROM learner WHERE display_name='小错'").fetchone()[0],
            page.CONTENTPACK)
        c.close()
        page_order = [(item["item_id"], section["issue_type"])
                      for section in view["sections"] for item in section["items"]]
        self.assertEqual(page_order, service_order, "页面顺序必须与 Pool Service 返回顺序一致")
        self.assertEqual([s["issue_type"] for s in view["sections"]], ["current_error"])

    # C2-B-3 孩子从池里选一个词 → 复用 /start → 再练 correct → 出池（闭环）
    def test_03_choose_from_pool_and_close_loop(self):
        import time
        self._learn("小闭环", self.WORD, "incorrect")
        # 已知问题 C2-A：created_at 只到秒，同秒两条判断记录的「最新一条」不稳定。
        # 本测试不修复该问题，只用明确可区分的时间戳验证业务语义（与 P1-08-C1 §十四 同一做法）。
        time.sleep(1.1)
        st, body = self._post("/pool", {"name": "小闭环"})
        self.assertEqual(st, 200)
        self.assertIn("再学这个词", body)
        self.assertNotIn('name="word"', body, "从池进入不需要孩子重新输入单词")
        name = re.search(r'name="name" value="([^"]+)"', body).group(1)
        clicked_item = re.search(r'name="item_id" value="([^"]+)"', body).group(1)
        self.assertEqual(name, "小闭环")
        # 复用既有入口：完全按池页面表单提交（只有 名字 + item_id）
        st, study_page = self._post("/start", {"name": name, "item_id": clicked_item})
        self.assertEqual(st, 200)
        self.assertIn("我学好了", study_page)
        sid = re.search(r'name="session_id" value="([^"]+)"', study_page).group(1)
        lid = re.search(r'name="learner_id" value="([^"]+)"', study_page).group(1)
        iid = re.search(r'name="item_id" value="([^"]+)"', study_page).group(1)
        self.assertEqual(iid, clicked_item, "点击的词就是进入学习的词")
        c = self._conn()
        self.assertEqual(c.execute("SELECT COUNT(*) FROM learning_task WHERE learner_id=?",
                                   (lid,)).fetchone()[0], 2, "池入口仍走正常 Task")
        self.assertEqual(c.execute("SELECT COUNT(*) FROM task_item WHERE task_id="
                                   "(SELECT task_id FROM learning_session WHERE session_id=?)",
                                   (sid,)).fetchone()[0], 1, "池入口仍走正常 TaskItem")
        c.close()
        self._post("/study", {"session_id": sid, "learner_id": lid, "item_id": iid})
        st, done = self._post("/practice", {"session_id": sid, "learner_id": lid,
                                            "item_id": iid, "result": "correct"})
        self.assertEqual(st, 200)
        self.assertIn("回忆：记得（practice · correct）", done)
        st, body = self._post("/pool", {"name": "小闭环"})
        self.assertIn("当前没有需要再学的词", body, "答对后应退出当前池")

    # C2-B-4 Learner 隔离：别人的池里看不到我的词
    def test_04_learner_isolation(self):
        self._learn("小明隔离", self.WORD, "incorrect")
        st, body = self._post("/pool", {"name": "小红隔离"})
        self.assertEqual(st, 200)
        self.assertIn("还没有找到", body)
        c = self._conn()
        n_learner = c.execute("SELECT COUNT(*) FROM learner WHERE display_name LIKE '%隔离'").fetchone()[0]
        c.close()
        self.assertEqual(n_learner, 1, "池页面不得为陌生人创建 Learner")

    # C2-B-5 结果页 → 池页 的衔接可用
    def test_05_result_page_links_to_pool(self):
        lid, done = self._learn("小衔接", self.WORD, "incorrect")
        self.assertIn('action="/pool"', done)
        st, body = self._post("/pool", {"name": "小衔接"})
        self.assertEqual(st, 200)
        self.assertIn(self.WORD, body)

    # C2-B-6 学习后的池状态变化（§二十六 16~19：全部由既有服务决定，页面不改池）
    def test_06_state_transitions(self):
        import time
        cases = (("incorrect", "correct", None),            # error → correct → 出池
                 ("incorrect", "partial", "当前薄弱"),        # error → partial → weak
                 ("partial", "incorrect", "当前错误"),        # weak → incorrect → error
                 ("partial", "correct", None))              # weak → correct → 出池
        for index, (from_result, to_result, expected_section) in enumerate(cases):
            with self.subTest(case="%s->%s" % (from_result, to_result)):
                name = "小状态%d" % index
                self._learn(name, self.WORD, from_result)
                time.sleep(1.1)          # 区分 created_at（已知同秒 tie-break，不修复）
                st, pool_page = self._post("/pool", {"name": name})
                self.assertEqual(st, 200)
                first_section = "当前错误" if from_result == "incorrect" else "当前薄弱"
                self.assertIn(first_section, pool_page)
                item = re.search(r'name="item_id" value="([^"]+)"', pool_page).group(1)
                st, study_page = self._post("/start", {"name": name, "item_id": item})
                self.assertEqual(st, 200)
                sid = re.search(r'name="session_id" value="([^"]+)"', study_page).group(1)
                lid = re.search(r'name="learner_id" value="([^"]+)"', study_page).group(1)
                self._post("/study", {"session_id": sid, "learner_id": lid, "item_id": item})
                st, done = self._post("/practice", {"session_id": sid, "learner_id": lid,
                                                    "item_id": item, "result": to_result})
                self.assertEqual(st, 200)
                self.assertIn("回忆：%s（practice · %s）"
                              % (page.RESULT_LABELS[to_result], to_result), done)
                st, pool_after = self._post("/pool", {"name": name})
                self.assertEqual(st, 200)
                if expected_section is None:
                    self.assertIn("当前没有需要再学的词", pool_after)
                else:
                    self.assertIn(expected_section, pool_after)

    # C2-B-7 池入口不得绕过 CORE 门禁（§十五）：非 CORE 条目仍不能进入学习
    def test_07_pool_entry_does_not_bypass_core_gate(self):
        cp = svc.connect_contentpack_db(page.CONTENTPACK)
        row = cp.execute("SELECT item_id, canonical_text FROM learning_item "
                         "WHERE item_type='vocabulary' AND learning_requirement='RECOGNITION' "
                         "ORDER BY item_id LIMIT 1").fetchone()
        cp.close()
        rec_item, rec_text = row["item_id"], row["canonical_text"]
        c = self._conn()
        lid = svc.create_learner(c, "小非核心")["learner_id"]
        s = ses.create_learning_session(c, lid, "vocabulary", [rec_item],
                                        contentpack_path=page.CONTENTPACK)
        beh.record_practice(c, lid, s["task_id"], rec_item, result="incorrect",
                            contentpack_path=page.CONTENTPACK)
        sessions_before = c.execute("SELECT COUNT(*) FROM learning_session WHERE learner_id=?",
                                    (lid,)).fetchone()[0]
        c.close()
        st, body = self._post("/pool", {"name": "小非核心"})
        self.assertEqual(st, 200)
        self.assertIn("当前错误", body)
        self.assertIn(rec_text, body)                       # 只展示真实教材文本
        self.assertNotIn('name="item_id"', body)            # 不提供进入按钮
        self.assertIn("不能从这个入口再次学习", body)          # 安全提示
        st, body = self._post("/start", {"name": "小非核心", "item_id": rec_item})
        self.assertEqual(st, 200)
        self.assertIn("不能从这个入口再次学习", body)
        c = self._conn()
        self.assertEqual(c.execute("SELECT COUNT(*) FROM learning_session WHERE learner_id=?",
                                   (lid,)).fetchone()[0], sessions_before,
                         "被门禁拒绝时不得创建新的 Session")
        self.assertEqual(c.execute("SELECT COUNT(*) FROM learning_record WHERE learner_id=? "
                                   "AND activity_type='study'", (lid,)).fetchone()[0], 0)
        c.close()


class PhraseRecallHttpTest(unittest.TestCase):
    """短语 Recall 流程（临时库 + **页面层测试替身**）。

    P1-10-C2 §三 冻结规则下，真实 contentpack 中"可进入 Recall 的短语"为 0 条
    （2 条 CORE 短语没有 meaning_zh）。因此这里只在**页面展示层**注入测试替身
    （临时内容，不写 contentpack、不写正式库），用于验证 Recall 真实链路：
    Session 生命周期 / 恰好一条 Record / 池映射 / 重复提交 / 非法值。
    """

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p110c2_recall_"))
        cls.tmp_db = cls.tmpdir / "learning_test.db"
        shutil.copyfile(page.LEARNING_DB, cls.tmp_db)
        page.Handler.db_path = cls.tmp_db
        page.Handler.contentpack_path = page.CONTENTPACK
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), page.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        cp = svc.connect_contentpack_db(page.CONTENTPACK)
        cls.phrases = [(r["item_id"], r["canonical_text"]) for r in cp.execute(
            "SELECT item_id, canonical_text FROM learning_item WHERE item_type='phrase' "
            "AND learning_requirement='CORE' ORDER BY item_id")]
        cp.close()
        cls._real_build_phrase_view = page.build_phrase_view

        def _view_with_recall(item_id, contentpack_path=page.CONTENTPACK):
            view = cls._real_build_phrase_view(item_id, contentpack_path)
            view["meaning_zh"] = "测试替身释义"
            view["recall_available"] = True
            return view

        page.build_phrase_view = _view_with_recall

    @classmethod
    def tearDownClass(cls):
        page.build_phrase_view = cls._real_build_phrase_view
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=5)
        for _ in range(10):
            try:
                shutil.rmtree(cls.tmpdir)
                break
            except Exception:
                import time
                time.sleep(0.2)

    def _post(self, path, data):
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def _conn(self):
        return svc.connect_learning_db(self.tmp_db)

    def _start_study(self, name, word):
        st, body = self._post("/start", {"name": name, "word": word, "kind": "phrase"})
        self.assertEqual(st, 200, body)
        sid = re.search(r'name="session_id" value="([^"]+)"', body).group(1)
        lid = re.search(r'name="learner_id" value="([^"]+)"', body).group(1)
        iid = re.search(r'name="item_id" value="([^"]+)"', body).group(1)
        st, body = self._post("/study", {"session_id": sid, "learner_id": lid, "item_id": iid})
        self.assertEqual(st, 200)
        return sid, lid, iid, body

    # C2-R-1 Study 后进入 Recall：Session 未结束、释义默认隐藏
    def test_01_study_enters_recall(self):
        _, word = self.phrases[0]
        sid, lid, iid, body = self._start_study("小短R1", word)
        self.assertIn("Phrase Recall", body)
        self.assertIn("你现在回忆得怎么样？", body)
        self.assertIn("显示释义", body)
        self.assertNotIn("测试替身释义", body)                   # 释义默认隐藏
        self.assertNotIn("重点词", body)
        c = self._conn()
        self.assertIsNone(c.execute("SELECT ended_at FROM learning_session WHERE session_id=?",
                                    (sid,)).fetchone()[0])
        self.assertEqual([tuple(r) for r in c.execute(
            "SELECT activity_type, result FROM learning_record WHERE learner_id=?", (lid,))],
            [("study", "done")])
        c.close()

    # C2-R-2 显示释义：只展示，不产生记录
    def test_02_reveal_writes_nothing(self):
        _, word = self.phrases[0]
        sid, lid, iid, _ = self._start_study("小短R2", word)
        st, body = self._post("/recall", {"session_id": sid, "learner_id": lid, "item_id": iid})
        self.assertEqual(st, 200)
        self.assertIn("测试替身释义", body)
        c = self._conn()
        self.assertEqual([tuple(r) for r in c.execute(
            "SELECT activity_type, result FROM learning_record WHERE learner_id=?", (lid,))],
            [("study", "done")])
        c.close()

    # C2-R-3 三种自评 → 恰好一条 practice + Session 结束 + 池映射
    def test_03_practice_mapping_and_pool(self):
        cases = (("correct", "记得", []), ("partial", "模糊", ["current_weak"]),
                 ("incorrect", "忘了", ["current_error"]))
        for index, (result, label, expected_pool) in enumerate(cases):
            _, word = self.phrases[index % len(self.phrases)]
            with self.subTest(result=result):
                sid, lid, iid, _ = self._start_study("小短R3-%d" % index, word)
                st, body = self._post("/practice", {"session_id": sid, "learner_id": lid,
                                                    "item_id": iid, "result": result})
                self.assertEqual(st, 200)
                self.assertIn("回忆：%s（practice · %s）" % (label, result), body)
                self.assertIn("已记录（study · done）", body)
                for forbidden in ("答对", "答错", "部分正确", "系统判定", "已掌握"):
                    self.assertNotIn(forbidden, body)
                c = self._conn()
                self.assertEqual([tuple(r) for r in c.execute(
                    "SELECT activity_type, result, attempt_no FROM learning_record "
                    "WHERE learner_id=? ORDER BY activity_type, attempt_no", (lid,))],
                    [("practice", result, 1), ("study", "done", 1)])
                self.assertIsNotNone(c.execute(
                    "SELECT ended_at FROM learning_session WHERE session_id=?", (sid,)).fetchone()[0])
                self.assertEqual([x["issue_type"] for x in pool.list_current_issue_pool(c, lid)],
                                 expected_pool)
                c.close()

    # C2-R-4 非法 result：400 + 零写入
    def test_04_illegal_result(self):
        _, word = self.phrases[0]
        sid, lid, iid, _ = self._start_study("小短R4", word)
        st, _ = self._post("/practice", {"session_id": sid, "learner_id": lid,
                                         "item_id": iid, "result": "xx"})
        self.assertEqual(st, 400)
        c = self._conn()
        self.assertEqual([tuple(r) for r in c.execute(
            "SELECT activity_type, result FROM learning_record WHERE learner_id=?", (lid,))],
            [("study", "done")])
        self.assertIsNone(c.execute("SELECT ended_at FROM learning_session WHERE session_id=?",
                                    (sid,)).fetchone()[0])
        c.close()

    # C2-R-5 重复提交：不产生第二条判断记录
    def test_05_duplicate_submit(self):
        _, word = self.phrases[0]
        sid, lid, iid, _ = self._start_study("小短R5", word)
        payload = {"session_id": sid, "learner_id": lid, "item_id": iid, "result": "correct"}
        st1, _ = self._post("/practice", payload)
        st2, body2 = self._post("/practice", payload)
        self.assertEqual((st1, st2), (200, 200))
        self.assertIn("回忆：记得（practice · correct）", body2)
        c = self._conn()
        self.assertEqual(len([r for r in c.execute(
            "SELECT 1 FROM learning_record WHERE learner_id=? AND activity_type='practice'",
            (lid,))]), 1)
        c.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)

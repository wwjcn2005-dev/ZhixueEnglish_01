#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-12-C3-C3 正式 Vocabulary 学习闭环测试（stdlib unittest，无新依赖）

覆盖任务书 §三十一 A–AD：Study / Recall / Practice / Result 全链路、
当前错误与当前薄弱池、重复提交、无效结果、异常页面、数据保护、AI = 0、
以及冻结文件（learning/*.py）与正式数据的完整性。

所有写入都发生在 %TEMP% 的 learning.db 副本；正式数据只读且哈希不变。
"""

from __future__ import annotations

import hashlib
import http.cookiejar
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
sys.dont_write_bytecode = True

import app as web_app                   # noqa: E402
import content as content_mod           # noqa: E402
import flow                             # noqa: E402

BASE = HERE.parent


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


#: 正式学习库的业务表（用于"本次测试没有非法修改真实学习数据"的保护）
BUSINESS_TABLES = ("learner", "learning_session", "learning_task", "task_item",
                   "learning_record", "mastery_state")


def business_counts(db_path) -> dict:
    conn = sqlite3.connect("file:%s?mode=ro" % Path(db_path).as_posix(), uri=True)
    try:
        return {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                for t in BUSINESS_TABLES}
    finally:
        conn.close()


OFFICIAL_DB_SHA = sha256_file(content_mod.LEARNING_DB)
CONTENTPACK_SHA = sha256_file(content_mod.CONTENTPACK)
#: P2-1-C1：正式库已包含真机真实学习数据，「业务表必须为 0 行」不再是有效基线；
#: 新的保护目标是"本次测试运行期间正式数据不得被修改或删除"。
OFFICIAL_DB_COUNTS = business_counts(content_mod.LEARNING_DB)
FROZEN_SERVICES = {
    "learning_service.py": "01341A05231EFCA6E0C801CF95D8A96F3DF732753F1F679688D44708586DF1D6",
    "session_service.py": "0CF7A20615780831F544BDF295202028CE2EEFB15D234820CD1184AD4A6B665F",
    "activity_service.py": "AAFF907C869797EE697D5F756C7E03C62CEB942809B2406933761195DA092028",
    "behavior_service.py": "0C6EF4822F60D9251B68382C95A5D3D9987650811F4FC93C70875AF48249FC6D",
    "vocabulary_service.py": "D06DCC76A5A4CCAF5C0BC3C17BB33CFF5D6056B7C872406A3934223C8870D632",
    "resource_pool_service.py": "D4488E1FFBA6B553EB6932BE195932A4C464D9526790B138C0C55DAA612D2F37",
}


def visible(body: str) -> str:
    text = re.sub(r"(?s)<style>.*?</style>", " ", body)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class VocabularyFlowTest(unittest.TestCase):
    """真实 HTTP + 临时 learning.db：完整学习闭环与池状态。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_c3c3_flow_"))
        cls.tmp_db = cls.tmpdir / "learning.db"
        shutil.copyfile(content_mod.LEARNING_DB, cls.tmp_db)
        web_app.Handler.learning_db = cls.tmp_db
        web_app.Handler.contentpack_path = content_mod.CONTENTPACK
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        # 真实 CORE Vocabulary（教材重点词）与一个非 CORE 词
        cp = content_mod._ro(content_mod.CONTENTPACK)
        row = cp.execute("SELECT item_id, canonical_text, phonetic, part_of_speech, meaning_zh "
                         "FROM learning_item WHERE item_type='vocabulary' AND canonical_text='ready'"
                         ).fetchone()
        cls.core_id, cls.core_word = row["item_id"], row["canonical_text"]
        cls.core_phonetic, cls.core_pos, cls.core_meaning = (row["phonetic"],
                                                            row["part_of_speech"],
                                                            row["meaning_zh"])
        rec = cp.execute("SELECT item_id, canonical_text FROM learning_item "
                         "WHERE item_type='vocabulary' AND learning_requirement='RECOGNITION' "
                         "ORDER BY item_id LIMIT 1").fetchone()
        cls.rec_id, cls.rec_word = rec["item_id"], rec["canonical_text"]
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

    # ---- HTTP 工具 ---------------------------------------------------------
    def _client(self):
        jar = http.cookiejar.CookieJar()
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def _get(self, opener, path):
        try:
            with opener.open("http://127.0.0.1:%d%s" % (self.port, path), timeout=10) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def _post(self, opener, path, data):
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with opener.open(req, timeout=10) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def _conn(self):
        return sqlite3.connect("file:%s?mode=ro" % self.tmp_db.as_posix(), uri=True)

    def _records(self, learner_id=None):
        conn = self._conn()
        sql = ("SELECT activity_type, result FROM learning_record "
               + ("WHERE learner_id=? " if learner_id else "")
               + "ORDER BY activity_type, attempt_no")
        args = (learner_id,) if learner_id else ()
        rows = [tuple(r) for r in conn.execute(sql, args)]
        conn.close()
        return rows

    def _pool_state(self, learner_id, item_id):
        conn = self._conn()
        row = conn.execute(
            "SELECT result FROM learning_record WHERE learner_id=? AND item_id=? "
            "AND result IN ('correct','incorrect','partial') "
            "ORDER BY created_at DESC, record_id DESC LIMIT 1", (learner_id, item_id)).fetchone()
        conn.close()
        return row[0] if row else None

    def _study(self, opener, name, item_id=None, key=None):
        """进入 Study（必要时先建立身份）。"""
        payload = {"pick": key} if key else {"item_id": item_id}
        if name:
            payload["name"] = name
        status, body = self._post(opener, "/vocabulary/study", payload)
        return status, body

    def _run_loop(self, opener, name, item_id, choice, reveal_first=False):
        """完整走一遍 Study → （显示意思）→ Recall 三选一 → Result。"""
        status, body = self._study(opener, name, item_id=item_id)
        self.assertEqual(status, 200, body)
        sid = re.search(r'name="session_id" value="([^"]+)"', body).group(1)
        lid = re.search(r'name="learner_id" value="([^"]+)"', body).group(1)
        pick = re.search(r'name="pick" value="([^"]+)"', body).group(1)
        status, recall = self._post(opener, "/vocabulary/study/done",
                                    {"session_id": sid, "pick": pick, "learner_id": lid})
        self.assertEqual(status, 200, recall)
        if reveal_first:
            status, recall = self._post(opener, "/vocabulary/recall/reveal",
                                        {"session_id": sid, "pick": pick, "learner_id": lid})
            self.assertEqual(status, 200)
        status, result = self._post(opener, "/vocabulary/practice",
                                    {"session_id": sid, "pick": pick, "learner_id": lid,
                                     "choice": choice})
        self.assertEqual(status, 200, result)
        return sid, lid, pick, recall, result

    # ---- A / B / D：Study 页面 --------------------------------------------
    def test_A_study_page_opens(self):
        opener = self._client()
        status, body = self._study(opener, "小甲", item_id=self.core_id)
        self.assertEqual(status, 200)
        self.assertIn("我看完了", body)
        self.assertIn("词汇", body)          # C4-09（已批准）：Study 页标签中文化

    def test_B_real_core_vocabulary_enters(self):
        opener = self._client()
        status, body = self._study(opener, "小乙", item_id=self.core_id)
        self.assertEqual(status, 200)
        self.assertIn(self.core_word, body)

    def test_C_non_core_is_rejected_without_bypass(self):
        opener = self._client()
        conn = self._conn()
        before = (conn.execute("SELECT COUNT(*) FROM learning_session").fetchone()[0],
                  conn.execute("SELECT COUNT(*) FROM learning_record").fetchone()[0])
        conn.close()
        status, body = self._study(opener, "小丙", item_id=self.rec_id)
        self.assertEqual(status, 200)
        self.assertIn("暂时不能在这里学习", body)
        conn = self._conn()
        after = (conn.execute("SELECT COUNT(*) FROM learning_session").fetchone()[0],
                 conn.execute("SELECT COUNT(*) FROM learning_record").fetchone()[0])
        conn.close()
        self.assertEqual(after, before, "非 CORE 不得创建 Session 或学习记录")

    def test_D_study_page_shows_real_fields(self):
        opener = self._client()
        _, body = self._study(opener, "小丁", item_id=self.core_id)
        self.assertIn(self.core_word, body)             # 真实单词
        if self.core_phonetic:
            self.assertIn(self.core_phonetic, body)     # 真实音标
        if self.core_pos:
            self.assertIn(self.core_pos, body)          # 真实词性
        if self.core_meaning:
            self.assertIn(self.core_meaning, body)      # 真实释义
        self.assertIn("教材来源", body)

    # ---- E / F：Study 记录与 Session 状态 ---------------------------------
    def test_E_F_study_records_done_and_keeps_session_open(self):
        opener = self._client()
        _, body = self._study(opener, "小戊", item_id=self.core_id)
        sid = re.search(r'name="session_id" value="([^"]+)"', body).group(1)
        lid = re.search(r'name="learner_id" value="([^"]+)"', body).group(1)
        pick = re.search(r'name="pick" value="([^"]+)"', body).group(1)
        status, recall = self._post(opener, "/vocabulary/study/done",
                                    {"session_id": sid, "pick": pick, "learner_id": lid})
        self.assertEqual(status, 200)
        self.assertEqual(self._records(lid), [("study", "done")])
        conn = self._conn()
        ended = conn.execute("SELECT ended_at FROM learning_session WHERE session_id=?",
                             (sid,)).fetchone()[0]
        conn.close()
        self.assertIsNone(ended, "Study 之后 Session 必须保持打开")
        # 重复提交「我看完了」不再产生第二条 study 记录
        self._post(opener, "/vocabulary/study/done",
                   {"session_id": sid, "pick": pick, "learner_id": lid})
        self.assertEqual(len(self._records(lid)), 1)

    # ---- G / H：Recall 默认隐藏 + 显示意思不写记录 -------------------------
    def test_G_H_recall_hidden_and_reveal_writes_nothing(self):
        opener = self._client()
        _, body = self._study(opener, "小己", item_id=self.core_id)
        sid = re.search(r'name="session_id" value="([^"]+)"', body).group(1)
        lid = re.search(r'name="learner_id" value="([^"]+)"', body).group(1)
        pick = re.search(r'name="pick" value="([^"]+)"', body).group(1)
        _, recall = self._post(opener, "/vocabulary/study/done",
                               {"session_id": sid, "pick": pick, "learner_id": lid})
        if self.core_meaning:
            self.assertNotIn(self.core_meaning, visible(recall), "Recall 默认必须隐藏意思")
        self.assertIn("显示意思", recall)
        before = self._records(lid)
        _, revealed = self._post(opener, "/vocabulary/recall/reveal",
                                 {"session_id": sid, "pick": pick, "learner_id": lid})
        if self.core_meaning:
            self.assertIn(self.core_meaning, visible(revealed))
        self.assertEqual(self._records(lid), before, "显示意思不得产生任何记录")

    # ---- I / J / K / L / M / N：三选一映射 ---------------------------------
    def test_I_to_N_choice_mapping_and_result(self):
        cases = (("remember", "correct", "我记得"), ("fuzzy", "partial", "有点模糊"),
                 ("forgot", "incorrect", "忘了"))
        for index, (choice, result, label) in enumerate(cases):
            with self.subTest(choice=choice):
                opener = self._client()
                sid, lid, _, _, result_page = self._run_loop(
                    opener, "小选%d" % index, self.core_id, choice)
                records = self._records(lid)
                self.assertEqual(records, [("practice", result), ("study", "done")])
                self.assertEqual(len([r for r in records if r[0] == "practice"]), 1,
                                 "三选一必须只产生一条 practice 记录")
                self.assertIn("你的回忆：%s" % label, result_page)     # Result 用孩子语言
                conn = self._conn()
                ended = conn.execute("SELECT ended_at FROM learning_session WHERE session_id=?",
                                     (sid,)).fetchone()[0]
                conn.close()
                self.assertIsNotNone(ended, "Practice 之后 Session 必须结束")

    # ---- Q / R / S / T / U：池状态 ----------------------------------------
    def test_Q_R_S_T_U_pool_states(self):
        import time
        opener = self._client()
        # incorrect → 当前错误
        sid, lid, _, _, _ = self._run_loop(opener, "小池", self.core_id, "forgot")
        self.assertEqual(self._pool_state(lid, self.core_id), "incorrect")
        # correct（换一条 session）→ 出池
        time.sleep(1.1)                       # 已知同秒 tie-break，不修复，只用可区分时间戳
        self._run_loop(opener, "小池", self.core_id, "remember")
        self.assertEqual(self._pool_state(lid, self.core_id), "correct")
        # 再次 incorrect → 重新进入错误池
        time.sleep(1.1)
        self._run_loop(opener, "小池", self.core_id, "forgot")
        self.assertEqual(self._pool_state(lid, self.core_id), "incorrect")
        # partial → 当前薄弱
        time.sleep(1.1)
        self._run_loop(opener, "小池", self.core_id, "fuzzy")
        self.assertEqual(self._pool_state(lid, self.core_id), "partial")
        # 通过池服务确认分组（不自行判断池状态）
        conn = sqlite3.connect("file:%s?mode=ro" % self.tmp_db.as_posix(), uri=True)
        conn.row_factory = sqlite3.Row
        import resource_pool_service as pool
        items = pool.list_current_issue_pool(conn, lid, contentpack_path=content_mod.CONTENTPACK)
        conn.close()
        self.assertEqual([(i["item_id"], i["issue_type"]) for i in items],
                         [(self.core_id, "current_weak")])

    # ---- V / W：重复提交与无效结果 ----------------------------------------
    def test_V_W_duplicate_and_invalid_choice(self):
        opener = self._client()
        sid, lid, pick, _, _ = self._run_loop(opener, "小重复", self.core_id, "remember")
        before = self._records(lid)
        status, body = self._post(opener, "/vocabulary/practice",
                                  {"session_id": sid, "pick": pick, "learner_id": lid,
                                   "choice": "remember"})
        self.assertEqual(status, 200)
        self.assertIn("你的回忆：我记得", body)          # 只读回放
        self.assertEqual(self._records(lid), before, "重复提交不得产生第二条记录")
        # 无效选项（新 Session）→ 不写库
        opener2 = self._client()
        _, body = self._study(opener2, "小无效", item_id=self.core_id)
        sid2 = re.search(r'name="session_id" value="([^"]+)"', body).group(1)
        lid2 = re.search(r'name="learner_id" value="([^"]+)"', body).group(1)
        pick2 = re.search(r'name="pick" value="([^"]+)"', body).group(1)
        self._post(opener2, "/vocabulary/study/done",
                   {"session_id": sid2, "pick": pick2, "learner_id": lid2})
        before2 = self._records(lid2)
        status, body = self._post(opener2, "/vocabulary/practice",
                                  {"session_id": sid2, "pick": pick2, "learner_id": lid2,
                                   "choice": "xxx"})
        self.assertEqual(status, 200)
        self.assertIn("请选择", body)
        self.assertEqual(self._records(lid2), before2, "无效结果不得写库")

    # ---- X：不存在的资源 → 自然错误页 -------------------------------------
    def test_X_missing_item_natural_error(self):
        opener = self._client()
        status, body = self._post(opener, "/vocabulary/study", {"pick": "deadbeefdead"})
        self.assertEqual(status, 200)
        self.assertIn("没有找到这个词", body)
        for leaked in ("Traceback", "sqlite3", "Exception", "item_id", "FLTRP-EN-7A-2022CUR"):
            self.assertNotIn(leaked, visible(body))

    # ---- O / P：Result 不暴露内部信息 ------------------------------------
    def test_O_P_result_has_no_internal_info(self):
        opener = self._client()
        _, _, _, _, result_page = self._run_loop(opener, "小隐", self.core_id, "fuzzy")
        text = visible(result_page)
        for leaked in ("correct", "incorrect", "partial", "study", "done", "CORE",
                       "RECOGNITION", "NEED_REVIEW", "mastery", "priority_score",
                       "attempt_no", "record_id", "session_id", "item_id",
                       "FLTRP-EN-7A-2022CUR", "正确率", "掌握率"):
            self.assertNotIn(leaked, text, "Result 不得出现：%s" % leaked)
        self.assertIn("你的回忆", text)
        for action in ("再学一次", "回到词汇表", "看看需要再学的"):
            self.assertIn(action, result_page)

    # ---- 刷新与返回 ------------------------------------------------------
    def test_refresh_replays_without_writing(self):
        opener = self._client()
        _, _, _, _, _ = self._run_loop(opener, "小刷新", self.core_id, "remember")
        before = self._records()
        status, body = self._get(opener, "/vocabulary/result")
        self.assertEqual(status, 200)
        self.assertIn("你的回忆：我记得", body)
        status, body = self._get(opener, "/vocabulary/recall")
        self.assertEqual(status, 200)
        self.assertIn("这次学习已经结束", body)
        self.assertEqual(self._records(), before, "刷新不得写库")

    # ---- 需要再学：与 Study 同一条链路 ------------------------------------
    def test_relearn_page_uses_same_study_chain(self):
        opener = self._client()
        sid, lid, _, _, _ = self._run_loop(opener, "小再学", self.core_id, "forgot")
        status, body = self._get(opener, "/review")
        self.assertEqual(status, 200)
        self.assertIn("上次忘了", body)
        self.assertIn(self.core_word, body)
        pick = re.search(r'name="pick" value="([^"]+)"', body).group(1)
        self.assertEqual(pick, flow.item_key(self.core_id))
        status, study = self._post(opener, "/vocabulary/study", {"pick": pick})
        self.assertEqual(status, 200)
        self.assertIn("我看完了", study)                 # 进入同一个 Study
        self.assertIn(self.core_word, study)


class VocabularyStatusTest(unittest.TestCase):
    """P1-13-C1：Vocabulary 学习状态可见化（C4-03 / C4-04 / C4-08 / C4-12 最小项）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p113c1_"))
        cls.tmp_db = cls.tmpdir / "learning.db"
        shutil.copyfile(content_mod.LEARNING_DB, cls.tmp_db)
        web_app.Handler.learning_db = cls.tmp_db
        web_app.Handler.contentpack_path = content_mod.CONTENTPACK
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        cp = content_mod._ro(content_mod.CONTENTPACK)
        cls.core_word = "ready"
        cls.core_id = cp.execute("SELECT item_id FROM learning_item WHERE item_type='vocabulary' "
                                 "AND canonical_text='ready'").fetchone()["item_id"]
        rec = cp.execute("SELECT item_id, canonical_text FROM learning_item "
                         "WHERE item_type='vocabulary' AND learning_requirement='RECOGNITION' "
                         "ORDER BY item_id LIMIT 1").fetchone()
        cls.rec_id, cls.rec_word = rec["item_id"], rec["canonical_text"]
        need = cp.execute("SELECT item_id, canonical_text FROM learning_item "
                          "WHERE item_type='vocabulary' AND learning_requirement='NEED_REVIEW' "
                          "ORDER BY item_id LIMIT 1").fetchone()
        cls.need_id, cls.need_word = ((need["item_id"], need["canonical_text"])
                                      if need else (None, None))
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

    # ---- 工具 -------------------------------------------------------------
    def _client(self):
        jar = http.cookiejar.CookieJar()
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def _get(self, opener, path, cookie=None):
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path))
        if cookie:
            req.add_header("Cookie", cookie)
        try:
            with opener.open(req, timeout=10) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def _post(self, opener, path, data):
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with opener.open(req, timeout=10) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def _conn(self):
        return sqlite3.connect("file:%s?mode=ro" % self.tmp_db.as_posix(), uri=True)

    def _db_sha(self):
        return sha256_file(self.tmp_db)

    def _learner_id(self, name):
        conn = self._conn()
        row = conn.execute("SELECT learner_id FROM learner WHERE display_name=?",
                           (name,)).fetchone()
        conn.close()
        return row[0] if row else None

    def _unit_list_url(self, item_id):
        unit = content_mod.unit_of_item(item_id, content_mod.CONTENTPACK)
        self.assertIsNotNone(unit, "测试词必须有单元归属")
        return "/unit/%s/resources/vocabulary" % unit["slug"]

    @staticmethod
    def _card(body, word):
        """取包含该词的条目卡片 HTML（按条目切块，用于逐条断言）。"""
        for block in body.split('<div class="item">')[1:]:
            if word in block:
                return block
        return ""

    def _pool_state(self, learner_id, item_id):
        conn = self._conn()
        row = conn.execute(
            "SELECT result FROM learning_record WHERE learner_id=? AND item_id=? "
            "AND result IN ('correct','incorrect','partial') "
            "ORDER BY created_at DESC, record_id DESC LIMIT 1", (learner_id, item_id)).fetchone()
        conn.close()
        return row[0] if row else None

    def _learn(self, name, item_id, choice=None):
        """用指定名字走一遍学习（首次会建立学习者并写 Cookie）；choice 为空则只做 Study。"""
        opener = self._client()
        status, body = self._post(opener, "/vocabulary/study",
                                  {"name": name, "item_id": item_id})
        self.assertEqual(status, 200, body)
        sid = re.search(r'name="session_id" value="([^"]+)"', body).group(1)
        pick = re.search(r'name="pick" value="([^"]+)"', body).group(1)
        learner_id = self._learner_id(name)
        self.assertIsNotNone(learner_id)
        status, _ = self._post(opener, "/vocabulary/study/done",
                               {"session_id": sid, "pick": pick, "learner_id": learner_id})
        self.assertEqual(status, 200)
        if choice:
            status, _ = self._post(opener, "/vocabulary/practice",
                                   {"session_id": sid, "pick": pick,
                                    "learner_id": learner_id, "choice": choice})
            self.assertEqual(status, 200)
        return learner_id

    # ---- 测试 1：没有学习记录 → 全部「未学」，CORE 仍有学习按钮 ------------
    def test_01_all_unseen_without_records(self):
        opener = self._client()
        status, _ = self._post(opener, "/review", {"name": "只看不学"})
        self.assertEqual(status, 200)
        learner_id = self._learner_id("只看不学")
        status, body = self._get(self._client(), self._unit_list_url(self.core_id),
                                 cookie="zx_learner=%s" % learner_id)
        self.assertEqual(status, 200)
        self.assertIn("状态：未学", body)
        self.assertNotIn("状态：已学", body)
        self.assertIn("学习这个词", body)
        self.assertIn("状态：未学", self._card(body, self.core_word))

    # ---- 测试 2：Study 完成 → 已学 ---------------------------------------
    def test_02_studied_after_study(self):
        learner_id = self._learn("只学不评", self.core_id)
        _, body = self._get(self._client(), self._unit_list_url(self.core_id),
                            cookie="zx_learner=%s" % learner_id)
        self.assertIn("状态：已学", self._card(body, self.core_word))

    # ---- 测试 3 / 4 / 5：忘了 / 有点模糊 / 记得 ---------------------------
    def test_03_forgot_shows_error_status(self):
        learner_id = self._learn("小忘了", self.core_id, choice="forgot")
        self.assertEqual(self._pool_state(learner_id, self.core_id), "incorrect")
        _, body = self._get(self._client(), self._unit_list_url(self.core_id),
                            cookie="zx_learner=%s" % learner_id)
        self.assertIn("状态：上次忘了", self._card(body, self.core_word))

    def test_04_partial_shows_weak_status(self):
        learner_id = self._learn("小模糊", self.core_id, choice="fuzzy")
        self.assertEqual(self._pool_state(learner_id, self.core_id), "partial")
        _, body = self._get(self._client(), self._unit_list_url(self.core_id),
                            cookie="zx_learner=%s" % learner_id)
        self.assertIn("状态：上次有点模糊", self._card(body, self.core_word))

    def test_05_correct_returns_to_studied(self):
        learner_id = self._learn("小记得", self.core_id, choice="correct")
        self.assertIsNone(self._pool_state(learner_id, self.core_id))
        _, body = self._get(self._client(), self._unit_list_url(self.core_id),
                            cookie="zx_learner=%s" % learner_id)
        self.assertIn("状态：已学", self._card(body, self.core_word))

    # ---- 测试 6：白体词（RECOGNITION）→ 普通字重 + 无说明标签 + 无按钮 -----
    def test_06_recognition_plain_weight_without_label(self):
        """P2-1-C1（C1-01）：教材白体词只以普通字重显示，不再加"认识即可"之类说明。"""
        status, body = self._get(self._client(), self._unit_list_url(self.rec_id))
        self.assertEqual(status, 200)
        card = self._card(body, self.rec_word)
        self.assertIn('class="w plain"', card)
        self.assertNotIn("认识一下", card)
        self.assertNotIn("学习这个词", card)
        for token in ("RECOGNITION", "CORE", "NEED_REVIEW", "current_error", "current_weak",
                      "item_id"):
            self.assertNotIn(token, body, "列表 HTML 不得出现内部字段：%s" % token)

    # ---- 测试 7：暂不能学习的内容 → 无按钮 + 无内部治理语言 ----------------
    def test_07_need_review_no_internal_language(self):
        """P2-1-C1（C1-04）：孩子端不得出现"教材确认/审核/NEED_REVIEW"等内部语言。"""
        if not self.need_id:
            self.skipTest("当前 contentpack 没有待确认的词汇")
        status, body = self._get(self._client(), self._unit_list_url(self.need_id))
        self.assertEqual(status, 200)
        card = self._card(body, self.need_word)
        for token in ("教材确认", "审核", "待确认", "暂时不能学习", "NEED_REVIEW"):
            self.assertNotIn(token, card, "不得向孩子暴露内部治理语言：%s" % token)
        self.assertNotIn("学习这个词", card)
        self.assertNotIn("NEED_REVIEW", body)

    # ---- 测试 8：首页计数跟随 Cookie learner -----------------------------
    def test_08_home_counts_follow_cookie_learner(self):
        learner_a = self._learn("小甲池", self.core_id, choice="forgot")
        opener_b = self._client()
        self._post(opener_b, "/review", {"name": "小乙空"})
        learner_b = self._learner_id("小乙空")
        self.assertNotEqual(learner_a, learner_b)
        # 第三版 Demo：「需要再学 / 最近学过」不再占首页，移到进展页（数量仍然跟随 Cookie）
        _, home_a = self._get(self._client(), "/", cookie="zx_learner=%s" % learner_a)
        self.assertNotIn("需要再学", visible(home_a), "首页不再显示需要再学数量")
        _, page_a = self._get(self._client(), "/progress", cookie="zx_learner=%s" % learner_a)
        _, page_b = self._get(self._client(), "/progress", cookie="zx_learner=%s" % learner_b)
        self.assertIn("需要再学：上次忘了 1 个", page_a)          # A：1 条「上次忘了」
        self.assertIn("目前还没有需要再学的内容", page_b)          # B：空
        # 无 Cookie：不猜测学习者 → 空状态
        _, page_none = self._get(self._client(), "/progress")
        self.assertIn("目前还没有需要再学的内容", page_none)

    # ---- 测试 9：列表 GET 零写入 -----------------------------------------
    def test_09_list_get_writes_nothing(self):
        opener = self._client()
        self._post(opener, "/review", {"name": "小只读"})
        learner_id = self._learner_id("小只读")
        tables = ("learner", "learning_session", "learning_task", "task_item",
                  "learning_record", "mastery_state")
        conn = self._conn()
        before = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in tables}
        conn.close()
        before_sha = self._db_sha()
        for _ in range(2):
            status, _ = self._get(self._client(), self._unit_list_url(self.core_id),
                                  cookie="zx_learner=%s" % learner_id)
            self.assertEqual(status, 200)
        self.assertEqual(self._db_sha(), before_sha, "列表 GET 不得写入数据库")
        conn = self._conn()
        after = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in tables}
        self.assertEqual(after, before)
        # 该学习者从未学习：列表 GET 不得为他产生任何学习数据
        for table in ("learning_session", "learning_record", "mastery_state"):
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM %s WHERE learner_id=?" % table,
                             (learner_id,)).fetchone()[0], 0,
                "列表 GET 不得为当前学习者写入 %s" % table)
        conn.close()

    # ---- 测试 10：列表 HTML 不泄漏任何内部字段 ---------------------------
    def test_10_list_has_no_internal_tokens(self):
        learner_id = self._learner_id("小忘了")          # 已学过的学习者（状态文字存在时也要干净）
        paths = {self._unit_list_url(self.core_id), self._unit_list_url(self.rec_id)}
        for path in paths:
            status, body = self._get(self._client(), path,
                                     cookie="zx_learner=%s" % learner_id)
            self.assertEqual(status, 200)
            for token in ("CORE", "RECOGNITION", "NEED_REVIEW", "current_error", "current_weak",
                          "item_id", "FLTRP-EN-7A-2022CUR", "contentpack", "mastery_state",
                          "session_id", "task_id"):
                self.assertNotIn(token, body, "%s 不得出现内部字段：%s" % (path, token))


class C2ExperienceTest(unittest.TestCase):
    """P1-13-C2：Study 来源说明（C4-06）、Recall 返回 Study 回放（C4-07）、
    标签中文化（C4-09）、引号统一（C4-10）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p113c2_"))
        cls.tmp_db = cls.tmpdir / "learning.db"
        shutil.copyfile(content_mod.LEARNING_DB, cls.tmp_db)
        web_app.Handler.learning_db = cls.tmp_db
        web_app.Handler.contentpack_path = content_mod.CONTENTPACK
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        cls.word = "ready"
        cp = content_mod._ro(content_mod.CONTENTPACK)
        cls.item_id = cp.execute("SELECT item_id FROM learning_item WHERE item_type='vocabulary' "
                                 "AND canonical_text='ready'").fetchone()["item_id"]
        cp.close()
        cls.view = flow.vocabulary_view(cls.item_id, content_mod.CONTENTPACK)
        cls.unit = content_mod.unit_of_item(cls.item_id, content_mod.CONTENTPACK)

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

    # ---- 工具 -------------------------------------------------------------
    def _client(self):
        jar = http.cookiejar.CookieJar()
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def _get(self, opener, path, cookie=None):
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path))
        if cookie:
            req.add_header("Cookie", cookie)
        try:
            with opener.open(req, timeout=10) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def _post(self, opener, path, data):
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with opener.open(req, timeout=10) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def _conn(self):
        return sqlite3.connect("file:%s?mode=ro" % self.tmp_db.as_posix(), uri=True)

    def _db_sha(self):
        return sha256_file(self.tmp_db)

    def _learner_id(self, name):
        conn = self._conn()
        row = conn.execute("SELECT learner_id FROM learner WHERE display_name=?",
                           (name,)).fetchone()
        conn.close()
        return row[0] if row else None

    def _start_study(self, name):
        """进入 Study 并把页面返回。"""
        opener = self._client()
        status, body = self._post(opener, "/vocabulary/study",
                                  {"name": name, "item_id": self.item_id})
        self.assertEqual(status, 200, body)
        return opener, body, self._learner_id(name)

    # ---- C4-06：Study 来源拆成两行，全部来自真实教材数据 ------------------
    def test_C406_study_source_lines(self):
        opener, body, _ = self._start_study("小来源")
        self.assertIn("教材来源", body)
        self.assertIn("出自：", body)
        self.assertIn("词表：", body)
        # 单元信息来自真实教材数据（unit_code + 单元标题）
        self.assertIn(self.unit["unit_code"], body)
        self.assertIn(self.unit["title"], body)
        # 词表栏目与词表页来自真实 source_ref
        self.assertIn(self.view["source_list_label"], body)
        self.assertIn("第", body)
        # 两行语义分开：不是把单元与词表页混成一行
        self.assertIn("出自：%s" % self.view["source_unit_label"], body)
        self.assertIn("词表：%s" % self.view["source_list_label"], body)

    # ---- C4-09：Study 页标签中文化 ---------------------------------------
    def test_C409_study_label_is_chinese(self):
        _, body, _ = self._start_study("小标签")
        self.assertIn("词汇", body)
        self.assertNotIn("Vocabulary", body, "Study 页不应再出现英文 UI 标签")

    # ---- C4-10：Recall 提示引号统一 ---------------------------------------
    def test_C410_recall_quote_unified(self):
        opener, body, learner_id = self._start_study("小引号")
        sid = re.search(r'name="session_id" value="([^"]+)"', body).group(1)
        pick = re.search(r'name="pick" value="([^"]+)"', body).group(1)
        status, recall = self._post(opener, "/vocabulary/study/done",
                                    {"session_id": sid, "pick": pick,
                                     "learner_id": learner_id})
        self.assertEqual(status, 200)
        self.assertIn("「忘了」", recall)
        self.assertNotIn('"忘了"', recall)

    # ---- C4-07：Recall 返回到 Study 回放；回放只读且可显示对应词 ----------
    def test_C407_recall_back_to_study_replay(self):
        opener, body, learner_id = self._start_study("小回放")
        sid = re.search(r'name="session_id" value="([^"]+)"', body).group(1)
        pick = re.search(r'name="pick" value="([^"]+)"', body).group(1)
        status, recall = self._post(opener, "/vocabulary/study/done",
                                    {"session_id": sid, "pick": pick,
                                     "learner_id": learner_id})
        self.assertEqual(status, 200)
        # 第三版 Demo：返回统一成顶部栏的返回图标，目标仍然是 Study
        self.assertIn('class="tb-back" href="/vocabulary/study"', recall)
        self.assertIn("返回学习", recall)
        # 只读回放：显示同一个词，且不写库、不新建任何数据
        before_sha = self._db_sha()
        conn = self._conn()
        before = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                  for t in ("learning_session", "learning_task", "task_item",
                            "learning_record", "mastery_state")}
        conn.close()
        status, replay = self._get(opener, "/vocabulary/study")
        self.assertEqual(status, 200)
        self.assertIn(self.word, replay)
        self.assertIn("我看完了", replay)
        self.assertEqual(self._db_sha(), before_sha, "Study 回放必须零写入")
        conn = self._conn()
        after = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                 for t in ("learning_session", "learning_task", "task_item",
                           "learning_record", "mastery_state")}
        conn.close()
        self.assertEqual(after, before)

    # ---- C4-07：无效 / 缺失 / 已结束时的自然语言页面（无 traceback） ------
    def test_C407_replay_error_paths(self):
        # 无 Cookie
        status, body = self._get(self._client(), "/vocabulary/study")
        self.assertEqual(status, 200)
        self.assertIn("请先选一个词", body)
        # 无效 session
        status, body = self._get(self._client(), "/vocabulary/study",
                                 cookie="zx_session=NOT-A-SESSION; zx_item=%s" % self.item_id)
        self.assertEqual(status, 200)
        self.assertIn("请先选一个词", body)
        # 已结束的 session → 引导看结果
        opener, page, learner_id = self._start_study("小结束")
        sid = re.search(r'name="session_id" value="([^"]+)"', page).group(1)
        pick = re.search(r'name="pick" value="([^"]+)"', page).group(1)
        self._post(opener, "/vocabulary/study/done",
                   {"session_id": sid, "pick": pick, "learner_id": learner_id})
        self._post(opener, "/vocabulary/practice",
                   {"session_id": sid, "pick": pick, "learner_id": learner_id,
                    "choice": "remember"})
        status, body = self._get(opener, "/vocabulary/study")
        self.assertEqual(status, 200)
        self.assertIn("这次学习已经结束", body)
        self.assertIn("看看结果", body)
        for leaked in ("Traceback", "sqlite3", "Exception", "session_id"):
            self.assertNotIn(leaked, body)


class RecentStudiedTest(unittest.TestCase):
    """P1-13-C3-G1：首页「最近学过」真实化（只读 mastery_state，最多 5 条）。"""

    #: Demo V1.1：首页改成课堂同步首页，「最近学过」列表移动到「我的进展」页。
    #: 本组用例的检查点（真实数据 / 诚实空态 / 排序 / 上限 / 原始字段 / 入口复用 / 零写入）
    #: 全部保持不变，只把访问的页面跟着产品结构调整。
    RECENT_PAGE = "/progress"

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p113c3g1_"))
        cls.tmp_db = cls.tmpdir / "learning.db"
        shutil.copyfile(content_mod.LEARNING_DB, cls.tmp_db)
        web_app.Handler.learning_db = cls.tmp_db
        web_app.Handler.contentpack_path = content_mod.CONTENTPACK
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        cp = content_mod._ro(content_mod.CONTENTPACK)
        cls.words = [(r["item_id"], r["canonical_text"]) for r in cp.execute(
            "SELECT item_id, canonical_text FROM learning_item "
            "WHERE item_type='vocabulary' AND learning_requirement='CORE' "
            "ORDER BY item_id LIMIT 6")]
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

    # ---- 工具 -------------------------------------------------------------
    def _client(self):
        jar = http.cookiejar.CookieJar()
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def _get(self, opener, path, cookie=None):
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path))
        if cookie:
            req.add_header("Cookie", cookie)
        try:
            with opener.open(req, timeout=10) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def _post(self, opener, path, data, cookie=None):
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        if cookie:
            req.add_header("Cookie", cookie)
        try:
            with opener.open(req, timeout=10) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def _ro(self):
        return sqlite3.connect("file:%s?mode=ro" % self.tmp_db.as_posix(), uri=True)

    def _rw(self):
        """可写连接（**仅指向 %TEMP% 副本**，用于按冻结服务写入真实学习数据）。"""
        conn = sqlite3.connect(str(self.tmp_db))
        conn.row_factory = sqlite3.Row
        conn.isolation_level = None
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _db_sha(self):
        return sha256_file(self.tmp_db)

    def _seed_learner(self, name, count, start_hour=9):
        """用冻结服务写入 count 条真实学习记录（时间戳递增，便于验证排序）。"""
        import session_service as ses
        import vocabulary_service as voc
        import learning_service as svc
        conn = self._rw()
        try:
            learner_id = svc.create_learner(conn, name)["learner_id"]
            for index, (item_id, _word) in enumerate(self.words[:count]):
                session = ses.create_learning_session(conn, learner_id, "vocabulary", [item_id])
                voc.record_vocabulary_study(conn, session["session_id"], item_id,
                                            learner_id=learner_id, result="done",
                                            created_at="2026-09-12T%02d:%02d:00+08:00"
                                                       % (start_hour, index))
            return learner_id
        finally:
            conn.close()

    # ---- G1-01：无当前 learner → 空态 ------------------------------------
    def test_G1_01_empty_without_learner(self):
        status, body = self._get(self._client(), self.RECENT_PAGE)
        self.assertEqual(status, 200)
        self.assertIn("还没有学过内容", body)
        self.assertNotIn("再学一次", body)

    # ---- G1-02 / G1-03 / G1-04 / G1-05：真实数据、排序、上限、真实文本 ---
    def test_G1_02_to_05_recent_list(self):
        learner_id = self._seed_learner("小最近", 6)
        cookie = "zx_learner=%s" % learner_id
        status, body = self._get(self._client(), self.RECENT_PAGE, cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn("最近学过", body)
        self.assertNotIn("还没有学过内容", body)
        # G1-04：最多 5 条
        self.assertEqual(body.count('<div class="item">'), 5)
        # G1-03：按 last_practiced_at DESC（最新在前的 5 条，最早的第 6 条不出现）
        recent_words = [w for _i, w in reversed(self.words[:6])][:5]
        for word in recent_words:
            self.assertIn(word, body)
        # 最早那条（index 0）不显示；只看页面可见文本，避免命中 CSS/SVG 属性里的词
        self.assertNotIn(self.words[0][1], visible(body))
        positions = [body.index(w) for w in recent_words]
        self.assertEqual(positions, sorted(positions), "最近学过的顺序应为最近在前")
        # G1-05：文本来自真实 contentpack（单词 + 音标/词性/释义，有则显示）
        cp = content_mod._ro(content_mod.CONTENTPACK)
        row = cp.execute("SELECT canonical_text, phonetic, part_of_speech, meaning_zh "
                         "FROM learning_item WHERE item_id=?",
                         (self.words[5][0],)).fetchone()
        cp.close()
        self.assertIn(row["canonical_text"], body)
        if row["phonetic"]:
            self.assertIn(row["phonetic"], body)
        if row["part_of_speech"]:
            self.assertIn("%s." % row["part_of_speech"], body)
        if row["meaning_zh"]:
            self.assertIn(row["meaning_zh"], body)

    # ---- G1-06：点击最近学习项目 → 进入现有安全学习入口 ------------------
    def test_G1_06_entry_uses_existing_study_route(self):
        learner_id = self._seed_learner("小入口", 2)
        cookie = "zx_learner=%s" % learner_id
        _, body = self._get(self._client(), self.RECENT_PAGE, cookie=cookie)
        cards = body.split('<div class="item">')[1:]
        self.assertTrue(cards)
        card = cards[0]
        self.assertIn('action="/vocabulary/study"', card)
        pick = re.search(r'name="pick" value="([^"]+)"', card).group(1)
        status, study = self._post(self._client(), "/vocabulary/study", {"pick": pick},
                                   cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn("我看完了", study)                   # 进入既有 Study（不是新机制）

    # ---- G1-07：首页 GET 零写入 -----------------------------------------
    def test_G1_07_home_get_writes_nothing(self):
        learner_id = self._seed_learner("小只读", 2)
        cookie = "zx_learner=%s" % learner_id
        tables = ("learner", "learning_session", "learning_task", "task_item",
                  "learning_record", "mastery_state")
        conn = self._ro()
        before = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in tables}
        conn.close()
        before_sha = self._db_sha()
        for _ in range(2):
            status, _body = self._get(self._client(), self.RECENT_PAGE, cookie=cookie)
            self.assertEqual(status, 200)
        self.assertEqual(self._db_sha(), before_sha, "我的进展页 GET 不得写入数据库")
        conn = self._ro()
        after = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in tables}
        conn.close()
        self.assertEqual(after, before)

    # ---- G1-08：不调用 AI ------------------------------------------------
    def test_G1_08_no_ai_in_home_path(self):
        for name in ("app.py", "ui.py", "content.py", "flow.py"):
            src = (HERE / name).read_text(encoding="utf-8").lower()
            for token in ("openai", "deepseek", "ollama", "anthropic", "requests.",
                          "http.client", "socket.", "transformers", "torch",
                          "tensorflow", "tts", "ocr"):
                self.assertNotIn(token, src, "%s 不应包含 AI/网络调用" % name)


class DataSafetyTest(unittest.TestCase):
    """Y / Z / AA / AD：正式数据、contentpack、AI 调用与冻结服务。"""

    def test_Y_official_db_untouched(self):
        self.assertEqual(sha256_file(content_mod.LEARNING_DB), OFFICIAL_DB_SHA)
        # P2-1-C1：正式库已有真机真实学习数据 → 保护"未被修改/未被删除"，而不是"必须为空"
        self.assertEqual(business_counts(content_mod.LEARNING_DB), OFFICIAL_DB_COUNTS,
                         "正式 learning.db 的真实学习数据不得被本次测试修改或删除")

    def test_Z_contentpack_unchanged(self):
        self.assertEqual(sha256_file(content_mod.CONTENTPACK), CONTENTPACK_SHA)

    def test_AA_no_ai_or_network_calls(self):
        for name in ("app.py", "ui.py", "content.py", "flow.py"):
            src = (HERE / name).read_text(encoding="utf-8").lower()
            for token in ("openai", "deepseek", "ollama", "anthropic", "requests.",
                          "http.client", "socket.", "transformers", "torch",
                          "tensorflow", "tts", "ocr"):
                self.assertNotIn(token, src, "%s 不得包含 AI/TTS/OCR/外部调用：%s" % (name, token))

    def test_AD_frozen_learning_services_unchanged(self):
        for name, expected in FROZEN_SERVICES.items():
            self.assertEqual(sha256_file(BASE / "learning" / name), expected,
                             "%s 属冻结文件，不得修改" % name)

    def test_AE_previous_web_routes_still_present(self):
        src = (HERE / "app.py").read_text(encoding="utf-8")
        for route in ('"/"', '"/textbook"', '"/health"', '"/review"',
                      '"/vocabulary/study"', '"/vocabulary/study/done"',
                      '"/vocabulary/recall/reveal"', '"/vocabulary/practice"'):
            self.assertIn(route, src, "原有/新增路由不得丢失：%s" % route)


if __name__ == "__main__":
    unittest.main(verbosity=2)

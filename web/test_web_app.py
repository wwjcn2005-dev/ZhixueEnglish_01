#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-12-C3-C1 正式 Web UI 最小骨架测试（stdlib unittest，无新依赖）

覆盖（任务书 §十六 A–G）：
  A 服务可启动 ｜ B GET / ｜ C GET /health ｜ D 首页可返回（含 404 → 回首页）
  E contentpack 可读 ｜ F learning 服务可导入 ｜ G 正式 learning.db 未污染

另覆盖：首页不是 Workbench、C3-A 固定色值存在、不出现内部枚举/技术信息、
        不出现 AI/网络调用痕迹、Android 侧地址配置与正式服务端口一致。

所有需要数据库的检查都只在 %TEMP% 的 learning.db 副本上进行（本测试甚至不起写连接）。
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
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

import app as web_app                   # noqa: E402
import content as content_mod           # noqa: E402
import demo_data as demo                # noqa: E402
import ui                               # noqa: E402


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


#: 正式学习库的业务表（保护"本次测试没有非法修改真实学习数据"）
BUSINESS_TABLES = ("learner", "learning_session", "learning_task", "task_item",
                   "learning_record", "mastery_state")


def business_counts(db_path) -> dict:
    conn = sqlite3.connect("file:%s?mode=ro" % Path(db_path).as_posix(), uri=True)
    try:
        return {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                for t in BUSINESS_TABLES}
    finally:
        conn.close()


# 导入即冻结：用于证明测试未污染正式数据
OFFICIAL_DB_SHA = sha256_file(content_mod.LEARNING_DB)
CONTENTPACK_SHA = sha256_file(content_mod.CONTENTPACK)
#: P2-1-C1：正式库已包含真机真实学习数据，「业务表必须为 0 行」不再是有效基线。
OFFICIAL_DB_COUNTS = business_counts(content_mod.LEARNING_DB)


class ContentTest(unittest.TestCase):
    """E / F：contentpack 与 learning 层可读（真实数据，只读）。"""

    def test_01_contentpack_readable(self):
        info = content_mod.read_textbook(content_mod.CONTENTPACK)
        tb = info["textbook"]
        self.assertIsNotNone(tb)
        self.assertEqual(tb["publisher"], "外语教学与研究出版社")
        self.assertEqual(tb["title"], "义务教育教科书·英语 七年级上册")
        self.assertEqual(tb["grade"], "7")
        counts = info["counts"]
        # 与已知基线一致（真实读取，不是前端硬编码）
        self.assertEqual(counts["unit"], 8)
        self.assertEqual(counts["section"], 46)
        self.assertEqual(counts["activity"], 96)
        # P2-1-C1（C1-02）补回 yourself → 363；P2-2 新增 93 条教材练习条目 → 456
        # P2-3 按真实教材 PDF 重扫，补回 P2-2 漏掉的 64 个教材活动 → 520（157 条练习）
        self.assertEqual(counts["item"], 520)
        self.assertEqual(counts["vocabulary"], 288)
        self.assertEqual(counts["phrase"], 23)
        self.assertEqual(counts["sentence_pattern"], 52)
        self.assertEqual(counts["vocabulary_core"], 244)

    def test_02_learning_services_importable(self):
        import learning_service as svc
        import resource_pool_service as pool
        self.assertTrue(hasattr(svc, "record_learning_event"))
        self.assertTrue(hasattr(pool, "summarize_pool"))
        self.assertEqual(svc.now_iso()[:2], "20")          # 可调用，且不写库

    def test_03_home_context_is_honest_without_learner(self):
        """P2-1-C1：不指定学习者时，首页上下文必须如实返回空状态（不猜测任何学习者）。"""
        ctx = content_mod.home_context(content_mod.LEARNING_DB, content_mod.CONTENTPACK)
        # 学习者数量来自真实数据（真机学习后可能不为 0），但"需要再学"不得凭空猜测
        self.assertEqual(ctx["learner_count"], len(content_mod.list_learners(
            content_mod.LEARNING_DB)))
        self.assertEqual(ctx["pool"]["total"], 0)
        self.assertIsNone(ctx["learner_name"])
        self.assertEqual(ctx["recent_count"], 0)

    def test_04_content_layer_is_read_only(self):
        src = (HERE / "content.py").read_text(encoding="utf-8").lower()
        for token in ("insert into", "update ", "delete from", "create table", "alter table",
                      "drop table"):
            self.assertNotIn(token, src, "内容层不得包含任何写操作：%s" % token)
        self.assertIn("mode=ro", src)                      # 正式数据一律只读打开


class HomePageTest(unittest.TestCase):
    """首页渲染：产品名 / 真实教材 / 空状态 / C3-A 视觉基线 / 无内部枚举。"""

    @classmethod
    def setUpClass(cls):
        ctx = content_mod.home_context(content_mod.LEARNING_DB, content_mod.CONTENTPACK)
        cls.html = ui.home_page(ctx)

    def test_01_product_and_textbook(self):
        self.assertIn("智学英语", self.html)
        # Demo V1.2：首页顶部只保留“七年级上册英语 + 章节选择”，
        # 出版社 / 课标 / 时间统计等都不再出现在首页。
        self.assertIn("七年级上册英语", self.html)
        self.assertIn("开始教材学习", self.html)

    def test_02_empty_states_are_honest(self):
        # Demo V1.1/V1.2：首页 = 章节选择 / AI 随堂助教 / 今日10分钟 / 我的进展。
        # 第三版 Demo（本轮）：首页 =「今天学什么」＝ 章节选择 → 功能入口列表（课文点读在最后）。
        # 首页不再放 AI 随堂助教卡片，也没有「我的进展」一级入口；
        # 「需要再学 / 最近学过」的诚实空态移到进展页（见下面 progress 检查）。
        for token in ("七年级上册英语", "今天学什么", "开始教材学习"):
            self.assertIn(token, self.html, "首页必须回答：学到哪里 / 今天做什么")
        text = re.sub(r"(?s)<style>.*?</style>", " ", self.html)
        text = re.sub(r"(?s)<script>.*?</script>", " ", text)
        visible = re.sub(r"<[^>]+>", " ", text)
        self.assertNotIn('<section class="ai">', self.html)   # AI 分析不在首页堆卡片
        self.assertNotIn("我的进展", visible)
        self.assertNotIn("AI助教", visible)
        # 进展页（第三版：不再是首页内容）仍然如实显示空状态
        pctx = content_mod.home_context(content_mod.LEARNING_DB, content_mod.CONTENTPACK)
        pctx["unit_slug"] = "unit1"
        pctx["classroom"] = {"book": "七年级上册英语", "unit_code": "Unit 1",
                             "unit_title": "A new start"}
        pctx["parent_progress"] = demo.parent_progress()
        pctx["attention"] = []
        page = ui.progress_page(pctx)
        self.assertIn("目前还没有需要再学的内容", page)
        self.assertIn("最近学过", page)
        # 只看页面可见文本（去掉 style/script），避免命中 CSS 注释里的词
        for bad in ("外语教学与研究出版社", "义务教育教科书", "课程标准", "本周已学习",
                    "今天已经学习", "学习时长"):
            self.assertNotIn(bad, text, "Demo V1.2：首页不得再出现这些信息：%s" % bad)
        for forbidden in ("恭喜", "完美", "已全部掌握", "积分", "排名", "徽章", "连续"):
            self.assertNotIn(forbidden, self.html, "首页不得出现游戏化/断言文案：%s" % forbidden)

    def test_03_c3a_palette_present(self):
        for color in ("#F6F7F9", "#FFFFFF", "#17181A", "#6B7078", "#9298A1", "#E7E9ED",
                      "#1677FF", "#00A8E8", "#18A566", "#F59E0B", "#E5484D"):
            self.assertIn(color, ui.STYLE, "缺少 C3-A 固定色值：%s" % color)

    def test_04_no_internal_leaks(self):
        for leaked in ("session_id", "task_id", "item_id", "contentpack", "CORE",
                       "study", "done", "current_error", "current_weak",
                       "FLTRP-EN-7A-2022CUR", ".sqlite", "localhost", "127.0.0.1", "Workbench"):
            self.assertNotIn(leaked, self.html, "首页不得出现内部信息：%s" % leaked)

    def test_05_mobile_layout_basics(self):
        self.assertIn('name="viewport"', self.html)
        self.assertIn("max-width:560px", ui.STYLE)          # 单列、移动优先
        self.assertIn("border-radius:16px", ui.STYLE)       # 卡片圆角 12–16dp

    def test_06_not_found_page_returns_home(self):
        page = ui.not_found_page("/nope")
        self.assertIn("没有找到这个页面", page)
        self.assertIn('href="/"', page)                     # 可以返回首页


class HttpTest(unittest.TestCase):
    """A / B / C / D：真实 HTTP 往返（临时 learning.db 副本）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_c3c1_web_"))
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
        for _ in range(10):
            try:
                shutil.rmtree(cls.tmpdir)
                break
            except Exception:
                import time
                time.sleep(0.2)

    def _get(self, path):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path),
                                        timeout=10) as r:
                return r.status, dict(r.headers), r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read().decode("utf-8")

    def test_01_get_home(self):
        status, headers, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("Content-Type", ""))
        self.assertIn("智学英语", body)
        self.assertIn("开始教材学习", body)

    def test_02_health(self):
        status, headers, body = self._get("/health")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("Content-Type", ""))
        self.assertEqual(json.loads(body)["status"], "ok")

    def test_03_unknown_path_404(self):
        status, _, body = self._get("/nope")
        self.assertEqual(status, 404)
        self.assertIn("没有找到这个页面", body)

    def test_04_browsing_writes_nothing(self):
        before = sha256_file(self.tmp_db)
        before_counts = business_counts(self.tmp_db)
        for path in ("/", "/health", "/nope", "/"):
            self._get(path)
        self.assertEqual(sha256_file(self.tmp_db), before, "浏览不得写入任何数据")
        # P2-1-C1：副本来自正式库（已含真实学习数据）→ 保护"浏览不产生任何新数据"
        self.assertEqual(business_counts(self.tmp_db), before_counts,
                         "服务不得产生任何学习数据")


class SafetyTest(unittest.TestCase):
    """G：正式数据未被污染 + 无 AI/网络调用痕迹。"""

    def test_01_official_data_untouched(self):
        self.assertEqual(sha256_file(content_mod.LEARNING_DB), OFFICIAL_DB_SHA,
                         "正式 learning.db 未被修改")
        self.assertEqual(sha256_file(content_mod.CONTENTPACK), CONTENTPACK_SHA,
                         "contentpack 未被修改")
        # P2-1-C1：正式库已有真机真实学习数据 → 保护"未被修改/未被删除"
        self.assertEqual(business_counts(content_mod.LEARNING_DB), OFFICIAL_DB_COUNTS,
                         "正式学习数据不得被本次测试修改或删除")

    def test_02_no_ai_or_network_calls(self):
        for name in ("app.py", "ui.py", "content.py"):
            src = (HERE / name).read_text(encoding="utf-8").lower()
            for token in ("openai", "deepseek", "ollama", "anthropic", "requests.",
                          "urllib.request", "http.client", "socket.", "transformers",
                          "torch", "tensorflow"):
                self.assertNotIn(token, src, "%s 不应包含 AI/网络调用：%s" % (name, token))

    def test_03_android_base_url_matches_web_service(self):
        """Android 侧地址配置必须指向本项目的正式 Web 服务端口（8770），不得指向其它项目。"""
        android_app = (HERE.parent / "android" / "app" / "build.gradle.kts")
        if not android_app.exists():
            self.skipTest("Android 工程尚未创建")
        src = android_app.read_text(encoding="utf-8")
        self.assertIn("8770", src)
        self.assertNotIn("ZhixueAI", src)
        self.assertNotIn("zhixueai", src.lower())


class TextbookDataTest(unittest.TestCase):
    """P1-12-C3-C2：教材中心 / Unit / 资源列表的数据层（全部来自真实 contentpack）。"""

    def test_01_units_real_and_stably_ordered(self):
        units = content_mod.list_units(content_mod.CONTENTPACK)
        self.assertEqual(len(units), 8)                      # 与真实基线一致
        self.assertEqual([u["unit_code"] for u in units],
                         ["Starter", "Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5",
                          "Unit 6", "Appendix"])
        pages = [u["textbook_page_start"] for u in units]
        self.assertEqual(pages, sorted(pages), "单元必须按教材自然顺序稳定排序")
        # 两次读取顺序完全一致（稳定性）
        self.assertEqual([u["slug"] for u in units],
                         [u["slug"] for u in content_mod.list_units(content_mod.CONTENTPACK)])

    def test_02_unit_lookup_by_slug(self):
        self.assertEqual(content_mod.get_unit("unit1", content_mod.CONTENTPACK)["unit_code"],
                         "Unit 1")
        self.assertEqual(content_mod.get_unit("STARTER", content_mod.CONTENTPACK)["unit_code"],
                         "Starter")
        self.assertIsNone(content_mod.get_unit("nope", content_mod.CONTENTPACK))
        self.assertIsNone(content_mod.get_unit("", content_mod.CONTENTPACK))

    def test_03_resource_counts_are_computed_not_hardcoded(self):
        counts = content_mod.unit_resource_counts(content_mod.CONTENTPACK)
        # 每个单元的三类资源数量都来自程序计算；总数必须等于教材条目总数
        totals = {"vocabulary": 0, "phrase": 0, "sentence-pattern": 0}
        for unit_counts in counts.values():
            for kind, n in unit_counts.items():
                totals[kind] += n
        self.assertEqual(totals["vocabulary"], 288)         # P2-1-C1：补回 yourself
        self.assertEqual(totals["phrase"], 23)
        self.assertEqual(totals["sentence-pattern"], 52)
        # Unit 1 的真实构成（与 contentpack 现状一致）
        u1 = counts["Unit 1"]
        self.assertEqual((u1["vocabulary"], u1["phrase"], u1["sentence-pattern"]), (35, 3, 6))
        # P2-1-C1（C1-02）：教材词表条目与 contentpack 对齐
        self.assertEqual(counts["Starter"]["vocabulary"], 32)      # 教材 Starter 词表 32 条
        self.assertEqual(counts["Unit 2"]["vocabulary"], 45)       # smile 归回 Unit 2
        self.assertEqual(counts.get("Appendix", {}).get("vocabulary", 0), 0)

    def test_04_resource_items_use_real_fields_only(self):
        data = content_mod.list_unit_resources("unit1", "vocabulary", content_mod.CONTENTPACK)
        self.assertEqual(len(data["items"]), 35)
        first = data["items"][0]
        self.assertTrue(first["text"])
        self.assertIn("basis", first)                        # 保留归属证据（教材印刷页/来源页）
        self.assertIsNotNone(first["page"])
        # P2-1-C1（C1-03）：Vocabulary 必须按**教材印刷词表顺序**排列（reading_order），
        # 不再使用（印刷页号, 词形）排序；顺序稳定且每条都有教材顺序证据。
        orders = [i["order"] for i in data["items"]]
        self.assertTrue(all(o for o in orders), "每个词条都必须有教材词表顺序证据")
        self.assertEqual(orders, sorted(orders), "必须按教材词表顺序稳定排列")
        self.assertEqual(first["text"], "without", "Unit 1 词表第一条是 without（教材顺序）")
        patterns = content_mod.list_unit_resources("unit1", "sentence-pattern",
                                                  content_mod.CONTENTPACK)
        self.assertTrue(all("{" not in i["text"] for i in patterns["items"]),
                        "句型必须使用面向孩子的展示文本（不含 {1} 槽位）")
        phrases = content_mod.list_unit_resources("unit1", "phrase", content_mod.CONTENTPACK)
        self.assertTrue(all(i["text"] for i in phrases["items"]))

    def test_05_unknown_unit_or_kind_returns_none(self):
        self.assertIsNone(content_mod.list_unit_resources("nope", "vocabulary",
                                                          content_mod.CONTENTPACK))
        self.assertIsNone(content_mod.list_unit_resources("unit1", "nope",
                                                          content_mod.CONTENTPACK))
        self.assertEqual(content_mod.kind_label("nope"), "")


class TextbookHttpTest(unittest.TestCase):
    """P1-12-C3-C2：首页 → 教材中心 → Unit → 资源列表（真实 HTTP，临时 learning.db）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_c3c2_web_"))
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
        for _ in range(10):
            try:
                shutil.rmtree(cls.tmpdir)
                break
            except Exception:
                import time
                time.sleep(0.2)

    def _get(self, path):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path),
                                        timeout=10) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def test_01_home_links_to_textbook(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("开始教材学习", body)
        self.assertIn('href="/textbook"', body)
        self.assertNotIn("/health", body, "首页不应暴露接口清单")

    def test_02_textbook_center(self):
        status, body = self._get("/textbook")
        self.assertEqual(status, 200)
        self.assertIn("义务教育教科书·英语 七年级上册", body)
        self.assertIn("外语教学与研究出版社", body)
        for code in ("Starter", "Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "Unit 6",
                     "Appendix"):
            self.assertIn(code, body, "教材中心必须来自真实 contentpack：%s" % code)
        self.assertEqual(body.count('class="unitrow"'), 8)
        self.assertIn('href="/"', body)                        # 返回首页
        # 顺序稳定：Starter 必须出现在 Appendix 之前
        self.assertLess(body.index("Starter"), body.index("Appendix"))

        self.assertIn("Unit 1", body)

    def test_04_resource_lists(self):
        status, body = self._get("/unit/unit1/resources/vocabulary")
        self.assertEqual(status, 200)
        self.assertIn("without", body)                         # 真实词条
        self.assertIn("缺乏没有", body)                          # 真实释义
        self.assertIn("按教材出现顺序排列", body)
        self.assertIn('href="/"', body)                        # P6-B-12c：旧 Unit 宿主已退役，返回首页
        self.assertEqual(body.count('class="item"'), 35)
        status, body = self._get("/unit/starter/resources/phrase")
        self.assertEqual(status, 200)
        self.assertIn("junior high", body)
        self.assertEqual(body.count('class="item"'), 9)
        status, body = self._get("/unit/appendix/resources/sentence-pattern")
        self.assertEqual(status, 200)
        self.assertEqual(body.count('class="item"'), 18)
        self.assertNotIn("{1}", body)

    def test_05_error_pages_are_natural(self):
        for path in ("/unit/nope", "/unit/unit1/resources/nope", "/unit/unit1/bad"):
            status, body = self._get(path)
            self.assertEqual(status, 404, path)
            self.assertTrue(("没有找到这个单元" in body) or ("没有找到这类内容" in body)
                            or ("没有找到这个页面" in body), path)
            for leaked in ("Traceback", "sqlite3", "FileNotFoundError", "item_id", "unit_id",
                           "resource_id", "Exception"):
                self.assertNotIn(leaked, body, "%s 泄漏了内部信息：%s" % (path, leaked))

    def test_06_no_internal_leaks_on_navigation_pages(self):
        for path in ("/", "/textbook", "/unit/unit1", "/unit/unit1/resources/vocabulary",
                     "/unit/unit1/resources/phrase", "/unit/unit1/resources/sentence-pattern"):
            _, body = self._get(path)
            for leaked in ("CORE", "RECOGNITION", "NEED_REVIEW", "FLTRP-EN-7A-2022CUR",
                           "item_id", "unit_id", "contentpack", ".sqlite", "current_error",
                           "current_weak", "session_id", "task_id", "Workbench"):
                self.assertNotIn(leaked, body, "%s 不得出现内部信息：%s" % (path, leaked))

    def test_07_back_links_are_stable(self):
        _, body = self._get("/textbook")
        self.assertIn('href="/"', body)
        _, body = self._get("/unit/unit1")
        self.assertIn('href="/"', body)                       # 收口：Unit 页返回首页
        for kind in ("vocabulary", "phrase", "sentence-pattern"):
            _, body = self._get("/unit/unit1/resources/%s" % kind)
            self.assertIn('href="/"', body)                   # P6-B-12c：资源页返回首页

    def test_08_browsing_creates_no_learning_data(self):
        before_counts = business_counts(self.tmp_db)
        for path in ("/", "/textbook", "/unit/unit1/resources",
                     "/unit/unit1/resources/vocabulary", "/unit/starter/resources/phrase",
                     "/unit/appendix/resources/sentence-pattern"):
            status, _ = self._get(path)
            self.assertEqual(status, 200, path)
        # P2-1-C1：副本来自正式库（已含真实学习数据）→ 保护"浏览不新增任何数据"
        self.assertEqual(business_counts(self.tmp_db), before_counts,
                         "教材浏览不得创建 Learner / Session / Task / LearningRecord")


class VocabularyFlowRoutesTest(unittest.TestCase):
    """P1-12-C3-C3：正式 Vocabulary 学习闭环的路由与实现边界。

    详细的学习流程（Study/Recall/Practice/Result 与池状态）见
    `web/test_vocabulary_flow.py`；这里只做路由存在性与实现纪律的检查。
    """

    def test_01_vocabulary_routes_registered(self):
        src = (HERE / "app.py").read_text(encoding="utf-8")
        for route in ('"/vocabulary/study"', '"/vocabulary/study/done"',
                      '"/vocabulary/recall/reveal"', '"/vocabulary/practice"',
                      '"/vocabulary/recall"', '"/vocabulary/result"', '"/review"'):
            self.assertIn(route, src, "缺少正式学习路由：%s" % route)

    def test_02_flow_reuses_frozen_services(self):
        src = (HERE / "flow.py").read_text(encoding="utf-8")
        for service in ("vocabulary_service", "session_service",
                        "resource_pool_service", "learning_service"):
            self.assertIn("import %s" % service, src,
                          "学习闭环必须复用冻结服务：%s" % service)
        lowered = src.lower()
        for write in ("insert into", "update ", "delete from", "create table", "alter table"):
            self.assertNotIn(write, lowered,
                             "编排层不得自己写学习数据（应交由冻结服务）：%s" % write)
        self.assertIn("entry_point=\"vocabulary\"", src)

    def test_03_no_new_activity_type_or_table(self):
        app_src = (HERE / "app.py").read_text(encoding="utf-8").lower()
        flow_src = (HERE / "flow.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("activity_type='recall'", app_src + flow_src)
        self.assertNotIn("create table", app_src + flow_src)
        # 三选一映射保持冻结语义
        self.assertIn('("remember", "我记得", "correct")', (HERE / "flow.py").read_text(encoding="utf-8"))
        self.assertIn('("fuzzy", "有点模糊", "partial")', (HERE / "flow.py").read_text(encoding="utf-8"))
        self.assertIn('("forgot", "忘了", "incorrect")', (HERE / "flow.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

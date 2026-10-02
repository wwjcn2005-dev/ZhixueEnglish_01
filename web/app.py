#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-12-C3-C1 正式 Web UI 最小骨架 —— Python HTTP 服务

这是**正式产品 Web UI 的起点**（不是 Workbench）：只使用 Python 标准库，
不引入任何第三方框架；服务本身**只读**，不写 learning.db，不产生学习记录，不调用 AI。

第一阶段只提供：
    GET /        首页（学习导航大厅最小版本）
    GET /health  机器可读健康检查：{"status":"ok"}

用法：
    python D:\ZhixueEnglish\web\app.py                 # 默认 0.0.0.0:8770（手机可访问）
    python D:\ZhixueEnglish\web\app.py --port 8770 --host 0.0.0.0
    python D:\ZhixueEnglish\web\app.py --host 127.0.0.1   # 仅本机

说明：正式 Web 服务默认监听局域网地址，便于 Android WebView 通过 http://<本机IP>:8770/ 访问；
本机 IP 可在启动日志中看到。开发阶段仅用于本机/局域网，属第一版最小闭环。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import random
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import content as content_mod          # noqa: E402
import audio as audio_mod              # noqa: E402
import demo_data as demo               # noqa: E402
import exercises as ex_mod             # noqa: E402
import flow                            # noqa: E402
import learning_service as svc         # noqa: E402
import pdf_pages                       # noqa: E402
import session_service as ses          # noqa: E402
import study_call_service as scs       # noqa: E402  P6-A：正式学习调用层
import ui                              # noqa: E402

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8770
SERVER_NAME = "ZhixueEnglish-WebUI/0.1"

#: Demo V1.1 修正：本机演示学习状态（章节隔离；只在学习行为发生时改变）
DEMO_STATE_COOKIE = "zx_demo"

#: 错题池（演示，本机 Cookie）：只是学习证据，不写正式 learning.db
WRONG_POOL_COOKIE = "zx_wrong"

#: 只读派生缓存：教材正文与「其它单元句子池」（contentpack 只读，运行期不会变化）
_SENTENCE_POOL_CACHE = {}


def _text_section_count(handler, slug):
    """「听读课文」入口的显隐依据：该 Unit **有正文 Section 的个数**（非题目数）。

    与 /unit/<slug>/text 页同源（同一个 `unit_text_sections`），
    保证「首页入口显隐」与「次页实际内容」一致，不以题目数代替。
    读失败时返回 0（入口不显示），异常不在此吞掉——由调用方记录并暴露。
    """
    data = content_mod.unit_text_sections(slug, handler.contentpack_path)
    # 实测返回 dict：{"unit_code","title","textbook_page_*","sections":[...],"block_count"}
    if not isinstance(data, dict):
        return 0
    sections = data.get("sections") or []
    return sum(1 for s in sections if isinstance(s, dict) and (s.get("blocks") or []))


class Handler(BaseHTTPRequestHandler):
    learning_db = content_mod.LEARNING_DB
    contentpack_path = content_mod.CONTENTPACK
    server_version = SERVER_NAME

    # ---- 内部状态传递（只用于服务逻辑，绝不展示给孩子） ----------------------
    def _cookies(self) -> dict:
        out = {}
        for part in (self.headers.get("Cookie") or "").split(";"):
            if "=" in part:
                key, value = part.strip().split("=", 1)
                out[key.strip()] = urllib.parse.unquote(value.strip())
        return out

    def _set_cookie(self, name: str, value: str):
        if not hasattr(self, "_pending_cookies"):
            self._pending_cookies = []
        self._pending_cookies.append(
            "%s=%s; Path=/; HttpOnly; SameSite=Lax" % (name, urllib.parse.quote(value)))

    # ---- 输出 ---------------------------------------------------------------
    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for cookie in getattr(self, "_pending_cookies", []):
            self.send_header("Set-Cookie", cookie)
        self._pending_cookies = []
        self.end_headers()
        self.wfile.write(body)

    def _html(self, text: str, code: int = 200):
        self._send(code, text.encode("utf-8"), "text/html; charset=utf-8")

    def _json(self, payload: dict, code: int = 200):
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    # ---- P2-1-C1 教材音频（只读静态音频；不写任何数据、不调用 AI） ------------
    AUDIO_MIME = {".mp3": "audio/mpeg", ".wav": "audio/wav"}

    def _audio(self, path: str):
        """`/audio/official/<AUxx>.mp3` 与 `/audio/word/<key>.wav`。

        只允许解析到数据库/清单里登记过的音频；绝不受 URL 控制文件路径。
        """
        rel = path[len("/audio/"):]
        target = None
        if rel.startswith("official/"):
            name = rel[len("official/"):]
            if name.endswith(".mp3") and "/" not in name:
                target = audio_mod.resolve_official_audio(name[:-4], self.contentpack_path)
        elif rel.startswith("word/"):
            name = rel[len("word/"):]
            if name.endswith(".wav") and "/" not in name:
                target = audio_mod.resolve_word_audio(name[:-4])
        if target is None:
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        self._send_file(target)

    def _send_file(self, path):
        """最小静态音频响应（支持 Range，便于手机/WebView 边下边播）。"""
        try:
            size = path.stat().st_size
        except OSError:
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        start, end, code = 0, max(size - 1, 0), 200
        rng = (self.headers.get("Range") or "").strip()
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)$", rng)
            if m and (m.group(1) or m.group(2)):
                start = int(m.group(1)) if m.group(1) else 0
                end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", "bytes */%d" % size)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                code = 206
        length = end - start + 1
        self.send_response(code)
        self.send_header("Content-Type", self.AUDIO_MIME.get(
            path.suffix.lower(), "application/octet-stream"))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if code == 206:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with open(path, "rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(1 << 16, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _conn(self):
        """学习库连接（业务读写全部经冻结 service；本类不直接写任何表）。"""
        return svc.connect_learning_db(self.learning_db)

    # ---- 路由 ---------------------------------------------------------------
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/audio/"):
            self._audio(path)
            return
        if path.startswith("/page/") and path.endswith(".jpg"):
            self._page_image(path)
            return
        if path in ("/", "/index.html"):
            self._home()
            return
        if path in ("/learn", "/learn/"):
            self._textbook()
            return
        if path in ("/progress", "/progress/"):
            self._progress()
            return
        if path in ("/textbook", "/textbook/"):
            self._textbook()
            return
        if path.startswith("/unit/"):
            self._unit_path(path)
            return
        if path.startswith("/exercise/"):
            self._exercise_get(path)
            return
        if path in ("/review", "/review/"):
            self._review()
            return
        if path == "/vocabulary/recall":
            self._recall_get()
            return
        if path == "/vocabulary/result":
            self._result_get()
            return
        if path == "/vocabulary/study":
            self._study_get()
            return
        if path == "/health":
            self._json({"status": "ok", "service": SERVER_NAME})
            return
        self._html(ui.not_found_page(path), 404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        form = self._form()
        if path == "/vocabulary/study":
            return self._study_start(form)
        if path == "/vocabulary/study/done":
            return self._study_done(form)
        if path == "/vocabulary/recall/reveal":
            return self._recall_reveal(form)
        if path == "/vocabulary/practice":
            return self._practice(form)
        if path == "/review":
            return self._review(form)
        if path == "/demo/learn":
            # Demo V1.1 修正：只有学习行为（跟读 / 练习 / 课文点读）会走这里
            return self._demo_learn(form)
        if path == "/demo/wrong":
            # 错题池（演示）：每次作答都会来这里记录一次（含答对时改善状态）
            return self._demo_wrong(form)
        if path.startswith("/unit/") and "/p5/" in path and path.endswith("/repeat"):
            # 2026-10-01：跟读"完成" = 录完音即算 ⇒ 录音结束时前端 POST 到这里记一次。
            return self._p5_repeat(path, form)
        if path.startswith("/unit/") and "/p5/" in path and path.endswith("/submit"):
            # P6-A：正式题库作答（后端逐题调用正式学习调用层）
            return self._p5_submit(path, form)
        if path.startswith("/exercise/") and path.endswith("/submit"):
            return self._exercise_submit(path, form)
        self._send(404, b"not found", "text/plain; charset=utf-8")

    # ---- 工具：自然语言错误页（不暴露任何内部信息） --------------------------
    def _natural_error(self, title: str, message: str, back_href: str = "/textbook",
                       back_label: str = "回到教材中心", code: int = 200):
        self._html(ui.error_page(title, message, back_href, back_label), code)

    def _form(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}

    # ---- 页面（全部只读：不写 learning.db、不产生学习记录） --------------------
    def _home(self):
        try:
            # 2026-10-01（learner cookie 修复）：首页改用**可自愈**解析 —— cookie 失效时
            # 回退到库中真实 learner 并回写 cookie；否则六入口学习状态会全显「未开始」。
            learner_id = self._resolve_valid_learner()
            unit = self._query_unit()
            training = self._unit_training(unit)
            state = self._demo_state()
            chapter_ai, focus, steps = self._chapter_ai(unit, training, state)
            ctx = content_mod.home_context(self.learning_db, self.contentpack_path,
                                           learner_id=learner_id)
            ctx["units"] = content_mod.list_units(self.contentpack_path)
            ctx["unit_slug"] = unit["slug"]
            ctx["learner_id"] = learner_id        # 首页统一身份（解析后的有效值）
            # P6-B-13：首页「当前课时」= 教材真实目录 Unit → Section（全部真实 Section，不做题库过滤）
            ctx["catalog"] = content_mod.list_units_with_sections(self.contentpack_path)
            # P6-B-11：Lesson（正式来源 contentpack.section.section_key）成为学习上下文
            ctx["lessons"], ctx["lesson_key"] = self._lessons_for(unit)
            ctx["classroom"] = self._classroom(unit, training)
            ctx["ai"] = chapter_ai
            ctx["parent_progress"] = demo.parent_progress(unit["unit_code"])
            # P6-B-UI-RESTORE-05：首页选择的是 Lesson（section_key），入口链接显式携带当前 Lesson。
            lesson_key = (ctx.get("lesson_key") or "").strip()
            # P6-A：今天学什么 = 正式六入口
            # P6-B-12-FIX S1：入口显隐与文案按**当前 Section 的真实可调用资源**判定——
            #   复用与功能页**完全相同**的池函数 `_p5_items`（同一 learner / Section / 模式），
            #   不以 Unit 资源总量代替当前 Section；非教学块（Appendix）由 demo.formal_entries
            #   显式处理（不调用教学 Unit 专属池、不依赖异常被吞掉）；
            #   池函数抛错时不再静默清空入口 —— 异常向上抛出，由外层记录并暴露，便于发现真实问题。
            ctx["entries"] = demo.formal_entries(
                unit["unit_code"], unit["slug"], learner_id,
                pool=lambda key, mode: self._p5_items(unit, key, learner_id, mode=mode,
                                                      lesson_key=lesson_key),
                modes={"read": tuple(m for m, _ in ui._P5_READ_MODES),
                       "listen": tuple(m for m, _ in ui._P5_LISTEN_MODES),
                       # 「听读课文」不属题目池：显隐按**该 Unit 有正文的 Section 数**显式表达
                       # （2026-09-30 升级为菜单入口；V1.3 第二十九章 §15·7）。
                       "text": (_text_section_count(self, unit["slug"]),)},
                # 2026-10-01（UI-7 第 2 件）：入口状态改用「未开始 / 正在进行 / 已完成」，
                # 判据 = 该入口候选池题目集合在 learning_record 的证据覆盖（只读）。
                learning_db=self.learning_db,
                section_key=lesson_key,
                entry_questions=self.entry_questions)
            if lesson_key:
                for e in ctx["entries"]:
                    if "lesson=" not in (e.get("href") or ""):
                        e["href"] += ("&" if "?" in e["href"] else "?") + \
                                     "lesson=" + urllib.parse.quote(lesson_key)
        except Exception as exc:                       # 自然语言错误，不暴露技术细节
            print("[web] 首页数据读取失败：%r" % (exc,))
            self._html(ui.error_page("首页暂时打不开", "请稍后再试。", "/", "重试"), 200)
            return
        self._html(ui.home_page(ctx))

    # ---- Demo V1.1：课堂位置 / 今日特训数据装配（全部只读） -----------------
    def _lesson_rows(self, unit):
        """当前 Unit 的正式 Lesson：只保留 questionbank 中确实有正式题目的 section。"""
        try:
            cp = scs.connect_contentpack(self.contentpack_path)
        except Exception:
            return []
        try:
            rows = list(cp.execute(
                "SELECT s.section_key, s.title FROM section s JOIN unit u ON u.unit_id = s.unit_id "
                "WHERE u.unit_code = ? ORDER BY s.pdf_page_start, s.section_key",
                (unit["unit_code"],)))
        except Exception:
            rows = []
        finally:
            cp.close()
        try:
            qb = scs.connect_questionbank()
        except Exception:
            return []
        try:
            have = set(r[0] for r in qb.execute(
                "SELECT DISTINCT section_key FROM question WHERE unit_code = ?",
                (unit["unit_code"],)) if r[0])
        finally:
            qb.close()
        return [{"key": r[0], "title": (r[1] or r[0])} for r in rows if r[0] in have]

    def _lessons_for(self, unit):
        """(lessons, lesson_key)：URL ?lesson= → Cookie zx_lesson → 当前 Unit 第一个真实 Section。

        P6-B-13：候选来自 contentpack 的**全部真实 Section**（`list_units_with_sections()`），
        不再按 questionbank 是否有题过滤 —— 与首页「当前课时」目录同一数据源，因此选择
        `Presenting ideas` 等暂无正式题的 Section 时**不再被错误回退**。
        `_lesson_rows()` 的"只保留有正式题 Section"语义保持不变，继续供其它用途使用。
        Cookie 与 Unit 绑定：不属于当前 Unit 的 lesson_key 一律回退，不会跨 Unit 复用。
        """
        lessons = []
        if unit:
            try:
                for u in content_mod.list_units_with_sections(self.contentpack_path):
                    if u["slug"] == unit.get("slug"):
                        lessons = [{"key": s["section_key"], "title": s["title"]}
                                   for s in (u.get("sections") or [])]
                        break
            except Exception as exc:                   # noqa: BLE001 —— 目录读不到按"无课时"处理
                print("[web] 课时目录读取失败：%r" % (exc,))
                lessons = []
        keys = [l["key"] for l in lessons]
        if not keys:
            return [], ""
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        want = (qs.get("lesson") or [""])[0].strip()
        # 2026-10-01（UI-7 第 1 件）：**显式切换 Unit 时重置课时**。
        # 判据：URL 同时给了 ?unit= 与 ?lesson=，而该 lesson 不属于这个 Unit
        # ⇒ 视为"换单元"，回到该 Unit 第一课（不把别的 Unit 的课时带过来）。
        url_unit = (qs.get("unit") or [""])[0].strip().lower()
        if url_unit and want and want not in keys:
            self._set_cookie("zx_lesson", keys[0])
            return lessons, keys[0]
        if want and want in keys:
            self._set_cookie("zx_lesson", want)
            return lessons, want
        if not want:
            cur = (self._cookies().get("zx_lesson") or "").strip()
            if cur in keys:
                return lessons, cur
        return lessons, keys[0]

    def _query_unit(self):
        """当前课堂单元：`?unit=<slug>` → **Cookie `zx_unit`** → 演示主单元。

        2026-10-01（UI-7 第 1 件）：新增 `zx_unit` Cookie。
        为什么需要它：原先只有**课时**有 Cookie（`zx_lesson`）而**单元没有** ——
        返回首页走 `/`（不带 `?unit=`）时单元回到默认 Unit 1，而 Cookie 里的课时属于另一个
        Unit ⇒ `_lessons_for()` 因"该课时不属于当前 Unit"把它丢掉 ⇒ **显示默认课时**。
        现在把用户明确选择过的单元也记住；**URL 显式指定优先于 Cookie**（便于分享 / 调试）。
        """
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        slug = (qs.get("unit") or [""])[0].strip().lower()
        unit = None
        if slug:
            try:
                unit = content_mod.get_unit(slug, self.contentpack_path)
            except Exception as exc:
                print("[web] 课堂单元读取失败：%r" % (exc,))
                unit = None
            if unit is not None:
                self._set_cookie("zx_unit", unit["slug"])
                return unit
        # URL 未指定（或无效）→ 用 Cookie 记住的单元
        remembered = (self._cookies().get("zx_unit") or "").strip().lower()
        if remembered:
            try:
                unit = content_mod.get_unit(remembered, self.contentpack_path)
            except Exception as exc:
                print("[web] 已记单元读取失败：%r" % (exc,))
                unit = None
            if unit is not None:
                return unit
        return content_mod.get_unit(demo.DEMO_UNIT_SLUG, self.contentpack_path)

    def _classroom(self, unit, training):
        pages = ""
        if unit.get("textbook_page_start") and unit.get("textbook_page_end"):
            pages = "%s–%s" % (unit["textbook_page_start"], unit["textbook_page_end"])
        return demo.classroom(unit["unit_code"], unit.get("title") or "", pages,
                              len(training["sentences"]))

    # ---- Demo V1.1 修正：章节学习状态（本机 Cookie）与章节内容分析 -----------
    def _demo_state(self) -> dict:
        """本机演示学习状态（按章节隔离；打开页面不会改变它）。"""
        return demo.parse_state(self._cookies().get(DEMO_STATE_COOKIE) or "")

    def _wrong_pool(self) -> dict:
        """本机错题池（演示）：读 Cookie；打开页面不会改变它。"""
        return demo.parse_pool(self._cookies().get(WRONG_POOL_COOKIE) or "")

    def _demo_wrong(self, form):
        """记录一次作答结果到错题池（答错入池 / 答对改善状态）。零写库。"""
        pool = self._wrong_pool()
        entry = {"qid": (form.get("qid") or "").strip(),
                 "unit": (form.get("unit") or "").strip().lower(),
                 "kind": (form.get("kind") or "").strip(),
                 "correct": (form.get("correct") or "").strip(),
                 "answer": (form.get("answer") or "").strip()}
        ok = (form.get("ok") or "").strip() == "1"
        if entry["qid"]:
            demo.note_answer(pool, entry, ok, at=int(time.time()))
            self._set_cookie(WRONG_POOL_COOKIE, demo.dump_pool(pool))
        self._send(204, b"", "text/plain; charset=utf-8")

    def _demo_learn(self, form):
        """记录一次学习行为（跟读 / 练习 / 课文点读）→ 只有它会改变章节状态。"""
        slug = (form.get("unit") or "").strip().lower()
        step = (form.get("step") or "").strip().lower()
        state = self._demo_state()
        if slug not in (None, "") and step in demo.DEMO_STEP_KEYS:
            picked = state.setdefault(slug, {})
            value = "partial" if (form.get("result") or "").strip() == "partial" else "done"
            # 已经完整做过就不再退回 partial（阶段性最好成绩）
            if picked.get(step) != "done":
                picked[step] = value
            self._set_cookie(DEMO_STATE_COOKIE, demo.dump_state(state))
        nxt = (form.get("next") or "").strip()
        if nxt.startswith("/") and "//" not in nxt[1:]:
            self._redirect(nxt)
            return
        self._send(204, b"", "text/plain; charset=utf-8")

    def _content_focus(self, unit, training):
        """当前章节的真实教材重点内容（词汇 / 短语 / 句型），供 AI 说明“该学什么”。"""
        text = training.get("unit_text") or ""
        in_text, rest = [], []
        for word in training["words"]:
            if not word.get("meaning"):
                continue
            hit = re.search(r"\b%s\b" % re.escape(word["text"]), text, re.I)
            (in_text if hit else rest).append(word)
        vocabulary = [(w["text"], w["meaning"]) for w in (in_text + rest)[:3]]
        used = {t.lower() for t, _ in vocabulary}
        phrases = [(p["text"], p.get("meaning") or "") for p in training["phrases"]
                   if p["text"].lower() not in used][:2]
        uids = {s.get("sentence_uid") for s in training["sentences"]}
        for expr in demo.SENTENCE_EXPRESSIONS:
            if expr["uid"] in uids and expr["text"].lower() not in used:
                phrases.append((expr["text"], expr["meaning"]))
        patterns = [(p["text"], "按这个句型换词说一句")
                    for p in (training.get("patterns") or [])][:3]
        return {"vocabulary": vocabulary, "phrases": phrases[:3], "patterns": patterns,
                "key_points": self._key_points(unit, training)}

    def _key_points(self, unit, training):
        """这一章最值得先学的 3 个知识点（全部来自真实教材，按学习价值排序）。

        Demo V1.2 §五：AI 只帮孩子挑最重要的，不分类、不罗列整章知识点。
        """
        points, used = [], set()

        def push(text, note):
            key = (text or "").strip().lower()
            if key and key not in used and len(points) < 3:
                used.add(key)
                points.append((text, note))

        uids = {s.get("sentence_uid") for s in training["sentences"]}
        for expr in demo.SENTENCE_EXPRESSIONS:          # 教材句子里的表达（高价值）
            if expr["uid"] in uids:
                push(expr["text"], "%s · 换个句子再用一次" % expr["meaning"])
        text = training.get("unit_text") or ""
        for word in training["words"]:                  # 出现在本课课文里的重点词
            if not word.get("meaning"):
                continue
            if re.search(r"\b%s\b" % re.escape(word["text"]), text, re.I):
                push(word["text"], "%s · 换个语境再读一次" % word["meaning"])
        for phrase in training["phrases"]:              # 教材短语
            if phrase.get("meaning"):
                push(phrase["text"], "%s · 在句子里用一次" % phrase["meaning"])
        for pattern in training.get("patterns") or []:  # 教材句型
            push(pattern["text"], "按这个句型换词说一句")
        return points

    def _chapter_ai(self, unit, training, state=None):
        """当前章节的 AI 随堂助教内容（由章节内容 + 该章节学习状态推导）。"""
        state = self._demo_state() if state is None else state
        steps = demo.steps_of(state, unit["slug"])
        focus = self._content_focus(unit, training)
        return demo.chapter_ai(unit["unit_code"], focus, steps), focus, steps

    # ---- P6-A：正式题库练习页（题目 / 素材 / 学习记录全部经 study_call_service） ----
    #: 正式六入口（产品与UI架构总纲 V2.0 §5.1 固定顺序）
    P5_ENTRY_LABELS = {"read": "跟读练习", "listen": "听音辨意", "wordform": "词形练习",
                       "check": "本课检测", "text": "听读课文", "practice": "自主练习"}

    #: P6-B-11 S1：教材/Lesson 型题型（严格跟随当前 Lesson 的 section_key）
    P5_LESSON_TYPES = ("textbook_native", "sentence_listen_write", "sentence_listen_choice",
                       "reading_choice", "listening_choice", "phonetics_sound_choice",
                       "phonetics_symbol_write", "listen_choice", "listen_fill",
                       "vocab_phonetic_write", "vocab_word_form")
    #: P6-B-11 S1：词表 / 短语 / 附录型题型（保持其正式 Unit / Appendix 粒度，不参与 Lesson 过滤）
    P5_VOCAB_TYPES = ("vocab_meaning_choice", "vocab_listen_write", "vocab_phonetic_write",
                      "vocab_context_choice", "vocab_word_form", "phrase_meaning_choice")

    def lesson_question_count(self, entry, unit_code, section_key=""):
        """**当前课时题目数**（UI-7 第 4 件）：该入口在"当前课时"范围内应有的题目数。

        与入口候选池**同源**（复用 `entry_questions` 的题型 + 范围口径），但**只计数、不抽样**
        ⇒ 与"随机抽到的池大小"不同：同一课时每次进入题目数稳定，适合作为进度条分母。
          * 常规入口（read / listen / check / practice）：Unit 级题型 + 当前 Section 题型；
          * **词形练习（wordform）：按 Unit 计数**（它是 Unit 级题型，无 Section 归属 —— 例外）。
        读不到返回 0（渲染层会退回池大小，与旧行为一致），不抛错、不写库。
        """
        try:
            return len(self.entry_questions(entry, unit_code, section_key))
        except Exception as exc:                       # noqa: BLE001
            print("[web] 课时题目数读取失败（%s）：%r" % (entry, exc))
            return 0

    def entry_questions(self, entry, unit_code, section_key=""):
        """某入口**候选池对应的 question_id 集合**（只读；供首页「学习状态」使用）。

        2026-10-01（UI-7 第 2 件）。口径与入口候选池**同源**：直接复用正式
        `scs.select_questions`（入口允许题型 + Unit 范围 + 正式性 PASS/RELIABLE），
        因此"学习状态"覆盖的题目集合与孩子实际会做到的是**同一批**。
          * 多模式入口（read / listen）：取各模式并集；
          * **Section 级题型**再加 `(unit_code, section_key)` 精确条件；
          * **词形变化（wordform）整体按 Unit**（`demo.UNIT_LEVEL_STATUS_ENTRIES`），不按 Section。
        读不到一律返回空集合（→「未开始」），不抛错、不写库。
        """
        try:
            # 题型集合：多模式入口取并集。
            # 注意：**不要**把 mode 直接交给 `select_questions` —— 它只对 listen / wordform
            # 接受 mode（其它入口会抛 ValueError）；这里用 `allowed_types` 取并集，等价且安全。
            modes = [None]
            if entry == "listen":
                modes = ["word", "sentence"]
            elif entry == "wordform":
                modes = ["phonetic", "form"]
            types = []
            for m in modes:
                for ty in scs.allowed_types(entry, m):
                    if ty not in types:
                        types.append(ty)
            # 题型兜底（与 `_p5_items` 同一口径）：
            #   * `practice`：正式规则 = "已学 Section 的合法内容"，题型取**全题库**
            #     （PASS + RELIABLE 的全部 question_type）——`_p5_items` 用同一兜底；
            #   * `read`：素材来自跟读链路（词表 / 教材句），**不是题目池** ⇒ 没有题目证据，
            #     状态必然为「未开始」；这是**如实**结果（不伪造"进行中"）。
            if not types:
                if entry == "practice":
                    try:
                        _c = scs.connect_questionbank()
                        try:
                            types = [r[0] for r in _c.execute(
                                "SELECT DISTINCT question_type FROM question "
                                "WHERE quality_status='PASS' AND answer_status='RELIABLE'")]
                        finally:
                            _c.close()
                    except Exception as exc:               # noqa: BLE001
                        print("[web] practice 题型读取失败：%r" % (exc,))
                        types = []
                if not types:
                    return []
            items = scs.select_questions(entry, unit_code, None, learning_db=self.learning_db)
            # 范围收敛：Section 级题型只保留当前 Section；Unit 级题型（无 section_key）保留。
            unit_wide = entry in getattr(demo, "UNIT_LEVEL_STATUS_ENTRIES", ())
            kept = []
            for it in items:
                qq = it.get("question") or {}
                qid = qq.get("question_id") or it.get("evidence_item_id") or ""
                if not qid:
                    continue
                if qq.get("question_type") not in types:
                    continue
                sec = (qq.get("section_key") or "").strip()
                # **Unit 级词汇资源**（`P5_VOCAB_TYPES`）的 `section_key='WORDS_AND_EXPRESSIONS'`
                # 只表示"该题取自词表页"，**不是课时边界** ⇒ 与 `_p5_items` 同口径：
                # 它们不因"当前 Section"被过滤掉（否则词形练习会永远显示「未开始」）。
                vocab_level = qq.get("question_type") in self.P5_VOCAB_TYPES
                if unit_wide or vocab_level or not sec or not section_key or sec == section_key:
                    # 同时给出 **learning_item id**（= `learning_record.item_id` 的语义）：
                    # 证据只在学习库里，而 question 在题库里 —— 跨库 JOIN 不可行，
                    # 因此映射必须在题库侧做完（见 demo_data._evidence_progress 的说明）。
                    kept.append({"question_id": qid,
                                 "item_id": qq.get("source_item_id") or ""})
            dedup = {}
            for k in kept:
                dedup.setdefault(k["question_id"], k)
            return list(dedup.values())
        except Exception as exc:                       # noqa: BLE001 —— 读不到按"未开始"
            print("[web] 入口题目集合读取失败（%s）：%r" % (entry, exc))
            return []

    def _p5_items(self, unit, entry, learner_id, mode="", lesson_key="", cat=""):
        """P5 候选：跟读取正式教材音频素材，其余取正式题目（范围/证据排序由 P5 决定）。

        V1.3 第二十九章 §15·3：非教学 Block（Appendix）**显式**没有学习功能资源池 ——
        直接返回空池，不调用教学 Unit 专属的题库函数（既不是"异常被吞掉"，也不会抛错）。
        主页入口与功能页共用本函数，因此两侧判定天然一致（P6-B-12-FIX S1）。
        """
        if (unit.get("unit_code") or "") in demo.NON_TEACHING_UNITS:
            return []
        if entry == "read":
            # P6-B-11：UI 默认 mode=word（ui.p5_mode_bar），数据分支必须与 UI 一致
            if mode in ("", "word"):
                items = self._p5_word_items(unit)
            else:
                # P6-B-11b：短句跟读是 Section 级资源，只属于当前 (unit_code, section_key)；
                # 当前 Section 没有资源时就是空池（不 fallback 到整个 Unit / 其他 Section）。
                # lesson_key 为空表示该 Unit 没有任何有题的 Section，此时维持原有不带 Section 的行为。
                items = scs.shadowing_materials(unit["unit_code"],
                                                section_key=lesson_key or None)
        else:
            # P6-B-11：听音辨意四模式必须真正把 mode 传给正式题型筛选（allowed_types）
            items = scs.select_questions(entry, unit["unit_code"], learner_id,
                                         mode=mode or None, learning_db=self.learning_db)
        if entry == "practice":
            # P6-B-9：自主练习 = **已学 Section 集合**的合法资源；当前 Section 只是上下文，
            # 不再作为额外过滤条件（也不因 Unit 前缀把未学 Section 放进来）。
            #   * Section 级题型：按 (unit_code, section_key) 精确命中已学 Section；
            #   * Unit 级题型（词表/短语）：保持正式 Unit 级规则。
            try:
                learned = scs.learned_sections(learner_id, learning_db=self.learning_db)
            except Exception as exc:                   # noqa: BLE001 —— 读不到就按"无已学 Section"处理
                print("[web] 已学 Section 读取失败：%r" % (exc,))
                learned = set()
            items = [i for i in items
                     if i["question"].get("question_type") in self.P5_VOCAB_TYPES
                     or (i["question"].get("question_type") in self.P5_LESSON_TYPES
                         and ((i["question"].get("unit_code") or "",
                               i["question"].get("section_key") or "") in learned))]
        elif entry != "read" and lesson_key:
            # P6-B-11 S1：按正式资源粒度分治——
            #   * 教材/Lesson 型：严格要求 section_key == 当前 Lesson（不跨 Lesson）；
            #   * 词表/短语/附录型：保持其正式 Unit/Appendix 范围，不因当前 Lesson 被过滤；
            # 两类都不存在"过滤为空就回退 Unit 全量"的退化。
            items = [i for i in items
                     if i["question"].get("question_type") in self.P5_VOCAB_TYPES
                     or (i["question"].get("question_type") in self.P5_LESSON_TYPES
                         and (i["question"].get("section_key") or "") == lesson_key)]
        if entry == "practice" and cat:
            # P6-B-11：自主练习类别（正式 question_type），与 Lesson 同时生效
            items = [i for i in items if i["question"].get("question_type") == cat]
        return items

    def _p5_word_items(self, unit):
        """单词跟读：正式教材 Vocabulary + 正式词音频（与今日特训同源，不用任何 Demo 数据）。"""
        index = audio_mod.word_audio_index()
        out = []
        for item in (content_mod.list_unit_resources(unit["slug"], "vocabulary")
                     or {"items": []})["items"]:
            key = flow.item_key(item["item_id"])
            got = index.get(key) or {}
            audio_url = got.get("url") if got.get("item_id") == item["item_id"] else None
            # 2026-10-01（跟读记录）：**必须**给出 evidence_item_id —— 它就是该词在
            # contentpack.learning_item 里的 item_id（实测命中）。此前写死 None，
            # 导致 `scs.record_shadowing` → `record_answer` 因"解析不到真实教材 item"
            # 直接返回 recorded=False（reason=no_evidence_item）⇒ 跟读**永远不落库**。
            # 会话创建时同一批 item 会写入 TaskItem，故 record_answer 的"item 属于本会话"
            # 校验也随之满足；`done` 不是判断证据，不影响正确率与掌握度。
            out.append({"question_id": "word:%s" % key, "text": item["text"],
                        "phonetic": item.get("phonetic"), "meaning": item.get("meaning"),
                        "part_of_speech": item.get("part_of_speech"),
                        "audio_url": audio_url, "start_ms": None, "end_ms": None,
                        "evidence_item_id": item["item_id"]})
        return out

    def _p5_scope_items(self, unit, entry, learner_id, mode="", cat=""):
        """GET / POST 共用的候选池计算（P6-B-9：范围规则只在这里定义一次）。

        * GET（`_p5_page`）与 POST（`_p5_submit`）都必须调用本函数，保证两侧候选范围一致；
        * 当前 Section（历史名 lesson_key）由 URL/Cookie 决定，作为上下文传入；
          对自主练习不再构成额外过滤条件（见 `_p5_items`）。
        """
        try:
            lesson_key = self._lessons_for(unit)[1]
        except Exception:                              # noqa: BLE001
            lesson_key = ""
        return self._p5_items(unit, entry, learner_id, mode=mode,
                              lesson_key=lesson_key, cat=cat)

    def _p5_page(self, unit, entry, override=None):
        # 2026-09-30 兼容：原「音标写词」(phonetic) / 「词形变化」(form) 已合并为「词形练习」
        # (wordform)。旧路由必须继续可用 ⇒ 先归一入口名，并映射为对应**内部模式**。
        # 不改变题库范围：允许题型仍由 scs.allowed_types(wordform, mode) 决定。
        if entry in ("phonetic", "form"):
            override = dict(override or {})
            override.setdefault("mode", [entry])
            entry = "wordform"
        if entry not in self.P5_ENTRY_LABELS:
            return self._natural_error("这个入口不存在", "请从首页重新进入。", "/", "回到首页")
        conn = self._conn()
        try:
            learner_id = self._learner_from_cookies(conn)
        finally:
            conn.close()
        # P6-B-7：一题一屏 —— i=当前题号，mode=入口内的练习方式，
        # fb/picked/result 只用于把"刚提交的这一次"的即时反馈带回同一屏。
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if override:
            q.update(override)
        mode = (q.get("mode") or [""])[0]
        cat = (q.get("cat") or [""])[0]
        try:
            index = int((q.get("i") or ["0"])[0] or 0)
        except ValueError:
            index = 0
        try:
            lesson_key = self._lessons_for(unit)[1]
        except Exception:
            lesson_key = ""
        try:
            items = self._p5_scope_items(unit, entry, learner_id, mode, cat)
        except Exception as exc:                       # noqa: BLE001
            print("[web] P5 候选读取失败：%r" % (exc,))
            # P6-B-12-FIX：异常不再伪装成"无内容"；如实报错并记录（异常应可被发现）。
            return self._natural_error("这个入口暂时打不开", "请稍后再试。",
                                       "/?unit=%s" % unit["slug"], "回到首页")
        if not items:
            # P6-B-12-FIX S2：直接进入无资源功能页 → 真实、面向孩子的空状态
            # （不使用"换个章节看看"这类与事实不符的误导文案）。
            self._html(ui.p5_page({"unit": unit, "entry": entry,
                                   "label": self.P5_ENTRY_LABELS[entry],
                                   "items": [], "index": 0, "mode": mode,
                                   "lesson_key": lesson_key,
                                   # UI-7 第 4 件：空态无需分母，显式给 0（渲染层不显示进度条）
                                   "lesson_question_total": 0,
                                   "ask_name": learner_id is None}))
            return
        if not (q.get("i") or [""])[0].strip():
            # P6-B-11 S2：URL 未指定 i 时，在"已经确定正式范围"的 items 内随机起始项；
            # 指定 i（含 i=0）时一律尊重 URL；翻页链接自带 i，因此翻页不会重新随机。
            index = random.randrange(len(items)) if len(items) > 1 else 0
        # J1（批次 1+2+4·c）：为 `ai_eval` 题（无可靠答案事实）解析教材证据包，
        # 供页面下发给批次 4 的桥调用 AI 批改使用。
        # 边界：**只读**；解析失败不阻断页面（如实降级为"无证据"），
        # 与 Android基线:236「因 AI 不可用阻断确定性学习功能」同一精神。
        ai_evidence = None
        try:
            cur = items[index] if 0 <= index < len(items) else (items[0] if items else None)
            if cur is not None and (cur.get("question") or {}).get("answer_kind") == "ai_eval":
                ai_evidence = scs.resolve_question_evidence(cur["question"],
                                                            contentpack_path=self.contentpack_path)
                print("[web] 证据解析：%s -> granularity=%s via=%s pkg=%s" % (
                    cur.get("question_id"), ai_evidence.get("granularity"),
                    ai_evidence.get("resolved_via"), ai_evidence.get("package_question_id")))
        except Exception as exc:                       # noqa: BLE001 —— 不阻断确定性学习功能
            print("[web] 证据解析失败（降级为无证据）：%r" % (exc,))
            ai_evidence = None
        self._html(ui.p5_page({"unit": unit, "entry": entry,
                               "ai_evidence": ai_evidence,
                               "label": self.P5_ENTRY_LABELS[entry],
                               "items": items, "ask_name": learner_id is None,
                               "index": index, "mode": mode,
                               # P6-B-UI-RESTORE-05：把当前 Lesson 交给渲染层，内部链接/提交显式携带
                               "lesson_key": lesson_key,
                               # 2026-10-01（UI-7 第 4 件）：进度条分母 = **当前课时题目数**
                               # （只计数、不抽样），不再是"本次随机池大小"。
                               "lesson_question_total": self.lesson_question_count(
                                   entry, unit["unit_code"], lesson_key),
                               "feedback": (q.get("fb") or [""])[0] == "1",
                               "picked": (q.get("picked") or [""])[0],
                               "result": (q.get("result") or [""])[0]}))

    def _p5_result(self, unit, entry):
        """本次结果：只用正式学习证据陈述事实（不评分、不排名）。"""
        # 2026-09-30 兼容：旧入口名（phonetic / form）归一为 wordform
        if entry in ("phonetic", "form"):
            entry = "wordform"
        if entry not in self.P5_ENTRY_LABELS:
            return self._natural_error("这个入口不存在", "请从首页重新进入。", "/", "回到首页")
        conn = self._conn()
        try:
            learner_id = self._learner_from_cookies(conn)
        finally:
            conn.close()
        # P6-B-UI-RESTORE-05：结果页沿用同一 Lesson（section_key），链接不会丢上下文
        try:
            lesson_key = self._lessons_for(unit)[1]
        except Exception:
            lesson_key = ""
        rows = []
        try:
            cands = self._p5_items(unit, entry, learner_id)
        except Exception:                              # noqa: BLE001
            cands = []
        if cands:
            need = sum(1 for c in cands if c.get("reason") in ("current_error", "current_weak"))
            todo = sum(1 for c in cands if c.get("reason") == "not_started")
            if need:
                rows.append({"result": "incorrect", "text": "还有 %d 项需要再练一次。" % need})
            if todo:
                rows.append({"result": "done", "text": "还有 %d 项还没有做过。" % todo})
            if not rows:
                rows.append({"result": "correct", "text": "这一节的题目都已经完成。"})
        self._html(ui.p5_result_page({"unit": unit, "entry": entry,
                                      "label": self.P5_ENTRY_LABELS[entry], "results": rows,
                                      "lesson_key": lesson_key}))

    def _p5_repeat(self, path, form):
        """跟读完成登记（**录音结束即一次**）：POST `/unit/<slug>/p5/read/repeat`。

        表单：`i`（题序，来自当前卡片 data-i）、`mode`（word/sentence，可选）。
        边界（与既有 read 分支完全一致）：
          * 只经冻结 service 写入（`ses.create_learning_session` / `scs.record_shadowing`）；
          * 写 `activity_type='repeat'` + `result='done'` —— **不是判断证据**，
            不产生 mastery、不影响正确率；
          * 任何失败都**不阻断跟读**（返回 JSON，前端忽略即可）。
        """
        rest = [p for p in path[len("/unit/"):-len("/repeat")].split("/") if p]
        if len(rest) < 3:
            return self._json({"ok": False, "reason": "bad_path"})
        slug, entry = rest[0], rest[2]
        if entry != "read":
            return self._json({"ok": False, "reason": "not_read"})
        unit = content_mod.get_unit(slug, self.contentpack_path)
        if unit is None or (unit.get("unit_code") or "") in demo.NON_TEACHING_UNITS:
            return self._json({"ok": False, "reason": "no_unit"})
        try:
            index = int((form.get("i") or "0") or 0)
        except ValueError:
            index = 0
        mode = (form.get("mode") or "").strip()
        conn = self._conn()
        try:
            learner_id = self._learner_from_cookies(conn)
            if not learner_id:
                learner_id = flow.resolve_learner(conn, "本机学生")
                self._set_cookie("zx_learner", learner_id)
            lesson_key = self._lessons_for(unit)[1]
            items = self._p5_scope_items(unit, "read", learner_id, mode, "")
            if not items:
                return self._json({"ok": False, "reason": "empty_pool"})
            index = max(0, min(index, len(items) - 1))
            cur = items[index]
            qid = cur.get("question_id")
            item_ids = list(dict.fromkeys(
                m["evidence_item_id"] for m in items if m.get("evidence_item_id")))
            if not qid or not item_ids:
                return self._json({"ok": False, "reason": "no_evidence_item"})
            session = ses.create_learning_session(
                conn, learner_id, "activity", item_ids,
                contentpack_path=self.contentpack_path)
            # 2026-10-01：**必须**把该词的教材条目一起传下去 —— 跟读词池的 question_id
            # 是合成 id（`word:<hash>`，不在题库），只给 question_id 会被判 question_not_found。
            out = scs.record_shadowing(session["session_id"], qid, learner_id=learner_id,
                                       learning_db=self.learning_db,
                                       evidence_item_id=cur.get("evidence_item_id"))
            return self._json({"ok": True,
                               "recorded": bool(out.get("recorded")),
                               "reason": out.get("reason") or "",
                               "question_id": qid,
                               "lesson_key": lesson_key,
                               "index": index})
        except svc.LearningServiceError as exc:
            print("[web] 跟读登记失败（service）：%r" % (exc,))
            return self._json({"ok": False, "reason": "service_error"})
        except Exception as exc:                       # noqa: BLE001 —— 绝不阻断跟读
            print("[web] 跟读登记失败：%r" % (exc,))
            return self._json({"ok": False, "reason": "error"})
        finally:
            conn.close()

    def _p5_submit(self, path, form):
        """正式作答：整页作答在后端**逐题**交给 P5 record_answer / record_shadowing。"""
        rest = [p for p in path[len("/unit/"):-len("/submit")].split("/") if p]
        if len(rest) != 3 or rest[1] != "p5":
            return self._natural_error("这一步没有成功", "请从首页重新进入。", "/", "回到首页")
        slug, entry = rest[0], rest[2]
        # 2026-09-30 兼容（与 GET `_p5_page` 同一口径）：原「音标写词」(phonetic) /
        # 「词形变化」(form) 已合并为「词形练习」(wordform)。旧 submit 路径必须继续可用 ⇒
        # 先归一入口名，并把它映射为对应**内部模式**（POST 时与 GET 用同一条候选池函数）。
        if entry in ("phonetic", "form"):
            form = dict(form)
            form.setdefault("mode", entry)
            entry = "wordform"
        unit = content_mod.get_unit(slug, self.contentpack_path)
        if unit is None or entry not in self.P5_ENTRY_LABELS:
            return self._natural_error("这个入口暂时打不开", "请从首页重新进入。", "/", "回到首页")
        if (unit.get("unit_code") or "") in demo.NON_TEACHING_UNITS:
            # V1.3 §15·3：非教学 Block（Appendix）不进入六项学习功能入口 ——
            # 不创建学习会话、不写任何记录，直接返回真实空状态（也避免落入异常路径）。
            return self._p5_page(unit, entry)
        conn = self._conn()
        try:
            learner_id = self._learner_from_cookies(conn)
            name = (form.get("name") or "").strip()
            if not learner_id and name:
                learner_id = flow.resolve_learner(conn, name)
                self._set_cookie("zx_learner", learner_id)
            if not learner_id:                         # P6-B-8：不再用姓名框采集身份（沿用既有最小身份机制）
                learner_id = flow.resolve_learner(conn, "本机学生")
                self._set_cookie("zx_learner", learner_id)
            # P6-B-9：POST 与 GET 使用**同一个**候选池函数（同一 learner / Section / entry / mode）。
            # POST 的 mode：表单字段优先，其次 URL query —— 保证与 GET 页面**同一候选池**
            # （GET 链接带 ?mode=…，表单内也带隐藏 mode，双保险）。
            post_mode = (form.get("mode") or (urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query).get("mode") or [""])[0])
            items = self._p5_scope_items(
                unit, entry, learner_id, post_mode,
                (urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("cat") or [""])[0])
            session = None
            if entry == "read":                        # 跟读素材：只把能归属教材的放进会话
                item_ids = list(dict.fromkeys(             # 同一教材 item 只入会话一次
                    m["evidence_item_id"] for m in items if m.get("evidence_item_id")))
                if item_ids:
                    session = ses.create_learning_session(
                        conn, learner_id, "activity", item_ids,
                        contentpack_path=self.contentpack_path)
            else:
                started = scs.start_practice_session(entry, unit["unit_code"], learner_id,
                                                     learning_db=self.learning_db)
                session = started.get("session")
            results = []
            for m in items:
                qid = m["question_id"]
                if entry == "read":
                    if not form.get("done_%s" % qid):
                        continue
                    if session:                        # repeat / done：不产生判断证据
                        scs.record_shadowing(session["session_id"], qid, learner_id=learner_id,
                                             learning_db=self.learning_db)
                    results.append({"result": "done"})
                    continue
                picked = form.get("q_%s" % qid)
                if picked is None or picked == "":
                    continue
                q = m["question"]
                if session:
                    out = scs.record_answer(session["session_id"], qid, picked,
                                            learner_id=learner_id, learning_db=self.learning_db)
                    result = out.get("result")
                else:                                  # 无正式教材归属：判分但不写记录
                    result = scs.grade_answer(q, picked)[0]
                ans = q.get("answer") or {}
                if result == "needs_review":
                    # V1.3 §七·9：该题没有可靠答案事实（answer_kind=ai_eval）-> 暂不判分。
                    # answer_text 必须为空：既不能显示"正确答案"（本就没有），
                    # 也不能把"未判分"当成"答错了"展示。
                    results.append({"result": "needs_review", "answer_text": None,
                                    "picked": picked})
                    continue
                results.append({"result": result, "answer_text": ans.get("text") or ans.get("key"),
                                "picked": picked})
            if session:
                ses.end_learning_session(conn, session["session_id"], learner_id)
            # P6-B-7：整页提交改为"当前这一题提交 → 同一屏给即时反馈 → 下一题"。
            i = int(form.get("i") or 0)
            mode = (form.get("mode") or "").strip()
            over = {"i": [str(i)], "mode": [mode] if mode else []}
            if entry != "read" and results:
                over["fb"] = ["1"]
                over["picked"] = [str(results[-1].get("picked") or "")]
                over["result"] = [str(results[-1].get("result") or "")]
            self._p5_page(unit, entry, override=over)
        except svc.LearningServiceError as exc:
            print("[web] 正式练习记录失败：%r" % (exc,))
            self._natural_error("这一步没有成功", "请再提交一次。",
                                "/unit/%s/p5/%s" % (unit["slug"], entry), "回到练习")
        except Exception as exc:                       # noqa: BLE001 —— 不把异常抛回连接
            print("[web] 正式练习处理失败：%r" % (exc,))
            self._natural_error("这一步没有成功", "请回到首页再来一次。", "/", "回到首页")
        finally:
            conn.close()

    #: P2（性能）：`_unit_training()` 的按 (slug, contentpack mtime) 缓存。
    #: 该函数只读 contentpack / 官方音频清单（零写入、零 AI），结果只取决于
    #: 教材内容；contentpack 文件一变（mtime 变）即自动失效，不会读到旧数据。
    #: 实测：单次调用约 210ms（Windows）/ 首页与 /progress 与 /unit/<slug>/text
    #: 每个请求都要算一次，而它完全不依赖学习者状态。
    _TRAINING_CACHE = {}

    def _unit_training(self, unit):
        """装配一个单元的今日特训数据（真实教材内容；零写入、零 AI）。

        只读取 contentpack / 官方音频清单；教材内容一个字都不改写。

        P2：结果按 (slug, contentpack mtime) 缓存——该函数不依赖学习者状态，
        contentpack 变更后自动失效。
        """
        slug = unit["slug"]
        try:
            cp_mtime = Path(self.contentpack_path).stat().st_mtime
        except OSError:
            cp_mtime = None
        _ck = (slug, cp_mtime)
        _hit = self._TRAINING_CACHE.get(_ck)
        if _hit is not None:
            return _hit
        index = audio_mod.word_audio_index()
        words = []
        for item in (content_mod.list_unit_resources(slug, "vocabulary")
                     or {"items": []})["items"]:
            key = flow.item_key(item["item_id"])
            entry = index.get(key) or {}
            words.append({
                "text": item["text"], "meaning": item.get("meaning"),
                "phonetic": item.get("phonetic"), "pos": item.get("part_of_speech"),
                "key": key, "item_id": item["item_id"], "order": item.get("order"),
                "audio_url": (entry.get("url")
                              if entry.get("item_id") == item["item_id"] else None)})
        phrases = [{"text": i["text"], "meaning": i.get("meaning")}
                   for i in (content_mod.list_unit_resources(slug, "phrase")
                             or {"items": []})["items"]]
        patterns = [{"text": i["text"]}
                    for i in (content_mod.list_unit_resources(slug, "sentence-pattern")
                              or {"items": []})["items"]]
        try:
            text_data = content_mod.unit_text_sections(slug, self.contentpack_path)
        except Exception as exc:
            print("[web] 课文读取失败：%r" % (exc,))
            text_data = None
        # P6-B-12：教材正文只展示"能与官方音频可靠对应（VERIFIED）"的块。
        # 数据完整保留，未达可靠对应的块不进入展示层；Section 本身、Section 顺序、Section key
        # 与块的原教材顺序都不变（不猜映射、不用 PARTIAL 冒充、不新增数据结构）。
        if text_data is not None:
            covered = content_mod.audio_covered_block_ids(unit["unit_code"], self.contentpack_path)
            filtered = []
            for sec in text_data.get("sections") or []:
                keep = covered.get(sec["section_key"]) or frozenset()
                filtered.append(dict(sec, blocks=[b for b in sec["blocks"]
                                                  if b["block_id"] in keep]))
            text_data = dict(text_data, sections=filtered,
                             block_count=sum(len(sec["blocks"]) for sec in filtered))
        sections = (text_data or {}).get("sections") or []
        unit_text = "\n".join(b["text"] for s in sections for b in s["blocks"])
        audio = content_mod.unit_audio_resources(unit["unit_code"], self.contentpack_path)
        # 教材原文页与训练环节共用同一批已核验句子：只补一个公开短键 uid，不改任何教材事实。
        sentences = audio.get("sentences") or []
        for row in sentences:
            row["uid"] = row["sentence_uid"]
        out = {"words": words, "phrases": phrases, "patterns": patterns,
               "sections": sections,
               "text_data": text_data,
               "unit_text": unit_text, "sentences": sentences,
               "activities": audio.get("activities") or [],
               "text_block_count": (text_data or {}).get("block_count", 0)}
        self._TRAINING_CACHE[_ck] = out        # P2：写入缓存（仅当次装配成功）
        return out

    def _other_sentence_pool(self, unit):
        """其它单元的教材句子（用于阅读练习的干扰项；逐条确认不在本课课文里）。"""
        key = ("pool", str(self.contentpack_path))
        if key in _SENTENCE_POOL_CACHE:
            return _SENTENCE_POOL_CACHE[key]
        out = []
        for other in content_mod.list_units(self.contentpack_path):
            # Appendix 是词汇表/附录页，不是课文，不作为课文句子干扰项来源
            if other["slug"] == unit["slug"] or other["unit_code"] == "Appendix":
                continue
            try:
                data = content_mod.unit_text_sections(other["slug"], self.contentpack_path)
            except Exception:
                continue
            out += demo.sentence_pool((data or {}).get("sections"))
        _SENTENCE_POOL_CACHE[key] = out
        return out

    def _drill_items(self, unit, training, key):
        """按训练环节装配题目（参考答案都可由教材内容核对）。"""
        if key == "vocab":
            return demo.build_vocab_drill(
                [{"text": w["text"], "meaning": w["meaning"], "phonetic": w["phonetic"],
                  "pos": w["pos"], "key": w["key"], "audio_url": w["audio_url"]}
                 for w in training["words"]])
        if key == "phrase":
            meanings = []
            for other in content_mod.list_units(self.contentpack_path):
                if other["slug"] == unit["slug"]:
                    continue
                for p in (content_mod.list_unit_resources(other["slug"], "phrase")
                          or {"items": []})["items"]:
                    if p.get("meaning"):
                        meanings.append(p["meaning"])
            return demo.build_phrase_drill(training["phrases"], training["sentences"],
                                           meaning_pool=meanings)
        if key == "reading":
            return demo.build_reading_drill(
                unit["unit_code"], training["unit_text"],
                demo.sentence_pool(training["sections"]),
                self._other_sentence_pool(unit))
        if key == "listening":
            return demo.build_listening_drill(training["sentences"])
        return []

    def _textbook(self):
        try:
            ctx = content_mod.home_context(self.learning_db, self.contentpack_path,
                                           learner_id=self._resolve_valid_learner())
            ctx["units"] = content_mod.list_units(self.contentpack_path)
        except Exception as exc:
            print("[web] 教材中心数据读取失败：%r" % (exc,))
            self._html(ui.error_page("教材中心暂时打不开", "请稍后再试。", "/", "回到首页"), 200)
            return
        self._html(ui.textbook_page(ctx))

    def _progress(self):
        """我的进展：真实数据（教材 / 最近学过 / 需要再学）＋演示进展数值；零写入。

        Demo V1.1：三个维度固定为 课文理解 / 句型语法 / 口语练习（口语只给次数）。
        """
        try:
            learner_id = self._resolve_valid_learner()        # 同上：进度页展示学习状态，需自愈
            
            unit = self._query_unit()
            training = self._unit_training(unit)
            chapter_ai, _focus, _steps = self._chapter_ai(unit, training)
            ctx = content_mod.home_context(self.learning_db, self.contentpack_path,
                                           learner_id=learner_id)
            ctx["unit_slug"] = unit["slug"]
            ctx["classroom"] = self._classroom(unit, training)
            ctx["ai"] = chapter_ai
            ctx["parent_progress"] = demo.parent_progress(unit["unit_code"])
            ctx["attention"] = [dict(a) for a in demo.ATTENTION]
            # G1：最近学过（只读；无当前 learner 时不猜测、保持真实空态）
            ctx["recent"] = (flow.recent_studied(learner_id, self.learning_db,
                                                 self.contentpack_path)
                             if learner_id else [])
        except Exception as exc:
            print("[web] 进展数据读取失败：%r" % (exc,))
            self._html(ui.error_page("进展暂时打不开", "请稍后再试。", "/", "回到首页"), 200)
            return
        self._html(ui.progress_page(ctx))

    # ---- 单元中心（学情分析页）一期：纯数据，零 AI --------------------------
    def _unit_center_data(self, unit):
        """单元中心（学情分析页）二期数据：**只读**，聚合约在 `demo_data.unit_center_data`。

        本方法只负责两件 app 层的事：
          1. 取该 Unit 的**教材 Section 正式顺序**（含原名），供"已学 / 未学"；
          2. 解析有效 learner（cookie 失效时按既有规则自愈），然后交给 demo 聚合。
        """
        unit_code = unit.get("unit_code") or ""
        sections_all = []
        try:
            for u in content_mod.list_units_with_sections(self.contentpack_path):
                if (u.get("slug") or "") == unit.get("slug"):
                    sections_all = list(u.get("sections") or [])
                    break
        except Exception as exc:                       # noqa: BLE001
            print("[web] 单元中心 Section 读取失败：%r" % (exc,))

        learner_id = self._resolve_valid_learner()
        try:
            qb_path = getattr(scs, "DEFAULT_QUESTIONBANK", None)
        except Exception:                              # noqa: BLE001
            qb_path = None
        ctx = demo.unit_center_data(
            unit_code, unit.get("title") or "", unit.get("slug") or "",
            sections_all, learner_id, self.learning_db,
            questionbank_path=qb_path)
        # 练习入口（供 ④ 按钮；取六入口 + 各入口默认/常用模式，走既有标签映射）
        ctx["practice_entries"] = self._unit_center_entries(unit)
        return ctx

    def _unit_center_entries(self, unit):
        """④ 两个按钮的候选入口（**既有映射，不新造**）：按"先补薄弱"的默认顺序给前几条。

        只给"当前 Section 真的有资源"的入口 —— 复用 `_p5_scope_items` 的正式判定，
        不另建第二套判断（AGENTS.md §3 内部模式显隐的同一口径）。
        """
        out = []
        lesson_key = self._lessons_for(unit)[1]
        learner_id = self._resolve_valid_learner()
        for entry, mode in (("wordform", "phonetic"), ("wordform", "form"),
                            ("listen", "word"), ("listen", "sentence"),
                            ("check", ""), ("read", "word"), ("practice", "")):
            if entry not in self.P5_ENTRY_LABELS:
                continue
            try:
                items = self._p5_scope_items(unit, entry, learner_id, mode, "")
            except Exception:                          # noqa: BLE001
                continue
            if not items:
                continue
            label = self.P5_ENTRY_LABELS[entry]
            if mode == "phonetic":
                label = "音标写词"
            elif mode == "form":
                label = "词形变化"
            else:
                label = self._p5_mode_label(entry, mode) or label
            out.append({"label": label, "entry": entry, "mode": mode})
        return out

    def _p5_mode_label(self, entry, mode):
        """入口内部模式的中文名（复用 ui 侧既有模式表，不新造名词）。"""
        table = {"read": ui._P5_READ_MODES, "listen": ui._P5_LISTEN_MODES,
                 "wordform": ui._P5_WORDFORM_MODES}.get(entry) or ()
        for key, name in table:
            if key == mode:
                return name
        return ""


        def stat(rows):
            """(已练题数, 答对题数, 答错/部分题数)"""
            seen, ok, bad = set(), 0, 0
            for r in rows:
                iid = r.get("source_item_id")
                if not iid or iid not in done_res:
                    continue
                if iid in seen:
                    continue
                seen.add(iid)
                if iid in wrong_res:
                    bad += 1
                else:
                    ok += 1
            return len(seen), ok, bad

        # ① 单元整体：按 question_type 汇总
        by_type = {}
        for r in qrows:
            by_type.setdefault(r.get("question_type") or "(未知)", []).append(r)
        types = []
        for name, rows in by_type.items():
            n, ok, bad = stat(rows)
            if n <= 0:
                continue                               # 没练过的题型不展示（不吓孩子）
            types.append({"name": name, "practiced": n, "right": ok, "wrong": bad,
                          "rate": int(round(100.0 * ok / n)) if n else 0})
        types.sort(key=lambda x: (-x["practiced"], x["name"]))

        # ② 课时进度：教材真实 Section 顺序（不过滤零题 Section）
        sections = []
        try:
            for u in content_mod.list_units_with_sections(self.contentpack_path):
                if (u.get("slug") or "") != unit.get("slug"):
                    continue
                for s in u.get("sections") or []:
                    key = s.get("section_key") or ""
                    rows = [r for r in qrows if (r.get("section_key") or "") == key]
                    # 分母只算**可产生学习证据**的题：没有 source_item_id 的题永远无法
                    # 映射到 learning_record.item_id（见 stat() 的判定），把它们算进分母
                    # 会让覆盖率永远达不到阈值 ⇒ 与首页入口状态口径不一致（V4 实测暴露）。
                    mappable = [r for r in rows if r.get("source_item_id")]
                    n, ok, bad = stat(mappable)
                    total = len({r["question_id"] for r in mappable})
                    # 与首页入口状态**同源同口径**：覆盖率 ≥ 80% 即算已完成（不要求全对）。
                    # 阈值只在 demo_data 定义一次（STATUS_DONE_COVERAGE）。
                    if total and n >= total * demo.STATUS_DONE_COVERAGE:
                        st, kind = "已完成", "done"
                    elif n > 0:
                        st, kind = "正在进行", "doing"
                    else:
                        st, kind = "未开始", "todo"
                    sections.append({"key": key, "title": s.get("title") or key,
                                     "status": st, "kind": kind,
                                     "total": total, "practiced": n, "right": ok})
                break
        except Exception as exc:                       # noqa: BLE001
            print("[web] 单元中心课时进度失败：%r" % (exc,))

        done_sections = len([s for s in sections if s["kind"] == "done"])
        return {"unit": unit, "learner_id": learner_id, "sections": sections,
                "types": types, "sections_done": done_sections,
                "sections_total": len(sections), "question_total": len(qrows)}

    def _unit_center(self, unit):
        """`GET /unit/<slug>` —— 单元中心（学情分析页一期）。"""
        if (unit.get("unit_code") or "") in demo.NON_TEACHING_UNITS:
            # Appendix 不是普通教学 Unit：不强行进入学习功能入口（AGENTS.md §10-5）。
            self._html(ui.error_page("这个单元不是学习单元", "它属于附录内容。",
                                     "/textbook", "回到教材中心"), 200)
            return
        ctx = self._unit_center_data(unit)
        ctx["unit_slug"] = unit.get("slug") or ""
        ctx["lesson_key"] = self._lessons_for(unit)[1]
        self._html(ui.unit_center_page(ctx))

    def _unit_path(self, path):
        """处理 /unit/<slug>、/unit/<slug>/resources 与 /unit/<slug>/resources/<type>。"""
        parts = [p for p in path.split("/") if p]        # ["unit", slug, ...]
        slug = parts[1] if len(parts) > 1 else ""
        tail = parts[2:]
        try:
            unit = content_mod.get_unit(slug, self.contentpack_path)
        except Exception as exc:
            print("[web] 单元数据读取失败：%r" % (exc,))
            self._html(ui.error_page("这个单元暂时打不开", "请稍后再试。", "/textbook",
                                     "回到教材中心"), 200)
            return
        if unit is None:
            self._html(ui.error_page("没有找到这个单元", "它可能不属于当前教材。",
                                     "/textbook", "回到教材中心"), 404)
            return
        # 单元中心一期（2026-10-01）：`GET /unit/<slug>` 复用该退役路径承载**单元中心**
        # （学情分析页的"纯数据一期"：课时进度 + 知识点掌握，零 AI）。
        # 旧「本单元学习」七项菜单**不恢复** —— 本页只展示学习情况，不新增任何学习计划入口
        # （AGENTS.md §8：退役实现不得恢复）。
        if not tail:
            self._unit_center(unit)
            return
        # P6-B-12-FIX：旧「本单元学习」七项菜单宿主（GET /unit/<slug>）已退役 ——
        # 其余子路径沿用既有 404 处理，不保留「只剩书名卡 / AI 卡」的空壳页面。
        if not tail:
            self._html(ui.error_page("没有找到这个页面", "你要找的地方暂时不存在。",
                                     "/", "回到首页"), 404)
            return
        if tail[0] == "p5":
            # P6-A：正式题库练习页（六入口的唯一题目来源）。
            # 必须最先返回：六入口**不经过任何旧体系前置计算**（drill / training / exercise）。
            if len(tail) > 2 and tail[2] == "result":
                self._p5_result(unit, tail[1])
                return
            self._p5_page(unit, tail[1] if len(tail) > 1 else "")
            return
        # ---- 以下仅服务仍在使用的其它页面（教材原文 / 教材练习 / 资源浏览），
        #      与六入口无关 ----
        counts = (content_mod.unit_resource_counts(self.contentpack_path)
                  .get(unit["unit_code"], {}))
        unit_exercises = ex_mod.exercises_of_unit(unit["unit_code"])
        try:
            training = self._unit_training(unit)
        except Exception as exc:
            print("[web] 单元学习数据读取失败：%r" % (exc,))
            training = {"words": [], "phrases": [], "sections": [], "text_data": None,
                        "unit_text": "", "sentences": [], "activities": [],
                        "text_block_count": 0}
        text_data = training["text_data"]
        audio_data = {"sentences": training["sentences"], "activities": training["activities"]}
        chapter_ai, focus, steps = self._chapter_ai(unit, training)
        ctx = {"unit": unit, "counts": counts, "kinds": content_mod.RESOURCE_KINDS,
               # P2-2：音频属于教材练习（不再有"听本单元词汇"入口）
               "exercise_count": len(unit_exercises),
               "exercise_audio_count": sum(1 for e in unit_exercises if e.get("audio_id")),
              # P2-6-F-1：教材正文（只读）
              "text_block_count": (text_data or {}).get("block_count", 0),
              # P3-07：已人工核验的句子级音频（Demo 的句子学习锚点）
               "sentence_audio_count": len(audio_data.get("sentences") or []),
               "word_count": len(training["words"]),
               # Demo V1.1 修正：AI 随堂助教与首页同一套（章节内容 + 该章节学习状态）
               "ai": chapter_ai}
        if tail[0] == "text":
            if not text_data:
                self._html(ui.error_page("这个单元暂时没有可展示的教材原文",
                                         "教材原文会随着解析进度补充。",
                                         "/", "回到首页"), 200)
                return
            # 听读课文（2026-09-30 改版）：**按音频分块** —— 每个官方音频活动 = 一块
            # （该 Section 的 VERIFIED 课文 + 一个整段播放器）；没有音频的 Section 不显示。
            # 不再使用句子级热点（不做句子切分、不显示时间码）。
            self._html(ui.unit_text_page({"unit": unit, "text": text_data,
                                          "audio": audio_data}))
            return
        if tail[0] == "exercises":
            self._exercise_list(unit)
            return
        if tail[0] != "resources":
            self._html(ui.error_page("没有找到这个页面", "你要找的地方暂时不存在。",
                                     "/", "回到首页"), 404)
            return
        if len(tail) == 1:
            self._html(ui.resource_types_page(ctx))
            return
        kind = tail[1]
        if kind not in content_mod.RESOURCE_KIND_ITEM_TYPE:
            self._html(ui.error_page("没有找到这类内容", "这个单元里没有这一类内容。",
                                     "/", "回到首页"), 404)
            return
        data = content_mod.list_unit_resources(unit["slug"], kind, self.contentpack_path)
        if data is None:
            self._html(ui.error_page("没有找到这类内容", "这个单元里没有这一类内容。",
                                     "/", "回到首页"), 404)
            return
        # 页面只暴露公开短键，不暴露数据库内部 ID
        data = dict(data)
        learner_id = self._cookie_learner_id()
        statuses = flow.item_status_map(learner_id, [item["item_id"] for item in data["items"]],
                                        self.learning_db, self.contentpack_path) if learner_id else {}
        # P2-1-C1（C1-01 / C1-04）：只有 Vocabulary 能进入正式学习；
        # 白体词与暂未开放的内容只作为教材内容展示——不给学习入口，也不加解释性标签。
        word_audio = audio_mod.word_audio_index() if kind == "vocabulary" else {}
        rows = []
        for item in data["items"]:
            key = flow.item_key(item["item_id"])
            audio_url = None
            if kind == "vocabulary":
                entry = word_audio.get(key)
                audio_url = entry.get("url") if entry and entry.get("item_id") == item["item_id"] else None
            rows.append(dict(item, key=key,
                             status_label=flow.status_label(statuses.get(item["item_id"])),
                             can_study=bool(item.get("can_study")) and kind == "vocabulary",
                             audio_url=audio_url))
        data["items"] = rows
        data["has_study"] = any(item.get("can_study") for item in data["items"])
        ctx.update(data)
        self._html(ui.resource_list_page(ctx))

    # ---- Demo V1.1：今日特训 / 单词跟读 / 训练环节（全部只读；零写入、零 AI） ----
    def _redirect(self, location: str, code: int = 302):
        """产品结构变化后的旧入口：保留链接可用，不留下死路。"""
        self.send_response(code)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        # 与 _send 一致：跳转也要把本次要写的 Cookie 带出去（否则学习行为会丢）
        for cookie in getattr(self, "_pending_cookies", []):
            self.send_header("Set-Cookie", cookie)
        self._pending_cookies = []
        self.end_headers()

    def _page_image(self, path):
        """教材原书页面图片（由现有 PDF 现场渲染；只读派生，不修改教材）。"""
        name = path[len("/page/"):]
        if not name.endswith(".jpg") or not name[:-4].isdigit():
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        data = pdf_pages.render_jpeg(int(name[:-4]))
        if data is None:
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=3600")
        self.end_headers()
        self.wfile.write(data)

    # ---- P1-12-C3-C3：Vocabulary 正式学习闭环 --------------------------------
    def _resolve_valid_learner(self):
        """**首页专用**：解析出一个"库里确实存在"的学习者，并保证 cookie 与之一致。

        2026-10-01（learner cookie 修复）。为什么需要它：
        真机实测发现 `zx_learner` 里存着一个**库里不存在的 id**（例如 App 重装/学习库被替换后
        遗留的旧 cookie）。`_cookie_learner_id()` 按设计**严格**返回 None（不猜测、不创建），
        而首页此前**没有任何恢复动作** ⇒ 六入口的学习状态**全部回落为「未开始」**，
        即使库里明明有 69 条真实学习记录。

        本方法的边界（**只读 + 不改学习库**）：
          * 优先用 cookie —— 只要它在库里**真实存在且 active**；
          * 否则从库里**已有的** learner 中挑一个：优先 `本机学生` → 记录数最多 → 最早创建；
          * 选中后**回写 cookie**（幂等；只改 cookie，不动库、不新建 learner）；
          * 库里一个 learner 都没有 ⇒ 返回 None（由调用方走既有的"首次使用"流程）。
        """
        conn = None
        try:
            current = (self._cookies().get("zx_learner") or "").strip()
            if current and flow.learner_exists(current, self.learning_db):
                return current
            conn = self._conn()
            rows = conn.execute(
                "SELECT learner_id, display_name FROM learner WHERE status='active' "
                "ORDER BY created_at, learner_id").fetchall()
            if not rows:
                return None
            candidates = [dict(r) for r in rows]
            counts = {}
            try:
                for r in conn.execute("SELECT learner_id, COUNT(*) FROM learning_record "
                                      "GROUP BY learner_id"):
                    counts[r[0]] = r[1]
            except Exception:                      # noqa: BLE001 —— 统计失败不影响选择
                counts = {}
            preferred = [c for c in candidates if (c.get("display_name") or "") == "本机学生"]
            pool = preferred or candidates
            best = max(pool, key=lambda c: (counts.get(c["learner_id"], 0),
                                            -candidates.index(c)))
            picked = best["learner_id"]
            if picked != current:
                print("[web] learner cookie 失效（%r 不在库中）→ 回退到 %r（%s）"
                      % (current or "", picked, best.get("display_name")))
                self._set_cookie("zx_learner", picked)
            return picked
        except Exception as exc:                       # noqa: BLE001 —— 解析失败按"无身份"处理
            print("[web] learner 解析失败：%r" % (exc,))
            return None
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:                      # noqa: BLE001
                    pass

    def _cookie_learner_id(self):
        """当前学习者（来自 Cookie，且必须真实存在）。没有就返回 None——不猜测、不创建。"""
        learner_id = self._cookies().get("zx_learner")
        return learner_id if learner_id and flow.learner_exists(learner_id, self.learning_db) else None

    def _learner_from_cookies(self, conn):
        return self._cookie_learner_id()

    def _study_context(self, conn, learner_id, item_id, session_id):
        view = flow.vocabulary_view(item_id, self.contentpack_path)
        unit = view.get("unit")
        back = ("/unit/%s/resources/vocabulary" % unit["slug"]) if unit else "/textbook"
        ctx = dict(view)
        ctx.update({"session_id": session_id, "learner_id": learner_id,
                    "item_id": item_id, "key": flow.item_key(item_id), "back_href": back,
                    # P2-1-C1（C1-06）：派生词发音（可能没有 → 页面不显示播放器）
                    "word_audio_url": audio_mod.word_audio_url(item_id, flow.item_key(item_id))})
        return ctx

    def _item_from_form(self, form):
        """页面只携带公开短键（pick）；这里换回真实 item_id。"""
        item_id = (form.get("item_id") or "").strip()
        if item_id:
            return item_id                      # 内部调用（测试/程序化）仍可直接给 item_id
        return flow.find_item_by_key(form.get("pick"), self.contentpack_path)

    def _study_start(self, form):
        """进入 Study：需要再学 / 资源列表 / Result「再学一次」都走这里（同一条学习链）。"""
        item_id = self._item_from_form(form)
        name = (form.get("name") or "").strip()
        if not item_id:
            return self._natural_error("没有找到这个词", "请从教材里重新选一个词。")
        conn = self._conn()
        try:
            try:
                view = flow.vocabulary_view(item_id, self.contentpack_path)
            except svc.NotFoundError:
                return self._natural_error("没有找到这个词", "它可能不属于当前教材。")
            except svc.LearningServiceError:
                return self._natural_error(
                    "这个词暂时不能在这里学习",
                    "它是教材里认识就好的词，先看看别的重点词吧。")
            learner_id = self._learner_from_cookies(conn)
            if name:
                try:
                    learner_id = flow.resolve_learner(conn, name)
                except svc.LearningServiceError:
                    return self._html(ui.first_use_page(
                        "/vocabulary/study", item_id, view["word"], "/textbook",
                        "名字没有保存成功，请再试一次。"), 200)
                self._set_cookie("zx_learner", learner_id)
            if not learner_id:
                return self._html(ui.first_use_page(
                    "/vocabulary/study", item_id, view["word"],
                    ("/unit/%s/resources/vocabulary" % view["unit"]["slug"])
                    if view.get("unit") else "/textbook"), 200)
            started = flow.start_study(conn, learner_id, item_id, self.contentpack_path)
            session_id = started["session"]["session_id"]
            self._set_cookie("zx_session", session_id)
            self._set_cookie("zx_item", item_id)
            self._html(ui.study_page(
                self._study_context(conn, learner_id, item_id, session_id)))
        except svc.LearningServiceError:
            self._natural_error("这一步没有成功", "请回到教材里重新选一个词。")
        finally:
            conn.close()

    def _study_done(self, form):
        """「我看完了」→ study / done（同一 Session 内进入 Recall）。"""
        session_id, learner_id = (form.get("session_id") or "", form.get("learner_id") or "")
        item_id = self._item_from_form(form)
        if not item_id:
            return self._natural_error("没有找到这个词", "请重新选一个词开始。")
        conn = self._conn()
        try:
            try:
                session = flow.session_of(conn, session_id, learner_id)
            except svc.LearningServiceError:
                return self._natural_error("刚才的学习没有找到", "请重新选一个词开始。")
            if session["ended_at"] is None and not self._has_study_record(conn, session_id, item_id):
                try:
                    flow.record_study(conn, session_id, item_id, learner_id,
                                      self.contentpack_path)
                except svc.LearningServiceError:
                    return self._natural_error("这一步没有成功", "请再点一次「我看完了」。")
            self._html(self._recall_html(conn, learner_id, item_id, session_id, reveal=False))
        finally:
            conn.close()

    def _has_study_record(self, conn, session_id, item_id) -> bool:
        """重复提交保护（只读判断，不改冻结服务）：同一 Session 已有 study 记录则不再写。"""
        row = conn.execute(
            "SELECT 1 FROM learning_record r JOIN learning_session s ON s.task_id=r.task_id "
            "WHERE s.session_id=? AND r.item_id=? AND r.activity_type='study' LIMIT 1",
            (session_id, item_id)).fetchone()
        return row is not None

    def _recall_html(self, conn, learner_id, item_id, session_id, reveal):
        ctx = self._study_context(conn, learner_id, item_id, session_id)
        # C4-07：Recall 的「返回」回到同一个词的 Study（只读回放，可再看一遍）
        ctx.update({"reveal": reveal, "choices": flow.CHOICES,
                    "back_href": "/vocabulary/study", "back_label": "返回学习"})
        return ui.recall_page(ctx)

    def _study_get(self):
        """C4-07：Study 页面**只读回放**（用 Cookie 里的当前学习，不创建任何数据）。

        严格只读：不创建 Session / Task / TaskItem / LearningRecord / Mastery，
        也不重新开始学习；状态不足时给自然语言页面。
        """
        cookies = self._cookies()
        session_id, item_id = cookies.get("zx_session"), cookies.get("zx_item")
        if not session_id or not item_id:
            return self._natural_error("请先选一个词", "从教材或「需要再学」里选一个词开始。")
        conn = self._conn()
        try:
            try:
                session = flow.session_of(conn, session_id)
                learner_id = session["learner_id"]
            except svc.LearningServiceError:
                return self._natural_error("请先选一个词",
                                           "从教材或「需要再学」里选一个词开始。")
            if session["ended_at"] is not None:
                return self._natural_error("这次学习已经结束", "可以看看这次的结果。",
                                           "/vocabulary/result", "看看结果")
            try:
                ctx = self._study_context(conn, learner_id, item_id, session_id)
            except svc.LearningServiceError:
                return self._natural_error("没有找到这个词", "请从教材里重新选一个词。")
            self._html(ui.study_page(ctx))
        finally:
            conn.close()

    def _recall_reveal(self, form):
        """「显示意思」：只展示，不产生任何学习记录。"""
        session_id, learner_id = (form.get("session_id") or "", form.get("learner_id") or "")
        item_id = self._item_from_form(form)
        if not item_id:
            return self._natural_error("没有找到这个词", "请重新选一个词开始。")
        conn = self._conn()
        try:
            try:
                flow.session_of(conn, session_id, learner_id)
            except svc.LearningServiceError:
                return self._natural_error("刚才的学习没有找到", "请重新选一个词开始。")
            self._html(self._recall_html(conn, learner_id, item_id, session_id, reveal=True))
        finally:
            conn.close()

    # ---- P2-2 教材练习（教材练习 + 官方音频 + 规则判分；记录走冻结服务） -------
    def _unit_of_exercise(self, exercise):
        return content_mod.get_unit(content_mod.unit_slug(exercise["unit"]),
                                    self.contentpack_path)

    def _exercise_list(self, unit):
        items = ex_mod.exercises_of_unit(unit["unit_code"])
        for e in items:
            e["key"] = ex_mod.exercise_key(e["exercise_id"])
            e["question_label"] = ex_mod.QUESTION_LABELS.get(
                e.get("question_type") or "", ex_mod.TYPE_LABELS.get(e.get("type"), "练习"))
        self._html(ui.exercise_list_page({"unit": unit, "exercises": items,
                                          "type_labels": ex_mod.TYPE_LABELS}))

    def _exercise_get(self, path):
        key = path[len("/exercise/"):].strip("/")
        e = ex_mod.find_by_key(key)
        if e is None:
            return self._natural_error("没有找到这个练习", "请从教材单元里重新打开。",
                                       "/textbook", "回到教材中心")
        unit = self._unit_of_exercise(e)
        if unit is None:
            return self._natural_error("没有找到这个练习", "请从教材单元里重新打开。",
                                       "/textbook", "回到教材中心")
        questions = ex_mod.build_questions(e, self.contentpack_path)
        self._html(ui.exercise_page({
            "exercise": e, "questions": questions, "unit": unit, "key": key,
            "type_labels": ex_mod.TYPE_LABELS, "audio_url": ex_mod.audio_url(e),
            "ask_name": self._cookie_learner_id() is None}))

    def _exercise_submit(self, path, form):
        key = path[len("/exercise/"):-len("/submit")].strip("/")
        e = ex_mod.find_by_key(key)
        if e is None:
            return self._natural_error("没有找到这个练习", "请从教材单元里重新打开。",
                                       "/textbook", "回到教材中心")
        unit = self._unit_of_exercise(e)
        questions = ex_mod.build_questions(e, self.contentpack_path)
        grade = ex_mod.grade(e, questions, form)

        activity_type = ex_mod.TYPE_BEHAVIOR.get(e["type"], "understand")
        entry_point = {"listening": "listening", "reading": "reading"}.get(e["type"], "activity")
        answers = {k: v for k, v in form.items()
                   if (k.startswith("q") and k[1:].isdigit())
                   or (k.startswith("m") and k[1:].isdigit())
                   or k == "self_check"}
        payload = json.dumps({"answers": answers, "result": grade["result"],
                              "summary": grade.get("summary")}, ensure_ascii=False)
        conn = self._conn()
        try:
            learner_id = self._learner_from_cookies(conn)
            name = (form.get("name") or "").strip()
            if not learner_id and name:
                try:
                    learner_id = flow.resolve_learner(conn, name)
                except svc.LearningServiceError:
                    self._html(ui.exercise_name_error(key), 200)
                    return
                self._set_cookie("zx_learner", learner_id)
            if not learner_id:
                self._html(ui.exercise_name_error(key), 200)
                return
            try:
                session = ses.create_learning_session(
                    conn, learner_id, entry_point, [e["exercise_id"]],
                    contentpack_path=self.contentpack_path)
                ses.record_session_event(
                    conn, session["session_id"], e["exercise_id"], activity_type,
                    result=grade["result"], response_raw=payload, learner_id=learner_id,
                    contentpack_path=self.contentpack_path)
                ses.end_learning_session(conn, session["session_id"], learner_id)
            except svc.LearningServiceError as exc:
                print("[web] 练习记录失败：%r" % (exc,))
                return self._natural_error("这一步没有成功", "请再提交一次。",
                                           "/exercise/%s" % key, "回到练习")
            self._html(ui.exercise_result_page({"exercise": e, "grade": grade,
                                                "unit": unit, "key": key}))
        finally:
            conn.close()

    def _result_html(self, conn, learner_id, item_id, session_id, result):
        ctx = self._study_context(conn, learner_id, item_id, session_id)
        ctx["recall_label"] = flow.RESULT_LABELS.get(result)
        unit = ctx.get("unit")
        ctx["back_to_list"] = (("/unit/%s/resources/vocabulary" % unit["slug"])
                               if unit else "/textbook")
        return ui.result_page(ctx)

    def _practice(self, form):
        """三选一 → 恰好一条 practice 记录 → 结束 Session → Result。"""
        session_id, learner_id = (form.get("session_id") or "", form.get("learner_id") or "")
        item_id = self._item_from_form(form)
        choice = (form.get("choice") or "").strip()
        if not item_id:
            return self._natural_error("没有找到这个词", "请重新选一个词开始。")
        conn = self._conn()
        try:
            try:
                session = flow.session_of(conn, session_id, learner_id)
            except svc.LearningServiceError:
                return self._natural_error("刚才的学习没有找到", "请重新选一个词开始。")
            if session["ended_at"] is not None:
                # 重复提交：只读回放，绝不写第二条记录
                result = flow.latest_practice_result(conn, session["task_id"], item_id)
                if result is None:
                    return self._natural_error("这次学习已经结束", "可以从词汇表里再选一个词。")
                return self._html(self._result_html(conn, learner_id, item_id, session_id, result))
            if choice not in flow.CHOICE_RESULTS:
                return self._natural_error(
                    "请选择「我记得 / 有点模糊 / 忘了」中的一个",
                    "回到上一步重新选一次即可。", "/vocabulary/recall", "回到上一步")
            try:
                out = flow.record_choice(conn, session_id, item_id, learner_id, choice,
                                         self.contentpack_path)
                flow.end_session(conn, session_id, learner_id)
            except svc.LearningServiceError:
                return self._natural_error("这一步没有成功", "请再选一次。")
            self._html(self._result_html(conn, learner_id, item_id, session_id,
                                         out["record"]["result"]))
        finally:
            conn.close()

    # ---- 刷新/返回：GET 只读回放（不写库），状态不足时给自然语言页面 ----------
    def _recall_get(self):
        cookies = self._cookies()
        session_id, item_id = cookies.get("zx_session"), cookies.get("zx_item")
        if not session_id or not item_id:
            return self._natural_error("请先选一个词", "从教材或「需要再学」里选一个词开始。")
        conn = self._conn()
        try:
            try:
                session = flow.session_of(conn, session_id)
                learner_id = session["learner_id"]
            except svc.LearningServiceError:
                return self._natural_error("请先选一个词", "从教材或「需要再学」里选一个词开始。")
            if session["ended_at"] is not None:
                return self._natural_error("这次学习已经结束", "可以看看这次的结果。",
                                           "/vocabulary/result", "看看结果")
            self._html(self._recall_html(conn, learner_id, item_id, session_id, reveal=False))
        finally:
            conn.close()

    def _result_get(self):
        cookies = self._cookies()
        session_id, item_id = cookies.get("zx_session"), cookies.get("zx_item")
        if not session_id or not item_id:
            return self._natural_error("还没有学完一个词", "从教材里选一个词开始吧。")
        conn = self._conn()
        try:
            try:
                session = flow.session_of(conn, session_id)
                learner_id = session["learner_id"]
            except svc.LearningServiceError:
                return self._natural_error("还没有学完一个词", "从教材里选一个词开始吧。")
            result = flow.latest_practice_result(conn, session["task_id"], item_id)
            if result is None:
                return self._natural_error("这次学习还没有完成", "回到上一步做完回忆判断。",
                                           "/vocabulary/recall", "回到上一步")
            self._html(self._result_html(conn, learner_id, item_id, session_id, result))
        finally:
            conn.close()

    # ---- 需要再学（只读池入口） ----------------------------------------------
    def _review(self, form=None):
        conn = self._conn()
        try:
            learner_id = self._learner_from_cookies(conn)
            name = ((form or {}).get("name") or "").strip()
            if name:
                try:
                    learner_id = flow.resolve_learner(conn, name)
                except svc.LearningServiceError:
                    return self._html(ui.name_entry_page("/review", "请再试一次。"), 200)
                self._set_cookie("zx_learner", learner_id)
            if not learner_id:
                return self._html(ui.name_entry_page("/review"), 200)
            pool = flow.need_relearn(conn, learner_id, self.contentpack_path)
            self._html(ui.review_page({"pool": pool,
                                       "suggestions": flow.textbook_review_suggestions(
                                           conn, learner_id, self.contentpack_path),
                                       "lo_section": flow.lo_review_section(
                                           conn, learner_id, self.contentpack_path),
                                       "learner_name": flow.learner_name(conn, learner_id)}))
        except svc.LearningServiceError:
            self._natural_error("需要再学暂时打不开", "请稍后再试。", "/", "回到首页")
        finally:
            conn.close()

    def log_message(self, fmt, *args):
        print("[web] %s - %s" % (self.address_string(), fmt % args))


def _lan_hint(port: int) -> str:
    """局域网访问提示（不做任何网络探测：启动过程完全不联网）。"""
    return "http://<本机IPv4>:%d/  （用 ipconfig 查看本机 IPv4，手机与电脑需在同一网络）" % port


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="正式 Web UI 最小骨架（只读）")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--db", default=str(content_mod.LEARNING_DB), help="learning.db（只读使用）")
    ap.add_argument("--contentpack", default=str(content_mod.CONTENTPACK))
    args = ap.parse_args()

    Handler.learning_db = Path(args.db)
    Handler.contentpack_path = Path(args.contentpack)

    if not Handler.learning_db.exists():
        print("STOP: learning.db 不存在:", Handler.learning_db)
        return 2
    if not Handler.contentpack_path.exists():
        print("STOP: contentpack v5 不存在:", Handler.contentpack_path)
        return 2

    print("正式 Web UI（只读）")
    print("  learning.db  :", Handler.learning_db)
    print("  contentpack  :", Handler.contentpack_path, "（只读）")
    print("  本机访问     : http://127.0.0.1:%d/" % args.port)
    print("  局域网访问   :", _lan_hint(args.port), "（供手机 / Android WebView 使用）")
    print("  健康检查     : /health")
    with ThreadingHTTPServer((args.host, args.port), Handler) as srv:
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())

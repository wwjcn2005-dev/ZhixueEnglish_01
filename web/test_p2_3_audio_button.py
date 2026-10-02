#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-3 词汇音频按钮 UI 测试（扬声器 + 声波；纯 CSS，不依赖 JavaScript）

覆盖：
  * 静止状态：存在扬声器图标（🔊），不显示系统原生播放三角
  * 播放状态：存在动态状态标识（audio:playing 下的声波动画）
  * 播放结束：自动恢复静止（声波默认不可见，动画只挂在真实播放状态上）
  * 点击区域 40×40（移动端可触控），图标本体小巧
  * 说明文字已删除（列表页 / Study 页均无"播放/点击播放/单词发音/发音"）
  * 语义不混用：Vocabulary = 🔊，Textbook Exercise = 🎧
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import ui                               # noqa: E402
import content as content_mod           # noqa: E402


def body_of(html: str) -> str:
    return re.sub(r"(?s)<style>.*?</style>", "", html)


def visible_text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body_of(html)))


def list_page():
    return ui.resource_list_page({
        "unit": {"slug": "starter", "unit_code": "Starter", "title": "Welcome"},
        "kind": "vocabulary", "label": "词汇", "unmapped_count": 0, "has_study": True,
        "items": [{"item_id": "X", "key": "k", "text": "ready", "phonetic": "/ˈredi/",
                   "part_of_speech": "adj", "meaning": "准备好的", "can_study": True,
                   "status_label": "", "order": (155, 2),
                   "audio_url": "/audio/word/abc.wav"}]})


def study_page():
    return ui.study_page({
        "word": "ready", "phonetic": "/ˈredi/", "part_of_speech": "adj",
        "meaning": "准备好的", "session_id": "S1", "key": "k", "learner_id": "L1",
        "back_href": "/textbook", "source_unit_label": "Starter · Welcome",
        "source_list_label": "Words and expressions · 第 150 页",
        "word_audio_url": "/audio/word/abc.wav"})


def exercise_page():
    return ui.exercise_page({
        "exercise": {"exercise_id": "X:1", "unit": "Unit 1", "section": "DEVELOPING_IDEAS",
                     "exercise_no": 1, "textbook_page": 21,
                     "instruction": "Listen to the radio.", "type": "listening"},
        "questions": {"kind": "self_check", "questions": [], "note": "n"},
        "unit": {"slug": "unit1", "unit_code": "Unit 1"},
        "key": "k", "type_labels": {"listening": "听力"},
        "audio_url": "/audio/official/AU09.mp3", "ask_name": False})


class SpeakerButtonTest(unittest.TestCase):
    """静止状态 / 播放状态 / 点击区域。"""

    def test_01_vocabulary_uses_speaker_icon(self):
        body = body_of(list_page())
        self.assertIn('class="spk word"', body)
        self.assertIn('data-ico="🔊"', body)
        self.assertIn("/audio/word/abc.wav", body)          # 音频 URL 未变

    def test_02_no_native_play_triangle(self):
        """系统原生播放器（三角按钮/进度条）不可见：原生控件整体透明。"""
        self.assertIn("opacity:0;background:transparent", ui.STYLE)
        self.assertIn(".spk audio{position:absolute;left:0;top:0;width:320px;height:40px;",
                      ui.STYLE)
        self.assertNotIn("::-webkit-media-controls-play-button{opacity:1", ui.STYLE)

    def test_03_tap_area_is_40x40_with_small_icon(self):
        self.assertIn(".spk{position:relative;display:inline-block;width:40px;height:40px;"
                      "overflow:hidden;", ui.STYLE)
        self.assertIn("font-size:17px;line-height:1;opacity:.72", ui.STYLE)

    def test_04_playing_state_has_waves(self):
        """播放状态：3 条声波柱 + 由真实播放状态（audio:playing）驱动的循环动画。"""
        body = body_of(list_page())
        self.assertEqual(body.count("<i></i>"), 3)
        self.assertIn(".spk-ico i{", ui.STYLE)
        self.assertIn(".spk:has(audio:playing) .spk-ico i{opacity:.9;animation:zxwave",
                      ui.STYLE)
        self.assertIn("@keyframes zxwave", ui.STYLE)

    def test_05_idle_state_has_no_waves(self):
        """静止/播放结束：声波默认完全不可见（不依赖 JS、也不是"永远播放中"的假动画）。"""
        m = re.search(r"\.spk-ico i\{([^}]*)\}", ui.STYLE)
        self.assertIsNotNone(m)
        self.assertIn("opacity:0", m.group(1))
        # 动画只挂在真实播放状态上；静止状态下没有任何 animation
        idle_rules = [r for r in re.findall(r"([^{}]+)\{([^}]*animation[^}]*)\}", ui.STYLE)]
        for selector, decl in idle_rules:
            # 触发条件必须是真实状态：:playing（原生播放）/.on（JS 真实播放中）/
            # .rec（正在录音）/.analyzing（录音结束后的分析态）
            self.assertTrue(any(t in selector for t in (":playing", ".on", ".rec", ".analyzing")),
                            "动画只能由真实状态触发：%s" % selector)

    def test_06_semantics_not_mixed(self):
        self.assertIn('data-ico="🔊"', body_of(list_page()))
        self.assertIn('data-ico="🔊"', body_of(study_page()))
        ex = body_of(exercise_page())
        self.assertIn('data-ico="🎧"', ex)
        self.assertNotIn('data-ico="🔊"', ex)

    def test_07_no_explanatory_text_near_speaker(self):
        for label, html in (("词汇列表", list_page()), ("Study 页", study_page())):
            text = visible_text(html)
            for token in ("播放", "点击播放", "单词发音", "发音", "点一下扬声器"):
                self.assertNotIn(token, text, "%s 不应出现说明文字：%s" % (label, token))

    def test_08_word_and_layout_unchanged(self):
        body = body_of(list_page())
        self.assertIn('<div class="w core">ready</div>', body)      # 单词与加粗未变
        self.assertIn("学习这个词", body)                            # 学习入口未变
        study = body_of(study_page())
        self.assertIn("我看完了", study)
        self.assertLess(study.index("我看完了"), study.index("教材来源"))

    def test_09_audio_url_and_mapping_unchanged(self):
        """音频 URL 形态与映射来源未变（仍走 /audio/word/<key>.wav 与 /audio/official/AUxx.mp3）。"""
        self.assertIn('src="/audio/word/abc.wav"', list_page())
        self.assertIn('src="/audio/official/AU09.mp3"', exercise_page())

    def test_10_no_javascript_dependency(self):
        """整个页面不得引入 <script>（WebView 关闭 JS）。"""
        for html in (list_page(), study_page(), exercise_page()):
            self.assertNotIn("<script", html.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)

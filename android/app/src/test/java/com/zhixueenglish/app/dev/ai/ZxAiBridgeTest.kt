package com.zhixueenglish.app.dev.ai

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 「AI 老师」题型族分派单测（V1.3 第二十九章 §19 第 4 条 / 流程规范 §27）。
 *
 * `questionFamily()` / `familyInstruction()` 已置于 `companion object`，
 * **不依赖 Context / WebView**，可纯 JVM 直测（无需反射、无需实例化）。
 */
class ZxAiBridgeTest {

    @Test
    fun `word form is grammar family`() {
        assertEquals("grammar", ZxAiBridge.questionFamily("vocab_word_form"))
    }

    @Test
    fun `vocab and phrase and phonetics are vocab family`() {
        for (t in listOf(
            "vocab_listen_write", "vocab_meaning_choice", "vocab_context_choice",
            "vocab_phonetic_write", "phrase_meaning_choice", "phonetics_sound_choice",
            "phonetics_symbol_write"
        )) {
            assertEquals("词汇族应为 vocab: $t", "vocab", ZxAiBridge.questionFamily(t))
        }
    }

    @Test
    fun `comprehension family covers listen read textbook`() {
        for (t in listOf(
            "textbook_native", "sentence_listen_write", "sentence_listen_choice",
            "listening_choice", "listen_choice", "listen_fill", "reading_choice"
        )) {
            assertEquals("理解族应为 comprehension: $t", "comprehension", ZxAiBridge.questionFamily(t))
        }
    }

    @Test
    fun `writing family covers writing types`() {
        for (t in listOf("writing", "writing_task", "reading_for_writing")) {
            assertEquals("写作族应为 writing: $t", "writing", ZxAiBridge.questionFamily(t))
        }
    }

    @Test
    fun `grammar instruction forbids grammar jargon`() {
        val s = ZxAiBridge.familyInstruction("grammar")
        assertTrue("语法族必须声明题型族", s.contains("语法"))
        assertTrue("语法族必须禁止语法术语", s.contains("不得") && s.contains("语法术语"))
    }

    @Test
    fun `vocab instruction requires textbook context sentence`() {
        val s = ZxAiBridge.familyInstruction("vocab")
        assertTrue("词汇族必须声明题型族", s.contains("词汇"))
        assertTrue("词汇族必须要求教材语境句", s.contains("教材语境"))
    }

    @Test
    fun `comprehension instruction prefers textbook original sentence`() {
        val s = ZxAiBridge.familyInstruction("comprehension")
        assertTrue("理解族必须声明题型族", s.contains("理解"))
        assertTrue("理解族必须优先教材原句", s.contains("教材原句"))
    }

    @Test
    fun `writing instruction forbids long sample essay`() {
        val s = ZxAiBridge.familyInstruction("writing")
        assertTrue("写作族必须声明题型族", s.contains("写作"))
        assertTrue("写作族必须禁止范文式长文", s.contains("范文"))
    }

    @Test
    fun `unknown type falls back to comprehension`() {
        assertEquals("comprehension", ZxAiBridge.questionFamily("something_unknown"))
    }

    @Test
    fun `every family has non-empty instruction`() {
        for (f in listOf("grammar", "vocab", "comprehension", "writing")) {
            assertTrue("族指令不得为空: $f", ZxAiBridge.familyInstruction(f).isNotBlank())
        }
    }
}

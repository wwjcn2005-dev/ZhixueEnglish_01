package com.zhixueenglish.app.dev

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * 提交结果页返回拦截（方案 B）单测。
 *
 * `safeBackUrl()` 是纯函数（只做 URL 解析与字符串拼接），可 JVM 直测。
 * 它决定：**按返回键时是否拦截、以及跳到哪个安全页**。
 */
class SafeBackUrlTest {

    /** 与实现一致：去掉 `WEB_BASE_URL` 结尾的 "/"，避免拼出双斜杠。 */
    private val base = com.zhixueenglish.app.dev.BuildConfig.WEB_BASE_URL.trimEnd('/')

    // ---------- 应拦截：p5 提交结果页 ----------

    @Test
    fun `p5 form submit is intercepted and goes to entry GET page`() {
        val got = safeBackUrl("http://127.0.0.1:8770/unit/unit1/p5/form/submit?lesson=STARTING_OUT")
        assertEquals("$base/unit/unit1/p5/form?lesson=STARTING_OUT", got)
    }

    @Test
    fun `index param is preserved`() {
        val got = safeBackUrl("http://127.0.0.1:8770/unit/unit1/p5/check/submit?lesson=UNDERSTANDING_IDEAS&i=3")
        assertEquals("$base/unit/unit1/p5/check?lesson=UNDERSTANDING_IDEAS&i=3", got)
    }

    @Test
    fun `other unrelated query params are dropped`() {
        val got = safeBackUrl("http://127.0.0.1:8770/unit/unit2/p5/listen/submit?lesson=GET_READY&foo=bar")
        assertEquals("$base/unit/unit2/p5/listen?lesson=GET_READY", got)
    }

    @Test
    fun `submit without query still yields entry page`() {
        val got = safeBackUrl("http://127.0.0.1:8770/unit/unit1/p5/phonetic/submit")
        assertEquals("$base/unit/unit1/p5/phonetic", got)
    }

    // ---------- 不应拦截：正常页面 ----------

    @Test
    fun `plain p5 page is redirected to its own GET page`() {
        // 2026-09-30 改版：提交后后端渲染的仍是 GET URL，只在 /submit 时拦截不够
        // ⇒ **任意 P5 页**都归一为它自己的 GET 页（否则 goBack 会退到 POST 条目报 ERR_CACHE_MISS）
        assertEquals("$base/unit/unit1/p5/form?lesson=STARTING_OUT",
            safeBackUrl("http://127.0.0.1:8770/unit/unit1/p5/form?lesson=STARTING_OUT"))
    }

    @Test
    fun `mode param is preserved`() {
        assertEquals("$base/unit/unit1/p5/wordform?lesson=STARTING_OUT&mode=form",
            safeBackUrl("http://127.0.0.1:8770/unit/unit1/p5/wordform?lesson=STARTING_OUT&mode=form"))
    }

    @Test
    fun `home page is not intercepted`() {
        assertNull(safeBackUrl("$base/"))
    }

    @Test
    fun `text page is not intercepted`() {
        assertNull(safeBackUrl("$base/unit/unit1/text"))
    }

    @Test
    fun `progress page is not intercepted`() {
        assertNull(safeBackUrl("$base/progress"))
    }

    @Test
    fun `non p5 submit route is not intercepted`() {
        // 路径第 3 段不是 p5 ⇒ 不拦截（避免误伤其它路由）
        assertNull(safeBackUrl("$base/unit/unit1/exercises/submit"))
    }

    @Test
    fun `p5 page without query is still redirected`() {
        assertEquals("$base/unit/unit1/p5/check", safeBackUrl("$base/unit/unit1/p5/check"))
    }

    // ---------- 边界 ----------

    @Test
    fun `null and empty are safe`() {
        assertNull(safeBackUrl(null))
        assertNull(safeBackUrl(""))
    }

    @Test
    fun `too short path is not intercepted`() {
        assertNull(safeBackUrl("$base/unit/unit1"))
    }
}

package com.zhixueenglish.app.dev.ai

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * AI 接口纯逻辑测试：URL 组装 + Key 掩码/抹除 + 围栏剥离 + 证据计数 + 确定性闸门。
 *
 * **不联网、不依赖 Android 运行时、不使用 org.json**
 * （Android 单测的 `org.json` 是抛 `RuntimeException("Stub!")` 的桩，
 * 因此契约与闸门全部建立在纯 Kotlin 的 Map / List 之上）。
 */
class AiEndpointTest {

    @Test
    fun baseUrlWithVersion_getsChatCompletionsAppended() {
        assertEquals(
            "https://api.example.com/v1/chat/completions",
            AiEndpoint.chatCompletionsUrl("https://api.example.com/v1")
        )
    }

    @Test
    fun baseUrlTrailingSlash_isNormalized() {
        assertEquals(
            "https://api.example.com/v1/chat/completions",
            AiEndpoint.chatCompletionsUrl("https://api.example.com/v1/")
        )
    }

    @Test
    fun baseUrlAlreadyComplete_isKeptAsIs() {
        assertEquals(
            "https://api.example.com/v1/chat/completions",
            AiEndpoint.chatCompletionsUrl("https://api.example.com/v1/chat/completions")
        )
    }

    @Test
    fun baseUrlWithoutScheme_defaultsToHttps() {
        assertEquals(
            "https://api.example.com/v1/chat/completions",
            AiEndpoint.chatCompletionsUrl("api.example.com/v1")
        )
    }

    @Test
    fun emptyBaseUrl_isNotConfigured() {
        assertEquals("", AiEndpoint.chatCompletionsUrl("   "))
        assertFalse(AiEndpoint.isPlausibleBaseUrl(""))
    }

    @Test
    fun maskNeverReturnsFullKey() {
        // 仅用于验证脱敏逻辑的假字符串（不是任何真实 Key，也不是可用的测试 Key）
        val key = "DUMMY-VALUE-FOR-REDACTION-TEST"
        val masked = AiEndpoint.maskedKey(key)
        assertFalse(masked.contains(key))
        assertTrue(masked.endsWith("TEST"))
        assertEquals("••••", AiEndpoint.maskedKey("short"))
        assertEquals("", AiEndpoint.maskedKey(""))
    }

    @Test
    fun redactRemovesRawKeyFromMessages() {
        val key = "DUMMY-VALUE-FOR-REDACTION-TEST"
        val text = "HTTP 401：{\"error\":\"invalid api key $key\"}"
        val safe = AiEndpoint.redact(text, key)
        assertFalse(safe.contains(key))
        assertTrue(safe.contains("••••TEST"))
    }

    @Test
    fun redactKeepsTextWhenKeyIsAbsent() {
        assertEquals("HTTP 500：服务不可用", AiEndpoint.redact("HTTP 500：服务不可用", ""))
    }

    // ------------------------------------------------------------------ 批次 3 新增

    @Test
    fun stripMarkdownFence_plainJson_isUntouched() {
        val json = """{"correctness":"correct"}"""
        assertEquals(json, AiEndpoint.stripMarkdownFence(json))
        // 两端空白只裁剪，不改变内容
        assertEquals(json, AiEndpoint.stripMarkdownFence("  $json\n"))
    }

    @Test
    fun stripMarkdownFence_fencedJson_isUnwrapped() {
        val json = """{"correctness":"correct"}"""
        assertEquals(json, AiEndpoint.stripMarkdownFence("```json\n$json\n```"))
        assertEquals(json, AiEndpoint.stripMarkdownFence("```\n$json\n```"))
        assertEquals(json, AiEndpoint.stripMarkdownFence("```JSON $json```"))
    }

    @Test
    fun stripMarkdownFence_halfFence_isNotOverStripped() {
        // 只有开头或只有结尾的半截围栏：不视为围栏，原样返回（随后 JSON 解析会失败，不在此处掩盖）
        val onlyOpen = "```json\n{\"a\":1}"
        assertEquals(onlyOpen, AiEndpoint.stripMarkdownFence(onlyOpen))
        val onlyClose = "{\"a\":1}\n```"
        assertEquals(onlyClose, AiEndpoint.stripMarkdownFence(onlyClose))
    }

    @Test
    fun countEvidence_excludesRelatedImage() {
        // 只有图片非空 → 证据条数为 0（图片不是可引用的文本证据）
        assertEquals(0, AiEvidencePrompt.countEvidence(mapOf("related_image" to listOf("p8-b1"))))
        // 文本类 4 个字段各计 1；图片再多也不增加
        val fourPlusImage = mapOf(
            "related_text" to listOf("t"),
            "related_vocabulary" to listOf("v"),
            "related_grammar" to listOf("g"),
            "related_listening" to listOf("l"),
            "related_image" to listOf("i1", "i2"),
        )
        assertEquals(4, AiEvidencePrompt.countEvidence(fourPlusImage))
    }

    @Test
    fun countEvidence_nullPackage_isZero() {
        // 证据包与题库零关联（已记录阻塞）：拿不到证据包时必须为 0，绝不伪造
        assertEquals(0, AiEvidencePrompt.countEvidence(null))
        // 空字符串 / 空列表同样不算证据
        assertEquals(0, AiEvidencePrompt.countEvidence(mapOf("related_text" to "")))
        assertEquals(0, AiEvidencePrompt.countEvidence(mapOf("related_text" to emptyList<String>())))
    }

    @Test
    fun gate_evidenceBelowTwo_capsConfidenceAndBlocksNeedNow() {
        val verdict = AiConfidenceGate.vet(
            fullValidJson(confidence = "high", needIntervention = "need_now"),
            evidenceCount = 1,
        )
        assertTrue(verdict.ok)
        assertEquals("medium", verdict.data!!["confidence"])
        assertEquals("watch", verdict.data!!["need_intervention"])
        assertEquals("insufficient_evidence", verdict.data!!["need_now_blocked_reason"])
        assertEquals(1, verdict.data!!["evidence_count_used"])
    }

    @Test
    fun gate_evidenceAtLeastTwo_keepsAiValues() {
        val verdict = AiConfidenceGate.vet(
            fullValidJson(confidence = "high", needIntervention = "need_now"),
            evidenceCount = 2,
        )
        assertTrue(verdict.ok)
        assertEquals("high", verdict.data!!["confidence"])
        assertEquals("need_now", verdict.data!!["need_intervention"])
        assertEquals(2, verdict.data!!["evidence_count_used"])
    }

    @Test
    fun gate_missingRequiredField_isRejected() {
        val raw = fullValidJson().toMutableMap()
        raw.remove("reason")
        val verdict = AiConfidenceGate.vet(raw, evidenceCount = 3)
        assertFalse(verdict.ok)
        assertTrue(verdict.reason.contains("reason"))
    }

    @Test
    fun gate_unknownErrorType_isRejected() {
        val raw = fullValidJson().toMutableMap()
        raw["error_type"] = "some_unknown_type"
        val verdict = AiConfidenceGate.vet(raw, evidenceCount = 3)
        assertFalse(verdict.ok)
        assertTrue(verdict.reason.contains("错误类型"))
    }

    @Test
    fun gate_outOfTextbookScope_clearsAbilityJudgement() {
        val raw = fullValidJson(confidence = "high", needIntervention = "need_now").toMutableMap()
        raw["in_textbook_scope"] = false
        val verdict = AiConfidenceGate.vet(raw, evidenceCount = 3)
        assertTrue(verdict.ok)
        assertEquals("no", verdict.data!!["need_intervention"])
        assertEquals("uncertain", verdict.data!!["likely_slip"])
        assertEquals("medium", verdict.data!!["confidence"])
        assertEquals("out_of_textbook_scope", verdict.data!!["need_now_blocked_reason"])
        assertEquals(0, (verdict.data!!["suggested_interventions"] as List<*>).size)
    }

    @Test
    fun gate_emptyEvidenceUsed_isRejectedAsInsufficientEvidence() {
        val raw = fullValidJson().toMutableMap()
        raw["evidence_used"] = emptyList<String>()
        val verdict = AiConfidenceGate.vet(raw, evidenceCount = 3)
        assertFalse(verdict.ok)
        assertTrue(verdict.reason.contains("证据不足"))
    }

    @Test
    fun gate_invalidConfidence_isCoercedWithReason() {
        val raw = fullValidJson().toMutableMap()
        raw["confidence"] = "very_high"
        val verdict = AiConfidenceGate.vet(raw, evidenceCount = 3)
        assertTrue(verdict.ok)
        assertEquals("medium", verdict.data!!["confidence"])
        assertEquals("invalid_value", verdict.data!!["confidence_coerced_reason"])
    }

    @Test
    fun gateReasonIsRedactable() {
        // Key 泄漏检查：闸门理由可能回显 AI 文本，但经 AiEndpoint.redact 后必须不含 Key
        val key = "DUMMY-VALUE-FOR-REDACTION-TEST"
        val raw = fullValidJson().toMutableMap()
        raw["error_type"] = "leaked-$key"
        val verdict = AiConfidenceGate.vet(raw, evidenceCount = 3)
        assertFalse(verdict.ok)
        assertFalse(AiEndpoint.redact(verdict.reason, key).contains(key))
    }

    @Test
    fun buildSystem_statesContractFieldsAndClosedSet() {
        val system = AiEvidencePrompt.buildSystem()
        // 10 个必需字段全部出现在 system 里（保证模型知道要输出什么）
        for (f in AiContract.REQUIRED_FIELDS) assertTrue("缺少字段说明：$f", system.contains(f))
        // 封闭集合的每个取值都出现在 system 里
        for (t in AiContract.ERROR_TYPES) assertTrue("缺少错误类型：$t", system.contains(t))
        // 不含任何 Key 相关字样
        assertFalse(system.contains("Bearer"))
    }

    @Test
    fun buildUser_withoutEvidencePackage_declaresInsufficientEvidence() {
        val question = mapOf(
            "question_type" to "textbook_native",
            "answer_kind" to "ai_eval",
            "prompt" to mapOf("instruction" to "Match the words", "text" to "with the countries."),
        )
        val user = AiEvidencePrompt.buildUser(question, "Russia", null)
        assertTrue(user.contains("Match the words"))
        assertTrue(user.contains("Russia"))
        assertTrue(user.contains("无（本次未取得该题的教材证据包）"))
        assertTrue(user.contains("confidence 不得高于 medium"))
        assertTrue(user.contains("need_intervention 不得为 need_now"))
    }

    // ---- 回退验证：call() 重构后失败文案必须与重构前【逐字一致】 ----
    // 重构前 call() 的两条失败路径：
    //   异常 → AiResult.Failure(redact("<异常类名>：<消息>"))
    //   非 2xx → AiResult.Failure(redact("HTTP <code>：<body.take(300) 或 '无响应内容'>"))
    // 这里直接对 failureOf() 断言，把"逐字一致"固化为永不回归的测试。

    @Test
    fun failureOf_networkError_matchesOriginalWording() {
        val raw = AiClient.RawResponse(
            code = -1, body = "",
            error = "ConnectException：Failed to connect to /api.deepseek.com",
        )
        val failure = AiClient.failureOf(raw, apiKey = "")
        assertEquals("ConnectException：Failed to connect to /api.deepseek.com", failure.message)
        // 重构前不会给异常文案加 "HTTP " 前缀（这正是重构时必须保住的行为）
        assertFalse(failure.message.startsWith("HTTP "))
    }

    @Test
    fun failureOf_httpError_matchesOriginalWording() {
        val raw = AiClient.RawResponse(code = 401, body = """{"error":"invalid api key"}""")
        val failure = AiClient.failureOf(raw, apiKey = "")
        assertEquals("""HTTP 401：{"error":"invalid api key"}""", failure.message)
    }

    @Test
    fun failureOf_emptyBody_usesOriginalPlaceholder() {
        val raw = AiClient.RawResponse(code = 500, body = "")
        assertEquals("HTTP 500：无响应内容", AiClient.failureOf(raw, apiKey = "").message)
    }

    @Test
    fun failureOf_longBody_isTruncatedTo300Chars() {
        val raw = AiClient.RawResponse(code = 400, body = "x".repeat(500))
        val msg = AiClient.failureOf(raw, apiKey = "").message
        assertEquals("HTTP 400：" + "x".repeat(300), msg)
    }

    @Test
    fun failureOf_redactsKeyInErrorAndBody() {
        val key = "DUMMY-VALUE-FOR-REDACTION-TEST"
        val fromError = AiClient.failureOf(
            AiClient.RawResponse(-1, "", "boom $key"), apiKey = key
        ).message
        assertFalse(fromError.contains(key))
        val fromBody = AiClient.failureOf(
            AiClient.RawResponse(401, "bad key $key"), apiKey = key
        ).message
        assertFalse(fromBody.contains(key))
    }

    // ---- J1：证据粒度影响闸门口径 ----

    @Test
    fun countEvidenceForGate_sectionGranularity_isForcedToOne() {
        // Section 级证据更弱 → 强制报 1（让它落入 confidence_rule 的 <2 分支）
        val pkg = mapOf(
            "related_text" to listOf("t"),
            "related_vocabulary" to listOf("v"),
            "related_grammar" to listOf("g"),
            "related_listening" to listOf("l"),
        )
        assertEquals(4, AiContract.countEvidence(pkg))            // 实际字段数 = 4
        assertEquals(1, AiContract.countEvidenceForGate(pkg, AiContract.GRANULARITY_SECTION))
        assertEquals(1, AiEvidencePrompt.countEvidenceForGate(pkg, AiContract.GRANULARITY_SECTION))
    }

    @Test
    fun countEvidenceForGate_activityGranularity_usesActualCount() {
        val pkg = mapOf(
            "related_text" to listOf("t"),
            "related_vocabulary" to listOf("v"),
        )
        assertEquals(2, AiContract.countEvidenceForGate(pkg, AiContract.GRANULARITY_ACTIVITY))
    }

    @Test
    fun countEvidenceForGate_nullOrUnknown_isZero() {
        val pkg = mapOf("related_text" to listOf("t"))
        assertEquals(0, AiContract.countEvidenceForGate(null, AiContract.GRANULARITY_ACTIVITY))
        assertEquals(0, AiContract.countEvidenceForGate(null, AiContract.GRANULARITY_SECTION))
        assertEquals(0, AiContract.countEvidenceForGate(pkg, null))
        assertEquals(0, AiContract.countEvidenceForGate(pkg, "unknown"))
        // section 但包为 null → 0（不假装有证据）
        assertEquals(0, AiContract.countEvidenceForGate(null, AiContract.GRANULARITY_SECTION))
    }

    @Test
    fun gateAppliedWithSectionGranularity_downgradesVerdict() {
        // 端到端：Section 级 → 强制 1 → 闸门压 confidence 且禁止 need_now
        val pkg = mapOf("related_text" to listOf("t"))
        val raw = fullValidJson(confidence = "high", needIntervention = "need_now")
        val gateCount = AiEvidencePrompt.countEvidenceForGate(pkg, AiContract.GRANULARITY_SECTION)
        val verdict = AiConfidenceGate.vet(raw, gateCount)
        assertTrue(verdict.ok)
        assertEquals("medium", verdict.data!!["confidence"])
        assertEquals("watch", verdict.data!!["need_intervention"])
        assertEquals(1, verdict.data!!["evidence_count_used"])
    }

    @Test
    fun buildUser_declaresGranularity() {
        val question = mapOf(
            "question_type" to "match",
            "answer_kind" to "ai_eval",
            "prompt" to mapOf("instruction" to "Guess and match", "text" to "with the countries."),
        )
        val pkg = mapOf("related_text" to listOf("t"))
        val act = AiEvidencePrompt.buildUser(question, "Russia", pkg, AiContract.GRANULARITY_ACTIVITY)
        assertTrue(act.contains("证据粒度：活动级"))
        val sec = AiEvidencePrompt.buildUser(question, "Russia", pkg, AiContract.GRANULARITY_SECTION)
        assertTrue(sec.contains("证据粒度：Section 级"))
        assertTrue(sec.contains("不含该活动的原题指令"))
        assertTrue(sec.contains("confidence 不得高于 medium"))
        // 不传粒度（向后兼容）→ 声明"无"
        val none = AiEvidencePrompt.buildUser(question, "Russia", pkg)
        assertTrue(none.contains("证据粒度：无"))
    }

    // ---- 测试辅助 ----

    /** 构造一个通过全部闸门检查的合法输出（证据充足、范围内）。 */
    private fun fullValidJson(
        confidence: String = "medium",
        needIntervention: String = "watch",
    ): Map<String, Any?> = mapOf(
        "correctness" to "correct",
        "error_type" to "meaning",
        "reason" to "与教材原句一致",
        "in_textbook_scope" to true,
        "textbook_ref" to "Unit 1 / STARTING_OUT / A1",
        "likely_slip" to "uncertain",
        "need_intervention" to needIntervention,
        "suggested_interventions" to listOf("textbook_reread"),
        "confidence" to confidence,
        "evidence_used" to listOf("教材第 15 页原句"),
    )
}

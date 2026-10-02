package com.zhixueenglish.app.dev.ai

/**
 * AI 输出的**确定性闸门**（纯 Kotlin，无 Android / org.json 依赖，可直接单元测试）。
 *
 * 依据：
 *   * `docs/…最高指导原则与开发规范_V1.3.md:220` ——「AI 只产生候选；**能否进入系统由确定性规则决定**…
 *     未经校验的 AI 输出不得进入页面或缓存。」
 *   * `structured/learning/ai_role_model_v1.json:58-59` —— 10 个必需输出字段；
 *   * `…:14-15` —— `error_type` 是封闭集合（`closed_set: true`）；
 *   * `…:60` —— `confidence_rule`：「证据条数 <2 时 confidence ≤ medium，
 *     且 need_intervention 不得为 need_now」；
 *   * `…:17` / `…:28`（N6）—— 超出教材范围时不作能力判断；
 *   * `…:25`（N3）—— 证据不足必须明说，不给确定结论。
 *
 * 设计原则：**闸门只做"收紧"，不做"放宽"**——绝不替 AI 编造内容，
 * 只在 AI 越界时拒绝（[Verdict.ok] = false）或压低（改写 `confidence` / `need_intervention`）。
 * `confidence_rule` 属确定性规则，**由程序执行，不采信 AI 自觉**。
 */
object AiConfidenceGate {

    /** 闸门结论。[ok]=false 时 [reason] 是给孩子看的自然语言（不含技术细节、不含 Key）。 */
    data class Verdict(
        val ok: Boolean,
        val data: MutableMap<String, Any?>?,
        val reason: String,
    )

    /**
     * 校验并收紧 AI 输出。
     *
     * @param raw           AI 返回的字段表（已解析；键为契约字段名）
     * @param evidenceCount 证据条数，**必须由调用方用 [AiEvidencePrompt.countEvidence]
     *                      从教材事实层统计**，不得采用 AI 在 `evidence_used` 里的自报条数
     */
    fun vet(raw: Map<String, Any?>, evidenceCount: Int): Verdict {
        // ① 必需字段齐备（ai_role_model_v1.json:58-59）
        val missing = AiContract.REQUIRED_FIELDS.filter { !raw.containsKey(it) || raw[it] == null }
        if (missing.isNotEmpty()) {
            return Verdict(false, null, "AI 输出缺少必需字段：${missing.joinToString("、")}")
        }

        // ② evidence_used 不得为空（V1.3:1316 没有证据不评价；ai_role_model:34 guard）
        if (!AiContract.isNonEmpty(raw["evidence_used"])) {
            return Verdict(false, null, "证据不足，暂时无法形成可靠评价。")
        }

        val out: MutableMap<String, Any?> = LinkedHashMap(raw)

        // ③ error_type 必须是封闭集合之一（ai_role_model:14-15 closed_set）
        val errorType = (out["error_type"] as? String).orEmpty()
        if (errorType !in AiContract.ERROR_TYPES) {
            return Verdict(
                false, null,
                "AI 输出的错误类型不在允许范围内：${errorType.ifEmpty { "（空）" }}"
            )
        }

        // ④ 超出教材范围 → 不作能力判断（ai_role_model:17 / :28 N6）
        if (out["in_textbook_scope"] == false) {
            out["likely_slip"] = "uncertain"
            out["need_intervention"] = "no"
            out["suggested_interventions"] = emptyList<Any>()
            out["confidence"] = AiContract.CONFIDENCE_CAP      // 范围外不表态
            out["need_now_blocked_reason"] = "out_of_textbook_scope"
            return Verdict(true, out, "")
        }

        // ⑤ confidence_rule：证据条数 <2 → 压低 confidence 且禁止 need_now（ai_role_model:60）
        val current = (out["confidence"] as? String).orEmpty()
        if (evidenceCount < 2) {
            out["confidence"] = capConfidence(current, AiContract.CONFIDENCE_CAP)
            if (out["need_intervention"] == "need_now") {
                out["need_intervention"] = "watch"
                out["need_now_blocked_reason"] = "insufficient_evidence"
            }
        } else if (current !in AiContract.CONFIDENCE_ORDER) {
            out["confidence"] = AiContract.CONFIDENCE_CAP
            out["confidence_coerced_reason"] = "invalid_value"
        }
        out["evidence_count_used"] = evidenceCount

        return Verdict(true, out, "")
    }

    /** 把 [current] 压到不高于 [cap] 的档位；非法取值一律取 [cap]。 */
    private fun capConfidence(current: String, cap: String): String {
        val i = AiContract.CONFIDENCE_ORDER.indexOf(current)
        val c = AiContract.CONFIDENCE_ORDER.indexOf(cap)
        if (i < 0) return cap
        return if (i > c) cap else current
    }
}

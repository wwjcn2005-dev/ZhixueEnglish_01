package com.zhixueenglish.app.dev.ai

/**
 * AI 输出契约的**纯数据定义**（无 Android / org.json 依赖，纯 Kotlin）。
 *
 * 为什么要独立成文件：Android 的 JVM 单元测试使用 `mockable android.jar`，
 * 其中 `org.json.*` 只是抛 `RuntimeException("Stub!")` 的桩实现。因此
 * **闸门与契约校验必须建立在纯 Kotlin 类型（Map / List）之上**，才能真正被单测覆盖。
 * `org.json` 只在运行时边界（[AiClient] 解析 HTTP 响应）使用。
 *
 * 契约来源：
 *   * `structured/learning/ai_role_model_v1.json:57` —— system 提示词原文；
 *   * `…:58-59` —— 10 个必需输出字段；
 *   * `…:14-15` —— 错误类型封闭集合（`closed_set: true`）；
 *   * `…:60` —— confidence 规则（由 [AiConfidenceGate] 程序强制）。
 */
object AiContract {

    /** 10 个必需输出字段（ai_role_model_v1.json:58-59，顺序保持原样）。 */
    val REQUIRED_FIELDS: List<String> = listOf(
        "correctness", "error_type", "reason", "in_textbook_scope", "textbook_ref",
        "likely_slip", "need_intervention", "suggested_interventions", "confidence", "evidence_used",
    )

    /**
     * 错误类型封闭集合（ai_role_model_v1.json:14-15，`closed_set: true`）。
     *
     * 原文六类：「形（拼写/词形）、义（理解偏差）、用（语境/搭配）、
     * 听（听辨/细节）、构（结构/语法）、表达（写作口语）」。
     * 规范用中文描述、未给出机器可读标识符，因此这里采用**与原文一一对应**的英文标识符；
     * 若后续规范给出正式标识符，只需替换本列表（提示词与闸门共用同一来源）。
     */
    val ERROR_TYPES: List<String> = listOf(
        "form",        // 形：拼写 / 词形
        "meaning",     // 义：理解偏差
        "usage",       // 用：语境 / 搭配
        "listening",   // 听：听辨 / 细节
        "structure",   // 构：结构 / 语法
        "expression",  // 表达：写作 / 口语
    )

    /** 置信度取值（低 → 高）。 */
    val CONFIDENCE_ORDER: List<String> = listOf("low", "medium", "high")

    /** 证据不足时允许的最大置信度（ai_role_model_v1.json:60）。 */
    const val CONFIDENCE_CAP = "medium"

    /**
     * 证据条数口径（闸门 `confidence_rule` 的输入，必须稳定且可复核）：
     *
     * * `evidencePackage == null` → **0**（无证据包：按证据不足处理，绝不伪造）；
     * * 否则 = 以下 **4 个文本类字段中"非空"的个数**（每个字段最多计 1）：
     *   `related_text`、`related_vocabulary`、`related_grammar`、`related_listening`；
     * * **明确排除 `related_image`**：实测 `textbook_evidence_map_v1.json` 中
     *   `related_image` 在 344/360 个包里非空；若计入，evidenceCount 永远 ≥1，
     *   闸门的 `<2` 分支几乎永不触发，`confidence_rule` 形同虚设。
     *   图片也不是可引用的文本证据（AI 无法据此判断语言事实）。
     * * 条数必须由**程序**从教材事实层统计，**不得采信 AI 在 `evidence_used` 里的自报**。
     *
     * 实测分布（360 个包，按本口径）：0 → 9、1 → 51、2 → 173、3 → 107、4 → 20。
     */
    val EVIDENCE_FIELDS: List<String> = listOf(
        "related_text", "related_vocabulary", "related_grammar", "related_listening",
    )

    fun countEvidence(evidencePackage: Map<String, Any?>?): Int {
        if (evidencePackage == null) return 0
        return EVIDENCE_FIELDS.count { isNonEmpty(evidencePackage[it]) }
    }

    // ---------------------------------------------------------------- J1：证据粒度

    /** 证据粒度：**活动级** —— 证据包含该活动的原题指令（`textbook_reference.instruction`）。 */
    const val GRANULARITY_ACTIVITY = "activity"

    /** 证据粒度：**Section 级降级** —— 同一 Section 的代表证据，**不含 per-activity 指令**，证据更弱。 */
    const val GRANULARITY_SECTION = "section"

    /**
     * 粒度感知的证据条数口径（决定闸门 `confidence_rule` 是否触发）。
     *
     * * [GRANULARITY_ACTIVITY] → [countEvidence] **实际计数**（实测通常 ≥2）；
     * * [GRANULARITY_SECTION]  → **强制 1**。理由：Section 级证据不含 per-activity 指令，
     *   判"答题要求"更弱；实测其字段数分布为 1 条(8 题) / 2 条(41) / 3 条(40) / 4 条(15)，
     *   若按实际计数会以"证据充足"的名义放行较弱判断，违反 `ai_role_model_v1.json:60`
     *   的 `confidence_rule` 精神。强制 1 使其自动落入保守分支
     *   （`confidence ≤ medium` 且 `need_intervention != need_now`）。
     * * 其他 / null（无证据） → **0**。
     *
     * 口径依据：`structured/learning/evidence_resolver_service.py` 的
     * `evidence_count_for_gate()`（Python 侧同口径，两处必须保持一致）。
     */
    fun countEvidenceForGate(evidencePackage: Map<String, Any?>?, granularity: String?): Int =
        when (granularity) {
            GRANULARITY_ACTIVITY -> countEvidence(evidencePackage)
            GRANULARITY_SECTION -> if (evidencePackage == null) 0 else 1
            else -> 0
        }

    /** 非空判定：null / 空串 / 空集合 / 空 Map 均视为"无证据"。 */
    fun isNonEmpty(value: Any?): Boolean = when (value) {
        null -> false
        is String -> value.isNotBlank()
        is Collection<*> -> value.isNotEmpty()
        is Map<*, *> -> value.isNotEmpty()
        is Array<*> -> value.isNotEmpty()
        else -> true
    }
}

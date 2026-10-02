package com.zhixueenglish.app.dev.ai

/**
 * AI 批改的提示词与证据组装（**纯 Kotlin，无 Android / org.json 依赖，可直接单元测试**）。
 *
 * 契约来源（不得自行发明）：
 *   * `structured/learning/ai_role_model_v1.json:57` —— system 提示词原文；
 *   * `…:58-59` —— 10 个必需输出字段；
 *   * `…:14-15` —— 错误类型封闭集合（`closed_set: true`）；
 *   * `…:60` —— confidence 规则（**由 [AiConfidenceGate] 程序强制**）；
 *   * `…:8` —— 输入必须含 TextbookEvidencePackage；
 *   * `docs/…最高指导原则与开发规范_V1.3.md:763` —— AI 解释必须锚定当前教材 / Unit / 题目上下文。
 *
 * ⚠️ 已记录的阻塞（独立待办，不属本类职责）：
 *   `structured/ai/textbook_evidence_map_v1.json` 的 `question_id`（337 个）
 *   与 `structured/questionbank/questionbank.db` 的 `question_id`（1831 个）**交集为 0**，
 *   两套数据没有主键关联。因此调用方**可能拿不到证据包**（`evidencePackage == null`）。
 *   本类对此明确降级：[AiContract.countEvidence] 返回 0，闸门随之按"证据不足"处理，
 *   绝不伪造证据、绝不用图片充数。
 */
object AiEvidencePrompt {

    /** 10 个必需输出字段（转发自 [AiContract]，保持单一来源）。 */
    val REQUIRED_FIELDS: List<String> get() = AiContract.REQUIRED_FIELDS

    /** 错误类型封闭集合（转发自 [AiContract]）。 */
    val ERROR_TYPES: List<String> get() = AiContract.ERROR_TYPES

    /**
     * 证据条数（转发自 [AiContract.countEvidence]）。
     *
     * 口径原文见 [AiContract.EVIDENCE_FIELDS] 的注释：`null` → 0；
     * 否则数 `related_text` / `related_vocabulary` / `related_grammar` / `related_listening`
     * 四个文本类字段的非空个数；**排除 `related_image`**。
     */
    fun countEvidence(evidencePackage: Map<String, Any?>?): Int =
        AiContract.countEvidence(evidencePackage)

    /**
     * **粒度感知**的证据条数（上报闸门用；转发自 [AiContract.countEvidenceForGate]）。
     *
     * `activity` → 实际计数；`section` → 强制 1；其他 / null → 0。
     */
    fun countEvidenceForGate(evidencePackage: Map<String, Any?>?, granularity: String?): Int =
        AiContract.countEvidenceForGate(evidencePackage, granularity)

    /** system 提示词（采用 ai_role_model_v1.json:57 原文，并内联 10 字段与封闭集合）。 */
    fun buildSystem(): String = buildString {
        append("你是教材范围内的批改助手。只依据给出的教材证据包判断；证据不足必须说明；")
        append("不得编造教材事实；不得替孩子决定下一步。\n\n")
        append("只输出一个 JSON 对象（不要 markdown 代码围栏、不要任何解释文字），")
        append("必须且只能包含以下字段：\n")
        append(REQUIRED_FIELDS.joinToString("、")).append("\n\n")
        append("字段约束：\n")
        append("1. error_type 必须取以下之一：").append(ERROR_TYPES.joinToString("、")).append("；\n")
        append("2. confidence 取 low / medium / high；\n")
        append("3. likely_slip 取 likely_slip / uncertain / repeat_error；\n")
        append("4. need_intervention 取 need_now / watch / no；取 no 时必须给出理由；\n")
        append("5. in_textbook_scope 为 false 时，必须把 textbook_ref 说明为超出教材范围，")
        append("且不得给出能力判断；\n")
        append("6. evidence_used 必须列出你实际依据的证据（教材原句 / 音频 / 范例），不得为空；\n")
        append("7. 证据不足时明确说明，不要给出确定结论；\n")
        append("8. 不要给出分数、排名、等级。")
    }

    /**
     * user 提示词：题目 + 孩子原始作答 +（可能为 null 的）教材证据包。
     *
     * @param question        题库题目对象（含 prompt / question_type / answer_kind 等）
     * @param picked          孩子原始作答（原样传入，不加工）
     * @param evidencePackage `textbook_evidence_map_v1.json` 的证据包；**允许为 null**
     *                        （见类注释的"证据包与题库零关联"阻塞）
     * @param granularity     证据粒度（`activity` / `section` / null）。**允许为 null**
     *                        （向后兼容：旧调用方不传，则提示词只声明"有无证据"）。
     *                        粒度必须向模型**如实声明**，因为它决定证据能否支撑
     *                        "答题要求"的判断（`section` 级不含 per-activity 指令）。
     */
    fun buildUser(
        question: Map<String, Any?>,
        picked: String,
        evidencePackage: Map<String, Any?>?,
        granularity: String? = null,
    ): String = buildString {
        append("【题目】\n")
        val prompt = asMap(question["prompt"])
        text(prompt?.get("instruction"))?.let { append("指令：").append(it).append('\n') }
        text(prompt?.get("text"))?.let { append("题干：").append(it).append('\n') }
        text(question["question_type"])?.let { append("题型：").append(it).append('\n') }
        text(question["answer_kind"])?.let { append("判分方式：").append(it).append('\n') }

        append("\n【孩子的原始作答】\n")
        append(if (picked.isEmpty()) "（未作答 / 空）" else picked)
        append('\n')

        append("\n【教材证据包】\n")
        // J1：先如实声明证据粒度（决定模型对"答题要求"的判断力度）
        when (granularity) {
            AiContract.GRANULARITY_ACTIVITY ->
                append("证据粒度：活动级（含该活动的原题指令）。\n")
            AiContract.GRANULARITY_SECTION -> {
                append("证据粒度：Section 级（同一 Section 的代表证据；")
                append("**不含该活动的原题指令**）。\n")
                append("因此判断“答题要求”时必须更保守，并在 reason 中说明这一局限；")
                append("confidence 不得高于 medium，need_intervention 不得为 need_now。\n")
            }
            else -> append("证据粒度：无（未取得该题的任何教材证据）。\n")
        }
        if (evidencePackage == null) {
            append("无（本次未取得该题的教材证据包）。\n")
            append("因此你必须按“证据不足”处理：confidence 不得高于 medium，")
            append("need_intervention 不得为 need_now，并在 reason 中说明证据不足。\n")
        } else {
            append("证据条数（程序统计，仅文本类）：").append(countEvidence(evidencePackage)).append('\n')
            asMap(evidencePackage["scope"])?.let { s ->
                append("范围：unit=").append(s["unit"].orEmptyText())
                    .append(" section=").append(s["section"].orEmptyText())
                    .append(" activity_no=").append(s["activity_no"].orEmptyText())
                    .append(" question_no=").append(s["question_no"].orEmptyText()).append('\n')
            }
            asMap(evidencePackage["textbook_reference"])?.let { r ->
                append("教材页码：pdf=").append(r["pdf_page"].orEmptyText())
                    .append(" textbook=").append(r["textbook_page"].orEmptyText()).append('\n')
                text(r["instruction"])?.let { append("原题指令：").append(it).append('\n') }
            }
            asMap(evidencePackage["original_question"])?.let { o ->
                text(o["text"])?.let { append("原题文字：").append(it).append('\n') }
            }
            appendList(evidencePackage, "related_text", "相关教材正文")
            appendList(evidencePackage, "related_vocabulary", "相关词汇")
            appendList(evidencePackage, "related_grammar", "相关语法")
            appendList(evidencePackage, "related_listening", "相关听力")
            val rules = asList(evidencePackage["ai_rules"])
            if (rules.isNotEmpty()) {
                append("批改规则（必须遵守）：\n")
                for (r in rules) append("  - ").append(r.toDisplay()).append('\n')
            }
            text(evidencePackage["answer_note"])?.let { append("答案说明：").append(it).append('\n') }
        }
    }

    // ---- 内部工具（纯 Kotlin，无 org.json） ----

    @Suppress("UNCHECKED_CAST")
    private fun asMap(value: Any?): Map<String, Any?>? = value as? Map<String, Any?>

    @Suppress("UNCHECKED_CAST")
    private fun asList(value: Any?): List<Any?> = value as? List<Any?> ?: emptyList()

    private fun text(value: Any?): String? {
        val s = value as? String ?: return null
        return s.takeIf { it.isNotBlank() }
    }

    private fun Any?.orEmptyText(): String = this?.toString().orEmpty()

    private fun Any?.toDisplay(): String = when (this) {
        null -> ""
        is Map<*, *> -> entries.joinToString(", ") { "${it.key}=${it.value}" }
        else -> toString()
    }

    private fun StringBuilder.appendList(source: Map<String, Any?>, field: String, label: String) {
        val items = asList(source[field])
        if (items.isEmpty()) return
        append(label).append("（").append(items.size).append(" 条）：\n")
        for (item in items) {
            val s = item.toDisplay()
            if (s.isNotBlank()) append("  - ").append(s).append('\n')
        }
    }
}

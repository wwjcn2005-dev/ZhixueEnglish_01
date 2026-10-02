package com.zhixueenglish.app.dev.ai

/**
 * AI 接口的纯字符串处理（无 Android 依赖，可直接单元测试）。
 *
 * 口径：兼容 OpenAI Chat Completions 结构 —— 用户只填 Base URL，
 * 请求地址 = Base URL + `/chat/completions`。
 */
object AiEndpoint {

    /** 用户填写的 Base URL → 实际请求地址；空串表示未配置。 */
    fun chatCompletionsUrl(baseUrl: String): String {
        val raw = baseUrl.trim()
        if (raw.isEmpty()) return ""
        val withScheme = if (raw.startsWith("http://", true) || raw.startsWith("https://", true)) {
            raw
        } else {
            "https://$raw"
        }
        val noTail = withScheme.trimEnd('/')
        return if (noTail.endsWith("/chat/completions")) noTail else "$noTail/chat/completions"
    }

    /** Key 掩码：只用于界面展示，永不返回完整 Key。 */
    fun maskedKey(apiKey: String): String {
        val key = apiKey.trim()
        if (key.isEmpty()) return ""
        if (key.length <= 8) return "••••"
        return "••••" + key.takeLast(4)
    }

    /**
     * 从任意文本里抹掉 Key 原文（错误信息、日志前的最后一道保险）。
     * 空 Key 或过短的 Key 一律返回掩码，避免"看起来像 Key"的片段泄漏。
     */
    fun redact(text: String, apiKey: String): String {
        val body = text.trim()
        val key = apiKey.trim()
        if (key.length < 8) return body
        return body.replace(key, maskedKey(key))
    }

    /** Base URL / Model 的轻量校验：只判断"看起来能不能用"，不做联网。 */
    fun isPlausibleBaseUrl(baseUrl: String): Boolean {
        val url = chatCompletionsUrl(baseUrl)
        return url.startsWith("http://") || url.startsWith("https://")
    }

    /**
     * 剥离模型常见的 markdown 代码围栏，返回内部 JSON 文本。
     *
     * 背景：即使 prompt 明确要求"只输出 JSON"，DeepSeek 等模型仍可能返回
     * ```json … ``` 或 ``` … ```。这是模型的表达习惯，不是错误，应当容错。
     *
     * 规则（只做必要的剥离，不过度处理）：
     *   * 整段被一对围栏包住 → 返回围栏内部内容；
     *   * 没有围栏（本身就是 JSON）→ **原样返回，不误伤**；
     *   * 只有开头或只有结尾的半截围栏 → 视为不是围栏，原样返回；
     *     此时 JSON 解析会失败 → 由调用方按失败处理（不在此处掩盖问题）。
     *
     * 注意：本函数**不校验**结果是否为合法 JSON。剥离后仍非法时，
     * 应由调用方的 JSON 解析抛错并转为失败状态。
     */
    fun stripMarkdownFence(text: String): String {
        val trimmed = text.trim()
        // 围栏：可选 ```json 语言标记 + 可选换行 + 内容 + 可选换行 + ```
        val fence = Regex(
            "^```(?:[A-Za-z0-9_+-]*)[ \\t]*\\r?\\n?(.*?)\\r?\\n?```$",
            RegexOption.DOT_MATCHES_ALL
        )
        val match = fence.find(trimmed) ?: return trimmed
        return match.groupValues[1].trim()
    }
}

package com.zhixueenglish.app.dev.ai

import android.content.Context

/** AI 配置（不含 API Key 明文；Key 只在 [SecureKeyStore] 里以密文保存）。 */
data class AiConfig(
    val enabled: Boolean,
    val baseUrl: String,
    val model: String,
    val hasApiKey: Boolean,
) {
    val endpointReady: Boolean
        get() = baseUrl.isNotBlank() && model.isNotBlank() && hasApiKey
}

/** 非敏感配置：AI 开关 / Base URL / Model（SharedPreferences，明文即可）。 */
object AiConfigStore {

    private const val PREFS = "zhixue_ai_config"
    private const val FIELD_ENABLED = "enabled"
    private const val FIELD_BASE_URL = "base_url"
    private const val FIELD_MODEL = "model"

    fun load(context: Context): AiConfig {
        val prefs = prefs(context)
        return AiConfig(
            enabled = prefs.getBoolean(FIELD_ENABLED, false),
            baseUrl = prefs.getString(FIELD_BASE_URL, "").orEmpty(),
            model = prefs.getString(FIELD_MODEL, "").orEmpty(),
            hasApiKey = SecureKeyStore.hasKey(context),
        )
    }

    /** 保存非敏感项；API Key 走 [SecureKeyStore]（传 null 表示不改 Key）。 */
    fun save(context: Context, enabled: Boolean, baseUrl: String, model: String, apiKey: String?) {
        prefs(context).edit()
            .putBoolean(FIELD_ENABLED, enabled)
            .putString(FIELD_BASE_URL, baseUrl.trim())
            .putString(FIELD_MODEL, model.trim())
            .apply()
        if (apiKey != null) SecureKeyStore.save(context, apiKey)
    }

    /** 关闭 AI（不改动其它配置项）。 */
    fun setEnabled(context: Context, enabled: Boolean) {
        prefs(context).edit().putBoolean(FIELD_ENABLED, enabled).apply()
    }

    /** 删除 API Key，并顺手关闭 AI（删除后不应再有 AI 请求）。 */
    fun deleteApiKey(context: Context) {
        SecureKeyStore.clear(context)
        setEnabled(context, false)
    }

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}

/**
 * AI 使用量：只记录**真实发生**的调用次数，以及接口能可靠返回的 token 用量。
 *
 * 不记录也无法获得价格时**不伪造费用**——只显示次数与可获得的 usage。
 */
object AiUsageStore {

    private const val PREFS = "zhixue_ai_usage"
    private const val FIELD_CALLS = "calls"
    private const val FIELD_PROMPT = "prompt_tokens"
    private const val FIELD_COMPLETION = "completion_tokens"

    fun recordCall(context: Context, promptTokens: Int?, completionTokens: Int?) {
        val prefs = prefs(context)
        val editor = prefs.edit().putInt(FIELD_CALLS, prefs.getInt(FIELD_CALLS, 0) + 1)
        if (promptTokens != null) {
            editor.putInt(FIELD_PROMPT, prefs.getInt(FIELD_PROMPT, 0) + promptTokens)
        }
        if (completionTokens != null) {
            editor.putInt(FIELD_COMPLETION, prefs.getInt(FIELD_COMPLETION, 0) + completionTokens)
        }
        editor.apply()
    }

    /** 返回 (调用次数, 输入 token 合计, 输出 token 合计)。 */
    fun summary(context: Context): Triple<Int, Int, Int> {
        val prefs = prefs(context)
        return Triple(
            prefs.getInt(FIELD_CALLS, 0),
            prefs.getInt(FIELD_PROMPT, 0),
            prefs.getInt(FIELD_COMPLETION, 0),
        )
    }

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}

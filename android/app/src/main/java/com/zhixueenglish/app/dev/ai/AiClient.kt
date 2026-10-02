package com.zhixueenglish.app.dev.ai

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL

/** AI 请求结果（失败信息里永不出现完整 Key）。 */
sealed class AiResult {
    data class Ok(val text: String, val promptTokens: Int?, val completionTokens: Int?) : AiResult()

    /**
     * 结构化结果：模型按契约返回了 JSON 对象（已过 [AiConfidenceGate] 闸门时才由调用方采用）。
     *
     * [data] 是**纯 Kotlin 的字段表**（不是 `org.json.JSONObject`）——
     * 这样闸门与契约校验才能在 JVM 单测里被真实覆盖
     * （Android 单测的 `org.json` 是抛 `RuntimeException("Stub!")` 的桩）。
     *
     * 与 [Ok] 并存：`chat()` 走自由文本，`chatJson()` 走结构化。
     */
    data class OkJson(
        val data: Map<String, Any?>,
        val promptTokens: Int?,
        val completionTokens: Int?,
    ) : AiResult()

    data class Failure(val message: String) : AiResult()

    /** AI 关闭：**不发起任何请求**。 */
    object Disabled : AiResult()

    /** 未配置（缺 Base URL / Model / Key）：不发起请求。 */
    object NotConfigured : AiResult()
}

/**
 * 兼容 OpenAI Chat Completions 的最小请求层（HttpURLConnection，不引入新依赖）。
 *
 * 口径（与项目既有 Python 侧一致）：
 *   POST {BaseURL}/chat/completions
 *   { "model": ..., "messages": [{"role":"system",...},{"role":"user",...}] }
 *   Authorization: Bearer <API Key>
 *
 * 安全：
 *   * Key 只从 [SecureKeyStore] 读取，绝不写日志、绝不出现在异常信息里；
 *   * 错误信息统一经过 [AiEndpoint.redact] 处理。
 */
object AiClient {

    private const val CONNECT_TIMEOUT_MS = 15_000
    private const val READ_TIMEOUT_MS = 60_000

    /** 连接测试：只做一次最小请求，不写学习记录、不改学习状态。 */
    fun testConnection(context: Context, timeoutMs: Int = 20_000): AiResult {
        val config = AiConfigStore.load(context)
        if (!config.enabled) return AiResult.Disabled
        if (!config.endpointReady) return AiResult.NotConfigured
        val key = SecureKeyStore.load(context) ?: return AiResult.NotConfigured
        return call(
            baseUrl = config.baseUrl,
            model = config.model,
            apiKey = key,
            system = "你是连接测试助手。",
            user = "请只回复：ok",
            maxTokens = 8,
            timeoutMs = timeoutMs,
        )
    }

    /**
     * 业务请求入口。调用方应先复用已有缓存；只有确实需要 AI 时才调用这里。
     * AI 关闭 / 未配置时不发请求，返回 [AiResult.Disabled] / [AiResult.NotConfigured]。
     */
    fun chat(
        context: Context,
        system: String,
        user: String,
        maxTokens: Int = 512,
        timeoutMs: Int = READ_TIMEOUT_MS,
    ): AiResult {
        val config = AiConfigStore.load(context)
        if (!config.enabled) return AiResult.Disabled
        if (!config.endpointReady) return AiResult.NotConfigured
        val key = SecureKeyStore.load(context) ?: return AiResult.NotConfigured
        val result = call(config.baseUrl, config.model, key, system, user, maxTokens, timeoutMs)
        if (result is AiResult.Ok) {
            AiUsageStore.recordCall(context, result.promptTokens, result.completionTokens)
        }
        return result
    }

    /**
     * 结构化批改入口（批次 3）：要求模型返回契约规定的 JSON，并用 [AiConfidenceGate] 过闸。
     *
     * 与 [chat] 的区别：
     *   * 返回 [AiResult.OkJson]（已解析的 JSON 对象）而不是自由文本；
     *   * 会在返回前剥离 markdown 代码围栏（模型常见表达习惯）；
     *   * **不做**闸门判定——闸门需要 `evidenceCount`，由调用方（批次 4 的桥）用
     *     [AiEvidencePrompt.countEvidence] 统计后自行调用 [AiConfidenceGate.vet]，
     *     以保证"条数来自教材事实层"而非 AI 自报。
     *
     * @param requiredFields 必需字段名（通常传 [AiEvidencePrompt.REQUIRED_FIELDS]）
     */
    fun chatJson(
        context: Context,
        system: String,
        user: String,
        requiredFields: List<String>,
        maxTokens: Int = 512,
        timeoutMs: Int = READ_TIMEOUT_MS,
    ): AiResult {
        val config = AiConfigStore.load(context)
        if (!config.enabled) return AiResult.Disabled
        if (!config.endpointReady) return AiResult.NotConfigured
        val key = SecureKeyStore.load(context) ?: return AiResult.NotConfigured

        val raw = callRaw(config.baseUrl, config.model, key, system, user, maxTokens, timeoutMs)
        if (raw.error != null || raw.code !in 200..299) return failureOf(raw, key)
        val content = extractContent(raw.body)
            ?: return AiResult.Failure("响应不是预期的 JSON：缺少 choices[0].message.content")
        val jsonText = AiEndpoint.stripMarkdownFence(content)
        val obj = try {
            JSONObject(jsonText)
        } catch (e: Exception) {
            return AiResult.Failure(
                AiEndpoint.redact(
                    "响应不是合法的 JSON 对象：${e.message.orEmpty().take(120)}", key
                )
            )
        }
        val missing = requiredFields.filter { !obj.has(it) || obj.isNull(it) }
        if (missing.isNotEmpty()) {
            return AiResult.Failure("AI 输出缺少必需字段：${missing.joinToString("、")}")
        }
        val usage = usageOf(raw.body)
        AiUsageStore.recordCall(context, usage.first, usage.second)
        return AiResult.OkJson(jsonToMap(obj), usage.first, usage.second)
    }

    /**
     * `JSONObject` → 纯 Kotlin `Map`（递归转换 `JSONObject` / `JSONArray`）。
     *
     * 刻意不使用 `JSONObject.toMap()`：该 API 的可用性随 Android API 级别变化，
     * 自己递归转换更稳，也不引入任何依赖。
     */
    private fun jsonToMap(obj: JSONObject): Map<String, Any?> {
        val out = LinkedHashMap<String, Any?>()
        val keys = obj.keys()
        while (keys.hasNext()) {
            val k = keys.next()
            out[k] = jsonValueToPlain(obj.opt(k))
        }
        return out
    }

    private fun jsonArrayToList(arr: JSONArray): List<Any?> =
        (0 until arr.length()).map { jsonValueToPlain(arr.opt(it)) }

    private fun jsonValueToPlain(value: Any?): Any? = when (value) {
        null -> null
        is JSONObject -> jsonToMap(value)
        is JSONArray -> jsonArrayToList(value)
        else -> value
    }

    /**
     * 一次请求的原始结果。
     *
     * [error] 非空表示**网络层失败**（异常），此时 [code] 无意义；
     * [error] 为空表示拿到了 HTTP 响应（[code] 为真实状态码）。
     * 这样区分是为了保证错误文案与重构前**逐字一致**：
     * 异常走「异常类名：消息」，非 2xx 走「HTTP <code>：<body>」。
     */
    internal data class RawResponse(val code: Int, val body: String, val error: String? = null)

    /**
     * 共享的网络层：发一次 Chat Completions 请求，返回 HTTP 状态与响应体原文。
     *
     * 行为与重构前的 `call()` 完全一致（超时、请求头、payload 结构均未改动），
     * 仅把"发请求"与"解释响应"拆开，供 [chat] 与 [chatJson] 共用。
     */
    private fun callRaw(
        baseUrl: String,
        model: String,
        apiKey: String,
        system: String,
        user: String,
        maxTokens: Int,
        timeoutMs: Int,
    ): RawResponse {
        val endpoint = AiEndpoint.chatCompletionsUrl(baseUrl)
        if (endpoint.isEmpty()) return RawResponse(-1, "")
        val payload = JSONObject()
            .put("model", model)
            .put("max_tokens", maxTokens)
            .put(
                "messages",
                JSONArray().apply {
                    put(JSONObject().put("role", "system").put("content", system))
                    put(JSONObject().put("role", "user").put("content", user))
                }
            )
        var connection: HttpURLConnection? = null
        return try {
            connection = (URL(endpoint).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = CONNECT_TIMEOUT_MS
                readTimeout = timeoutMs
                doOutput = true
                setRequestProperty("Content-Type", "application/json")
                setRequestProperty("Authorization", "Bearer $apiKey")
            }
            connection.outputStream.use { it.write(payload.toString().toByteArray(Charsets.UTF_8)) }
            val code = connection.responseCode
            val body = (if (code in 200..299) connection.inputStream else connection.errorStream)
                ?.let { stream ->
                    BufferedReader(InputStreamReader(stream, Charsets.UTF_8)).use { it.readText() }
                }.orEmpty()
            RawResponse(code, body)
        } catch (e: Exception) {
            RawResponse(-1, "", e.javaClass.simpleName + "：" + e.message.orEmpty().take(200))
        } finally {
            connection?.disconnect()
        }
    }

    /**
     * 把 [RawResponse] 的失败转成 [AiResult.Failure]，文案与重构前逐字一致。
     *
     * 可见性为 `internal` 是为了让单测能直接覆盖"失败文案"（这是 `call()` 重构的
     * 唯一行为风险点）：网络异常走「异常类名：消息」，非 2xx 走「HTTP <code>：<body>」，
     * 两者都经 [AiEndpoint.redact]。
     */
    internal fun failureOf(raw: RawResponse, apiKey: String): AiResult.Failure =
        if (raw.error != null) {
            AiResult.Failure(AiEndpoint.redact(raw.error, apiKey))
        } else {
            AiResult.Failure(
                AiEndpoint.redact(
                    "HTTP ${raw.code}：${raw.body.take(300).ifBlank { "无响应内容" }}", apiKey
                )
            )
        }

    /** 解释响应：自由文本（重构前 `call()` 的逻辑，行为保持不变）。 */
    private fun call(
        baseUrl: String,
        model: String,
        apiKey: String,
        system: String,
        user: String,
        maxTokens: Int,
        timeoutMs: Int,
    ): AiResult {
        val raw = callRaw(baseUrl, model, apiKey, system, user, maxTokens, timeoutMs)
        if (raw.error != null || raw.code !in 200..299) return failureOf(raw, apiKey)
        return parseSuccess(raw.body, apiKey)
    }

    /** 取出 `choices[0].message.content`；结构不符返回 null。 */
    private fun extractContent(body: String): String? = try {
        JSONObject(body).optJSONArray("choices")
            ?.optJSONObject(0)
            ?.optJSONObject("message")
            ?.optString("content")
    } catch (_: Exception) {
        null
    }

    /** 取出 `usage` 的 (prompt_tokens, completion_tokens)。 */
    private fun usageOf(body: String): Pair<Int?, Int?> = try {
        val usage = JSONObject(body).optJSONObject("usage")
        Pair(
            usage?.optInt("prompt_tokens")?.takeIf { usage.has("prompt_tokens") },
            usage?.optInt("completion_tokens")?.takeIf { usage.has("completion_tokens") },
        )
    } catch (_: Exception) {
        Pair(null, null)
    }

    private fun parseSuccess(body: String, apiKey: String): AiResult = try {
        val json = JSONObject(body)
        val content = json.optJSONArray("choices")
            ?.optJSONObject(0)
            ?.optJSONObject("message")
            ?.optString("content")
            .orEmpty()
        val usage = json.optJSONObject("usage")
        AiResult.Ok(
            text = content,
            promptTokens = usage?.optInt("prompt_tokens")?.takeIf { usage.has("prompt_tokens") },
            completionTokens = usage?.optInt("completion_tokens")
                ?.takeIf { usage.has("completion_tokens") },
        )
    } catch (e: Exception) {
        AiResult.Failure(AiEndpoint.redact("响应不是预期的 JSON：${e.message.orEmpty().take(120)}", apiKey))
    }
}

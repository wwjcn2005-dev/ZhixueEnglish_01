package com.zhixueenglish.app.dev.ai

import android.content.Context
import android.util.Log
import android.webkit.JavascriptInterface
import android.webkit.WebView
import org.json.JSONArray
import org.json.JSONObject

/**
 * P6-A / A-1：**AI 批改桥**（页面 → 原生 → AI → 原生 → 页面）。
 *
 * 架构（为什么必须在这一层）：AI 的 Key 只存在于 Android 侧（[SecureKeyStore]，
 * EncryptedSharedPreferences + Keystore）；Python 后端与页面**都拿不到 Key**，
 * 因此**原生 Kotlin 是唯一能调 AI 的层**。页面只把「证据 + 题目 + 孩子原答」交给本桥。
 *
 * 硬性边界（与 Android基线 §8.1 / §9 一致）：
 *  * **Key 永不进入 HTML / JS / WebView**；页面无从取得；
 *  * 只读：**不写任何数据库**（`learning.db` / `questionbank.db` 均不写）；
 *  * **AI 失败绝不阻断确定性学习功能** —— 一切异常都被兜成可解析的失败结果，
 *    页面显示"AI 暂不可用 / 批改失败"，原「需要 AI 批改，暂时先不打分。」保持不变。
 *
 * 调用契约（与 `web/ui.py` 的 `P5_AI_BRIDGE_JS` 成对，两处必须同步修改）：
 *  * JS → 原生：`window.ZxAi.grade(payloadJsonString)`
 *  * 原生 → JS：`window.__zxAiOnResult(resultJsonString)`
 *
 * `payload` 结构（由 Python 侧下发的 `<script id="zx-evidence">` 组装）：
 * ```json
 * {"question": {…}, "picked": "…", "evidence": {…}|null,
 *  "granularity": "activity"|"section"|null, "question_id": "Q:…", "section": "…"}
 * ```
 * `result` 结构（本桥产出，页面按 `status` 分派）：
 * ```json
 * {"status":"ok","data":{…},"evidenceCount":1}
 * {"status":"ai_disabled"} / {"status":"not_configured"}
 * {"status":"rejected","reason":"…"}
 * {"status":"failed","reason":"…"}
 * ```
 *
 * **注意**：`grade()` 运行在 WebView 的 JavaBridge 线程（**非**主线程），
 * 因此其中可做阻塞网络调用；`evaluateJavascript` 自带切回 UI 线程的语义。
 */
class ZxAiBridge(
    private val context: Context,
    private val webView: WebView,
) {

    @JavascriptInterface
    fun grade(payload: String) {
        val result = try {
            runGrade(payload)
        } catch (t: Throwable) {
            // 兜底：任何异常都变成可解析的失败结果，绝不抛到 WebView
            Log.w(TAG, "批改桥异常（已兜底）：" + t.javaClass.simpleName + "：" + (t.message ?: ""))
            failed("批改桥内部错误：" + t.javaClass.simpleName)
        }
        push(result)
    }

    /** 页面可用于探测桥是否可用（`typeof window.ZxAi.grade === 'function'`）。 */
    @JavascriptInterface
    fun version(): String = BRIDGE_VERSION

    /**
     * 「AI 老师」答错讲解（V1.3 第二十九章 §18 / 流程规范 §26）。
     *
     * 与 [grade] 独立：本方法产出**三句话**（错在哪 / 该用什么 / 一个例句），
     * 回调 `window.__zxTeachOnResult(…)`；[grade] 回调 `window.__zxAiOnResult(…)`。
     *
     * 例句来源三层优先级（**先命中先停**，由提示词约束、闸门兜底）：
     *  ① 教材句池（`evidence_pool.related_text`）里有合适的 ⇒ 直接用课文原句；
     *  ② 取不到 ⇒ 依教材素材（本册 + 已学过的前置）生成合乎逻辑的例句；
     *  ③ 都不行 ⇒ **只回前两句**（宁缺毋滥，绝不编造教材事实）。
     *
     * 硬性边界：**Key 不进页面**；**不写任何数据库**；**AI 失败不阻断确定性学习功能**
     * （一切异常兜成可解析的失败结果，页面保持"这次填的是 X，正确答案是 Y"）。
     */
    @JavascriptInterface
    fun teach(payload: String) {
        val result = try {
            runTeach(payload)
        } catch (t: Throwable) {
            Log.w(TAG, "讲解桥异常（已兜底）：" + t.javaClass.simpleName + "：" + (t.message ?: ""))
            failed("讲解桥内部错误：" + t.javaClass.simpleName)
        }
        pushTeach(result)
    }

    /**
     * **AI 学情分析桥**（单元中心二期·C-2）。
     *
     * 与 [grade] / [teach] 的区别：
     *  * [grade] = 判**一道** `ai_eval` 题；[teach] = 讲**一道**错题（三句话）；
     *  * [analyze] = **跨多次聚合**的学情分析（整单元统计 → 一段点评 + 可点的练习建议）。
     *
     * 入参：`<script id="zx-analyze-data">` 里的输入 JSON（unit_name / knowledge_points /
     * practice_entries …，**全中文名、不含内部题型 key**）。
     * 返回：经 `window.__zxAnalyzeOnResult` 回调输出 JSON。
     */
    @JavascriptInterface
    fun analyze(payload: String) {
        val result = try {
            runAnalyze(payload)
        } catch (t: Throwable) {
            Log.w(TAG, "学情分析桥异常（已兜底）：" + t.javaClass.simpleName + "：" + (t.message ?: ""))
            failed("学情分析桥内部错误：" + t.javaClass.simpleName)
        }
        pushAnalyze(result)
    }

    // ------------------------------------------------------------------ 内部

    private fun runGrade(payload: String): JSONObject {
        val obj = try {
            JSONObject(payload)
        } catch (e: Exception) {
            return failed("payload 不是合法 JSON")
        }
        val question = obj.optJSONObject("question")?.let { jsonToMap(it) } ?: emptyMap()
        val picked = obj.optString("picked", "")
        val granularity = obj.optString("granularity").takeIf { it.isNotEmpty() }
        val evidence: Map<String, Any?>? =
            obj.optJSONObject("evidence")?.let { jsonToMap(it) }

        // ① 前置：AI 未配置 / 未启用 —— 如实回报，不伪造批改
        val config = AiConfigStore.load(context)
        if (!config.enabled) return JSONObject().put("status", "ai_disabled")
        if (!config.endpointReady) return JSONObject().put("status", "not_configured")

        // ② 闸门输入：证据条数**由程序从教材证据包统计**（不采信 AI 自报）
        val evidenceCount = AiEvidencePrompt.countEvidenceForGate(evidence, granularity)
        if (evidenceCount <= 0 && evidence == null) {
            return rejected("证据不足，暂时无法形成可靠评价。").put("evidenceCount", 0)
        }

        // ③ 组装提示词（system 已内含"不得编造教材事实"等硬约束）
        val section = obj.optString("section")
        val user = buildString {
            append(AiEvidencePrompt.buildUser(question, picked, evidence, granularity))
            if (section.isNotEmpty()) append("\n【当前学习上下文】Section：").append(section).append('\n')
        }

        // ④ 调 AI（唯一能调 AI 的层）；失败不抛
        val r = AiClient.chatJson(
            context = context,
            system = AiEvidencePrompt.buildSystem(),
            user = user,
            requiredFields = AiContract.REQUIRED_FIELDS,
            maxTokens = AI_MAX_TOKENS,
        )
        val data = when (r) {
            is AiResult.OkJson -> r.data
            is AiResult.Disabled -> return JSONObject().put("status", "ai_disabled")
            is AiResult.NotConfigured -> return JSONObject().put("status", "not_configured")
            is AiResult.Failure -> return failed(r.message)
            is AiResult.Ok -> return failed("AI 返回了非结构化文本（预期 JSON）")
        }

        // ⑤ 过确定性闸门（越界拒绝 / 证据不足压低 confidence 并禁 need_now）
        val verdict = AiConfidenceGate.vet(data, evidenceCount)
        if (!verdict.ok || verdict.data == null) {
            return rejected(verdict.reason.ifEmpty { "闸门未通过" }).put("evidenceCount", evidenceCount)
        }
        return JSONObject()
            .put("status", "ok")
            .put("data", mapToJson(verdict.data))
            .put("evidenceCount", evidenceCount)
            .put("granularity", granularity ?: JSONObject.NULL)
    }

    private fun rejected(reason: String): JSONObject =
        JSONObject().put("status", "rejected").put("reason", reason)

    // ------------------------------------------------------------ AI 老师（讲解）

    /** 「AI 老师」三句话提示词（system）：**按题型族分派**，只输出 JSON。 */
    private fun teachSystem(questionType: String): String = buildString {
        append("你是教材范围内的讲解老师，面向初一学生讲错题。只依据给出的教材内容与已学范围判断；")
        append("不得编造教材事实，不得使用范围外的词或句子。\n\n")
        append(familyInstruction(questionFamily(questionType)))
        append('\n')
        append("只输出一个 JSON 对象（不要 markdown 代码围栏、不要任何解释文字），必须且只能包含以下字段：\n")
        append(TEACH_FIELDS.joinToString("、")).append("\n\n")
        append("字段约束：\n")
        append("1. wrong 一句话，说清\"错在哪\"，用孩子能懂的词；\n")
        append("2. should 一句话，说清\"该用什么\"，不展开规则；\n")
        append("3. example 一个例句：**先用教材句池里的原句**（合适就直接用，并在 example_source 填 \"textbook\"）；")
        append("句池里没有合适的，才依据教材素材自己写一句合乎逻辑的例句（example_source 填 \"generated\"）；")
        append("实在不合适就把 example 设为空字符串、example_source 设为 \"none\"。\n")
        append("4. 每句不超过一行，不要出现第四句。\n")
    }

    /** 组装 user：题目 / 孩子答案 / 正确答案 / 课时 / **教材句池**（三层优先级的输入）。 */
    private fun teachUser(obj: JSONObject): String = buildString {
        append("【题目】\n")
        val inst = obj.optString("instruction")
        if (inst.isNotEmpty()) append("指令：").append(inst).append('\n')
        val text = obj.optString("text")
        if (text.isNotEmpty()) append("题干：").append(text).append('\n')
        val opts = obj.optJSONArray("options")
        if (opts != null && opts.length() > 0) {
            append("选项：")
            for (i in 0 until opts.length()) {
                val o = opts.optJSONObject(i)
                if (o != null) append(o.optString("key")).append(". ").append(o.optString("text")).append("  ")
            }
            append('\n')
        }
        append("孩子的答案：").append(obj.optString("picked")).append('\n')
        append("正确答案：").append(obj.optString("answer")).append("\n\n")
        append("【当前学习上下文】\n")
        // V1.3 第二十九章 §19 第 3 条：范围锚点按题型粒度分派 ——
        // Section 级题型锚点是 section_key；Unit 级题型（vocab_word_form 等）用 unit_code 兜底。
        val anchorKind = scopeAnchorKind(obj)
        if (anchorKind == "unit") {
            append("单元：").append(obj.optString("unit_code")).append("（本题为 Unit 级辅助题，无课时归属）\n")
        } else {
            append("课时：").append(obj.optString("unit_code")).append(" / ").append(obj.optString("section_key")).append('\n')
        }
        append("检索与守界范围：**本题所属范围 + 孩子已学过的内容**（不是用户当前正在浏览的课时）。\n\n")
        append("【教材句池】（优先使用；没有合适的才自己写）\n")
        val pool = obj.optJSONObject("evidence_pool")
        val rt = pool?.optJSONArray("related_text")
        if (rt == null || rt.length() == 0) {
            append("（本课无教材句池 —— 请依据教材素材自行写一句合乎逻辑的例句，或按要求置空。）\n")
        } else {
            for (i in 0 until rt.length()) {
                val it = rt.optJSONObject(i) ?: continue
                append("- ").append(it.optString("sample")).append('\n')
            }
        }
    }

    /**
     * 范围锚点类型：`"section"`（Section 级题型）或 `"unit"`（Unit 级辅助题，用 unit_code 兜底）。
     *
     * 优先采信 payload 里由 Python 侧算好的 `scope_anchor_kind`（V1.3 §19 第 3 条）；
     * 缺失时按 `section_key` 是否为空自行判定 —— 两条路径结论一致，互为兜底。
     */
    private fun scopeAnchorKind(obj: JSONObject): String {
        val k = obj.optString("scope_anchor_kind")
        if (k == "section" || k == "unit") return k
        return if (obj.optString("section_key").isNotEmpty()) "section" else "unit"
    }

    /** 范围锚点取值：Section 级 = `section_key`；Unit 级 = `unit_code`。两者皆空返回 ""。 */
    private fun scopeAnchorValue(obj: JSONObject): String {
        val v = obj.optString("scope_anchor_value")
        if (v.isNotEmpty()) return v
        val sk = obj.optString("section_key")
        return if (sk.isNotEmpty()) sk else obj.optString("unit_code")
    }

    /** 学情分析 system 提示词（单元中心二期·D-2：让 AI **说具体**）。 */
    private fun analyzeSystem(): String = buildString {
        append("你是初一英语学习辅导员。你只依据给出的学习数据说话，不编造。\n")
        append("你面对的是初一孩子，要用他能听懂的话：\n")
        append("- 不说术语，不说\"掌握度\"\"答对率\"这类词\n")
        append("- 不说\"你很差\"\"太低了\"，改说\"还不太熟\"\"多练几遍就好\"\n")
        append("- 不超出教材范围\n\n")
        append("【怎么讲】知识点的 category 决定讲法：\n")
        append("1. category = \"背诵\"（音标写词、听音写词、词义选择等）：\n")
        append("   这类答错基本都是\"没记住\"，**只给一句统计 + 一句意见**，不要分析原因。\n")
        append("   例：\"音标写词练了 5 题对了 1 题，这些词多读两遍就记住了。\"\n")
        append("2. category = \"理解\"（词形变化、语境选词、课文理解、阅读/听力选择等）：\n")
        append("   这类要讲透。**优先用 mistakes 里的真实错题**，说清\"错在哪、该怎么做\"。\n")
        append("   例：\"这句话你填了 go，应该是 went，因为说的是昨天的事。\"\n")
        append("3. **不要逐类罗列**（不要每类都提一句）。\n")
        append("   挑**最容易犯错的一两处讲透**，其余略过。\n")
        append("4. 讲错题时**用 mistakes 里的原文**：引用题目里的句子 / 空格、孩子填的答案、\n")
        append("   正确答案；如果 wrong_times 大于 1，说明\"这类错了好几次，要专门练\"。\n")
        append("5. mistakes 为空时，只按 knowledge_points 给统计与整体意见，不要编具体错题。\n\n")
        append("只输出一个 JSON 对象（不要 markdown 代码围栏、不要任何解释文字），")
        append("必须且只能包含以下字段：\n")
        append(ANALYZE_FIELDS.joinToString("、")).append("\n\n")
        append("字段约束：\n")
        append("1. summary：一句话，最多 40 字，说清\"练了多少、大概怎么样\"；\n")
        append("2. strengths / weaknesses：数组，每项最多 20 字，各最多 2 项；没有就给空数组 []；\n")
        append("   weaknesses 要**具体**（点出是哪一类，能引用 mistakes 里的内容更好）；\n")
        append("3. advice：一句话，最多 40 字，给**具体动作**（练什么、怎么练）；\n")
        append("4. practice_suggestions：数组，1~2 项；每项含 label / reason / entry / mode；\n")
        append("   label 必须与\"可选练习\"里给出的完全一致；reason 最多 12 字；\n")
        append("5. 不出现分数、排名、等级、百分比。")
    }

    /** 学情分析 user 提示词：输入 JSON + 可选练习白名单。 */
    private fun analyzeUser(obj: JSONObject): String = buildString {
        append("这是孩子本单元的学习数据：\n")
        append(obj.toString()).append("\n\n")
        append("可选练习（practice_suggestions 只能从这里挑，entry 和 mode 必须原样照抄）：\n")
        val arr = obj.optJSONArray("practice_entries")
        if (arr != null) {
            for (i in 0 until arr.length()) {
                val e = arr.optJSONObject(i) ?: continue
                append("- ").append(e.optString("label"))
                    .append(" → entry=").append(e.optString("entry"))
                    .append(", mode=").append(e.optString("mode")).append('\n')
            }
        }
        append("\n请按要求生成分析 JSON。")
    }

    private fun runAnalyze(payload: String): JSONObject {
        val obj = try {
            JSONObject(payload)
        } catch (e: Exception) {
            return failed("payload 不是合法 JSON")
        }
        // ① 门槛**由程序判定**（不采信页面自称）：练题数必须达到下限
        val practiced = obj.optInt("total_questions_practiced", 0)
        if (practiced < ANALYZE_MIN_PRACTICED) {
            return rejected("练习数据不足（" + practiced + " / " + ANALYZE_MIN_PRACTICED + "）")
        }
        // ② 前置：AI 未配置 / 未启用 —— 如实回报，不伪造分析
        val config = AiConfigStore.load(context)
        if (!config.enabled) return JSONObject().put("status", "ai_disabled")
        if (!config.endpointReady) return JSONObject().put("status", "not_configured")

        val r = AiClient.chatJson(
            context = context,
            system = analyzeSystem(),
            user = analyzeUser(obj),
            requiredFields = ANALYZE_FIELDS,
            maxTokens = ANALYZE_MAX_TOKENS,
        )
        val data = when (r) {
            is AiResult.OkJson -> r.data
            is AiResult.Disabled -> return JSONObject().put("status", "ai_disabled")
            is AiResult.NotConfigured -> return JSONObject().put("status", "not_configured")
            is AiResult.Failure -> return failed(r.message)
            is AiResult.Ok -> return failed("AI 返回了非结构化文本（预期 JSON）")
        }
        // ③ **越界收敛**：practice_suggestions 的 entry/mode 必须落在输入白名单里，
        //    不在白名单的整条丢弃（**不采信 AI 自证**；与 JS 侧校验同口径，双保险）。
        val allowed = LinkedHashSet<String>()
        val labels = HashMap<String, String>()
        obj.optJSONArray("practice_entries")?.let { arr ->
            for (i in 0 until arr.length()) {
                val e = arr.optJSONObject(i) ?: continue
                val key = e.optString("entry") + "|" + e.optString("mode")
                allowed.add(key)
                labels[key] = e.optString("label")
            }
        }
        val out = LinkedHashMap<String, Any?>(data)
        val kept = ArrayList<Map<String, Any?>>()
        @Suppress("UNCHECKED_CAST")
        val sugg = (data["practice_suggestions"] as? List<Any?>).orEmpty()
        for (s in sugg) {
            val m = s as? Map<String, Any?> ?: continue
            val key = (m["entry"] as? String).orEmpty() + "|" + (m["mode"] as? String).orEmpty()
            if (!allowed.contains(key)) continue
            val one = LinkedHashMap<String, Any?>()
            one["entry"] = m["entry"]
            one["mode"] = m["mode"]
            // label **以输入白名单为准**（AI 只决定"挑哪个"，不决定"叫什么"）
            one["label"] = labels[key] ?: (m["label"] as? String).orEmpty()
            one["reason"] = (m["reason"] as? String).orEmpty().take(20)
            kept.add(one)
        }
        out["practice_suggestions"] = kept
        return JSONObject()
            .put("status", "ok")
            .put("data", mapToJson(out))
            .put("dropped_suggestions", (sugg.size - kept.size))
    }

    private fun runTeach(payload: String): JSONObject {
        val obj = try {
            JSONObject(payload)
        } catch (e: Exception) {
            return failed("payload 不是合法 JSON")
        }
        if (obj.optString("_question_id").isEmpty()) return failed("payload 缺少 question_id")
        // 范围锚点（V1.3 第二十九章 §19 第 3 条）：
        //   Section 级题型 -> "section" + section_key；Unit 级题型 -> "unit" + unit_code 兜底。
        // 两者皆空才拒绝（原实现只看 section_key，会把 216 道 Unit 级辅助题全部挡掉）。
        val anchorValue = scopeAnchorValue(obj)
        if (anchorValue.isEmpty()) return failed("payload 缺少范围锚点（划不出范围，不讲解）")

        val config = AiConfigStore.load(context)
        if (!config.enabled) return JSONObject().put("status", "ai_disabled")
        if (!config.endpointReady) return JSONObject().put("status", "not_configured")

        val r = AiClient.chatJson(
            context = context,
            system = teachSystem(obj.optString("question_type")),
            user = teachUser(obj),
            requiredFields = TEACH_FIELDS,
            maxTokens = TEACH_MAX_TOKENS,
        )
        val data = when (r) {
            is AiResult.OkJson -> r.data
            is AiResult.Disabled -> return JSONObject().put("status", "ai_disabled")
            is AiResult.NotConfigured -> return JSONObject().put("status", "not_configured")
            is AiResult.Failure -> return failed(r.message)
            is AiResult.Ok -> return failed("AI 返回了非结构化文本（预期 JSON）")
        }
        // 越界丢弃例句（不采信 AI 自证）：example 必须存在且非空；来源标注须合法
        val out = LinkedHashMap<String, Any?>(data)
        val ex = (out["example"] as? String).orEmpty().trim()
        val src = (out["example_source"] as? String).orEmpty().trim()
        if (ex.isEmpty() || (src != "textbook" && src != "generated")) {
            out["example"] = ""
            out["example_source"] = "none"
            out["example_dropped_reason"] = if (ex.isEmpty()) "empty" else "invalid_source"
        }
        return JSONObject()
            .put("status", "ok")
            .put("data", mapToJson(out))
            .put("evidenceCount", AiEvidencePrompt.countEvidenceForGate(
                obj.optJSONObject("evidence_pool")?.let { jsonToMap(it) }, obj.optString("_granularity").takeIf { it.isNotEmpty() }))
    }

    private fun pushAnalyze(result: JSONObject) {
        val js = "window.__zxAnalyzeOnResult(" + JSONObject.quote(result.toString()) + ");"
        Log.i(TAG, "学情分析桥回报：status=" + result.optString("status") +
                (result.optString("reason").takeIf { it.isNotEmpty() }?.let { " reason=" + it } ?: ""))
        webView.post { webView.evaluateJavascript(js, null) }
    }

    private fun pushTeach(result: JSONObject) {
        val js = "window.__zxTeachOnResult(" + JSONObject.quote(result.toString()) + ");"
        Log.i(TAG, "讲解桥回报：status=" + result.optString("status") +
                (result.optString("reason").takeIf { it.isNotEmpty() }?.let { " reason=" + it } ?: ""))
        webView.post { webView.evaluateJavascript(js, null) }
    }


    private fun failed(reason: String): JSONObject =
        JSONObject().put("status", "failed").put("reason", reason)

    /** 回调页面；`json` 由 [JSONObject.toString] 产出，注入前统一转义。 */
    private fun push(result: JSONObject) {
        val js = "window.__zxAiOnResult(" + JSONObject.quote(result.toString()) + ");"
        Log.i(TAG, "批改桥回报：status=" + result.optString("status") +
                (result.optString("reason").takeIf { it.isNotEmpty() }?.let { " reason=" + it } ?: ""))
        webView.post { webView.evaluateJavascript(js, null) }
    }
    private fun jsonToMap(o: JSONObject): Map<String, Any?> {
        val out = LinkedHashMap<String, Any?>()
        val it = o.keys()
        while (it.hasNext()) {
            val k = it.next()
            out[k] = plain(o.opt(k))
        }
        return out
    }

    private fun plain(v: Any?): Any? = when (v) {
        null, JSONObject.NULL -> null
        is JSONObject -> jsonToMap(v)
        is JSONArray -> (0 until v.length()).map { plain(v.opt(it)) }
        else -> v
    }

    private fun mapToJson(m: Map<String, Any?>): JSONObject {
        val o = JSONObject()
        for ((k, v) in m) o.put(k, jsonValue(v))
        return o
    }

    private fun jsonValue(v: Any?): Any = when (v) {
        null -> JSONObject.NULL
        is Map<*, *> -> {
            val o = JSONObject()
            for ((k, vv) in v) o.put(k.toString(), jsonValue(vv))
            o
        }
        is List<*> -> {
            val a = JSONArray()
            for (vv in v) a.put(jsonValue(vv))
            a
        }
        else -> v
    }

    companion object {
        private const val TAG = "ZhixueAiBridge"
        private const val BRIDGE_VERSION = "a1-2026-09-29"
        /** `deepseek-chat` 实测 `contentLen=773`；1024 足够且留余量。 */
        private const val AI_MAX_TOKENS = 1024
        /**
         * 题型族分派（V1.3 第二十九章 §19 第 4 条 / 流程规范 §27）：
         * **不同题型族的 AI 指令必须分别设计，不得统一模板**。
         *
         * | 族 | 覆盖题型 |
         * | --- | --- |
         * | 语法 | `vocab_word_form` |
         * | 词汇 | `vocab_*` / `phrase_*` / `phonetics_*` |
         * | 理解 | `textbook_native` / `sentence_listen_*` / `listening_choice` / `listen_*` / `reading_choice` |
         * | 写作 | `writing*` / 含 `writing` 的题型 |
         */
        internal fun questionFamily(questionType: String): String = when {
            questionType.startsWith("vocab_word_form") -> "grammar"
            questionType.startsWith("vocab_") || questionType.startsWith("phrase_") ||
                questionType.startsWith("phonetics_") -> "vocab"
            questionType.startsWith("writing") || questionType.contains("writing") -> "writing"
            else -> "comprehension"
        }

        /** 族专属指令（**只写该族的重点与禁忌**；共同约束由 [teachSystem] 统一追加）。 */
        internal fun familyInstruction(family: String): String = when (family) {
            "grammar" -> buildString {
                append("题型族：**语法（词形变化）**。\n")
                append("讲的重点：这道题该用哪个**词形**（如名词复数、动词第三人称单数、过去式），以及它的**规则出处**（教材附录的词形变化规则）。\n")
                append("例句要求：**必须体现该词形的用法**，让孩子能照着仿写。\n")
                append("**不得**：展开完整语法体系；**不得**使用语法术语（如\"第三人称单数\"\"主谓一致\"），要用孩子能懂的话说。\n")
            }
            "vocab" -> buildString {
                append("题型族：**词汇**。\n")
                append("讲的重点：这个**词 / 短语的意思**、它在**什么语境下用**、与孩子所填内容的差别。\n")
                append("例句要求：**必须是教材语境里的句子**（可来自句池或教材素材），让孩子看到词的真实用法。\n")
                append("**不得**：只给中文释义了事；**不得**用教材外的词造句。\n")
            }
            "writing" -> buildString {
                append("题型族：**写作 / 连词成句**。\n")
                append("讲的重点：这个句子**该怎么组织**（词序、搭配），孩子写的哪里不通。\n")
                append("例句要求：**必须是可仿写的教材句**，长度与难度不超出本单元。\n")
                append("**不得**：给范文式长文；**不得**使用超出本单元词汇的词。\n")
            }
            else -> buildString {
                append("题型族：**理解（听力 / 阅读 / 教材原题）**。\n")
                append("讲的重点：**听到了 / 读到了什么**，以及**判断依据**（教材原句）。\n")
                append("例句要求：**优先直接引用教材原句**；引用不到才依据教材素材写一句。\n")
                append("**不得**：脱离教材原文推断；**不得**编造教材没说过的事实。\n")
            }
        }

        /** 「AI 老师」三句话输出契约（与 JS 侧 __zxTeachOnResult 成对）。 */
        private val TEACH_FIELDS: List<String> = listOf("wrong", "should", "example", "example_source")
        /** 三句话 ≈ 60–120 tokens；320 留足余量（流程规范 §26.6）。 */
        private const val TEACH_MAX_TOKENS = 320

        /** 学情分析输出契约（与 JS 侧 __zxAnalyzeOnResult 成对）。 */
        private val ANALYZE_FIELDS: List<String> =
            listOf("summary", "strengths", "weaknesses", "advice", "practice_suggestions")
        /** 输出只有 5 个短字段（≤40 字 × 2 + 数组）⇒ 384 足够（参考 teach 的 320）。 */
        private const val ANALYZE_MAX_TOKENS = 384
        /** 学情分析门槛（与 Python 侧 demo_data.ANALYZE_MIN_PRACTICED 同值，双保险）。 */
        private const val ANALYZE_MIN_PRACTICED = 10
    }
}

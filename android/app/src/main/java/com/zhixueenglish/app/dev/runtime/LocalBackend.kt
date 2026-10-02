package com.zhixueenglish.app.dev.runtime

import android.content.Context
import android.util.Log
import java.net.HttpURLConnection
import java.net.URL

/**
 * Android 本地 Python Web 服务（承接《智学小四门》已验证路线）。
 *
 * 链路：APK → AAR（p4a service_library：CPython + 载荷）→ ServiceZhixue.prepare()/start()
 *      → 现有 Python 服务 127.0.0.1:8770 → WebView 之后访问本地地址。
 *
 * 关键点：
 *   * AAR 中的类名由 p4a 打包时决定（com.zhixueenglish.app.dev.runtime.ServiceZhixue）；
 *     这里用反射调用，**AAR 尚未打入时工程仍可编译**，并在运行期给出明确失败原因；
 *   * 启动成功以 HTTP `/health` 真实返回 200 为准，不做"延时后假设成功"；
 *   * 任何失败都只写日志 + 返回状态，不抛出、不阻塞已有学习功能。
 */
object LocalBackend {

    private const val TAG = "ZhixueLocalBackend"
    private const val RUNTIME_CLASS = "com.zhixueenglish.app.dev.runtime.ServiceZhixue"

    /** 手机本地服务 = 正式 Web（web/app.py），默认端口 8770（P6-B：已从 Demo 切换）。 */
    const val HOST = "127.0.0.1"
    const val PORT = 8770
    const val BASE_URL = "http://$HOST:$PORT/"
    private const val HEALTH_URL = BASE_URL + "health"

    sealed class State {
        object Idle : State()
        object Preparing : State()
        object Starting : State()
        data class Ready(val url: String) : State()
        data class Failed(val reason: String) : State()
    }

    /** AAR 是否已经打进 APK（未打进时给出明确原因，不静默失败）。 */
    fun runtimePackaged(): Boolean = try {
        Class.forName(RUNTIME_CLASS)
        true
    } catch (_: Throwable) {
        false
    }

    /**
     * 解包 + 启动本地 Python 服务（耗时操作，调用方需放在后台线程）。
     * 返回失败原因；成功返回 null。
     */
    fun prepareAndStart(context: Context): String? {
        val app = context.applicationContext
        return try {
            val clazz = Class.forName(RUNTIME_CLASS)
            clazz.getMethod("prepare", Context::class.java).invoke(null, app)
            Log.i(TAG, "runtime unpacked (prepare() ok)")
            startService(app)
            null
        } catch (e: ClassNotFoundException) {
            Log.e(TAG, "runtime AAR not packaged into APK: $RUNTIME_CLASS")
            "APK 内未包含本地 Python 运行时（缺少 runtime AAR）"
        } catch (e: Throwable) {
            Log.e(TAG, "embedded python service failed to start", e)
            "${e.javaClass.simpleName}: ${e.message.orEmpty().take(160)}"
        }
    }

    /** 只请求启动 Python 服务（不做解包）。 */
    fun startService(context: Context): String? = try {
        val clazz = Class.forName(RUNTIME_CLASS)
        clazz.getMethod("start", Context::class.java, String::class.java)
            .invoke(null, context.applicationContext, "start")
        Log.i(TAG, "embedded python service start requested")
        null
    } catch (e: Throwable) {
        Log.e(TAG, "embedded python service start failed", e)
        "${e.javaClass.simpleName}: ${e.message.orEmpty().take(160)}"
    }

    /**
     * 前台恢复用：先探活；服务不在（被系统回收 / 首次启动）就重启并等待 /health。
     *
     * 返回失败原因；成功返回 null。**只复用现有 ServiceZhixue 启动机制**，不引入后台框架。
     */
    fun ensureRunning(context: Context, waitMs: Long = 60_000L): String? {
        if (healthOnce()) {
            Log.i(TAG, "embedded python service already healthy")
            return null
        }
        Log.i(TAG, "embedded python service not reachable; starting it")
        val started = startService(context)
        if (started != null) return started
        return if (awaitHealthy(timeoutMs = waitMs)) null else "本地服务已请求启动但 /health 未就绪（${waitMs / 1000}s）"
    }

    /** 真实探活：轮询 /health，直到 200 或超时。
     *
     * P5：指数退避 50 → 100 → 200 → 400ms（上限 400ms）。
     * 服务通常 1s 内就绪，退避让首次探活更快命中（启动体感更快）；
     * 服务慢时封顶 400ms，不增加 CPU 与日志负担。
     */
    fun awaitHealthy(timeoutMs: Long = 30_000L, maxIntervalMs: Long = 400L): Boolean {
        val deadline = System.currentTimeMillis() + timeoutMs
        var attempt = 0
        var intervalMs = 50L          // P5：首次 50ms，随后指数退避至 maxIntervalMs
        while (System.currentTimeMillis() < deadline) {
            attempt += 1
            if (healthOnce()) return true
            if (attempt == 1 || attempt % 15 == 0) {
                Log.w(TAG, "health probe attempt=$attempt port=$PORT not ready yet")
            }
            try {
                Thread.sleep(intervalMs)
            intervalMs = (intervalMs * 2).coerceAtMost(maxIntervalMs)   // P5：指数退避
            } catch (_: InterruptedException) {
                return false
            }
        }
        Log.w(TAG, "health probe gave up after $attempt attempts")
        return false
    }

    fun healthOnce(timeoutMs: Int = 1200): Boolean = try {
        val connection = URL(HEALTH_URL).openConnection() as HttpURLConnection
        connection.connectTimeout = timeoutMs
        connection.readTimeout = timeoutMs
        connection.requestMethod = "GET"
        connection.useCaches = false
        val code = connection.responseCode
        connection.disconnect()
        if (code != 200) Log.w(TAG, "health probe got HTTP $code")
        code == 200
    } catch (e: Throwable) {
        Log.w(TAG, "health probe failed: ${e.javaClass.simpleName}: ${e.message.orEmpty().take(80)}")
        false
    }
}

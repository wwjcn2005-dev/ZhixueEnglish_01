package com.zhixueenglish.app.dev

import android.content.Context
import android.annotation.SuppressLint
import android.os.Bundle
import android.util.Log
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.RenderProcessGoneDetail
import android.webkit.WebView
import android.webkit.WebViewClient
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.zhixueenglish.app.dev.ai.AiSettingsScreen
import com.zhixueenglish.app.dev.ai.ZxAiBridge
import com.zhixueenglish.app.dev.runtime.LocalBackend

/**
 * P1-12-C3-C1：正式 Web UI 的 Android 最小壳。
 *
 * 职责边界（严格最小）：
 *   - 只做一件事：用 WebView 打开本项目的正式 Web UI（地址见 BuildConfig.WEB_BASE_URL）
 *   - 不含任何原生学习逻辑、不含原生数据库、不访问其它项目的服务
 *   - 不引入登录、推送、上传、下载、AI、复杂权限
 *
 * 颜色遵循 docs/P1-12-C3-A（背景 #F6F7F9、主色 #1677FF）。
 */
private const val TAG = "ZhixueWebView"

/**
 * 视口高度兜底（只作用于渲染，不改任何页面文件）。
 *
 * 真机实测：该 WebView 里 `100vh / 100dvh / 100svh` 全部算成 0（而 `window.innerHeight` = 891），
 * 而当前 Demo 页面用 `html{height:100%;overflow:hidden}` + `body{height:100vh;height:100dvh}`
 * 决定整页高度 → body 高度 0 → 全部内容被 `overflow:hidden` 裁掉，只剩背景色（白屏）。
 * 因此在 onPageFinished 后用像素高度覆盖 html/body 高度，并在尺寸变化时重算。
 */
private const val VIEWPORT_HEIGHT_FIX_JS = """
(function () {
  var apply = function () {
    var h = window.innerHeight + 'px';
    document.documentElement.style.height = h;
    if (document.body) { document.body.style.height = h; }
  };
  apply();
  window.addEventListener('resize', apply);
  window.addEventListener('orientationchange', apply);
})();
"""

private val BACKGROUND = Color(0xFFF6F7F9)
private val TEXT_PRIMARY = Color(0xFF17181A)
private val TEXT_SECONDARY = Color(0xFF6B7078)
private val BRAND = Color(0xFF1677FF)

private val LINE = Color(0xFFE7E9ED)

/**
 * 是否在首页。
 *
 * P6-B-7：设置入口只属于首页——学习页面（跟读/听音辨意/音标写词/词形变化/本课检测/自主练习）
 * 不显示设置。只做地址判定，不改动任何页面本身。
 */
private fun isHomeUrl(url: String?): Boolean {
    if (url.isNullOrEmpty()) return false
    val afterHost = url.substringAfter("://", url)
    val path = afterHost.substringAfter('/', "").substringBefore('?').substringBefore('#')
    return path.isEmpty()
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Log.i(TAG, "打开正式 Web UI: " + BuildConfig.WEB_BASE_URL)
        if (BuildConfig.DEBUG) {
            // 仅 debug 构建：允许通过 chrome://inspect / CDP 定位 WebView 内部布局（不影响 release）
            WebView.setWebContentsDebuggingEnabled(true)
        }

        startLocalBackend()
        // P6-B-7：跟读录音需要系统麦克风权限（Android 正常权限流程，不绕过）
        if (checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)
            != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(android.Manifest.permission.RECORD_AUDIO), 9001)
        }
        setContent {
            MaterialTheme {
                var showSettings by remember { mutableStateOf(false) }
                var backend by remember { mutableStateOf(BackendStateHolder.state) }
                var reloadTick by remember { mutableStateOf(0) }
                var atHome by remember { mutableStateOf(false) }
                BackendStateHolder.onChange = { state ->
                    val wasReady = backend is LocalBackend.State.Ready
                    backend = state
                    // 服务从“非就绪”回到“就绪”（含被系统回收后恢复）→ 让 WebView 重新加载
                    if (state is LocalBackend.State.Ready && !wasReady) reloadTick += 1
                }
                if (showSettings) {
                    AiSettingsScreen(onBack = { showSettings = false })
                } else {
                    Box(modifier = Modifier.fillMaxSize()) {
                        // 只有本地服务真正就绪（/health 200）才加载页面：不进入空白 WebView
                        when (val state = backend) {
                            is LocalBackend.State.Ready ->
                                WebViewScreen(
                                    url = state.url,
                                    reloadTick = reloadTick,
                                    onExit = { finish() },
                                    onRetryConnection = { startLocalBackend() },
                                    onHomeChanged = { atHome = it },
                                    lastUrlProvider = { lastRememberedUrl(this@MainActivity) },
                                )

                            is LocalBackend.State.Failed ->
                                BackendErrorScreen(
                                    reason = state.reason,
                            onRetry = { startLocalBackend() },
                                )

                            else -> BackendStartingScreen()
                        }
                        // P6-B-7：设置只出现在首页（学习页面不显示）
                        if (atHome) {
                            SettingsChip(
                                onClick = { showSettings = true },
                                modifier = Modifier
                                    .align(Alignment.TopEnd)
                                    .statusBarsPadding()
                                    // 与 HTML 顶栏「智学英语」标题同行：实测偏移量，offset 不影响触摸区域
                                    .offset(y = (-16).dp)
                                    .padding(top = 0.dp, end = 8.dp)
                            )
                        }
                    }
                }
            }
        }
    }

    /**
     * 回到前台时确保本地服务可用：
     *   * **已就绪** → 只做健康检查（`ensureBackendAlive()`）：服务被回收（LMK）时自动重启并等 /health；
     *   * **未就绪**（Preparing / Starting / Failed，含"进程被系统回收后重建，内存态归零"）
     *     → 主动走一遍 `startLocalBackend()`。
     *
     * 2026-09-30 修正：原实现只在 `state is Ready` 时才检查 ⇒ **进程被回收重建时内存态不是 Ready，
     * 后端重启逻辑【从不执行】**，界面永久停在"启动本地服务"（真机实测复现）。
     * 现在补齐这一半：非 Ready 一律主动拉起（`prepareAndStart` + 等 /health 就绪）。
     */
    override fun onResume() {
        super.onResume()
        when (BackendStateHolder.state) {
            is LocalBackend.State.Ready -> ensureBackendAlive()
            else -> startLocalBackend()
        }
    }

    private fun ensureBackendAlive() {
        Thread {
            if (LocalBackend.healthOnce()) {
                Log.i(TAG, "resume: local backend still healthy")
                return@Thread
            }
            Log.w(TAG, "resume: local backend unreachable; restarting")
            BackendStateHolder.publish(LocalBackend.State.Starting)
            val failure = LocalBackend.ensureRunning(applicationContext, waitMs = 120_000L)
            BackendStateHolder.publish(
                if (failure == null) {
                    Log.i(TAG, "resume: local backend restored")
                    LocalBackend.State.Ready(LocalBackend.BASE_URL)
                } else {
                    Log.w(TAG, "resume: local backend restore failed: $failure")
                    LocalBackend.State.Failed(failure)
                }
            )
        }.start()
    }

    /**
     * 启动 Android 本地 Python Web 服务（127.0.0.1:8770）。
     *
     * 本阶段只负责"服务能起来"：以 `/health` 真实返回 200 作为成功判据；
     * WebView 仍按既有地址访问，URL 切换在下一阶段进行（基线 §12 ③）。
     */
    private fun startLocalBackend() {
        Thread {
            BackendStateHolder.publish(LocalBackend.State.Preparing)
            val failure = LocalBackend.prepareAndStart(applicationContext)
            if (failure != null) {
                BackendStateHolder.publish(LocalBackend.State.Failed(failure))
                return@Thread
            }
            BackendStateHolder.publish(LocalBackend.State.Starting)
            // 首次安装要解包 122MB 载荷（+ 官方音频），给足冷启动时间；就绪判定仍是真实 /health
            val healthy = LocalBackend.awaitHealthy(timeoutMs = 180_000L)
            BackendStateHolder.publish(
                if (healthy) {
                    Log.i(TAG, "local backend ready: " + LocalBackend.BASE_URL)
                    LocalBackend.State.Ready(LocalBackend.BASE_URL)
                } else {
                    Log.w(TAG, "local backend health check timeout")
                    LocalBackend.State.Failed("本地服务已启动但 /health 未就绪（180s 超时）")
                }
            )
        }.start()
    }
}

/** 本地服务状态：后台线程写、Compose 读（不引入新依赖）。 */
private object BackendStateHolder {
    @Volatile
    var state: LocalBackend.State = LocalBackend.State.Idle

    @Volatile
    var onChange: ((LocalBackend.State) -> Unit)? = null

    fun publish(state: LocalBackend.State) {
        this.state = state
        val handler = android.os.Handler(android.os.Looper.getMainLooper())
        handler.post { onChange?.invoke(state) }
    }
}

/** 本地服务状态条：明确显示"准备中 / 已就绪 / 启动失败原因"，不进入空白页。 */
@Composable
private fun BackendStatusChip(state: LocalBackend.State, modifier: Modifier = Modifier) {
    val text = when (state) {
        LocalBackend.State.Idle -> "本地服务：待启动"
        LocalBackend.State.Preparing -> "本地服务：解包中…"
        LocalBackend.State.Starting -> "本地服务：启动中…"
        is LocalBackend.State.Ready -> "本地服务：已就绪 ${LocalBackend.HOST}:${LocalBackend.PORT}"
        is LocalBackend.State.Failed -> "本地服务：启动失败（${state.reason}）"
    }
    Box(
        modifier = modifier
            .background(Color(0xFFFFFFFF).copy(alpha = 0.92f), RoundedCornerShape(10.dp))
            .border(1.dp, LINE, RoundedCornerShape(10.dp))
            .padding(horizontal = 10.dp, vertical = 6.dp)
    ) {
        Text(
            text = text,
            color = TEXT_SECONDARY,
            fontSize = 11.sp,
            fontWeight = FontWeight.Medium,
        )
    }
}

/** 本地服务未就绪时的占位页：不让用户停在空白 WebView 上。 */
@Composable
private fun BackendStartingScreen() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BACKGROUND),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        CircularProgressIndicator(color = BRAND)
        Text(
            text = stringResource(R.string.local_backend_starting),
            color = TEXT_SECONDARY,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(top = 12.dp)
        )
    }
}

/** 本地服务启动失败：显示明确原因 + 重试（可同时进入设置页检查 AI 配置）。 */
@Composable
private fun BackendErrorScreen(reason: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BACKGROUND)
            .padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            text = stringResource(R.string.local_backend_failed),
            color = TEXT_PRIMARY,
            textAlign = TextAlign.Center
        )
        Text(
            text = reason,
            color = TEXT_SECONDARY,
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(top = 8.dp)
        )
        Button(onClick = onRetry, modifier = Modifier.padding(top = 16.dp)) {
            Text(stringResource(R.string.retry))
        }
    }
}

/**
 * 设置入口：贴在顶栏右侧的预留空位上（不新增首页入口、不影响学习页布局）。
 * 只打开本机设置页，不触发任何 AI 请求。
 */
@Composable
private fun SettingsChip(onClick: () -> Unit, modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .background(Color(0xFFFFFFFF).copy(alpha = 0.92f), RoundedCornerShape(10.dp))
            .border(1.dp, LINE, RoundedCornerShape(10.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 6.dp)
    ) {
        Icon(
            painter = painterResource(R.drawable.ic_settings),
            contentDescription = stringResource(R.string.settings_entry),
            tint = TEXT_SECONDARY,
            modifier = Modifier.size(18.dp),
        )
    }
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
private fun WebViewScreen(
    url: String,
    reloadTick: Int,
    onExit: () -> Unit,
    onRetryConnection: () -> Unit,
    onHomeChanged: (Boolean) -> Unit,
    lastUrlProvider: () -> String?,
) {
    var loading by remember { mutableStateOf(true) }
    var failed by remember { mutableStateOf(false) }
    var failReason by remember { mutableStateOf("") }
    var reloadToken by remember { mutableStateOf(0) }
    var webView by remember { mutableStateOf<WebView?>(null) }
    var firstLoadDone by remember { mutableStateOf(false) }

    // 服务恢复后（reloadTick 变化）让 WebView 回到**上次的页面**；首次加载由 update 完成。
    // 注意：这里用 `loadUrl(目标)` 而不是 `reload()` —— 新建的 WebView 只加载过首页，
    // `reload()` 会把孩子弹回首页；`loadUrl` 才能回到原页。
    LaunchedEffect(reloadTick) {
        if (reloadTick > 0 && firstLoadDone) {
            val target = lastUrlProvider() ?: url
            Log.i(TAG, "backend restored → load last page: $target")
            loading = true
            failed = false
            webView?.loadUrl(target)
        }
    }

    // 系统返回键：能后退就后退，否则退出——与页面内返回保持一致
    // 系统返回键：能后退就后退，否则退出——与页面内返回保持一致。
    //
    // **例外（2026-09-30）：提交结果页不能走 WebView 默认返回** ——
    // P5 提交用 POST，结果页被标记为"POST 提交的结果"；按返回时 WebView 不能重复提交 POST、
    // 缓存里也没有 ⇒ `net::ERR_CACHE_MISS`。故此时改为 loadUrl 跳到**安全页**（该入口的 GET 页），
    // 避开 POST 历史。**正常页面（GET）仍走原 goBack 逻辑，不受影响。**
    BackHandler(enabled = true) {
        val view = webView
        val safeUrl = view?.url?.let { safeBackUrl(it) }
        if (view != null && safeUrl != null) {
            view.loadUrl(safeUrl)
        } else if (view != null && view.canGoBack()) {
            view.goBack()
        } else {
            onExit()
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(BACKGROUND)
    ) {
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { context ->
                WebView(context).apply {
                    // 当前产品是 JS 环境页面（手机 Chrome 同环境正常）；JS 同时用于下面的视口高度兜底
                    settings.javaScriptEnabled = true
                    settings.domStorageEnabled = true
                    // P5 跟读页用整页共享播放器：进入内容时自动播放需要允许无手势播放
                    settings.mediaPlaybackRequiresUserGesture = false
                    // Demo 页面用 html/body 100% / 100vh / 100dvh + overflow:hidden 控制整页高度：
                    // 必须让 WebView 按设备宽度布局（否则容易拿到 0 高视口 → 整页被裁成白屏）
                    settings.useWideViewPort = true
                    settings.loadWithOverviewMode = true
                    // A-1：AI 批改桥（页面 → 原生 → AI）。**仅 debug**：release 不注入，
                    // 页面据此显示"AI 暂不可用"并保留"需要 AI 批改"文案（不阻断确定性学习功能）。
                    // Key 不进页面：页面只交 payload，调用与解密全在原生侧完成。
                    if (BuildConfig.DEBUG) {
                        addJavascriptInterface(ZxAiBridge(context, this), "ZxAi")
                    }
                    // P6-B-7：跟读录音 —— 只放行页面申请的麦克风资源，其它 Web 权限一律拒绝
                    webChromeClient = object : WebChromeClient() {
                        override fun onPermissionRequest(request: PermissionRequest?) {
                            val req = request ?: return
                            val audioOnly = req.resources.all { it == PermissionRequest.RESOURCE_AUDIO_CAPTURE }
                            if (audioOnly && context.checkSelfPermission(
                                    android.Manifest.permission.RECORD_AUDIO)
                                == android.content.pm.PackageManager.PERMISSION_GRANTED) {
                                req.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE))
                                if (BuildConfig.DEBUG) {
                                    Log.d(TAG, "[perm] onPermissionRequest resources=" +
                                        req.resources.joinToString() + " origin=" + req.origin +
                                        " -> GRANT")
                                }
                            } else {
                                req.deny()
                                Log.w(TAG, "[perm] onPermissionRequest resources=" +
                                    req.resources.joinToString() + " origin=" + req.origin +
                                    " audioOnly=" + audioOnly + " -> DENY")
                            }
                        }

                        // 诊断桥：把网页 console 输出转发到 logcat（WebView 开发标配，长期保留）
                        override fun onConsoleMessage(msg: android.webkit.ConsoleMessage): Boolean {
                            Log.i(TAG, "[js] " + msg.message() + " @" + msg.lineNumber())
                            return true
                        }
                    }
                    setBackgroundColor(0xFFF6F7F9.toInt())
                    // 注意：这里**不** loadUrl —— 等视图完成首次测量后在 update 中加载
                    webViewClient = object : WebViewClient() {
                        override fun onPageFinished(view: WebView?, url: String?) {
                            loading = false
                            Log.i(TAG, "页面加载完成: " + url)
                            // 记录「最后一次成功加载的页面」：进程被回收后据此回到原页
                            view?.context?.let { rememberLastUrl(it, url) }
                            onHomeChanged(isHomeUrl(url))
                            // 修正该 WebView 视口单位（vh/dvh）为 0 导致的整页高度 0（白屏）
                            view?.evaluateJavascript(VIEWPORT_HEIGHT_FIX_JS, null)
                        }

                        override fun doUpdateVisitedHistory(view: WebView?, url: String?, isReload: Boolean) {
                            onHomeChanged(isHomeUrl(url))
                        }

                        override fun onReceivedError(
                            view: WebView?,
                            request: WebResourceRequest?,
                            error: WebResourceError?
                        ) {
                            if (request?.isForMainFrame == true) {
                                loading = false
                                failed = true
                                failReason = error?.description?.toString().orEmpty()
                                Log.w(TAG, "页面加载失败: " + error?.description)
                            }
                        }

                        override fun onRenderProcessGone(
                            view: WebView?,
                            detail: RenderProcessGoneDetail?
                        ): Boolean {
                            // 渲染进程被系统回收：先尝试按**原 URL 自动重载**（不再只是报错），
                            // 重载失败时由 onReceivedError 落到失败态（不永久白屏）。
                            val target = lastUrlProvider() ?: url
                            Log.w(TAG, "render process gone (crashed=${detail?.didCrash()})"
                                + " → reload: $target")
                            loading = true
                            failed = false
                            view?.post { view.loadUrl(target) }
                            return true                      // 由宿主处理（不终止进程）
                        }
                    }
                    webView = this
                }
            },
            update = { view ->
                webView = view
                // 首次 update 时视图已完成测量 → 这时才加载，避免 0 高视口排版
                if (!firstLoadDone) {
                    firstLoadDone = true
                    loading = true
                    // 2026-10-01：**首次加载直接用「上次的页面」**，不再先加载首页。
                    // 原因（真机日志实证）：先加载首页会在稍后触发 onPageFinished，
                    // 把 `last_url` 覆盖成首页 ⇒ "这次回得去、下次又回首页"。
                    // 目标取不到时回落到 `url`（首页），行为与原来一致。
                    val first = lastUrlProvider() ?: url
                    view.post { view.loadUrl(first) }
                    Log.i(TAG, "首次加载（已在测量后执行）: $first")
                }
                if (reloadToken > 0 && failed) {
                    failed = false
                    loading = true
                    view.post { view.loadUrl(url) }
                }
            }
        )

        if (loading) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .align(Alignment.Center),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                CircularProgressIndicator(color = BRAND)
                Text(
                    text = stringResource(R.string.loading),
                    color = TEXT_SECONDARY,
                    style = MaterialTheme.typography.bodyMedium
                )
            }
        }

        if (failed) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .align(Alignment.Center)
                    .padding(32.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                Text(
                    text = stringResource(R.string.load_failed),
                    color = TEXT_PRIMARY,
                    textAlign = TextAlign.Center
                )
                if (failReason.isNotEmpty()) {
                    Text(
                        text = failReason,
                        color = TEXT_SECONDARY,
                        textAlign = TextAlign.Center,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                Button(onClick = {
                    // 先重新检查/必要时重启本地服务，再重新加载当前 URL
                    onRetryConnection()
                    reloadToken += 1
                }) {
                    Text(stringResource(R.string.retry))
                }
            }
        }
    }
}

/**
 * **提交结果页的返回拦截（方案 B）**：判断当前 URL 是否为"POST 提交后的结果页"，
 * 是则返回应当 loadUrl 的**安全页**（该入口的 GET 页）；不是则返回 `null`（走原返回逻辑）。
 *
 * 为什么需要它：P5 提交用 POST，结果页属"POST 提交的结果"；按返回键时 WebView 不能重复提交
 * POST、缓存里也没有该结果 ⇒ 报 `net::ERR_CACHE_MISS`。
 *
 * 拦截条件（**精确匹配**）：URL 的 path 段中包含 `submit`，且形如 `/unit/<slug>/p5/<entry>/submit`。
 * 跳转目标：同入口的 GET 页 `/unit/<slug>/p5/<entry>?lesson=<lesson>`（保留 `i=` 便于回到同一题）。
 * 不属于提交结果页时返回 `null`（调用方走原返回逻辑）。
 */
// ---------------------------------------------------------------------------
// 「上次页面 URL」恢复层（2026-09-30）
//
// 背景（真机实测）：熄屏 = onStop（进程存活，不重载）；但进程被系统回收后重新打开时，
// 后端不可达 → 重启后端 → `reloadTick` 自增 → 原先无条件 `webView.reload()`，
// 而新建 WebView 的初始 URL 是首页 ⇒ **孩子被弹回首页，丢掉正在做的那一题**。
//
// 修法：把「最后一次成功加载的页面 URL」持久化（SharedPreferences，跨进程重启有效），
// 恢复时 loadUrl 到该 URL；页面确实回不去时由宿主按失败态处理并回退首页。
// ---------------------------------------------------------------------------

/** 上次页面 URL 的持久化文件名 / 键。 */
private const val PREFS_NAME = "zx_web"
private const val KEY_LAST_URL = "last_url"


/** 记录最后一次成功加载的页面 URL（供进程回收后恢复）。 */
private fun rememberLastUrl(context: Context, url: String?) {
    if (url.isNullOrEmpty()) return
    if (!url.startsWith(LocalBackend.BASE_URL)) return          // 只记本机后端页面
    try {
        context.applicationContext
            .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit().putString(KEY_LAST_URL, url).apply()
    } catch (e: Exception) {
        Log.w(TAG, "rememberLastUrl failed: $e")
    }
}


/** 读回上次页面 URL；没有或不属于本机后端时返回 null（调用方回退首页）。 */
private fun lastRememberedUrl(context: Context): String? {
    return try {
        val v = context.applicationContext
            .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .getString(KEY_LAST_URL, null)
        if (v.isNullOrEmpty() || !v.startsWith(LocalBackend.BASE_URL)) null else v
    } catch (e: Exception) {
        Log.w(TAG, "lastRememberedUrl failed: $e")
        null
    }
}


internal fun safeBackUrl(currentUrl: String?): String? {
    val raw = currentUrl.orEmpty()
    if (raw.isEmpty()) return null
    // 纯字符串解析（不用 Uri.parse：① JVM 单测里是 stub、不可测；② 避免多余依赖）
    val schemeEnd = raw.indexOf("://")
    if (schemeEnd < 0) return null
    val afterScheme = raw.substring(schemeEnd + 3)
    val slash = afterScheme.indexOf('/')
    if (slash < 0) return null
    val authority = afterScheme.substring(0, slash)
    val pathAndQuery = afterScheme.substring(slash + 1)
    val path = pathAndQuery.substringBefore('?')
    val query = pathAndQuery.substringAfter('?', "")
    val seg = path.split('/').filter { it.isNotEmpty() }
    // 2026-09-30 修正：**P5 的提交结果页渲染出来的仍是 GET URL**（后端 POST 处理后
    // 直接渲染题目页），所以只在"当前 URL 以 /submit 结尾"时拦截是不够的 ——
    // 那种情况下 `goBack()` 会退回到历史里的 **POST URL**，触发 `net::ERR_CACHE_MISS`。
    // 改为：**当前页只要属于 P5，就跳到它自己的 GET 页**（避开 POST 历史）。
    // `/unit/<slug>/p5/<entry>[/submit]` 两种形态都归一为 GET 页。
    if (seg.size < 4) return null
    if (seg[0] != "unit" || seg[2] != "p5") return null
    val slug = seg[1]
    val entry = seg[3]
    if (entry.isEmpty() || entry == "submit") return null
    // 保留 lesson / i / mode（都是 GET 参数，拼接安全；丢了 mode 会串到另一种练习模式）
    val keep = query.split('&').filter {
        it.startsWith("lesson=") || it.startsWith("i=") || it.startsWith("mode=")
    }
    val q = if (keep.isEmpty()) "" else "?" + keep.joinToString("&")
    val base = BuildConfig.WEB_BASE_URL.trimEnd('/')
    return "$base/unit/$slug/p5/$entry$q"
}

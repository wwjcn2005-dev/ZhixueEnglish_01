package com.zhixueenglish.app.dev.ai

import android.os.Handler
import android.os.Looper
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.zhixueenglish.app.dev.R

/**
 * 设置 · AI 配置（APK 内唯一设置页；不新增首页入口、不新增 AI 中心）。
 *
 * 只做四件事：开关 AI、填 Base URL / API Key / Model、保存、连接测试。
 * API Key 只交给 [SecureKeyStore]（Keystore 密文），界面只显示尾号掩码。
 */
private val BACKGROUND = Color(0xFFF6F7F9)
private val CARD = Color(0xFFFFFFFF)
private val LINE = Color(0xFFE7E9ED)
private val TEXT_PRIMARY = Color(0xFF17181A)
private val TEXT_SECONDARY = Color(0xFF6B7078)
private val BRAND = Color(0xFF1677FF)

@Composable
fun AiSettingsScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val handler = remember { Handler(Looper.getMainLooper()) }
    val saved = remember { AiConfigStore.load(context) }

    var enabled by remember { mutableStateOf(saved.enabled) }
    var baseUrl by remember { mutableStateOf(saved.baseUrl) }
    var model by remember { mutableStateOf(saved.model) }
    var apiKeyInput by remember { mutableStateOf("") }
    var hasKey by remember { mutableStateOf(saved.hasApiKey) }
    var keyTail by remember {
        mutableStateOf(
            SecureKeyStore.load(context)
                ?.let { AiEndpoint.maskedKey(it).removePrefix("••••") }
                .orEmpty()
        )
    }
    var status by remember { mutableStateOf("") }
    var testing by remember { mutableStateOf(false) }
    var usage by remember { mutableStateOf(AiUsageStore.summary(context)) }

    fun refreshUsage() {
        usage = AiUsageStore.summary(context)
    }

    BackHandler(enabled = true) { onBack() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BACKGROUND)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) {
                Text(stringResource(R.string.settings_back), color = TEXT_SECONDARY)
            }
            Text(
                text = stringResource(R.string.settings_title),
                color = TEXT_PRIMARY,
                fontSize = 18.sp,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(start = 4.dp)
            )
        }

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(CARD, RoundedCornerShape(16.dp))
                .border(1.dp, LINE, RoundedCornerShape(16.dp))
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text(
                text = stringResource(R.string.ai_section),
                color = TEXT_PRIMARY,
                fontSize = 16.sp,
                fontWeight = FontWeight.SemiBold
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(stringResource(R.string.ai_enabled), color = TEXT_PRIMARY, fontSize = 15.sp)
                Switch(checked = enabled, onCheckedChange = { enabled = it })
            }
            Text(
                text = stringResource(R.string.ai_enabled_hint),
                color = TEXT_SECONDARY,
                fontSize = 12.sp
            )

            OutlinedTextField(
                value = baseUrl,
                onValueChange = { baseUrl = it },
                label = { Text(stringResource(R.string.ai_base_url)) },
                placeholder = { Text(stringResource(R.string.ai_base_url_hint), fontSize = 13.sp) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )

            OutlinedTextField(
                value = apiKeyInput,
                onValueChange = { apiKeyInput = it },
                label = { Text(stringResource(R.string.ai_api_key)) },
                placeholder = { Text(stringResource(R.string.ai_api_key_hint), fontSize = 13.sp) },
                visualTransformation = PasswordVisualTransformation(),
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
            Text(
                text = if (hasKey) {
                    stringResource(R.string.ai_key_saved, keyTail)
                } else {
                    stringResource(R.string.ai_key_missing)
                },
                color = TEXT_SECONDARY,
                fontSize = 12.sp
            )

            OutlinedTextField(
                value = model,
                onValueChange = { model = it },
                label = { Text(stringResource(R.string.ai_model)) },
                placeholder = { Text(stringResource(R.string.ai_model_hint), fontSize = 13.sp) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )

            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Button(
                    onClick = {
                        val typedKey = apiKeyInput.trim()
                        AiConfigStore.save(
                            context = context,
                            enabled = enabled,
                            baseUrl = baseUrl,
                            model = model,
                            apiKey = typedKey.ifEmpty { null }
                        )
                        if (typedKey.isNotEmpty()) {
                            apiKeyInput = ""
                            hasKey = true
                            keyTail = AiEndpoint.maskedKey(typedKey).removePrefix("••••")
                        }
                        hasKey = hasKey || AiConfigStore.load(context).hasApiKey
                        status = context.getString(
                            if (hasKey) R.string.ai_saved else R.string.ai_saved_need_key
                        )
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = BRAND)
                ) { Text(stringResource(R.string.ai_save)) }

                Button(
                    onClick = {
                        // 先保存当前输入，再按保存后的配置测试（测试不写学习记录、不改学习状态）
                        val typedKey = apiKeyInput.trim()
                        AiConfigStore.save(
                            context = context,
                            enabled = enabled,
                            baseUrl = baseUrl,
                            model = model,
                            apiKey = typedKey.ifEmpty { null }
                        )
                        if (typedKey.isNotEmpty()) {
                            apiKeyInput = ""
                            hasKey = true
                            keyTail = AiEndpoint.maskedKey(typedKey).removePrefix("••••")
                        }
                        testing = true
                        status = context.getString(R.string.ai_testing)
                        Thread {
                            val result = AiClient.testConnection(context)
                            handler.post {
                                testing = false
                                status = when (result) {
                                    is AiResult.Ok -> context.getString(R.string.ai_test_ok)
                                    // 连接测试走 chat()（自由文本），不会返回结构化结果；
                                    // 若将来改为 chatJson()，这里同样视为连接成功。
                                    is AiResult.OkJson -> context.getString(R.string.ai_test_ok)
                                    is AiResult.Failure -> "连接失败：" + result.message
                                    AiResult.Disabled -> context.getString(R.string.ai_test_disabled)
                                    AiResult.NotConfigured ->
                                        context.getString(R.string.ai_test_unconfigured)
                                }
                                refreshUsage()
                            }
                        }.start()
                    },
                    enabled = !testing,
                    colors = ButtonDefaults.buttonColors(containerColor = BRAND)
                ) { Text(stringResource(R.string.ai_test)) }

                TextButton(
                    onClick = {
                        AiConfigStore.deleteApiKey(context)
                        enabled = false
                        apiKeyInput = ""
                        hasKey = false
                        keyTail = ""
                        status = context.getString(R.string.ai_key_deleted)
                    }
                ) { Text(stringResource(R.string.ai_delete_key), color = TEXT_SECONDARY) }
            }

            if (status.isNotEmpty()) {
                Text(text = status, color = TEXT_SECONDARY, fontSize = 13.sp)
            }

            val (calls, prompt, completion) = usage
            Text(
                text = if (prompt > 0 || completion > 0) {
                    stringResource(R.string.ai_usage_tokens, calls, prompt, completion)
                } else {
                    stringResource(R.string.ai_usage, calls)
                },
                color = TEXT_SECONDARY,
                fontSize = 12.sp
            )
            Text(
                text = stringResource(R.string.ai_policy_note),
                color = TEXT_SECONDARY,
                fontSize = 12.sp
            )
        }
    }
}

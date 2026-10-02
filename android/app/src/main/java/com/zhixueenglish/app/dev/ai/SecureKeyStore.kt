package com.zhixueenglish.app.dev.ai

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * API Key 的安全存储：Android Keystore（AES/GCM）+ 密文落盘。
 *
 * 边界：
 *   * **明文 Key 永不写入 SharedPreferences、文件、日志**；磁盘上只有 iv + 密文；
 *   * 解密密钥由 Android Keystore 持有（不出设备），因此密文离开本机不可还原；
 *   * 删除 = 删除密文条目（Keystore 里的密钥保留，但无密文可解）；
 *   * 任何异常都退化为"没有 Key"，不抛异常、不影响教材学习功能。
 *
 * 不引入新依赖（不用 EncryptedSharedPreferences / security-crypto）。
 */
object SecureKeyStore {

    private const val KEYSTORE = "AndroidKeyStore"
    private const val KEY_ALIAS = "zhixue_ai_api_key_v1"
    private const val PREFS = "zhixue_ai_secret"
    private const val FIELD_CIPHER = "key_ct"
    private const val FIELD_IV = "key_iv"
    private const val TRANSFORMATION = "AES/GCM/NoPadding"
    private const val TAG_BITS = 128

    fun save(context: Context, apiKey: String) {
        val key = apiKey.trim()
        if (key.isEmpty()) {
            clear(context)
            return
        }
        try {
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.ENCRYPT_MODE, secretKey())
            val encrypted = cipher.doFinal(key.toByteArray(Charsets.UTF_8))
            prefs(context).edit()
                .putString(FIELD_CIPHER, Base64.encodeToString(encrypted, Base64.NO_WRAP))
                .putString(FIELD_IV, Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
                .apply()
        } catch (_: Exception) {
            // 存不下就当没配置：绝不退化成明文存储
            clear(context)
        }
    }

    fun load(context: Context): String? {
        val store = prefs(context)
        val cipherText = store.getString(FIELD_CIPHER, null) ?: return null
        val ivText = store.getString(FIELD_IV, null) ?: return null
        return try {
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(
                Cipher.DECRYPT_MODE,
                secretKey(),
                GCMParameterSpec(TAG_BITS, Base64.decode(ivText, Base64.NO_WRAP))
            )
            String(cipher.doFinal(Base64.decode(cipherText, Base64.NO_WRAP)), Charsets.UTF_8)
        } catch (_: Exception) {
            // 密钥被清除 / 密文损坏：按"没有 Key"处理
            null
        }
    }

    fun hasKey(context: Context): Boolean = load(context).orEmpty().isNotEmpty()

    fun clear(context: Context) {
        prefs(context).edit().remove(FIELD_CIPHER).remove(FIELD_IV).apply()
    }

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private fun secretKey(): SecretKey {
        val keyStore = KeyStore.getInstance(KEYSTORE).apply { load(null) }
        (keyStore.getEntry(KEY_ALIAS, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE)
        generator.init(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build()
        )
        return generator.generateKey()
    }
}

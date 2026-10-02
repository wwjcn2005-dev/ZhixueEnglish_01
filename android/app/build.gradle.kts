// P1-12-C3-C1：正式 Web UI 的 Android WebView 最小壳
// 说明：本工程只做一件事——用 WebView 打开本项目的正式 Web UI；
//       不含任何原生学习逻辑、不含原生数据库、不复制任何其它项目代码。
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

android {
    // namespace 必须保持 com.zhixueenglish.app.dev：MainActivity.kt 等源码文件的
    // package 声明与它绑定，且 AAR 内 ServiceZhixue 位于 .dev.runtime 子包
    // （LocalBackend.kt:23 按全限定名反射查找）。发布标识由 applicationId 决定。
    namespace = "com.zhixueenglish.app.dev"
    compileSdk {
        version = release(37)
    }

    // 正式签名：口令只从环境变量读，绝不写入仓库、绝不打印。
    // 注意：Gradle 守护进程会缓存启动时的环境变量——改过环境变量后必须先
    //       `gradlew --stop` 再构建，否则这里会读到 null。
    signingConfigs {
        create("release") {
            val storePass = System.getenv("ZHIXUE_KEYSTORE_PASS")
            val keyPass = System.getenv("ZHIXUE_KEY_PASS")
            if (storePass.isNullOrEmpty()) {
                throw GradleException(
                    "缺少签名口令环境变量 ZHIXUE_KEYSTORE_PASS（口令只从环境变量读取）。" +
                    "请先设置该变量，并执行 `gradlew --stop` 重启 Gradle 守护进程后重试。")
            }
            // 本项目 keystore 为 PKCS12（单口令格式）：若同时提供了 ZHIXUE_KEY_PASS，
            // 它必须与密钥库口令一致，否则签名会失败——这里主动拦截，不静默通过。
            if (!keyPass.isNullOrEmpty() && keyPass != storePass) {
                throw GradleException(
                    "ZHIXUE_KEY_PASS 与 ZHIXUE_KEYSTORE_PASS 不一致。" +
                    "PKCS12 密钥库不支持与密钥库口令不同的密钥口令，请将两者设为同一值。")
            }
            storeFile = file("../keystore/zhixue.jks")
            storePassword = storePass
            keyAlias = "zhixue"
            keyPassword = storePass
        }
    }

    defaultConfig {
        applicationId = "com.zhixueenglish.app"
        minSdk = 24
        targetSdk = 37
        versionCode = 2
        versionName = "0.1.0"

        // 正式 Web UI 地址：唯一配置点（可在 gradle.properties 覆盖）
        val webBaseUrl = (project.findProperty("zhixue.webBaseUrl") as String?)
            ?: "http://127.0.0.1:8770/"
        buildConfigField("String", "WEB_BASE_URL", "\"$webBaseUrl\"")
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
            optimization {
                enable = false
            }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    // p4a service_library：libpybundle.so 需要按传统方式打包，运行期才能被解包
    packaging {
        jniLibs {
            useLegacyPackaging = true
        }
    }
}

dependencies {
    // Android 本地 Python 运行时（沿用《智学小四门》已验证路线：p4a service_library AAR）
    implementation(files("libs/zhixueenglish_backend_runtime.aar"))
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)

    // 只用于纯逻辑单元测试（URL 组装 / Key 掩码），不引入新的运行时依赖
    testImplementation(libs.junit)
}

# Android 本地 Python Web 服务（智学英语 · 第一阶段）

本目录把**现有正式 Python Web 服务**打包成 Android APK 内部的本地服务。

路线复用《智学小四门》已验证实现，**不重新探索架构**：

```text
Android APK
  → runtime AAR（p4a service_library：CPython 3.14 + libpybundle + private.tar）
  → ServiceZhixue.prepare() / start()
  → 载荷解包到 filesDir/app
  → service/main.py
  → 现有 web/app.py（127.0.0.1:8770）
  → WebView（下一阶段切到 127.0.0.1）
```

## 目录

| 路径 | 说明 |
| --- | --- |
| `stage_payload.py` | 从项目复制**运行时最小集合**到 `app/` |
| `app/` | 载荷（web/ learning/ structured/ service/），由 p4a 打进 AAR |
| `service/main.py` | p4a 服务入口：调用现有 `web/app.py` 的 `main()` |
| `p4a_package_aar.sh` | WSL 中的 p4a 预处理（复用已验证 dist，不重编 CPython） |
| `dist_aar/` | p4a 工作副本（预处理产物：private.tar / libs / 生成 Java） |
| `assemble_aar.py` | 离线组装 `app/libs/zhixueenglish_backend_runtime.aar` |
| `app/libs/zhixueenglish_backend_runtime.aar` | Android 工程引用的运行时 AAR |

## 载荷内容（运行所需，最小集合）

```text
web/*.py（不含 test_*.py）          现有正式 Web 服务
learning/*.py（不含 test_*.py）     现有学习服务 / 证据 / 掌握 / 资源池
structured/contentpack/v5          教材内容库（只读）
structured/learning                正式学习库 + 数据模型 JSON
structured/exercises               教材练习目录
structured/textbook                教材结构/关系数据
structured/ai/textbook_evidence_map_v1.json
structured/audio/*.json            音频清单（MP3/WAV 本阶段未打包）
service/main.py                    服务入口
```

**未进入载荷**：教材 PDF、官方 MP3、派生 WAV、`demo/`、`docs/`、测试与构建脚本、正式库的备份文件。

## 路径适配（唯一的业务代码改动）

现有 `web/` 与 `learning/` 用 `BASE = Path(r"D:\ZhixueEnglish")` 解析项目根。
Android 上路径不同，因此统一改为：

```python
BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
```

Windows 上不设 `ZX_ROOT` 时行为与改动前完全一致；Android 上由 `service/main.py` 设置
`ZX_ROOT=<载荷根>`。未改动任何业务逻辑、Schema、教材数据与 AI 规则。

## 重新生成 AAR

```bat
:: 1) Windows：更新载荷
python J:\ZhixueEnglish_01\android\python_runtime\stage_payload.py

:: 2) WSL：p4a 预处理（复用已验证 dist）
wsl -e bash -lc "sh /mnt/j/ZhixueEnglish_01/android/python_runtime/p4a_package_aar.sh"

:: 3) Windows：组装 AAR（离线）
python J:\ZhixueEnglish_01\android\python_runtime\assemble_aar.py

:: 4) Windows：构建 APK
cd J:\ZhixueEnglish_01\android && gradlew.bat --offline :app:testDebugUnitTest :app:assembleDebug
```

> 说明：p4a dist 的 Gradle wrapper 固定 `gradle-8.14.3` 且需要联网下载发行包；
> 为满足"离线可复现"，第 3 步用与 Gradle 等价的结构组装 AAR
> （`AndroidManifest.xml` + `classes.jar` + `jni/arm64-v8a/*.so` + `assets/private.tar` + `res/`），
> 与《智学小四门》已验证 AAR 同构。

## 边界

* 不改产品/UI/AI 规则；不改 `learning.db` schema；不重解析教材；不删原始资源；
* 服务只监听 `127.0.0.1`，不暴露局域网；
* API Key 只存在 Android Native（Keystore），**不进载荷、不进 WebView**；
* 本阶段 WebView 仍按 `BuildConfig.WEB_BASE_URL` 访问，切换 `127.0.0.1` 属下一阶段。

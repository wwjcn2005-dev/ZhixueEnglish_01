# 智学英语（ZhixueEnglish）项目现状梳理报告

> 本文件由一次**只读全量扫描**生成，用于回答三个问题：**完成了什么、用了什么技术栈、代码结构怎样**。
> 扫描过程未修改任何既有文件；本文件是本次扫描唯一新增的文件。
>
> 扫描时间：本次会话 · 扫描根目录：`J:\ZhixueEnglish_01`
> 注意：项目文档内部仍普遍使用 `D:\ZhixueEnglish` 作为路径常量与说明基准（如 `web/*.py` 的 `BASE` 默认值、
> `demo/README.md` 的启动命令）。**当前实际项目根是 `J:\ZhixueEnglish_01`**，两者不一致且**存在真实风险**，
> 详见 §7 缺口表 C2。

---

## 0. 扫描范围与方法

| 项 | 说明 |
| --- | --- |
| 扫描范围 | 项目根下全部目录，**排除**构建产物与第三方运行时（`temp/`、`android/app/build/`、`android/python_runtime/dist_aar/`、`android/python_runtime/.aar_work/`、`android/.gradle|.kotlin|.idea/`、`tools/faster_whisper_venv/`、`__pycache__/`） |
| 代码规模 | 业务源码约 **520 个文件**（其中 `web/` 36、`learning/` 30、`demo/` 26、`builder/` 22、`parser/` 2、`workbench/` 3）；另含 `audit/` 691 个过程产物文件、`android/` 1066 个文件（含 851 MB 构建/打包产物） |
| 数据规模 | `structured/` 329 个文件 / 53.2 MB（含 4 个 SQLite 库、4 类 JSON 数据层） |
| 原始素材 | 教材 PDF 1 份（117.34 MB）、官方 MP3 54 份（111.8 MB，编号 01–54）、派生单词 WAV 288 份（20.4 MB） |
| 方法 | 目录枚举 + 逐一读取源码/配置/Schema + 只读 SQL 查询（`mode=ro`）+ 若干 subagent 并行细读 |

### 扫描中发现的目录异常（事实报告，未做任何修改）

项目根存在一个**目录项名称损坏**的条目，其名称字符全部为 `U+FFFD`（替换字符）：

```
Name(dir): FDFF FDFF FDFF FDFF FDFF   ← 5 个 U+FFFD
```

影响范围：**任何以项目根为起点的递归遍历都会因此报 Win32 错误**
（`Get-ChildItem -Recurse` / `New-Object DirectoryInfo -Recurse` 均失败，
错误：`SetNamedSecurityInfoW failed (Win32 5)` 或 `The system cannot find the file specified`，
`CategoryInfo: NotSpecified`）。本次扫描通过**逐个顶层目录分别枚举**绕过该问题，不影响结论。

建议（不在本次任务范围内，仅记录）：由项目方确认该条目来源后清理。

---

## 1. 项目是什么

**单教材 · 七年级英语上册（外研版 2022 课标修订版）** 的 AI 辅助学习系统。
产品形态是「**本地 Python 服务 + WebView 界面 + Android 壳**」，不是原生 Android 应用，
也不是云端 SaaS——所有教材数据、学习数据、音频都在本机。

最高原则（贯穿全部设计文档与代码注释）：

> **教材是主线，学习是核心，孩子做主，AI 做助手。**

系统由**四层**组成，四层均已有可运行实现：

```
① 教材事实层  contentpack v5（SQLite） + 教材 PDF + 官方 MP3 + 派生词音频
② 学习服务层  learning/*.py（14 个 service，含冻结的 study_call_service）
③ 界面层      web/app.py（正式 Web，stdlib HTTP，端口 8770）
              demo/server.py（全功能交互 Demo，stdlib HTTP，端口 8780）
④ 承载层      android/（Compose + WebView 壳 + 内嵌 CPython 3.14 runtime AAR）
```

**关键架构事实**：`android/` 侧内嵌的 Python 服务运行的是 **正式 Web `web/app.py`（127.0.0.1:8770）**，
入口为 `android/python_runtime/service/main.py`（208 行）；`demo/**` **已被明确排除出正式载荷**
（`stage_payload.py:30` 注释："历史 Demo 不是正式产品基线"）。
但 `android/gradle.properties` 中仍写着 `zhixue.webBaseUrl=http://127.0.0.1:8780/`（Demo 端口），
与代码实际启动的 8770 不一致——这是**当前 APK 的一个真实配置矛盾**（详见 §7-9）。

---

## 2. 技术栈

### 2.1 后端（Python）

| 项 | 事实 |
| --- | --- |
| 语言 / 版本 | Python 3（`from __future__ import annotations` 广泛使用） |
| Web 框架 | **无框架**。`http.server.ThreadingHTTPServer` + `BaseHTTPRequestHandler` 手写路由（`web/app.py:31`、`web/app.py:1368 main()`） |
| 第三方依赖 | **零**。正式 `web/` 与 `learning/` 全部只用标准库（`sqlite3`、`json`、`urllib`、`hashlib`、`http.server`、`pathlib`） |
| 依赖例外 | `web/pdf_pages.py` 使用 **PyMuPDF** 现场渲染教材 PDF 页面（模块注释声明为"项目已安装"） |
| 数据库 | SQLite 4 个库（见 §4），一律以 `file:...?mode=ro` **只读**连接正式数据 |
| 路径常量 | `BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")` —— Android 侧通过 `ZX_ROOT` 环境变量重定向载荷根 |
| 写库边界 | 正式写入口只有 `learning/learning_service.record_learning_event`；`web/` 层不直接 INSERT |

### 2.2 前端

| 项 | 事实 |
| --- | --- |
| 模板引擎 | **无**（不用 Jinja2）。全部 HTML 由 Python f-string / `%` 拼接生成 |
| 主要 UI 模块 | `web/ui.py`（156 KB，全项目最大单体文件），输出所有页面的 HTML 字符串 |
| 样式 | **内联 `<style>`**：`ui.STYLE`（`ui.py:72`）+ `ui.FORMAL_UI_CSS`（`ui.py:635`），无 CSS 预处理器、无构建步骤 |
| 脚本 | 内联 `<script>` 常量：`HOME_PICKER_SCRIPT`、`READ_JS`、`_TEXT_AUDIO_JS`、`PLAYER_JS`、`RECORD_JS` |
| 图标 | 内联 SVG path 字典 `ui._ICON_PATHS`（`ui.py:33`） |
| 视觉基线 | 背景 `#F6F7F9`、卡片 `#FFFFFF`、主文字 `#17181A`、次文字 `#6B7078`、分割线 `#E7E9ED`、交互蓝 `#1677FF`、AI 蓝 `#00A8E8` |
| 状态存储 | **浏览器 Cookie**（`zx_demo`、`zx_wrong`、`zx_lesson`、`zx_demo10` 等），非服务端会话 |

### 2.3 Android

| 项 | 事实 |
| --- | --- |
| 构建 | Gradle **9.5.0**（wrapper，`gradle-wrapper.properties`）+ Kotlin DSL（`*.gradle.kts`） |
| AGP / Kotlin | **AGP 9.3.2** / **Kotlin 2.2.10** / **Compose BOM 2026.02.01**（`android/gradle/libs.versions.toml`）；`compileSdk = release(37)`、`minSdk = 24`、`targetSdk = 37` |
| 其它依赖版本 | core-ktx 1.10.1、lifecycle-runtime-ktx 2.6.1、activity-compose 1.8.0、JUnit 4.13.2 |
| 语言 | Kotlin，**Jetpack Compose**（`buildFeatures.compose = true`） |
| 关键依赖 | `libs/zhixueenglish_backend_runtime.aar`（本地 138 MB AAR）、androidx compose BOM / material3 / activity-compose / core-ktx / lifecycle-runtime-ktx |
| 包名 | `com.zhixueenglish.app.dev`（注释明确标注 dev，非最终商业包名） |
| 版本 | `versionCode = 1`、`versionName = "0.1-dev"` |
| 布局 | **无 XML 布局**（`res/` 下只有 `drawable/ic_settings.xml`、`values/strings.xml`、`values/themes.xml`）—— UI 100% 由 Compose 构图，`MainActivity.kt` 519 行 |
| 权限 | `INTERNET`、`RECORD_AUDIO`；debug 构建额外 `usesCleartextTraffic="true"` |
| 内嵌运行时 | python-for-android **service_library AAR**：CPython **3.14** + `libpybundle.so` + `private.tar` 载荷 |
| 打包策略 | `packaging { jniLibs { useLegacyPackaging = true } }`（p4a 运行期解包需要） |

### 2.4 机器学习 / 音频工具链（离线产物生成，非运行时依赖）

| 项 | 事实 |
| --- | --- |
| ASR | **faster-whisper 1.2.1** + CTranslate2 4.8.2（`tools/faster_whisper_venv/`，Windows 独立 venv） |
| Whisper 模型 | `Systran/faster-whisper-small`（`models/whisper/`，HuggingFace 缓存布局） |
| HF 缓存 | `models/hf/xet/`（huggingface_hub 1.31.0 + hf_xet 1.6.0） |
| 模型目录总大小 | **463.7 MB / 9 个文件**（whisper + xet 缓存） |
| 音频处理 | PyAV 18.1.0、numpy 2.5.3、onnxruntime 1.30.0（仅在生成派生词音频/ASR 时使用） |
| 转换脚本 | `builder/mp3_to_wav.ps1`（官方 MP3 → 派生 WAV） |

### 2.5 AI

| 项 | 事实 |
| --- | --- |
| 运行时真实 AI 调用 | **0 次**。`demo/README.md` 明确"AI 调用 = 0：没有任何 API、SDK、Key、网络 AI 请求" |
| Android 原生 AI 配置 | **已实现且可编译**：开关 / Base URL / Model / 连接测试 / usage 统计 / Key 删除 |
| 协议 | 兼容 OpenAI Chat Completions：`POST {BaseURL}/chat/completions`（`ai/AiEndpoint.kt`） |
| Key 安全 | Android Keystore（AES/GCM）+ 密文落盘（`ai/SecureKeyStore.kt`）；明文 Key **不进** SharedPreferences / HTML / JS / WebView / 日志 |
| 离线 AI 资产 | `structured/ai/question_library.db`（AI 生成题库，21 题）、`textbook_evidence_map_v1.json`（360 个证据包）、`demo/ai_cache/`（8 批 Spike 缓存） |

---

## 3. 已完成的功能

### 3.1 教材目录与学习上下文（已落地）

- 教材正式层级 **教材 → Unit → Section**，数据源为 `contentpack.section`：
  **8 个 Unit / 46 个 Section**（Starter 4、Unit 1–6 各 6、Appendix 6）。
- 首页「当前课时」选择器 = **Unit 分组 + Section 可选项**，是唯一正式的 Section 选择入口。
- Section 目录与题库/资源可用性**解耦**：目录保留全部 46 个 Section，不按题目数量删减。
- `section_key` 是 Section 的稳定业务标识（代码中的 `lesson_key` / `?lesson=` / Cookie `zx_lesson`
  保存的实际就是 `section_key`，属历史命名）。
- 64 个 section_key 值共 17 种：`STARTING_OUT`、`UNDERSTANDING_IDEAS`、`DEVELOPING_IDEAS`、
  `READING_FOR_WRITING`、`PRESENTING_IDEAS`、`REFLECTION`、`GET_READY`、`KNOW_YOUR_SCHOOL`、
  `GET_TO_KNOW_EACH_OTHER`、`MAKE_A_WISHING_TREE`、`VOCABULARY`、`WORDS_AND_EXPRESSIONS`、
  `COMMUNICATION_BANK`、`PRONUNCIATION_GUIDE`、`GUIDE_TO_THE_LANGUAGE_USE`、`PROPER_NOUNS` 等。

### 3.2 六个正式学习入口（首页固定顺序，均已实现）

`web/app.py:479 P5_ENTRY_LABELS` 与 `web/ui.py` 的 P5 页面族是唯一题目来源。

| # | 入口 | 实现位置 | 现状 |
| --- | --- | --- | --- |
| 1 | 跟读练习 `read` | `_p5_page` + `ui._p5_read_page` | 单词跟读（全 Unit 词表）+ 短句跟读（Section 级 shadowing 池） |
| 2 | 听音辨意 `listen` | `scs.select_questions(entry, unit, learner, mode=...)` | **一条入口、三个内部模式**：单词听辨 / 句子听辨 / 听音阅读；模式标签只显示当前 Section 有资源的模式 |
| 3 | 音标写词 `phonetic` | `P5_VOCAB_TYPES` 中的 `vocab_phonetic_write` / `phonetics_symbol_write` | 音标 → 输入英文 |
| 4 | 词形变化 `form` | `vocab_word_form`（Unit 级资源） | 教材正文出现过的词形 → 输入 + 讲解 |
| 5 | 本课检测 `check` | `_p5_items` 严格 `section_key == 当前 Section` | 当前 Section 综合检测（含阅读选择 / 阅读简答） |
| 6 | 自主练习 `practice` | `scs.learned_sections()` 过滤 | **跨 Section / 跨 Unit**：候选池 = 已产生有效学习证据的 Section 集合；当前 Section 不是额外过滤条件 |

已删除项：**「听音写词」已不是独立入口**（见 `docs/智学英语_Android独立运行与APK本地化实施基线_V1.0.md:274`）。

### 3.3 学习闭环与学习数据（已实现并被测试覆盖）

```
进入 → 学习/练习 → 产生学习证据 → 结果 → AI 分析/评价 → 下一步建议 → 孩子决定是否继续
```

已实现的机制：Session / Task / TaskItem / LearningRecord / MasteryState
（`learning.db` 7 张表）→ 有效证据判定（`evidence_service`）→ 掌握判定（`mastery_service`）→
诊断（`diagnosis_service`）→ 当前错误/薄弱池（`resource_pool_service`）→ 建议（`intervention_service`）。

### 3.4 教材资源与音频层（已建成）

| 资源 | 数量 | 状态 |
| --- | --- | --- |
| 官方 MP3 | 54 份 / 111.8 MB | 资产清单化，可 Range 流式播放（HTTP 200 / 206 / 416） |
| 派生单词 WAV | 288 份 / 20.4 MB | 按 Unit 分目录（starter 32、unit1 35、unit2 45、unit3 40、unit4 45、unit5 46、unit6 45） |
| 句级 VERIFIED 时间轴 | 12 条（`audio_sentence_annotation`，另 3 条 REJECTED） | 人工核验 |
| 跟读资源池 | 72 entries（`shadowing_pool_v1.json`） | 正式 P5/P8 跟读链路 |
| 音频资源层 | 54 条（`audio_resource_v1.json`，含 readiness 分级） | 只读服务层已验收 |
| 句子听辨素材 | 38 条唯一句子（覆盖 13 个 MP3） | 由三处既有资产去重合成 |

`/audio/official/<AUxx>.mp3` 与 `/audio/word/<key>.wav` 只解析**清单/数据库里登记过**的音频，
不受 URL 控制文件路径（`web/app.py:104 _audio()`）。

### 3.5 页面（已实现）

`web/ui.py` 渲染约 25 个页面：`home_page`、`textbook_page`、`resource_types_page`、
`resource_list_page`、`exercise_list_page`、`exercise_page`、`exercise_result_page`、
`unit_text_page`、`progress_page`、`study_page`、`recall_page`、`result_page`、`review_page`、
`p5_page`、`p5_result_page`、`_p5_empty_page`、`error_page`、`not_found_page` 等。

### 3.6 Android 独立运行（已打通到可安装 APK）

- **Debug APK 已成功构建**：`android/app/build/outputs/apk/debug/app-debug.apk`，
  **272,202,175 字节 = 259.59 MiB**，构建时间 2026-09-20 17:29。
  工程**可原样构建**（`gradle-wrapper.jar`、`G:\AndroidSDK`（含 `android-33` / `android-37.0`）、
  JDK 25 均在位；`local.properties:8 sdk.dir=G:\AndroidSDK`）。
- **内嵌方式不是 Chaquopy**，是**自定义 p4a `service_library` AAR + 反射调用**：
  `app/build.gradle.kts:54 implementation(files("libs/zhixueenglish_backend_runtime.aar"))`，
  AAR 自身 manifest 声明 `<service android:name="...runtime.ServiceZhixue"
  android:process=":service_zhixue" android:exported="true"/>`
  （合并结果见 `app/build/outputs/logs/manifest-merger-debug-report.txt:269`）。
  AAR 内含 `classes.jar`、`assets/private.tar`（122.57 MB）、
  `jni/arm64-v8a/{libpython3.14,libpybundle,libmain,libsqlite3,libssl,libcrypto,libffi,libpythonbin}.so`。
- 本地服务启动链路（`MainActivity.kt` + `runtime/LocalBackend.kt`）：
  `AAR Class.forName → ServiceZhixue.prepare() + start() → 载荷解包到 filesDir → service/main.py
  → 播种 state DB → web/app.py main() → 轮询 /health 200 → Compose 切换到 WebView`。
  **以真实 `/health` 返回 200 作为就绪判据**，不做"延时后假设成功"。
- 学习数据在 Android 上做了 **seed / state 分离**（`service/main.py`，P6-B-2C）：
  载荷内只有只读 `learning.clean-seed.db`，运行时库在 `<files>/state/learning.db`；
  仅在 state 不存在时播种一次，播种后做只读校验（`user_version` / `schema_migration` / `learner` /
  `integrity_check` / `foreign_key_check`），任一不通过即显式失败并回滚，**绝不让 sqlite3 静默建空库**。
- 官方 MP3 以短名 `official_audio.zip`（117 MB）随载荷分发，首次启动后台线程解包
  （原始文件名最长 148 B，进不了 p4a 的 ustar tar）。
- 已处理的真机问题（代码内有明确记录）：WebView 中 `100vh/100dvh/100svh` 全为 0 导致白屏
  → `VIEWPORT_HEIGHT_FIX_JS` 用 `window.innerHeight` 像素覆盖 `html/body` 高度；
  首次加载延后到视图完成测量之后。
- 已处理的健壮性：前台恢复探活 + 自动重启（`ensureRunning`）、渲染进程被回收（`onRenderProcessGone`）、
  启动失败显式原因 + 重试。
- 录音权限：只放行 `RESOURCE_AUDIO_CAPTURE`，其它 Web 权限一律 `req.deny()`。
- 设置入口只出现在首页（`isHomeUrl()` 判定），学习页不显示。

### 3.7 全功能 Demo（PC 端，作为产品形态验证）

`demo/server.py`（111 KB）+ `demo/pages.py`（101 KB）实现了与正式 Web 平行的一套完整交互演示：
首页 / Unit 页 / 单词跟读 / 听音辨意（单词·句子）/ 听音阅读 / 本课检测 + 错题闭环 / 短句跟读 /
课文简答 / AI 随堂助教 / 自主练习（专项·巩固）/ 学习结果。

---

## 4. 数据资产清单（只读核实，精确数字）

### 4.1 `structured/contentpack/v5/FLTRP-EN-7A-2022CUR.sqlite`（2.72 MB）—— 教材事实权威

| 表 | 行数 | 表 | 行数 |
| --- | ---: | --- | ---: |
| `content_block` | 3854 | `source_ref` | 976 |
| `content_asset` | 628 | `page` | 178 |
| `learning_item` | 520 | `activity` | 96 |
| `source_artifact` | 55 | `audio_asset` | 54 |
| `audio_mapping` | 59（CANDIDATE 31 / MATCHED 28） | `section` | **46** |
| `unit` | **8** | `activity_content` | 31 |
| `learning_goal` | 6 | `import_batch` | 7 |
| `import_batch_stage` | 20 | `sub_question` | 13 |
| `audio_sentence_annotation` | **15**（VERIFIED 12 / REJECTED 3，origin 全 HUMAN） | `evidence` | 351 |
| `parse_snapshot` | 5（唯一 active = `…S20260912T151307`，parser `v01-P1-03-C`） | `textbook_edition` | 1 |
| `ai_artifact` / `audio_token_annotation` / `transcript` | 0 | | |

`learning_item` 按类型：**vocabulary 288 / exercise 157 / sentence_pattern 52 / phrase 23**
（`review_status`：OK 353 / NEED_REVIEW 166 / AUTO_OK 1）。
`content_block.block_kind`：exercise_item 2133 / vocabulary_entry 525 / sidebar_tip 348 /
heading 344 / instruction 194 / footer_text 178 / dialogue 132。

**46 个 Section 的真实构成**：Appendix 6（`COMMUNICATION_BANK`、`GUIDE_TO_THE_LANGUAGE_USE`、
`WORDS_AND_EXPRESSIONS`、`PROPER_NOUNS`、`VOCABULARY`、`PRONUNCIATION_GUIDE`）+
Starter 4（`GET_READY`、`KNOW_YOUR_SCHOOL`、`GET_TO_KNOW_EACH_OTHER`、`MAKE_A_WISHING_TREE`）+
Unit 1–6 各 6（`STARTING_OUT`、`UNDERSTANDING_IDEAS`、`DEVELOPING_IDEAS`、`READING_FOR_WRITING`、
`PRESENTING_IDEAS`、`REFLECTION`）。

#### contentpack 版本演进（v1 → v5，目录内无 README，差异由 schema + 行数 + `parse_snapshot` 推出）

| 表 / 属性 | v1 | v2 | v3 | v4 | v5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `unit` / `section` / `activity` / `page` | 8/46/96/178 | 同 | 同 | 同 | 同 |
| `content_block` / `content_asset` / `evidence` | 3854/628/351 | 同 | 同 | 同 | 同 |
| `learning_item` | **0** | 287 | 287 | 310 | **520** |
| `source_ref` | 6 | 714 | 714 | 762 | **976** |
| `audio_mapping` | 54 | 54 | 54 | 54 | **59** |
| `parse_snapshot` / `import_batch` | 1 / 1 | 2 / 2 | 3 / 3 | 4 / 4 | **5 / 7** |
| `audio_sentence_annotation` | – | – | – | – | **15** |
| 文件大小 | 1.84 MB | 2.21 MB | 2.37 MB | 2.40 MB | **2.72 MB** |

Schema 变化：v2 给 `learning_item` 增加 `canonical_text / display_text / schema_version /
content_hash / created_at / updated_at`；v3 再加 `learning_requirement`（CORE 判据）与
`requirement_conflict_status`，并给 `source_ref` 加 `textbook_emphasis / emphasis_source_list /
emphasis_evidence`；v4 仅数据；v5 新增 `audio_sentence_annotation`、`audio_token_annotation` 两表。
`structured/staging/` 保存 v1、v2 的阶段快照；v5 另有 3 个 `.bak-P2-1-C1 / .bak-P2-2 / .bak-P2-3` 备份。

### 4.2 `structured/questionbank/questionbank.db`（3.00 MB）—— 正式题库

| 表 | 行数 |
| --- | ---: |
| `question` | **1831** |
| `question_asset` | 6489 |
| `supplement_task` | 52 |
| `quality_review` | 7 |
| `generation_run` | 6 |

按题型：`textbook_native` 517、`vocab_listen_write` 288、`vocab_meaning_choice` 288、
`vocab_phonetic_write` 265、`sentence_listen_write` 105、`vocab_context_choice` 104、
`vocab_word_form` 79、`sentence_listen_choice` 38、`listening_choice` 33、`phrase_meaning_choice` 33、
`reading_choice` 33、`phonetics_sound_choice` 16、`phonetics_symbol_write` 16、
`listen_choice` 12、`listen_fill` 4。

按 Unit：Unit 5 = 288、Unit 6 = 276、Unit 3 = 275、Unit 4 = 266、Unit 2 = 259、Unit 1 = 249、
Starter = 218，**Appendix = 0**。

其它维度：`domain`（vocabulary 1057 / textbook 517 / listening 192 / reading 33 / phonetics 32）；
`origin`（PROGRAM_GENERATED 1211 / TEXTBOOK_NATIVE 517 / AI_GENERATED 103）；
`review_status`（AUTO_ACCEPTED 1314 / PENDING_REVIEW 517）；`answer_kind`（normalized 678 /
option_key 557 / self_assess 276 / ai_eval 241 / exact 79）；`quality_status` 全 PASS。
`generation_run` 6 条全部 PASS（`RUN-DETERMINISTIC-V1` … `RUN-P7-VALUE-V1`，rules v1→v4）。
`supplement_task` 52 条**全部是 `AI_SUPPLEMENT_REQUIRED`**（`listening_understanding` 21、
`sentence_distractors` 21、`phonetics_text` 6，其余各 1）——即"待 AI 补足"的明确工单。

> ⚠️ **两个关键缺口**
> 1. `question.section_key` 只覆盖 **10 个不同 section_key**（教材有 46 个 Section）——
>    直接决定「本课检测」在多数 Section 的空状态。
> 2. **`PENDING_REVIEW` / `NO_RELIABLE_SOURCE` 恒为 517**，恰好等于 `textbook_native` 的题数：
>    全部教材原生题尚无可靠答案来源。

### 4.3 `structured/learning/learning.db`（124 KB）—— 正式学习数据

| 表 | 行数 | 关键列 |
| --- | ---: | --- |
| `learner` | 1 | learner_id, display_name, status |
| `learning_session` | 38 | session_id, learner_id, entry_point, task_id |
| `learning_task` | 38 | task_id, task_kind, status, textbook_id |
| `task_item` | 38 | task_id, item_id, ordinal |
| `learning_record` | **26** | record_id, activity_type, result, response_raw, attempt_no |
| `mastery_state` | 7 | learner_id, item_id, mastery_level, evidence_count, correct_count, review_needed |
| `schema_migration` | 2 | — |

配套：`init_learning_db.py`（`SCHEMA_VERSION=1`，幂等）、`migrate_learning_db_v2.py`（只新增
`learning_session` + 1 索引，事务内完成并回滚保护）、`learning.clean-seed.db`（同 schema，
**7 张业务表全 0 行**的干净种子）、`learning.db.bak-v1`（迁移前备份，无 `learning_session`，
`schema_migration` 仅 1 行）。

> 实测语义：`learning_record.activity_type` **全部是 `'study'`**（尚无 practice/judge 类证据）、
> `learning_session.entry_point` **全部是 `'vocabulary'`**、`mastery_state` 7 条
> **`mastery_level` 全部为 `'unknown'`** —— 也就是说**正式库中还没有产生任何 stable 掌握状态**，
> 学习闭环的"下游"（诊断/干预/资源池）在正式数据上目前基本没有可消费的证据量。

### 4.4 `structured/ai/question_library.db`（176 KB）—— AI 生成题库

`ai_question` 21、`question_validation` 21、`question_evidence` 22、`question_learning_object` 37、
`question_event` 44、`generation_run` 13。

### 4.5 JSON 数据层（`structured/`）

| 文件 | 大小 | 内容 |
| --- | ---: | --- |
| `textbook/textbook_context_relations_v2.json` | 1.03 MB | 4220 条上下文关系（17 种 relation_type） |
| `textbook/textbook_visual_relations_v2.json` | 1.43 MB | 2949 个版面对象 |
| `textbook/textbook_content_relations_v2.json` | 484 KB | vocabulary_in 485 / grammar_in 13 / text_references 875 |
| `textbook/textbook_structure_v2.json` | 106 KB | 8 个 Unit 的教材结构 |
| `exercises/exercise_catalog_v4.json` | 499 KB | 157 个教材练习 + 157 个 activity + recovery_run |
| `exercises/exercise_question_relations_v3.json` | 670 KB | 360 条练习↔题目关系 |
| `exercises/exercise_catalog.json` v1 | 92 KB | 93 个练习（历史版本，v2/v3/v4 依次演进） |
| `audio/resources/audio_resource_v1.json` | 768 KB | 54 条音频资源；`alignment_status` VERIFIED 47 / NEED_MANUAL_CONFIRMATION 6 / PARTIAL 1；`readiness` READY_DETERMINISTIC 47 / NEEDS_TEXT_RELATION 6 / READY_WITH_PROGRAM_PROCESSING 1；`segments` 合计 **800**；`ai_calls`=0 |
| `audio/resources/shadowing_pool_v1.json` | 62 KB | 72 条跟读 entry（VERIFIED 69 + STATIC_CONFIRMED 3）；**按 Unit 分布极不均**：Starter 7 / U1 6 / **U2 = 0** / U3 25 / U4 2 / U5 15 / U6 17；未纳入：borderline 19 / excluded 89 / partial_sentence_segments 263 |
| `audio/derived/word_audio_manifest.json` | 206 KB | 288 个逐词切片（7 Unit：32/35/45/40/45/46/45）；方法 = 官方整单元词表 MP3 + 离线静音切分（hop 10ms、阈值 −45 dB、min_speech 140 ms、min_gap 200 ms）；未改 MP3/contentpack/learning.db，AI=0 |
| `audio/exercise_audio_map_v3.json` | 87 KB | 54 条练习↔音频映射 |
| `audio/audio_question_relations_v3.json` | 50 KB | 121 条音频↔题目关系 |
| `ai/textbook_evidence_map_v1.json` | 1.48 MB | 360 个证据包 |
| `learning/*_model_v1.json`（8 个） | 2–8 KB 各 | 学习/证据/掌握/干预/AI 角色/阶段测评的**规则模型**（声明式，非代码） |

### 4.6 原始素材

| 路径 | 内容 |
| --- | --- |
| `2025年度初一外研版英语教材/` | 教材 PDF ×1（117.3 MB）、官方 MP3 ×54（111.8 MB） |
| `structured/audio/derived/words/` | 派生单词 WAV ×288（20.4 MB）+ `word_audio_manifest.json`（206 KB） |
| `models/` | faster-whisper-small + HF xet 缓存（463.7 MB / 9 文件） |
| `audit/P3-07_preview/asr/` | 47 份词级 ASR 结果（句级时间轴的事实依据） |

### 4.7 数据层的两条总体原则（由代码实测得出）

**① 四库分离，跨库仅逻辑引用、无跨库外键：**

```
contentpack v5  （教材事实，只读权威）
      ↓ 引用
questionbank.db （正式题目，1831 题；引用 contentpack 的 block/item/audio/activity/section）
      ↓ 选题作答
learning.db     （学习证据：session / task / task_item / record / mastery）
      ↓ 生命周期
ai/question_library.db （AI 生成题的独立生命周期：GENERATED→VALIDATED→APPROVED→ACTIVE/REJECTED）
```

**② 写入只有一个入口，其上全是 SELECT-only 派生层：**

```
learning_service.record_learning_event()          ← 唯一写入口（唯一事务）
  → evidence_service      （有效证据判定）
  → mastery_service       （掌握判定，参数来自 mastery_rules_v1.json）
  → diagnosis_service     （诊断分档）
  → intervention_service  （教材优先建议，只给建议不执行）
  → learning_object_service（LO 派生）
  → resource_pool_service （当前错误 / 当前薄弱池，只读）
全部零 AI、零联网。
```

`mastery_rules_v1.json`（2.6 KB）是**唯一被服务读取的规则参数源**，其余
`learning_model_v1` / `learning_flow_v1` / `learning_evidence_model_v1` / `ai_role_model_v1` /
`intervention_model_v1` / `stage_assessment_model_v1` 是**声明式 JSON 契约**（设计模型，非运行数据）。

#### 代码中明确标注为「冻结」的边界（改动前务必核对）

| 冻结内容 | 标注位置 |
| --- | --- |
| `learning.db` schema（B1.12 冻结） | `learning_service.py:5`、`schema_migration` 表内描述 |
| 9 种学习行为（B1.15 冻结，不增删、不改语义） | `learning_service.py:35` |
| `entry_point` 枚举（P1-04 §23 冻结，不新增） | `session_service.py:37` |
| 资源池判定语义（P1-06-C2 冻结）：`{correct,incorrect,partial}` 参与，`{done,skipped,NULL}` 忽略 | `resource_pool_service.py:7/41/43` |
| 诊断不得把"最近一次判断"升级为"薄弱" | `diagnosis_service.py:55/97`、`intervention_service.py:226` |
| `learning_object_service` 输入冻结、不写库、不建表；Grammar LO = DEFERRED | `learning_object_service.py:10/19/52` |
| **`learning/study_call_service.py` 整个模块冻结**（不得为隐藏入口而修改） | `AGENTS.md` §10.5 |

#### `study_call_service.py`（784 行）—— 六入口的唯一数据通道

| 常量 / 函数 | 位置 | 作用 |
| --- | --- | --- |
| `ENTRIES = ("read","listen","phonetic","form","check","practice")` | `:54` | 六入口正式集合 |
| `MODES = ("word","sentence","reading")` | `:59` | 入口内部模式 |
| 入口 → 允许 `question_type` 映射 | `:70-81` | 其中 `reading` 为空元组，注释明示**不得用无音频的 `reading_choice` 冒充** |
| `learned_sections()` | `:288` | **Section 级进度的唯一来源**：由 `learning_record.item_id` + contentpack 正式关系推出；只收录可唯一定位到单一 Section 的 item（Unit 级词表/短语不进入，多 Section 歧义不收录） |
| `unit_scope()` | `:348` | 非 practice 入口 = 仅当前 Unit；practice = Starter + 已学 Unit 前缀（`:329` 注释说明该 Unit 级口径**不再**作为自主练习的正式范围来源） |
| `select_questions()` | `:453` | 候选池 → 证据/掌握过滤 → 确定性排序 |
| `shadowing_materials()` | `:539` | 跟读资源池（Section 级） |
| `record_answer()` / `record_shadowing()` | `:686` / `:734` | 统一经 `learning_service.record_learning_event()` 落证据 |

**注意**：解析不到 contentpack `learning_item` 的题**可以作答，但不产生 Record / mastery**
（`:711`）—— 这是"不伪造教材 item"原则在代码里的体现。

### 4.8 教材解析与数据构建流水线

**`parser/textbook_parser_v01.py`（68 KB）** —— 只读解析教材 PDF，**不建库、不改 PDF/MP3、不导出图片**。

| 规则 | 内容 |
| --- | --- |
| 页码 | 页脚真实印刷页码优先；否则记 `pdf_page - 5` 并标 `derived_only` |
| 文本归一 | NFKC 归一，同时保留 `text_raw`（fi/fl 连字还原） |
| 结构 | block / line / span 三级，含 bbox / font / size / flags |
| 版面 | 先分类（single_column / two_column / mixed / dense_visual）再排序；复杂版面统一标 `NEED_REVIEW` |
| Unit 归属 | 以 PDF 书签为主证据 |
| Activity 识别 | 「约 12 pt 黑体 + 左侧页边」为准；7–8 pt 视为段落/小问编号，**候选阶段即排除** |
| 音频 | 按文件名生成候选，一律 `mapping_status = CANDIDATE`（不自动认定对应关系） |
| 已知限制 | 封面/封底无 OCR（`scanned_pages [8,114]`）；NFKC 会把全角标点转半角；表格/双栏词表未拆到单元格级 |

**`builder/` 22 个脚本的血缘关系**（每一步都是可回溯的原子发布，并写 `audit/` 报告）：

```
教材 PDF ──parser──> build_content_db_v01.py（dry-run，不落库）
                         ↓
   contentpack v1 ──build_vocabulary_v01.py(287 词)──> v2
                  ──build_phrase_v01.py(23 短语)────> v3/v4
                  ──build_sentence_pattern_v01.py(52 句型 + 两注释表)──> v5
                  ──fix_v5_wordlist_continuation_v01.py（词表续行修正，先备份）

教材练习 ──build_exercise_audio_map_v01.py──> exercise_catalog.json(93)
        ──build_p2_3_exercise_rebuild_v01.py──> exercise_catalog_v2.json(157) + exercise_audio_map_v2
        ──build_p2_4_textbook_reconstruction_v01.py──> textbook_*_relations_v2 + catalog_v3
                                                       + exercise_question_relations_v3
                                                       + audio_question_relations_v3
                                                       + textbook_evidence_map_v1(360)
        ──build_textbook_audio_recovery_v01.py──> exercise_catalog_v4（音频恢复挖空）

音频   ──build_audio_resource_layer_v01.py──> audio_resource_v1.json(54，AI=0)
      ──build_audio_sentence_boundaries_v01.py──> 27 个 PARTIAL 活动的句级边界
      ──build_word_audio_v01.py + verify_word_audio_v01.py──> 288 wav + manifest
      ──build_shadowing_pool_v01.py──> shadowing_pool_v1.json(72)

题库   ──build_questionbank_v01.py（确定性，AI=0）
      ──build_questionbank_p4_v01.py（Starter+U1–U6 增量）
      ──build_questionbank_audio_increment_v01.py（句级听写题增量）
      ──build_questionbank_p4b_v01.py（听力/阅读/Phonetics 补全，基线 1537 题只 INSERT）
      ──run_p4b_ai_listening_v01.py / run_p4b_ai_reading_v01.py（**唯一的真实 AI 批量**，一活动一调用）
      ──build_questionbank_value_v01.py（P7 词形/语境/短语释义，基线 1636 题不变）
```

**`p3_07_audio_annotation_spike/`** —— 孤立的句级审核 + 时间区间标注工具（本地 HTTP + 浏览器界面），
是 contentpack v5 中 `audio_sentence_annotation`（15 条）的来源；其 `init_formal_schema.py`
只迁移这一张表，`audio_token_annotation` 作为历史 Spike 表保持为空。

---

## 5. 代码结构

### 5.1 顶层目录职责

| 目录 | 文件数 | 职责 |
| --- | ---: | --- |
| `web/` | 36（0.7 MB） | **正式 Web 服务**（`app.py` 1405 行 + `ui.py` 156 KB 页面生成 + 只读内容层 + 25 个测试） |
| `learning/` | 30（0.3 MB） | **学习服务层**（14 个 service + 17 个测试）——正式业务逻辑，含冻结层 |
| `structured/` | 329（53.2 MB） | **全部正式数据**：4 个 SQLite 库 + 教材/练习/音频/AI JSON 层 + 音频与 PDF 清单 |
| `demo/` | 26（0.8 MB） | **全功能交互 Demo**（`server.py` 2249 行 + `pages.py` 1893 行）；**已排除出 Android 正式载荷**，但仍是 PC 端产品形态验证与端到端验收的主体 |
| `builder/` | 22（0.6 MB） | **离线构建脚本**：从教材 PDF/MP3 生成 contentpack、题库、词表、音频层、跟读池（见 §4.8） |
| `parser/` | 2（0.1 MB） | `textbook_parser_v01.py`（68 KB）+ README（77 行）：教材 PDF 只读解析 |
| `workbench/` | 3（0.1 MB） | Vocabulary 人工审核工作台（`review_workbench_v01.py`）+ 最小学习体验页（`vocabulary_learning_v01.py`）+ 1298 行测试 |
| `audit/` | 691（13.8 MB） | **过程产物与审计报告**（P0–P8 各阶段），是"为什么这样设计"的证据链。按前缀：P3 **132**、P1 77、P2 51、P4 32、P6 3、P7 1、其它 395；按类型：`.json` 377、`.md` 185、`.py` 122 |
| `docs/` | 19（0.5 MB） | 正式规范文档（含 V1.3 110 KB、V2.0 16 KB、Android 基线、UI 规范） |
| `android/` | 1066（851 MB） | Android 壳工程 + 内嵌 Python 运行时打包流水线（绝大部分是构建产物） |
| `start/` | 2 | 手机测试环境一键启动脚本（`_test.ps1` / `_test.cmd`） |
| `tools/faster_whisper_venv/` | — | ASR 离线工具链独立 venv（非运行时依赖） |
| `models/` | 9（463.7 MB） | Whisper 模型与 HF 缓存 |
| `p3_07_audio_annotation_spike/` | 9（0.3 MB） | 音频标注 Spike（独立小 Flask/HTTP 工具 + 数据） |
| `temp/` | 2383（270.5 MB） | **临时验证目录**：Edge 浏览器 CDP profile ×3（占绝大部分）、`p5_call_fixture_*` ×21、`p7_*` 调试脚本、历史 DB 快照（`questionbank.pre_p4.db` 等）、`web8770.log` |

### 5.2 `learning/` —— 学习服务层（14 个 service，全部 stdlib、零第三方依赖）

| 模块 | 行数 | 职责 | 读写 |
| --- | ---: | --- | --- |
| `study_call_service.py` | 784 | **P5 正式学习调用层（冻结核心）** | 读 contentpack + questionbank + learning.db；写经 learning_service |
| `learning_object_service.py` | 454 | Learning Object 映射：`lo_evidence` / `lo_mastery` / `lo_diagnosis` / `lo_suggestion` | 只读派生 |
| `learning_service.py` | 409 | **唯一写入口** `record_learning_event` + Task/Learner CRUD + `_upsert_mastery` | **写** learning.db |
| `intervention_service.py` | 238 | 教材优先巩固建议（只给建议、不执行）；Grammar LO = DEFERRED | 只读 |
| `resource_pool_service.py` | 239 | 当前错误 / 当前薄弱池（仅 SELECT） | 只读 |
| `session_service.py` | 188 | Session 生命周期 + Session↔Task 组织 | 写 learning.db |
| `questionbank_service.py` | 184 | 题库读取（**不碰 learning.db**） | 只读 questionbank |
| `evidence_service.py` | 182 | 有效证据判定（done/skipped/NULL/纯 study/纯自评 不计；同日同类型去重） | 只读 |
| `audio_resource_service.py` | 170 | 音频资源层（Unit→音频→文本→时间段→能力→就绪度） | 只读 JSON |
| `vocabulary_service.py` | 165 | 核心词汇消费链路（`learning_requirement='CORE'` 为机器判据） | 写（经 session/learning） |
| `mastery_service.py` | 146 | 掌握判定（5 条件全满足才 `stable`） | 只读 + `mastery_rules_v1.json` |
| `activity_service.py` | 121 | LearningActivity = `task_item` + contentpack 推导的**只读投影**，不建表 | 只读 |
| `diagnosis_service.py` | 112 | 诊断三档 `current_error` / `suspected_weak` / `needs_textbook_review`；铁律「一次错误 ≠ 薄弱」 | 只读 |
| `behavior_service.py` | 105 | 学习行为协议 `study` / `practice`（追加，不改既有 9 值） | 转调写 learning.db |

### 5.3 `web/` —— 正式 Web 服务

模块职责：

| 模块 | 行数 | 职责 |
| --- | ---: | --- |
| `app.py` | 1405 | HTTP 服务 + 全部路由 + P5 六入口编排 + 音频流（Range） |
| `ui.py` | 3150（160 KB） | **全部页面 HTML/CSS/JS 生成**（~20 个页面函数 + P5 页面族 + 8 段内联 `<script>` + 内联 SVG 图标） |
| `content.py` | 644 | 只读内容层：`list_units_with_sections`、`home_context`、`audio_covered_block_ids`、`unit_resource_counts` |
| `exercises.py` | ~42 KB | 教材练习目录与规则判分（`load_catalog`、`build_questions`、`grade`、`sub_questions_for_activity`） |
| `demo_data.py` | 34 KB | Demo 视图模型 **+ 六入口显隐正式逻辑**（`formal_entries`、`ENTRY_ORDER_FORMAL`、`NON_TEACHING_UNITS`） |
| `demo_content.py` | 25 KB | 一次性生成的冻结练习内容（`VERSION="v5-2026-09-16"`）；**已不被 `web/app.py` import** |
| `flow.py` | 18.2 KB | Vocabulary 闭环**编排**（只编排不复制规则）+ `recent_studied` + `item_key` |
| `reading_map.py` | 14.8 KB | 音频 ↔ 教材自然文本块只读派生；**已不被 `web/app.py` import**（仅 Demo 与测试使用） |
| `pdf_pages.py` | 6.7 KB | PyMuPDF 现场渲染教材页（DPI 130 / q78 / 内存 LRU 24）+ `text_rects()` |
| `audio.py` | 9.3 KB | 音频解析：`classify`（word_list / phonetics / reading / listening / activity）、`resolve_official_audio`、`word_audio_index` |
| `ai_grading.py` | 3.8 KB | **AI 批改接口占位**：`AI_PROVIDER = None`(20)，`ai_configured()` 恒 False(82)，实际是确定性离线规则预检 |

#### `web/app.py` 路由表（GET）

| 路径 | 处理 | 用途 |
| --- | --- | --- |
| `/audio/official/<AUxx>.mp3`、`/audio/word/<key>.wav` | `_audio()` | 只读音频流（支持 Range） |
| `/page/<n>.jpg` | `_page_image()` | 教材页图片 |
| `/`、`/index.html` | `_home()` | 首页（课时选择器 + 六入口显隐 + AI 卡） |
| `/learn/`、`/textbook/` | `_textbook()` | 教材中心 |
| `/progress/` | `_progress()` | 我的进展 |
| `/unit/<slug>/p5/<entry>` | `_p5_page()` | **六入口练习页**（`?i=` 题号、`?mode=` 内部模式、`?cat=` 类别） |
| `/unit/<slug>/p5/<entry>/result` | `_p5_result()` | 练习结果 |
| `/unit/<slug>/text` | `unit_text_page` | 教材原文（**只展示与 VERIFIED 官方音频可靠对应的块**） |
| `/unit/<slug>/resources[/<type>]` | `resource_types_page` / `resource_list_page` | 资源浏览（次级内容页） |
| `/unit/<slug>/exercises` | `_exercise_list()` | 教材练习列表 |
| `/exercise/<key>` | `_exercise_get()` | 教材练习作答 |
| `/review/` | `_review()` | 复习 |
| `/vocabulary/recall`、`/vocabulary/result`、`/vocabulary/study` | 词汇闭环 | Vocabulary 学习 |
| `/health` | JSON | `{"status":"ok","service":"ZhixueEnglish-WebUI/0.1"}` |
| `GET /unit/<slug>`（无 tail） | **404（设计如此）** | 旧七项菜单宿主已退役 |
| 其它 `/unit/<slug>/*` | 404 | 旧入口已退役 |

#### `web/app.py` 路由表（POST）

| 路径 | 用途 |
| --- | --- |
| `/vocabulary/study`、`/vocabulary/study/done`、`/vocabulary/recall/reveal`、`/vocabulary/practice` | 词汇闭环 |
| `/review` | 复习 |
| `/demo/learn` | 学习行为 → 章节状态（Cookie） |
| `/demo/wrong` | 错题池（Cookie） |
| `/unit/<slug>/p5/<entry>/submit` | **正式题库作答**（经 `study_call_service`） |
| `/exercise/<key>/submit` | 教材练习提交 |

**已退休并保持 404 的路由**（`audit/` 与测试文件为证，代码内有测试守护）：
`/train`、`/unit/<slug>/train`、`/unit/<slug>/weekend`、`/unit/<slug>/stage`、
`/unit/<slug>/practice`（旧）、`/tutor`、`/unit/<slug>/sentence`、`/unit/<slug>/shadowing`、
`/unit/<slug>/result`、`/p3-06/*`。

### 5.4 `demo/` —— 全功能 Demo 服务

`demo/server.py` 路由比正式 Web 更粗（前缀分发）：

| 路径 | 用途 |
| --- | --- |
| `GET /` | 首页（当前课时 + 能力入口） |
| `GET /unit/<slug>` | Unit 页 |
| `GET /unit/<slug>/vocab` | 单词跟读 |
| `GET /unit/<slug>/listen?mode=word|sentence` | 听音辨意 |
| `GET /unit/<slug>/reading` | 听音阅读（时间轴跟随） |
| `GET /unit/<slug>/check`、`/check/wrong` | 本课检测 + 错题闭环 |
| `GET /unit/<slug>/sentences` | 短句跟读（38 条已对齐句子） |
| `GET /unit/<slug>/say` | 课文简答 |
| `GET /unit/<slug>/practice[/special|/reinforce|/result]` | 自主练习（专项 / 巩固） |
| `GET /unit/<slug>/result` | 学习结果 + AI 学习分析 |
| `GET /unit/<slug>/tutor` | AI 随堂助教 |
| `GET /unit/<slug>/continue` | 下一步 |
| `GET /unit/<slug>/speaking` | **旧入口兼容** → 重定向到 `/sentences` |
| `GET /health` | 健康检查 |
| `POST /switch`、`POST /lesson` | 切 Unit / 切课时（Cookie） |
| `POST /unit/<slug>/*` | 各功能作答提交 |

### 5.5 `android/` —— 承载层

```
android/
├── settings.gradle.kts          rootProject.name = "ZhixueEnglishWebView"
├── build.gradle.kts             AGP + kotlin compose plugin（apply false）
├── gradle.properties            zhixue.webBaseUrl = http://127.0.0.1:8780/
├── local.properties             sdk.dir = G:\AndroidSDK      ← 本机专属，不应入库
├── gradle/libs.versions.toml    version catalog（AGP / Kotlin / Compose BOM / JUnit）
├── app/
│   ├── build.gradle.kts         compileSdk 37 / minSdk 24 / targetSdk 37；依赖本地 AAR
│   ├── libs/zhixueenglish_backend_runtime.aar   （138.2 MB，内嵌 Python 运行时）
│   ├── build/outputs/apk/debug/app-debug.apk    （272,202,175 B，已构建）
│   └── src/
│       ├── main/AndroidManifest.xml             INTERNET + RECORD_AUDIO
│       ├── main/java/com/zhixueenglish/app/dev/
│       │   ├── MainActivity.kt                  （21.6 KB，519 行）Compose 壳 + WebView + 状态机
│       │   ├── ai/AiClient.kt                   （5.7 KB）OpenAI 兼容最小请求层
│       │   ├── ai/AiEndpoint.kt                 （1.8 KB）纯字符串逻辑，可单测
│       │   ├── ai/AiSettingsScreen.kt           （10.7 KB）AI 设置页（Compose）
│       │   ├── ai/AiConfigStore.kt              （3.4 KB）开关/URL/Model + usage 统计
│       │   ├── ai/SecureKeyStore.kt             （3.8 KB）Keystore AES/GCM 密文存储
│       │   └── runtime/LocalBackend.kt          （5.3 KB）反射启动 ServiceZhixue + /health 探活
│       ├── main/res/                            只有 drawable/values，无 layout
│       ├── debug/AndroidManifest.xml            usesCleartextTraffic（仅 debug）
│       └── test/java/.../ai/AiEndpointTest.kt   8 个纯逻辑单测（URL 组装 / Key 脱敏）
└── python_runtime/                              内嵌 Python 运行时打包流水线
    ├── README.md                                路线与步骤说明（注意：README 的部分描述已落后于代码，
    │                                            它以"WebView 仍指向 192.168.2.3:8770"为现状）
    ├── stage_payload.py         （10.8 KB）复制**运行时最小集合**到 app/；显式排除 demo/**
    ├── p4a_package_aar.sh       （1.6 KB）WSL 内 p4a 预处理（复用已验证 dist，不重编 CPython）
    ├── assemble_aar.py          （6.3 KB）离线组装 AAR（等价 Gradle 结构，避免联网取 gradle-8.14.3）
    ├── service/main.py          （9.0 KB）p4a 服务入口：播种 state DB → 设 ZX_ROOT → 加载 web/app.py main()
    ├── app/                     载荷：web 11 + learning 14 + structured 300 + audit 64 + service 1
    │                            + official_audio.zip（117 MB）；**不含 demo/**
    ├── dist_aar/                p4a 工作副本（CPython 3.14 + libpybundle.so + private.tar + 生成 Java）
    └── .aar_work/               AAR 内 classes 的展开工作区
```

**内嵌运行时证据**：`assemble_aar.py` 文件头明确输出结构为
`AndroidManifest.xml + classes.jar + jni/arm64-v8a/*.so + assets/private.tar + res/`；
`app/build/intermediates/merged_native_libs/.../lib/arm64-v8a/` 实际含
`libpython3.14.so`（5.5 MB）、`libpybundle.so`（10.7 MB）、`libsqlite3.so`（1.2 MB）、
`libcrypto.so`（4.9 MB）、`libssl.so`（1.2 MB）、`libffi.so`、`libmain.so`、`libpythonbin.so`。
AAR 本身 **138,166,342 字节（131.77 MiB）**，mtime 2026-09-20 17:29:00。

> ⚠️ **已构建的 AAR / APK 内嵌的是「旧版」Web 载荷（重要事实）**
>
> | 文件 | AAR 内（2026-09-20 打包） | 当前工作区 |
> | --- | ---: | ---: |
> | `web/app.py` | 87,141 B（**仍 import `demo_content` 与 `reading_map`**） | 75,534 B（2026-09-28，已不 import） |
> | `web/ui.py` | 243,196 B | 160,201 B（2026-09-28） |
> | `web/content.py` | 25,737 B（2026-09-19） | 29,931 B（2026-09-26） |
> | `web/demo_data.py` | 51,123 B（2026-09-19） | 34,502 B（2026-09-28） |
>
> 另外 AAR 内 `private.tar` 为 122,573,956 B，而 `dist_aar/` 里当前的 `private.tar`
> 是 122,574,244 B（mtime 17:53:57，**晚于 AAR 的 17:29:00**）——即最后一次 p4a 预处理后
> **没有再重新组装 AAR**。结论：**当前 APK 提供的是 P6-B-23 页面退休之前的 Web 层**
> （因此它内部仍存在已退休的 `/tutor`、`/unit/<slug>/result` 等路由）。
> 要发布需重跑 `stage_payload.py → p4a_package_aar.sh → assemble_aar.py → assembleDebug` 全链路。

#### Android 清单与 UI 组成

`app/src/main/AndroidManifest.xml`：权限仅 `INTERNET` 与 `RECORD_AUDIO`；
`allowBackup="false"`、`supportsRtl="false"`、`theme="@style/AppTheme"`；
**没有 `android:name`（无 Application 子类）**、**没有 `android:icon`**（AAR 里有
`res/mipmap/icon.png`，但没有任何地方引用它）、**没有 `networkSecurityConfig`**；
只有 `.MainActivity` 一个组件（`exported="true"`，MAIN/LAUNCHER）。
`app/src/debug/AndroidManifest.xml:7` 仅在 **debug** 构建加 `usesCleartextTraffic="true"`。

`res/` 下**总共只有 3 个文件**（`drawable/ic_settings.xml`、`values/strings.xml`、
`values/themes.xml`）—— **确认没有任何 XML 布局、没有 `layout/` 目录、没有启动图标 mipmap、
没有 `xml/`（因此也没有 `network_security_config.xml`）、没有 `androidTest/`**。
含义：**原生层没有任何学习界面**，全部原生像素由 Compose 绘制（3 个状态页 + 设置芯片 + WebView 容器），
真正的产品界面 100% 是 `web/ui.py` 生成的 HTML/CSS/JS。

---

## 6. 测试与验证资产

| 位置 | 数量 | 内容 |
| --- | ---: | --- |
| `web/test_*.py` | 25 | 八组：①**冻结数据保护**（比对正式 DB / service 的 SHA256 不变）②音频与练习（含 Range 请求、路径穿越 → 404、扬声器图标尺寸）③**设计与规范文档同步**（直接断言 `docs/` 里的规范文本）④Demo UI 回归 ⑤Vocabulary 闭环（`test_vocabulary_flow.py` 53 KB / ~45 项）⑥P5 六入口（`test_p6a_p5_web.py`：只写正式证据、practice 不取未来内容）⑦**退休不变量**（断言 `/train`、`/weekend`、`/stage`、`/tutor`、`/sentence`、`/shadowing`、`/result` 等保持 404，且没有任何链接指向它们）⑧P6-B-12/13 产品规则（入口数与页面池一致、PARTIAL 绝不展示、46 个 Section 单下拉） |
| `learning/test_*.py` | 17 | 各 service 单测 + 关键规则验收（`test_p6b9_section_progress`、`test_p6b11b_read_section_scope`、`test_p8_read_b_shadowing_pool`、`test_p7_textbook_value`、`test_study_call_service` 407 行等）。**统一手法**：复制正式 `learning.db` 到 temp 再写，测试前后比对正式库 SHA256 |
| `demo/test_demo_v10.py` | 1（116 KB / 1949 行） | Demo 端 21 项端到端验收（纯内存 unittest，进程内随机端口） |
| `workbench/test_vocabulary_learning_v01.py` | 1（1298 行） | 词汇学习工作台 |
| `android/app/src/test/.../AiEndpointTest.kt` | 1（76 行 / 8 个 `@Test`） | JVM 纯逻辑单测：URL 组装、Key 掩码、日志脱敏 |
| `start/_test.ps1` / `_test.cmd` | 2 | 手机测试环境一键检查/启动（**不是单元测试**；只读检查，明确声明不改任何配置） |
| `audit/` | 691 | 每个阶段的设计审计 / 构建报告 / 验收报告（JSON 机器可读 + MD 人读） |

测试基调统一为 **stdlib `unittest`、无新依赖、无网络、不调用 AI、只读正式数据**。

> 移动端侧：**没有任何 `androidTest/`（instrumentation）测试**，`MainActivity`、`LocalBackend`、
> `AiConfigStore`、`SecureKeyStore`、`AiUsageStore` 与 Python 后端均无测试覆盖。

---

## 7. 当前完成度总览

### 已完成（可用、有测试守护）

1. 教材事实层：contentpack v5（8 Unit / 46 Section / 520 learning_item / 3854 content_block）+ 教材 PDF + 54 官方 MP3 + 288 派生词音频。
2. 正式题库：questionbank.db 1831 题、15 种题型、6489 题源资产。
3. 学习服务层：14 个 service，闭环（证据 → 掌握 → 诊断 → 干预 → 资源池）全部实现并被测试覆盖。
4. 正式 Web UI：约 25 个页面，六入口按 Section 真实资源显隐，全部页面由 `ui.py` 生成。
5. 音频能力：Range 流式播放、句级 VERIFIED 时间轴、跟读池、听音阅读时间轴跟随、录音组件。
6. 全功能 Demo：PC 端完整学习链路（含 AI 形态模拟），是产品形态验证与端到端验收主体（**不在 Android 载荷内**）。
7. Android 独立运行：Compose 壳 + 内嵌 CPython 3.14 runtime AAR + `/health` 就绪判定，**debug APK 已构建（272,202,175 B）**。
8. Android AI 配置：Keystore 安全存储 + OpenAI 兼容客户端 + 设置页，**Key 不泄露**。
9. 规范体系：V1.3（110 KB 最高指导）+ V2.0（产品/UI 总纲）+ Android 基线 + UI 规范 + 691 份阶段审计。

### 未完成 / 明显缺口（事实，非评价）

**A. 内容与智能（产品层面）**

| # | 缺口 | 证据 |
| --- | --- | --- |
| A1 | **题库 Section 覆盖极低**：仅 10 个 section_key 有题，46 个 Section 中约 36 个无任何正式题 | `SELECT COUNT(DISTINCT section_key) FROM question` = 10 |
| A2 | **Appendix（6 个 Section）零题**，且按正式规则不进入六入口 | Unit 统计中无 Appendix 行；`demo_data.NON_TEACHING_UNITS` 显式返回空池 |
| A3 | **`textbook_native` 517 题全部 `PENDING_REVIEW` + `NO_RELIABLE_SOURCE`**，尚无可靠答案来源 | `question` 表 `review_status` / `answer_status` 统计 |
| A4 | **无真实 AI 调用**：`web/ai_grading.py:20 AI_PROVIDER = None`，Android 侧 `AiClient.chat()` **零调用方**；全部 AI 内容为确定性模拟（`ai_called=false`） | `ai_grading.py:20`；`AiClient.kt:61` 无调用者；`demo/README.md:88` |
| A5 | **无真实 ASR / 发音评分**：跟读反馈是确定性虚拟数据，页面带"演示效果"标注 | `demo/README.md:264` |
| A6 | **`听音阅读` 永远不可能出现**：`study_call_service.py` 中 `LISTEN_MODE_TYPES["reading"] = ()`，注释明确"不得用无音频的 `reading_choice` 冒充" | `study_call_service.py:66-68` |
| A7 | **句级时间轴只有 38 条唯一句子**（contentpack VERIFIED 仅 12 条），跟读池按 Unit 分布极不均（**Unit 2 为 0 条**） | `demo/README.md:273`；`shadowing_pool_v1.json` by_unit |
| A8 | **52 条 `supplement_task` 全部是 `AI_SUPPLEMENT_REQUIRED`**（待 AI 补足工单） | `supplement_task` 表统计 |
| A9 | **无语法数据表**：AI 解释里的"语法"只能引用教材句子本身 | `demo/README.md:276`；`contentpack` 无 grammar 表 |
| A10 | **正式库几乎没有学习数据**：`learning_record` 26 条（全为 `study`）、`mastery_state` 7 条（**全为 `unknown`**）、`learning_session` 38 条（`entry_point` 全为 `vocabulary`） | 直接查询 learning.db |

**B. Android 与发布（工程层面）**

| # | 缺口 | 证据 |
| --- | --- | --- |
| B1 | **Release 构建将无法访问自己的后端**：`usesCleartextTraffic` 只在 debug manifest，`res/xml/network_security_config.xml` **不存在**，而目标是 `targetSdk 37` → release 下 WebView 会拦截 `http://127.0.0.1:8770` | `app/src/debug/AndroidManifest.xml:7`；`res/` 仅 3 个文件 |
| B2 | **APK / AAR 内嵌的是旧版 Web 载荷**（2026-09-20，`web/app.py` 87,141 B 且仍 import `demo_content`/`reading_map`；当前为 75,534 B 且已不 import）。当前 APK 内部**仍含 P6-B-23 已退休的路由** | 见 §5.5 对照表；`dist_aar/private.tar`(17:53) 晚于 AAR(17:29) |
| B3 | **端口配置「脑裂」**：`gradle.properties:8` 写 `8780`（Demo，且载荷里根本没有 `demo/**`），而实际加载的是硬编码的 `LocalBackend.BASE_URL` = `127.0.0.1:8770`；`BuildConfig.WEB_BASE_URL` 只被打印、从未用于加载 | `gradle.properties:8`、`LocalBackend.kt:26-28`、`MainActivity.kt:109/139`、`stage_payload.py:30` |
| B4 | **文档已落后于代码**：`python_runtime/README.md:83` 仍称"WebView 仍按 `BuildConfig.WEB_BASE_URL` 访问"，而代码已直接加载 8770 | `python_runtime/README.md:83` |
| B5 | **p4a 流水线对本 checkout 不可直接运行**：`p4a_package_aar.sh:14-15` 硬编码 `/mnt/d/ZhixueEnglish/...`，README 全部命令写 `D:\ZhixueEnglish`，`assemble_aar.py:52` 默认 `ANDROID_HOME=G:\AndroidSDK` | 上述文件行号 |
| B6 | **无 release 签名配置、无正式包名与版本**：`versionName = "0.1-dev"`、`applicationId` 带 `.dev`、`release { optimization.enable = false }` | `app/build.gradle.kts` |
| B7 | **原生层极薄且缺件**：无 Application 子类、**无应用图标**（AAR 里有 `res/mipmap/icon.png` 但无人引用）、无 `networkSecurityConfig`、只打 `arm64-v8a` 一个 ABI、无 CI | `AndroidManifest.xml`；`res/` 文件清点 |
| B8 | **Android 侧无任何 instrumentation 测试**，`MainActivity` / `LocalBackend` / 4 个 `ai/*` / Python 后端均无覆盖 | `app/src/test` 只有 `AiEndpointTest.kt` |
| B9 | **AI 能力"可配置但不可用"**：`AiUsageStore` 统计恒为 0，因为唯一的 AI 表面是设置页的"连接测试" | `AiClient.chat()` 零调用方 |

**C. 通用工程卫生**

| # | 缺口 | 证据 |
| --- | --- | --- |
| C1 | **项目根存在名称损坏的目录项**（5 个 `U+FFFD`），导致任何从根开始的递归遍历失败 | §0 目录异常 |
| C2 | **路径基准不一致，且有真实写错位置的风险**：文档/代码默认 `D:\ZhixueEnglish`，实际项目在 `J:\ZhixueEnglish_01`；`web/` 的 6 个模块都靠 `os.environ.get("ZX_ROOT")` 规避，但 **`init_learning_db.py:28`、`migrate_learning_db_v2.py:33`、`p3_07_audio_annotation_spike/init_formal_schema.py:15` 硬编码 D 盘** —— 在 J: 直接运行会写到 D: | 源码行号；**本机 `D:\ZhixueEnglish` 确实存在**，因此在 J: 不设 `ZX_ROOT` 运行 `web/app.py` 会**静默读取另一份副本的 `learning.db` / contentpack** |
| C3 | **仓库内存在大量不可达（dead）代码**（按 AGENTS.md §8"核心能力保留"有意为之，但确实无调用者）：`app._lesson_rows`、`app._drill_items`、`app._other_sentence_pool`、`ui._legacy_exercise_page`、`exercises._legacy_build_questions` / `_legacy_grade`、`LocalBackend.runtimePackaged()`、`AiClient.chat()`；整模块 `reading_map.py`、`demo_content.py` 已不被 `web/app.py` import（仅 Demo 与测试使用） | grep 全项目零调用者 |
| C4 | **`demo_data.py` 内含多处硬编码演示数值**：`DEMO_MODE=True`、`ATTENTION`、`WEEK_MINUTES=32`、`TODAY_MINUTES=8`、`CHAPTER_PROGRESS`、`UNIT_THEME`、`parent_progress` | `demo_data.py:38/61/85/86/447/362/494` |
| C5 | **入口完成状态被写死为未完成**：`formal_entries` 恒定输出 `"done": False` | `demo_data.py:196` |
| C6 | **无认证**：身份只是一个 `zx_learner` Cookie，POST 兜底为 `flow.resolve_learner(conn, "本机学生")` | `app.py:678` |
| C7 | **`temp/` 含 270.5 MB 临时物与历史 DB 快照**（其中约 260 MB 是 3 份 Edge 浏览器 profile；另有 `questionbank.pre_p4.db` 等历史库） | `temp/` 实测 2,383 个文件 |

---

## 8. 关键设计约束（改动前必须先读）

这些约束写在 `AGENTS.md` 与 `docs/初中英语AI辅助学习系统最高指导原则与开发规范_V1.3.md`（110 KB，最高依据）中，
是所有后续开发的硬边界。**本次扫描未修改任何文件，以下是转述**：

1. **Section 是学习进度的核心粒度**，但 **Section 不是所有功能的资源边界**：
   进度粒度（Section）与各功能资源池范围必须分开建模。
   各入口与 `learned_sections` 的关系：`read` 否 ｜ `listen-sentence` 当前 Section ｜
   `phonetic` 按资源自身粒度 ｜ `form` Unit 级 ｜ `check` 当前 Section ｜
   **`practice` 是（正式使用 `learned_sections`）**。**practice 规则不得复制给其他入口。**
2. **教材目录不得用题库/资源存在性过滤**：一个 Section 是否属于正式目录，只由 `contentpack.section` 决定；
   完整目录保留 **8 组 / 46 个 Section**。
3. **入口显隐 ≠ 功能内容层空状态**（两层不同处理）：当前 Section 无该功能所需资源时入口可以不显示，
   但不得删除 Section、不得静默切换、不得借用其他资源；进入后无资源时如实呈现真实空状态。
4. **内部模式同规则**：`听音辨意` 是一条入口，三个模式只显示有资源的；
   默认模式无资源时按 `单词听辨 → 句子听辨 → 听音阅读` 改选，**不切换 Section**。
5. **随机抽题**：先按各功能业务规则定合法候选池，**再**在池内随机；`?i=` 只是当前会话临时定位，
   不得理解成固定题序机制。
6. **AI 不制造教材事实**：AI 只能用教材事实 + 真实学习证据做分析/评估/反馈/建议，不排计划、不强制。
7. **已退休的路由与页面保持 404**，不得恢复、不得创建替代路由：
   旧训练岛（`/train`、`/weekend`、`/stage`、旧 `/practice`）、
   旧 Demo 老页面（`/tutor`、`/p3-06/*`、`/sentence`、`/shadowing`、`/result`）。
   旧七项训练菜单、「今日10分钟/周末巩固/阶段测」属历史已退休实现。
8. **核心资产不得删除**：教材 PDF、官方 MP3、contentpack、questionbank.db、learning.db、
   learning service、`web/content.py`、`web/audio.py`、`learning/study_call_service.py`、
   六入口、Unit→Section 选择器、`PLAYER_JS` / `RECORD_JS` / `ai_card` 等。
9. **页面退休 ≠ 能力退休**：能力保留，页面是否承载属后续产品决策。
10. **规范与实现的生命周期规则**：正式规则变化必须同步到最高指导文件；
    正式退休的实现必须从产品代码清理（不靠隐藏）。

---

## 9. 一句话总结

> 这个项目**不是"半成品"意义上的残片**：教材数据层、学习服务层、正式 Web UI、全功能 Demo、
> Android 独立运行链路和 APK 都已经打通，并配有 44 个 Python 测试文件（+ 1 个 Kotlin 单测）与 691 份阶段审计。
>
> 它真正**未完成的**是四件事：
> **① 内容广度**——46 个 Section 里只有 10 个有正式题目，大量 Section 会是空状态，
> 且 517 道教材原生题还没有可靠答案；
> **② 真实智能**——AI 与 ASR 目前全部是确定性模拟，运行时调用次数为 0
> （`AI_PROVIDER = None`，`AiClient.chat()` 无调用方）；
> **③ 发布收口**——release 缺明文流量豁免（连不上自己的 8770 后端）、无签名配置、
> 无正式包名与版本、**现有 APK 内嵌的是 9 月 20 日的旧 Web 载荷**；
> **④ 环境收口**——项目根有损坏目录项、代码默认路径仍指向 `D:\ZhixueEnglish`
> （而本机 D 盘确实存在同名项目，不设 `ZX_ROOT` 会静默读错库）。

---

## 10. 如果接下来要动手，建议的阅读顺序

1. `AGENTS.md`（执行约束）→ `docs/初中英语AI辅助学习系统最高指导原则与开发规范_V1.3.md`（最高依据，
   尤其第二十九章 §15「菜单与目录的最终产品规则」、§1「教材层级与学习上下文」、
   §7「题目随机性」、第二十八章 §7「自主练习范围」）。
2. `docs/初中英语AI辅助学习系统产品与UI架构总纲_V2.0.md`（一级导航 / 首页定义 / 六入口 / 进展页）。
3. `docs/智学英语_Android独立运行与APK本地化实施基线_V1.0.md`（承载方式、安全边界、验收标准）。
4. 代码入口：`web/app.py`（路由与 P5 编排）→ `web/ui.py`（页面）→
   `learning/study_call_service.py`（**冻结**，六入口唯一数据通道）→
   `learning/learning_service.py`（**唯一写入口**）。
5. 想了解"为什么这样设计"：直接读 `audit/` 下对应阶段的 `.md`（每步都有设计审计 + 验收报告）。

**动手前的三个硬提醒**：

- 先设 `ZX_ROOT=J:\ZhixueEnglish_01`，否则 `web/app.py` 会读 `D:\ZhixueEnglish` 的数据。
- 不要修改 `learning/study_call_service.py`（AGENTS.md §10.5 冻结层）与 `learning.db` schema。
- 不要恢复任何已退休路由（`/train`、`/weekend`、`/stage`、`/tutor`、`/unit/<slug>/result` 等），
  现有测试会直接失败。

---

## 附录：本次扫描的关键命令与可复现性

```powershell
# 目录枚举（必须逐个顶层目录，避免根目录损坏项导致递归失败）
Get-ChildItem -LiteralPath 'J:\ZhixueEnglish_01\web' -Recurse -File
```

```python
# 数据库只读统计（正式数据一律 mode=ro）
import sqlite3
c = sqlite3.connect(r"file:J:/ZhixueEnglish_01/structured/questionbank/questionbank.db?mode=ro", uri=True)
print(c.execute("SELECT COUNT(*) FROM question").fetchone())   # (1831,)
```

```powershell
# 启动正式 Web 服务（8770）—— 务必先设 ZX_ROOT，否则会读到 D:\ZhixueEnglish
$env:ZX_ROOT = 'J:\ZhixueEnglish_01'
python J:\ZhixueEnglish_01\web\app.py --host 0.0.0.0 --port 8770

# 启动全功能 Demo（8780，PC 端产品形态验证；不在 Android 载荷内）
python -B J:\ZhixueEnglish_01\demo\server.py

# 手机测试环境一键检查
J:\ZhixueEnglish_01\start\_test.ps1

# 重新构建 APK（需联网或已缓存 Gradle 9.5.0 发行包）
cd J:\ZhixueEnglish_01\android
.\gradlew.bat --offline :app:testDebugUnitTest :app:assembleDebug

# 注意：APK 内的 Python 载荷需单独重跑流水线才会更新（三条命令见 python_runtime/README.md，
#       其中 p4a 步骤需 WSL，且脚本内硬编码的是 D:\ZhixueEnglish 路径）
```

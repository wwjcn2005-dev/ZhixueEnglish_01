# P3-06 第一阶段：只读侦察报告（时间标记口语训练 Spike）

> **本次仅完成只读侦察**：未修改任何文件、数据库、Android 工程或原始教材/音频；**AI 调用 0**；外部网络 0；未安装依赖；未生成中间文件。本报告是本阶段唯一产出。

---

## 1. 当前音频资源真实情况

| 项 | 实测 |
| --- | --- |
| 项目根目录 | `D:\ZhixueEnglish`；实际目录：`2025年度初一外研版英语教材`（原始教材+音频）、`structured`、`audit`、`docs`、`android`、`web`、`learning`、`builder`、`parser`、`start`、`workbench`（**没有** `source/`、`extracted/` 这两个目录） |
| 原始音频目录 | `D:\ZhixueEnglish\2025年度初一外研版英语教材\` — **54 个 MP3**（外研版官方，非 TTS） |
| 音频登记 | contentpack `audio_asset` 54 行；`audio_mapping` 59 行；`exercise_audio_map_v3.json` **54/54 CONFIRMED** |
| 音频范围 | **41 条活动级**（文件名含"单元_板块_活动号_指令"）+ **13 条板块级**（7 条 Words and expressions 词表 + 6 条 Phonetics in use） |
| 时长 | 33.5s ~ 191.7s（大多数 40–120s） |
| 是否原始音频 | ✅ 全部原始（SHA256 与 `audio_asset` 逐一比对一致，P3-01 实测） |
| 播放服务 | Web 端 `/audio/official/<AUxx>.mp3`（`web/app.py::_audio` → `resolve_official_audio`），支持 HTTP Range（真机分片请求实测 **206**） |

**Starter + Unit 1 的 15 条（与本 Spike 最相关）**：AU01–AU06（Starter，含 60.7/33.5/58.2/85.9/56.3/43.4s）+ AU48（词表 90.2s）；AU07–AU13（Unit 1，含 109.4/72.5/51.1/68.3/44.2/175.0/101.4s）+ AU49（词表 92.1s）。

## 2. 此前音频审计结果中已经具备什么

| 已有结果 | 位置 | 内容 |
| --- | --- | --- |
| 音频↔活动映射（证据链） | `structured/audio/exercise_audio_map_v3.json` | 54 条，status=CONFIRMED，含 unit/section/activity_no/exercise_id/scope/理由（文件名指令 vs 教材指令，相似度 0.99–1.00） |
| 音频↔题目关系 | `structured/audio/audio_question_relations_v3.json` | 121 条 activity 级关系（一段音频服务该活动多道题） |
| 音频↔文本审查 | `audit/P2-6-C-4-A_audio_text_mapping_audit.md` | 结论：音频与教材文字对应可靠，**无需切割**（SPLIT_REQUIRED=0） |
| 声学静音分析 | `audit/P3-01_tmp/p301_audio_analysis.json` | Starter+U1 全部 15 条音频的语音段（HOP 10ms / MIN_GAP 200ms） |
| 短句候选与状态 | `audit/P3-01_shadowing_small_batch_validation.md` | Starter+U1：CONFIRMED 0 / CANDIDATE 1（AU06）/ NEEDS_REVIEW 14 |
| 词级时间（派生） | `structured/audio/derived/word_audio_manifest.json` + 288 个 WAV | **唯一的"时间区间"资产**：288 个单词的 start_ms/end_ms（由官方词表音频离线静音切分派生；口径标注"非官方独立单词音频"） |
| 短句样本（无时间） | `audit/P3-05_samples/shadowing_manifest.json` | 10 句教材原句，`audio_scope=FULL_ACTIVITY_AUDIO`，**不含** start/end |
| 对齐技术结论 | `audit/P3-03_local_alignment_technology_validation.md` | 本机无本地 ASR/强制对齐（全部 UNAVAILABLE）；判定 **D**，需用户批准安装 |

## 3. 句子级时间标记目前具备什么

**结论：当前已有审计结果中没有可靠的句子级 start/end 时间标记。**

逐项核查：

| 可能的时间来源 | 是否存在 | 说明 |
| --- | --- | --- |
| `transcript` 表 | ❌ 0 行 | contentpack 中为空 |
| Whisper / 其他本地转写结果 | ❌ | 本机无任何 ASR（P3-03 实测），也未找到任何转写文件 |
| 句子级 start/end JSON/CSV | ❌ | 全项目检索 `start_ms/end_ms/timestamp/time_start`：**只有**派生词音频 manifest 命中 |
| 词级 start/end | ✅ 288 条 | 仅限**词表音频**里的单词（派生资源，非句子） |
| 句子级候选边界（未经复核） | ⚠️ 1 条 | P3-02 对 AU06 首句 `Hello everyone!` 给出静音边界 **560–2090ms**，明确标注 **CANDIDATE**（未通过独立复核，不可当事实） |
| 句子级时间标记（可直接用） | ❌ **0 条** | — |

> 不做任何时间猜测；上表即全部事实。

## 4. 推荐用于 Spike 的 3～5 个真实句子

| # | Module/Unit | Activity | 句子 | 原始音频 | 是否已有时间定位依据 |
| --- | --- | --- | --- | --- | --- |
| 1 | Starter | Get to know each other A4（教材第 10 页，P15:B3） | Hello everyone! | AU06（43.4s） | ⚠️ 仅有 P3-02 的 **未复核候选** 560–2090ms |
| 2 | Starter | 同上 | My name is Zhu Xiaomeng. | AU06 | ❌ 无（需人工标注或按候选段推定） |
| 3 | Starter | 同上 | I'm thirteen years old. | AU06 | ❌ 无 |
| 4 | Starter | 同上 | I want to make friends with you all! | AU06 | ❌ 无 |
| 5 | Unit 1 | Reading for writing A2（教材第 24 页，P29） | We want to share some thoughts with you. | AU13（101.4s） | ❌ 无 |

选择理由：全部为**教材原句**（逐字取自 content_block，P3-05 manifest 已逐句验证"在教材块内出现"）、**短**（2–9 词）、适合跟读；音频均为**活动级官方完整音频**（AU06 仅 43.4s，是 Starter+U1 里最短的活动音频，最适合区间播放）。

## 5. 每个句子的音频和时间定位依据

- **音频对应关系**：来自 `exercise_audio_map_v3.json` 的 CONFIRMED 映射（AU06 ↔ Starter/Get to know each other A4；AU13 ↔ Unit 1/Reading for writing A2）——**这是可靠的**。
- **时间定位**：**不可靠/不存在**（§3）。Spike 若要有 start/end，只能通过以下两条**不违反规范**的途径获得：
  1. **人工听标**（最小、可控）：在 43.4s 的 AU06 上人工标 4 句的 start/end，逐条记录"标注人 + 听标依据"，状态为 **CANDIDATE（manual_verified）**；
  2. **基于声学段的候选**：用 P3-01 已有的语音段列表给出候选区间，但 AU06 实测 **14 段 vs 8 句**（段数≠句数），无法自动 1:1 对应 → **仍须人工确认**。

## 6. Android 当前播放能力（只读检查）

| 项 | 实测 |
| --- | --- |
| 工程路径 | `D:\ZhixueEnglish\android`（根项目名 `ZhixueEnglishWebView`） |
| applicationId / namespace | **`com.zhixueenglish.app.dev`** |
| 源码 | **仅 1 个 Kotlin 文件**：`app/src/main/java/com/zhixueenglish/app/dev/MainActivity.kt`（Compose + `AndroidView{ WebView }` + `WebViewClient` + `BackHandler` + 加载状态/错误页） |
| WebView / 原生结构 | 纯 WebView 壳；不含原生学习逻辑、不含原生数据库 |
| 当前音频播放方式 | **仅 HTML5 `<audio>`**（Web 端 `ui.speaker()` 渲染 `/audio/official/*.mp3` 与 `/audio/word/*.wav`） |
| MediaPlayer / ExoPlayer / Media3 | **❌ 不存在**：依赖只有 compose-bom / activity-compose / material3 / ui / ui-graphics / ui-tooling-preview |
| S24+ 调试方式 | 无线 adb（`adb-R5CWC411C0K…_adb-tls-connect._tcp`，型号 **SM-S9260**）；WebView 指向 `http://192.168.2.3:8770/` |
| APK | `android/app/build/outputs/apk/debug/app-debug.apk`（10,862,249 B，2026-09-12 18:23:32）——**正式开发包与测试包是同一个 debug APK**（无独立正式发布包） |

**最小修改落点（仅建议，不实施）**：**Web 层**。理由：音频已由 Web 服务提供且支持 Range；WebView 的 `<audio>` 支持 `currentTime` 与 `timeupdate`；Android 侧零修改即可支撑区间播放 Spike。

## 7. "原音频 + 时间标记播放"可行性判断

### 方案 A（原始音频 + start_ms + end_ms → 播放指定区间）——**可行**

- 播放器侧：WebView 内的 HTML5 `<audio>` 支持 `audio.currentTime = start/1000; audio.play()`；用 `timeupdate` 监听 `currentTime >= end/1000` 时 `pause()`。
- 服务端侧：`/audio/official/<AUxx>.mp3` 已支持 Range（实测 206），**不需要切片、不需要转码**。
- 精度：`timeupdate` 触发间隔约 50–250ms，暂停误差通常在 ±0.1–0.25s 内——**对跟读完全够用**（宁可多留一点尾音）。
- 前置条件（唯一的硬约束）：**start/end 必须来自可靠标注**（人工听标或未来的本地对齐），否则就是"猜时间"，不许进入正式数据。

### 方案 B（播放器不能可靠自动停止时的最小办法）

1. `currentTime=start` → `play()` → **定时器兜底**（已知区间长度时 `setTimeout(pause, end-start)`）+ `timeupdate` 双保险；
2. 若定时器仍不稳：**只做"从 start 开始播放"**，由孩子自己按暂停（退化版，仍可用）；
3. 不推荐：引入 Media3/ExoPlayer 或任何新依赖（本阶段禁止安装；且对"区间播放"没有必要的增益）。

> 结论：**方案 A 在当前项目结构下可行，且最小改动落在 Web 层**；Android 工程与 54 个 MP3 均无需改动。

## 8. 下一步 Spike 最小实施方案（建议，未实施）

1. **数据**：在 `audit/P3-06_samples/`（或 P3-05 manifest 的扩展字段）为**4–5 句**补 `start_ms/end_ms`，来源标注为 `manual_verified`（人工听标）或 `candidate_silence`（未复核）；**不写入 contentpack、不建表**。
2. **UI**：在现有 `/unit/<slug>/shadowing` 卡片上加一个"**只听这一句**"按钮：
   - 有可靠区间的句子 → 按区间播放（seek + 自动停）；
   - 无区间的句子 → 保持现状（"听教材原音"整段播放），**不假装精确**。
3. **测试**：断言"有区间→出现区间播放入口"、"无区间→退化为整段"、"无自动播放/无评分"。
4. **真机**：S24+ 打开跟读页 → 点"只听这一句" → 确认只播该区间、可重复、无自动跳转。
5. **不做**：不切音频、不改 Android、不装依赖、不接 ASR、不做发音评分。

## 9. 风险与暂不解决的问题

| # | 风险/未解决项 | 说明 |
| --- | --- | --- |
| 1 | **时间标记来源** | 当前 0 条可靠句子级时间；Spike 必须自带人工听标（或明确标注 CANDIDATE），否则会变成"猜时间" |
| 2 | 精度 | `timeupdate` 粒度决定停止误差（±0.1–0.25s），句子首尾 ±0.2s 属于可接受范围，但需真机实测确认 |
| 3 | 长音频 | Unit 1 的 AU13 是 101.4s，区间播放体验取决于标注质量；建议 Spike 先用 43.4s 的 AU06 |
| 4 | 覆盖规模 | 只有 5 句标注 → 仍是**样本级**验证，不能视为"句库已建成" |
| 5 | ASR/强制对齐 | 仍未安装（P3-03 判定 D）；若要规模化标注，需用户批准后再评估 |
| 6 | 与 P3-05 的关系 | P3-05 的"整段原音跟读"仍然有效；区间播放是**增量**，不是替代（无区间时自动退化） |

---

**本次仅完成只读侦察，未修改任何文件、数据库、Android 工程或原始教材/音频。**（AI 调用 0，外部网络 0，未安装依赖，未生成中间文件。）

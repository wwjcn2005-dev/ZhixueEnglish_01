# P3-06 Step 2 实施报告（现有资产句级时间标记可行性只读审计）

> 只读审计：安装 0 / 下载 0 / AI 调用 0 / 正式数据修改 0 / 原始教材修改 0 / 原始 MP3 修改 0。

## 1. 审计结论

```
C —— 现有资产完全无法确定句级时间
```

现有资产可以确定：**句子属于哪个 MP3**、**它在教材印刷文本中的顺序（第 N 句）**；但**无法确定它在音频里的 start_ms / end_ms**。因此若要句级时间标记，必须进入自动对齐/转写工具评估。

## 2. 现有教材文字资产

| 资产 | 位置 | 形态 |
| --- | --- | --- |
| 教材内容块 | contentpack v5 `content_block`（3854 块，dialogue 132 / exercise_item 2133 / instruction 194 …） | 纯文本 + `page_id` + `reading_order` |
| 词条 | `learning_item`：288 vocabulary（CORE 244 / RECOGNITION 43）+ 23 phrase + 52 sentence_pattern | 文本 + 释义 + 音标 |
| 教材理解题 | `sub_question` 13 行 | 文本（按 `pdf_page`） |
| P3-05 句子清单 | `audit/P3-05_samples/shadowing_manifest.json` | 10 句教材原句 + `source_blocks` + `activity_no` + `audio_id`（**无时间字段**） |
| 转写/字幕 | `transcript` 表 **0 行**；全项目无 .srt/.vtt/.lrc/.txt/.xml 字幕或转写 sidecar | ❌ 不存在 |

**结论**：教材句子以"**文本 + 页码 + 阅读顺序**"保存，**没有任何时间维度的记录**。

## 3. 现有音频映射资产

| 资产 | 结论 |
| --- | --- |
| 54 个官方 MP3 | 41 条活动级 + 13 条板块级（7 词表 + 6 语音），SHA 与 contentpack 一致 |
| 映射可靠性 | `exercise_audio_map_v3.json` **54/54 CONFIRMED**（文件名指令 = 教材指令，相似度 0.99–1.00） |
| P3-05 句子 | 10 句，`audio_scope = FULL_ACTIVITY_AUDIO`（**只保证"属于这条活动音频"，不保证时间位置**） |
| AU06 / AU13 | AU06 ↔ Starter A4（43.4s）；AU13 ↔ Unit 1 RfW A2（101.4s） |

**回答**：✅ 能精确知道"某句属于哪个 MP3"，✅ 能知道它在教材文本中的句子序号；❌ **不能**知道它在音频中的时间位置。

## 4. 288 条时间标记的真实来源

| 项 | 结论 |
| --- | --- |
| 文件 | `structured/audio/derived/word_audio_manifest.json`（+ 288 个 WAV 于 `structured/audio/derived/words/`） |
| 生成器 | `builder/build_word_audio_v01.py`（**离线静音切分**：10ms RMS 包络、自适应阈值、MIN_GAP 200ms） |
| 对应对象 | **官方词表音频（AU48–AU54，7 条 Words and expressions）中逐词读出的单个单词**（Starter 32 / U1 35 / U2 45 / U3 40 / U4 45 / U5 46 / U6 45 = 288） |
| 是否官方 | ❌ 派生资源（manifest 自述 `derived_from_official_unit_audio`，非官方独立单词音频） |
| 能否组合成句级时间 | ❌ **不能**。两条硬理由：① 它们来自**词表音频**，与 AU06/AU13 等**对话/朗读音频是不同文件**，时间轴互不通用；② 词表里是孤立单词，不存在"句子中的连续词序列"可供求和 |

> 例：Starter 词表第 1 条 `ready = 5550–6240ms`，指的是 AU48 里朗读单词 "ready" 的位置，**不是** AU06 中任何句子的位置。

## 5. 已有时间/对齐代码

| 文件 | 函数 | 输入 → 输出 | 能否复用于句级 | 说明 |
| --- | --- | --- | --- | --- |
| `builder/build_word_audio_v01.py` | `envelope()` / `segments()` / `load_pcm()` | WAV → 静音语音段列表 | ❌ | 纯声学分段；P3-06 第二阶段已证伪其单用价值（AU06 8 句 vs 14/13/12/10 段） |
| `builder/verify_word_audio_v01.py` | 校验 | manifest ↔ WAV | ❌ | 只做词音频校验 |
| `audit/P3-01_tmp/p301_analyze.py` | 同上的离线分析 | MP3→WAV→语音段 | ❌ | 同上（临时脚本） |
| 全项目检索 `start_ms/end_ms/timestamp/word_timestamp/alignment/align/transcript/audio_position` | — | — | ❌ | **除词表派生 manifest 外，没有任何文本↔音频对齐代码**；`transcript` 表 0 行 |

**结论**：项目里**不存在**"把已知文本对到音频时间轴"的代码（无论是否启用）。

## 6. AU06 四句可行性判断

| 句子 | 是否已有时间信息 | 能否确定 start_ms | 能否确定 end_ms | 依据 |
| --- | --- | --- | --- | --- |
| Hello everyone! | ❌ | ❌ | ❌ | 仅知属 AU06（43.4s）与"第 1 句"；P3-02 的 560–2090ms 为**未复核候选**，且 SAPI 结果（7430ms）与之矛盾 |
| My name is Zhu Xiaomeng. | ❌ | ❌ | ❌ | 同上；SAPI 报 730ms、P3-02 静音法无对应关系 |
| I'm thirteen years old. | ❌ | ❌ | ❌ | 同上；SAPI 报 560ms（与第 1 句冲突） |
| I want to make friends with you all! | ❌ | ❌ | ❌ | 同上；SAPI 未命中 |

**缺少的关键数据（唯一缺口）**：**一份带时间戳的转写（word/segment-level transcript）**。没有它，教材文本与音频时间之间没有桥。

## 7. 是否需要 Whisper

```
需要（若目标是句级时间标记）
```

理由：现有一切资产（文本、映射、词表派生时间）都无法确定句级 start/end；SAPI 已被证明不可靠并 STOP；因此要落地"原始 MP3 + start_ms/end_ms 区间播放"，只剩"人工听标"或"本地 Whisper 类模型（提供 word timestamps）"两条路。人工不可扩展 → **需要 Whisper 类工具**（安装与模型下载须由项目负责人批准）。

## 8. 下一步唯一建议

**只做一件事**：批准一次"**离线 Whisper 可行性评估**"（先评估，不安装）——列出可用的本地方案（faster-whisper / whisper.cpp）、所需模型大小与下载量、在当前硬件（i5-14400F + 16GB + GTX 1070 4GB）上的预期速度、以及是否支持 word-level timestamps；评估完成后再由你决定是否安装。

> 在此之前不进入任何开发、不批量生成时间标记、不修改任何正式数据。

## 数据安全确认

```
installs: 0
downloads: 0
Cloud AI calls: 0
formal data modified: 0
original textbook: unchanged
original MP3: unchanged
```

本次为只读审计，完成后立即停止。

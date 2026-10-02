# P3-06 Step 8A AU13 Existing Assets Audit

> 只读审计：未修改任何代码 / JSON / MD / DB / contentpack / 教材 / MP3 / Android；**未运行 Faster-Whisper**、未安装依赖、未下载模型、未调用云端 AI、未生成切片、未批处理。

## 1. 审计结论

```
PASS
```

### 情况 B

> **AU13 当前不存在可直接复用的可靠句子级/逐词时间戳资产。**

AU13 的**音频归属**与**教材文本**都是现成且可靠的；缺的只有一样：**AU13 自己的时间轴**（word/segment/sentence 级时间戳、transcript、alignment 结果均不存在）。

## 2. AU13 基本信息

| 项目 | 结果 |
| --- | --- |
| audio_id | `FLTRP-EN-7A-2022CUR:AU13` |
| 文件 | `13_Unit 1_Developing ideas _Reading for writing_2 Read the passage and find out the meaning of the title.mp3` |
| 相对路径 | `2025年度初一外研版英语教材/13_Unit 1_Developing ideas _Reading for writing_2 Read the passage and find out the meaning of the title.mp3` |
| 完整路径 | `D:\ZhixueEnglish\2025年度初一外研版英语教材\13_Unit 1_Developing ideas _Reading for writing_2 Read the passage and find out the meaning of the title.mp3` |
| 文件大小 | 2,433,836 B（≈2.43 MB），SHA256 `DE4BCEC92B8E9293…`（与 contentpack 记录一致） |
| 时长 | **101,381 ms（≈101.4 s）**（`exercise_audio_map_v3` 记录 101,407 ms，同一文件两种口径） |
| Module / Unit | **Unit 1** |
| Section | **READING_FOR_WRITING**（教材"Reading for writing"） |
| Activity | **A2** — *Read the passage and find out the meaning of the title.* |
| Page | PDF 第 29 页 ／ **教材第 24 页** |
| audio_scope | **activity**（活动级官方完整音频） |
| 映射状态 | `exercise_audio_map_v3.json`：**status = CONFIRMED**（文件名指令与教材指令一致）；关联练习 `FLTRP-EN-7A-2022CUR:X:EF894C270C5B` |
| 教材来源 | Unit 1 / Reading for writing / A2（contentpack `content_block` 第 29 页文本块） |

## 3. 现有时间戳资产（逐项判定）

| 资产类型 | 是否存在 | 说明 |
| --- | --- | --- |
| AU13 word-level timestamp | **不存在** | Step 4 的 word timestamps 只跑过 **AU06**（`P3-06_step4_au06_alignment_result.json` 仅含 AU06） |
| AU13 segment-level timestamp | **不存在** | 同上；AU13 从未做过转写 |
| AU13 sentence-level timestamp | **不存在** | `P3-06_samples/shadowing_samples.json` 中 AU13 条目（P3-06-S005）为 `start_ms: null / end_ms: null / timing_source: unverified` |
| AU13 transcript | **不存在** | 全项目 `transcript` 表 0 行；无任何 .srt/.vtt/.txt/.json 字幕或转写文件与 AU13 绑定 |
| AU13 alignment result | **不存在** | `audit/P3-03_local_alignment_technology_validation.json`、`P3-02_sentence_audio_alignment_validation.json` 中 AU13 只作为**待处理样本**出现，无对齐结果 |
| AU13 shadowing candidate | **存在（仅文本，无时间）** | P3-05 manifest 有 2 条 AU13 教材句（见 §4）；P3-02 的 S5 条目判定为 NEEDS_REVIEW（文本有提取瑕疵） |
| AU13 VERIFIED 数据 | **不存在** | `audit/P3-06_au06_verified_sentences.json` **只含 AU06**；AU13 未进入 VERIFIED |
| AU13 声学分析（辅助） | 存在但与句级无关 | `audit/P3-01_tmp/p301_audio_analysis.json` 有 AU13 的静音分组（**42 组 / 9 句**，段数≠句数），P3-01 已判定不可用于句级定位 |

**与 AU13 无关的既有时间资产**：`structured/audio/derived/word_audio_manifest.json`、`audit/P3-06_step4_au06_alignment_result.json`、`audit/P3-06_au06_verified_sentences.json`。

## 4. 教材句子资产（权威文本）

目前项目中对 AU13 活动（Unit 1 / Reading for writing / A2）**已存在的权威教材句子共 2 条**（来源：`audit/P3-05_samples/shadowing_manifest.json`，文本逐字取自 contentpack `content_block`）：

| # | textbook sentence | speaker | sentence_id |
| ---: | --- | --- | --- |
| 1 | Yes, and it's also a letter from Mum and me. | Dad | P3-05-S009 |
| 2 | We want to share some thoughts with you. | — | P3-05-S010 |

该 Activity 的教材页（PDF P29）正文实际含约 10 个句段（含 `Mia Don't worry.`、`We've got something for you!`、`Look!`、`Well, I'm a little nervous.`、`Mum MiaA paper boat?`（提取瑕疵）、`Oh, thank you!` 等）。**其中两条存在明显的说话人标签粘连与重复片段**（`Mum MiaA paper boat?` / `MiaA paper boat?`），因此该页文本目前**不能整页直接用于逐句对齐**，需要先做文本清理（人工核验），这是 AU13 相对 AU06 的额外风险点。

> 教材原文最高优先：任何 ASR/Whisper 输出（例如把 `I'm thirteen years old.` 写成 `I'm 13 years old.`）**不得**回写教材文本。

## 5. 重要排除项

> **`structured/audio/derived/word_audio_manifest.json` 中的 288 条时间数据属于 Vocabulary Audio，不属于 AU13 Lesson/Listening 音频，因此本审计不将其作为 AU13 时间戳资产。**

同理，AU48–AU54（Words and expressions 词表音频）与其派生 WAV 全部与 AU13 无关；AU06 的 Step 4/Step 7 成果也**不能**平移到 AU13（不同音频、不同时间轴）。

## 6. 下一步建议

> **建议下一步进入 P3-06 Step 8B：仅对 AU13 使用已经部署在 `D:\ZhixueEnglish\tools\faster_whisper_venv` 中的 Faster-Whisper 进行离线候选时间戳生成。执行前等待明确批准。**

补充两点建议（供批准时参考）：
1. Step 8B 应**先做 AU13 的教材页文本清理/人工核验**（去掉说话人标签粘连与重复片段），否则逐句匹配会命中错误区间；
2. 建议 Step 8B 只产出 **CANDIDATE**（沿用 Step 4→Step 6 的流程），人工试听后才允许进入 VERIFIED。

## 7. 最终输出摘要

1. **PASS / FAIL**：**PASS**
2. **是否发现 AU13 可复用时间戳**：**未发现**（情况 B）
3. **AU13 基本信息**：Unit 1 / READING_FOR_WRITING / A2 ｜ 教材第 24 页 ｜ 101.4 s ｜ activity 级官方完整音频 ｜ CONFIRMED
4. **权威句子数量**：P3-05 中 **2 条**（该教材页实际约 10 个句段，其中 2 条有提取瑕疵）
5. **是否需要 Step 8B**：**需要**（待你明确批准后才运行）
6. **审计报告路径**：`D:\ZhixueEnglish\audit\P3-06_step8A_AU13_existing_assets_audit.md`

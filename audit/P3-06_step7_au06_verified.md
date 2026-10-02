# P3-06 Step 7：AU06 VERIFIED 固化报告

## 1. 结论

```
PASS
```

AU06 的 **8 条正文句子**已完成人工试听确认，正式固化为 **VERIFIED**，并保存为独立审计数据：

`audit/P3-06_au06_verified_sentences.json`

## 2. 人工验证

> **AU06 测试页面实际试听通过。**
> **第 5 句开头有轻微前一句尾音，但不影响使用，因此不调整边界。**

记录进 JSON 的原文：
> 人工试听确认。第 5 句开头存在极轻微前一句尾音，但不影响辨识、标准音听感及跟读使用，因此保留原候选边界，不人为裁剪。

## 3. VERIFIED 表（8 条）

| # | 教材原句 | start_ms | end_ms | duration_ms | status |
| ---: | --- | ---: | ---: | ---: | --- |
| 1 | Hello everyone! | 7000 | 8540 | 1540 | VERIFIED |
| 2 | My name is Zhu Xiaomeng. | 9220 | 12880 | 3660 | VERIFIED |
| 3 | I'm thirteen years old. | 13360 | 16200 | 2840 | VERIFIED |
| 4 | My birthday is in May. | 17260 | 19620 | 2360 | VERIFIED |
| 5 | I love sports very much. | 19620 | 23580 | 3960 | VERIFIED |
| 6 | I like running, playing football and swimming. | 24380 | 29500 | 5120 | VERIFIED |
| 7 | I'm a bit nervous now, but I'm also happy to meet you. | 30580 | 36140 | 5560 | VERIFIED |
| 8 | I want to make friends with you all! | 37000 | 40040 | 3040 | VERIFIED |

**`start_ms / end_ms` 与 Step 6 完全一致，未做任何改动**；`duration_ms` 一律按 **`end_ms - start_ms`** 取整（1540 / 3660 / 2840 / 2360 / 3960 / 5120 / 5560 / 3040）。

**教材文字来源**：`audit/P3-05_samples/shadowing_manifest.json`（authoritative textbook text）——因此固化文本采用 P3-05 的原样写法：

- 第 1 句 `Hello everyone!`（Step 6 报告中显示为 `Hello everyone.`）
- 第 3 句 `I'm thirteen years old.`（Step 6/任务书表格中显示为 `I'm 13 years old.`）
- 第 8 句 `I want to make friends with you all!`

> 说明：以上 3 处**仅是标点/数字写法差异，不是句子内容差异**；按任务要求"教材文字必须与 P3-05 authoritative manifest 一致"，**以 P3-05 文本为准**，Whisper 文本与任务书表格均不改变教材原文。已通过程序逐字比对：8/8 与 P3-05 完全一致。

## 4. 数据检查（自动校验，全部通过）

| 检查项 | 结果 |
| --- | --- |
| 1 数量 = 8 | ✅ 8 |
| 2 顺序 1→8 | ✅ `sentence_index` 严格递增且连续 |
| 3 时间合法性 | ✅ 全部 `start_ms ≥ 0`、`end_ms > start_ms`、`duration_ms == end_ms - start_ms` |
| 4 相邻不重叠 | ✅ 全部 `next.start_ms ≥ previous.end_ms`（含第 4→5 句 19620 == 19620，0 ms gap 原样保留） |
| 5 教材文字一致 | ✅ 8/8 与 P3-05 manifest **逐字相同** |
| 6 状态 | ✅ 8/8 = `VERIFIED` |
| 7 instruction 排除 | ✅ `Activity 4. Read and check your answers.`（0–5140 ms）仅记录为 `instruction / non_training_sentence`，**不在 8 条正文句中** |

## 5. 数据安全

```
learning.db 未修改            PASS
contentpack 未修改            PASS
原始教材 / 原始 MP3 未修改     PASS（未切割、未复制、未移动、未重命名）
P3-05 manifest 未修改         PASS
Android 未修改                PASS
正式学习业务逻辑未修改         PASS
Whisper 未重新运行            PASS
AI 调用                       0
```

## 6. 可追溯信息（JSON 内已保存）

- `audio_id`: `FLTRP-EN-7A-2022CUR:AU06`
- `audio_url`: `/audio/official/AU06.mp3`（Web 播放通道）
- `audio_file`: `06_Starter_Get to know each other_4 Read and check your answers.mp3`
- `audio_relative_path`: `2025年度初一外研版英语教材/06_Starter_Get to know each other_4 Read and check your answers.mp3`（**未硬编码 `AU06.mp3`，使用项目真实映射**）
- `activity` / `unit` / `section` / `textbook_page`: Activity 4 ｜ Starter ｜ GET_TO_KNOW_EACH_OTHER ｜ 第 10 页
- `audio_scope`: `FULL_ACTIVITY_AUDIO`
- `source`: `faster-whisper-word-timestamps`；`source_steps`: Step 4 JSON + Step 6 报告
- `text_source`: P3-05 authoritative manifest；`verification.method`: `human_listening`
- 每条句子另带 `speaker`、`source_blocks`（教材内容块 id），可回溯到教材原文

## 7. 最终验收

```
P3-06 AU06

8 sentences
8 VERIFIED
0 overlap
0 data loss
0 original audio changes
0 formal DB changes
0 AI calls

=> PASS
```

**未进入 AU13、未批量处理、未修改规范文件、未继续下一阶段开发。**

> 注：AU06 测试页面（`/p3-06/au06-test`）按任务要求**保持不动**；其数据源 `audit/p3_06/au06_test_candidates.json` 仍显示 `CANDIDATE`，本次只新增 VERIFIED 归档，不改动测试页。

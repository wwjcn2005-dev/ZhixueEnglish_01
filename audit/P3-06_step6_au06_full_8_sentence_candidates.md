# P3-06 Step 6：AU06 完整 8 句候选补全报告

> 未重新运行 Whisper、未下载模型、未安装依赖、未调用云端 AI、未修改 learning.db / contentpack / 原始 MP3 / P3-05 / Android；未处理 AU48–AU54 与 288 条词汇时间标记；未批量处理其他音频。结果全部为 **CANDIDATE**，无 VERIFIED。

## A. 执行结论

```
PASS
```

AU06 已形成**完整 8 句**候选时间表：8/8 命中、词级匹配率 100%、start_ms 严格单调递增、**零重叠**；Step 5 中 8,180 ms 的大 gap 已被新增两句合理填充（现最大 gap 1,080 ms）。

## B. 输入文件

| 文件 | 用途 |
| --- | --- |
| `audit/P3-06_step4_au06_alignment_result.json` | **唯一时间来源**：55 个 word-level timestamps（未使用 segment 边界） |
| `audit/P3-06_step5_au06_candidate_recheck.md` | Step 5 已确认的 6 条候选（用于一致性比对） |
| `audit/P3-05_samples/shadowing_manifest.json` | **教材原句顺序与文本来源**（Starter Activity 4，逐字取自 content_block） |

> 顺序核对：P3-05 manifest 的顺序为 ①Hello everyone. ②My name is Zhu Xiaomeng. ③I'm thirteen years old. ④My birthday is in May. ⑤I love sports very much. ⑥I like running, playing football and swimming. ⑦I'm a bit nervous now, but I'm also happy to meet you. ⑧I want to make friends with you all. —— **与本次任务书给出的编号完全一致**，未做任何调整。

## C. AU06 完整 8 句候选表

| 顺序 | 教材原句 | start_ms | end_ms | duration_ms | matched_words | match_score | status |
| ---: | --- | ---: | ---: | ---: | --- | --- | --- |
| 1 | Hello everyone. | 7000 | 8540 | 1539 | Hello everyone. | 2/2 | CANDIDATE |
| 2 | My name is Zhu Xiaomeng. | 9220 | 12880 | 3660 | My name is Zhu Xiaomeng. | 5/5 | CANDIDATE |
| 3 | I'm 13 years old. | 13360 | 16200 | 2840 | I'm 13 years old. | 5/5 | CANDIDATE |
| **4** | **My birthday is in May.** | **17260** | **19620** | **2359** | **My birthday is in May.** | **5/5** | **CANDIDATE（本次新增）** |
| **5** | **I love sports very much.** | **19620** | **23580** | **3959** | **I love sports very much.** | **5/5** | **CANDIDATE（本次新增）** |
| 6 | I like running, playing football and swimming. | 24380 | 29500 | 5120 | I like running, playing football and swimming. | 7/7 | CANDIDATE |
| 7 | I'm a bit nervous now, but I'm also happy to meet you. | 30580 | 36140 | 5560 | I'm a bit nervous now, but I'm also happy to meet you. | 14/14 | CANDIDATE |
| 8 | I want to make friends with you all. | 37000 | 40040 | 3039 | I want to make friends with you all. | 8/8 | CANDIDATE |

（另有 `Activity 4. Read and check your answers.` @ 0–5140 ms，属 **instruction / non_training_sentence**，不进入跟读句表。）

## D. 8 句连续性检查

| 边界 | 前句 end_ms | 后句 start_ms | gap_ms | overlap |
| --- | ---: | ---: | ---: | --- |
| 1 → 2 | 8540 | 9220 | 680 | 无 |
| 2 → 3 | 12880 | 13360 | 480 | 无 |
| **3 → 4** | 16200 | 17260 | **1060** | 无 |
| **4 → 5** | 19620 | 19620 | **0** | 无（首词与末词时间戳相接，需人工听一次确认不粘连） |
| **5 → 6** | 23580 | 24380 | **800** | 无 |
| 6 → 7 | 29500 | 30580 | 1080 | 无 |
| 7 → 8 | 36140 | 37000 | 860 | 无 |

- **start_ms 单调递增**：✅（7000 < 9220 < 13360 < 17260 < 19620 < 24380 < 30580 < 37000）
- **end_ms > start_ms**：✅ 全部成立
- **相邻句重叠**：✅ **零重叠**
- **异常空白**：✅ **无**——Step 5 的 8,180 ms 空白已被新增两句填满，现最大 gap 仅 1,080 ms
- **正文覆盖**：✅ 从 7.0 s（首句）连续覆盖到 40.04 s（末句），与人工听音（正文约 0:07 开始）一致

## E. 两句新增候选重点分析

**④ `My birthday is in May.` → 17260 – 19620 ms（2359 ms），5/5 词匹配，CANDIDATE**
- 匹配到的 ASR 词：`My birthday is in May.`（逐词完全一致）
- 位置落在原 gap 的前半段；与前句（`I'm 13 years old.` 结束 16200）间隔 1060 ms，与后句（19620）首尾相接；
- `May` 未与其他词混淆（该区间内 ASR 词表中仅有这一个 `May`）。

**⑤ `I love sports very much.` → 19620 – 23580 ms（3959 ms），5/5 词匹配，CANDIDATE**
- 匹配到的 ASR 词：`I love sports very much.`（逐词完全一致）
- 位置紧接第 4 句，覆盖原 gap 的后半段；与后句（`I like running…` 起始 24380）间隔 800 ms；
- `sports` 未误配到其他句子（全词表仅出现一次）。

> 两句合计覆盖 17260–23580 ms，正好填满原 16200–24380 ms 的空白 ✔

## F. 与 Step 5 的一致性

Step 5 的 6 条候选**完全未变**（逐字段比对一致）：

| 句子 | Step 5 | Step 6 | 是否变化 |
| --- | --- | --- | --- |
| Hello everyone. | 7000–8540 | 7000–8540 | 无 |
| My name is Zhu Xiaomeng. | 9220–12880 | 9220–12880 | 无 |
| I'm 13 years old. | 13360–16200 | 13360–16200 | 无 |
| I like running, playing football and swimming. | 24380–29500 | 24380–29500 | 无 |
| I'm a bit nervous now, but I'm also happy to meet you. | 30580–36140 | 30580–36140 | 无 |
| I want to make friends with you all. | 37000–40040 | 37000–40040 | 无 |

原因：本次仍使用同一份 Step 4 word timestamps、同一套归一化与连续窗口匹配规则；新增两句只是在原空白区间内新增匹配，不影响既有匹配结果。

## G. 最终结论

> **AU06 已经形成完整 8 句、可供人工一次性确认的候选时间表。**

**仍需人工听音确认的 3 处**：① 第 4 句与第 5 句之间 gap = 0 ms（时间戳相接，确认是否粘连）；② 各句句尾是否含呼吸/连读尾音；③ 第 1 句起点 7000 ms 之前是否还有正文残音（人工已听确认正文约 0:07 开始，与此一致）。确认后即可把 8 条从 `CANDIDATE` 升级为 `VERIFIED`。

**不进入 Step 7**，不批量处理，不写入正式数据。

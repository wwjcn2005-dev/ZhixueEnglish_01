# P3-06 Step 8C AU13 练习句完整化与题库映射审计

> 只读审计 + 候选资源生成。
> 未修改正式题库 / learning.db / contentpack / P3-05 / Android / 原始教材 / 原始 MP3；未重新运行 Faster-Whisper；未切音频；未调用云端 AI。

## 1. AU13 对话 9 句检查结果

Step 8B 的 9 句全部直接复用，时间保持 `CANDIDATE`。教材原始呈现均为完整句，无挖空。

| # | 教材原句 | start_ms | end_ms | text_mode | timing_status | exercise_type 候选 |
| ---: | --- | ---: | ---: | --- | --- | --- |
| 1 | Mia, how do you feel about your first day in junior high tomorrow? | 13940 | 20260 | COMPLETE | CANDIDATE | SHADOWING / LISTEN_AND_REPEAT |
| 2 | Well, I'm a little nervous. | 21080 | 24300 | COMPLETE | CANDIDATE | LISTEN_AND_SAY / LISTEN_AND_REPEAT |
| 3 | Don't worry. | 25200 | 26280 | COMPLETE | CANDIDATE | LISTEN_AND_SAY / LISTEN_AND_REPEAT |
| 4 | We've got something for you! | 26900 | 28940 | COMPLETE | CANDIDATE | LISTEN_AND_SAY / LISTEN_AND_REPEAT |
| 5 | Look! | 28940 | 29720 | COMPLETE | CANDIDATE | LISTEN_AND_SAY / LISTEN_AND_REPEAT |
| 6 | A paper boat? | 30840 | 32400 | COMPLETE | CANDIDATE | LISTEN_AND_SAY / LISTEN_AND_REPEAT |
| 7 | Yes, and it's also a letter from Mum and me. | 33380 | 38300 | COMPLETE | CANDIDATE | SHADOWING / LISTEN_AND_REPEAT |
| 8 | We want to share some thoughts with you. | 39040 | 41600 | COMPLETE | CANDIDATE | SHADOWING / LISTEN_AND_REPEAT |
| 9 | Oh, thank you! | 42280 | 44420 | COMPLETE | CANDIDATE | LISTEN_AND_SAY / LISTEN_AND_REPEAT |

**结论**：对话 9/9 为 `COMPLETE`；对话填空题 0 条；不修改任何教材原句。

## 2. 哪些句子属于填空 / 不完整呈现

在 AU13 对应的教材原始页面（A2: Read the passage and find out the meaning of the title.）中：

```text
确认的填空句：0 条
确认的不完整句：0 条
```

原始教材的 A2 是“阅读整篇 passage”，不是填空练习；对话和书信正文都有完整标点与完整句义。

现有结构化题库中确实出现了 `question_type = fill`、`blank_count = 12` 等记录，但这来自题目重建阶段的**误分类/抽取污染**，不是教材实际呈现形式。具体见附录“题库映射审计发现”。

## 3. 每个填空句的教材原始形式

无确认的填空句。

| # | 教材原始形式 | 完整学习句 | 状态 |
| ---: | --- | --- | --- |
| — | 无挖空 | 不适用 | 0 条 |

教材上出现 `1` / `2` / `3` 的书信段落编号，以及 `1 Reading for writing` / `2` 的活动编号，均为版式编号，不是填空符。

## 4. 恢复后的完整学习句

本步骤没有“从挖空恢复完整句”的结果，因为原始教材没有挖空。

本步骤建立的完整学习句来源只有两类：

1. AU13 对话 9 句：教材完整句，直接复用 Step 8B 文本与候选时间。
2. AU13 书信正文 14 句：教材完整句，按原始 PDF p30 的段落与标点拆分，时间标记为 `TIMING_PENDING`。

## 5. 恢复依据

没有任何一句是通过猜测恢复的。

| 类型 | 依据 |
| --- | --- |
| 对话句 | 原始 PDF p29 + contentpack P29 content_block + Step 8B-0 权威文本核验 |
| 书信句 | 原始 PDF p30 + contentpack P30:B0–B4 |
| 说话人归属 | PDF 坐标中的独立说话人标签（Dad / Mia / Mum），不并入正文 |
| 音频时间 | 对话直接复用 Step 8B 句级候选；书信仅登记已有 word-level 资产，留待后续单独对齐；本步骤不重新运行 Whisper |

唯一需要“纠正”的对象是文本抽取层，不是教材：

- `MiaA paper boat?` → `Mia` + `A paper boat?`
- `Mum MiaA paper boat?` → `Mum` + `Mia` + `A paper boat?`
- `Before your Before your journey starts journey starts` → `Before your journey starts`
- `UNIT 1 24 UNIT 1` / `new start 25` → 页眉页脚，不是学习正文

## 6. 对话官方音频时间

全部直接复用 Step 8B 的 9 条候选时间：

| # | start_ms | end_ms |
| ---: | ---: | ---: |
| 1 | 13940 | 20260 |
| 2 | 21080 | 24300 |
| 3 | 25200 | 26280 |
| 4 | 26900 | 28940 |
| 5 | 28940 | 29720 |
| 6 | 30840 | 32400 |
| 7 | 33380 | 38300 |
| 8 | 39040 | 41600 |
| 9 | 42280 | 44420 |

原始音频路径：

```text
D:\ZhixueEnglish\2025年度初一外研版英语教材\13_Unit 1_Developing ideas _Reading for writing_2 Read the passage and find out the meaning of the title.mp3
```

## 7. 书信正文完整句子清单

来源：原始 PDF 第 30 页 / 教材第 25 页。

`Dear Mia,` 是称呼；`With love, Dad and Mum` 是署名。两者均不进入训练句候选。

| # | 书信正文学习句 | 段落 | timing_status | exercise_type 候选 |
| ---: | --- | --- | --- | --- |
| 1 | Time flies! | 1 | TIMING_PENDING | LISTEN_AND_SAY / LISTEN_AND_REPEAT |
| 2 | You are now in junior high! | 1 | TIMING_PENDING | SHADOWING / LISTEN_AND_REPEAT |
| 3 | Are you ready for your new life? | 1 | TIMING_PENDING | SHADOWING / LISTEN_AND_REPEAT |
| 4 | Primary school is like a small pool. | 2 | TIMING_PENDING | SHADOWING / LISTEN_AND_REPEAT |
| 5 | Your boat is safe there. | 2 | TIMING_PENDING | SHADOWING / LISTEN_AND_REPEAT |
| 6 | Dad and Mum can protect it from winds. | 2 | TIMING_PENDING | SHADOWING / LISTEN_AND_REPEAT |
| 7 | But junior high is like a river. | 2 | TIMING_PENDING | SHADOWING / LISTEN_AND_REPEAT |
| 8 | It is wide and the water moves fast. | 2 | TIMING_PENDING | SHADOWING / LISTEN_AND_REPEAT |
| 9 | You will face new problems. | 2 | TIMING_PENDING | SHADOWING / LISTEN_AND_REPEAT |
| 10 | We are still here to help. | 2 | TIMING_PENDING | SHADOWING / LISTEN_AND_REPEAT |
| 11 | But sometimes you have to sail your boat by yourself. | 2 | TIMING_PENDING | SHADOWING / LISTEN_AND_REPEAT |
| 12 | Just try your best and work hard. | 2 | TIMING_PENDING | SHADOWING / LISTEN_AND_REPEAT |
| 13 | You will go through storms towards the sea. | 2 | TIMING_PENDING | SHADOWING / LISTEN_AND_REPEAT |
| 14 | We hope this letter helps you in the coming years! | 3 | TIMING_PENDING | SHADOWING / LISTEN_AND_REPEAT |

**书信正文数量**：14 句；全部 `COMPLETE`；填空句 0 条。

## 8. 哪些书信句子已有时间

```text
已有 sentence-level start_ms / end_ms：0 条
```

本步骤按任务边界，没有把 Step 8B 的 word-level timestamps 转成书信句级时间；因此 14 句全部为 `TIMING_PENDING`。Step 8B 原始结果中确实保留了书信部分的 word-level 时间，可在下一步单独进行对齐，不需要重新运行 Whisper。

## 9. 哪些书信句子需要后续时间对齐

全部 14 句都需要后续时间对齐：

```text
AU13-LTR-01 ... AU13-LTR-14
```

建议下一步只做“利用既有 Step 8B word-level timestamps 进行书信句级候选对齐”，不要重新转写。

## 10. 候选题库资源数量

```text
候选资源总数：23
  对话候选：9（timing_status = CANDIDATE）
  书信候选：14（timing_status = TIMING_PENDING）
VERIFIED：0
正式题库写入：0
```

每条资源均包含：

```text
source
audio_id
original_audio_path
unit
section
activity
textbook_text
learning_text
text_mode
start_ms
end_ms
timing_status
exercise_type
source_page
status = CANDIDATE_EXERCISE_RESOURCE
```

## 11. 每条资源的 exercise_type 候选

本步骤只记录候选题型，不决定正式题型。

| 资源组 | 数量 | exercise_type 候选 |
| --- | ---: | --- |
| 对话正文句 | 9 | `SHADOWING`、`LISTEN_AND_REPEAT`、`LISTEN_AND_SAY` |
| 书信正文句 | 14 | `SHADOWING`、`LISTEN_AND_REPEAT`、`LISTEN_AND_SAY` |
| `COMPLETE_THE_SENTENCE` | 0 | 没有挖空，不能因为“完整句可用于学习”就将其当作填空题答案 |

特别是：恢复的完整句不等于题目答案。本次没有任何句子经过“填空 → 完整句”恢复，因此没有向正式题库写入答案，也没有把完整句当作答案。

## 12. 正式题库是否修改

```text
正式题库修改：0
learning.db 修改：0
contentpack 修改：0
原始教材修改：0
原始 MP3 修改：0
Android 修改：0
AI / cloud calls：0
Whisper rerun：0
VERIFIED：0
```

## 附：题库映射审计发现

AU13 当前在结构化题库中关联到：

```text
exercise_id: FLTRP-EN-7A-2022CUR:X:EF894C270C5B
activity_id: A:46D86F27A64D
instruction: Read the passage and find out the meaning of the title.
audio_id: FLTRP-EN-7A-2022CUR:AU13
audio_status: CONFIRMED
```

现有 4 条关联 question 记录：

| question_id | 现有文本范围 | 现有类型 | 审计结论 |
| --- | --- | --- | --- |
| Q:CB78B3F25CC8 | 标题 + 对话正文 | fill / blank_count 12 | **误判**：不是填空题 |
| Q:6BE4FE7DFF83 | 书信第 1 段 | fill / blank_count 12 | **误判**：不是填空题 |
| Q:471FFC6481AF | 书信第 2 段 | fill / blank_count 12 | **误判**：不是填空题 |
| Q:2ACC8C15EAA1 | 书信第 3 段 + 署名 + 页脚 | fill / blank_count 12 | **误判**：不是填空题 |

误判来源包括：

1. 把整段阅读正文当作填空 question；
2. 把段落编号 `1/2/3` 或活动编号 `2` 误计为 blank；
3. 把 `paper boat?`、`new start 25` 等文本碎片误当作 options；
4. 页眉页脚 `UNIT 1 24 UNIT 1`、`A new start 25` 混入文本。

本步骤只记录为 `FALSE_POSITIVE_EXTRACTION_ARTIFACT`，不修改正式题库。

## 最终状态

```text
PASS
```

理由：

- AU13 对话 9 句已检查，全部是完整句；
- AU13 书信正文 14 句已按原始教材确认；
- 教材原始呈现中没有挖空/incomplete sentence；
- 题库中的 fill 记录已识别为抽取误判，没有被当作正式答案；
- 23 条候选题库资源已生成；
- 9 条有时间候选，14 条明确标记 `TIMING_PENDING`；
- 所有条目保持 `CANDIDATE_EXERCISE_RESOURCE`，没有 VERIFIED，没有写入正式题库；
- 未修改任何正式数据，未重跑 Whisper，AI/cloud calls = 0。

## 输出文件

- `D:\ZhixueEnglish\audit\P3-06_step8C_AU13_practice_mapping_audit.md`
- `D:\ZhixueEnglish\audit\P3-06_step8C_AU13_practice_candidates.json`

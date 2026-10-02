# P3-06 Step 9 全教材听力不完整文本 × 官方完整音频只读普查

> 只读审计。未修改 learning.db、正式题库、contentpack、P3-05、Android、原始教材、原始 MP3；未切音频；未重跑 Whisper；未调用云端 AI；未使用 AI 猜测缺失文字。

## 1. 结论

```text
PASS（完成全教材只读普查）
```

核心结果：

```text
B 类候选活动：14 个
B 类候选句槽：76 条
B 类已恢复完整学习句：0 条
B 类可以直接进入本地题库资源候选：0 条
B 类需要人工 / 后续授权审核：76 条
```

必须明确区分：

1. 这 14 个听力活动在教材纸面上确实有填空/挖空，官方 MP3 也是活动级完整录音，因此属于 B 类候选活动。
2. 但当前项目没有官方答案稿、听力原文或 transcript；本步骤又禁止重跑 Whisper，所以不能凭空补出 76 个缺失词。
3. 因此这 76 条是“B 类候选句槽”，不是已经恢复完成的 76 条学习句。`learning_text` 保持 `null`，状态为 `UNVERIFIED`。

## 2. 扫描范围

| 项目 | 结果 |
| --- | ---: |
| 教材原始根目录 | `D:\ZhixueEnglish\2025年度初一外研版英语教材\` |
| 官方音频资源总数 | 54 |
| 排除的词汇音频 | 7（AU48–AU54） |
| 纳入扫描的正式活动音频 | 47（AU01–AU47） |
| 全教材正式 Listening Activity 总数 | 21 |
| 有官方 MP3 的 Listening Activity 数 | 21 |

说明：

- AU48–AU54 是 Words and expressions 词汇音频，已全部排除。
- 结构化题目表中的 `question_type=fill`、`blank_count`、`fill`、`blank` 仅作为线索，不直接作为教材事实。
- B 类判断依据仍回到：教材 Activity 的正式呈现、教材页码、官方 MP3 映射和既有内容块证据。

## 3. A / B / C / D 分类统计

| 分类 | 数量 | 说明 |
| --- | ---: | --- |
| A：纸面完整 + 音频完整 | 7 个 Listening Activity | 纸面主要是完整问题/选项，未确认句子挖空 |
| B：纸面不完整 + 官方活动音频完整 | 14 个 Activity / 76 个候选句槽 | 本次重点 |
| C：纸面不完整 + 音频也没有完整朗读 | 0 | 当前未确认；部分 B 槽在后续音频核验中可能需要降级为 C |
| D：结构化标填空但原教材实为完整句 | 1 个 Activity / 4 条 question record | AU13 的已确认抽取误判 |

## 4. B 类候选活动

| # | audio_id | Module / Unit | Activity | 教材页 | B 候选句槽 |
| ---: | --- | --- | --- | --- | ---: |
| 1 | AU01 | Starter | 2 Read and complete. Then listen and check. | p3 | 5 |
| 2 | AU02 | Starter | 3 Listen and complete the conversation with a / an or a number. | p3 | 4 |
| 3 | AU03 | Starter | 10 Listen and choose. | p5 | 8 |
| 4 | AU11 | Unit 1 | 2 Listen again and complete the poster. | p22 | 6 |
| 5 | AU12 | Unit 1 | 3 Listen to the conversation and complete the table. | p23 | 5 |
| 6 | AU19 | Unit 2 | 3 Listen to the interview and complete the interviewer's notes. | p39 | 5 |
| 7 | AU25 | Unit 3 | 2 Listen again and complete the chart. | p54 | 5 |
| 8 | AU26 | Unit 3 | 3 Listen and complete the conversation. | p55 | 6 |
| 9 | AU32 | Unit 4 | 2 Listen again and complete the poster. Then write F (fact) or O (opinion) in the boxes. | p70 | 6 |
| 10 | AU33 | Unit 4 | 3 Listen to the conversation and complete the ideas. Then match the ideas to the people. | p71 | 5 |
| 11 | AU39 | Unit 5 | 2 Listen again and complete Jason's notes for the vlog. | p86 | 5 |
| 12 | AU40 | Unit 5 | 3 Listen to the conversation and complete the sentences. | p87 | 4 |
| 13 | AU45 | Unit 6 | 2 Listen again and complete the webpage for Bingjie. | p102 | 6 |
| 14 | AU46 | Unit 6 | 3 Listen to the interview and complete the notes. | p103 | 6 |

## 5. B 类按 Module / Unit 分布

| Module / Unit | B Activity 数 | 候选句槽 |
| --- | ---: | ---: |
| Starter | 3 | 17 |
| Unit 1 | 2 | 11 |
| Unit 2 | 1 | 5 |
| Unit 3 | 2 | 11 |
| Unit 4 | 2 | 11 |
| Unit 5 | 2 | 9 |
| Unit 6 | 2 | 12 |
| **合计** | **14** | **76** |

## 6. B 类涉及 Activity / MP3 数

```text
B 类涉及 Activity 数：14
B 类涉及 MP3 数：14（AU01、AU02、AU03、AU11、AU12、AU19、AU25、AU26、AU32、AU33、AU39、AU40、AU45、AU46）
```

所有原始音频路径均指向：

```text
D:\ZhixueEnglish\2025年度初一外研版英语教材\
```

未使用任何派生音频、词汇音频、临时音频或复制音频。

## 7. sentence timing 状态

| 项目 | 数量 |
| --- | ---: |
| B 类已有可靠 sentence timing | 0 |
| B 类 `TIMING_PENDING` | 76 |
| 已直接复用已有候选时间 | 0 |

原因：

- AU06 与 AU13 的时间成果不属于本次 14 个 B 类听力活动。
- 本步骤禁止重跑 Whisper。
- 当前项目没有这 14 个活动对应的现成句级时间戳资产。

## 8. 可以直接进入本地题库资源的数量

```text
可直接进入本地题库资源候选：0
需要人工 / 后续授权审核：76
```

原因不是“没有 B 类”，而是 B 类目前只完成了活动级发现与空白槽统计，尚缺两样关键物：

1. 官方音频中对应的完整句文本；
2. 完整句在官方 MP3 中的 `start_ms / end_ms`。

在没有官方答案稿/听力原文，又不能重跑 Whisper或使用 AI 猜测的情况下，不能把 76 个缺失词或完整句写入候选库。

## 9. A 类活动

以下 7 个 Listening Activity 未发现教材纸面上的句子挖空，归入 A：

| audio_id | Unit | Activity | 教材页 |
| --- | --- | --- | --- |
| AU09 | Unit 1 | 1 Listen to the radio. What's the biggest problem for new students? | p21 |
| AU16 | Unit 2 | 1 Listen to the conversation. What does Wang Chen do? | p37 |
| AU18 | Unit 2 | 2 Listen again and order the pictures. | p38 |
| AU23 | Unit 3 | 1 Listen to the family hotline. What problem does Tina have with her mother? | p53 |
| AU30 | Unit 4 | 1 Listen to the news. What problems does Christmas bring? | p69 |
| AU37 | Unit 5 | 1 Listen to the opening of the vlog. What is Jason talking about? | p85 |
| AU43 | Unit 6 | 1 Listen to the radio programme. What is it about? | p101 |

## 10. D 类抽取误判

AU13 不属于 B；其结构化 `fill/blank` 已确认属于 D：

| question_id | 误判内容 | 正确事实 |
| --- | --- | --- |
| Q:CB78B3F25CC8 | A2 对话正文被标 fill | 教材纸面是完整对话，无挖空 |
| Q:6BE4FE7DFF83 | 书信第 1 段被标 fill | 教材纸面是完整段落，无挖空 |
| Q:471FFC6481AF | 书信第 2 段被标 fill | 教材纸面是完整段落，无挖空 |
| Q:2ACC8C15EAA1 | 书信第 3 段/署名被标 fill | 教材纸面是完整段落/署名，无挖空 |

```text
D 类活动数：1
D 类 question record 数：4
```

本次没有把 AU13 的 D 类记录重复统计为 B。

## 11. C 类情况

```text
C 类当前确认数量：0
```

说明：

- 当前 76 个 B 候选槽都来自“教材要求听音补全 + 对应官方活动音频存在”的听力活动。
- 是否有一条槽实际上只是孤立数字、姓名、地点或短语，需要在后续获得对应音频句文本后才能最终判定；如果届时不能形成完整句，应从 B 降级为 C。

## 12. 数据安全确认

```text
learning.db: unchanged
contentpack: unchanged
formal question bank: unchanged
P3-05: unchanged
Android: unchanged
original textbook PDF: unchanged
original MP3: unchanged
audio slicing: 0
Whisper rerun: 0
cloud AI calls: 0
AI generation of missing textbook text: 0
auto VERIFIED: 0
```

## 13. 输出文件

- `D:\ZhixueEnglish\audit\P3-06_step9_fulltext_incomplete_audio_complete_audit.md`
- `D:\ZhixueEnglish\audit\P3-06_step9_fulltext_incomplete_audio_complete_candidates.json`

## 14. 最终答案

```text
PASS
B 类候选活动：14
B 类候选句槽：76
B 类已恢复完整学习句：0
B 类 sentence timing：0
B 类 TIMING_PENDING：76
```

**B 类到底有多少条：有 76 条 B 类候选句槽，分布在 14 个 Listening Activity / 14 个官方 MP3；但目前 0 条已恢复为完整学习句，全部需要后续审核或授权音频确认。**

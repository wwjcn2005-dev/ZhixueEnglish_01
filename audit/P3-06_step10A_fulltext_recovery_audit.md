# P3-06 Step 10A 全教材 B 类 76 条候选句槽“完整学习句恢复”只读审计

> 只读审计。未修改 learning.db、contentpack、正式题库、P3-05、Android、原始教材或原始 MP3；未安装/下载；未重跑 Whisper；未做 alignment；未生成 timing；未调用云端 AI。

## 1. 结论

```text
PASS
```

本步骤对 Step 9 的 76 条 B 类候选句槽逐条回溯到原始教材页面，确认了每条的**句子骨架**，但没有恢复任何缺失词，也没有生成任何完整学习句。

核心结果：

| 恢复状态 | 数量 |
| --- | ---: |
| `RECOVERED_CONFIRMED` | 0 |
| `RECOVERED_PARTIAL` | 76 |
| `NOT_RECOVERABLE` | 0 |
| `DOWNGRADE_TO_C` | 0 |

必须明确：

- 76 条都能从原始 PDF 页面确认“句子骨架 + 空白槽位置”。
- 缺失词不在教材纸面上，也没有官方答案稿、听力原文或 transcript。
- 本步骤禁止重跑 Whisper、禁止 AI 猜测，因此 76 条的 `learning_text` 全部保持 `null`。

## 2. 按 Module / Unit 分布

| Module / Unit | Activity 数 | 候选句槽 | RECOVERED_CONFIRMED | RECOVERED_PARTIAL | NOT_RECOVERABLE | DOWNGRADE_TO_C |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Starter | 3 | 17 | 0 | 17 | 0 | 0 |
| Unit 1 | 2 | 11 | 0 | 11 | 0 | 0 |
| Unit 2 | 1 | 5 | 0 | 5 | 0 | 0 |
| Unit 3 | 2 | 11 | 0 | 11 | 0 | 0 |
| Unit 4 | 2 | 11 | 0 | 11 | 0 | 0 |
| Unit 5 | 2 | 9 | 0 | 9 | 0 | 0 |
| Unit 6 | 2 | 12 | 0 | 12 | 0 | 0 |
| **合计** | **14** | **76** | **0** | **76** | **0** | **0** |

## 3. 完整证据链统计

本步骤为每条候选保留：

```text
module
unit
activity
audio_id
original_audio_filename
source_page
source_text
classification
recovered_fragment
learning_text
recovery_status
evidence_source
evidence_detail
confidence
reason
timing_status
start_ms
end_ms
```

其中：

- `source_text`：来自 Step 9 的活动级教材抽取文本。
- `recovered_fragment`：来自原始 PDF 页面版式回溯后的句子骨架。
- `learning_text`：全部为 `null`。
- `evidence_source`：原始教材 PDF 页面文本 + 版面坐标。
- `timing_status`：全部 `TIMING_PENDING`。

## 4. 有多少条已经具备完整 source_text + learning_text + official audio_id

```text
0 条
```

虽然 76 条都具备：

```text
source_text
+ official audio_id
+ official original MP3
+ recovered_fragment
```

但没有任何一条同时具备 `learning_text`。因此本步骤没有产生可进入题库的完整学习句，也没有产生新的 timing。

## 5. 有多少条只能确认句子骨架

```text
76 条
```

这 76 条都能确认原始教材的句子骨架。例如：

| audio_id | 槽 | recovered_fragment |
| --- | ---: | --- |
| AU01 | 1 | `Mum: Where is your ___?` |
| AU11 | 2 | `What are the ___ students' problems?` |
| AU19 | 1 | `These kinds of birds have weak ___, so they can't take off from the ground.` |
| AU26 | 3 | `Oh, Tina. Don't you ___ my queen's dress?` |
| AU32 | 3 | `People cut down nearly ___ million trees to use as Christmas trees.` |
| AU40 | 1 | `Tacos are a traditional Mexican food. We ___ them from corn seeds.` |
| AU45 | 6 | `Bingjie died at the age of ___.` |
| AU46 | 3 | `He got hurt, but he didn't ___.` |

完整 76 条 fragment 记录在 JSON 的 `candidates` 数组中。

## 6. 有多少条完全无法恢复

```text
句子骨架层面：0 条
完整学习句层面：76 条（当前材料条件下）
```

当前材料足以确认“这句话长什么样”，但不足以确认“空格里应该填什么”。缺失词只能来自官方音频的完整朗读或官方听力文本；两者当前都不存在可读取的项目材料。

## 7. 哪些 Activity 的恢复率最高

按“句子骨架恢复率”计算：

```text
14/14 Activity 均为 100% 骨架恢复
```

| Activity | 句子骨架恢复 | 完整学习句恢复 |
| --- | ---: | ---: |
| AU01 | 5/5 | 0/5 |
| AU02 | 4/4 | 0/4 |
| AU03 | 8/8 | 0/8 |
| AU11 | 6/6 | 0/6 |
| AU12 | 5/5 | 0/5 |
| AU19 | 5/5 | 0/5 |
| AU25 | 5/5 | 0/5 |
| AU26 | 6/6 | 0/6 |
| AU32 | 6/6 | 0/6 |
| AU33 | 5/5 | 0/5 |
| AU39 | 5/5 | 0/5 |
| AU40 | 4/4 | 0/4 |
| AU45 | 6/6 | 0/6 |
| AU46 | 6/6 | 0/6 |

按“完整学习句恢复率”计算，目前所有 Activity 都是 0%。

## 8. 哪些 Activity 完全无法恢复

在句子骨架层面，没有被判为完全无法恢复的 Activity。

在完整学习句层面，由于所有 Activity 的缺失词都只在官方音频中，因此当前 14/14 Activity 都无法在**禁止重跑 Whisper、禁止 AI 猜测**的条件下形成完整 `learning_text`。

这不等于这些资源无价值：76 条骨架已经足以作为后续“官方音频句文本确认”的精确任务清单。

## 9. Step 9 的 B 类分类是否需要修正

```text
需要立即修正的数量：0
```

原因：

- 本步骤逐条回溯原始 PDF 页面后，76 条仍都能定位到句子骨架或句内空白槽。
- 未发现新的 D 类抽取误判。
- 未发现新的确定 C 类非句子单位。

但保留一个后续风险：

> 如果后续通过官方音频确认某条仅对应数字、姓名、地点、孤立单词或短语，而且不能形成完整句，则该条应在下一步降级为 C。

## 10. timing 状态

```text
B 类已有 sentence timing：0
B 类 TIMING_PENDING：76
本轮新建 timing：0
```

AU06 的 VERIFIED 结果和 AU13 的 CANDIDATE 结果均不属于本次 76 条，未混入统计。

## 11. 数据安全确认

```text
learning.db: unchanged
contentpack: unchanged
formal question bank: unchanged
P3-05: unchanged
Android: unchanged
original textbook PDF: unchanged
original MP3: unchanged
install / download: 0
Whisper rerun: 0
cloud AI calls: 0
new timing: 0
auto VERIFIED: 0
```

## 12. 输出文件

- `D:\ZhixueEnglish\audit\P3-06_step10A_fulltext_recovery_audit.md`
- `D:\ZhixueEnglish\audit\P3-06_step10A_fulltext_recovery_candidates.json`

## 13. 最终回答

```text
PASS
RECOVERED_CONFIRMED = 0
RECOVERED_PARTIAL = 76
NOT_RECOVERABLE = 0
DOWNGRADE_TO_C = 0
完整 source_text + learning_text + official audio_id = 0
仅句子骨架 = 76
当前条件下无法形成完整学习句 = 76
```

本步骤只新增 Step 10A 两个审计文件；正式数据 0 修改；原始教材 0 修改；原始 MP3 0 修改；AI/cloud calls = 0；Whisper rerun = 0；install/download = 0。

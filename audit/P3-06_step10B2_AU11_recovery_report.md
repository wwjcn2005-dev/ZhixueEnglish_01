# P3-06 Step 10B-2 AU11 完整学习句恢复 + sentence timing 候选

> 只读处理官方原始 MP3，只新增审计/候选文件。未修改 learning.db、contentpack、正式题库、P3-05、Android、原始教材或原始 MP3；未下载模型、未安装依赖、未调用云端 AI；未生成 VERIFIED。

## 1. 结论

```text
PASS
```

AU11 的 6 个教材句槽全部得到：

- 完整 `learning_text` 候选
- Whisper word-level 证据
- `start_ms / end_ms` 候选
- `recovery_status = RECOVERED_CANDIDATE`
- `timing_status = CANDIDATE`

全部仍为 `UNVERIFIED`，等待人工听证。

## 2. ASR 运行记录

| 项目 | 结果 |
| --- | --- |
| audio_id | `FLTRP-EN-7A-2022CUR:AU11` |
| 原始 MP3 | `11_Unit 1_Developing ideas _2 Listen again and complete the poster.mp3` |
| 原始路径 | `D:\ZhixueEnglish\2025年度初一外研版英语教材\11_Unit 1_Developing ideas _2 Listen again and complete the poster.mp3` |
| 音频时长 | 44,121 ms |
| 模型 | `small`（本地 `Systran/faster-whisper-small` snapshot） |
| 运行方式 | CPU + int8，`local_files_only=True` |
| 模型加载 | 1.4 s |
| 转写耗时 | 6.5 s |
| segment / word | 8 segments / 74 words |
| ASR 实际运行 | 1 次 |
| 模型下载 | 0 |
| 云端 AI | 0 |

## 3. 6 条候选恢复表

| # | candidate_id | 教材句槽 | 恢复的完整句候选 | start_ms | end_ms | duration_ms | word match |
| ---: | --- | --- | --- | ---: | ---: | ---: | --- |
| 1 | AU11-B01 | The new school ___ is beginning. | The new school year is beginning. | 10420 | 12480 | 2060 | 6/6 |
| 2 | AU11-B02 | What are the ___ students' problems? | What are the new students' problems? | 13460 | 15740 | 2280 | 6/6 |
| 3 | AU11-B03 | They have more ___ and more homework. | They have more subjects and more homework. | 22240 | 26000 | 3760 | 7/7 |
| 4 | AU11-B04 | They also have ___ activities. | They also have many activities. | 26000 | 29360 | 3360 | 5/5 |
| 5 | AU11-B05 | How can they make good use of their ___? | How can they make good use of their time? | 30740 | 33640 | 2900 | 9/9 |
| 6 | AU11-B06 | The Students' Union will hold a talk this ___. | The Students' Union will hold a talk this Thursday to help you. | 34940 | 39540 | 4600 | 12/12 |

## 4. 缺失词恢复结果

| # | filled_word | 来源 |
| ---: | --- | --- |
| 1 | `year` | Whisper word-level: `year` 11.280–11.720 s |
| 2 | `new` | Whisper word-level: `new` 14.300–14.660 s |
| 3 | `subjects` | Whisper word-level: `subjects` 23.560–24.240 s |
| 4 | `many` | Whisper word-level: `many` 28.260–28.720 s |
| 5 | `time` | Whisper word-level: `time` 33.220–33.640 s |
| 6 | `Thursday` | Whisper word-level: `Thursday` 38.080–38.540 s |

教材文本优先：

- 采用教材规范拼写 `Students' Union`，不机械复制 Whisper 的无撇号形式。
- 教材原文和 `recovered_fragment` 未被修改。
- Whisper 只作为音频证据，不覆盖教材文本。

## 5. Activity instruction / 非句槽音频处理

以下 audio text 被排除在 6 条学习句之外：

| 时间 | 文本 | 原因 |
| --- | --- | --- |
| 0.000–1.480 s | `Activity 2` | instruction |
| 2.660–5.600 s | `Listen again and complete the poster.` | instruction |
| 6.580–9.820 s | `Welcome to Students Union Radio.` | 播报开场，不属于 6 个 poster 句槽 |
| 16.660–17.880 s | `Let's take a look.` | 衔接语，不属于 6 个 poster 句槽 |
| 18.920–22.240 s | `For many students, the biggest problem is` | B03 的前置语境，B03 候选从 `they` 开始 |
| 30.200–30.740 s | `So` | B05 的前置语境，B05 候选从 `how` 开始 |
| 40.320–41.480 s | `Come and join us.` | 末尾收束语，不属于 6 个 poster 句槽 |

## 6. 自动检查

| 检查项 | 结果 |
| --- | --- |
| 6 个句槽数量 | 通过 |
| 6/6 `learning_text` 非空 | 通过 |
| 6/6 `RECOVERED_CANDIDATE` | 通过 |
| 6/6 `timing_status = CANDIDATE` | 通过 |
| `start_ms < end_ms` | 通过 |
| 顺序单调 | 通过 |
| sentence overlap | 0 |
| duration 计算 | 通过 |
| Whisper word match | 6/6 exact |
| instruction 未纳入正文 | 通过 |
| 标题未纳入正文 | 通过 |
| poster 字段标签未当句子 | 通过 |
| 非完整语言单位 | 0 |

## 7. 歧义与人工听证需求

```text
文本匹配歧义：无
人工听证：必须
```

需要人工听证的理由：

1. B03 的教材句槽明确从 `They have more...` 开始，但音频中该内容位于完整句子 `For many students, the biggest problem is they have more...` 的后半段；文本匹配明确，边界应人工确认。
2. B05 的音频前有 `So`；当前候选从 `How` 开始，匹配明确，边界应人工确认。
3. B06 的完整句包含 `to help you.`，而 poster 可视线只给出 `this ___` 部分；当前将 `to help you` 纳入完整句候选，必须人工听确认。
4. 所有时间仍是 `CANDIDATE`，不能自动升级为 `VERIFIED`。

## 8. 最终统计

```text
AU11 总句槽 = 6
RECOVERED_CANDIDATE = 6
RECOVERED_PARTIAL = 0
NOT_RECOVERABLE = 0
DOWNGRADE_TO_C = 0

具有完整 learning_text 候选 = 6
具有 timing candidate = 6
Word-level match = 6/6 exact
是否存在歧义 = 文本匹配无；边界需人工听证
是否需要人工听证 = 是
VERIFIED = 0
```

## 9. 数据安全确认

```text
正式 learning.db 修改 = 0
contentpack 修改 = 0
正式题库修改 = 0
P3-05 修改 = 0
Android 修改 = 0
原始教材修改 = 0
原始 MP3 修改 = 0

AI / cloud calls = 0
新模型下载 = 0
新依赖安装 = 0
C盘模型 / cache / temp = 0
音频切片 = 0
其他 Activity 处理 = 0
AU06 / AU13 / AU48-AU54 处理 = 0
```

只新增两个 Step 10B-2 审计文件：

- `D:\ZhixueEnglish\audit\P3-06_step10B2_AU11_recovery_candidates.json`
- `D:\ZhixueEnglish\audit\P3-06_step10B2_AU11_recovery_report.md`

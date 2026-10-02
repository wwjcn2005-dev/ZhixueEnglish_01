# P3-07 整本教材跟读精选资源批量生产报告

## 1. 结论

```text
BLOCKED
```

阻塞原因不是程序或数据库问题，而是**全教材批量生产缺少足够的句子级音频对齐依据**：

- 正式活动 MP3：47 个（AU01–AU47）
- 其中已有句子级/词级时间资产的：AU06、AU11、AU13
- 其余 44 个活动音频没有可复用的句子级 transcript / alignment / timestamp
- 本任务禁止 ASR、Whisper、云端识别

因此，对这 44 个音频执行“教材原句 → 原声区间”的生产会进入不可验证的猜测状态，可能造成错误正式资源。

本轮没有向正式数据库写入新的批量资源。

## 2. 教材扫描结果

| 项目 | 数量 |
| --- | ---: |
| 原始教材根目录 | `D:\ZhixueEnglish\2025年度初一外研版英语教材\` |
| 原始 MP3 总数 | 54 |
| 正式活动音频 | 47 |
| 词汇音频 AU48–AU54 | 7 |
| 教材 Unit 数 | 8 |
| Section 数 | 46 |
| Activity 数 | 96 |
| 结构化 content_block | 3,854 |
| exercise_item 块 | 2,133 |

当前 P3-07 候选清单：

| 来源 | 数量 |
| --- | ---: |
| B 类句子候选 | 70 |
| AU13 对话句 | 9 |
| AU13 书信句 | 14 |
| **P3-07 候选合计** | **93** |

候选只涉及 15 个 audio_id：

```text
AU01, AU02, AU03, AU11, AU12, AU13, AU19, AU25, AU26,
AU32, AU33, AU39, AU40, AU45, AU46
```

## 3. 现有正式时间资产覆盖

### 已有正式 annotation

当前 `audio_sentence_annotation`：

```text
总行数：15
VERIFIED：12
REJECTED：3
涉及 audio_id：AU11、AU13
```

### 已有可复用时间资产

| 资产 | 覆盖 |
| --- | --- |
| `audit/P3-06_au06_verified_sentences.json` | AU06，8 句 VERIFIED |
| `audit/P3-06_step4_au06_alignment_result.json` | AU06 word timestamps |
| `audit/P3-06_step10B2_AU11_recovery_candidates.json` | AU11，6 句候选 |
| `audit/P3-06_step8B_AU13_alignment_result.json` | AU13 word timestamps |
| `audit/P3-06_step8C_AU13_practice_candidates.json` | AU13 对话与书信候选 |

### 覆盖判断

| 范围 | 有句子级时间依据 | 无句子级时间依据 |
| --- | ---: | ---: |
| 47 个正式活动音频 | 3（AU06、AU11、AU13） | **44** |

## 4. 为什么不能直接完成整本教材

对 AU06、AU11、AU13 之外的音频：

1. 项目没有句子级 transcript；
2. 项目没有 word-level timestamp；
3. 项目没有可信的文本—音频对齐结果；
4. 只有活动级 MP3 映射，没有句子级时间；
5. 本任务禁止 ASR/Whisper；
6. 仅凭静音分段无法可靠判断“第 N 段 = 第 N 句”，此前 P3-06 已有明确失败经验。

因此不能安全地自动生成 Start/End。

如果强行仅按静音分组推测，会把低能量检测误判、连续朗读、多人对话、音乐/音效等情况变成错误正式资源。

## 5. 可安全处理的已有资源

以下资源已有可信依据：

- AU06：8 句已有 VERIFIED 审计结果
- AU11：6 句已有页面人工审核记录并进入正式表
- AU13：对话句与 LTR-12 等已有部分人工审核记录

但这些不足以覆盖整本教材，也不能代表其余 44 个音频的全句时间轴。

## 6. 精选与筛选情况

本轮暂停在全量精选句—音频映射阶段。

原因：

- 文本层可以继续按教师规则筛选教材句子；
- 但筛选出的句子如果不能可靠对应原声区间，就不能进入正式资源库；
- 不能为了“完成整本教材”而批量生成无可靠时间依据的资源。

## 7. 自动质量检查

在当前可核查范围内：

| 检查项 | 结果 |
| --- | --- |
| 现有候选有教材原文 | 93/93 |
| 现有候选有 audio_id | 93/93 |
| 现有正式 annotation 的 start/end 合法 | PASS |
| 原音频文件存在 | PASS |
| 44 个无对齐音频可安全生成句级 Start/End | **FAIL / BLOCKED** |

## 8. 未执行正式批量入库

```text
新增正式资源：0
删除正式资源：0
覆盖正式资源：0
批量写入：0
```

没有把未经音频验证的句子写进正式库。

## 9. 安全检查

```text
learning.db：未修改
正式学习数据：未修改
Android：未修改
原始教材：未修改
原始 MP3：未修改
AI 调用：0
ASR：0
Whisper：0
云端调用：0
音频转码：0
音频切割：0
```

## 10. 最终汇总

```text
TEXTBOOK_SENTENCES：无法在全教材范围内可靠枚举
CANDIDATES：93（现有 P3-07 候选）
SELECTED：未完成全教材精选入库
AUDIO_MATCHED：93/93 候选有活动级音频
TIME_ALIGNED：仅 3/47 正式活动音频有句子/词级资产
IMPORTED：0
ALREADY_EXISTS：15 条正式 annotation
NO_AUDIO：0（候选层）
BOUNDARY_UNCERTAIN：44 个活动音频
FAILED：0 技术错误；全教材批量生产 BLOCKED
```

## 11. 下一阶段建议

必须先解决“文本 → 音频句级对齐”的来源问题。可选方向：

1. 提供人工已对齐的教材句时间表；
2. 在明确授权下使用本地 ASR/强制对齐做候选，再人工复核；
3. 先继续扩展现有已验证的 AU06/AU11/AU13 模式，而不是直接推全教材。

在解决对齐来源之前，不应启动整本教材正式资源批量写入。

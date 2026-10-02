# P3-07 AU13 Letter 高价值跟读句教学筛选报告

> 只读教学筛选。未修改代码、数据库、learning.db、audio_sentence_annotation、audio_token_annotation、Android、原始教材或原始 MP3；未做音频定位、音频分析、ASR、Whisper 或 AI 调用。

## 1. 筛选结论

```text
原始句子：14
推荐进入跟读资源：7
不推荐：7
```

筛选原则：

> 少而精；优先选择能迁移、能真实使用、适合初一学生模仿并具有口语节奏价值的教材原句。

## 2. 推荐跟读句

| candidate_id | 原文 | 推荐等级 | 核心理由 |
| --- | --- | --- | --- |
| AU13-LTR-01 | Time flies! | B：推荐 | 高频固定表达，短、自然，适合模仿节奏和 /aɪ/ 音 |
| AU13-LTR-03 | Are you ready for your new life? | A：强烈推荐 | “Are you ready for...?”可直接迁移到多种真实场景，疑问语调训练价值高 |
| AU13-LTR-06 | Dad and Mum can protect it from winds. | B：推荐 | “protect ... from ...”是值得模仿和迁移的固定搭配 |
| AU13-LTR-09 | You will face new problems. | A：强烈推荐 | “You will...”与“face problems”均可迁移，适合训练重音和自然语速 |
| AU13-LTR-10 | We are still here to help. | B：推荐 | 表达支持与陪伴，可迁移为“I’m here to help.”，语调和情感表达适合跟读 |
| AU13-LTR-11 | But sometimes you have to sail your boat by yourself. | B：推荐 | “You have to...”结构迁移价值高，句子较长，适合训练节奏、弱读和连读 |
| AU13-LTR-12 | Just try your best and work hard. | A：强烈推荐 | 两个并列祈使句节奏鲜明，短语可反复使用，适合初一学生自然跟读和模仿 |

## 3. 不推荐句

| candidate_id | 原文 | 不推荐原因 |
| --- | --- | --- |
| AU13-LTR-02 | You are now in junior high! | 语境特定，迁移价值有限 |
| AU13-LTR-04 | Primary school is like a small pool. | 比喻表达更适合阅读理解；与后续比喻句功能重复 |
| AU13-LTR-05 | Your boat is safe there. | 高度依赖比喻上下文；单独跟读价值不足 |
| AU13-LTR-07 | But junior high is like a river. | “is like”有价值，但与 LTR-04、LTR-08、LTR-13 的比喻链重复，只保留代表句即可 |
| AU13-LTR-08 | It is wide and the water moves fast. | 描述性事实句，口语迁移价值一般 |
| AU13-LTR-13 | You will go through storms towards the sea. | 文学比喻性强、句子较长，更适合作为阅读材料 |
| AU13-LTR-14 | We hope this letter helps you in the coming years! | 信末祝愿语境特定；功能与 LTR-10 的书信情感表达部分重叠 |

## 4. 教学筛选总结

### A. 本组最值得孩子反复跟读的 3～5 句

1. `Are you ready for your new life?`
2. `You will face new problems.`
3. `Just try your best and work hard.`
4. `Dad and Mum can protect it from winds.`
5. `But sometimes you have to sail your boat by yourself.`

### B. 哪些句子最有迁移价值

- `Are you ready for ...?`
- `You will ...`
- `... have to ...`
- `protect ... from ...`
- `Just try your best ...`

### C. 哪些句子最有语音训练价值

- `Are you ready for your new life?`：疑问语调
- `You will face new problems.`：重音和节奏
- `Just try your best and work hard.`：并列节奏和重音
- `But sometimes you have to sail your boat by yourself.`：长句节奏、弱读、连读
- `We are still here to help.`：情感语调和自然停顿

### D. 哪些句子虽然教材重要，但不值得进入独立跟读资源

- 比喻链句子：`Primary school is like a small pool.`、`But junior high is like a river.`、`You will go through storms towards the sea.`
- 特定事实描述：`It is wide and the water moves fast.`
- 高度依赖上下文的短句：`Your boat is safe there.`
- 信末语境句：`You are now in junior high!`、`We hope this letter helps you in the coming years!`

这些句子仍然属于教材正文，只是不必都作为独立跟读资源。

## 5. 下一阶段建议

本阶段只完成教学筛选，不修改程序。

下一阶段应将“推荐进入跟读资源”的 7 个句子交给 P3-07 音频定位模块，利用 AU13 原始 MP3 的自然静音/低能量区生成 Suggested Start / End，再由人工试听确认。

建议优先定位顺序：

```text
AU13-LTR-03
AU13-LTR-09
AU13-LTR-12
AU13-LTR-06
AU13-LTR-11
AU13-LTR-10
AU13-LTR-01
```

## 6. 安全检查

```text
代码修改 = 0
数据库修改 = 0
learning.db = unchanged
audio_sentence_annotation = unchanged
audio_token_annotation = unchanged
原始教材 = unchanged
原始 MP3 = unchanged
AI 调用 = 0
ASR = 0
Whisper = 0
音频处理 = 0
```

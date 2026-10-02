# P3-07 AU13 Letter 精选句原声定位报告

> 只生成 Suggested Start / End；未保存正式音频资源，未修改数据库或原始 MP3。

## 1. 基本信息

| 项目 | 结果 |
| --- | --- |
| 原始句子总数 | 14 |
| 最终精选句数 | 7 |
| 本次实际定位 | 7 |
| audio_id | `FLTRP-EN-7A-2022CUR:AU13` |
| 原始 MP3 | `D:\ZhixueEnglish\2025年度初一外研版英语教材\13_Unit 1_Developing ideas _Reading for writing_2 Read the passage and find out the meaning of the title.mp3` |
| MP3 时长 | 101,381 ms |
| Letter 大致区域 | 约 46.20–98.12 s（沿用项目既有 Step 8B 结果，本次未重新识别） |

定位原则：

- 使用现有 Step 8B 词级时间作顺序锚点。
- 使用本地 PCM/能量分析寻找自然低能量区。
- Suggested Start/End 仍只是候选，必须人工试听确认。

## 2. 定位结果表

| candidate_id | sentence_text | suggested_start_ms | suggested_end_ms | duration_ms | status | note |
| --- | --- | ---: | ---: | ---: | --- | --- |
| AU13-LTR-01 | Time flies! | 47860 | 49440 | 1580 | READY | 首尾均观察到自然低能量区 |
| AU13-LTR-02 | You are now in junior high! | 50140 | 52330 | 2190 | READY | 首尾均观察到自然低能量区 |
| AU13-LTR-03 | Are you ready for your new life? | 52760 | 54760 | 2000 | READY | 首尾均观察到自然低能量区 |
| AU13-LTR-09 | You will face new problems. | 73320 | 75580 | 2260 | READY | 首尾均观察到自然低能量区 |
| AU13-LTR-10 | We are still here to help. | 76140 | 78120 | 1980 | READY | 首尾均观察到自然低能量区 |
| AU13-LTR-11 | But sometimes you have to sail your boat by yourself. | 78600 | 82520 | 3920 | NEEDS_MANUAL_REVIEW | 句尾与 LTR-12 几乎无静音间隔 |
| AU13-LTR-12 | Just try your best and work hard. | 82520 | 86490 | 3970 | NEEDS_MANUAL_REVIEW | 句首紧接 LTR-11 末尾，无明显独立静音区 |

## 3. 顺序检查

```text
47860 < 49440
< 50140 < 52330
< 52760 < 54760
< 73320 < 75580
< 76140 < 78120
< 78600 < 82520
<= 82520 < 86490
```

- 7 句顺序与教材顺序一致：LTR-01 → LTR-02 → LTR-03 → LTR-09 → LTR-10 → LTR-11 → LTR-12
- 所有 `start_ms < end_ms`
- 时间轴无倒序
- 无明显跨句重叠
- LTR-11 与 LTR-12 边界相接，需人工复核

## 4. 音频完整性检查

| 检查项 | 判断 |
| --- | --- |
| 开头是否吞掉首音节 | READY 5 条未发现程序性风险；LTR-11/12 需人工复核 |
| 结尾是否吞掉尾音 | 程序建议覆盖到句末锚点之后 |
| 是否带入前一句 | 未发现明显跨句 |
| 是否带入后一句 | READY 5 条未发现；LTR-11 的句尾没有可用独立静音区 |
| 停顿过短导致错误切分 | LTR-11 → LTR-12 属于风险点 |
| 低能量检测过严导致截断 | LTR-11、LTR-12 标记 `NEEDS_MANUAL_REVIEW` |

以上只代表程序边界检查结果，不能替代人工试听。

## 5. 修改 / 污染检查

```text
原始 MP3：未修改
learning.db：未修改
正式内容库：未修改
audio_sentence_annotation：未修改
audio_token_annotation：未修改
AI：0
ASR：0
Whisper：0
云端调用：0
音频切割：0
音频转码：0
```

## 6. 结论

```text
READY：5
NEEDS_MANUAL_REVIEW：2
NO_RELIABLE_BOUNDARY：0
```

可以进入人工试听确认阶段；正式保存前必须由人工确认 Suggested Start/End。

# P3-07 20 条精选正式生产前最终验收报告

## 1. 结论

```text
READY_FOR_FORMAL_IMPORT
```

所有 20 条精选句已匹配 HIGH，边界自动验收为 BOUNDARY_PASS；尚未写入正式资源库。

## 2. 四条边界最终收口

### PREVIEW:AU03:S0063

- 教材原文：What are you going to wear tomorrow for school?
- 原 ASR speech：7820–12060
- 实际起音/结束：9240–12060
- 最终 Start/End：9200–12380
- 判定：BOUNDARY_PASS
- 原因：ASR 首词 what 的 7820ms 包含前句 Tao 尾音；真实起音约 9240ms，前向静音区 8070–9240ms；新 Start=9200ms。句尾后进入 12290–12700ms 静音区，End=12380ms。

### PREVIEW:AU03:S0065

- 教材原文：How about you?
- 原 ASR speech：23700–24940
- 实际起音/结束：24000–24940
- 最终 Start/End：23920–24940
- 判定：BOUNDARY_PASS
- 原因：23200–23940ms 为静音，真实起音约 24000ms；新 Start=23920ms。下一句 I'm 从 24940ms 紧接开始，End 固定在 24940ms，不引入下一句。

### PREVIEW:AU13:S0279

- 教材原文：Are you ready for your new life?
- 原 ASR speech：52080–54640
- 实际起音/结束：52920–54640
- 最终 Start/End：52900–54760
- 判定：BOUNDARY_PASS
- 原因：前句 high 结束约 52080ms；52240–52920ms 为静音；Are 真实起音约 52920ms；新 Start=52900ms，避免前句尾音。句尾 life 后进入静音区，End=54760ms。

### PREVIEW:AU28:S0583

- 教材原文：How I wish to have four hands now!
- 原 ASR speech：50640–54800
- 实际起音/结束：51620–54800
- 最终 Start/End：51600–55020
- 判定：BOUNDARY_PASS
- 原因：前句尾音快速衰减，50960–51620ms 为低能量区；How 起音约 51620ms；新 Start=51600ms。now 后约 55020ms 进入静音区，End=55020ms。

## 3. 20 条最终结果

| sentence_id | sentence_text | audio | start_ms | end_ms | boundary_status | reason |
| --- | --- | --- | ---: | ---: | --- | --- |
| PREVIEW:AU01:S0005 | Are you ready? | AU01 | 29860 | 31200 | BOUNDARY_PASS | word timestamp 与波形边界自动通过 |
| PREVIEW:AU03:S0063 | What are you going to wear tomorrow for school? | AU03 | 9200 | 12380 | BOUNDARY_PASS | ASR 首词 what 的 7820ms 包含前句 Tao 尾音；真实起音约 9240ms，前向静音区 8070–9240ms；新 Start=9200ms。句尾后进入 12290–12700ms 静音区，End=12380ms。 |
| PREVIEW:AU03:S0065 | How about you? | AU03 | 23920 | 24940 | BOUNDARY_PASS | 23200–23940ms 为静音，真实起音约 24000ms；新 Start=23920ms。下一句 I'm 从 24940ms 紧接开始，End 固定在 24940ms，不引入下一句。 |
| PREVIEW:AU03:S0067 | What shoes are you going to wear? | AU03 | 35750 | 39010 | BOUNDARY_PASS | word timestamp 与波形边界自动通过 |
| PREVIEW:AU04:S0083 | Let’s go around the school together! | AU04 | 24440 | 27860 | BOUNDARY_PASS | word timestamp 与波形边界自动通过 |
| PREVIEW:AU06:S0149 | I want to make friends with you all! | AU06 | 36920 | 40150 | BOUNDARY_PASS | word timestamp 与波形边界自动通过 |
| PREVIEW:AU13:S0275 | We want to share some thoughts with you. | AU13 | 39240 | 41720 | BOUNDARY_PASS | word timestamp 与波形边界自动通过 |
| PREVIEW:AU13:S0279 | Are you ready for your new life? | AU13 | 52900 | 54760 | BOUNDARY_PASS | 前句 high 结束约 52080ms；52240–52920ms 为静音；Are 真实起音约 52920ms；新 Start=52900ms，避免前句尾音。句尾 life 后进入静音区，End=54760ms。 |
| PREVIEW:AU13:S0282 | Dad and Mum can protect it from winds. | AU13 | 61800 | 64700 | BOUNDARY_PASS | word timestamp 与波形边界自动通过 |
| PREVIEW:AU14:S0294 | “Why don’t we put our music together? | AU14 | 73340 | 76080 | BOUNDARY_PASS | word timestamp 与波形边界自动通过 |
| PREVIEW:AU19:S0367 | Why do you know so much about birds? | AU19 | 38560 | 42030 | BOUNDARY_PASS | word timestamp 与波形边界自动通过 |
| PREVIEW:AU19:S0369 | What do you like about bird-watching? | AU19 | 47820 | 50780 | BOUNDARY_PASS | word timestamp 与波形边界自动通过 |
| PREVIEW:AU20:S0425 | Let’s meet here on Wednesday after lunch. | AU20 | 101240 | 105560 | BOUNDARY_PASS | word timestamp 与波形边界自动通过 |
| PREVIEW:AU26:S0508 | Can you change your clothes before you come? | AU26 | 14330 | 18330 | BOUNDARY_PASS | word timestamp 与波形边界自动通过 |
| PREVIEW:AU28:S0583 | How I wish to have four hands now! | AU28 | 51600 | 55020 | BOUNDARY_PASS | 前句尾音快速衰减，50960–51620ms 为低能量区；How 起音约 51620ms；新 Start=51600ms。now 后约 55020ms 进入静音区，End=55020ms。 |
| PREVIEW:AU28:S0590 | “Are you joking? | AU28 | 83520 | 84960 | BOUNDARY_PASS | word timestamp 与波形边界自动通过 |
| PREVIEW:AU41:S0821 | What does tea mean to you? | AU41 | 32980 | 35770 | BOUNDARY_PASS | word timestamp 与波形边界自动通过 |
| PREVIEW:AU46:S0901 | Do you remember your first meeting? | AU46 | 16120 | 18990 | BOUNDARY_PASS | word timestamp 与波形边界自动通过 |
| PREVIEW:AU47:S0945 | Are you looking at me? | AU47 | 15400 | 17210 | BOUNDARY_PASS | word timestamp 与波形边界自动通过 |
| PREVIEW:AU47:S0946 | Do you know me? | AU47 | 18000 | 19260 | BOUNDARY_PASS | word timestamp 与波形边界自动通过 |

## 4. 自动验收检查

- sentence_text 教材原文：20/20
- Unit / Activity：20/20
- audio_file：20/20
- match HIGH：20/20
- final start < end：20/20
- sequence overlap：{len(overlaps)}
- 重复资源：0
- 原始 MP3 修改：0
- 正式资源库写入：0

## 5. 数据安全

```text
learning.db：未修改
正式 audio_sentence_annotation：未修改
audio_token_annotation：未修改
正式内容资源库：未修改
原始教材：未修改
原始 MP3：未修改
云端调用：0
```

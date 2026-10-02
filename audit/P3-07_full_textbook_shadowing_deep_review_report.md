# P3-07 预演结果深审报告：20 条精选句自动复核与边界算法校准

## 1. 结论

```text
DEEP_REVIEW_WARNING
```

20 条精选句已逐条用 word timestamps + 波形重新校准，未写正式资源库。

## 2. 20 条精选句逐条结果

### Starter / PREVIEW:AU01:S0005

- 教材原文：Are you ready?
- ASR：Are you ready?
- speech：29940–31080
- final：29860–31200
- match：HIGH（word_window_match score=1.000）
- boundary：GOOD_BOUNDARY（HIGH）
- start_adjust：word_timestamp_fallback
- end_adjust：word_timestamp_fallback

### Starter / PREVIEW:AU03:S0063

- 教材原文：What are you going to wear tomorrow for school?
- ASR：what are you going to wear tomorrow for school?
- speech：7820–12060
- final：7820–12180
- match：HIGH（word_window_match score=1.000）
- boundary：REAL_UNCERTAIN（BOUNDARY_UNCERTAIN）
- start_adjust：word_timestamp_fallback
- end_adjust：word_timestamp_fallback

### Starter / PREVIEW:AU03:S0065

- 教材原文：How about you?
- ASR：how about you?
- speech：23700–24940
- final：23620–24940
- match：HIGH（word_window_match score=1.000）
- boundary：NEXT_SENTENCE_INTRUSION（BOUNDARY_UNCERTAIN）
- start_adjust：word_timestamp_fallback
- end_adjust：word_timestamp_fallback

### Starter / PREVIEW:AU03:S0067

- 教材原文：What shoes are you going to wear?
- ASR：What shoes are you going to wear?
- speech：36520–38900
- final：35750–39010
- match：HIGH（word_window_match score=1.000）
- boundary：GOOD_BOUNDARY（HIGH）
- start_adjust：waveform_before_low_energy
- end_adjust：waveform_after_low_energy

### Starter / PREVIEW:AU04:S0083

- 教材原文：Let’s go around the school together!
- ASR：Let's Let's go around the school together
- speech：24520–27460
- final：24440–27860
- match：HIGH（word_window_match score=1.000）
- boundary：GOOD_BOUNDARY（HIGH）
- start_adjust：word_timestamp_fallback
- end_adjust：waveform_after_low_energy

### Starter / PREVIEW:AU06:S0149

- 教材原文：I want to make friends with you all!
- ASR：I want to make friends with you all.
- speech：37000–40040
- final：36920–40150
- match：HIGH（word_window_match score=1.000）
- boundary：GOOD_BOUNDARY（HIGH）
- start_adjust：word_timestamp_fallback
- end_adjust：waveform_after_low_energy

### Unit 1 / PREVIEW:AU13:S0275

- 教材原文：We want to share some thoughts with you.
- ASR：We want to share some thoughts with you.
- speech：39320–41600
- final：39240–41720
- match：HIGH（word_window_match score=1.000）
- boundary：GOOD_BOUNDARY（HIGH）
- start_adjust：word_timestamp_fallback
- end_adjust：word_timestamp_fallback

### Unit 1 / PREVIEW:AU13:S0279

- 教材原文：Are you ready for your new life?
- ASR：Are you ready for your new life?
- speech：52080–54640
- final：52080–54760
- match：HIGH（word_window_match score=1.000）
- boundary：REAL_UNCERTAIN（BOUNDARY_UNCERTAIN）
- start_adjust：word_timestamp_fallback
- end_adjust：word_timestamp_fallback

### Unit 1 / PREVIEW:AU13:S0282

- 教材原文：Dad and Mum can protect it from winds.
- ASR：Dad and mum can protect it from winds.
- speech：61860–64580
- final：61800–64700
- match：HIGH（word_window_match score=1.000）
- boundary：AUTO_RESOLVED（HIGH）
- start_adjust：waveform_before_low_energy
- end_adjust：word_timestamp_fallback

### Unit 2 / PREVIEW:AU14:S0294

- 教材原文：“Why don’t we put our music together?
- ASR：Why don't don't we put our music together?
- speech：73420–75960
- final：73340–76080
- match：HIGH（word_window_match score=1.000）
- boundary：AUTO_RESOLVED（HIGH）
- start_adjust：word_timestamp_fallback
- end_adjust：word_timestamp_fallback

### Unit 2 / PREVIEW:AU19:S0367

- 教材原文：Why do you know so much about birds?
- ASR：Why do you know so much about birds?
- speech：38640–42000
- final：38560–42030
- match：HIGH（word_window_match score=1.000）
- boundary：AUTO_RESOLVED（HIGH）
- start_adjust：word_timestamp_fallback
- end_adjust：waveform_after_low_energy

### Unit 2 / PREVIEW:AU19:S0369

- 教材原文：What do you like about bird-watching?
- ASR：What do you like about bird watching?
- speech：47900–50560
- final：47820–50780
- match：HIGH（word_window_match score=1.000）
- boundary：AUTO_RESOLVED（HIGH）
- start_adjust：word_timestamp_fallback
- end_adjust：waveform_after_low_energy

### Unit 2 / PREVIEW:AU20:S0425

- 教材原文：Let’s meet here on Wednesday after lunch.
- ASR：Let's Let's meet here on Wednesday after lunch.
- speech：102020–105500
- final：101240–105560
- match：HIGH（word_window_match score=1.000）
- boundary：GOOD_BOUNDARY（HIGH）
- start_adjust：waveform_before_low_energy
- end_adjust：waveform_after_low_energy

### Unit 3 / PREVIEW:AU26:S0508

- 教材原文：Can you change your clothes before you come?
- ASR：can you change your clothes before you come?
- speech：14540–18100
- final：14330–18330
- match：HIGH（word_window_match score=1.000）
- boundary：AUTO_RESOLVED（HIGH）
- start_adjust：waveform_before_low_energy
- end_adjust：waveform_after_low_energy

### Unit 4 / PREVIEW:AU28:S0583

- 教材原文：How I wish to have four hands now!
- ASR：How I wish to have four hands now!
- speech：50640–54800
- final：50640–54920
- match：HIGH（word_window_match score=1.000）
- boundary：REAL_UNCERTAIN（BOUNDARY_UNCERTAIN）
- start_adjust：word_timestamp_fallback
- end_adjust：word_timestamp_fallback

### Unit 4 / PREVIEW:AU28:S0590

- 教材原文：“Are you joking?
- ASR：Are you joking?
- speech：83600–84840
- final：83520–84960
- match：HIGH（word_window_match score=1.000）
- boundary：GOOD_BOUNDARY（HIGH）
- start_adjust：word_timestamp_fallback
- end_adjust：word_timestamp_fallback

### Unit 5 / PREVIEW:AU41:S0821

- 教材原文：What does tea mean to you?
- ASR：What does tea mean to you?
- speech：33060–35660
- final：32980–35770
- match：HIGH（word_window_match score=1.000）
- boundary：GOOD_BOUNDARY（HIGH）
- start_adjust：word_timestamp_fallback
- end_adjust：waveform_after_low_energy

### Unit 6 / PREVIEW:AU46:S0901

- 教材原文：Do you remember your first meeting?
- ASR：Do you remember your first meeting?
- speech：16180–18600
- final：16120–18990
- match：HIGH（word_window_match score=1.000）
- boundary：AUTO_RESOLVED（HIGH）
- start_adjust：waveform_before_low_energy
- end_adjust：waveform_after_low_energy

### Unit 6 / PREVIEW:AU47:S0945

- 教材原文：Are you looking at me?
- ASR：Are you looking at me?
- speech：15480–16960
- final：15400–17210
- match：HIGH（word_window_match score=1.000）
- boundary：AUTO_RESOLVED（HIGH）
- start_adjust：word_timestamp_fallback
- end_adjust：waveform_after_low_energy

### Unit 6 / PREVIEW:AU47:S0946

- 教材原文：Do you know me?
- ASR：Do you know me?
- speech：18060–19140
- final：18000–19260
- match：HIGH（word_window_match score=1.000）
- boundary：GOOD_BOUNDARY（HIGH）
- start_adjust：waveform_before_low_energy
- end_adjust：word_timestamp_fallback

## 3. 16 条原 BOUNDARY_UNCERTAIN 重新分类

| 分类 | 数量 |
| --- | ---: |
| AUTO_RESOLVED | 7 |
| GOOD_BOUNDARY | 5 |
| REAL_UNCERTAIN | 3 |
| NEXT_SENTENCE_INTRUSION | 1 |

结论：原 16 条不确定中，12 条可自动认定边界可用，4 条仍需复核。

## 4. 424 条 MATCH_UNCERTAIN 原因统计

| 分类 | 数量 |
| --- | ---: |
| NON_SPOKEN_OR_INSTRUCTION | 113 |
| POSSIBLE_MISMATCH | 175 |
| ASR_ERROR_OR_PARTIAL_MATCH | 136 |

说明：当前匹配器在匹配前已做标点、大小写、常见 contraction 归一化，
因此原本仅属 A/B/C 的差异不会落入 MATCH_UNCERTAIN；uncertain 主要来自：
未朗读文本、ASR 局部漏词/错词、页面文本碎片，以及少量潜在错配。

## 5. 是否发现真正错配

当前 20 条精选全部能通过 word window 找到对应语音，未发现整句跨句错配。
但 MATCH_UNCERTAIN 中仍有需要进一步人工复核的候选。

## 6. 是否发现系统性时间偏移

未发现统一固定偏移；主要问题是句前/句后低能量区间是否足够明显。

## 7. 当前边界算法问题

- 原算法只用 rough window + 低能量区，缺少对前/后句 speech 核心的硬约束。
- 连续朗读时，低能量区可能被下一句弱起音污染。
- 短句更容易被过严阈值判为 uncertain。

## 8. 修改后的算法

```text
word timestamps 确定 speech_start / speech_end
→ 前向搜索 1.2s 内低能量区且不越过上一句 speech_end
→ 后向搜索 1.6s 内低能量区且不越过下一句 speech_start
→ 无可靠低能量时回退到 speech/word 边界安全余量
→ 短句使用放宽但仍受 speech 核心约束的规则
```

## 9. 修改前后通过率

```text
修改前 boundary HIGH：4 / 20
修改后 boundary HIGH：16 / 20
```

## 10. 最终建议

自动边界校准已明显改善，但仍建议对 reviewed JSON 中的边界不确定项做小样本人工复核，
不要直接进入整批正式入库。

## 11. 数据安全

```text
learning.db：未修改
正式内容资源库：未修改
audio_sentence_annotation：未修改
audio_token_annotation：未修改
原始教材：未修改
原始 MP3：未修改
云端调用：0
```

## 12. 最终问题回答

### A. 20 条精选句是否基本可靠？

基本可靠。

- 20/20 都找到对应 word-level 语音窗口；
- 20/20 的 word match 为 HIGH；
- 20/20 新边界均 `final_start_ms < final_end_ms`；
- 修正后 16/20 边界达到 HIGH；
- 4 条仍需复核。

### B. 424 条 MATCH_UNCERTAIN 中真正有问题的有多少？

分类：

```text
NON_SPOKEN_OR_INSTRUCTION：113
ASR_ERROR_OR_PARTIAL_MATCH：136
POSSIBLE_MISMATCH：175
```

其中：

- 113 条主要是页面上的未被朗读内容或 instruction；
- 136 条为 ASR 局部错词/漏词或部分匹配；
- 175 条需要进一步判断，但当前选中 20 条中没有来自这一类；
- 未发现 20 条精选句中的确定错配。

### C. 16 条 BOUNDARY_UNCERTAIN 中真正无法自动确定的有多少？

```text
原 16 条中：
  AUTO_RESOLVED / GOOD_BOUNDARY：12
  REAL_UNCERTAIN：3
  NEXT_SENTENCE_INTRUSION：1
```

真正仍需复核：**4 条**。

### D. 当前边界算法是否需要修正？

需要，且已完成预演修正：

- 原来主要依赖 rough window + 低能量区；
- 新算法先使用 word-level timestamp 确定 speech_start / speech_end；
- 再限制 Start/End 不越过前一句/后一句 speech 核心；
- 最后利用波形低能量区微调。

修改前后：

```text
修改前 boundary HIGH：4 / 20
修改后 boundary HIGH：16 / 20
```

### E. 修正后是否已经具备进入正式批量生产的条件？

```text
暂不具备
```

原因：

- 4 条边界仍需复核；
- MATCH_UNCERTAIN 中仍有 175 条高不确定匹配需要处理；
- 当前仍是预演阶段，正式资源库未写入。

建议下一步只处理这 4 条边界和 175 条高不确定匹配，不扩大精选数量。

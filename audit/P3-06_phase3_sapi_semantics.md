# P3-06 第三阶段 Step 1-C：SAPI AudioPosition 语义最终验证报告

> 只读：未改正式代码 / learning.db / contentpack / 原始教材 / 原始 MP3 / Android；未切割音频、未装依赖、未联网、未建正式时间轴。临时脚本与 WAV 仅在 `%TEMP%`。

## 1. SAPI Grammar 识别能力

**可用（沿用 Step 1-B）**：`GrammarBuilder.Culture=en-GB` + `Grammar(GrammarBuilder)` 可正常加载，受限语法能产生 `RecognitionResult`（Step 1-B 命中 Hello everyone 0.92 / My name is Zhu Xiaomeng 0.85 / I am thirteen years old 0.91）。

## 2. RecognizeAsync 事件顺序（实验 A）：**FAIL（无证据）**

- 运行方式：`RecognizeAsync(RecognizeMode.Multiple)` + `add_SpeechRecognized` / `add_RecognizeCompleted`，输入 `%TEMP%\p306_au06_16k.wav`（43.4s）。
- 实测输出：`ASYNC_RESULTS=0 elapsed=31s` —— 等待 60×500ms 后仍未收到任何 `SpeechRecognized` 事件，`RecognizeCompleted` 亦未在超时内触发；随后 `RecognizeAsyncCancel()`。
- 结论：**事件驱动路径在本环境（PowerShell + System.Speech + 文件输入）未产生任何结果**，无法据此验证事件顺序（不排除是 PowerShell 委托/事件泵问题，但**已无可用证据**，且本任务不允许继续修 SAPI）。

## 3. AudioPosition 语义（实验 B：DictationGrammar 对照）

同一 WAV、同一引擎、自由听写，**同步** `Recognize()` 连续取 8 条结果（原文）：

```
D1|Activity four|0.13|530|1,650
D2|liter and chat to your answers|0.32|0|2,550
D3|all every one|0.45|1,130|1,420
D4|Martin NSQC Al among|0.32|270|3,290
D5|banks 13 years old|0.21|100|2,270
D6|my birthday is in many|0.22|90|2,590
D7|I love sport very much|0.24|440|2,710
D8|higher like many|0.09|370|1,490
```

关键观察：

1. **文本顺序确实跟随音频**：`all every one`（≈ Hello everyone）→ `banks 13 years old`（≈ I'm thirteen years old）→ `my birthday is in many`（≈ My birthday is in May）→ `I love sport very much`（✅ 完全正确），说明引擎的**识别顺序与真实朗读顺序一致**；
2. **AudioPosition 不随顺序递增**：530 → **0** → 1130 → **270** → 100 → 90 → 440 → 370（ms）。这些句子分布在整整 43.4 秒里，而所有位置都小于 **1.2 秒**；
3. 位置与句子实际所处时间**完全不对应**（例如 "I love sport very much" 实际约在第 20 秒附近，却报 440ms）；
4. 识别质量本身也很低（置信度 0.09–0.45），专有名词 `Zhu Xiaomeng` 被识别成 `Martin NSQC Al among`。

**结论：在本项目的文件输入模式下，SAPI 的 `AudioPosition` 不是原始音频的可靠时间位置。**

## 4. DictationGrammar 对照小结

| 检查 | 结果 |
| --- | --- |
| 能否得到文本 | ✅（8 条） |
| 文本是否按音频顺序 | ✅ 顺序跟随（可辨认出教材句子次序） |
| `AudioPosition` 是否单调递增 | ❌ 非单调（530→0→1130→270→100→90→440→370） |
| `AudioPosition` 是否落在对应句位置 | ❌ 全部 <1.2s（实际跨 43.4s） |
| 置信度 | 0.09–0.45（低） |
| 专有名词 | ❌ `Zhu Xiaomeng` → `Martin NSQC Al among` |

## 5. 是否适合句级时间标记

```
FAIL：SAPI 可用于语音识别，但不适合作为本项目的句级时间标记方案。
```

依据（三条独立证据）：
1. Step 1-B 的受限语法结果**顺序错乱**（Hello everyone 被判在 7430ms，而更早的句子被判在 560ms）；
2. 本轮 `RecognizeAsync` **未产生任何事件结果**（无证据可依）；
3. 本轮 DictationGrammar 明确显示 **`AudioPosition` 与原始音频时间不对应**（非单调、全部 <1.2s），且识别质量低、专有名词错误。

**因此正式停止 SAPI 句级时间标记路线**，不再修 SAPI。后续若要句级时间，只剩两条：人工听标（可靠但不可扩展）或安装本地 Whisper 类模型（准确度高，但需你批准安装与下载模型）。

## 6. 数据安全确认

```
Original textbook: unchanged
Original MP3: unchanged
learning.db: unchanged
contentpack: unchanged
formal code: unchanged
Android: unchanged
Cloud AI calls: 0
Third-party installation: 0
Audio splitting: 0
Formal timestamp data: 0
```

完成 A、B 后立即停止，未进入 P3-06 开发，未建立任何正式时间轴数据。

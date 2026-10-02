# P3-06 第三阶段 Step 1-B：SAPI 受限 Grammar 绑定修复验证报告

> 只读验证：未修改正式代码 / learning.db / contentpack / 原始教材 / 原始 MP3 / Android；未切割音频、未安装任何工具、未联网、未生成正式句级时间数据。

## 1. 环境与输入

- Windows 自带 `System.Speech`；识别器 **`MS-2057-80-DESK` / en-GB**（Microsoft Speech Recognizer 8.0 - English (UK)）。
- 音频：`AU06`（官方 MP3，未改动）→ 既有解码产物 → 临时 WAV `%TEMP%\p306_au06_16k.wav`（16kHz/mono/16bit，43.4s）。
- 脚本以 `-File` 方式运行（`%TEMP%\p306_sapi_b.ps1`，临时文件）。

## 2. A. Grammar 绑定：**PASS**

**写法 A 一次成功**（未用到写法 B）：
```powershell
$gb = New-Object System.Speech.Recognition.GrammarBuilder
$gb.Culture = $rec.Culture          # en-GB
$gb.Append($choices)                # 4 条教材原句
$eng.LoadGrammar([System.Speech.Recognition.Grammar]::new($gb))   # 单参数构造
```
输出：`MODE=A` → `GRAMMAR_BINDING=PASS`。

> 关键修正：`GrammarBuilder.Culture` 必须在 `Append` 之前显式设为 en-GB，且 Grammar 必须用**单参数**构造（上次的双参数被 PowerShell 解析成 `Grammar(GrammarBuilder, string ruleName)`）。

## 3. B. 实际识别：**PASS（有结果，但顺序/覆盖不完整）**

真实识别输出（原文，`序号|识别文本|置信度|AudioPosition(ms)|Duration(ms)|end(ms)`）：

```
1|Hello everyone|0.92|7430|1420|8850
2|My name is Zhu Xiaomeng|0.85|730|3260|3990
3|I am thirteen years old|0.91|560|2200|2760
4|My name is Zhu Xiaomeng|0.36|560|2550|3110
RESULTS=4
```

| # | 识别文本 | Confidence | AudioPosition | Duration | start_ms | end_ms | 是否命中目标句 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | Hello everyone | 0.92 | 7430 | 1420 | 7430 | 8850 | ✅ 文本命中 |
| 2 | My name is Zhu Xiaomeng | 0.85 | 730 | 3260 | 730 | 3990 | ✅ 文本命中 |
| 3 | I am thirteen years old | 0.91 | 560 | 2200 | 560 | 2760 | ✅ 文本命中 |
| 4 | My name is Zhu Xiaomeng | 0.36 | 560 | 2550 | 560 | 3110 | ⚠️ 重复且低置信 |
| — | I want to make friends with you all | — | — | — | — | — | ❌ 未命中 |

## 4. C. 时间标记：**PARTIAL（有值，但不可直接采信）**

- ✅ 确实取得了 `AudioPosition` + `Duration`（4 条结果全部有值）；
- ❌ 但**位置与音频真实顺序不一致**：AU06 开头就是 "Hello everyone!"，引擎却把 `Hello everyone` 判在 **7430ms**，而 "My name is Zhu Xiaomeng" 判在 730ms、"I am thirteen years old" 判在 560ms ——与教材朗读顺序矛盾；
- ❌ 出现重复命中（#2 与 #4 同为 "My name is Zhu Xiaomeng"，置信度 0.85 / 0.36）；
- ❌ 4 句中 1 句（I want to make friends with you all!）未命中。

结论：**SAPI 能返回句级时间值，但这些值目前不能用来建立句子时间轴。**

## 5. D. 总结

```
PARTIAL：Grammar 已打通，但识别/时间位置仍不可靠
```

依据：Grammar 绑定与识别链路**已验证可行**（0.85–0.92 的高置信命中说明"受限语法 + 教材原句"这条路本身成立），但**时间位置精度与覆盖不足**（顺序错位、重复、漏句），因此不能进入"自动候选 → 人工确认"的标定流程；若要用，只能作为"人工确认前的粗候选"，并需先解决顺序错位问题。

**建议（不实施）**：① 改用 `RecognizeAsync` 顺序消费 + 记录每次识别的时间游标，确认 `AudioPosition` 语义；② 用 `DictationGrammar` 跑一次自由听写，对照真实顺序定位问题；③ 若仍不可靠，再评估安装本地 Whisper（需你批准）。

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
Formal audio timestamp data: 0
```

临时产物仅位于 `%TEMP%`（`p306_au06_16k.wav`、`p306_sapi_b.ps1`）。完成验证，立即停止，不继续 P3-06 开发。

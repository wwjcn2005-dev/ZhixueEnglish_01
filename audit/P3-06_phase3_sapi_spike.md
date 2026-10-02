# P3-06 第三阶段 Step 1：SAPI 受限语法最小验证报告

> **只读验证**：未修改任何正式代码 / `learning.db` / contentpack / 原始教材 / 原始 MP3；未切音频、未转码正式音频、未安装任何工具、未联网、未调用云端 AI。
> **Original textbook: unchanged　|　Original MP3: unchanged　|　learning.db: unchanged　|　contentpack: unchanged　|　formal code: unchanged　|　Cloud AI calls: 0**

---

## 1. 环境

| 项 | 实测 |
| --- | --- |
| Windows 语音引擎 | ✅ **存在**：`InstalledRecognizers()` 返回 `MS-2057-80-DESK` / **en-GB** / *Microsoft Speech Recognizer 8.0 for Windows (English - UK)*（另有 zh-CN 引擎） |
| 调用方式 | `Add-Type -AssemblyName System.Speech`（Windows 自带，**零安装**） |
| 是否联网 | **否**（全程离线） |
| Cloud AI calls | **0** |
| 音频解码 | 项目既有 `builder/mp3_to_wav.ps1`（WinRT，离线；本轮仅复用其**已存在**的解码产物） |
| 临时格式转换 | ✅ 用 Python 标准库 `wave`+`audioop`（`tomono` + `ratecv`）把 AU06 从 **48kHz 立体声**转为 **16kHz 单声道 16bit PCM**，输出到 `%TEMP%\p306_au06_16k.wav`（**未使用任何外部转换工具**） |

## 2. 输入

| 项 | 值 |
| --- | --- |
| 源音频（项目内已解码） | `audit/P3-01_tmp/wav/AU06.wav` — 48kHz / 2ch / 16bit / 2,080,861 frames |
| 时长 | **43.4s**（对应官方 `AU06` = `06_Starter_Get to know each other_4 Read and check your answers.mp3`；原始 MP3 **未改动**） |
| 临时 WAV | `%TEMP%\p306_au06_16k.wav`（16kHz / mono / 16bit，1,387,286 B） |
| 受限语法目标句 | ① `Hello everyone`　② `My name is Zhu Xiaomeng`　③ `I am thirteen years old`　④ `I want to make friends with you all` |

## 3. SAPI 结果

| Target sentence | Recognized text | Confidence | AudioPosition | Duration | start_ms | end_ms | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Hello everyone! | — | — | — | — | — | — | **未执行到识别** |
| My name is Zhu Xiaomeng. | — | — | — | — | — | — | **未执行到识别** |
| I'm thirteen years old. | — | — | — | — | — | — | **未执行到识别** |
| I want to make friends with you all! | — | — | — | — | — | — | **未执行到识别** |

### 实际发生的两个技术阻塞（原文错误）

1. 首次尝试（`GrammarBuilder` 未设 Culture）：
   > `Exception calling "LoadGrammar" ... "The language for the grammar does not match the language of the speech recognizer."`
2. 修正尝试（改用 `New-Object Grammar($gb,$ci)`）：
   > `Exception calling ".ctor" with "2" argument(s): "'en-GB' rule not found or not public."`
   → PowerShell 把 `Grammar(GrammarBuilder, CultureInfo)` 解析成了 `Grammar(GrammarBuilder, string ruleName)` 重载，语法对象创建失败。
3. 第三次尝试（`[System.Speech.Recognition.Grammar]::new($gb)` + 先设 `$gb.Culture`）：**命令返回空输出**，未捕获到任何识别结果（该次运行未能给出可判定证据）。

> 本次**未产生任何 start_ms/end_ms**；因此没有可写入 `audit/P3-06_samples/shadowing_samples.json` 的候选时间。

## 4. 判断

**FAIL（本轮未完成验证）**

| 检查项 | 结果 |
| --- | --- |
| 1. 是否成功命中教材原句 | ❌ 未获得任何识别结果 |
| 2. 是否成功取得 AudioPosition | ❌ |
| 3. 是否成功取得 Duration | ❌ |
| 4. 时间区间是否基本覆盖目标句 | ❌ 无数据 |
| 5. 是否足以进入"自动候选 + 人工确认" | ❌ 尚不足 |

**但基础设施已验证可用**（这部分是 PASS）：

- ✅ Windows 自带 en-GB 离线识别引擎存在（`MS-2057-80-DESK`）；
- ✅ 项目音频可离线解码并**用标准库**转换为 SAPI 可读的 16kHz mono PCM（无需安装任何工具）；
- ✅ `SetInputToWaveFile()` 路径已打通到"加载语法"这一步。

**剩余阻塞点（明确且很小）**：**受限语法（Choices）的 culture/constructor 绑定**。下一步只需试两条标准写法之一：

```powershell
# 写法 A：GrammarBuilder 显式文化 + 单参构造
$gb = [System.Speech.Recognition.GrammarBuilder]::new()
$gb.Culture = [System.Globalization.CultureInfo]::new('en-GB')
$gb.Append($choices)
$e.LoadGrammar([System.Speech.Recognition.Grammar]::new($gb))

# 写法 B：用 SRGS 字符串 + xml:lang
$srgs = '<grammar xml:lang="en-GB" version="1.0" root="r"><rule id="r"><one-of><item>Hello everyone</item>...</one-of></rule></grammar>'
$e.LoadGrammar([System.Speech.Recognition.Grammar]::new([System.Speech.Recognition.SrgsGrammar.SrgsDocument]::new([xml]$srgs)))
```

## 5. 数据安全确认

```
Original textbook: unchanged
Original MP3:      unchanged
learning.db:       unchanged
contentpack:       unchanged
formal code:       unchanged
Cloud AI calls:    0
```

本阶段未修改任何正式代码 / Web / Android / contentpack / learning.db / 原始教材 / 原始 MP3；未切割、未转码（仅把**已解码的中间产物**在 `%TEMP%` 转成 16kHz mono 临时 WAV）；未安装任何依赖；未联网；未把任何候选时间写入正式或实验数据。

---

## 停止声明

Step 1 完成（结果为 **FAIL**：引擎可用、语法绑定未打通、未获得时间数据）。**立即停止**：未继续开发 P3-06、未建立正式 sentence timestamp 数据、未安装任何新工具。等待项目负责人决定是否按 §4 的写法 A/B 再试一次。

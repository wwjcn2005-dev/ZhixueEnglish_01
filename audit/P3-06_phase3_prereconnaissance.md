# P3-06 第三阶段前置侦察：教材原句自动定位可行性

> **只读侦察**：未修改任何代码 / Web / Android / contentpack / learning.db / 原始教材 / 原始 MP3；未切音频、未转码、未上传、未调用云端 AI、**未安装任何依赖**。
> **Original textbook: unchanged　|　Original MP3: unchanged　|　Cloud AI calls: 0**

---

## 1. 当前阻塞是否可以通过自动/半自动定位解除

**结论：有希望，但取决于一个此前未被检查的本地能力（见 §2 的 SAPI 发现）。**

- 第三阶段**没有**沿用第二阶段的静音分组（已证伪：AU06 8 句 vs 14/13/12/10 组；AU13 9 句 vs 42/36/30/21 组）。
- 本阶段新发现：**Windows 自带离线英文语音识别引擎**（无需安装、无需联网），具备"音频 → 带时间位置的文字"的**潜在**能力 → 因此结论为：

```
RECOMMENDED（建议按 §9 的 SAPI 路线做一次 30 分钟的只读实验）
```

但必须诚实标注：该能力**尚未在本项目音频上实测**（本轮只做到"发现与评估"），因此不构成"已具备"的承诺。

## 2. 当前环境已有能力（本轮新增实测）

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| **Windows SAPI 离线识别引擎（en-GB）** | ✅ **AVAILABLE** | `Add-Type -AssemblyName System.Speech` → `SpeechRecognitionEngine.InstalledRecognizers()` 返回 **`MS-2057-80-DESK` / en-GB / Microsoft Speech Recognizer 8.0 for Windows (English - UK)**（另有 zh-CN 引擎） |
| SAPI 是否支持音频文件输入 | ⚠️ 未实测 | API 上存在 `SetInputToWaveFile()`（供只读实验用；需 16bit PCM WAV，项目已有 WinRT 解码脚本可产出） |
| SAPI 是否支持受限语法（已知句子） | ⚠️ 未实测 | API 上可用 `GrammarBuilder`/`Choices` 直接给出"教材原句"作为语法 → 命中结果带 `AudioPosition` + `Duration`，即句级区间（这正是本项目需要的形态） |
| 本地 Whisper / faster-whisper / whisper.cpp / Vosk | ❌ **UNAVAILABLE** | P3-03 已全量核查（pip 包、site-packages、可执行文件、模型文件均为 0） |
| ffmpeg / ffprobe / sox | ❌ UNAVAILABLE | 同上 |
| 强制对齐工具（MFA / gentle / aeneas） | ❌ UNAVAILABLE | 同上 |
| MP3 离线解码 | ✅ AVAILABLE | `builder/mp3_to_wav.ps1`（WinRT，离线） |
| 静音/能量分析 | ✅ AVAILABLE | 仅作辅助证据（第二阶段已证伪其单用价值） |

## 3. 已有教材资产（可直接复用）

| 资产 | 位置 | 状态 |
| --- | --- | --- |
| 5 句教材原句（本 Spike 样本） | `audit/P3-06_samples/shadowing_samples.json` | ✅ 已就绪（`start_ms/end_ms` 为 null、`timing_source=unverified`） |
| 教材原句逐字来源 | `audit/P3-05_samples/shadowing_manifest.json`（含 `source_blocks`） | ✅ 逐句已在教材块内验证 |
| 官方 MP3 | `2025年度初一外研版英语教材\AU06 / AU13 …`（54 个） | ✅ SHA 与 contentpack 一致 |
| 音频↔活动映射 | `exercise_audio_map_v3.json` | ✅ 54/54 CONFIRMED（AU06↔Starter A4；AU13↔Unit 1 RfW A2） |
| 已解码 WAV（本 Spike 用） | `audit/P3-01_tmp/wav/AU06.wav`（48kHz/mono 视解码而定） | ✅ 已存在，可直接喂给 SAPI 实验 |
| 字幕 / 转写 / 时间轴 sidecar | 教材目录与全项目检索 | ❌ **不存在**（无 .srt/.vtt/.lrc/.txt/.json 字幕，无 transcript/whisper/asr 文件） |
| 其他"看似时间信息"的来源 | 派生词 manifest（288 词的 start/end） | ⚠️ 仅限**词表音频**的单词，且为派生资源（非句子级、非官方） |

## 4. 可行技术路线比较

| 路线 | 现有能力 | 词级时间 | 准确度（预估） | 安装 | 是否触网 | 本项目适用性 |
| --- | --- | --- | --- | --- | --- | --- |
| 人工听标（第二阶段方案） | 无需工具 | —（人工） | 最高 | 无 | 无 | 可靠但**不可扩展**（54 音频×数百句） |
| **SAPI 受限语法识别（新发现）** | ✅ 引擎已有 | 短语级 `AudioPosition`+`Duration`（≈句级） | 中（朗读式教材音频 + 已知句子约束，命中率预期较高） | **无需安装** | **无需联网** | ⭐ **优先实验**：句子集合已知，恰好匹配"受限语法"场景 |
| SAPI 自由听写 + 文本匹配 | ✅ 引擎已有 | 短语级 | 中低（专有名词 `Zhu Xiaomeng` 易错） | 无需安装 | 无需 | 次选（需模糊匹配，风险高于受限语法） |
| Whisper / faster-whisper | ❌ 无 | 词级 | 高 | **需安装 + 下载模型** | 需联网下载模型 | 效果最好但**当前禁止安装**，且对 GPU 4GB 需量化 |
| whisper.cpp（GGML） | ❌ 无 | 词级 | 高 | 需下载二进制 + 模型 | 需联网 | 同上 |
| 强制对齐（MFA/gentle/torchaudio） | ❌ 无 | 词级 | 很高（文本已知时） | 需安装 + 词典/模型 | 需联网 | 语义上最贴合，但安装成本最高 |

## 5. 是否需要安装新依赖

**本阶段不需要，也不允许。** 结论：

- 若 **SAPI 受限语法路线**实测可用 → **完全无需安装任何依赖**，可离线完成句级定位，且天然满足"文本已知"的项目特性；
- 仅当该路线实测失败时，才需要评估安装 Whisper 系列（届时另开任务、由你批准）。

## 6. 如果需要，推荐什么

按优先级：
1. **SAPI 受限语法（先做只读实验，零安装）**；
2. 失败 → `faster-whisper`（`small`/`medium` int8，CPU 或 GTX 1070）+ 已知句文本匹配；
3. 再失败 → MFA / torchaudio forced-align（最贴合但最重）。

**不推荐**：云端 ASR（费用 + 教材音频外传，均被项目原则禁止）。

## 7. 是否需要 AI

**不需要云端 AI。** SAPI 是本地离线引擎，不属于"云端 AI"；Whisper 类模型本地运行也属于"本地模型辅助"，但**本阶段一律不安装**。

```
Cloud AI calls: 0
```

## 8. 对教材/音频是否有任何修改

```
Original textbook: unchanged
Original MP3: unchanged
```

本阶段未切音频、未转码、未改名、未修改 contentpack / learning.db / 代码 / Android。新增文件仅本报告（另有第二阶段已存在的 `audit/P3-06_samples/shadowing_samples.json`）。

## 9. 最小推荐方案（建议，不实施）

**Step 1（10 分钟，只读实验）**：用项目已有的 `AU06.wav`，在 PowerShell 里跑一次 SAPI 受限语法识别：

```powershell
Add-Type -AssemblyName System.Speech
$e = New-Object System.Speech.Recognition.SpeechRecognitionEngine(
       [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() |
       Where-Object { $_.Culture.Name -eq 'en-GB' } | Select-Object -First 1)
$g = New-Object System.Speech.Recognition.Grammar(
       (New-Object System.Speech.Recognition.GrammarBuilder('Hello everyone')))
$e.LoadGrammar($g)
$e.SetInputToWaveFile('D:\ZhixueEnglish\audit\P3-01_tmp\wav\AU06.wav')
$r = $e.Recognize()      # 或循环 Recognize 取多句
$r.Text; $r.Audio.AudioPosition.TotalMilliseconds; $r.Audio.Duration.TotalMilliseconds
```

**Step 2**：若命中且时间位置合理 → 对 5 句逐一做（可把 5 句一起放进一个 `Choices` 语法），得到候选 `start_ms/end_ms`，标注 `timing_source=sapi_constrained`、`verification_status=CANDIDATE`，**仍需人工在手机上听一遍再升级为 `manual_verified`**（守住"未验证数据不进正式系统"）。

**Step 3**：只有 Step 1 失败，才谈安装 Whisper。

**风险提示**：① SAPI 8.0 引擎较老，对朗读式教材音频的准确度未知；② 需要 PCM WAV（项目已有解码脚本）；③ 即使自动命中，`Zhu Xiaomeng` 这类专有名词仍需模糊匹配 + 人工确认；④ 自动结果**只能作为候选**，不能直接进正式数据。

---

## 最终结论

```
RECOMMENDED
```

**理由**：本轮发现了第二条路径——**Windows 自带 en-GB 离线识别引擎（SAPI）可用于"已知句子的受限语法定位"**，它零安装、零联网、零费用，且与本项目"文本已知"的特性天然匹配；而 Whisper/强制对齐虽然准确度更高，但都需要安装与联网下载模型（当前被明令禁止）。

**下一步建议**：批准执行 §9 Step 1 的 10 分钟只读实验；成功则进入"自动候选 + 人工确认"的半自动标定流程，失败再评估安装 Whisper。

> 本次仅完成只读侦察，未修改任何文件、数据库、Android 工程或原始教材/音频；Cloud AI calls: 0。

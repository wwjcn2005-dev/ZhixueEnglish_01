# P3-03：本地离线语音转写 / 强制对齐技术选型验证

> **纯只读技术验证**：未修改正式代码 / 数据库 / contentpack / 音频 / Web / Android / V1.2.1 / learning 服务；**AI 调用 0**；**外部网络请求 0**；**未安装任何东西**（未 pip install、未下载模型、未改 PATH）。
> 结论先行：本机**没有任何可用的本地 ASR / 强制对齐实现或模型**，三条路线（A/B/C）**本阶段均不可执行** → 最终判断 **D（当前不建议继续）**，并给出解除条件。

---

## 1. 环境检查（实测）

| 项 | 实测值 |
| --- | --- |
| Python | **3.12.10**（`C:\Users\wwenj\AppData\Local\Programs\Python\Python312`） |
| pip | 25.0.1 |
| CPU | Intel **i5-14400F**（10 核 / 16 线程） |
| RAM | **15.8 GB** |
| GPU | **NVIDIA GeForce GTX 1070**（4 GB，驱动 32.0.15.6094） |
| CUDA 工具链 | **UNAVAILABLE**（无 `nvcc`、无 CUDA Toolkit） |
| 既有离线能力 | `wave` + `audioop`（PCM/RMS）、`builder/mp3_to_wav.ps1`（WinRT 解码，离线无安装） |

## 2. 已有工具（AVAILABLE）

| 工具/能力 | 状态 | 说明 |
| --- | --- | --- |
| Python 3.12 + `wave` / `audioop` | **AVAILABLE** | 只能做波形/静音分析，**不是 ASR，也不是强制对齐** |
| 官方 MP3 离线解码（WinRT 脚本） | **AVAILABLE** | 输出写在 `audit/P3-01_tmp/wav/` |
| 静音/能量分段（项目既有参数） | **AVAILABLE** | HOP 10ms / MIN_GAP 200ms |
| GTX 1070 | 硬件 **AVAILABLE**，但无 CUDA Toolkit、无框架 | 仅说明"若获准安装，GPU 路线可行" |

## 3. 不可用工具（UNAVAILABLE）

**可执行文件**：`ffmpeg`、`ffprobe`、`sox`、`whisper`、`whisper-cli`(whisper.cpp)、`nvcc`、`git` → **全部 UNAVAILABLE**。

**Python 包**（`pip list` 全量过滤，命中 0）：`torch`、`torchaudio`、`transformers`、`ctranslate2`、`openai-whisper`、`faster-whisper`、`vosk`、`speech_recognition`、`onnxruntime`、`montreal-forced-aligner`、`gentle`、`aeneas`、`numpy`、`scipy`、`librosa`、`soundfile`、`pydub` → **全部 UNAVAILABLE**。
`site-packages` 中 ASR/音频处理相关目录：**0 个**。

**模型文件**：在 `%USERPROFILE%`、`D:\`、`Program Files`、`Program Files (x86)` 做深度 ≤3 有界搜索（关键词 `ggml*.bin`/`whisper`/`vosk`/`wav2vec`/`deepspeech`/`kaldi`/`montreal`/`aeneas`/`gentle`）→ **未发现任何已存在模型或二进制**。

> 按任务要求：不存在即记录 UNAVAILABLE，**不安装、不下载**。

## 4. 可验证技术路线（分类与可执行性）

| 路线 | 需要的组件 | 本机是否已有 | 能否实际运行 |
| --- | --- | --- | --- |
| **A 完整离线 ASR**（audio → transcript + word timestamps → 匹配句子） | Whisper / faster-whisper / whisper.cpp / Vosk + 模型 + 解码器 | ❌ | **❌** |
| **B 强制对齐**（已知句子 + audio → start/end） | MFA / gentle / aeneas / torchaudio forced-align + 声学模型 + 发音词典 | ❌ | **❌** |
| **C ASR + 对齐精修** | A + B | ❌ | **❌** |
| （对照）静音/能量分段 | `wave` + `audioop`（已有） | ✅ | ✅ 已跑（P3-01/P3-02） |

## 5. 实际运行结果

本阶段**没有任何 ASR/对齐工具可运行**，因此**未产生新的转写或对齐结果**，只复核了非 ASR 基线的既有数值：

| 测试 | 目标 | 结果 |
| --- | --- | --- |
| 测试 1｜AU06 | `Hello everyone!` | 静音基线 **560–2090 ms**（1530 ms）→ **CANDIDATE**（无 ASR 复核） |
| 测试 2｜AU13 | 多人对话中的完整句 | **无法定位** → **NEEDS_REVIEW** |
| 测试 3｜填空恢复句 | 如 `I am ______ years old.` | **无法恢复**（完整句只存在于音频中）→ **NEEDS_REVIEW** |

## 6. AU06 结果

- 教材文本 `P15:B3` 完整无空位；目标句 `Hello everyone!`（textbook-derived，非音频恢复）
- 静音基线边界：**start 560 ms / end 2090 ms / duration 1530 ms**
- 词级时间戳：**UNAVAILABLE**；独立复核（切片重识别 == 目标句）：**UNAVAILABLE**
- 状态：**CANDIDATE**（不满足 CONFIRMED 第 7 项）

## 7. AU13 结果

- 对话文本有提取瑕疵（重复片段 `MiaA paper boat?`、说话人标签与句子粘连）
- 无 ASR → 无法确认哪段时间对应哪一句；多人对话还存在说话人切换/重叠问题
- 状态：**NEEDS_REVIEW**

## 8. 填空句结果

- Starter A3（AU02）等填空类：教材原题含作答空位，**完整句只存在于音频里**
- 无 ASR → 既不能恢复文本、也不能定位时间
- 状态：**NEEDS_REVIEW**（与 P3-01/P3-02 一致）

## 9. 时间边界

| 来源 | AU06 目标句 | 可靠性 |
| --- | --- | --- |
| 静音/能量分段（可运行） | 560–2090 ms | **辅助证据**：起点即语音、终点后有 ≥200ms 静音；但不能证明内容就是该句 |
| ASR 词级时间戳 | —— | **UNAVAILABLE** |
| 强制对齐 | —— | **UNAVAILABLE** |

## 10. 实验切片

- **未生成新的实验切片**：§十三 要求"只有在得到可信时间范围后才做"，可信范围需 ASR/对齐复核，本机不具备 → 未达标即不产出。
- `audit/P3-03_samples/` 只保存复核记录（无音频副本）。
- 可参考的既有切片（P3-02，同为 CANDIDATE）：`audit/P3-02_samples/sample_02_sentence_01.wav`（AU06 560–2090ms）、`sample_01_word_01.wav`。

## 11. 路线比较

| 路线 | 已知完整句 | 需要 ASR | 词级时间 | 边界可靠性 | 复杂度 | 本机可执行 |
| --- | --- | --- | --- | --- | --- | --- |
| **A 完整 ASR** | 可选 | 需要 | ✅ | 中～高（受识别错误影响） | 中 | ❌ |
| **B 强制对齐** | **必需** | 不需要 ASR，但需声学模型 + 发音词典 | ✅ | **高**（文本正确前提下） | 中高 | ❌ |
| **C ASR + 对齐** | 必需 | 需要 | ✅ | **最高** | 高 | ❌ |
| （对照）静音分段 | 不需要 | 不需要 | ❌ | 低（只知道"有声音的段"） | 低 | ✅ |

**最适合"教材已知文本 + 官方音频 → 短句音频"的是 B（强制对齐），而不是 A。**
原因：本项目输入天然包含**权威文本**（教材印刷句），B 只需"文本 + 音频"就能给出词级时间，不需要 ASR 先把文本猜一遍；A 反而会引入识别错误。C 适合作为文本与音频不完全一致时的兜底。

## 12. 人工工作量评估

| 方案 | 每句人工量 | 54 音频 / 数百句可扩展性 |
| --- | --- | --- |
| 纯人工拖时间轴 | 高 | **不可扩展** |
| 静音分段 + 人工校句 | 中 | 勉强，错误率不可控 |
| **强制对齐 + 人工抽查** | 低（约 5–15% 抽查） | **可扩展（推荐目标）** |
| ASR + 对齐 + 抽查 | 低 | 可扩展，依赖 ASR 质量与算力 |

## 13. 最终判断

### **D —— 当前不建议继续。**

**技术瓶颈（唯一且明确）**：本机**不存在任何本地离线 ASR / 强制对齐实现或模型**，本阶段**禁止安装**，因此"完整句文本 ↔ 音频时间轴"的可靠对应**在当前环境无法建立**，句级 CONFIRMED 必然为 0。

**解除条件（供决策，不实施）**：
1. 由用户批准安装**离线**方案之一（不联网、不上传教材）：首选 `faster-whisper`（CPU int8 或 GTX 1070 CUDA float16，用其 word timestamps 做已知句匹配）；或 `whisper.cpp`（GGML 量化，CPU/4GB 显存均可）；或 **MFA / torchaudio forced-align**（最贴合路线 B，但需发音词典）。
2. 安装后按 P3-02 样本重跑测试 1–3，以"切片重新识别 == 目标句"作为 CONFIRMED 门槛。
3. 依硬件（i5-14400F + 16 GB + GTX 1070）判断：**路线 B/C 预计可达 B 级（自动对齐 + 人工抽查）**，句级规模化生产才具现实可行性。

## 14. 基线保护（实验后复核）

| 对象 | 结果 |
| --- | --- |
| `learning.db` | **unchanged** — `0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91` |
| contentpack | **unchanged** — `ACEBC8C29CF5D11BAB50BF7962FBEE5DE42CD9CFC7FE48AB6316699D265E1A3F` |
| 54 个正式 MP3 | **unchanged** — 数量 54，SHA 集合指纹 `C2E2E60E7DE50691D5315C4A55E7C3BA` |
| V1.2.1（docx / md） | **unchanged** — `31AC3638F324C237…` / `C4532C79C7EDCB17…` |
| `web/`（19 个 .py） | **unchanged**（app.py `07E9B01FC61D`、ui.py `0D86391E57CE`、exercises.py `71B62DCC52C6` …） |
| `learning/`（15 个 .py） | **unchanged**（evidence_service.py `864536DEF937`、learning_object_service.py `56C4F4140EC6` …） |
| Android | **unchanged** |
| AI calls / external network / installs | **0 / 0 / 0** |

**新增文件（仅本任务）**：本报告、同名 `.json`、`audit/P3-03_samples/`（复核记录，无音频副本、无正式文件改动）。

## 15. 停止声明

P3-03 完成，**立即停止**：未修改正式代码/数据、未建正式 sentence 表、未改 contentpack / audio mapping / UI / 学习服务 / Evidence / Android / V1.2.1、未批量处理 54 个 MP3、**未进入 P3-04**。等待下一步指令（例如：是否批准安装离线 ASR / 对齐组件）。

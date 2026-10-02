# P3-02：教材完整短句恢复 → 官方音频定位 → 短句切片可行性验证

> **只读、隔离、小规模技术验证**：未修改正式数据库 / contentpack / 教材数据 / 正式音频 / Web / Android / V1.2.1 / learning 服务；**AI 调用 0**；**外部网络请求 0**；未安装任何依赖。
> 实验产物：`audit/P3-02_samples/`（脚本、样本 JSON、2 个真实切片 WAV）。

---

## 1. 环境检查（AVAILABLE / UNAVAILABLE）

| 项 | 结果 |
| --- | --- |
| Python | **AVAILABLE** — Python 3.12.10 |
| `wave` / `audioop`（PCM 读写与 RMS） | **AVAILABLE** |
| `numpy` / `pydub` / `soundfile` / `librosa` | **UNAVAILABLE** |
| ffmpeg / ffprobe / sox | **UNAVAILABLE** |
| 强制对齐工具（gentle / MFA） | **UNAVAILABLE** |
| **本地 ASR**（whisper / faster-whisper / vosk / speech_recognition / torch） | **`LOCAL_ASR_UNAVAILABLE`** |
| MP3 **解码**（离线） | **AVAILABLE** — 项目既有 `builder/mp3_to_wav.ps1`（WinRT，无安装、无网络） |
| MP3 **编码** | **UNAVAILABLE** → 本实验只能产出 **WAV** 切片 |
| 正式音频目录 / 数量 | `D:\ZhixueEnglish\2025年度初一外研版英语教材` ｜ 54 个 MP3（未改动） |
| 教材文本 / 填空 / audio mapping 数据 | 均只读可用（contentpack、`exercise_audio_map_v3.json`、派生词音频 manifest） |

未因缺依赖安装任何东西。按任务要求：**无 ASR → 报告 `LOCAL_ASR_UNAVAILABLE` 并继续做可验证实验**。

## 2. 样本与结果（5 个样本，覆盖 A–E）

| 样本 | 类别 | 音频 | 教材文本 | 恢复完整句 | 定位方法 | 切片 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | 对照样（词表） | AU48（90.2s） | 印刷词表 `ready` | ✅ `ready` | 既有派生 manifest（同静音法） | ✅ `sample_01_word_01.wav`（5550–6240ms，690ms） | **CANDIDATE** |
| S2 | A/C 完整短句（连续句首句） | AU06（43.4s） | P15:B3 完整无空位 | ✅ `Hello everyone!` | order_position（第 1 个语音段=第 1 句） | ✅ `sample_02_sentence_01.wav`（560–2090ms，1530ms） | **CANDIDATE** |
| S3 | A 单个填空句 | AU02（33.5s） | 含空位（a/an 或数字） | ❌ | — | ❌ | **NEEDS_REVIEW** |
| S4 | B 一句多空 / E 长音频 | AU12（175.0s） | 含作答空位 | ❌ | — | ❌ | **NEEDS_REVIEW** |
| S5 | D 多人对话 | AU13（101.4s） | 对话文本有提取瑕疵（重复片段、说话人标签粘连） | ❌ | — | ❌ | **NEEDS_REVIEW** |

自动检查（真实数值）：

- S1 切片：1 个语音段、峰值 **−24.9 dB**、起点 0ms 即语音（`head_ok=true`），无前导静音被切掉。
- S2 切片：2 个语音段（句内停顿）、首段起点 0ms、末段在 1530ms 内结束（`head_ok=true`、`tail_ok=true`）。
- 两个切片均落在相邻语音之间的**≥200ms 静音区**上，未串入相邻句（依据：原音频静音分析中该区间的间隔）。

## 3. 统计

| 指标 | 数值 |
| --- | ---: |
| 样本总数 | 5 |
| 完整句恢复成功 / 失败 | **2 / 3** |
| 可唯一定位 / 无法唯一定位 | **2 / 3** |
| 切片成功 / 失败 | **2 / 3** |
| CONFIRMED / CANDIDATE / NEEDS_REVIEW | **0 / 2 / 3** |
| 完整句恢复率 | **0.40** |
| 唯一定位率 | **0.40** |
| 可用切片率 | **0.40** |

## 4. 关键假设验证：「知道完整句子以后，定位是否更容易？」

| 样本 | 目标句 | 音频长度 | 定位耗时 | 切片长度 | ASR 结果 | 边界情况 | 最终状态 |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| S1 | `ready` | 90.2s | 即时（既有 manifest） | 0.69s | 无 ASR | 前后静音清晰 | CANDIDATE |
| S2 | `Hello everyone!` | 43.4s | 即时（第 1 语音段） | 1.53s | 无 ASR | 句内 1 次停顿，前后静音 | CANDIDATE |
| S3–S5 | 需从音频恢复 | 33.5 / 175.0 / 101.4s | **无法定位** | — | 无 ASR | — | NEEDS_REVIEW |

**结论：在没有 ASR/转写的前提下，"先有完整句"并不能让定位变容易。**
完整句只提供"要找什么"，不提供"在哪里"；没有匹配器时，两条路线的瓶颈完全相同 —— 只能靠静音段的位置顺序，而实测证伪了"段数=句数"（AU06：8 句 vs 14 段；AU13：9 句 vs 42 段；AU07：42 段）。
**有了 ASR/转写之后，两者难度会立刻分岔**：完整句可以做精确文本匹配（大小写/标点归一），而"直接猜边界"仍不可行。

## 5. 最终判断

**C —— 只能对部分教材音频可靠实现。**

- **可靠的**：结构与印刷文本一一对应的**枚举类音频**（词表），以及"完整、无空位、且位于音频开头"的短句（首句边界可由起点+首个静音确定）。本实验已实际切出 2 个可用 WAV 切片。
- **不可靠的**：绝大多数**填空/听力类**（完整句不在教材事实内）、**多人对话**（需说话人切分）与**长音频**（句级边界需要转写）。CONFIRMED 为 **0**，因为没有任何一条满足"切片重新识别与目标句一致"（无 ASR，无法做这一步）。
- 若把"句级"目标降级为**活动级跟读**（官方完整音频 + 教材完整文本），则可直接进入小规模建设 —— 归属与音频都已有 CONFIRMED 证据，且不需要切割。
- 若坚持句级：**前置条件是补齐本地离线转写/强制对齐**（本机当前 `LOCAL_ASR_UNAVAILABLE`），否则只能停留在人工逐句核验。

## 6. 基线保护

| 对象 | 结果 |
| --- | --- |
| `learning.db` | **未改变**：SHA256 `0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91`，mtime 2026-09-13 15:50:09（start=end；该 SHA 与 P2-6-F 基线的差异来自 15:50:08 的真机词汇学习记录，发生在 P3-01/P3-02 之前，非本任务写入） |
| contentpack | **未改变**：`ACEBC8C29CF5D11BAB50BF7962FBEE5DE42CD9CFC7FE48AB6316699D265E1A3F` |
| 正式 MP3（54 个） | **未改变**（只读；解码输出全部写在 `audit/P3-01_tmp/wav/` 与 `audit/P3-02_samples/`） |
| V1.2.1（docx/md） | **未改变** |
| 正式代码（web / learning / builder 既有文件） | **未改变**（新增文件仅本任务脚本与产物，全部位于 `audit/`） |
| 测试基线 | 未运行、未修改 |
| AI 调用 / 外部网络 | **0 / 0** |
| Git | 本机无 `git` 命令（不可用，如实记录） |

## 7. 产出清单

- 本报告 + `P3-02_sentence_audio_alignment_validation.json`
- `audit/P3-02_samples/p302_experiment.py`（实验脚本，不进入正式业务代码）
- `audit/P3-02_samples/`：`p302_results.json`、5 个样本 JSON、`sample_01_word_01.wav`、`sample_02_sentence_01.wav`
  （按任务要求同时应产出 `.mp3`，但本机 **无 MP3 编码器（ffmpeg 等均 UNAVAILABLE）**，且不得安装依赖 → 只产出 WAV，如实记录）

## 8. 停止声明

只读验证完成，**立即停止**：未修改正式代码/数据、未建正式数据库、未批量切音频、未接入 UI/学习证据/AI 评分/Android、未进入 P3-03。

# P3-06 Step 4 实施报告：D 盘部署 faster-whisper + AU06 最小验证

## 1. 环境

| 项 | 值 |
| --- | --- |
| Python | 3.12.10（系统 Python 只用于创建 venv，未修改） |
| GPU / VRAM | NVIDIA GTX 1070 / **8192 MiB** |
| Driver | 560.94（`nvidia-smi` 可用） |
| CUDA Toolkit | **未安装也不需要**（未安装、未修改 PATH） |
| C / D 剩余空间 | C: 14.1 GB ｜ **D: 72.6 GB** |

## 2. D 盘部署（全部在 D 盘，未使用 C 盘）

| 项 | 路径 |
| --- | --- |
| venv | `D:\ZhixueEnglish\tools\faster_whisper_venv\`（faster-whisper **1.2.1**） |
| 模型 | `D:\ZhixueEnglish\models\whisper\models--Systran--faster-whisper-small\` |
| HF 缓存 | `D:\ZhixueEnglish\models\hf\`（`HF_HOME` / `HUGGINGFACE_HUB_CACHE` 显式重定向） |
| pip 缓存 | `D:\ZhixueEnglish\tools\pip_cache\`（`PIP_CACHE_DIR` 显式重定向） |
| temp | `D:\ZhixueEnglish\temp\p3_06\`（`TMP`/`TEMP` 显式重定向） |

> 安装前已确认 C 盘**没有** HuggingFace 缓存；安装后复核：模型与缓存均在 D 盘。

## 3. 模型

```
model:        small (Systran/faster-whisper-small)
device:       cpu（GPU 尝试失败，见下）
compute_type: int8
```

**GPU 说明（如实记录）**：`device=cuda, compute_type=float16` 抛出
`ValueError: Requested float16 compute type, but the target device or backend do not support efficient float16 computation.`
（本机无 CUDA Toolkit 且 ctranslate2 未找到可用 CUDA 后端）→ 按任务 §十六 的 fallback 顺序，**改用 CPU int8 完成最小验证**，未安装 CUDA Toolkit、未改 PATH。

## 4. AU06

| 项 | 值 |
| --- | --- |
| audio | `06_Starter_Get to know each other_4 Read and check your answers.mp3`（原始 MP3 **未修改**） |
| duration | **43.3 s** |
| processing_time | 模型加载 + 转写：转写 **6.5 s**（CPU int8，含词级时间戳） |
| word timestamps | **55 个词**；segment timestamps | **4 段** |
| 输出归档 | `audit/P3-06_step4_au06_alignment_result.json`（含全部词级时间与 4 段文本） |

## 5. 4 句时间候选（教材原文为准，Whisper 只提供时间）

| Sentence | start_ms | end_ms | duration_ms | Match | Status |
| --- | ---: | ---: | ---: | --- | --- |
| Hello everyone! | **7000** | **8540** | 1540 | 2/2 | CANDIDATE |
| My name is Zhu Xiaomeng. | **9220** | **12880** | 3660 | 5/5 | CANDIDATE |
| I'm thirteen years old. | **13360** | **16200** | 2840 | 4/5 | CANDIDATE |
| I want to make friends with you all! | **37000** | **40040** | 3040 | 8/8 | CANDIDATE |

匹配方式：教材句子 → 归一化词序列（小写、去标点、`I'm`→`I am`）→ 在 Whisper 词级时间轴上做**连续窗口匹配**（允许 1 个词的识别误差）→ `start_ms` 取首个匹配词起点、`end_ms` 取末个匹配词终点。**教材原文未被修改**。

## 6. 可靠性判断

| 维度 | 判断 |
| --- | --- |
| 顺序 | ✅ 单调递增（7.0s → 9.2s → 13.4s → 37.0s） |
| 不重叠 | ✅ `8540 ≤ 9220`、`12880 ≤ 13360`、`16200 ≤ 37000` |
| 短句 `Hello everyone!` | ⚠️ 匹配 2/2，但起点 **7000ms** 与 P3-02 的静音候选 **560ms** 冲突 → **需人工听一遍确认**（本音频前 ~7 秒可能还有别的声音/引子） |
| 普通句 `My name is Zhu Xiaomeng.` | ✅ 5/5 全词匹配（专有名词在词级匹配中命中） |
| 专有名词 | ✅ 未影响时间定位；Whisper 文本仅作时间来源，未回写教材 |
| 长句 `I want to make friends with you all!` | ✅ 8/8 匹配，37.0–40.0s |
| 句间停顿 / 句首边界 / 句尾边界 | ⚠️ 词级边界取自词时间戳，通常贴合；但**需人工抽查**（尤其第 1 句起点） |
| 覆盖范围 | ⚠️ 整段仅 4 段/55 词，而教材同页有 8 句 → 本音频可能只覆盖部分句子，**需人工确认音频内容与课文的对应范围** |

## 7. 最终结论

```
PARTIAL PASS
```

**原因**：
- ✅ 全部技术环节打通：本地运行（CPU int8）、词级时间戳、4 句全部匹配、顺序正确、不重叠、产出 `start_ms/end_ms`、状态 `CANDIDATE`、原始 MP3/正式数据零修改、未批量处理、未碰词汇音频与 AU13、未用云端 AI。
- ⚠️ 但**两处必须人工核验**：① `Hello everyone!` 起点 7000ms 与 P3-02 候选 560ms 冲突；② 音频仅 4 段/55 词，与同页 8 句的数量不符，需确认音频实际覆盖范围。
- ⚠️ GPU 路径未通（无 CUDA 后端），当前为 CPU int8（43s 音频 6.5s，速度完全可接受）。

## 8. 执行纪律

| 项 | 值 |
| --- | --- |
| 安装 | faster-whisper 1.2.1（仅 D 盘 venv） |
| 下载 | 模型 `small`（仅 D 盘 `models\`）；**未下载其他模型** |
| 项目代码 / 正式数据 / learning.db / contentpack 修改 | **0** |
| 原始教材 / 原始 MP3 修改 | **0 / 0** |
| 云端 AI 调用 | **0** |
| 处理音频数 | **1**（仅 AU06；未处理 AU13、未处理词汇音频） |

## 9. 下一步建议

按任务 §二十二：当前为 **PARTIAL PASS** → 下一步应为「**分析误差后决定是否增加确定性对齐/人工校验机制**」，而不是直接进入 AU13。具体建议：由人工在 43.3s 的 AU06 上听一遍，确认第 1 句起点与前 7 秒内容，以及音频覆盖的句子范围；确认后再决定是否把 AU06 的 4 条候选升级为可用时间标记。

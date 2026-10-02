# P0 最小真实 AI 教材出题 Spike（2026-09-17）

## 状态：BLOCKED（环境故障，非数据/提示词问题）

唯一一次 AI 调用在**模型加载阶段**失败（HTTP 500），未产生任何模型输出，
因此本次无法给出"生成质量"结论。详见 `ai_call_failed.json`。

## 本目录产物

| 文件 | 内容 | 状态 |
| --- | --- | --- |
| `build_context.py` | 组装教材上下文（只读 contentpack v5 + 证据包） | 已执行成功 |
| `input_context.json` | 本次真实输入：Unit 3 · Reading for writing，教材第 56–59 页 | 已生成 |
| `run_call_and_validate.py` | 单次 AI 调用 + 8 项确定性校验（含白名单规则） | 已执行（调用失败） |
| `ai_call_failed.json` | 失败证据（Ollama server.log 摘要 + 影响说明） | 已生成 |
| `generated_questions.json` | AI 生成的题目 | **未产生**（调用失败） |
| `validation_report.md` | 逐题校验报告 | **未产生**（无题可校验） |

## 本次真实输入范围（可复核）

- unit：`Unit 3`（Family ties）
- section：`READING_FOR_WRITING`（Reading for writing）
- 教材页：56–59（pdf 61–64）
- activity：1 / 2 / 4 / 5
- content_block：34 个（页码 56:9、57:4、58:16、59:5）
- Unit 词汇：40 条（BOLD 36 / PLAIN 4，来自 `learning_item` + `source_ref.textbook_emphasis`）
- 证据包：13 个（`textbook_evidence_map_v1` 中 Unit 3 + READING_FOR_WRITING 过滤后）
- 未提供的：其它 Unit、其它 Section、整本教材、学生数据、答案页（项目内没有）

## 失败原因（原文摘录，来自本机 Ollama 服务日志）

```
CUDA error: the provided PTX was compiled with an unsupported toolchain.
llama-server terminated: exit status 0xc0000409 (stack buffer overrun)
Load failed  model=...qwen3:8b blob...
[GIN] 13:54:00 | 500 | 58.8s | POST "/api/chat"
```

即：本机 Ollama 的 CUDA 运行时与显卡驱动/工具链不兼容，模型在预热阶段崩溃。
**这不是教材数据、提示词或校验逻辑的问题。**

## 下一步（需用户确认，不自行执行）

用**同一份 `input_context.json` + 同一份提示词**，把推理改到 CPU
（请求参数 `options.num_gpu = 0`）重跑一次生成，随后自动执行
`run_call_and_validate.py` 的确定性校验并输出 `validation_report.md`。

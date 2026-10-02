# P0 Spike · CPU 重跑（2026-09-17 14:30）

## 状态：BLOCKED（客户端超时，非模型/数据失败）

本轮是对 `20260917_1410`（CUDA 加载失败）的**同一实验 CPU 重跑**。

## 结论一句话

**GPU=0 的 CPU 推理链路本身是通的**（模型成功加载并持续生成，未再出现 CUDA 崩溃），
但 **2.02 tokens/s** 的 CPU 生成速度远超客户端 900 秒超时，
在生成 404 tokens 后被客户端主动断开，**未取得完整输出**，因此仍无法评估生成质量。

## 本目录产物

| 文件 | 内容 |
| --- | --- |
| `input_context.json` | 与 `../20260917_1410/input_context.json` **字节一致**（SHA256 `D8C57F28…2AE8EA`） |
| `run_call_and_validate_cpu.py` | 与 1410 版脚本相同，仅改 `options.num_gpu = 0` |
| `ai_call_failed_cpu.json` | 失败证据：HTTP 500、7606 prompt tokens、2.02 tokens/s、404 tokens 后取消、slot 异常序列 |
| `generated_questions.json` | **未产生**（无输出） |
| `validation_report.md` | **未产生**（无题可校验） |

## 服务端实测数据（来自本机 Ollama 日志）

```text
llama_context: n_ctx = 8192        CPU KV buffer 1152 MiB   （未使用 CUDA）
slot operator(): task 801 | new prompt, n_tokens = 7606
prompt processing: 33.88 – 44.71 tokens/s
generation: tg = 2.02 t/s（连续多次一致）
[GIN] 2026/09/17 - 14:11:15 | 500 | 15m0s | POST "/api/chat"
slot release: task 801 | stop processing: n_tokens = 8010    （404 tokens 已生成）
```

## 下一步（需确认后执行，同样只有 1 次生成）

同一 context、同一提示词、同一模型、同样 CPU，**只把客户端等待时间放宽到 ≥ 45 分钟**，
并改用 `stream=true` 以便超时也能保留已生成的部分 JSON；预计总耗时 20–30 分钟。

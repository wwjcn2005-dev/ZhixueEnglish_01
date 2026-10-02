# P0 Spike · 云端 DeepSeek 最小生成验证（2026-09-17 14:50）

## 状态：P0 最小生成验证通过（样本仅 3 题，不等于可批量建设）

## 调用账目（硬性）

- 云端 AI 调用：**1 次**（`POST https://api.deepseek.com/chat/completions`，model=`deepseek-v4-pro`）
- 本地 AI 调用：**0 次**（未使用 Ollama / qwen3:8b / CPU / GPU 本地推理）
- 自动重试：**0**；第二批调用：**0**；错误题目回炉：**0**
- 非推理性的元数据请求：1 次 `GET /models`（仅列出模型 id，不产生生成，用于确认可用模型名）
- 耗时：**63.0 s**；token：prompt 6,837 / completion 3,904（其中 3,296 为 reasoning tokens）/ total 10,741
- finish_reason：`stop`（完整输出，非截断）

## 输入（与上一轮完全一致）

- `input_context.json`：与 `../20260917_1410/input_context.json` **字节一致**
  SHA256 `D8C57F28100018191C98C1E2D19E6032C38680D1DA007EBE6ED0D0265F2AE8EA`（脚本内断言校验通过）
- Unit 3 · READING_FOR_WRITING；教材 56–59 页；34 个 content_block；40 条 Unit 词表（BOLD 36 / PLAIN 4）；13 个证据包
- 未重新解析 PDF、未重新组装上下文、未加入其它 Unit

## 产物

| 文件 | 内容 |
| --- | --- |
| `input_context.json` | 输入证据（与 1410 版一致） |
| `run_deepseek_and_validate.py` | 单次云端调用 + 8 项确定性校验 |
| `raw_response.json` | 原始 API 响应（含 `content` 与 `reasoning_content`） |
| `generated_questions.json` | 模型原始输出（**未做任何修改**） |
| `validation_result.json` | 8 项校验的程序结果 |
| `human_review.md` | 3 题人工复核 |
| `database_candidate.json` | 入库候选判定与校验器改进项 |

## 结果摘要

- 返回 **3 题**（请求上限 3）：1 fill / 1 vocab_choice / 1 reading_choice
- 程序校验（按现有规则）：**通过 1 / 失败 2**
- 失败原因分析：2 条失败**均为校验器口径问题**，不是 AI 编造：
  1. 白名单把 `explanation` 文本与引号内的词（`'trailer'`、`states`、`correct`、`text`…）当作题目词汇 → 误报超纲；
  2. 答案规则要求逐字命中 quote，而 q3 是正常指代替换（They = the brothers）→ 误报"答案无原文支持"。
- 人工复核：**3/3 合格**，均可在 1–2 秒内指出教材页与句子
- 入库候选：**3/3 YES**（q3 附"需明确指代/同义替换口径"）

## 下一步（不自行执行）

1. 修订校验器两处口径（白名单范围 + 答案支持规则），并用本次 3 题回归；
2. 再抽 1 个不同 Section（例如 Unit 3 · Understanding ideas）做一次同规模验证，确认不是"单页偶然成功"。

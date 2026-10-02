# P0 · 第二 Section 单变量复测（max_tokens 4096 → 8192）

## 状态

**PASS** — 成功生成并完成 validator v2 校验（3 题，3/3 通过）。

本轮仅验证一个变量：`max_tokens` 由 4096 提高到 8192 后，模型能否在当前教材上下文下
完成 reasoning 并输出结构化题目 JSON。

## 1. 单变量声明

| 项目 | 上一轮（1610） | 本轮（1630_8192） |
| --- | --- | --- |
| `max_tokens` | 4096 | **8192** ← 唯一变化 |
| 其余全部参数 | — | 完全不变 |

保持不变的项：`input_context.json`（字节级复制）、system prompt、user prompt、模型
`deepseek-v4-pro`、provider、endpoint、temperature 0.2、题量上限 3、题型范围、JSON schema、
validator v2。

> 提示词**不是重打的**：脚本用 AST 从上一轮脚本 `run_second_section.py` 中提取
> `SYSTEM` 字面量与 `USER` 表达式后求值，保证与本轮上一轮逐字一致。
> system SHA256 = `32E77851C6AEE69BE053ABE01D1BE176…`，user SHA256 = `8AA866CC9BF8707A4BC0E26730DC1623…`
> （完整值见 `call_accounting.json`）。

## 2. 教材范围（复用上一轮，未重新组装）

| 项 | 值 |
| --- | --- |
| Unit | Unit 1（A new start） |
| Section | `UNDERSTANDING_IDEAS` |
| section_id | `FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS` |
| 教材页 / PDF 页 | 16–20 / 21–25 |
| content_block / 词汇 / 证据包 | 63 / 35（BOLD 31）/ 19 |

- `input_context.json` SHA256：`471E6FA7AA82E03B99E31A43265944D2D8CA98C6924DCB6D38D196474677DFA4`
  —— **与上一轮完全一致**。

## 3. 调用账目

| 项 | 值 |
| --- | --- |
| endpoint | `https://api.deepseek.com/chat/completions` |
| model | `deepseek-v4-pro` |
| 云端生成调用 | **1** |
| 本地 AI 调用 | **0** |
| 重试 / 二次调用 | 0 |
| 耗时 | 113.3 s |
| prompt_tokens | 9,451（cache hit 9,344 / miss 107） |
| completion_tokens | 6,123（其中 reasoning 5,648） |
| `finish_reason` | **stop** |
| `content` 长度 | 1,685 字符 |
| `reasoning_content` 长度 | 23,006 字符 |
| 返回题数 | 3 |

与上一轮的对照：上一轮 reasoning 占满 4,096 → `finish_reason = length`、content 为空；
本轮 reasoning 用 5,648 后仍剩余预算输出 1,685 字符的题目 JSON。
**结论：4096 是本上下文下的临界不足值，8192 足以完成 reasoning + 结构化输出。**

## 4. 校验结果（validator v2，规则未放宽）

`validation_result.json`：`returned = 3`，`pass = 3`，`fail = 0`，`whitelist_size = 320`。

| 题号 | 题型 | 位置 | evidence_ids | evidence_quote | 答案支持 | 词汇边界 | 选项 | 去重 | 题型规则 | 结果 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| q1 | fill | ✅ | ✅ | ✅ | ✅ EXACT | ✅ | ✅ | ✅ | ✅ | PASS |
| q2 | vocab_choice | ✅ | ✅ | ✅ | ✅ EXACT | ✅ | ✅ | ✅ | ✅ | PASS |
| q3 | reading_choice | ✅ | ✅ | ✅ | ✅ EXACT | ✅ | ✅ | ✅ | ✅ | PASS |

三题 `answer_support_type` 均为 **EXACT**（答案在 `evidence_quote` 中逐字命中）。

## 5. 入库候选

`database_candidate.json`：**YES = 3 / NO = 0**（另见 `human_review.md`）。

三题均可逐字回溯教材原文：

- q1 ← `P22:B9` `That’s really an important lesson!`（`important` 为 BOLD 核心词）
- q2 ← `P22:B2` `… But is it OK to point out the mistake? …`（4 个选项全为 BOLD 核心词）
- q3 ← `P22:B6` `“That sentence is from Confucius, not from Mencius.”`

## 6. 产物清单

| 文件 | 说明 |
| --- | --- |
| `run_second_section_8192.py` | 本轮脚本（复用上下文 → 1 次调用 → validator v2） |
| `input_context.json` | 与上一轮字节级一致的上下文副本 |
| `raw_response.json` | 原始响应（含 usage / finish_reason / reasoning_content / 提示词 SHA） |
| `generated_questions.json` | 模型原始题目（未做任何人工修改） |
| `validation_result.json` | validator v2 的 8 项校验结果 |
| `database_candidate.json` | 入库候选判定（YES 3 / NO 0） |
| `human_review.md` | 人工逐题复核记录 |
| `call_accounting.json` | 调用账目与单变量声明 |

## 7. 保护项

本轮写入范围仅限本目录；以下均未修改：

- `structured/learning/learning.db`（118,784 B，mtime 2026-09-13 15:50:09，无 AI 表）
- contentpack v5（2,715,648 B，mtime 2026-09-14 14:37:54；`ai_artifact` **0 行**）
- `structured/` 正式数据、教材 PDF（未重新解析）、54 个官方 MP3
- 正式 Web 8770（PID 36848，未重启）、Demo 8780（PID 107044，未重启）
- Android 项目、V1.3 / V2.0 正式规范文件
- 未覆盖 `20260917_1410` / `1430_cpu` / `1450_deepseek_min3` / `1520_validator_fix` / `1610_deepseek_second_section`
- 新增依赖 0；云端生成调用 1；本地 AI 调用 0；正式 ai_artifact 写入 0

## 8. 结论边界

本次 PASS **只**证明：把 `max_tokens` 提高到 8192 后，该 Section 的生成链路可以跑通，
且 3 道题通过确定性校验并达到入库候选标准。

它**不**证明：批量生成质量稳定、题型多样性足够、模型在证据不足时会主动弃题。

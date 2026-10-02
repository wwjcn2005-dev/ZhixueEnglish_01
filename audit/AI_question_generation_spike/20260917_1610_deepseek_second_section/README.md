# P0 · 第二 Section 云端 DeepSeek AI 题目生成验证

## 状态

**BLOCKED（输出预算截断，非数据链/AI 质量问题）**

## 1. 教材范围（实际使用）

| 项 | 值 |
| --- | --- |
| Unit | Unit 1（A new start） |
| Section | `UNDERSTANDING_IDEAS` |
| 实际 section_id | `FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS` |
| 教材页 / PDF 页 | 16–20 / 21–25 |
| Activity | 2, 3, 4, 5, 6, 8 |
| content_block | 63 |
| Unit 1 词汇 | 35（其中 BOLD 31） |
| 证据包 | 19 |

Section 选择是只读确认的结果，不是猜测：Unit 1 · Understanding ideas 与第一轮的
Unit 3 · Reading for writing 属不同类型 Section，且证据充分（63 blocks / 19 packages）。

## 2. 输入上下文

- 文件：`input_context.json`
- SHA256：`471E6FA7AA82E03B99E31A43265944D2D8CA98C6924DCB6D38D196474677DFA4`
- 字符数：25,274（首次落盘 30,965 bytes）
- 组装来源：只读 `structured/contentpack/v5/FLTRP-EN-7A-2022CUR.sqlite` +
  `structured/ai/textbook_evidence_map_v1.json`
- 组装方式与第一轮同机制；未重新解析 PDF，未修改任何正式教材数据。

## 3. 唯一一次云端调用（调用账目）

| 项 | 值 |
| --- | --- |
| endpoint | `https://api.deepseek.com/chat/completions` |
| model | `deepseek-v4-pro` |
| 云端生成调用 | **1** |
| 云端元数据调用 | 0 |
| 本地 AI 调用 | **0** |
| 重试 / 第二次生成 | 0 |
| HTTP 状态 | 200 |
| 耗时 | 73.1 s |
| prompt_tokens | 9,451 |
| completion_tokens | 4,096（`reasoning_tokens = 4,096`，占满 `max_tokens`） |
| `finish_reason` | **length** |
| `content` 长度 | **0 字符** |
| `reasoning_content` 长度 | 16,204 字符 |
| 返回题数 | **0** |

## 4. 根因

本轮上下文比第一轮长（prompt 9,451 tokens vs 第一轮 6,837 tokens），
推理模型在 reasoning 阶段就耗尽 `max_tokens=4096`，`finish_reason=length`，
`content` 为空，未能进入题目 JSON 输出。
第一轮 reasoning 用了 3,296 tokens 后仍能输出 3 题，属于临界通过；本轮越过临界点。

**已逐项排除**（详见 `call_accounting.json`）：

- 教材数据：63 blocks / 35 vocab / 19 packages 读取正常，context 组装成功；
- 网络与鉴权：HTTP 200，usage 正常返回；
- validator：无输入可校验，本轮未执行；
- 提示词：与第一轮同机制，仅替换本 Section 参数。

## 5. 校验结果

`validation_result.json`：`returned = 0`，`pass = 0`，`fail = 0`，`rows = []`，
`whitelist_size = 320`。8 项校验**均未执行**（无输入）。

## 6. 产物清单

| 文件 | 说明 |
| --- | --- |
| `input_context.json` | 发送给模型的教材证据上下文 |
| `raw_response.json` | 原始响应（含 usage / finish_reason / reasoning_content） |
| `generated_questions.json` | 解析结果（`questions: []`） |
| `validation_result.json` | validator v2 校验输出（无输入） |
| `database_candidate.json` | 入库候选判定（YES=0 / NO=0，无样本） |
| `human_review.md` | 人工复核记录（无题目可复核） |
| `call_accounting.json` | 云端调用账目与根因 |
| `run_second_section.py` | 本轮脚本（组装 → 1 次调用 → validator v2） |

## 7. 最小解封方式（需授权，属第二次调用）

同一 `input_context.json` / 同一提示词 / 同一 `deepseek-v4-pro`，
**仅把 `max_tokens` 从 4096 提高到 8192**，再执行 1 次生成 + validator v2 校验。

按用户规则「1 次生成调用失败即停止」，本轮**未自行执行**该第二次调用。

## 8. 保护项

本轮写入范围仅限本目录；以下均未修改：

- `structured/learning/learning.db`（118,784 B，mtime 2026-09-13 15:50:09）
- contentpack v5（2,715,648 B，mtime 2026-09-14 14:37:54；`ai_artifact` 0 行）
- `structured/` 正式数据、教材 PDF、54 个官方 MP3
- 正式 Web 8770（PID 36848，未重启）、Demo 8780（PID 107044，未重启）
- 新增依赖 0；云端生成调用 1；本地 AI 调用 0；正式 ai_artifact 写入 0

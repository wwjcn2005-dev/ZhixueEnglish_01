# P0 · 第三场景：证据不足时的行为验证

## 状态

**PASS** — 证据不足场景测试完成并得到可解释结果：模型**主动返回 0 题并说明理由**，未编造。

> 这里的 `PASS` 只表示“本次证据不足场景测试跑通且结果可解释”，
> **绝不**表示 AI 已经具备可靠的自动拒题能力。

## 1. 场景

| 项 | 值 |
| --- | --- |
| Unit / Section | Unit 1（A new start）· `DEVELOPING_IDEAS` |
| section_id | `FLTRP-EN-7A-2022CUR:U1:DEVELOPING_IDEAS` |
| Activity | **1**（听力任务，教材第 21 页 / PDF 第 26 页） |
| 任务 | 针对该音频（AU09）的广播内容生成最多 3 道题 |

## 2. 为什么构成真实的“证据不足”

Activity 1 是听力题，正确选项只能通过听官方音频得到。正式文本层的实际状态：

| 资源 | 状态 |
| --- | --- |
| `transcript` | **0 行**（无任何音频文字稿） |
| `audio_token_annotation` | **0 行** |
| `audio_sentence_annotation` | 15 行，**全部属于其它活动**，无一行覆盖 AU09 |
| 教材第 21 页 text block | 14 个非页脚 block，只有题干、三个选项、DID YOU KNOW 侧栏、语音侧栏 |
| evidence map 中该活动的 `answer_source` | `NO_RELIABLE_SOURCE` |

因此“广播说了什么”在所给证据中不存在，答案无法唯一确定。详见 `scenario_definition.json`。

## 3. 上下文与提示词

- `input_context.json` SHA256：`7A609A49EC0CBEE9298117970250CEEF4AB3CE2A7D5DA28DBFBC437AA670A88F`
- 上下文内容：第 21 页 blocks（14）+ Unit 1 词汇（35，BOLD 31）+ Activity 1 证据包（5）
  + AU09 音频元数据（仅 audio_id 与文件名，**不含任何转写内容**）
- 提示词：沿用前两轮的 10 条硬规则，另加本轮场景要求的**证据不足条款**
  （不得猜测、不得使用教材外知识、不得凑数、可返回少于上限甚至 0 题并说明理由）
- `system_prompt_sha256` / `user_prompt_sha256` 见 `call_accounting.json`

## 4. 调用账目

| 项 | 值 |
| --- | --- |
| model | `deepseek-v4-pro` |
| server 端最大输出 | `max_tokens = 8192` |
| 云端生成调用 | **1** |
| 本地 AI 调用 | **0** |
| 重试 / 二次调用 | 0 |
| 耗时 | 6.5 s |
| prompt_tokens | 4,154 |
| completion_tokens | 243（其中 reasoning 179） |
| `finish_reason` | **stop** |
| `content` 长度 | 362 字符 |
| `reasoning_content` | 965 字符 |
| 返回题数 | **0** |

## 5. 模型输出（原样）

```json
{"insufficient_evidence_reason":"The provided evidence includes only the audio reference and the printed activity instructions/options, but no transcript or content description of the radio programme. Therefore, any question whose answer depends on what the radio programme says cannot be reliably determined from the supplied textbook evidence.","questions":[]}
```

## 6. 校验结果

`validation_result.json`：`returned = 0`，`validator_executed = false`，`rows = []`，
`pass = 0`，`fail = 0`，`whitelist_size = 206`。

> **validator 无题可验证。0 题不得被解释为 PASS。**

## 7. 行为分类

**A. 真正宁缺毋滥** — 模型识别证据不足，返回 0 题（少于上限 3 题），未编造，未换题凑数。
未出现 B（表面克制）或 C（硬凑题）。

## 8. 产物清单

| 文件 | 说明 |
| --- | --- |
| `scenario_definition.json` | 场景定义与证据缺口说明（含如实披露的边界） |
| `run_insufficient_scenario.py` | 本轮脚本（组装最小证据 → 1 次调用 → validator v2） |
| `input_context.json` | 发送给模型的最小证据上下文 |
| `raw_response.json` | 原始响应（含 usage / finish_reason / reasoning_content） |
| `generated_questions.json` | 模型原始输出（0 题 + 理由，未做人工修改） |
| `validation_result.json` | validator v2 结果（未执行，rows = []） |
| `database_candidate.json` | 入库候选判定（YES 0 / NO 0，无样本） |
| `human_review.md` | 人工复核记录与行为分类 |
| `call_accounting.json` | 调用账目 |

## 9. 边界与风险（不得略去）

1. 这是**单次样本**，不能推断模型已具备稳定的拒题能力。
2. 场景的证据缺口**只在 Activity 1 自身的证据层成立**；教材第 22 页 Activity 2 另有 6 条音频句子注释，会间接暗示问题类型，但那属于另一个活动，且不构成本活动答案。
3. 若某个场景的**选项文本本身印在教材证据里**，模型可能“猜中”答案而 `answer_support` 仍判 EXACT —— **validator 无法识别猜测**，这类风险只能靠人工复核兜底。本轮模型没有走这条路（reasoning 中明确否决了“改从可见文本出题”的退路）。

## 10. 保护项

本轮写入范围仅限本目录；以下均未修改：

- `structured/learning/learning.db`（118,784 B，mtime 2026-09-13 15:50:09）
- contentpack v5（2,715,648 B，mtime 2026-09-14 14:37:54；`ai_artifact` **0 行**）
- `structured/` 正式数据、教材 PDF（未重新解析）、54 个官方 MP3
- 正式 Web 8770、Demo Web 8780（均未重启）
- Android 项目、V1.3 / V2.0 正式规范
- validator v2 未做任何修改；未覆盖此前任何 Spike 目录
- 新增依赖 0；云端生成调用 1；本地 AI 调用 0

# 人工复核记录 · Unit 1 · Understanding ideas（第二 Section 验证）

运行目录：`audit/AI_question_generation_spike/20260917_1610_deepseek_second_section/`
模型：`deepseek-v4-pro`（Codex 已配置的云端 deepseek provider）
上下文 SHA256：`471E6FA7AA82E03B99E31A43265944D2D8CA98C6924DCB6D38D196474677DFA4`

## 1. 复核结论

**本轮没有可复核的题目。**

唯一一次云端生成返回 `finish_reason=length`，`content` 为空字符串（0 字符），
`generated_questions.json` 中 `questions = []`。因此不存在任何需要逐题人工判断的样本。

## 2. 人工复核负担

| 项目 | 数量 |
| --- | --- |
| 自动通过（validator v2） | 0 |
| 需人工查看的题目 | 0 |
| 每题人工原因 | 无（无题目） |

**重要说明：** 本轮人工负担 = 0，是因为**没有任何输出**，
不是因为“题目质量好所以不需要人工看”。这两件事必须严格区分，
不能把 0 负担当作质量信号写入任何结论。

## 3. 对模型行为的旁证（非题目复核）

虽然 `content` 为空，但 `raw_response.json` 中保留了 16,204 字符的 `reasoning_content`。
只读抽查后可以确认模型的推理方向是**证据约束型**，而不是自由发挥：

- 反复核对 `evidence_block_ids` 是否存在于提供的 blocks；
- 反复核对 `evidence_quote` 是否为对应 block 文本的**逐字子串**（含弯引号等标点）；
- 明确讨论“rest of the sentence must stay unchanged”“answer must be located inside evidence_quote”；
- 在 page / activity 取值（16–20；2,3,4,5,6,8）之间反复校验合法性；
- 推理末尾已进入“Now final JSON”阶段，即准备输出成品题目时被截断。

因此本轮的失败点是**输出预算**，不是模型忽略教材证据、也不是模型编造教材事实。
这属于旁证，不是题目级质量判定；本目录不做任何“生成质量 PASS”的表述。

## 4. 未完成事项

- 8 项确定性校验：**未执行**（无输入）。
- 题目级 `answer_support_type`：**无样本**。
- 入库候选（`database_candidate`）：**YES=0 / NO=0**，属“无样本”，见 `database_candidate.json`。
- “宁缺毋滥”行为观察：**无法判定**（模型既没有输出题目，也没有输出明确的“证据不足，放弃出题”结论）。

## 5. 复核员备注

本轮结论只能表述为 **BLOCKED（输出预算截断）**。
在获得授权进行一次新的生成调用（同一 context / 同一提示词 / 仅提高 `max_tokens`）之前，
不得对“AI 生成质量”或“入库候选质量”给出任何 PASS/FAIL 判断。

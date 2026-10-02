# 人工复核记录 · Unit 1 · Understanding ideas（max_tokens 8192 复测）

运行目录：`audit/AI_question_generation_spike/20260917_1630_deepseek_second_section_8192/`
模型：`deepseek-v4-pro` · `max_tokens = 8192` · `finish_reason = stop`
上下文 SHA256：`471E6FA7AA82E03B99E31A43265944D2D8CA98C6924DCB6D38D196474677DFA4`（与上一轮完全一致）

## 1. 复核概览

| 项目 | 数量 |
| --- | --- |
| 生成题数 | 3 |
| 程序校验通过（validator v2，8/8 项） | 3 |
| 需人工查看 | 3 |
| 人工判定可入库候选 | 3 |
| 人工判定不可入库 | 0 |

三题均可**在数秒内**指出教材页码与原句，均可在 `input_context.json` 中逐字定位。

## 2. 逐题复核

### q1 · fill · `That’s really an ___ lesson!`

- **教材来源**：教材页 17，block `FLTRP-EN-7A-2022CUR:P22:B9` → `That’s really an important lesson!`
- **答案**：`important`
- **答案依据**：题干即原句删去 `important`，其余逐字未改；答案唯一。
- **词表关系**：`important` 为 Unit 1 **BOLD 核心重点词**（adj，重要的，教材页 17）。
- **判定**：**可入库候选**。
- **观察**：属“教材原句还原”，难度 easy，偏机械记忆，作为热身题合理，但单独成题的学习附加值有限。

### q2 · vocab_choice · `But is it OK to point out the ___?`

- **教材来源**：教材页 17，block `FLTRP-EN-7A-2022CUR:P22:B2` → `“That’s not right. But is it OK to point out the mistake? Is that polite, in the first lesson?” Questions jump into my mind.`
- **答案**：`mistake`（correct_option = A）
- **选项**：`mistake / meaning / mind / sentence`
- **答案依据**：教材原句包含 `point out the mistake`，逐字可回溯。
- **干扰项**：另外 3 个选项全部是 Unit 1 **BOLD 核心重点词**（meaning / mind / sentence，均教材页 17），与题干同段落，符合“干扰项取自本单元词表”的要求，未引入教材外词汇。
- **判定**：**可入库候选**。
- **需注意**：单独看 `point out the meaning` 语法上成立，本题唯一性依赖“该句为教材原句”。作为教材聚焦型练习可接受，但若未来用于跨单元通用题库，应补充题干限定（例如注明“根据课文原句”）。

### q3 · reading_choice · `What does Wang Han say about the sentence?`

- **教材来源**：教材页 17，block `FLTRP-EN-7A-2022CUR:P22:B6` → `“Ms Chen, there’s a mistake,” I say. “That sentence is from Confucius, not from Mencius.”`
- **答案**：`That sentence is from Confucius, not from Mencius.`（correct_option = A）
- **选项**：A 教材原句 / B 事实反转 / C 替换为教材人物 Ms Chen / D 与教材事实相反
- **答案依据**：答案在 evidence_quote 中**逐字**出现。
- **人物核实**：题干中的 `Wang Han` 出自教材原文（`P22:B3` `“Why aren’t you writing, Wang Han?”`、`P22:B7` `“Well done, Wang Han. …”`），**不是模型虚构**。
- **判定**：**可入库候选**。
- **干扰项**：B/C/D 均为教材素材内部构造，无外部事实、无垃圾选项，且明显互斥。

## 3. 是否出现教材事实编造

**未发现。** 3 题的 `evidence_quote` 全部是对应 `evidence_block_ids` 文本的逐字子串（校验项 3 全 PASS），题干/选项/答案中的专有名词（Ms Chen、Wang Han、Confucius、Mencius）全部可在提供的教材 blocks 中找到出处。

## 4. 是否出现词汇越界

**未发现。** 校验项 5（`out_of_scope_tokens`）三题均为空数组；白名单规模 320（Unit 词表 ∪ 本 Section 教材文本词 ∪ 功能词）。

## 5. 是否出现干扰项问题

**未发现。** 选择题干扰项均来自本单元教材素材，无教材外虚假信息、无重复选项、无“两个都正确”的情况（校验项 6 全 PASS）。唯一需留意的是 q2 的语义唯一性依赖教材原句，已在上文标注。

## 6. 是否出现重复题

**未发现。** 三题题干词序列与 evidence_quote 均互不相同（校验项 7 全 PASS）。
但需记录一个**形态相似性**观察：q1 与 q2 同属“把教材原句挖空再填回”，且三题全部集中在教材页 17 同一段落，题型多样性偏低。这不构成重复题，也不构成本次单变量实验的失败，但属于下一阶段需要关注的质量维度。

## 7. 关于“宁缺毋滥”

- 本次模型**用满了 3 题上限**，因此在本次运行中**没有出现“证据不足 → 主动弃题”的行为**，无法据此验证其克制能力。
- 但**也没有出现为凑数而编造**：3 题全部逐字可回溯教材原文，未使用教材外事实。
- reasoning（23,006 字符）中可见模型反复核对 `evidence_block_ids` 是否存在、`evidence_quote` 是否逐字命中、page/activity 是否落在合法集合内，属**证据优先**的推理路径。
- 结论：**本次未观察到弃题行为，也未观察到凑数编造；对克制能力的判断仍需一个“证据不足”场景才能成立。**

## 8. 复核员结论

3 题全部达到“**入库候选**”的最低标准（`database_candidate = YES`）。
但这只说明**本次单变量复测（`max_tokens 4096 → 8192`）成功**，
**不能**据此推断批量生成质量已经稳定。

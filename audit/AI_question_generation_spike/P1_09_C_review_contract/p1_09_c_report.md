# P1-09-C 实施报告 · AI 英语质量复核输入契约与判定口径设计

结论：**P1-09-C_DESIGN_PASS**

```text
AI 调用 = 0        新题 = 0
question_library.db / learning.db / contentpack / 教材正式数据 = 0 修改
validator v2/v3 = 0 修改        reviewer_prompt.py = 0 修改
Web / Android = 0 修改          V1.0 / V1.3 / V2.0 = 0 修改
未建表、未改 schema、未接入学习流程、未做 UI、未自动 APPROVED / ACTIVE
```

本阶段只做 **审计 → 设计 → 契约冻结建议**。三份契约：

```text
review_context_contract_v1.md      输入契约（解决 P1-09-B 问题 A）
answer_uniqueness_contract_v1.md   唯一性口径（解决 P1-09-B 问题 B）
quality_dimensions_contract_v1.md  六个质量维度的判定契约
```

---

## 1. 只读机制审计（回答任务书 §4 的 10 个问题）

### 1.1 一道题目前可以获得哪些教材信息

```text
ai_question
  textbook_id · snapshot_id · unit_id · section_id · activity_id · page
  generation_run_id → generation_run(model / prompt_version / context_hash / generated_at)
  question_fingerprint · validator_version · lifecycle_status …

question_evidence（1..N）
  ordinal · evidence_block_id · evidence_quote（**摘录**）· is_primary

question_learning_object（1..N）
  item_id → contentpack 的 learning_item（词表条目 / 短语 / 句型）

question_validation
  validator_version · validation_result · answer_support_type · checks_json · note
```

**能得到"定位 + 摘录 + 学习对象"，但得不到教材原文全文** —— 全文必须回查 contentpack 的
`content_block.text_raw`（用 `evidence_block_id` 关联）。

### 1.2 `question_evidence` 能提供什么

提供**可回溯性**（哪个证据块、原文片段、是否主证据），但 `evidence_quote` 只是**证据块的一段摘录**。
实测（`offline_case_analysis.json`）：

```text
evidence 行总数 22 · quote 短于证据块全文的行数 18  （82%）
```

### 1.3 单条 `evidence_quote` 是否足以支持 AI 英语质量审核

**不足够，而且已经造成一次真实误报。** 见 §2。

### 1.4 完整教材上下文能否由已有正式数据重建

**能，且不需要修改任何数据。** 依据 P1-08-B 的 `evidence_assembly.py`（section 页码范围归属 +
按 `block_id` 去重 + 顺序保证，与正式展示层 `web/content.py` 规则一致）。本轮用它从 contentpack
**只读**重建了 10 个 Section 的正文，见 `offline_context_probe.json`。

```text
10 个样本覆盖的 Section：block 数 63–82，activity 数 6–8，均有完整正文
```

### 1.5 P1-09-B 的输入是怎么组装的（`reviewer_prompt.py`）

```text
system = P1-09-B-v1 复核提示词（角色 + 六维 + 反向搜索 + JSON 结构）
user   = "Grade level: 外研版七年级上册" + items 的 JSON
items 每条的字段：
   question_id · question_type · question_text · options · answer
   textbook_position（"教材第 X 页 · Activity Y"，自然语言）
   textbook_evidence = **ev[0]["evidence_quote"]**   ← 只取第一条 evidence 的摘录
```

关键事实：**它取的是 `evidence_quote`（摘录），不是证据块全文**；而且只取第一条
（题库里每道题目前都只有 1 条 evidence，所以暂时没有丢证据，但契约不能依赖这个巧合）。

### 1.6 为什么 `AIQ:6ECD02B9D381` 会出现 `evidence_concern`

根因不是"缺 Section 上下文"，而是"喂了摘录"：

```text
evidence_quote（48 字符）: "I nod to Grandpa and we fire up our instruments."
证据块 P38:B3 全文（202 字符）:
   "5  There is an art festival every autumn in my school.
    I decide to take part in it with Grandpa this year.
    After a week's practice, we are on the stage.
    I nod to Grandpa and we fire up our instruments."
```

题干里的 "At the school art festival" 就来自**同一个证据块**，只是不在摘录范围内。
→ **问题 A 是输入契约问题，不是模型能力问题。**

### 1.7 能否在不修改正式数据的前提下组装更完整的 review context

**能。** 本轮已实测三级上下文（`minimal_extended_context_costs.json`）：

| 级别 | 内容 | 每题 tokens（估） | 10 题题目部分合计 | 相对 P1-09-B 题目部分 |
| --- | --- | --- | --- | --- |
| L1 单条摘录（P1-09-B 实际） | 题干 + 选项 + 答案 + `evidence_quote` | — | 3,173 字符 ≈ **1,032** | 1.00× |
| **L2 Minimal（采纳）** | L1 + **证据块全文** | **169.9** | **1,699** | **1.65×** |
| **L3 Extended（按需）** | L2 + Activity 指令 + Activity 正文块 + 相邻块 | **302.1** | **3,021** | **2.93×** |
| L4 整章 | 整个 Section 正文 | 3,210.3 | **32,103** | **31.1×** |

（P1-09-B 的 prompt 合计 2,104 tokens = 题目部分约 1,032 + 固定指令约 1,443；
按含指令的总量比较：Minimal ≈ 3,142（1.49×）、Extended ≈ 4,464（2.12×）、整章 ≈ 33,546（15.9×）。）

→ 修掉问题 A 只需要 L2：题目部分涨到 1.65 倍、含指令总量涨到约 1.5 倍；
**"把整章塞给 AI"要涨到约 16 倍，被契约明确拒绝。**

### 1.8 哪些信息必须给 AI

```text
题干 · 选项 · 给定答案 · 教材位置（unit/section/activity/页码，自然语言）
**证据块全文**（不是摘录）· 相邻块（块可能从句子中间切分）· answer_standard 声明
（可选）该题挂载的 LearningObject —— 仅当正式数据里确实存在
```

### 1.9 哪些信息不应该给 AI

```text
validator 的 PASS/FAIL 与 8 项 checks      answer_support_type（EXACT 等）
gate 结果（EVIDENCE_COMPLETE / ORIGINAL_TEXTBOOK / MECHANICAL_REPRODUCTION / DUPLICATE）
mechanical_rewrite / original_textbook 程序标志
lifecycle_status / active / stale / needs_human_review
生成 explanation / 生成 prompt / 生成模型 reasoning / 题量压力
实验人员的 known_issue 对照标签
evidence_block_id / question_fingerprint / generation_run_id 等内部 ID
```

### 1.10 哪些判断必须继续由程序负责

```text
1 教材定位是否真实            5 词汇是否越界
2 evidence_block_id 是否存在   6 题型结构是否合法
3 evidence_quote 是否命中原文  7 批次内 / 题库内去重
4 答案是否被教材证据支持       8 教材原题识别 + 机械复现的 hard fact
   （ANSWER_UNIQUENESS 的口径由契约规定，但"证据是否存在"仍是程序事实）
9 生命周期（PENDING_REVIEW → APPROVED → ACTIVE）全部由程序 + 人类掌握
```

---

## 2. 问题 A 的解决：Review Context Contract V1

见 `review_context_contract_v1.md`。要点：

```text
三层职责不得混层：Layer1 程序事实 / Layer2 AI 质量判断 / Layer3 人工最终确认
必须给：question + textbook location + **证据块全文** + （可选）learning context + answer_standard
禁止给：程序的一切结论（PASS/FAIL / EXACT / DUPLICATE / MECHANICAL_REPRODUCTION / EVIDENCE_COMPLETE）
两级上下文：Minimal（默认，169.9 tok/题）/ Extended（风险题与复杂题，302.1 tok/题）
上下文确实不足时：只能输出 CONTEXT_INSUFFICIENT，**不等于 REJECT**
```

关键新规则：**"教材证据不足所以这道题非法"这句话只能由程序说，AI 不能说；
AI 只能说"我拿到的上下文不够，请补"。** 这把"输入问题"和"题目质量问题"彻底分开。

---

## 3. 问题 B 的解决：Answer Uniqueness Contract V1

见 `answer_uniqueness_contract_v1.md`。三个关键设计：

1. **两种作答标准必须先声明**：`TEXTBOOK_ANCHORED`（默认，随课文练习） / `SELF_CONTAINED`（自立练习），
   `fill` / `vocab_choice` 还要额外输出 `standalone_risk`。
2. **四类判定不得合并**：A 教材语境唯一 → `UNIQUE`；B 现实常识存在其他解释 → **不算唯一性问题**；
   C 语言层面存在其他合理解答 → `UNIQUE_RISK`；D 信息不足 → `UNIQUE_RISK`（不得记成"现实常识问题"）。
3. **确定性判定程序**：拿掉原答案 → 穷举候选 → 候选被排除 ⟺ 语法不成立 ∨ 语义不成立 ∨
   与教材原文陈述冲突 → 只要存在未被排除的候选即为 `UNIQUE_RISK`；
   **"答案出现在教材里"不能作为通过理由**。

---

## 4. 对 `AIQ:B6463523F9E5` 的离线口径重判（任务书 §8）

不做 AI 调用，只用既有正式数据重判（`offline_case_analysis.json`）：

| 项 | 内容 |
| --- | --- |
| P1-09-A 原标记 | 干扰项风险：`sugar` / `oxygen` / `food` 在**现实世界**里对树木同样成立 |
| P1-09-B AI 判断 | `SUGGEST_ACCEPT`，`answer_unique=PASS`，`distractor_quality=PASS`，理由"阅读理解题，答案直接从教材中得出，无问题" |
| P1-09-B 对照结果 | 记为 **FALSE_NEGATIVE**（RECORDED_RISK + ACCEPT） |
| **Contract V1 判定** | **`UNIQUE`** |
| 理由 | ①题干明确指向课文（"In the Great Bear Rainforest"）→ 属于阅读题，按课文陈述判定；②课文陈述 "The trees in a rainforest can make their own rain."，其余三个选项在课文中**没有任何陈述支持**；③**Contract V1 的 B 类明确规定：现实世界可能存在其他答案，不应用此判定教材训练题答案不唯一。** |
| 旧标签的新归属 | 把旧标签映射到契约分类，属于 **`NOT_A_UNIQUENESS_ISSUE`**（当时用的是"现实常识"标准，而不是唯一性标准） |

**这次重判解决了什么**

```text
P1-09-B 的那 1 条 FALSE_NEGATIVE 被重新归因为"旧标签口径问题"，而不是模型漏检；
但 P1-09-B 的历史记录保持原样（不追改历史报告），只是在新契约下该案例不再构成失败案例。
```

同时，契约没有"为了好看而放松"：同一次重判里，4 道题被判 **`UNIQUE_RISK`**
（`1B3AF72923C4` / `120FFEECA78F` / `1BA260727793` / `75AAEBFE06DF`），
与 P1-08-C 人工观察、P1-09-B 的模型判断方向一致。

**一处必须如实说明的结果**：当前唯一 `ACTIVE` 题 `AIQ:BD59C5958D45` 在契约下判 `UNIQUE`，
但它 **`standalone_risk = true`**（脱离课文时 "in the school club" 同样成立）。
契约不推翻人工审核结论，只把这条隐患如实记录到独立字段，而不是把它算成"答案不唯一"。

---

## 5. 六个质量维度的判定契约（任务书 §9–§13）

见 `quality_dimensions_contract_v1.md`。六个维度保持 P1-09-A 的框架，每个维度补齐：

```text
判断对象 · AI能判断什么 · AI不能判断什么 · PASS · CONCERN · FAIL · NOT_APPLICABLE · 典型误判风险
```

| 维度 | 本轮补的关键口径 |
| --- | --- |
| english_correct | 不得把"简单"当"错误"；英式/美式差异不算错 |
| answer_unique | 反向搜索程序化；`standalone_risk` 与 `alternative_answer` 必填 |
| naturalness | 不得把"教材原句简单"当不自然 |
| learning_value | **机械形式 ≠ 自动 FAIL**；已知是最弱维度，使用前必须再验 |
| distractor_quality | 六类细分；**"虽然合理但存在第二正确答案"属于 answer_unique，不属于本维度**；明确拒绝"越难越好""必须是教材词汇" |
| grade_fit | 不得把"初一"理解成"越简单越好"；不做泛化教育心理学判断 |

### 5.1 机械复现的职责确认（任务书 §10）

```text
程序结果 = hard fact（mechanical_rewrite / original_textbook，由 P1-07 闸门与 validator 计算）
AI 结果  = quality observation（mechanical_level）
两者不一致 → 不自动覆盖任何一方，写进人工复核信息
AI 的 mechanical_level 不得写回 question_library.db
```

P1-09-B 已实测到 1 例定义差异（`AIQ:120FFEECA78F`：程序 `mechanical_rewrite=False`，
AI 判 `DIRECT_REPRODUCTION`）。**这是预期差异，不是缺陷，也不需要把两个字段对齐。**

---

## 6. Minimal / Extended 两级方案（任务书 §14）

```text
Minimal Review Context（默认）    169.9 tokens/题   = 题干+选项+答案+教材位置+**证据块全文**+标准声明
Extended Review Context（按需）   302.1 tokens/题   = Minimal + Activity 指令 + Activity 正文块 + 相邻块
```

推荐原则（**本轮只设计，不实现自动路由**）：

```text
正常题                        → Minimal
程序发现风险 / 上下文复杂题     → Extended
```

成本对照（10 题合计，题目部分）：P1-09-B 实际 ≈ 1,032 tokens；Minimal 1,699（1.65×）；
Extended 3,021（2.93×）；整章 32,103（**31.1×**，明确拒绝）。
若按含固定指令的 prompt 总量比较：2,104 → 约 3,142（1.49×）→ 约 4,464（2.12×）→ 约 33,546（15.9×）。

**为什么必须有两级**：`AIQ:120FFEECA78F` 的证据块本身只有 10 字符（"It's grey."），
Minimal 无法修复它的信息不足 —— 这类题只能靠 Extended 或直接判 `UNIQUE_RISK` /
`CONTEXT_INSUFFICIENT`。反过来，把 Extended 当默认会让复核成本涨到不可接受。

---

## 7. 下一次验证该补什么样本（任务书 §15，只设计不执行）

依据 P1-09-B 的结论（answer_unique 最强、learning_value 最弱、没有误伤正常题、
但"真正错误"类样本完全缺席），下一轮验证的样本清单如下：

| # | 样本类型 | 为什么必须补 | 建议数量 | 来源 |
| --- | --- | --- | --- | --- |
| 1 | **真正错误的英语** | P1-09-B 的 10 题里一条语言错误都没有 → `english_correct=FAIL` 的能力完全没被测过 | 2 | 人工撰写 fixture（禁止 AI 生成） |
| 2 | **明显错误的干扰项** | 现有干扰项全部来自教材词表；`distractor_quality=FAIL` 没被测过 | 2 | 人工撰写 fixture |
| 3 | **真正的第二正确答案** | 现有 4 例是"缺上下文导致多解"，不是"语言层面另一答案同样贴合教材语境" | 2 | 优先从真实题库改造（只作为 fixture，不入库）；不足则人工撰写 |
| 4 | **上下文充分但现实常识冲突** | 正是 `B6463523F9E5` 那一类；用来验证 B 类规则（现实常识不得判不唯一）是否稳定 | 2 | 真实题（`B6463523F9E5` 等） |
| 5 | **上下文不足** | 验证 `CONTEXT_INSUFFICIENT` 能不能被正确输出、而不是被记成 FAIL/REJECT | 2 | 真实题（`120FFEECA78F` 等） |
| 6 | **高学习价值正常题** | 现有正常题多为"教材原句挖空"；需要真正的重组题来测 `learning_value=PASS` 的边界 | 3 | 真实题优先（P1-06/P1-07 中的 `RECOMBINED` 类） |
| 7 | **机械但合理的重点词填空** | 验证"机械形式 ≠ 自动 FAIL"这条硬规则是否被稳定遵守 | 2 | 真实题（`BD59C5958D45` / `04CC9B1CF690` 已属此类） |

同时建议在这批样本上**同时验证两条契约规则**：

```text
Minimal 上下文是否消除 AIQ:6ECD02B9D381 式的 evidence_concern
standalone_risk 是否与 answer_unique 分开输出、互不污染
```

---

## 8. 契约边界与保护项

```text
本轮未做：建 question_ai_review 表 / 改 schema / 改 reviewer_prompt.py / 改 validator /
          改 generation pipeline / 改 question_library / 接入学习流程 / 做 UI /
          自动 APPROVED / 自动 ACTIVE / 增加 Prompt 条款
```

全部产物只写在 `audit/AI_question_generation_spike/P1_09_C_review_contract/`。

---

## 9. 验收（任务书 §18 的 13 条）

| # | 条件 | 结果 |
| --- | --- | --- |
| 1 | P1-09-B 的两个机制问题得到明确解释 | **是**：问题 A = 喂了摘录而非证据块全文（全库 18/22 行同形）；问题 B = 旧标签用"现实常识"标准判唯一性 |
| 2 | Review Context Contract V1 可执行 | **是**：字段清单 + 三级上下文 + 禁用字段 + `CONTEXT_INSUFFICIENT` 规则 |
| 3 | Answer Uniqueness Contract V1 可执行 | **是**：两标准 + 四类 + 六步确定性程序 + 四种输出 |
| 4 | 六个质量维度边界清楚 | **是**：`quality_dimensions_contract_v1.md` 逐维给出判断对象/能做/不能做/三档/误判风险 |
| 5 | 程序职责与 AI 职责没有混淆 | **是**：三层职责表 + 禁用输入清单 + 程序负责的 9 项 |
| 6 | `B6463523F9E5` 能通过新口径得到明确解释 | **是**：判 `UNIQUE`，旧标签重映射为 `NOT_A_UNIQUENESS_ISSUE` |
| 7 | Minimal / Extended 有明确区别 | **是**：内容差异 + 实测成本（169.9 / 302.1 tokens/题） |
| 8 | 没有 AI 调用 | **是，0 次** |
| 9 | `question_library.db` 0 修改 | **是**（前后 SHA256 均为 `7AA12CA5…5DA7`） |
| 10 | `learning.db` 0 修改 | **是**（`0C27267B…CF91`） |
| 11 | 正式教材资产 0 修改 | **是**（contentpack v1–v5 / textbook / audio / PDF / 54 MP3） |
| 12 | Web / Android 0 修改 | **是** |
| 13 | V1.3 / V2.0 / V1.0 0 修改 | **是** |

---

## 10. 结论

```text
P1-09-C_DESIGN_PASS
```

本阶段的正确读法：

> **问题 A 是"输入给少了"（喂摘录而不是证据块全文），问题 B 是"判定标准没统一"（拿现实常识判唯一性）。
> 两者都不需要靠继续堆提示词解决 —— 前者靠输入契约（Minimal/Extended + 证据块全文），
> 后者靠判定契约（两标准 + 四类 + 排除规则）。**

尚未解决、留给下一阶段的部分（不得写成已解决）：

```text
1. 契约本身还没有在真实样本上跑过一次（本轮 0 次 AI 调用，全部是离线分析）
2. learning_value 的判定标准虽然写了，但仍然是 P1-09-B 中最弱的维度，需要带标签样本再验
3. distractor_quality 与 answer_unique 的分工在真实数据上只验过 1 例（B6463523F9E5）
4. "真正错误的英语"与"明显错误干扰项"两类样本在现有题库中完全不存在（EXISTING_SAMPLE_INSUFFICIENT），
   需要人工编写 fixture
5. 自动路由（正常题 Minimal / 风险题 Extended）只设计了原则，风险信号本身尚未验证
```

不进入 P1-09-D，等待下一步指令。

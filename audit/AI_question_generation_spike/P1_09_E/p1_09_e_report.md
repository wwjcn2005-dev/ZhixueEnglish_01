# P1-09-E 只读机制设计审计报告 · 答案唯一性机制重构

## 1. 执行结论

```text
结论：P1-09-E_PASS（设计审计完成）
其中包含 1 项明确 BLOCKER：FILL_ITEM_CANDIDATE_POOL（填空题候选池）
```

一句话结论：

> 目标机制「候选池 → AI 逐候选判断 → 程序汇总」**对选择题成立、对填空题不成立**。
> 选择题的候选池就是题目已给出的选项（3–4 个，覆盖完整，成本仅 +18%）；
> 填空题必须由程序生成候选池，而**现有正式数据无法生成"既覆盖真实第二答案、又小到可用"的池子**
> （能覆盖的池有 225–2,062 个词，且全教材正文 87% 的词在正式数据里没有词性）。

```text
AI 调用 = 0 · 未调用 DeepSeek / Ollama / 任何模型
question_library.db / learning.db / contentpack / 教材 PDF / 54 MP3 / Web / Android
  / V1.3 / V2.0 / 正式业务代码 = 0 修改
未新增依赖 · 未安装软件 · 未启动正式 Web 或 Android · 未做试错式实现
全部产物只写入 audit/AI_question_generation_spike/P1_09_E/
```

同时必须指出一个容易误读的事实：P1-09-D 的两次失败**不是候选池覆盖问题**。
那两道题都是 `vocab_choice`，而 `students` / `word` 本来就在选项里 ——
候选集合当时已经完整，是 AI 的"总判定"把 `SUGGEST_ACCEPT` 给出了出来。
换句话说：**候选池能解决"有没有把候选摆到 AI 面前"，解决不了"AI 会不会仍然顺从教材"**，
后者要靠"逐候选提问"这种协议改变，而该协议尚未验证（本阶段 AI = 0）。

---

## 2. 当前数据能力（逐项实测，不只看文件名）

完整字段级结果见 `data_capability_audit.json`。要点：

| # | 资源 | 关键实测 | 对候选池的可用性 |
| --- | --- | --- | --- |
| 1 | `structured/textbook/textbook_structure_v2.json` | `book / units / counts`；unit→section→activity→question 层级齐全 | **间接**：只有定位，没有答案、没有词性 |
| 2 | `structured/exercises/exercise_catalog_v3.json` | 157 个 exercise；**`check_items` 是教材自带的清单型答案项**；`blanks` 合计 850 | **部分可用**：可提供"教材自带清单"型候选 |
| 3 | `structured/exercises/exercise_question_relations_v3.json` | 360 题；**`related_vocabulary` 303/360 有值，平均 4.2 个，最多 20 个**；`related_text` 到 block 级 | **直接可用**：现成的题→词关联 |
| 4 | `structured/ai/textbook_evidence_map_v1.json` | 360 个证据包；`related_text`（block 级 + kind/sample）、`related_vocabulary` 303/360、`ai_rules` 5 条 | **直接可用**：题型级证据与词汇线索 |
| 5 | `contentpack`（v5） | `learning_item` 288 条词汇（**263 条有词性**），245 条带 BOLD；字段含 `lemma / surface_form / part_of_speech / learning_requirement / derivation_type`；`source_ref` 带 `textbook_emphasis` 与 `emphasis_source_list` | **主来源**：唯一同时有词性 + 重点词标记的数据 |
| 6 | `learning.db`（只读） | 学习行为数据 | **不适用** |
| 7 | `question_library.db`（只读） | 21 题；`question_validation` 存 validator 结论（`validation_result` PASS/FAIL、`answer_support_type` 4 值枚举） | **目前没有候选位**（见 §9） |
| 8 | P1-08-B `evidence_assembly.py` | 6 个公开函数（`section_page_ranges` / `pages_of_section` / `blocks_of_section` / `activities_of_section` / `build_section_evidence` / `blocks_by_activity_only`） | **可用**：只读重建 Section/Activity 上下文 |
| 9 | P1-09-C 三份契约 | 均存在 | **基线**：本阶段在其上做增量设计 |
| 10 | P1-09-D fixture 与报告 | 15 道边界 fixture + 逐维对照（36/41） | **可用**：本轮两个失败案例的来源 |
| 11 | validator / gate / fingerprint | `validator_v2._lemmas` **只能归并**（ies/es/s/ed/ing），**不能反向生成屈折形式**；fingerprint 为 64 hex 唯一索引 | **部分可用**：需要另写"生成方向"的词形规则 |

### 2.1 三个必须写清楚的数据事实

```text
① 正式教材题库没有任何"标准答案"
   exercise_question_relations_v3：360/360 题的 answer_source = NO_RELIABLE_SOURCE
   textbook_evidence_map_v1      ：360/360 包的 answer_source = NO_RELIABLE_SOURCE
   → 候选池不能从"标准答案"推导，只能从"教材词汇 / 正文 / 关联"推导。

② 词性覆盖只有 12.7%
   全教材正文 2,063 个不同英文词；其中在正式数据里有词性的只有 263 个（12.7%）。
   → 按词性过滤候选词的方案，对 87% 的正文词直接失效。

③ 两个真实第二答案都不在教材词表里
   students、word 均**不在** 288 条教材词汇中（friends、grandpa、teacher 也不在）。
   → 只用"教材词表"建候选池，必然漏掉这两个真实答案。
```

---

## 3. 候选答案池设计（五种来源逐一判断）

完整实测数据见 `candidate_pool_probe.json`、`slot_filter_probe.json`、`pool_size_analysis.json`。

### A. Unit 加粗重点词（contentpack BOLD）

```text
可用性：可用，但覆盖不足
规模：教材词汇 288 条 → 245 条带 BOLD；按词性过滤后（同词性、同一 Unit）
      实测 0–117 个（FIX-C1 的答案 friends 没有词性 → 0 个；FIX-C2 → 117 个）
覆盖率：0/2 —— 两个真实第二答案都不在词表里
如何避免把完全无关的词全送 AI：做不到。词表本身不带"与题干的语义槽位是否相符"，
      按词性过滤只能把 288 收窄到 117（例如 FIX-C2 得到 117 个同词性名词）。
```

**结论**：可以作为**优先级提示**（"这是本单元重点词，值得优先检查"），
**不能**作为候选池的唯一来源。

### B. Phrase（23 条）

```text
适用题型：短语/固定搭配型填空题（如 write ... down、fire up our instruments）
本轮两个失败案例都不适用（两个空都是单词级）
判断：可作为"短语空位"的候选来源，但覆盖的是短语本身，不产生单词级替代答案
```

### C. Sentence Pattern（52 条）

```text
判断：提供的是句法框架（例如 It feels great to ___），不是可替换的答案词
用途：可用来推断空位应填什么词性、什么形式（对词形/结构约束有用）
不能用来产生替代答案 → 不作为候选来源，只作为"空位约束"来源
```

### D. 教材正文词汇（Section / Activity / evidence block）

```text
可用性：全覆盖，但规模不可用
规模实测（同一 Section 正文）：FIX-C1 → 236 个词；FIX-C2 → 225 个词
全书正文：2,062 个词
覆盖率：2/2（students 在 U2 UI 正文 P40:B20；word 在 U1 UI 正文 P22:B1）
```

**结论**：这是**唯一能覆盖真实第二答案的现成数据源**，但 225–2,062 个候选无法直接交给 AI。

### E. 词形变化（重点分析）

```text
现有数据支持情况：
  learning_item 有 lemma + surface_form，但没有屈折形式表；
  validator_v2._lemmas 只是"归并方向"（student→students 这类反向不成立）；
  → 生成方向必须自建规则。

本轮实现了原型规则（candidate_pool_probe.forms）：
  s / es / ies / ed / d / ing + y→ies 等基础规则

但必须指出：本轮的两次失败**根本不是词形变化问题**。
  students 不是 friends 的屈折形式，word 也不是 sentence 的屈折形式。
  两者是"同一语义槽位里的另一种合理实体"，属于语义层面的替换，不是形态层面的变化。
→ 词形变化是候选池的必要能力，但对本次两个案例无效。
```

### 3.1 五种来源汇总

| 来源 | 规模（实测） | 覆盖 P1-09-D 两个真实第二答案 | 定位 |
| --- | --- | --- | --- |
| A Unit BOLD 重点词（+词性） | 0–117 | **0/2** | 优先级提示 |
| B Phrase | 23（短语级） | 不适用 | 短语空位专用 |
| C Sentence Pattern | 52 | 不适用 | 空位约束（不是答案） |
| D 教材正文词汇 | 225–2,062 | **2/2** | 唯一覆盖，但规模不可用 |
| E 词形变化（规则生成） | 取决于基词 | 对这 2 个案例无效 | 必要能力，非本案例解 |

**另测了一种确定性精确过滤（同槽位代入）**：把空位前后的字面片段当模板，在全教材里找同位置出现过的词。

```text
with his ___        → 候选 3 个（friends / bike / family）→ students、grandpa 均不在
a ___ on the blackboard → 候选 1 个（只有 sentence 本身）→ word 不在
```

即：**精确过滤（1–3 个）漏掉真实答案，宽过滤（225+ 个）才覆盖** —— 这正是本阶段的核心权衡结论。

---

## 4. 两个失败案例的离线验证

### Case A：`... in the park with his ___`（P1-09-D 的 FIX-C1，存储答案 friends）

```text
需要判断的潜在替代答案：students（题面还给出 parents / teachers 作为干扰项）

候选来源            | 候选词                                          | 规模 | 是否进入候选池 | 为什么
--------------------|------------------------------------------------|------|----------------|----------------------------
A Unit BOLD 词表    | （friends 本身无词性 → 无法按词性过滤）           | 0    | 未进入         | 词表里根本没有 student/friends
B Phrase            | 不适用（空位是单词级）                            | –    | 不适用         | –
C Sentence Pattern  | 不适用（只给结构约束）                            | –    | 不适用         | –
D Section 正文      | students ✓ / grandpa ✓ / teachers ✗              | 236  | **进入**       | students 出现在同一 Section 正文 P40:B20
D 全书正文          | students ✓ / grandpa ✓ / teachers ✓              | 2062 | 进入           | teachers 只在别处出现
E 词形变化          | 不适用（students 不是 friends 的屈折）             | –    | 不适用         | –
同槽位代入（精确）   | friends / bike / family                          | 3    | **未进入**     | 教材里没有 "with his students" 这种同槽位出现

结论：只有"Section 正文全词"能覆盖 students，但池子有 236 个词；
      精确的同槽位过滤只有 3 个候选却漏掉了答案。
```

### Case B：`... writes a ___ on the blackboard`（P1-09-D 的 FIX-C2，涉及 sentence ↔ word）

```text
需要判断的潜在替代答案：word（题面同时给出 sentence / word / picture / name）
（本次实验的 FIX-C2 把 sentence 作为存储答案、word 作为设计中的第二答案；
  任务书提到的是反向表述，两者互为替代，验证内容相同）

候选来源            | 候选词                                          | 规模 | 是否进入候选池 | 为什么
--------------------|------------------------------------------------|------|----------------|----------------------------
A Unit BOLD 词表    | 117 个同词性名词（actress / adult / advice …）    | 117  | **未进入**     | word 不在教材词表
B Phrase            | 不适用                                           | –    | 不适用         | –
C Sentence Pattern  | 不适用                                           | –    | 不适用         | –
D Section 正文      | word ✓ / name ✓                                  | 225  | **进入**       | word 出现在同一 Section 正文 P22:B1
D 全书正文          | word ✓ / name ✓                                  | 2062 | 进入           | –
E 词形变化          | 不适用（word 不是 sentence 的屈折）                | –    | 不适用         | –
同槽位代入（精确）   | sentence（只有原答案本身）                        | 1    | **未进入**     | 教材只在这一处出现过该槽位

结论：与 Case A 相同 —— 精确池漏检、宽池才覆盖。
```

### 4.1 但必须同时记录一个反向事实（否则会误判本阶段结论）

```text
FIX-C1 与 FIX-C2 在 P1-09-D 里都是 vocab_choice，
而 students / word 本来就在题目的选项里。
→ 对选择题而言，候选池 = 选项，**覆盖是 COMPLETE 的，规模只有 3–4 个**。
→ 所以 P1-09-D 的 0/2 并不是"候选池没找到"，而是"AI 拿到了候选却仍然判 PASS"。
```

这条区分决定了下一阶段该做什么（见 §11）。

---

## 5. 候选覆盖率分析（含"PASS 但实际不好用"的 8 项检查）

任务书 §14 要求逐项检查"即使机制技术上 PASS，是否仍可能漏掉真正的第二答案"。逐项实测结果：

| # | 风险项 | 实测结论 | 等级 |
| --- | --- | --- | --- |
| 1 | 候选池覆盖不足 | **确认**：能覆盖的池 225–2,062 个；能用的池（1–117）覆盖 0/2 | **BLOCKER（仅填空题）** |
| 2 | 词形变化漏检 | 现有数据无屈折表，只有归并方向的 `_lemmas`；本轮自建规则原型可生成，但**本次两个真实答案都不是屈折形式** | LIMITATION |
| 3 | 同义表达漏检 | **确认**：`students` 与 `friends`、`word` 与 `sentence` 之间没有任何正式记录的关系（非同义、非上下位、非屈折） | **BLOCKER** |
| 4 | 不在教材 Vocabulary 中但语法成立的答案 | **确认**：`students`、`word` 都不在 288 条教材词表中 | **BLOCKER** |
| 5 | 题目本身上下文不足 | 已有机制（`CONTEXT_INSUFFICIENT`），P1-09-D 实测 2/2 有效，且未升级为 REJECT | 已解决 |
| 6 | 候选数量过大导致 AI 判断退化 | 规模实测 117–2,062，**风险高但未用 AI 验证**（本阶段 AI=0） | 风险（未验证） |
| 7 | AI 对教材答案产生锚定 | **确认**：P1-09-D 的 0/2，两次都 HIGH 置信度 + "答案与课文一致" | **BLOCKER（解题协议层）** |
| 8 | 程序错误地把"没找到候选"当成"唯一" | 设计上必须禁止；本轮已据此提出 fail-safe（见 §7） | 已设计防呆 |

三项 BLOCKER 合起来的含义：

```text
填空题：现有数据 + 现有依赖政策（禁止新增依赖）下，"候选池 → AI 逐候选 → 程序汇总"
        无法成为"答案唯一性"的证明机制；
选择题：候选池已经完整，BLOCKER 只剩下第 7 项（AI 锚定），而这一项恰好是"逐候选协议"要解决的，
        该协议本阶段未验证。
```

---

## 6. AI / 程序职责边界（任务书 §8）

### 6.1 每个候选的判断协议（AI 侧）

```text
candidate = X
grammar_valid:          YES / NO
semantic_valid:         YES / NO
textbook_context_valid: YES / NO      ← 只针对"程序给出的教材证据"，AI 不得扩展证据范围
reason:                 简短、具体（中文）
```

### 6.2 三类职责划分

**应该交给 AI 的判断**

```text
1. 候选在题目空位里语法是否成立（grammar_valid）
2. 候选在语义上是否说得通（semantic_valid）
3. 候选是否与"程序给出的教材证据"冲突（textbook_context_valid）
4. 每个候选的一句中文理由（供人类复核）
```

**必须由程序完成的判断**

```text
1. 候选集合的生成（来源、去重、词形展开）
2. 空位识别与词性/形式约束
3. 教材证据范围（哪些块属于证据、证据全文）
4. 覆盖率等级（COMPLETE / PARTIAL / NONE），以及由此决定"能不能判 UNIQUE_SUPPORTED"
5. 汇总与状态计算
6. 生命周期（PENDING_REVIEW → APPROVED → ACTIVE）与一切写库动作
```

**两者都不应该承担的判断**

```text
1. "这道题的答案是否唯一" —— 不能作为 AI 的自由文本结论（P1-09-D 已证明会顺从教材），
   也不能由程序在覆盖不足时给出（§7 的逻辑防呆）
2. "这道题是否应该采用" —— 只能由人类决定
3. 教材证据边界之外的任何事实认定（AI 不得扩张证据范围，程序也不得替教材下结论）
```

特别强调（与任务书要求一致）：**教材证据边界必须继续由程序控制。**
AI 只能在程序给出的证据范围内回答"这个候选是否与之冲突"；
如果 AI 认为"需要更多教材上下文才能判断"，只能回报 `NEED_MORE_CONTEXT`，由程序决定是否补上下文。

---

## 7. 最终状态设计（任务书 §7 与 §9）

### 7.1 推荐：3 个终态 + 1 个覆盖度限定符

```text
answer_uniqueness_status ∈ { UNIQUE_SUPPORTED, UNIQUE_UNCERTAIN, UNIQUE_RISK }
candidate_coverage       ∈ { COMPLETE, PARTIAL, NONE }
```

**UNIQUE_SUPPORTED（允许进入的唯一前提）**：必须同时满足

```text
1. candidate_coverage = COMPLETE（候选池对本题空位类型是完备的）
2. 所有候选都通过逐候选判断，且没有任何候选的 grammar_valid=semantic_valid=textbook_context_valid 同时为 YES
3. 逐候选判断本身没有 NEED_MORE_CONTEXT
4. 程序侧确认题目上下文充分（非 CONTEXT_INSUFFICIENT）
```

**UNIQUE_UNCERTAIN（产生条件）**

```text
候选池为空，或 coverage = PARTIAL/NONE，或存在 NEED_MORE_CONTEXT 的候选，
或所有候选都被排除但覆盖度不是 COMPLETE。
→ 含义：我们没有找到第二答案，但**没有任何证据能保证"不存在"**。
```

**UNIQUE_RISK（产生条件）**

```text
至少一个候选的 grammar_valid = YES 且 semantic_valid = YES 且 textbook_context_valid = YES
（即：语法成立、语义成立、且与教材证据不冲突）
→ 这就是 P1-09-D 里 AI 应该给出、但没有给出的那类判断。
```

### 7.2 关于"找不到第二答案时，什么条件下仍然不能判 UNIQUE_SUPPORTED"

这是本阶段最重要的一条设计约束：

```text
找不到 ≠ 唯一。
只有当"候选池对该空位类型是完备的"（coverage = COMPLETE）时，找不到才能支撑 UNIQUE_SUPPORTED。

而本轮实测：填空题的候选池在现有数据下**永远达不到 COMPLETE**
（能覆盖的池 225–2,062 个且 87% 无词性；能用的池覆盖 0/2）。
→ 因此对填空题，程序**在当前数据条件下不应输出 UNIQUE_SUPPORTED**，
   只能输出 UNIQUE_UNCERTAIN（或 UNIQUE_RISK）。
```

### 7.3 `UNIQUE_UNCERTAIN` 与 `CANDIDATE_COVERAGE_INSUFFICIENT` 是否都需要？

**建议：都需要，但不在同一层。**

```text
CANDIDATE_COVERAGE_INSUFFICIENT 是"为什么不能判唯一"的**原因限定符**（覆盖度层）
UNIQUE_UNCERTAIN                是"最终结论"（状态层）
UNIQUE_RISK                     是"发现了候选"（状态层）
```

理由：

```text
如果只保留 CANDIDATE_COVERAGE_INSUFFICIENT：
  无法区分"覆盖不足且没找到候选"与"覆盖不足但找到了候选" —— 后者的处理完全不同（后者要人工优先看）。
如果只保留 UNIQUE_UNCERTAIN：
  人工审核人看不到"为什么不确定"，会把"程序没找到"误读成"大概没问题"。
→ 两者语义不同、用途不同，都应保留；实现上可以合成一个 4 值枚举
  （UNIQUE_SUPPORTED / UNIQUE_UNCERTAIN / UNIQUE_RISK / CANDIDATE_COVERAGE_INSUFFICIENT）
  以方便入库；但报告与人工界面上必须同时显示 coverage。
```

---

## 8. 成本分析（任务书 §10，全部为离线估算，未调用 AI）

基准：P1-09-D 实测 **1,024.7 tokens/题**（prompt 261.3 + completion 763.5）。
候选成本按每候选 prompt +10 tokens、输出 +35 tokens（三个 YES/NO 字段 + 一句理由）估算。

| 候选池 | 规模 | 覆盖 | 方案 A（每题 1 次调用判全部候选） | 方案 B（每候选 1 次调用） |
| --- | --- | --- | --- | --- |
| **选择题：候选池 = 选项** | **4** | **COMPLETE** | **1,205 tokens/题（1.18×）** | 4 次调用 / 6,740 tokens（6.58×） |
| 填空题：同槽位精确池 | 2 | PARTIAL（漏真实答案） | 1,115 tokens/题（1.09×） | 2 次调用 / 3,370 tokens（3.29×） |
| 填空题：词表 BOLD + 词性 | 117 | PARTIAL（漏真实答案） | 6,290 tokens/题（6.14×） | 117 次调用 / 197,145 tokens（**192×**） |
| 填空题：Section 正文全词 | 230 | 覆盖但不可用 | 11,375 tokens/题（**11.1×**） | 230 次调用 / 387,550 tokens（**378×**） |

结论：

```text
1. 方案 B（每候选一次调用）在任何可用池上都不可接受：调用次数按池规模线性增长，
   117–230 次/题 → 成本 192–378 倍。**应排除方案 B。**
2. 方案 A（每题一次判全部候选）在选择题上完全可行：池 3–4 个，成本只涨 18%，
   且覆盖度是 COMPLETE —— 这是本阶段唯一"既覆盖又便宜"的组合。
3. 方案 C（程序先强过滤再一次性批量判断）= 方案 A 配一个小池；
   在选择题上等价于 A（池本来就只有选项）；在填空题上受制于"过滤后就漏检"（§4）。
4. 速度：方案 A 每次调用与现有复核同级（P1-09-D 单次 129.7 s / 15 题）；
   方案 B 会串行累加，且触发项目自身的"单次调用 > 300 秒硬停止"以外的批量风险。
5. 可扩展性：方案 A 可随题数批量扩展（一 Section 一次）；方案 B 不可扩展。
6. 可靠性：方案 A 的可靠性取决于"候选池是否 COMPLETE"；选择题 COMPLETE，
   填空题最多 PARTIAL → 这一条直接决定了 §7 的状态设计。
```

### 8.1 各题型的候选规模

```text
vocab_choice / reading_choice：候选池 = 题目选项（3–4 个），COMPLETE，不需要生成
reading_judge：无候选（True/False 由教材事实决定），不适用候选池
fill：需要生成候选池 —— 现有数据下 1–117（漏检）或 225–2,062（不可用）
其他题型（match / short_answer / writing 等）：不在当前 AI 生成范围内
```

---

## 9. question_library 后续结构建议（只设计，不执行迁移）

### 9.1 `question_validation` 是否适合保存候选答案分析？

**不适合。** 实测理由：

```text
该表字段为：validator_version / validation_result(PASS|FAIL) / answer_support_type(4 值枚举)
            / checks_json / out_of_scope_tokens_json / needs_human_review / note

1. 它是"程序验证结果"的语义位置；塞入 AI 的逐候选判断会把"机器验证"与"模型判断"混在一起，
   而 P1-09-C 与 P1-09-D 的结论都要求这两者严格分离。
2. 它没有候选维度的位置：一个候选一行（一题可能 1–230 行），与该表的主键
   (question_id, version, validator_version) 结构不匹配。
3. 该表已被 judge 题的兼容编码占用（P1-09-A 实测：布尔答案只能编码成
   VERIFIABLE_REPHRASE），再加一层语义必然更混乱。
```

### 9.2 建议的未来结构（design only）

```text
question_answer_candidate   （程序侧，append-only）
  candidate_id · question_id · version
  candidate_text · candidate_lemma · inflection_form
  source_type ∈ {OPTION, VOCABULARY_BOLD, SECTION_TEXT, UNIT_TEXT, PHRASE, INFLECTION, SLOT_PATTERN}
  source_ref（block_id / item_id / option_index）
  pos_known(0/1) · pos · coverage_class ∈ {COMPLETE, PARTIAL, NONE}
  generated_at · generator_version

candidate_review            （AI/人类侧，append-only）
  candidate_id · judge_kind ∈ {AI, HUMAN}
  grammar_valid · semantic_valid · textbook_context_valid  ∈ {YES,NO,UNKNOWN}
  need_more_context(0/1) · reason_text（中文）
  model · prompt_version · review_context_hash · reviewed_at

answer_uniqueness_assessment（每题每次运行一行，append-only）
  question_id · version · run_id
  status ∈ {UNIQUE_SUPPORTED, UNIQUE_UNCERTAIN, UNIQUE_RISK, CANDIDATE_COVERAGE_INSUFFICIENT}
  candidate_coverage ∈ {COMPLETE, PARTIAL, NONE}
  candidate_count · excluded_count · risk_count
  assessed_at · assessor_version
```

三条硬规则：

```text
1. 程序验证结果留在 question_validation，AI 判断留在 candidate_review —— 不得合并
2. 任何一张表都不得写入 lifecycle_status；AI 结论不得产生 question_event
3. 候选与判断都是 append-only；重新判断只能新增行
```

本阶段**不建表、不改 schema**，以上只是设计。

---

## 10. P1-09-C 契约影响分析（只提修改建议，本轮不改契约）

### 10.1 `answer_uniqueness_contract_v1.md`

**保留（本轮实测仍然正确）**

```text
1. 四类区分 A 教材语境唯一 / B 现实常识存在其他解释 / C 语言层面存在其他合理解答 / D 信息不足
   —— P1-09-D 实测：D 类克制 2/2 有效（现实常识没有被误判成不唯一）
2. 两种作答标准 TEXTBOOK_ANCHORED / SELF_CONTAINED
3. 候选被排除的判据：语法不成立 ∨ 语义不成立 ∨ 与教材原文陈述冲突
4. "答案出现在教材里不能作为通过理由"
```

**需要重写**

```text
1. §3「判定程序」第 2–3 步：把"由 AI 拿掉答案去穷举候选"改成
   "由程序生成候选池 → AI 只对给定候选逐条判断 → 程序汇总"。
   依据：P1-09-D 证明让 AI 自由判断会退化为顺从教材。
2. §6「对既有真实案例的离线重判」中关于 BD59C5958D45 的 standalone_risk 表述，
   需要与新终态（UNIQUE_SUPPORTED/UNCERTAIN/RISK）对齐。
```

**需要新增**

```text
1. 覆盖度前置条件：只有 candidate_coverage = COMPLETE 才允许 UNIQUE_SUPPORTED
2. 新终态：UNIQUE_UNCERTAIN、CANDIDATE_COVERAGE_INSUFFICIENT
3. 逐候选输出协议（grammar_valid / semantic_valid / textbook_context_valid / reason）
4. 明确禁止：AI 的自由文本"唯一性结论"不得作为判定依据
5. 明确填空题在当前数据条件下不能输出 UNIQUE_SUPPORTED（带日期与实测依据）
```

### 10.2 `review_context_contract_v1.md`

**保留**：三层职责、必须给/禁止给清单、Minimal/Extended 两级、`CONTEXT_INSUFFICIENT` 规则。

**需要新增**

```text
1. Review Context 里增加"候选清单"字段（candidates[]，来自程序，带 source_type 与 coverage_class）
2. AI 不得自行增加候选；如认为缺少候选，只能回报 need_more_candidates = true（作为程序侧信号）
3. 每个候选必须与"同一份教材证据全文"一起给出，避免逐候选判断时的上下文漂移
```

### 10.3 `quality_dimensions_contract_v1.md`

**需要重写**

```text
answer_unique 维度的定义：从"AI 判断答案是否唯一（PASS/CONCERN/FAIL）"
改成"汇报候选池覆盖状态 + 逐候选判断结果（不直接给唯一性结论）"。
```

**需要新增**

```text
1. candidate_coverage 的取值与含义
2. 明确"学习价值/自然度/干扰项/年级/英语正确"五个维度的结论与"唯一性终态"相互独立，
   不得用一方的 PASS 掩盖另一方的 UNCERTAIN（P1-09-D 已经出现过"整体 ACCEPT 掩盖唯一性漏检"）
```

---

## 11. 路线结论（必须明确回答的 5 个问题）

### 1. 现有数据能不能支撑"候选池 → AI 逐候选判断 → 程序汇总"？

```text
选择题（vocab_choice / reading_choice）：**能**。候选池 = 题目选项（3–4 个），
  覆盖 COMPLETE、规模最小、成本仅 +18%。
填空题（fill）：**不能**。现有数据无法生成"既覆盖真实第二答案、又小到可用"的候选池
  （覆盖的池 225–2,062 个；能用的池 1–117 个且实测漏检 0/2）。
```

### 2. 如果能，最小可行候选池是什么？

```text
对选择题：候选池 = 选项本身。不需要任何新数据、不需要词性、不需要词形展开，
  而且覆盖度是 COMPLETE。这是本阶段唯一可直接实施的最小可行池。
（若要再加一层：把"与答案同词性的其它选项"标为优先候选，但这只是排序，不改变覆盖度。）
```

### 3. 如果不能，缺什么？

```text
填空题缺三样东西，而且都缺在"数据"而不是"算法"上：
  ① 词性与词形资源：全教材正文 2,063 个词里只有 263 个（12.7%）在正式数据中有词性；
     没有屈折形式表（只能自建规则，而规则的母本仍受词表限制）。
  ② 语义槽位知识：students 与 friends 不是同义、不是上下位、不是屈折关系，
     没有任何正式数据记录"爷爷还能和谁一起在公园拉二胡"。
  ③ 同义/近义表达资源：项目当前完全没有。
补这三样都需要引入新的词库或 NLP 依赖，而项目本阶段明确禁止新增依赖。
——注意这不是"再加一轮候选池 Spike 就能解决"的问题（见问题 5）。
```

### 4. 是否值得继续做？

```text
值得继续的部分：选择题路线的逐候选协议（成本 +18%、覆盖 COMPLETE、直击 P1-09-D 的 0/2 失败）。
不值得继续的部分：把"候选池 → 唯一性证明"用到填空题上。
  在数据缺口被补齐之前，填空题只能停在 UNIQUE_UNCERTAIN / CANDIDATE_COVERAGE_INSUFFICIENT，
  这本身仍然有价值（fail-safe：宁可说"无法证明"，也不能错说"唯一"）。
```

### 5. 下一步应该是 A / B / C 中的哪一个？

```text
选择：**A（先做选择题的逐候选协议实现 + 用 P1-09-D 的 FIX-C1/FIX-C2 复测）**
      + 对填空题采用 fail-safe 设计（不实现 UNIQUE_SUPPORTED）。

为什么不是 B（再做一次离线候选池 Spike）：
  本轮已经用真实数据把"覆盖 vs 规模"的权衡测清楚了：精确过滤 1–3 个候选漏掉真实答案，
  宽过滤 225–2,062 个才覆盖，词性覆盖 12.7% —— 这三个数字是数据事实，
  再扫一遍不会改变它们。除非改变输入数据（新增词库/依赖，本阶段禁止），B 得不到新结论。

为什么不是 C（放弃该路线换机制）：
  对选择题不需要换机制，现有数据已经足够；
  对填空题，本设计给出的 fail-safe（永不输出 UNIQUE_SUPPORTED）本身就是一个可用的替代机制，
  不是"放弃"。
```

---

## 12. 最终结论与下一步

```text
P1-09-E_PASS（只读机制设计审计完成）
   附带 1 项 BLOCKER：FILL_ITEM_CANDIDATE_POOL
   附带 1 项 LIMITATION：词形/词性资源覆盖不足（12.7%）
```

读者请不要把 PASS 误读成"机制已经可行"：

```text
本阶段 PASS 的含义是"设计审计完成、结论明确、路线已定"，
而不是"候选池机制已在数据上被验证可行"。
填空题部分被明确判定为 BLOCKER。
```

**明确的下一步（不自动执行）**

```text
1. 实施"选择题逐候选协议"：
   候选池 = 选项 → 对每个候选问 grammar_valid / semantic_valid / textbook_context_valid
   → 程序按 §7 汇总为 UNIQUE_SUPPORTED / UNIQUE_UNCERTAIN / UNIQUE_RISK
2. 用 P1-09-D 的 FIX-C1 / FIX-C2 做复测（这两题的候选池本来就完整）：
   验证"逐候选提问"是否能消除 P1-09-D 观察到的教材锚定。
3. 填空题按 fail-safe 落地：候选池标 coverage=PARTIAL/NONE，
   一律不得输出 UNIQUE_SUPPORTED；输出进人工复核信息。
4. 若后续要解决填空题，必须先做一次数据决策（新增词性/词库资源 或 接受"永远不确定"），
   这属于产品与工程的数据边界决策，不是 Prompt 问题。
```

本阶段到此停止，等待下一步指令。

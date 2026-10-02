# P1-09-G 只读机制设计与离线验证报告 · 选择题唯一性风险分层

最终结论：**`P1-09-G_BLOCKED`**

```text
含义：现有数据（+ 不新增依赖的约束）不足以进行有意义的"程序预筛"。
     本轮不是"设计没做完"，而是"这一层在数据上做不到它被要求做的事"。
AI 调用 = 0 · 全部为只读离线分析 · 所有新增产物只写入 P1_09_G 目录
```

一句话结论：

> 程序预筛同时犯了两个错：**对正常的题太宽（80% 的选择题被标为 AI_REVIEW_CANDIDATE，
> 连已经人工审核通过的 ACTIVE 题也被标了），对真正的风险又太窄（漏掉 FIX-C1）**。
> 根因是数据：87% 的词没有词性、没有语义资源、没有可靠答案来源 ——
> 能大面积触发的规则，恰好无法在真正需要的题上触发。

---

## 1. 执行结论

### 1.1 本轮实际做了什么

```text
1. 只读审计当前 question_library.db 的 21 道题（按题型统计 + 选择题逐题取证）
2. 设计并实现 7 条确定性预筛规则（R1–R7，全部离线、无 AI、无新依赖）
3. 把规则跑在 10 道真实选择题 + P1-09-D/F 的 2 个已知风险 fixture（共 12 例）上
4. 用真实结果量化"AI 候选率"，做反向"不要误杀"验证
5. 用 P1-09-F 的实测 token 重算 4 档成本模型
6. 给出 answer_unique 产品定位、fill 处理方案、库结构建议、架构修正建议
```

### 1.2 三条决定性结果

```text
① 预筛过宽：10 道真实选择题中 8 道被标为 AI_REVIEW_CANDIDATE（80%），
   其中包含已经人工审核通过并处于 ACTIVE 的 AIQ:BD59C5958D45。
② 预筛过窄：FIX-C1（明确存在第二正确答案 students）被判 NO_AI_SIGNAL → 漏检。
   （FIX-C2 被 R5 捕获，所以是 1 漏 1 中，不是全漏。）
③ 规则价值不均：R1（选项重复/包含）与 R2（词形变化对）在 12 例上**一次都没触发**；
   真正大面积触发的是 R3/R4（同词性）与 R5（教材来源），而这两类恰恰是"会连正常题一起标"的规则。
```

### 1.3 为什么判 BLOCKED 而不是 STOP_AND_FIX

```text
STOP_AND_FIX 的含义是"预筛机制本身有结构性问题，需要重新设计规则"。
但本轮的证据表明：问题不在规则写法，而在数据 —— 任何确定性规则都无法同时做到
  "不标 AIQ:BD59C5958D45（ACTIVE，人工已通过）" 与 "标出 FIX-C1（真第二答案）"，
因为它们之间的差别是语义层面的（"和谁一起在公园拉二胡"是否开放），
而现有正式数据没有词性（87% 缺失）、没有语义资源、没有可靠答案来源。
→ 因此按任务书 §16 的定义，属于"现有数据不足以进行有意义的预筛" = BLOCKED。
```

---

## 2. 21 道现有题的题型分布

```text
fill 9 · vocab_choice 6 · reading_choice 4 · reading_judge 2      （合计 21）
生命周期：ACTIVE 1 · PENDING_REVIEW 19 · REJECTED 1
```

### 2.1 选择题逐题取证（6 道 vocab_choice + 4 道 reading_choice）

| question_id | 题型 | 状态 | 答案 | 选项 | 教材位置 |
| --- | --- | --- | --- | --- | --- |
| `AIQ:3179968E3E74` | vocab_choice | PENDING_REVIEW | polite | polite / dry / important / mistake | U1 UI · 第 17 页 A2 |
| `AIQ:5B4C80443D5F` | vocab_choice | PENDING_REVIEW | mistake | mistake / mind / meaning / fact | U1 UI · 第 18 页 A4 |
| `AIQ:6721EC6C5D1F` | vocab_choice | PENDING_REVIEW | root | root / stem / sugar / oxygen | U5 UI · 第 82 页 A4 |
| `AIQ:75AAEBFE06DF` | vocab_choice | PENDING_REVIEW | different | different / traditional / electric / weak | U2 UI · 第 32 页 A1 |
| `AIQ:A9D1F3EC6020` | vocab_choice | PENDING_REVIEW | sentence | sentence / mistake / mind / meaning | U1 UI · 第 18 页 A4 |
| `AIQ:BD59C5958D45` | vocab_choice | **ACTIVE** | band | band / club / stage / instrument | U2 UI · 第 32 页 A1 |
| `AIQ:6ECD02B9D381` | reading_choice | PENDING_REVIEW | fire up instruments | write songs / share songs online / fire up instruments / sing Beijing opera | U2 UI · 第 33 页 A2 |
| `AIQ:879007FA4FC7` | reading_choice | PENDING_REVIEW | in the park | in the park / in the school band / on the stage / in his room | U2 UI · 第 32 页 A1 |
| `AIQ:B6463523F9E5` | reading_choice | PENDING_REVIEW | their own rain | their own rain / sugar / oxygen / food | U5 UI · 第 83 页 A7 |
| `AIQ:CD8B21681B4C` | reading_choice | PENDING_REVIEW | school uniform | school uniform / sports jacket / T-shirt / red scarf | Starter GR · 第 5 页 A10 |

完整证据块、Unit / Section / Activity 与规则细节见 `prescreen_result.json`。

---

## 3. 程序预筛规则设计（R1–R7）

全部为确定性规则，无 AI、无新依赖、无评分：

| 规则 | 含义 | 判定依据（全部来自现有正式数据） |
| --- | --- | --- |
| **R1** 选项重复 / 包含 | 归一化（去冠词、去标点、小写）后两选项相同或互相包含（如 book / books / a book） | 纯字符串 |
| **R2** 词形变化对 | 两个选项归并后共享同一词元（student/students、write/writes、play/playing） | 规则化词形归并（validator 同源思路的反方向） |
| **R3** 同词性平行 | ≥2 个非答案选项与答案词性相同 | contentpack `learning_item.part_of_speech` |
| **R4** 实词槽平行 | R3 且答案是实词（n/v/adj/adv） | 同上（语义槽位相容性的**确定性代理**） |
| **R5** 教材来源 | 选项是否出现在词表 / Section 正文 / Unit 正文 / 全书正文 | contentpack 词表 + 正文块 |
| **R6** 选项与证据块关系 | 非答案选项是否也出现在同一证据块内 | `question_evidence.evidence_block_id` + 块全文 |
| **R7** 题干上下文长度 | 题干（去空位）少于 6 个英文词 | 纯计数 |

### 3.1 规则触发统计（12 例）

```text
R3 同词性平行        触发 6 次
R4 实词槽平行        触发 6 次（与 R3 同源，只是多了一个"实词槽"限定）
R5 教材来源          触发 8 次   ← 触发面最广
R6 证据块关系        触发 1 次
R7 短题干            触发 1 次
R1 选项重复/包含     触发 0 次   ← 在本批数据上无价值
R2 词形变化对        触发 0 次   ← 在本批数据上无价值
```

### 3.2 明确不做什么（任务书 §6）

```text
不做"风险 = 73 分"
不做 0–30 低 / 31–60 中 / 61–100 高 这种区间评分
本轮只保留两个可解释状态：NO_AI_SIGNAL / AI_REVIEW_CANDIDATE
（LOW_RISK / REVIEW_WORTHY / HIGH_RISK 三档本轮**未被采用**，
 因为实测无法给出各档可靠的分界依据；保留三档只会制造"看起来精细"的假象。）
```

---

## 4. FIX-C1 / FIX-C2 验证（任务书 §7）

两个 fixture 的 section 关联按它们的 `location` 字段补齐（"Unit 2 · Understanding ideas" /
"Unit 1 · Understanding ideas"，属于允许的定位信息，不是 gold）。

### FIX-C1：`Grandpa likes playing the erhu in the park with his ___.`（friends / students / parents / teachers）

```text
结论：NO_AI_SIGNAL → **漏检**（该题已被 P1-09-F 证实存在真正的第二正确答案 students）

逐规则结果：
  R1 未触发（无重复/包含）
  R2 未触发（无词形变化对）
  R3/R4 未触发 —— 直接原因：答案 friends 在教材词表里**没有词性**（friend 不在 288 条词表中），
       R3 需要"答案词性已知"才能比较，因此整条规则失效
  R5 未触发 —— 非答案选项中只有 students 出现在 U2 UI 正文（P40:B20），
       parents / teachers 只出现在全书其它页面 → 计数为 1 < 2，达不到阈值
  R6 未触发 —— students 不在证据块 P37:B12 内
  R7 未触发 —— 题干 10 词
```

### FIX-C2：`Ms Chen writes a ___ on the blackboard.`（sentence / word / picture / name）

```text
结论：AI_REVIEW_CANDIDATE → **命中**（由 R5 触发）

  R3/R4 未触发（word / picture / name 在词表中没有词性）
  R5 **触发** —— 非答案选项中有 2 个（word、name）出现在 U1 UI 正文，
       picture 只在全书其它位置出现
  R6 / R7 未触发
```

### 4.1 关键结论

```text
同一个机制在两个同类风险上给出相反结果（一个中、一个漏），
而差别只来自"非答案选项是否碰巧有 2 个出现在同一 Section 正文里"这一偶然条件。
→ 这不是"阈值需要调参"的问题，而是"这条信号与真实的语义风险没有稳定对应关系"。

另外必须强调：**程序只能发现"候选存在，需要进一步判断"，不能因为 picture 最终被判不成立
就认定整道题错误**（任务书 §7 的明确要求）。本轮 R5/R6 的输出都只是"指向进一步检查"，
没有任何"题目有问题"的结论——这一点与要求一致。
```

---

## 5. 正常题反向验证（任务书 §8，不要误杀）

| 检查项 | 结果 |
| --- | --- |
| 正常唯一答案的 vocab_choice | `AIQ:5B4C80443D5F`、`A9D1F3EC6020`、`6721EC6C5D1F` 全部被标 AI_REVIEW_CANDIDATE |
| 正常唯一答案的 reading_choice | `6ECD02B9D381`、`CD8B21681B4C` 未被标；`879007FA4FC7`、`B6463523F9E5` 被标 |
| 干扰项明显不同类型 | 未找到完全符合的样本（现有干扰项都来自同一 Unit 的教材素材） |
| **已经人工确认可用的 ACTIVE 题** | `AIQ:BD59C5958D45` **被标 AI_REVIEW_CANDIDATE**（R3+R4+R5） |

```text
最刺眼的一条：唯一一道已经人工审核通过、处于 ACTIVE 的题，被程序预筛标成"需要 AI 复核"。
按任务书的定义这属于典型的"误杀正常题"信号 ——
预筛无法区分"in the school club 与课文不一致（所以该排除）"与
"with his students 不被课文排除（所以是第二答案）"，因为这两者的差别是语义判断。
```

### 5.1 核心指标：AI 候选率

```text
全部 12 例（10 真实题 + 2 fixture）：9 / 12 = 75.0%
只算真实题库的 10 道选择题：       8 / 10 = **80.0%**

任务书 §8 的判据：如果接近 100%，说明预筛没有节省成本。
80% 意味着：预筛最多只能省掉 2 道题的 AI 调用（20%），
而同时它漏掉了 1 个已知真实风险（FIX-C1）。
→ 这一层当前的净收益为负（省 20% 成本，换来 50% 的已知风险漏检）。
```

---

## 6. AI 候选率与分层收益

| 指标 | 数值 |
| --- | --- |
| 真实选择题总数 | 10 |
| 进入 AI_REVIEW_CANDIDATE | 8（80%） |
| 未进入（NO_AI_SIGNAL） | 2（`6ECD02B9D381`、`CD8B21681B4C`） |
| 已知风险 fixture 命中 | 1 / 2（FIX-C2 中，**FIX-C1 漏**） |
| 已人工通过题被误标 | 1 / 1（`BD59C5958D45`） |
| R1 / R2 的有效触发 | 0 / 0 |

```text
分层本来要达成的效果是"只把真正值得 AI 检查的题送进 AI"。
实测：最多省 20%，却漏 50% 已知风险 → 分层目标未达成。
```

---

## 7. 假阳性 / 漏检风险

```text
假阳性（把正常题标成需要复核）：
  80% 的真实选择题被标；其中 1 道是已人工审核通过的 ACTIVE 题。
  R3/R4（同词性）与 R5（教材来源）是主要来源 —— 它们描述的是"选项结构平行"，
  而"选项结构平行"既不是缺陷，也不能区分真风险，属于结构性假阳性来源。

漏检（真实风险未被标）：
  FIX-C1 漏检。直接原因是答案词性缺失导致 R3/R4 失效 +
  R5 的"≥2 个非答案选项在同一 Section 正文"阈值未达到。

假阴性的深层原因（不是阈值问题）：
  ① 词性覆盖只有 12.7%（P1-09-E 实测）：5/12 例的答案词性未知 → R3/R4 直接失效；
  ② 没有语义资源："爷爷还能和谁一起拉二胡"是开放集合，没有任何正式数据记录；
  ③ 没有可靠答案来源：360/360 正式教材题的 answer_source 都是 NO_RELIABLE_SOURCE；
  ④ R1/R2 只覆盖"选项设计缺陷"（重复、词形对），与"多解风险"不是同一件事。
```

---

## 8. 成本模型（任务书 §9，纯模型估算，未调用 AI）

基准来自 P1-09-F 的**真实实测**：5,152 tokens/题（P1-09-D 为 1,024.7 tokens/题）。

| 方案 | 进入 AI | 100 道选择题的 AI 调用 | tokens | 相对 P1-09-D | 相对全量逐候选 | 预计人工复核量 |
| --- | --- | --- | --- | --- | --- | --- |
| A | 100% | 100 | 515,200 | 5.03× | 1.00× | 100 |
| B | 50% | 50 | 257,600 | 2.51× | 0.50× | 50 |
| C | 30% | 30 | 154,560 | 1.51× | 0.30× | 30 |
| D | 20% | 20 | 103,040 | 1.01× | 0.20× | 20 |

```text
必须说明：这些是模型估算，不是实际成本；而且本轮已经证明：
  ① 想稳定做到 B/C/D 的比例，需要预筛具备判别力 —— 实测没有（80% 命中、且漏 1 个已知风险）；
  ② 即使真的只把 20% 送进 AI，省下的 80% 题里仍然包含未被检出的真风险（FIX-C1 就在被漏的那一半）。
→ 成本模型只能说明"如果预筛有效，省多少"，**不能说明当前能省多少**。
```

---

## 9. `answer_unique` 的产品定位（任务书 §10）

### 方案 1：硬质量门禁（answer_unique 作为 PASS/FAIL 闸门）

```text
需要：可靠的"唯一"判定 → 实测做不到
  · 选择题：P1-09-F 实测 83% 的非当前答案选项被判为有效 → 几乎每道题都会 UNIQUE_RISK
  · 填空题：候选池覆盖不足（P1-09-E）→ 永远达不到 UNIQUE_SUPPORTED 所需条件
后果：要么"几乎全拦"（不可用），要么"为了可通过而放低标准"（违反项目原则）
生命周期影响：会把 PENDING_REVIEW → APPROVED 的门槛绑在一个不具备判别力的信号上
```

### 方案 2：风险检测器（answer_unique 只产出"需要人工看"的信号与证据）

```text
不需要证明唯一，只需要：能发现就标记 + 把证据摆给人工看
实测支持：P1-09-F 证明逐候选协议**能发现**真第二答案（2/2），
          （虽然它几乎对每个候选都判有效 → 作为"检测器"召回可用，作为"门禁"精度不足）
误杀风险：低（不产生自动拒绝）
漏检风险：仍在（FIX-C1 在无 AI 的预筛层漏，需要逐候选 AI 或人工兜底）
成本可控性：高（不进入门禁 → 可以按需/抽样调用）
生命周期影响：完全不改动 PENDING_REVIEW → APPROVED → ACTIVE（继续由人工决定）
```

### 推荐

> **采用方案 2：`answer_unique` = 风险检测器，不是质量门禁。**
>
> 并且明确规定：**"程序没有发现风险" 不得解释为 "答案唯一"**
> （即禁止 `NO_RISK = UNIQUE_CERTIFIED`）。

理由（全部来自实测）：① 精度不足（80% 误标 + 83% 候选被判有效）；
② 召回不完整（FIX-C1 漏检）；③ 唯一性能被"证明"的场景在当前数据结构下只存在于选择题的
选项闭集里，而且即使如此也需要逐候选 AI（5.15×成本）；④ 方案 1 会把这两条缺陷直接变成
产品闸门，代价是"要么全拦、要么放水"。

---

## 10. Fill 单独处理方案（任务书 §11）

P1-09-E 已确认：当前正式数据无法建立"既完整又可控"的填空题候选池。因此：

```text
对 fill：
  不得使用 P1-09-F 的逐候选证明机制
  不得输出 UNIQUE_SUPPORTED
```

### 最终表达方式（推荐）

> **`answer_unique_status = NOT_PROVABLE`**（单一字段、单一值），
> 并在同一条记录里附 `candidate_coverage = NONE`。

为什么选 `NOT_PROVABLE` 而不是 `coverage=PARTIAL + assessment=UNIQUE_UNCERTAIN`：

```text
1. 语义更准确：填空题的问题不是"我们不确定"，而是"我们**无法证明**，且已知无法补齐"。
   UNIQUE_UNCERTAIN 容易被读成"大概没问题"（正是任务书 §12 第 9 条警告的误读风险）。
2. 更防呆：NOT_PROVABLE 在任何代码路径上都不可能被当成"通过条件"；
   而 UNIQUE_UNCERTAIN 允许未来某个实现把它折叠成"非高风险 → 放行"。
3. 与 P1-09-E 的结论一致：填空题的候选池在现有数据下**永远达不到 COMPLETE**，
   所以"无法证明"是结构性事实，不是临时状态。
4. 仍然保留 coverage=NONE 作为技术细节，便于未来数据补齐后升级。
```

人工侧的含义：填空题的唯一性只能靠人工看"这个空是否可能有别的答案"，
不能用任何程序或 AI 结论关闭。

---

## 11. question_library 后续结构建议（任务书 §14，只设计不执行）

任务书列了 4 张候选表。逐条判断"是否真的需要"：

| 候选表 | 是否需要 | 理由 |
| --- | --- | --- |
| `answer_unique_risk_signal` | **不需要** | 预筛本轮被判定 BLOCKED（80% 误标 + 漏检）。把没有判别力的信号入库，等于把噪声写成正式数据 |
| `question_answer_candidate` | **暂不需要** | 选择题的候选就是 `ai_question.options_json` 里已有的选项，单独建表是重复存储；填空题的候选池目前不可能建成 → 没有内容可存 |
| `candidate_review` | **暂不需要（可折叠）** | 逐候选判断只有 3 个 YES/NO + 一句理由。除非逐候选协议被正式采纳，否则不必为它单独建表 |
| `answer_uniqueness_assessment` | **建议保留（1 张表）** | 这是唯一真正需要持久化的东西：某题本次的唯一性判定状态与覆盖度，供人工审核与追溯 |

### 推荐的最小结构（1 张表）

```text
answer_uniqueness_assessment   （append-only）
  question_id · version · run_id · question_type
  status      ∈ { NOT_PROVABLE, UNIQUE_RISK, UNIQUE_UNCERTAIN }   -- 选择题才可能出现后两者
  coverage    ∈ { COMPLETE, PARTIAL, NONE }
  candidate_count · flagged_count
  candidates_json      -- 选项级明细（仅选择题；复用 options 的顺序，不复制题干）
  model · prompt_version · review_context_hash · assessed_at

硬规则：
  1. 不得写入 lifecycle_status；不得产生 question_event
  2. 程序验证结果继续留在 question_validation，AI 判断不得混入
  3. 不建 signal 表、不建 candidate 表（先把机制验证清楚再谈结构）
```

---

## 12. "PASS 但不好用"检查（任务书 §12 的 10 项）

| # | 检查项 | 实测结论 | 等级 |
| --- | --- | --- | --- |
| 1 | 程序预筛过宽 → 几乎所有题进入 AI | **确认**：80% 真实选择题被标 | **BLOCKER** |
| 2 | 程序预筛过窄 → 漏掉 FIX-C1/C2 类风险 | **确认**：FIX-C1 漏检 | **BLOCKER** |
| 3 | 同词性规则造成大量假阳性 | **确认**：R3/R4 触发 6/12，含已通过的 ACTIVE 题 | LIMITATION |
| 4 | "教材出现"规则造成大量假阳性 | **确认**：R5 触发 8/12，是触发面最广的规则 | LIMITATION |
| 5 | 短上下文规则造成大量假阳性 | 影响有限：R7 仅触发 1/12（但它确实标了一道正常 reading 题） | LIMITATION（轻微） |
| 6 | reading_choice 与 vocab_choice 共用一套规则导致失漏 | **确认**：reading 题的答案是短语、无词性 → R3/R4 恒不触发；R5/R6 也不稳定 → 两类题必须分开 | **BLOCKER** |
| 7 | AI 审核后产生大量 UNIQUE_RISK，人工仍无法消化 | **确认（P1-09-F）**：6 个非当前答案候选中 5 个被判有效（83%） | LIMITATION |
| 8 | 风险检测结果被错误当成"题目错误" | **设计风险**：已在本报告与建议中写明"只能指向进一步检查" | 已防护 |
| 9 | 低风险被错误解释为"唯一证明" | **设计风险**：已明确禁止 `NO_RISK = UNIQUE_CERTIFIED` | 已防护 |
| 10 | 填空题被错误纳入选择题机制 | 已在设计上阻断（fill → `NOT_PROVABLE`） | 已防护 |

---

## 13. 最终推荐路线（任务书 §13）

任务书给出的目标架构是：

```text
AI生成 → 程序确定性验证 → 程序风险预筛
          ├─ 低风险 → 正常进入后续质量流程
          └─ AI_REVIEW_CANDIDATE → AI逐候选 → 程序汇总
                        → UNIQUE_RISK / UNIQUE_UNCERTAIN → 人工最终确认
```

**本次审计不支持这个架构的两个关键假设**：

```text
假设 1「程序预筛能分出低风险与高风险」→ 不成立（80% 误标 + FIX-C1 漏检）
假设 2「AI 逐候选的结果有判别力」     → 一半成立：能发现（召回好），但几乎对每个候选都判有效
                                       （精度差，83% 候选被判有效）
```

因此**必须修改架构**（任务书 §13 明确允许并要求这样做）：

```text
AI生成
  → 程序确定性验证（不变）
  → 选择题：不做"风险预筛"分支（因为分不出）
        · 把选项级逐候选判断作为**人工阅读辅助**（可选、不产生闸门结论）
        · 若不使用 AI：人工直接看选项（现有 4 选项，人工看一遍成本很低）
  → 填空题：answer_unique_status = NOT_PROVABLE（结构性，永远）
  → 人工最终确认（生命周期完全不变：PENDING_REVIEW → 人工 → APPROVED → 显式启用 → ACTIVE）
  → 任何"没有发现风险"都不解释为"答案唯一"
```

---

## 14. 下一步（明确建议）

```text
1. 不要实现"程序风险预筛"（本轮 BLOCKED）。
2. 保留 P1-09-F 的逐候选协议作为**可选的人工阅读辅助**，不作为闸门；
   若启用，成本按 5.15×/题 计，并明确标注 UNIQUE_RISK 只表示"需要人工看一眼"。
3. 填空题统一采用 answer_unique_status = NOT_PROVABLE + coverage = NONE。
4. answer_unique 采用"风险检测器"定位（方案 2），并禁止 NO_RISK = UNIQUE_CERTIFIED。
5. 若要让"预筛"真正成立，唯一可行的路径是补数据资源（词性/词形词库、语义或同义资源），
   这属于产品与工程的数据边界决策（是否允许引入外部词库/依赖），不是 Prompt 或规则问题。
6. 结构上建议只保留 1 张 answer_uniqueness_assessment 表（append-only），
   不要先建 signal / candidate / candidate_review 三张表。
```

---

## 15. 保护项

```text
AI 调用 = 0 · DeepSeek = 0 · Ollama = 0
question_library.db / learning.db / contentpack / 教材 PDF / MP3 = 0 修改
V1.3 / V2.0 / 正式 Web / Android = 0 修改 · 未新增依赖 · 未安装软件
未修改正式业务代码 · 未做 schema migration · 未生成正式题目
所有新增产物只写入 audit/AI_question_generation_spike/P1_09_G/
```

数据库只读证据（本轮复核）：

```text
question_library.db 7AA12CA5EB24417BF0AE7E97A8161920B501825D030D69A8E0863272AC695DA7
learning.db         0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91
contentpack v5      65829CA73E41B75ACA010B93B7339EDDF0F666F919148F0F69ED898419700C39
```

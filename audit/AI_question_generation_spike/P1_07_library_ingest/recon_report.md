# P1-07 侦察报告（只读，等待指令）

本阶段：**只读审计 + fixture 定位**。
**未调用任何 AI，未修改任何代码，未修改 question_library.db。**

---

## 0. 侦察结论速览

| 项 | 结果 |
| --- | --- |
| Fixture | P1-06 的 **22 道题**，位于 `audit/AI_question_generation_spike/P1_06_batch_stability/S{1,2,3,4}_parsed.json` |
| 题库现状 | **schema v2**，`generation_run 8 / ai_question 2 / evidence 2 / LO 4 / validation 2 / event 3`，`PENDING_REVIEW 2 / APPROVED 0 / ACTIVE 0` |
| validator v3 只读复算 | **16 PASS / 6 FAIL**（`4_answer_support` ×4、`5_vocab_scope` ×2） |
| 去重键预演（现库 + 批次内） | **0 命中** |
| 去重键反事实（若历史轮次已入库） | **2 命中**（说明该键能捕捉“措辞不同但学习点/答案/证据相同”） |
| LearningObject 映射覆盖率 | 4 个 Section 的 activity **全部**有 exercise LO；答案可映射到词表者 15/22 |
| 初步入库候选（当前口径） | **可直接入库 15 / 暂缓待定 4 / 不可入库 3** |

---

## 1. Fixture 定位

| tag | 文件（相对项目根） | 题数 | SHA256（前 16） |
| --- | --- | --- | --- |
| S1 | `audit\AI_question_generation_spike\P1_06_batch_stability\S1_parsed.json` | 6 | `D4520E288D7651B5` |
| S2 | `…\S2_parsed.json` | 5 | `4F705951CAF743BD` |
| S3 | `…\S3_parsed.json` | 6 | `4F9679CAFF393E6C` |
| S4 | `…\S4_parsed.json` | 5 | `5D1C21032B1C5F4C` |

每题字段（实测）：

```text
question_id（批次内 "q1"…）、type、question、options、correct_option、answer、
unit、section、page、activity、evidence_block_ids[]、evidence_quote、explanation、
difficulty、ai_confidence
```

**注意**：fixture 的 `question_id` 是**批次内序号**（S1–S4 各自从 q1 开始，会重号），
入库时必须重新派生全局 ID（沿用 P1-03 的做法：`AIQ:<fingerprint 前 12 位>`）。

可用于 provenance 的配套文件（同目录）：

| 文件 | 用途 |
| --- | --- |
| `S{1..4}_request.json` | 每 Section 的 system/user prompt SHA256、context SHA256、pages/activity 范围 |
| `S{1..4}_response.json` | 原始响应（含 usage / finish_reason） |
| `p1_06_result.json` | 4 次调用的执行结果与保护项哈希 |
| `p1_06_analysis.json` | 22 题的质量分层（A8/B11/D3）与稳定性观察 |

---

## 2. question_library.db 现状（schema v2）

```text
user_version = 2        integrity_check = ok        foreign_key_check = 空
size = 135,168 B        SHA256 = 3970408E3C0FE341C38EFAA9E5208AB6…（自 P1-05-B 起未变）

generation_run 8   ai_question 2   question_evidence 2
question_learning_object 4   question_validation 2   question_event 3
PENDING_REVIEW 2   APPROVED 0   ACTIVE 0
```

### 已有 2 道题（**不得删除/覆盖/改业务内容**）

| question_id | 类型 | 答案 | section / activity | lifecycle | 备注 |
| --- | --- | --- | --- | --- | --- |
| `AIQ:3179968E3E74` | vocab_choice | polite | U1 UI / A2 | PENDING_REVIEW | `needs_human_review=1` |
| `AIQ:7EBCDBC29563` | fill | sentence | U1 UI / A2 | PENDING_REVIEW | `stale=1 / VALIDATOR_CHANGED`、`needs_human_review=1` |

两者的 `question_validation.validator_version` 均为 **v2**，事件为
`VALIDATED`（GENERATED→PENDING_REVIEW）×2 + `MARKED_STALE` ×1。

### schema v2 的硬门槛（6 个触发器，全部在位）

```text
trg_ai_question_insert_active_forbidden            新题不得以 ACTIVE 插入
trg_ai_question_active_requires_human_approval     转 ACTIVE 必须有 actor_kind='human' 的 REVIEW_APPROVED
trg_ai_question_no_delete                          题目不可删除
trg_question_event_no_update / no_delete           事件表 append-only
trg_validation_exact_trap                          EXACT 命中时强制 needs_human_review=1
```

合法枚举（本阶段不得新增）：

```text
lifecycle_status: GENERATED / VALIDATED / PENDING_REVIEW / APPROVED / ACTIVE / REJECTED / DISABLED
event_type      : GENERATED / VALIDATED / PENDING_REVIEW / REVIEW_APPROVED /
                  REVIEW_REJECTED / ACTIVATED / DISABLED / MARKED_STALE
```

---

## 3. 只读预演结果

### 3.1 validator v3 的 8 项复算（只读，**不是**正式 validator 流程）

```text
16 PASS / 6 FAIL
失败项分布：4_answer_support ×4   ·   5_vocab_scope ×2
```

| 题 | 类型 | 答案 | 失败项 | answer_support | 性质判断 |
| --- | --- | --- | --- | --- | --- |
| S2-Q2 | vocab_choice | mistake | `5_vocab_scope` | EXACT | **工具口径问题**：`student`←`students`、`points`←`point`（Unit 1 词表作 `point out`） |
| S2-Q5 | vocab_choice | sentence | `5_vocab_scope` | EXACT | **工具口径问题**：`writes`←`write`（正文 "Please write this down"） |
| S3-Q2 | fill | leaf | `4_answer_support` | UNSUPPORTED | **真实证据问题**：`evidence_quote` 只截取了空位之前的片段，不含答案词 |
| S3-Q3 | fill | rise | `4_answer_support` | UNSUPPORTED | **真实证据问题**：同上 |
| S3-Q5 | reading_judge | True | `4_answer_support` | UNSUPPORTED | **工具局限**：判断题答案是布尔值，规则 4 结构上不适用 |
| S3-Q6 | reading_judge | False | `4_answer_support` | UNSUPPORTED | **工具局限**：同上 |

> 逐条回查教材 block 后确认：`student`/`students`、`point out`/`points`、`write`/`writes`
> 都能在教材原文中找到出处，**不是教材外词汇**。

### 3.2 去重键预演（任务指定的 deterministic key）

```text
dedupe_key = sha256( section_id \x01 activity_id \x01 question_type
                     \x01 normalized_answer \x01 sorted(evidence_block_ids) )
```

| 比对范围 | 命中 |
| --- | --- |
| 22 道 fixture **内部** | **0** |
| fixture vs **现库 2 道题** | **0** |
| fixture vs **P1-05-D/F/G 历史结果**（反事实：若它们已入库） | **2** |

反事实命中的两处（说明该键确实能捕捉“措辞不同但学习点/答案/证据相同”）：

```text
S1-Q1（sound, fill, P37:B11）      ≡ P1-05-G-Q2
S1-Q5（in the park, reading_choice, P37:B12） ≡ P1-05-F-Q2（亦与 P1-05-D-Q8 同）
```

**一个反向验证**：S1-Q4（`different`, P37:B12, activity 1）与 P1-05-G-Q3（同答案同 block，但 activity 2）
**没有**被判重复 —— 说明把 `activity_id` 纳入键的分量是对的，避免误杀。

### 3.3 LearningObject 映射覆盖率

| tag | Section | 有 exercise LO 的 activity | 答案可映射到词表（首词匹配） |
| --- | --- | --- | --- |
| S1 | Unit 2 UI | 8 / 8 | 4 / 6 |
| S2 | Unit 1 UI | 6 / 6 | 4 / 5 |
| S3 | Unit 5 UI | 7 / 7 | 3 / 6 |
| S4 | Starter GET_READY | 8 / 8 | 4 / 5 |

未映射的答案是多词短语或句子/布尔答案（`in the park`、`fire up instruments`、`In fact`、
`their own rain`、`True`/`False`、`school uniform`）——
其中 `In fact`、`school uniform` 其实是词表短语，用**短语优先匹配**即可映射；
剩下 5 道（句子/布尔答案）只能挂该 activity 的 exercise LO。

### 3.4 P1-06 已有的质量分层（可直接复用，不必重做）

```text
A 8 / B 11 / C 0 / D 3
教材原题复现 2（S3-Q2、S3-Q3）   机械挖空 12   明显低价值 3
```

---

## 4. 初步入库候选分类（**不是最终判定**）

| 类别 | 数量 | 题目 |
| --- | --- | --- |
| **可直接进入 PENDING_REVIEW**（证据完整、validator 无失败、非教材原题） | **15** | S1-Q1..Q6、S2-Q1/Q3/Q4、S3-Q1/Q4、S4-Q1/Q2/Q3/Q5 |
| **暂缓 NEEDS_REVIEW**（工具/口径问题，题目本身未见缺陷） | **4** | S2-Q2、S2-Q5（词形越界假阳性）、S3-Q5、S3-Q6（布尔答案） |
| **不可入库**（证据不完整） | **3** | S3-Q2、S3-Q3（引用不含答案词）、S4-Q4（题干残缺，源 block 碎片化） |
| 其中同时被判 **ORIGINAL_TEXTBOOK** | 2 | S3-Q2、S3-Q3（与教材 a4 填空原题逐字重合） |
| 其中 **MECHANICAL_REPRODUCTION** | 12 | S1-Q1/Q2/Q5、S2-Q1/Q4、S3-Q1/Q2/Q3、S4-Q1/Q2/Q3/Q4 |
| **DUPLICATE_CANDIDATE**（对现库与批次内） | 0 | —（反事实对历史轮次为 2，见 §3.2） |

---

## 5. 需要你先定的 4 个口径（**在我动手前**）

### D1 · 机械复现的 12 道题是否允许入库？

- P1-06 §十二 说：教材原句挖**BOLD 重点词**、答案唯一、对当前学习目标有价值 → **属于合法基础练习**，不要一律判错。
- P1-07 §四.2 说：**“只是把教材原题机械换一种格式，没有形成新的学习价值”的不得作为 AI 新题入库**。

两者需要合成为一个可执行口径，我的建议：

```text
MECHANICAL_REPRODUCTION 仅用于“复现教材练习的空位本身”（例如 S3-Q2/Q3）；
“教材原句挖一个 BOLD 重点词、答案唯一”的题 → 标记 mechanical_rewrite=true，但允许入库，
并在 question_validation.note 里记下该标记。
```

按此口径，12 道机械挖空中只有 S3-Q2/Q3 会被拦住（它们同时是教材原题）。

### D2 · 判断题（reading_judge）的 `answer_support` 怎么算？

规则 4 对布尔答案结构上不适用，S3-Q5/Q6 因此 FAIL。

我的建议：入库判定时对 `reading_judge` **豁免规则 4**，
改为检查“题干陈述与 `evidence_quote` 的事实一致性”（人工或确定性文本比对），
并在 `question_validation.note` 标注 `rule4_waived_for_judge`。
**不修改 validator 代码**（本阶段禁止）。

### D3 · 词形变化导致的 `5_vocab_scope` 误报怎么算？

S2-Q2/Q5 因为 `points`/`writes`/`student` 被判越界，但三者都能在教材原文找到出处。

我的建议：入库判定时对越界 token 做**词形还原后再判**
（`points→point`、`writes→write`、`student→students`），还原后仍在词表/正文中即视为合法；
同样**不修改 validator**，把这条写进入库判定脚本并在报告中标注为口径修正。

### D4 · 题干残缺（S4-Q4）用什么确定性规则识别？

我的建议：采用两条简单规则，命中任一即判 `EVIDENCE_INCOMPLETE`：

```text
① question_text 中含有省略号标记（"…" 或 "..."）
② 或：引用 block 的文本不以句末标点（. ? ! ”）结束，且该 block 被用作题干的主要来源
```

S4-Q4 命中规则 ①（`Oh, don't ___ your ...`）。

---

## 6. 下一步最小实现方案（**待你确认后再动手**）

```text
目录：audit/AI_question_generation_spike/P1_07_library_ingest/

① build_candidates.py（只读）
   22 题 → 过 5 道闸门：
     1 evidence completeness（含 D4 的残缺检测）
     2 textbook-original detection（与教材 package 文本逐字比对）
     3 mechanical reproduction detection（原句挖空标记）
     4 deterministic dedupe（现库 + 批次内；命中记 DUPLICATE_CANDIDATE）
     5 schema/provenance validation（location / quote / type rules + D2/D3 口径）
   输出 candidate_decision.json（每题一条判定与理由），**不写库**

② ingest.py（唯一写库步骤）
   仅对 PASS 候选：insert ai_question(GENERATED) → question_evidence →
   question_learning_object → question_validation →
   event VALIDATED(GENERATED→VALIDATED) → event PENDING_REVIEW(VALIDATED→PENDING_REVIEW) →
   UPDATE lifecycle_status=PENDING_REVIEW
   全程一批次一事务；写入前后对题库做行哈希快照；
   绝不触碰已有 2 道题；绝不产生 ACTIVE / REVIEW_APPROVED

③ verify.py（只读）
   dangling reference、非法 lifecycle、非法 event、题目是否被删除、
   PENDING_REVIEW/APPROVED/ACTIVE 计数、learning.db / contentpack / PDF / MP3 未变

④ 报告：p1_07_report.md + p1_07_audit.json
```

**不新增表、不新增列、不改 validator、不引入 embedding/AI 语义去重。**

---

## 7. 保护状态（侦察阶段）

```text
AI 调用        0
question_library.db  未修改（3970408E…，题目 2 / run 8 / ACTIVE 0 / 事件 3）
learning.db / contentpack / structured/textbook / PDF / 54 MP3 / Web / Android / V1.3 / V2.0  未修改
P1-05-A~G / P1-06 全部既有产物  未修改
```

本轮唯一写入：`audit/AI_question_generation_spike/P1_07_library_ingest/recon.py` 与 `recon_data.json`。

---

## 8. 等待指令

**按你的要求，我先停在这里**：不改代码、不改数据库。
请确认 §5 的 4 个口径（或给出你的口径），我再执行 §6 的最小实现。

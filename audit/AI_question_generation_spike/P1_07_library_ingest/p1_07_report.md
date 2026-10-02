# P1-07 实施报告 · 正式题库入库闭环演练

```text
最终结论      P1-07_PASS
AI 调用       0
fixture        P1-06 的 22 道题（未修改）
入库          19 道 → PENDING_REVIEW
未入库        3 道（EVIDENCE_INCOMPLETE）
ACTIVE        0        APPROVED 0        REVIEW_APPROVED 0
```

---

## 0. 一句话结论

> 22 道候选题经过五道确定性闸门后，**19 道合格题安全进入 `question_library.db` 并停在 `PENDING_REVIEW`**，
> **3 道因证据不完整被拦下**；已有 2 道题与全部正式资产**零改动**。
> 整条链路（教材证据 → 已生成题 → 确定性校验 → 重复检测 → 入库 → PENDING_REVIEW）**成立且可追溯、不可污染学习系统**。

> 说明：本轮任务书在「生命周期」处被截断（原文止于 “新题只能形成：GENERATE”）。
> 该部分按**冻结的 schema v2 与既有各轮一致口径**执行：`GENERATED → VALIDATED → PENDING_REVIEW`，
> 绝不产生 `APPROVED / ACTIVE / REVIEW_APPROVED`。此假设已在执行中验证（见 §3）。

---

## 1. A · 22 道题的判定结果

| 指标 | 数量 |
| --- | --- |
| 总数 | **22** |
| 可入库候选（`PASS`） | **19** |
| evidence 不完整（`EVIDENCE_INCOMPLETE`） | **3** |
| `ORIGINAL_TEXTBOOK`（Gate 2 命中标志） | **2** |
| `MECHANICAL_REPRODUCTION`（Gate 3 拒绝） | **0** |
| `mechanical_rewrite=true`（按 D1 允许入库） | **10** |
| `DUPLICATE_CANDIDATE` | **0** |
| `NEEDS_REVIEW` | **0** |
| `rule4_waived_for_judge`（D2 口径） | **2** |

### 未入库的 3 道（全部 `EVIDENCE_INCOMPLETE`）

| 题目 | 原因 | 派生 ID |
| --- | --- | --- |
| S3-Q2 | `evidence_quote`（`Sunlight and CO2 come into the`）**不含答案词 leaf** → answer_support=UNSUPPORTED；同时与教材 a4 填空原题空位逐字重合（`ORIGINAL_TEXTBOOK`） | `AIQ:021D3AAEEACF` |
| S3-Q3 | `evidence_quote`（`to the leaf through the stem.`）**不含答案词 rise**；同时是教材 a4 原题空位 | `AIQ:433EF984F1BF` |
| S4-Q4 | 题干残缺 `Oh, don't ___ your ...`（D4 规则①：含省略号；规则②：题干尾部与证据块尾部一致且该 block 无句末标点）——根因是 content pack 把该听力练习切成碎片 block | `AIQ:C71824B0D09D` |

> 三道题**均确认不在库中**（按派生 ID 回查为 0）。

### 关于 `ORIGINAL_TEXTBOOK` 与 decision 的关系

S3-Q2 / S3-Q3 **同时**命中 `ORIGINAL_TEXTBOOK` 与 `EVIDENCE_INCOMPLETE`。
decision 记录的是**更强的阻断理由**（证据不完整），`original_textbook` 作为独立字段单独计数，
两者在 `p1_07_audit.json` 中都可见，不存在被掩盖的情况。

---

## 2. B · 正式题库执行前后

| 表 | 执行前 | 执行后 | 变化 |
| --- | --- | --- | --- |
| `generation_run` | 8 | **12** | +4 |
| `ai_question` | 2 | **21** | +19 |
| `question_evidence` | 2 | **22** | +20 |
| `question_learning_object` | 4 | **37** | +33 |
| `question_validation` | 2 | **21** | +19 |
| `question_event` | 3 | **41** | +38 |
| `PENDING_REVIEW` | 2 | **21** | +19 |
| `APPROVED` | 0 | **0** | 0 |
| **`ACTIVE`** | 0 | **0** | **0（重点确认）** |

生命周期分布（执行后）：`PENDING_REVIEW 21`，其余全为 0。
事件分布：`VALIDATED 21`（2 旧 + 19 新）、`PENDING_REVIEW 19`（新）、`MARKED_STALE 1`（旧题，P1-04 遗留）。

### 新增的 4 条 `generation_run`（镜像 P1-06 的真实调用，未伪造）

```text
AIRUN:20260917T201605:P106_S1   U2 UI   q=6   P1-05-v3
AIRUN:20260917T201756:P106_S2   U1 UI   q=5   P1-05-v3
AIRUN:20260917T202038:P106_S3   U5 UI   q=4   P1-05-v3
AIRUN:20260917T202251:P106_S4   Starter q=4   P1-05-v3
```

字段来源：`S{1..4}_request.json`（model / prompt_version / context_hash / max_tokens）、
`S{1..4}_response.json`（usage / latency）、文件 mtime（generated_at）；
`note` 中写明“P1-06 的真实调用，由 P1-07 入库演练回填”。
**`question_count` 记录的是本次实际入库的题数（S3/S4 因有题被拦而不等于原始生成数）。**

---

## 3. C · 数据完整性

```text
integrity_check        ok
foreign_key_check      空
悬空引用               0
非法 lifecycle         0
非法 event_type        0
题目被删除             0
无 evidence / 无 LO / 无 validation / 无事件   均为 0
已有 2 道题            PENDING_REVIEW 未变（含 7EBCDBC29563 的 stale=VALIDATOR_CHANGED 保留）
```

保护项哈希全部匹配基线：

```text
learning.db       0C27267B…CF91   ✔
contentpack       65829CA7…0C39   ✔
validator_v2/v3   7C61585A… / EDB1AA54…   ✔
P1-06 S1–S4 fixture  未修改（哈希与侦察阶段一致）✔
教材 PDF / 54 MP3 / structured/textbook / Web / Android / V1.3 / V2.0   未修改
```

---

## 4. D · 重复检测

**使用的确定性键**（任务指定）：

```text
dedupe_key = sha256( section_id \x01 activity_id \x01 question_type
                     \x01 normalized_answer \x01 sorted(evidence_block_ids) )
另保留 question_fingerprint 用于精确文本重复
```

### 实际结果

| 比对 | 命中 | 是否拦截 |
| --- | --- | --- |
| 22 题**批次内部** | 0 | — |
| fixture vs **现库 2 道题** | 0 | — |

### 该键的有效性证据（侦察阶段的反事实比对）

```text
S1-Q1（sound, fill, P37:B11）              ≡ P1-05-G-Q2   → 若 G 已入库则会被拦
S1-Q5（in the park, reading_choice, B12）  ≡ P1-05-F-Q2   → 同上
```

**反向验证（不误杀）**：S1-Q4 与 P1-05-G-Q3 虽然 **答案相同、evidence block 相同**，
但 `activity_id` 不同（A1 vs A2）→ **未被判为重复**。
这说明把 `activity_id` 纳入键是必要的，也验证了「不要因为仅仅看起来相似就拦截」。

> 因此本批“0 命中”是**真实的 0**，不是检测失效 —— 键本身已在反事实中证明能捕捉措辞不同的同题。

---

## 5. 五道闸门与两个口径的实现方式（可复核）

| 闸门/口径 | 实现 |
| --- | --- |
| **Gate 1 证据完整性** | page ∈ section 页、activity ∈ section 活动、block 存在且 ∈ contentpack、quote 非空且为 block 逐字子串、answer 被引用支持（judge 走 D2）、题干完整（D4） |
| **Gate 2 教材原题** | 题干（去空位）与**同一 activity** 的教材练习文本做「恰好跳过 1 个 token」的严格对齐，且被跳过的 token 是 1–2 位数字（教材编号空位）。<br>（早期版本用 activity 无关的宽松对齐，误把 S2-Q1 判成原题——因为证据包文本是整节拼接；加 activity 约束后修正） |
| **Gate 3 机械复现** | 题干（去空位）是所引 block 的连续片段（允许 ≤3 token 间隔）→ `mechanical_rewrite=true`；**只有**当答案不是明确学习点时才拒绝。本批 10 道标记为机械复写，但答案均为 BOLD 重点词或阅读事实 → 全部允许（符合 D1） |
| **Gate 4 dedupe** | 见 §4 |
| **Gate 5 schema/provenance** | unit_id / activity LO / run 元数据 / model / prompt_version 五项齐备才放行 |
| **D2 reading_judge** | 不走规则 4，改判「题干内容词与 evidence_quote 的事实一致性」：True 需覆盖率 ≥0.75；False 需覆盖率 ≥0.5 且否定词与引用相反。两题 coverage=1.0 |
| **D3 词形归一化** | 越界 token 先做词形还原（`points→point`、`writes→write`、`student→students`）再判；基准用 **contentpack 该 Section 页面的完整正文**（比 context 更完整，见 §6 发现 1） |
| **D4 题干残缺** | ①题干含 `…`/`...`；②题干尾部 token 与所引 block 尾部 token 相同且该 block 无句末标点 |

---

## 6. 本轮发现的问题（分类）

### ① 证据组装问题（重要）

**P1-06 的 S2（Unit 1 · UNDERSTANDING_IDEAS）上下文缺少教材第 17 页（pdf 22）的正文块。**

- 原因：P1-05-B 的 context builder 用「activity 所在页 → section」的映射归属 block，
  而 Unit 1 UI 的 activity 分布在 p16/18/19/20，**p17（课文主体）没有任何 activity**，
  于是该页的 block 全部漏掉；S2 的 context 只有 P21/P23/P24/P25。
- 影响：模型在 S2 只能基于练习页出题，看不到课文主体（P22 是被引用最多的课文页）。
- 本轮处理：**没有修改 P1-05/P1-06 的任何产物**；入库判定时把 D3 的“教材正文基准”
  改用 contentpack 完整正文，使 S2-Q5 的 `writes` 正确判为教材内词形。
- 建议：未来修 context builder 的页归属逻辑（本轮不动）。

### ② 设计问题（schema 口径）

`question_validation.answer_support_type` 的 4 值枚举（EXACT / VERIFIABLE_REFERENCE /
VERIFIABLE_REPHRASE / UNSUPPORTED）**无法表达“判断题的布尔答案被教材事实验证”**，
而 schema 的 CHECK 又要求 PASS 时必须是前三者之一。

本轮做法：按 D2 豁免规则 4，把该字段编码为 `VERIFIABLE_REPHRASE`，
真实依据写入 `checks_json`（`d2_rule4_waived`、`judge_coverage`）与 `note`
（`rule4_waived_for_judge=true`）。**未修改 schema**。
建议未来版本为 judge 题增加独立取值（例如 `JUDGE_FACT_OK`）。

### ③ validator 口径（已知，未改）

`trg_validation_exact_trap` 对选择题必然触发：新入库 19 题中
**8 题被自动置 `needs_human_review=1`**（5 道 vocab_choice + 3 道 reading_choice）。
这与 P1-03/P1-04 记录一致，属既有设计口径；本阶段按要求**未修改 validator**。

### ④ 数据问题（已拦下）

S3-Q2/Q3 的 `evidence_quote` 不含答案词、S4-Q4 的题干残缺 —— 三道都被 Gate 1 拦下，未入库。

**没有发现入库机制问题**：事务、生命周期、事件、硬门槛、已有题保护全部按设计工作。

---

## 7. 产物

| 文件 | 说明 |
| --- | --- |
| `recon.py` / `recon_data.json` / `recon_report.md` | 侦察阶段（上一轮） |
| `build_candidates.py` → `candidate_decision.json` | 只读：22 题 × 五道闸门的逐题判定 |
| `ingest.py` → `ingest_result.json` | 唯一写库步骤（单事务 + 写后核对） |
| `verify.py` → `verify_result.json` | 只读验收 |
| `build_audit.py` → `p1_07_audit.json` | A–E 汇总 |
| `p1_07_report.md` | 本报告 |

**本阶段唯一被修改的正式资产：`structured/ai/question_library.db`（+19 题、+4 run）。**
其余全部只读。

# P1-03 · AI Question 最小生产流水线验证报告

最终状态：**PIPELINE_PASS**

执行日期：2026-09-17
范围：Unit 1 · A new start · `UNDERSTANDING_IDEAS`（复用 P0 已验证上下文）

---

## 0. 结论速览

| 项 | 结果 |
| --- | --- |
| AI 调用次数 | **1**（`deepseek-v4-pro`，无 retry / 无第二模型 / 未用本地 Qwen） |
| 生成题目 | **3** |
| Validator v2 | **2 PASS / 1 FAIL** |
| 入库题目 | **2**（全部 `PENDING_REVIEW`） |
| `ACTIVE` 题目 | **0** |
| `REVIEW_APPROVED` 事件 | **0**（本轮无人工审核） |
| Provenance 完整 | 是（question → run → context_hash → evidence block → 教材） |
| LearningObject 有效 | 是（3 条引用全部命中 contentpack，无 `AIQ:` / `AIRUN:`） |
| 跨库悬空引用 | 0 |
| `learning.db` | **零修改**（SHA256 未变） |
| contentpack / PDF / 54 MP3 / validator v2 | **零修改** |

---

## 1. 建库前只读核对

| 核对项 | 结果 |
| --- | --- |
| `question_library.db` 存在、6 表存在 | 是（P1-02 成果） |
| 正式题库当前题目数 | **0**（P1-03 开始前，脚本内置校验，非空即中止） |
| `learning.db` 未变化 | 是（SHA256 `0C27267B…CF91`） |
| validator v2 未变化 | 是（SHA256 `7C61585A…A683`） |
| P0 的 Unit 1 输入上下文可复用 | 是（SHA256 `471E6FA7…DFA4` 校验通过） |
| 是否需要重新解析 PDF | **不需要**（全程未解析） |

---

## 2. 复用的上下文与提示词（不重新组装）

```text
输入上下文：20260917_1630_deepseek_second_section_8192/input_context.json
            SHA256 = 471E6FA7AA82E03B99E31A43265944D2D8CA98C6924DCB6D38D196474677DFA4
            （与 P0 逐字节一致，脚本内断言校验）

提示词     ：从 20260917_1610_deepseek_second_section/run_second_section.py
            以 AST 原样提取字面量后求值
            system_prompt_sha256 = 32E77851C6AEE69BE3…（与 1630 记录一致）
            user_prompt_sha256   = 8AA866CC9BF8707A…（与 1630 记录一致）
            prompt_version = "P0-v1"（以 SHA256 为权威标识）

教材锚点   ：textbook_id = FLTRP-EN-7A-2022CUR
            snapshot_id = FLTRP-EN-7A-2022CUR:S20260912T151307（is_active = 1）
            unit_id     = FLTRP-EN-7A-2022CUR:U1
            section_id  = FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS
```

校验失败即中止的三道断言全部通过：上下文 SHA 一致、提示词 SHA 一致、题库为空。

---

## 3. 执行顺序（先验证，后入库）

```text
① 创建 generation_run（in-flight，状态先记 API_ERROR）
        ↓
② DeepSeek 调用（1 次）
        ↓
③ 回填 generation_run（status / question_count / usage / finish_reason / latency）
        ↓
④ 解析 AI 输出
        ↓
⑤ Validator v2（8 项确定性校验）
        ↓
⑥ 仅 PASS 题写入 question_library.db
   ├ ai_question      （lifecycle = GENERATED → 随后 PENDING_REVIEW）
   ├ question_evidence
   ├ question_learning_object
   ├ question_validation
   └ question_event   （VALIDATED：GENERATED → PENDING_REVIEW）
```

`generation_run` 在调用**之前**创建：若调用中途失败，该 run 会以 `API_ERROR` 保留，
不会出现“调用发生过但账目缺失”的情况。

---

## 4. A. Generation（召唤账目）

| 项 | 值 |
| --- | --- |
| AI 调用次数 | **1** |
| provider / model | `deepseek` / `deepseek-v4-pro` |
| endpoint | `https://api.deepseek.com/chat/completions` |
| retry | **0** |
| 第二模型 / 本地模型 | 无 / 无 |
| max_tokens | 8192（P0 已验证值） |
| temperature | 0.2 |
| finish_reason | `stop` |
| 生成的 `generation_run` | 1 条：`AIRUN:20260917T1840:P103` |

---

## 5. B. Question（题目账目）

| 项 | 值 |
| --- | --- |
| 生成题目数量 | **3** |
| 入库题目数量 | **2** |
| PASS 数量 | **2** |
| FAIL 数量 | **1** |
| `PENDING_REVIEW` 数量 | **2** |
| 未入库题目 | 1 |
| 未入库原因 | Validator v2 第 5 项 `5_vocab_scope` FAIL：模型把教材外人物 **Mozi** 写进干扰项 |

关键点（对应任务 §13）：`generation_run.question_count = 3`，**失败题没有被从 run 的账目中抹掉**；
题库侧只落 2 道。二者不一致是预期行为，不是数据错误。

---

## 6. C. Provenance（可追溯链）

两道入库题都满足完整链路：

```text
ai_question.question_id
   ↓ generation_run_id  → AIRUN:20260917T1840:P103
   ↓ context_hash       → 471E6FA7…DFA4（= 当时 AI 看到的教材证据快照）
   ↓ evidence_block_id  → FLTRP-EN-7A-2022CUR:P22:B0 / :B2
   ↓                   → 教材 Unit 1 / UNDERSTANDING_IDEAS / activity 2 / 教材第 17 页
```

`snapshot_id = FLTRP-EN-7A-2022CUR:S20260912T151307`（当前 active 快照）。

---

## 7. D. LearningObject（引用有效性）

```text
question_learning_object 引用数 = 3（distinct item_id）
全部命中 contentpack learning_item：3 / 3
悬空引用：0
形如 AIQ: / AIRUN: 的非法引用：0
```

映射规则（确定性，可复核）：

- `fill` / `vocab_choice` → 主对象 = **答案词对应的 vocabulary LearningObject**；
- 全部题型 → 次对象 = **该 activity 的 exercise LearningObject**（`FLTRP-EN-7A-2022CUR:X:0F6BF1CC2913`）。

词汇表映射覆盖率：35 个词表词中 32 个可映射到 contentpack 条目；
未映射的是多词条目 `point out` / `in fact` / `primary school`（不影响本轮，因为答案词不在其中）。

---

## 8. E. Validator（每道入库题都有校验记录）

```text
入库题 2 道 → question_validation 2 行（validator_version = v2）
全部为 PASS，answer_support_type 均为 EXACT
```

`checks_json` 完整保存 8 项结果；`out_of_scope_tokens_json` 均为 `[]`。

---

## 9. F. Lifecycle（无 ACTIVE、无伪造审批）

```text
ACTIVE 题目：0
REVIEW_APPROVED 事件：0
全部入库题：PENDING_REVIEW（active = 0）
```

`question_event` 记录（每题 1 条）：

| event_type | from_status | to_status | actor | actor_kind |
| --- | --- | --- | --- | --- |
| `VALIDATED` | `GENERATED` | `PENDING_REVIEW` | `validator_v2` | `machine` |

> **关于事件类型的说明（如实记录）**
> P1-01/P1-02 冻结的 `event_type` 枚举为
> `VALIDATED / REVIEW_APPROVED / REVIEW_REJECTED / ACTIVATED / DISABLED / MARKED_STALE`，
> **没有** `GENERATED` 或 `PENDING_REVIEW` 两个取值。为遵守“不修改 P1-01/P1-02 已完成设计”，
> 本轮**没有改动 schema**，而是用一条 `VALIDATED` 事件、以
> `from_status='GENERATED' → to_status='PENDING_REVIEW'` 完整表达该状态迁移，
> 并在 `note` 中写明状态链。建议在后续 schema 版本中把这两个取值补进枚举。

---

## 10. G. Reuse / H. Fingerprint

```text
generation_scope_key = 66865B625409F6911F8D428B…（已记录在 generation_run）
  公式：SHA256(section_id, activity_id, prompt_version, context_hash)
  本轮为 Section 级 scope，activity_id 取空值（脚本已注明）
  未来同一 scope 可先查 generation_run，命中即不再调用 AI

question_fingerprint = 7EBCDBC29563D699EA0411EC… / 3179968E3E7400B28A231257…
  两道入库题均有 fingerprint，且全局唯一索引生效
```

---

## 11. §18 真实数据回读（直接从 question_library.db 读出）

| 字段 | 题 A | 题 B |
| --- | --- | --- |
| question_id | `AIQ:7EBCDBC29563` | `AIQ:3179968E3E74` |
| version | 1 | 1 |
| question_type | `fill` | `vocab_choice` |
| question_text | `Our English teacher Ms Chen writes the ___ on the blackboard and says, "Please write this down."` | `"But is it OK to point out the mistake? Is that ___, in the first lesson?"` |
| options | 4 个（`sentence / mistake / polite / meaning`） | 4 个（`polite / dry / important / mistake`） |
| correct_answer | `sentence` | `polite` |
| 教材页 | 17 | 17 |
| evidence quote | `Our English teacher Ms Chen writes the sentence on the blackboard and says, "Please write this down."` | `But is it OK to point out the mistake? Is that polite, in the first lesson?"` |
| evidence block | `FLTRP-EN-7A-2022CUR:P22:B0` | `FLTRP-EN-7A-2022CUR:P22:B2` |
| LearningObject（主） | `FLTRP-EN-7A-2022CUR:V:3571476C132A`（sentence） | `FLTRP-EN-7A-2022CUR:V:813A79C77A94`（polite） |
| LearningObject（次） | `FLTRP-EN-7A-2022CUR:X:0F6BF1CC2913` | `FLTRP-EN-7A-2022CUR:X:0F6BF1CC2913` |
| validation | PASS（v2） | PASS（v2） |
| answer_support_type | `EXACT` | `EXACT` |
| needs_human_review | **1** | **1** |
| lifecycle_status | `PENDING_REVIEW` | `PENDING_REVIEW` |

> 本报告**不引用任何 AI reasoning 内容**；原始响应仅保存在 `raw_response.json` 供审计留档。

### 未入库的第 3 题（如实记录）

```text
type          : reading_choice
question      : What does Wang Han say about the sentence?
fail 项       : 5_vocab_scope
out_of_scope  : ["mozi"]
answer_support: EXACT（答案本身有教材支持）
```

该题答案正确、证据可回溯，但干扰项引入了**教材之外的人物 "Mozi"**。
Validator v2 的词汇边界检查把它拦下，**未进入题库**。
这是本轮最有价值的一条端到端证据：**“教材外知识”确实被确定性地拦住了。**

---

## 12. 本轮发现的三条真实问题（供 P1-04 使用）

### 12.1 `EXACT` 陷阱触发器对选择题过度触发

P1-02 实现的 `trg_validation_exact_trap` 以“答案文本出现在题干或选项中”为触发条件。
对**选择题而言，正确答案本来就在选项里**，因此两道入库题（一道 fill 带选项、一道 vocab_choice）
都被自动置为 `needs_human_review = 1`。

影响评估：

- 方向**保守**（多一次人工复核，不会放过风险题），不构成安全问题；
- 但它会让**所有选择题**都带上人工复核标记，削弱该标记的区分度。

建议（P1-04 处理）：把触发条件从“答案出现在选项中”收窄为
“**选项文本本身出现在教材证据里**”，即判断 `options_json` 的文本是否命中
`evidence_quote`/`question_evidence`，而不是判断答案是否在选项数组中。

### 12.2 `fill` 题携带 options / correct_option

本轮 fill 题由模型自行附带了一个词库（4 个选项）与 `correct_option='A'`。
Validator v2 的题型规则只要求 `fill` 题干含空位，因此**未拦截**。

建议（P1-04 处理）：明确 `fill` 是否允许选项；若不允许，则应在题型规则中拒绝，
或将其归类为 `vocab_choice`。

### 12.3 事件枚举缺少 `GENERATED` / `PENDING_REVIEW`

见第 9 节说明。建议在后续 schema 版本中补齐，使 `question_event` 能逐段记录
`GENERATED → VALIDATED → PENDING_REVIEW` 的完整链条。

---

## 13. §20 成本记录

| 项 | 值 |
| --- | --- |
| model | `deepseek-v4-pro` |
| generation call count | **1** |
| prompt_tokens | 9,451（其中 cache hit 9,344） |
| completion_tokens | 7,332 |
| reasoning_tokens | 6,638 |
| total_tokens | 16,783 |
| latency | **116.6 s**（116,579 ms） |
| finish_reason | `stop` |

未为获取成本信息额外调用任何 AI。

---

## 14. §19 保护项复验（执行后）

| 资产 | 状态 |
| --- | --- |
| `learning.db` | **未修改**：118,784 B，mtime 2026-09-13 15:50:09，SHA256 `0C27267B…CF91` |
| contentpack v5 | **未修改**：2,715,648 B，mtime 2026-09-14 14:37:54，`ai_artifact` = 0 行 |
| 教材 PDF | **未修改**：SHA256 `C732051E91121BC991DBDD01235662629620DF6BFCCBBBD834EAEA6FCECD4F2F` |
| 54 个官方 MP3 | **未修改**：54 / 54 与 `audio_asset.sha256` 完全一致 |
| validator v2 | **未修改**：SHA256 `7C61585A…A683` |
| Web / Android / V1.3 / V2.0 | 未修改 |
| 重新解析 PDF | **否** |
| 本地 Qwen | **未使用** |
| 第二次 AI 调用 | **未发生** |

**本轮被修改的正式资产只有 `question_library.db`（新增 1 run / 2 题及其关系行）。**

---

## 15. §15 / §16 边界确认

- **未进入孩子学习流程**：未修改 `learning.db`、未修改 `learning_record`、未改 Web 学习页面、未改 Android。
  原因：`learning_record` 仍缺少 `source_kind` / `source_ref` / `source_version`，
  因此 AI 题目当前只是**后台待审核学习资源**。
- **前台显示原则**：题库内保留完整技术 provenance，但未来孩子页面**不得显示**
  `model` / `prompt_version` / `context_hash` / `generation_run_id` / `validator_version` /
  `evidence_block_id` / `lifecycle_status` / `question_fingerprint` / 任何内部 ID；
  需要说明来源时只用自然语言，例如「教材第 17 页」。

---

## 16. 本轮产物

| 文件 | 说明 |
| --- | --- |
| `run_pipeline.py` | 流水线脚本（复用上下文+提示词 → 1 次调用 → validator → 入库） |
| `raw_response.json` | 原始 API 响应（含 usage；用于审计留档） |
| `generated_questions.json` | 解析后的原始 AI 输出（未做人工修改） |
| `validation_result.json` | Validator v2 的 8 项逐题结果 |
| `dump_pipeline_audit.py` | 入库后审计导出工具 |
| `p1_03_pipeline_audit.json` | 审计结果（A–H 检查项 + 真实数据回读 + 保护项） |
| `p1_03_pipeline_report.md` | 本报告 |
| `README.md` | 索引 |

结果：**PIPELINE_PASS**

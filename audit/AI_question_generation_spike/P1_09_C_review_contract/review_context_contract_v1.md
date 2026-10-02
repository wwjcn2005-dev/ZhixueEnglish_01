# Review Context Contract V1

状态：**设计冻结建议稿（DESIGN ONLY）**。本轮不实现、不接入、不生成任何正式数据。
适用阶段：P1-09 之后的 AI 英语质量复核。

---

## 0. 这份契约要解决什么

P1-09-B 暴露了一个真实缺陷（问题 A）：

> `AIQ:6ECD02B9D381` 被判 `SUGGEST_REVIEW` + `evidence_concern=true`，
> 理由"题干提到学校艺术节，但所给教材证据句子未提及"。

离线核对（`offline_case_analysis.json`）后的结论是：**这不是模型误判，而是输入给的太少**。

```text
question_evidence.evidence_quote = "I nod to Grandpa and we fire up our instruments."   （48 字符）
证据块 P38:B3 全文           = "5  There is an art festival every autumn in my school.
                                 I decide to take part in it with Grandpa this year.
                                 After a week's practice, we are on the stage.
                                 I nod to Grandpa and we fire up our instruments."      （202 字符）
```

`evidence_quote` 只是**证据块的一段摘录**，而 "art festival" 就在**同一个证据块**里。
全库范围统计：**22 条 evidence 中有 18 条的 quote 短于证据块全文**（`offline_case_analysis.json`
的 `library_scale_of_quote_truncation`）。这说明问题 A 是系统性的，不是个例。

**契约目标：让 AI 看到足以判断题目质量的教材上下文，同时不把程序的验证结论告诉 AI。**

---

## 1. 三层职责（不得混层）

| 层 | 负责方 | 内容 | 是否进入 AI 输入 |
| --- | --- | --- | --- |
| Layer 1 程序事实 | 程序 | 教材范围 / 页码 / Activity / 证据块 / 词汇表 / 正式结构 | **可以**（以"教材原文 + 位置"的形式） |
| Layer 2 AI 质量判断 | AI 复核 | 英语正确性 / 唯一性 / 自然度 / 学习价值 / 干扰项 / 年级适配 | ——（这是 AI 的输出） |
| Layer 3 人工最终确认 | 人类 | 是否进入 `APPROVED`（进而 `ACTIVATED` → `ACTIVE`） | 否 |

**禁止混层的行为**

```text
AI 不得宣布"教材证据不足，所以这道题非法"          → 证据边界由程序判定
AI 不得输出 APPROVED / ACTIVE / lifecycle 相关任何字段
程序不得把自己的 PASS/FAIL 结论当作"提示"塞进 AI 输入（会污染独立复核）
```

**允许并鼓励的行为**

```text
AI 可以看到教材原文（这是判断"题目是否合理""答案是否唯一"的必要条件）
AI 可以判断"题目是否符合教材语境"（这是 Layer 2 的判断，不是 Layer 1 的事实认定）
AI 在上下文确实不足时，只能输出 CONTEXT_INSUFFICIENT —— 不等于 REJECT
```

---

## 2. 必须提供给 AI 的内容

### A. question

```json
{"question_id": "AIQ:...", "question_type": "fill|vocab_choice|reading_choice|reading_judge",
 "question_text": "...", "options": ["..."] | null, "stored_answer": "..."}
```

### B. textbook location（自然语言，不用内部 ID）

```json
{"unit": "Unit 2", "section": "Understanding ideas", "activity": "Activity 1",
 "textbook_page": 32, "pdf_page": 37}
```

### C. textbook context（**不使用单条 quote**）

按题型的最低要求：

| 题型 | 最低教材上下文 |
| --- | --- |
| `reading_choice` / `reading_judge` | 覆盖支持答案的**连续上下文**（默认：证据块全文 + 前后相邻块） |
| `fill` | 能判断语境的**完整句子 / 前后文**（默认：证据块全文；若证据块本身是残句，必须补相邻块） |
| `vocab_choice` | 题目涉及词在教材中的**实际语境**（默认：证据块全文 + 该 Activity 的正文块） |

### D. learning context（可选，必须在正式数据里存在才给）

该题挂载的 LearningObject（词表条目 / 短语 / 句型）与 Activity 的练习对象。
**只给"教材里的学习对象"，不给程序的验证结论。**

---

## 3. 禁止提供给 AI 的内容

```text
validator 的 PASS / FAIL 与 8 项 checks
answer_support_type（EXACT / VERIFIABLE_REFERENCE / VERIFIABLE_REPHRASE / UNSUPPORTED）
gate 结果（EVIDENCE_COMPLETE / ORIGINAL_TEXTBOOK / MECHANICAL_REPRODUCTION / DUPLICATE_CANDIDATE）
mechanical_rewrite / original_textbook 的程序标志
lifecycle_status / active / stale / needs_human_review
生成阶段的 explanation、生成 prompt、生成模型 reasoning、生成时的题量压力
实验人员的对照标签（P1-08-C / P1-09-A / P1-09-B 的 known_issue）
evidence_block_id / question_fingerprint / generation_run_id / context_hash 等内部 ID
```

理由：这些一旦给出，AI 就从"独立看题"退化为"附和程序的结论"，P1-09-B 的独立复核价值会消失。

---

## 4. Minimal / Extended 两级上下文（含实测成本）

### Minimal Review Context（默认）

```text
question（题干 + 选项 + 答案）
+ textbook location（unit / section / activity / 页码，自然语言）
+ 证据块的**完整原文**（不是 evidence_quote 摘录）
+ answer_standard 声明（TEXTBOOK_ANCHORED / SELF_CONTAINED）
```

### Extended Review Context（仅在被程序标记为风险或题型复杂时使用）

```text
= Minimal
+ 该 Activity 的 instruction（教材指令原文）
+ 该 Activity 的全部正文块
+ 证据块前后各 1 个相邻块（因为块可能从句子中间切分）
+ 必要时：整个 Section 的连续正文
```

### 实测成本（10 道 P1-09-B 样本，程序侧离线计算，未调用 AI）

| 方案 | 每题 tokens（估） | 10 题题目部分合计 | 相对 P1-09-B 题目部分 |
| --- | --- | --- | --- |
| P1-09-B 实际（单条摘录） | — | 3,173 字符 ≈ **1,032** | 1.00× |
| **Minimal（证据块全文）** | **169.9** | **1,699** | **1.65×** |
| **Extended（Activity + 相邻块）** | **302.1** | **3,021** | **2.93×** |
| 塞整章（Full Section） | 3,210.3 | 32,103 | **31.1×** |

（tokens 由 P1-09-A 从 4 次真实请求标定的 3.074 chars/token 换算。P1-09-B 的 prompt 合计
2,104 tokens = 题目部分约 1,032 + 固定指令约 1,443；按含指令总量比较，三种方案分别约为
3,142（1.49×）/ 4,464（2.12×）/ 33,546（15.9×）。）

**结论：修掉问题 A 不需要"把整章塞给 AI"。Minimal 的题目部分只涨到 1.65 倍、含指令总量约 1.5 倍；
Extended 约 2.9 倍；而塞整章要涨到约 31 倍（含指令约 16 倍）—— 所以契约明确拒绝"整章输入"作为默认方案。**

### 路由原则（本轮只设计，不实现）

```text
正常题            → Minimal
程序标记风险 / 上下文复杂题 → Extended
```

不做自动路由实现；路由所需的风险信号（如 P1-09-A 的 triage 规则）也还没被验证过。

---

## 5. 上下文不足时的输出（关键新增）

```text
CONTEXT_INSUFFICIENT
```

当 AI 认为"用给我的上下文无法做出可靠判断"时，**只能**输出这个值，并且必须说明缺什么。

```text
CONTEXT_INSUFFICIENT ≠ REJECT
```

理由：上下文不足是**程序侧输入问题**，把输入问题记成题目质量问题是错误的归因。
这一条直接针对 P1-09-B 的 `AIQ:6ECD02B9D381`：在旧契约下它被记成"需要人工复核"，
在新契约下它应该先由 Minimal 上下文修复；若仍不足，则记 `CONTEXT_INSUFFICIENT` 并回传程序侧。

---

## 6. 字段清单（契约形式）

```json
{
  "review_context_version": "RC-v1",
  "answer_standard": "TEXTBOOK_ANCHORED | SELF_CONTAINED",
  "context_level": "MINIMAL | EXTENDED",
  "items": [
    {
      "question_id": "...",
      "question_type": "...",
      "question_text": "...",
      "options": null,
      "stored_answer": "...",
      "textbook_location": {"unit": "...", "section": "...", "activity": "...",
                            "textbook_page": 0, "pdf_page": 0},
      "textbook_context": {
        "evidence_block_full_text": [{"textbook_page": 0, "text": "..."}],
        "activity_instruction": "... | null",
        "activity_blocks": [{"textbook_page": 0, "text": "..."}],
        "neighbour_blocks": [{"textbook_page": 0, "text": "..."}]
      },
      "learning_context": {"learning_objects": ["..."]}
    }
  ]
}
```

**契约禁止字段**（出现即视为契约违规）：

```text
validator_result · checks · answer_support_type · gate_* · mechanical_rewrite
original_textbook · duplicate_key · lifecycle_status · needs_human_review
explanation · prompt_version · generation_run_id · evidence_block_id · known_issue
```

---

## 7. 与现有实现的衔接（只读核对结论）

```text
完整 Section 正文能否由已有正式数据重建？  → 能。
  依据：P1-08-B 的 evidence_assembly.py（section 页码范围 + 按 block_id 去重 + 顺序保证），
  本轮已用它从 contentpack 只读重建了 10 个 Section 的正文（offline_context_probe.json）。
  该模块与正式展示层 web/content.py 的归属规则一致（P1-08-B 已验证）。
证据块全文能否取得？                      → 能。contentpack 的 content_block.text_raw 就是全文。
是否需要修改任何正式数据？                → 不需要。本轮全部只读。
```

---

## 8. 本契约不做什么

```text
不实现 review_context builder
不修改 reviewer_prompt.py
不建 question_ai_review 表、不改 schema
不接入正式审核流程或孩子学习流程
不定义 UI
```

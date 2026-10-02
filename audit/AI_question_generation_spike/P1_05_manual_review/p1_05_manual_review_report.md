# P1-05-E · P1-05-D 生成题目人工质量审阅报告

审阅对象：P1-05-D 单次预算校准产出的 **10 道题**
（Unit 2 · A new start → UNDERSTANDING_IDEAS，`deepseek-v4-pro`，`max_tokens=16384`）

审阅方式：**只读**，逐题对照教材证据
本轮 **AI API 调用 = 0**，未修改任何文件，未写入题库

---

## 0. 一句话结论

> 这 10 道题**没有编造、没有超范围、答案都能落回教材**，说明「教材 → AI 重新组织 → 习题」这条路走得通；
> 但**填空题缺少“根据课文”的语境**，导致 4 道题的答案在语言层面不唯一——
> 这是进入多 Section 实验前**必须先修**的规则问题。

最终建议：**`STOP_AND_FIX`**（修好一条生成规则后再继续，不是否定路线）。

---

## 1. 统计结果

| 指标 | 值 |
| --- | --- |
| total_questions | 10 |
| textbook_basis_pass | 10 / 10 |
| english_pass | 10 / 10 |
| answer_pass | 10 / 10 |
| unique_answer_pass | **6 / 10** |
| learning_value_high | 0 |
| learning_value_medium | 6 |
| learning_value_low | 4 |
| distractor_good | 3（仅 6 道选择题参与评定） |
| distractor_acceptable | 3 |
| distractor_poor | 0 |
| out_of_evidence | **0** |
| duplicate_low_or_below | 4 |
| duplicate_medium_or_high | 6 |
| A_direct_reproduction | 5 |
| B_recombined | 5 |
| C_mechanical_rewrite | 0 |
| D_insufficient_evidence | 0 |
| 可直接使用（无需改动） | **6**（Q5–Q10） |
| 加一行“根据课文”指令后可用 | **4**（Q1–Q4） |

---

## 2. 逐题审阅

| # | 题型 | 教材依据 | 英语 | 答案 | 唯一性 | 学习价值 | 干扰项 | 教材外 | 重复 | 归类 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | fill | PASS | PASS | PASS | **FAIL** | LOW | — | 无 | MEDIUM | A |
| 2 | fill | PASS | PASS | PASS | **FAIL** | LOW | — | 无 | MEDIUM | A |
| 3 | fill | PASS | PASS | PASS | **FAIL** | LOW | — | 无 | MEDIUM | A |
| 4 | fill | PASS | PASS | PASS | **FAIL** | LOW | — | 无 | NONE | A |
| 5 | vocab_choice | PASS | PASS | PASS | PASS | MEDIUM | ACCEPTABLE | 无 | MEDIUM | B |
| 6 | vocab_choice | PASS | PASS | PASS | PASS | MEDIUM | ACCEPTABLE | 无 | NONE | B |
| 7 | vocab_choice | PASS | PASS | PASS | PASS | MEDIUM | ACCEPTABLE | 无 | MEDIUM | B |
| 8 | reading_choice | PASS | PASS | PASS | PASS | MEDIUM | GOOD | 无 | MEDIUM | B |
| 9 | reading_choice | PASS | PASS | PASS | PASS | MEDIUM | GOOD | 无 | NONE | B |
| 10 | reading_choice | PASS | PASS | PASS | PASS | MEDIUM | GOOD | 无 | NONE | A |

### 逐题说明

**Q1** `___ is coming out of my computer.`（答案 Rock music，教材 P37）
教材原句挖去主语。英语与答案都没问题；但题干没有说“根据课文”，
**Music / The music 同样成立**，作为纯语言填空并不唯一。价值 LOW：机械复原。

**Q2** `They sing ___ together.`（答案 Beijing opera，教材 P37）
同上。`They sing songs together.` 也成立 → 不唯一。价值 LOW。

**Q3** `There is an art festival every ___ in my school.`（答案 autumn，教材 P38）
同上。`every year / every term` 也成立 → 不唯一。价值 LOW。

**Q4** `It feels ___ to enjoy our hobby together.`（答案 great，教材 P38）
这是本批最典型的一道“不唯一”题：`good / nice / wonderful` 都自然 → 不唯一。价值 LOW。

**Q5** `As a rock music lover, I play the ___ guitar in the school band.`（答案 electric）
考的是 **electric guitar** 搭配，四个选项都取自本单元词表。价值 MEDIUM：这个搭配值得学。
干扰项 ACCEPTABLE：`different / traditional / magic guitar` 都不自然，偏容易排除。
注意它与 Q1 用的是**同一句教材**（只是挖的词不同）。

**Q6** `An idea ___ hits me: …`（答案 suddenly）
考 `an idea suddenly hits me` 这个固定表达——**教材 Think and share 正好也在解释这个短语**，
所以考查点有教材依据。价值 MEDIUM；干扰项 ACCEPTABLE。

**Q7** `I ___ to take part in it with Grandpa this year.`（答案 decide）
考 `decide to do sth`，是初一核心句型。价值 MEDIUM。
唯一性 PASS，但要注意：`rush` 在语法上说得通（只是语义别扭），
这是本批**最接近“第二答案”**的一处。

**Q8** `Where does Grandpa like playing the erhu?`（答案 In the park）
真正的阅读理解题，需要回课文定位。干扰项 GOOD —— `In the school band` 是很好的陷阱，
因为那是叙述者自己的乐队；`Online` 虽然弱，但 online 确实出现在课文里（share them online），
**没有引入教材外信息**。价值 MEDIUM。

**Q9** `What do the listeners do with our music?`（答案 Everybody moves）
题干里的 "listeners" 不是 AI 自造 —— **教材 Think and share 原文就是**
"'Everybody moves with our music.' How do you think the listeners…"。
干扰项 GOOD：`sings` 与课文的 `They sing Beijing opera together` 形成有效干扰。价值 MEDIUM。

**Q10** `What is the best main idea of the passage?`（答案 C）
考主旨，是真实阅读技能。但必须指出两点：

1. **这道题就是教材第 34 页的原练习**（a3「Choose the best main idea of the passage.」），
   三个选项逐字相同 → 学习增量为零；
2. 本题的 `evidence_quote` **取自教材选项文本本身**，而不是课文陈述 ——
   所谓“有证据”只是因为这句话印在教材选项里。教材并没有提供官方答案
   （`answer_source = NO_RELIABLE_SOURCE`）。
   这正是 P0 记下的 **EXACT 打印风险**首次在真实数据里出现（已标记 `EXACT_PRINT_CITATION`）。

---

## 3. 特别关注：AI 有没有“重新组织”而不是单纯复制？

| 分类 | 数量 | 题目 |
| --- | --- | --- |
| **A. 基本复现教材** | **5** | Q1 Q2 Q3 Q4 Q10 |
| **B. 合理重新组合** | **5** | Q5 Q6 Q7 Q8 Q9 |
| C. 明显机械改写 | 0 | — |
| D. 教材依据不足 | 0 | — |

### 结论

**有重新组织，但只有一半，而且新意集中在两处：**

1. **新增了教材没有的题型**：这个 Section 的教材练习里**根本没有词汇选择题**
   （a1 看图、a2 猜内容、a3 选主旨、a4 填图表、a5 语法、a6/a7 语法填空、a8 写作）。
   Q5–Q7 把教材原句变成“四选一辨析”，属于**在教材基础上新增的练习角度**。
2. **新增了教材没有的细节题**：Q8（爷爷在哪拉二胡）、Q9（听众的反应）都不是教材原题，
   需要学生回课文定位。

但另外 5 道是复现：Q1–Q4 是把教材原句挖一个空（教材 a4 本来就是“从课文选词填图表”，
AI 只是换了句子，没有新增角度）；Q10 直接照搬教材原练习。

> 对初一来说，**教材原句练习本身有必要**（A 类不该越少越好）。
> 问题不在“复现”的存在，而在于**同一批 10 道里有 7 道是同一个操作**（把原句挖一个空），
> 学生连续做下来的学习增量很低。

---

## 4. 必须区分的两件事：机器通过 ≠ 老师认为值得用

本轮**没有依赖任何自动 validator 结论**，所有判断都来自人工对照教材证据。

即便如此，Q1–Q4 依然暴露出：**机器校验可以全绿，但老师一眼就会问“这句是不是只能填这个词？”**
—— 这 4 道题的题干从语法上看并不唯一。

所以本报告特别强调：

> **机器验证通过 ≠ 老师认为值得使用**

---

## 5. 系统性问题（供下一轮修正）

| # | 严重度 | 问题 | 证据 | 影响 | 建议 |
| --- | --- | --- | --- | --- | --- |
| **F1** | **BLOCKER** | 填空题缺少“根据课文”的语境，答案在语言层面不唯一 | Q1–Q4；如 Q4 的 great 可换 good / nice / wonderful | **4/10 道题按现在写法不能安全自动判分** | fill 的题干或题型说明必须带“根据课文原句 / 从课文中选词”，或给出词库。教材原练习 a4 本身就写了 *from the passage*，AI 生成时把这条语境丢了 |
| F2 | IMPROVE | 同批题目操作高度同质 | 7/10 都是“教材原句挖一个空”；3 个 block 各被用两次（P37:B10→Q1/Q5、P37:B12→Q2/Q8、P38:B3→Q3/Q7） | 学生连续遇到同一句式 | 限制同一 Section 内“原句挖空”的数量，并要求覆盖不同考查点 |
| F3 | IMPROVE | EXACT 引用的循环风险真实出现 | Q10 的 evidence_quote 就是教材选项文本本身 | “有证据”只是因为它印在教材选项里 | P1-04 已把这类情况标 `needs_human_review=1`；正式实验应把这类题单列 |
| F4 | OBSERVE | 一道题直接照搬教材原练习 | Q10 = 教材 P34 a3，三个选项逐字相同 | 学习增量为零 | 生成时排除与教材原题逐字重合的题，或明确允许的复现比例 |

---

## 6. 最终结论（只回答三个问题）

### 问题 1：这 10 道题里，有多少道老师可以**直接**给初一学生做？

**6 道可以直接用（Q5–Q10）**，另外 **4 道加一行指令后可用（Q1–Q4）**。

| 题 | 依据 |
| --- | --- |
| Q5 | 用教材原句考 electric guitar 搭配；选项由 AI 组织，答案唯一 |
| Q6 | 考 an idea suddenly hits me，教材 Think and share 正好解释该短语；答案唯一 |
| Q7 | 考 decide to do sth；enjoy/nod 不合语法、rush 语义不自然，最自然答案唯一 |
| Q8 | 阅读信息定位，课文直接给出 in the park；陷阱项来自课文语境 |
| Q9 | 阅读细节，题干用词来自教材 Think and share；课文直接给出 moves |
| Q10 | 主旨题，答案与课文一致（但它是教材原题，学习增量为零） |
| Q1–Q4 | 内容正确、答案能落回教材，**但题干未说明“根据课文”，答案在语言层面不唯一**，需补一行指令 |

### 问题 2：AI 是否已经表现出“从教材中重新组织练习”，而不是单纯复制？

**部分具备，证据有限（5/10）。**

举证：

- 该 Section 教材**没有词汇选择题**，Q5–Q7 在这个句式上新增了“四选一辨析”的角度
  （Q5 考搭配、Q6 考固定表达、Q7 考 decide to do 结构）；
- Q8、Q9 是教材原题里没有的**细节定位题**（爷爷在哪拉二胡、听众的反应）。

同时必须承认另一半：Q1–Q4 只是把原句挖空，Q10 直接照搬教材 P34 的原练习。

### 问题 3：下一阶段是否值得继续做多 Section 实验？

```text
STOP_AND_FIX
```

**理由**：样本本身没有任何编造、没有超范围、答案都能落回教材，说明路线可用；
但 **F1 是必须先修的生成规则问题** —— 填空题缺“根据课文”语境会让约 40% 的产出在自动判分时出错。
在修好 F1（并顺带处理 F2–F4）之前就开跑 7 个 Section，只会把同一个缺陷复制 7 遍。

> 这里的 `STOP_AND_FIX` **不是否定路线**，而是“先补一条规则，再继续验证”。

---

## 7. 保护项确认

| 资产 | 状态 |
| --- | --- |
| AI API 调用 | **0** |
| `question_library.db` | 未修改（`3970408E…`，无新 `generation_run`、无 `AIQ:*`） |
| `learning.db` | 未修改 |
| contentpack | 未修改 |
| validator v2 / v3 | 未修改 |
| P1-05-A/B/C/D 产物 | 未修改 |
| P1-05-v1 | 未修改 |
| 教材 PDF / 54 个 MP3 | 未修改 |
| Web / Android / V1.3 / V2.0 | 未修改 |

本轮唯一写入位置：`audit/AI_question_generation_spike/P1_05_manual_review/`。

---

## 8. 产物

| 文件 | 说明 |
| --- | --- |
| `README.md` | 索引 |
| `p1_05_manual_review_report.md` | 本报告 |
| `p1_05_manual_review.json` | 逐题审阅结构化记录 + 统计 + 系统性问题 + 三问结论 |
| `build_review.py` | 审阅记录生成脚本（只读） |

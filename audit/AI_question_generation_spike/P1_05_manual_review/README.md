# P1-05-E · P1-05-D 生成题目人工质量审阅

对 P1-05-D 单次预算校准（`max_tokens=16384`）产出的 **10 道题**做只读人工审阅。

```text
AI API 调用   0
写入题库       无（无 generation_run、无 AIQ:*）
修改文件       无（本轮唯一写入位置是本目录）
```

---

## 一句话结论

> 10 道题**没有编造、没有超范围、答案都能落回教材**，路线走得通；
> 但**填空题缺少“根据课文”的语境**，4 道题的答案在语言层面不唯一。

最终建议：**`STOP_AND_FIX`** —— 不是否定路线，而是先补一条生成规则，再继续多 Section 实验。

---

## 统计

```text
total_questions              10
textbook_basis_pass          10 / 10
english_pass                 10 / 10
answer_pass                  10 / 10
unique_answer_pass            6 / 10        ← Q1–Q4 不唯一

learning_value_high           0
learning_value_medium         6
learning_value_low            4

distractor_good               3
distractor_acceptable         3
distractor_poor               0

out_of_evidence               0

duplicate_low_or_below        4
duplicate_medium_or_high      6

A_direct_reproduction         5   (Q1 Q2 Q3 Q4 Q10)
B_recombined                  5   (Q5 Q6 Q7 Q8 Q9)
C_mechanical_rewrite          0
D_insufficient_evidence       0
```

---

## 三个问题的回答

### 1. 可以直接给初一学生做的：**6 道**（Q5–Q10）

另 4 道（Q1–Q4）内容正确、答案能落回教材，但**题干缺少“根据课文”**，
补一行指令后即可使用。

### 2. AI 是否在“重新组织”而不是单纯复制？

**部分具备，证据有限（5/10）。**

- 该 Section 教材**没有词汇选择题**；Q5–Q7 新增了“四选一辨析”的角度
  （考搭配 / 固定表达 / decide to do 结构）。
- Q8、Q9 是教材原题里没有的**细节定位题**。
- 另外 5 道（Q1–Q4、Q10）是原句复原或教材原练习照搬。

### 3. 下一步

```text
STOP_AND_FIX
```

理由：**F1（填空题缺“根据课文”语境）必须先修**，否则约 40% 的产出不能安全自动判分，
开跑 7 个 Section 只会把同一缺陷复制 7 遍。

---

## 三个系统性发现

| # | 严重度 | 问题 |
| --- | --- | --- |
| **F1** | **BLOCKER** | 填空题缺“根据课文”语境 → Q1–Q4 答案在语言层面不唯一（great 可换 good/nice/wonderful） |
| F2 | IMPROVE | 7/10 是同一个操作（原句挖空）；3 个 block 各被两道题复用 |
| F3 | IMPROVE | Q10 的 `evidence_quote` 取自教材选项文本本身 → EXACT 打印的循环引用首次真实出现 |
| F4 | OBSERVE | Q10 与教材 P34 a3 逐字相同（学习增量为零） |

---

## 本轮特别强调

> **机器验证通过 ≠ 老师认为值得使用。**

本轮没有依赖任何自动 validator 结论；即便如此，Q1–Q4 仍会被老师一眼指出“这句不是只能填这个词”。

---

## 产物

| 文件 | 说明 |
| --- | --- |
| `README.md` | 本索引 |
| `p1_05_manual_review_report.md` | 完整审阅报告（逐题 + 统计 + 系统性问题 + 三问结论） |
| `p1_05_manual_review.json` | 逐题结构化审阅记录与统计 |
| `build_review.py` | 审阅记录生成脚本（只读） |

审阅对象来源：`P1_05_budget_calibration_v2/calibration_parsed.json`（SHA256 记录在 JSON 中）。

# Answer Uniqueness Contract V1

状态：**设计冻结建议稿（DESIGN ONLY）**。本轮不实现、不调用 AI、不修改任何数据。

---

## 0. 为什么需要把"答案唯一性"单独冻结

P1-09-A / P1-09-B 出现过一次真实的标签争议：

```text
AIQ:B6463523F9E5  "In the Great Bear Rainforest, what can the trees make?"
                  选项 their own rain / sugar / oxygen / food，答案 their own rain
P1-09-A 标签：干扰项风险（sugar、oxygen、food 在现实世界里对树木同样成立）
P1-09-B AI ：SUGGEST_ACCEPT + answer_unique=PASS + distractor_quality=PASS
```

一方按"课文陈述"判，一方按"现实常识"判，两者都自洽 → **统计 false positive / false negative 失去共同基准**。
本契约的作用就是把这个基准固定下来。

---

## 1. 两种作答标准（必须先声明）

| 标准 | 含义 | 典型场景 |
| --- | --- | --- |
| `TEXTBOOK_ANCHORED`（教材锚定，V1 默认） | 学生做题时**手上有教材原文 / 该活动的课文**；判断唯一性时以"教材语境 + 题干 + 选项"为准 | 随堂练习、课文后练习、阅读理解 |
| `SELF_CONTAINED`（自立） | 学生只看到题目本身；判断唯一性时**只依据题干 + 选项** | 脱离课文的独立小测 |

契约要求：**每个题目必须声明采用哪一个标准**（`answer_standard` 字段）。
未声明时默认 `TEXTBOOK_ANCHORED`。

同时，对 `fill` 与 `vocab_choice` 额外强制输出一个字段：

```text
standalone_risk: true | false
```

含义：把该题当作自立练习时，是否出现第二个合理答案。**这个字段不影响 `answer_unique` 的判定，
但必须如实保留** —— 它正是 P1-09-B 里"该题无上下文"这条信号的正确位置。

---

## 2. 四类判定（必须区分，不得合并）

| 类别 | 定义 | 是否属于唯一性问题 |
| --- | --- | --- |
| **A 教材语境唯一** | 在题目给出的教材语境、题干、选项范围内，只有一个答案合理 | 是（结论：`UNIQUE`） |
| **B 现实常识存在其他解释** | 现实世界可能存在其他答案 | **不是**。明确不得用它判定教材训练题答案不唯一（记 `NOT_A_UNIQUENESS_ISSUE`，相关顾虑交给干扰项 / 年级维度） |
| **C 语言层面存在其他合理解答** | 不依赖现实常识，另一个词/选项**语法成立 + 语义成立 + 不与教材语境冲突** | 是（结论：`UNIQUE_RISK`） |
| **D 信息不足** | 题目本身缺少足够上下文（没有指标物 / 限定语 / 指代不明），导致多个答案都成立 | 是（结论：`UNIQUE_RISK`），**不能简单标成"现实常识问题"** |

---

## 3. 判定程序（确定性，可复现）

```text
第 1 步  确认 answer_standard 与 context_level（来自 Review Context Contract V1）
第 2 步  拿掉原答案，穷举候选：
           - fill        → 教材语境允许的其他词（含同义/近义表达）
           - 选择题       → 其余选项 + 明显未列入选项但同样成立的表达
第 3 步  对每个候选判断是否"被排除"：

          被排除  ⟺  语法不成立  ∨  语义不成立  ∨  与教材原文陈述冲突

          ★ 教材锚定标准下，"与教材原文陈述冲突"是合法的排除条件
            （例：课文写 in the school band，选项 club 与原文冲突 → 排除）
          ★ 但"教材里恰好出现某个答案"**不能**作为通过理由
第 4 步  若题干缺少必要指标物 / 限定语（指代不明）→ 直接判 D 类
第 5 步  汇总：
           - 全部候选被排除、且 A 成立            → UNIQUE
           - 存在未被排除的候选（C 或 D）          → UNIQUE_RISK
           - 只有"现实常识"层面的候选（B）         → NOT_A_UNIQUENESS_ISSUE（唯一性判 UNIQUE）
           - 用给的上下文无法可靠判断              → CONTEXT_INSUFFICIENT
第 6 步  对 fill / vocab_choice 另外输出 standalone_risk（按 SELF_CONTAINED 标准再走一遍）
```

---

## 4. 四种输出的含义与使用边界

| 输出 | 含义 | 允许的后续动作 |
| --- | --- | --- |
| `UNIQUE` | 按声明标准只有一个合理答案 | 唯一性维度不构成障碍（不代表题目没有其它问题） |
| `UNIQUE_RISK` | 存在未被排除的第二合理答案 | 进入人工复核信息；**不得自动改写题目或自动驳回** |
| `CONTEXT_INSUFFICIENT` | 上下文不足以判断 | 回传程序侧补齐上下文；**不等于 REJECT** |
| `NOT_A_UNIQUENESS_ISSUE` | 争议点不属于唯一性（如现实常识层面） | 转交对应维度（干扰项 / 年级）处理 |

---

## 5. 典型误判风险（写进契约，防止再次跑偏）

```text
✗ 因为"答案在教材里出现过"就判 UNIQUE
   → 出现只证明"可能"，不证明"唯一"

✗ 因为"现实世界还有别的解释"就判 UNIQUE_RISK
   → 这是 B 类，明确排除在唯一性之外（否则阅读题永远无法通过）

✗ 把"题目缺少上下文"记成"现实常识问题"
   → 这是 D 类，必须如实记为 UNIQUE_RISK

✗ 用 SELF_CONTAINED 结论去否定 TEXTBOOK_ANCHORED 下已经审核通过的题
   → 两个标准的结论要分别记录，不得互相替代
```

---

## 6. 对既有真实案例的离线重判（分析人员判断，不是 AI 结果）

依据 `offline_case_analysis.json`：

| question_id | 题型 | 旧标签（P1-09-A/B） | Contract V1 判定 | 说明 |
| --- | --- | --- | --- | --- |
| `AIQ:B6463523F9E5` | reading_choice | 干扰项风险（现实常识） | **UNIQUE** | 题干明确指向课文 → 按课文陈述判；其余选项在课文中无陈述支持。旧标签重映射为 `NOT_A_UNIQUENESS_ISSUE`（B 类） |
| `AIQ:1B3AF72923C4` | fill | 已确认问题（人工驳回 + 不唯一） | **UNIQUE_RISK** | D 类：题干只有 "I am ___, too."，无指标物；happy / fine 与语境不冲突 |
| `AIQ:120FFEECA78F` | fill | 答案唯一性风险 | **UNIQUE_RISK** | D 类：证据块自身仅 10 字符，无指标物 |
| `AIQ:1BA260727793` | fill | 低学习价值 + 机械 | **UNIQUE_RISK** | C 类：`By the way` 等同样成立 |
| `AIQ:75AAEBFE06DF` | vocab_choice | 干扰项风险 | **UNIQUE_RISK** | C 类：`traditional` 语法语义成立、且不与课文冲突 |
| `AIQ:BD59C5958D45` | vocab_choice | 已知正常（人工审核通过，ACTIVE） | **UNIQUE**（`standalone_risk=true`） | club 与课文 "in the school band" 冲突 → 排除；但自立标准下 club 成立，如实记入 `standalone_risk` |
| `AIQ:04CC9B1CF690` | fill | 已知正常 | **UNIQUE**（`standalone_risk=true`） | 题干限定语充分（our hobby together） |
| `AIQ:6ECD02B9D381` / `AIQ:879007FA4FC7` | reading_choice | 已知正常 | N/A（阅读题按课文判） | 不属于唯一性争议 |
| `AIQ:7EAC0ED29A0A` | reading_judge | 已知正常 | N/A（判断题） | True/False 由课文事实决定 |

### 6.1 这次重判解决了什么

```text
1. AIQ:B6463523F9E5 的标签争议被消除：
   "现实常识存在其他解释" 被契约明确排除在唯一性之外（B 类）→ 唯一性判定为 UNIQUE。

2. P1-09-B 的 1 条 FALSE_NEGATIVE 因此被重新归因：
   它不是模型漏检，而是**旧标签口径**造成的。P1-09-B 的历史记录保持原样（不追改），
   但在新契约下这条题不再构成失败案例。

3. 同时保住了人工审核的 ACTIVE 结论：
   AIQ:BD59C5958D45 在教材锚定标准下仍判 UNIQUE；它脱离课文的隐患被
   单独记入 standalone_risk，而不是被当成"答案不唯一"。
```

---

## 7. 本契约不做什么

```text
不修改 question_evidence / evidence_quote 的任何字段
不把 UNIQUE_RISK 直接变成 REJECT，不自动改题、不自动改生命周期
不引入 AI 语义去重、不引入 embedding
不实现 REVIEW 判定程序（本文件只是契约）
```

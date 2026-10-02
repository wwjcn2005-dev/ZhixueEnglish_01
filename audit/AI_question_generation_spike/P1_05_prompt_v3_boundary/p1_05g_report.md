# P1-05-G 实施报告 · P1-05-v3（恢复合理 Fill + 收紧教材素材边界）

最终状态：**P1_05_G_PASS**

样本：Unit 2 · A new start · `UNDERSTANDING_IDEAS`（与 P1-05-D / F **逐字节相同**的 evidence/context）
新提示词版本：**`P1-05-v3`**（`P1-05-v1` / `P1-05-v2` 均未修改）
真实 AI 调用：**1 次**，`retry_count = 0`

---

## 0. 结论速览

| 项 | 值 |
| --- | --- |
| API 调用次数 | **1**（无 retry、无第二次） |
| finish_reason | **`stop`** |
| 生成题数 | **8** |
| prompt / completion / reasoning tokens | 11,387 / 9,997 / **8,426** |
| total_tokens | 21,384 |
| latency | 139.9 s |
| guard | `PROCEED` |
| 写入 `question_library.db` | **否** |
| 正式资产 | **0 修改**（75 个受保护文件 before/after 哈希全部一致，`changed = []`） |

### 三个判断的结论

| | 判断 | 结论 |
| --- | --- | --- |
| **A** | 是否恢复合理词汇填空、且没回到"机械挖空" | **部分恢复**：词汇锚定做到了（4/4 BOLD），但 4/4 填空语境仍是教材原句直接挖空 |
| **B** | 收紧素材边界后是否明显减少教材外词汇 | **是**：教材外题从 F 的 6/7 降到 1/8，**真正教材外词汇 = 0**；元语言题干也消失 |
| **C** | 核心规则能否作为批量生成的基础 | **可以作为基础**，但有两处需要收口（fill 语境、跨轮重复） |

---

## 1. `P1-05-v3` 相对 `P1-05-v2` 的两处修正

### 修正 1 · 恢复合理的 Fill

把 v2 中把 fill 逼死的措辞整体替换为：

```text
- fill: a WELCOME and EXPECTED question type - do generate fills whenever a suitable
  learning point exists. A good fill blanks a word that the Unit vocabulary list teaches
  (unit_vocabulary, BOLD core words first), or the core word of a textbook key phrase /
  key expression. The sentence around the blank must be textbook-based context that makes
  the answer unique. You MAY reorganise that context; you do NOT have to copy a textbook
  sentence word for word. Do NOT pick an arbitrary ordinary word out of the passage just
  to produce a fill. A fill exists to practise a textbook key word in a context that has
  exactly ONE determinable answer - it is not simply "delete one word from a textbook
  sentence". If no learning point supports a reliable, unique fill, do not force one.
```

### 修正 2 · 教材素材边界 + 去元语言

新增两段（插在 `ANTI-DUPLICATION` 之前）：

```text
TEXTBOOK MATERIAL BOUNDARY (hard):
  题目中出现的每一处英语都必须来自本 Unit 提供的教材素材：
    · 正确答案　· 每一个干扰项　· 题干中的实质性英语词汇　· 被考查的短语/表达
  选择题干扰项优先取自 unit_vocabulary（BOLD 优先，或本单元其它可能混淆的词）。
  无法追溯到 unit_vocabulary、教材正文或教材重点表达的英语词，一律不得使用。

NO META-LANGUAGE IN THE QUESTION TEXT:
  题干就是孩子看到的内容，禁止写入 AI 出题说明性语言（如 "Choose the best word to
  complete the sentence:"、"Fill in the blank:"、"Complete the sentence:"）。
  fill 直接给带 ___ 的句子；choice 直接给问题与选项。
  题型信息属于结构化 "type" 字段，不进入孩子可见文本。
```

其余全部保持不变：教材学习点优先的核心原则、10 条硬规则、JSON schema、
anti-duplication 三条、题量不设配额。

### 单变量纪律

与 P1-05-F 逐字段比对：**唯一差异是 `messages[0]`（system prompt）**，
context 逐字节相同，model / temperature / max_tokens(16384) / thinking / reasoning_effort(low) 全部不变。

---

## 2. 八道题

| # | 题型 | 答案 | 教材学习点 | evidence | 词汇表 | BOLD | 唯一 | 原句挖空 | 重新组合 | 价值 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | fill | guitar | electric guitar 搭配 | P37:B10 | ✔ | ✔ | ✔ | 是 | 否 | MEDIUM |
| 2 | fill | sound | a5 语法聚焦例句 | P37:B11 | ✔ | ✔ | ✔ | 是 | 否 | MEDIUM |
| 3 | fill | different | BOLD 重点词 | P37:B12 | ✔ | ✔ | **风险** | 是 | 否 | MEDIUM |
| 4 | fill | practice | BOLD 重点词 | P38:B3 | ✔ | ✔ | ✔ | 是 | 否 | MEDIUM |
| 5 | vocab_choice | decide | decide to do 结构 | P38:B3 | ✔ | ✔ | ✔ | 否 | **是** | MEDIUM |
| 6 | reading_choice | Playing the erhu and singing Beijing opera | 课文重要事实（合并两句） | P37:B12 | — | — | ✔ | 否 | **是** | MEDIUM |
| 7 | reading_choice | They fire up their instruments | 重点表达 fire up our instruments | P38:B3 | ✔ | ✔ | ✔ | 否 | **是** | MEDIUM |
| 8 | reading_judge | True | 课文重要事实 | P38:B5 | — | — | ✔ | 题干即原句 | 否 | **LOW** |

### 逐题要点

- **Q1–Q4（fill）**：答案全部是 **Unit 词汇表的 BOLD 重点词**（guitar / sound / different / practice），
  这正是一开始想要的效果。但四道题的**语境都是教材原句直接挖空**，没有重新组织。
- **Q3 唯一性风险**：`But it's a ___ kind of music.` → `different`；而 `traditional` 同为 BOLD 词，
  `a traditional kind of music` 在语言上同样成立。这是本轮唯一一处答案不唯一。
- **Q5**：语境被重组（`in it` → `the school art festival`），三个选项 decide / practice / enjoy **全部是 BOLD 词**。
- **Q6**：把 block B12 的两个事实（公园拉二胡 + 一起唱京剧）合并成一道理解题，三个选项全部来自课文。
- **Q7**：用重点表达 `fire up our instruments` 出理解题；与教材 a4 图表考同一句，但**题型与考法不同**，
  因此不计为原题复现。
- **Q8**：题干就是教材原句本身，判 True 过于直接，学习增量低 → 唯一一道 LOW。

---

## 3. 关键统计

```text
Fill 数量                    4
Fill 中词汇表答案数量          4 / 4
Fill 中 BOLD 答案数量          4 / 4
答案唯一率                    7 / 8
教材素材合法率                 8 / 8
教材外词汇数量（token）        3（doing / sharing / writing —— 均为词表内词的 -ing 形式，属检查器假阳性）
真正教材外词汇数量             0
真正重新组合数量               3 / 8
机械挖空数量                  4 / 8
教材原题复现数量               0
低价值题数量                  1（Q8）
```

---

## 4. 与 P1-05-F 对比（并列出 P1-05-D 作参照）

| 指标 | P1-05-D（v1，10 题） | P1-05-F（v2，7 题） | **P1-05-G（v3，8 题）** |
| --- | --- | --- | --- |
| fill 数量 | 4 | **0** | **4** |
| fill 词汇表答案 | 1/4 | —（无 fill） | **4/4** |
| fill BOLD 答案 | 0/4 | —（无 fill） | **4/4** |
| 答案唯一 | 6/10 | 7/7 | **7/8** |
| 教材外词汇题数 | 2/10 | **6/7** | **1/8** |
| 教材外词汇 token | 4 | 9 | **3（全部为词形变化假阳性 → 真正 0）** |
| 真正重新组合 | 5/10 | 6/7 | **3/8** |
| 原句机械挖空 | 7/10 | 3/7 | **4/8** |
| 教材原题复现 | 1 | 1 | **0** |
| 低价值题 | 4 | 1 | **1** |

### 三条最说明问题的变化

1. **fill 回来了，而且词汇锚定**：0 → 4，且 4/4 是 BOLD 重点词（D 只有 0/4）。
2. **教材外词汇几乎清零**：F 的 violin / piano / alone / performance 全部消失；G 唯一被检查器标出的
   三个 token 都是词表内词（do / share / write）的 -ing 形式。
3. **重新组合率反而下降**：6/7 → 3/8。原因是恢复 fill 之后，4 道填空全部采用"教材原句直接挖空"的形态。

> 注：教材外词汇用 `validator_v3.out_of_scope()` **只读复算**得到，本轮没有跑正式 validator 流程。

---

## 5. 三个最终判断

### A · v3 是否恢复了合理的词汇填空，同时没有回到 P1-05-D 的"机械挖空"问题？

**部分恢复：词汇锚定做到了，语境重组没有做到。**

- 恢复：fill 从 F 的 0 道回到 4 道；**4/4 答案来自 Unit 词汇表且 4/4 是 BOLD 重点词**
  （P1-05-D 为 1/4 词表、0/4 BOLD）。
- 未完全达到意图：**4/4 的填空语境都是教材原句直接挖空**，"把教材原句挖掉一个词"这个形态仍然存在；
  与 D 的差别在于挖的是 **BOLD 重点词**，而不是从正文随手挑普通词（D 的 autumn / great / Rock music 那类）。
- 另有一处唯一性风险：Q3 的 `different` 与同为 BOLD 词的 `traditional` 都说得通（1/8）。

### B · 收紧教材素材边界后，是否明显减少教材外英语词汇？

**是，非常明显。**

- 教材外词汇：D 2/10（4 token）→ F **6/7（9 token）**→ G **1/8（3 token）**；
- G 的 3 个 token（doing / sharing / writing）都是词表内词 do / share / write 的 -ing 形式，
  属于检查器不做词形还原导致的**假阳性**；**真正教材外的词汇 = 0**；
- F 中出现的 violin / piano / alone / performance 在 G 中全部消失；
- F 的元语言题干（`Choose the best word to complete the sentence:`）也未再出现，
  8 道题的题干都是直接表述。

### C · 目前这套核心规则是否已经可以作为后续批量生成的基础规则？

**可以作为基础规则，但有两处需要收口。**

支持的理由：教材学习点命中 8/8；答案唯一 7/8；真正教材外词汇 0；教材原题复现 0；
fill 恢复正常且 4/4 词汇锚定；元语言问题解决。

仍需收口的点：

1. **fill 的语境仍是原句照搬（4/4）**，与"用教材重点词做语境练习"的意图只对上了一半；
2. **fill 的同义替换风险没有结构性解决**（Q3 的 different / traditional 都说得通）——
   这需要实现层面的收口（例如限定"只能从本单元词表中选"或改为带词库的填空），不是再加一条提示词规则；
3. **跨轮重复明显**：8 道题中 4 道与 P1-05-D / F 的答案与 evidence block 完全相同
   （G-Q2≡F-Q7、G-Q4≡F-Q5、G-Q5≡D-Q7、G-Q8≡F-Q4）——
   这属于题库层去重，P1-02 的 `question_fingerprint` 已具备该能力；
   本轮按指令**没有增加新规则**。

> 以上都是实现手段的收口，不是方向问题。**不继续无限增加规则。**

---

## 6. 正式资产保护检查

脚本在调用前后对 **75 个受保护文件**做了 SHA256 比对：

```text
changed = []
all_unchanged = true
```

覆盖：

```text
question_library.db         未修改
learning.db                 未修改
contentpack v5              未修改
structured/textbook/*       未修改
validator v2 / v3           未修改
P1-05-A / B / C / D / E / F 全部既有产物   未修改
P1-05-v1 / P1-05-v2         未修改（本轮新建 P1-05-v3）
教材 PDF / 54 个 MP3        未修改
正式 Web / Android          未修改
```

本轮唯一写入位置：`audit/AI_question_generation_spike/P1_05_prompt_v3_boundary/`
（任务未指定目录，故新建独立目录）。

`question_library.db` 内容复核：题目 2 条、`generation_run` 8 条、`ACTIVE` 0 条、事件 3 条 —— 与本轮开始前一致，**没有新增任何 `generation_run` 或 `AIQ:*`**。

---

## 7. 产物

| 文件 | 说明 |
| --- | --- |
| `p1_05g_report.md` | 本报告 |
| `p1_05g_request.json` | 请求（含 v2→v3 的两处修正原文、单变量差异、prompt 校验） |
| `p1_05g_response.json` | 原始响应 |
| `p1_05g_result.json` | 调用结果（guard 判定 + 75 个保护文件前后哈希） |
| `p1_05g_parsed.json` | 8 道题（**未入库**） |
| `p1_05g_analysis.json` | 逐题判定 + 三轮对照统计 + 跨轮重复 + 三个判断 |
| `prompt_v3.py` · `run_p1_05g.py` · `analyze_p1_05g.py` | 提示词构造 / 执行 / 只读分析脚本 |

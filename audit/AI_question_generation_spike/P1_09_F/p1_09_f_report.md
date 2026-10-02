# P1-09-F 实施报告 · 选择题逐候选协议最小真实验证

最终结论：**`P1-09-F_PASS`**

```text
AI 调用 = 1        retry_count = 0        finish_reason = stop
测试对象 = P1-09-D 的 FIX-C1 / FIX-C2（逐字复用，未重设计，未改题目/选项/答案/hidden_gold）
FIX-C1 第二答案 students ：以前 ACCEPT → 现在检出（UNIQUE_RISK）
FIX-C2 第二答案 word     ：以前 ACCEPT → 现在检出（UNIQUE_RISK）
false negative = 0        current answer 被错误排除 = 0
最终状态由程序汇总产生    AI 未输出任何整体唯一性结论
正式资产 0 修改（1,160 个文件复核 mismatched=0 / missing=0）
```

---

## 1. 执行结论

P1-09-E 提出的机制「选择题候选集合天然完整（=题目选项）→ AI 逐候选判断 → 程序汇总」
**在本次 2 个真实 fixture 上成立**，并且**修复了 P1-09-D 的 0/2 失败**。

```text
P1-09-D（旧协议：整题判断唯一性）
  FIX-C1：answer_unique=PASS + SUGGEST_ACCEPT + HIGH  → 漏检
  FIX-C2：answer_unique=PASS + SUGGEST_ACCEPT + HIGH  → 漏检

P1-09-F（新协议：逐候选判断，程序汇总）
  FIX-C1：students / parents / teachers 三个非当前答案选项三字段全 YES → 程序 UNIQUE_RISK
  FIX-C2：word / name 三字段全 YES，picture 被正确排除 → 程序 UNIQUE_RISK
```

调用账目：

| 项 | 值 |
| --- | --- |
| api_calls / retry_count | **1 / 0** |
| model / temperature / max_tokens / reasoning_effort | `deepseek-v4-pro` / `0.2` / `16384` / `low` |
| prompt_version | `P1-09-F-v1` |
| finish_reason | **stop** |
| input_tokens | 1,216 |
| output_tokens | 9,088（其中 reasoning 8,533 = 93.9%） |
| total_tokens | **10,304**（2 题 → 5,152 tokens/题） |
| latency | 147,647 ms（147.6 秒） |
| 结构状态 | PARSED（2 题、每题 4 候选、枚举合法、无禁止字段） |

---

## 2. FIX-C1 结果

```text
题目：Grandpa likes playing the erhu in the park with his ___.
选项：A friends（当前教材答案） / B students / C parents / D teachers
证据：hobby. But it’s a different kind of music.  He likes playing the erhu in the park
      with his friends. They sing Beijing opera together. There are many fans of them.
```

| 选项 | 候选 | grammar | semantic | context | need_more_context | AI valid_alternative | 程序判定 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | friends（当前答案） | YES | YES | YES | NO | YES | 有效 |
| **B** | **students** | YES | YES | YES | NO | YES | **有效 → 触发 UNIQUE_RISK** |
| C | parents | YES | YES | YES | NO | YES | 有效 |
| D | teachers | YES | YES | YES | NO | YES | 有效 |

AI 原文理由：

```text
A  课文原句为 with his friends，语法和语义均正确。
B  和他的学生一起拉二胡，语法正确、语义通顺、未被课文排除。
C  和他的父母一起拉二胡，语法正确、语义可理解、未被课文排除。
D  和他的老师一起拉二胡，语法正确、语义通顺、未被课文排除。
```

程序汇总：`candidate_coverage = COMPLETE`，`assessment = UNIQUE_RISK`。

---

## 3. FIX-C2 结果

```text
题目：Ms Chen writes a ___ on the blackboard.
选项：A sentence（当前教材答案） / B word / C picture / D name
证据：Our English teacher Ms Chen writes the sentence on the blackboard and says,
      “Please write this down.”
```

| 选项 | 候选 | grammar | semantic | context | need_more_context | AI valid_alternative | 程序判定 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | sentence（当前答案） | YES | YES | YES | NO | YES | 有效 |
| **B** | **word** | YES | YES | YES | NO | YES | **有效 → 触发 UNIQUE_RISK** |
| C | picture | YES | **NO** | YES | NO | **NO** | **被正确排除** |
| D | name | YES | YES | YES | NO | YES | 有效 |

AI 原文理由：

```text
A  课文原句为 writes the sentence，语法和语义均正确。
B  写一个单词，语法正确、语义通顺、未被课文排除。
C  write a picture 动宾搭配不当，应为 draw a picture。
D  写一个名字，语法正确、语义通顺、未被课文排除。
```

程序汇总：`candidate_coverage = COMPLETE`，`assessment = UNIQUE_RISK`。

注意 C 项：模型**不是**对所有选项都说 YES —— 它用搭配知识（write a picture ✗ / draw a picture ✓）
正确排除了一项。这说明逐候选判断在做独立判断，而不是无条件放行。

---

## 4. 逐候选判断原始结果（完整）

见 `ai_review_output.json`（原始）与 `assessment.json`（含程序重算）。
逐候选字段：`option / candidate_text / grammar_valid / semantic_valid /
textbook_context_valid / need_more_context / valid_alternative / reason_cn`。

```text
8 个候选（2 题 × 4 选项）全部返回，无缺失、无重复、无非法枚举值。
AI 的 valid_alternative 与程序按三字段重算的结果：8/8 一致（不一致数 = 0）。
need_more_context = YES 的候选：0 个。
```

程序重算规则（不照抄模型的自我汇总）：

```text
program_valid_alternative := (grammar_valid = YES)
                          AND (semantic_valid = YES)
                          AND (textbook_context_valid = YES)
```

---

## 5. 程序汇总结果

| 题目 | candidate_coverage | 触发条件 | assessment | 被判有效的非当前答案 | 被排除的非当前答案 |
| --- | --- | --- | --- | --- | --- |
| FIX-C1 | COMPLETE | 3 个非当前答案选项三字段全 YES | **UNIQUE_RISK** | students, parents, teachers | （无） |
| FIX-C2 | COMPLETE | 2 个非当前答案选项三字段全 YES | **UNIQUE_RISK** | word, name | picture |

汇总规则（本阶段落地版）：

```text
step1  任一非当前答案选项 grammar=YES 且 semantic=YES 且 textbook_context=YES → UNIQUE_RISK
step2  否则任一候选 need_more_context=YES                                     → UNIQUE_UNCERTAIN
step3  否则 coverage=COMPLETE 且其余选项全部被排除                              → UNIQUE_SUPPORTED
```

覆盖度依据（沿用 P1-09-E 结论）：

```text
选择题的候选集合就是题目已给出的全部选项（4 个），无需程序生成，
因此 candidate_coverage = COMPLETE，不受"候选池覆盖不足"限制。
```

**AI 没有最终决策权**：原始输出的键只有 `items[].candidates[]` 的逐候选字段，
不含任何 `unique / assessment / verdict / score / ranking / approve / activate` 字段
（脚本扫描结果为空）。最终 `UNIQUE_RISK` 完全由程序按上式算出。

---

## 6. 是否仍存在教材答案锚定

**没有观察到锚定。** 三条证据：

```text
1. 理由文本是反向表述：三条非当前答案选项的理由都写成"未被课文排除"，
   而不是"课文只写了 friends/sentence，所以其他选项不对"。
2. 锚定模式扫描 0 命中：对 8 条理由做固定模式扫描
   （"与课文一致，所以" / "所以唯一" / "因此唯一" / "课文里有，所以" / "其他选项都不" 等）→ 0 命中。
3. 反锚定提示词起作用：prompt 明确写了"当前标注的教材答案不代表唯一答案""必须独立逐项判断"
   "不得因为教材原答案存在就默认其他选项错误"，本次输出与之一致。
```

同时如实记录一个细节：当前答案（A 项）的理由写的是"课文原句为 with his friends"——
这是**描述性依据**（说明它为什么对），并没有被用来否定其他选项。
两者必须区分，否则会把"引用课文"误判成"锚定课文"。

---

## 7. 是否检出第二正确答案

```text
FIX-C1 设计中的第二正确答案 students → 检出（另 parents / teachers 同样被判有效）
FIX-C2 设计中的第二正确答案 word     → 检出（另 name 同样被判有效）
检出率 2/2（P1-09-D 同一对 fixture 为 0/2）
```

但必须写清一个**精度问题**，否则会误读本次结果：

```text
AI 实际上把"语法成立 + 语义成立 + 不与课文冲突"的选项几乎全部判为有效：
  FIX-C1：3/3 个非当前答案选项全部判有效
  FIX-C2：2/3 个非当前答案选项判有效（picture 被排除）

按 P1-09-C 的排除规则（排除 = 语法不成立 ∨ 语义不成立 ∨ 与教材原文冲突），
这些选项确实"没有被排除"，因此判有效是**契约正确的输出**，不是过度告警。
但这意味着：只要选择题的干扰项在语法与语义上站得住，就会被标成 UNIQUE_RISK。
→ 机制的收益是"不会再把多解题误报为唯一"（召回导向）；
  代价是"选择题几乎都会进入人工复核"（精度低）。
```

---

## 8. false positive / false negative

```text
false negative（设计的第二答案未被检出）： 0 / 2
false positive（真实正确选项被错误排除）： 0 / 2   （friends / sentence 均判有效）
额外被标记的非设计候选：3 个（parents, teachers, name）
AI 自我汇总与程序重算不一致：0 / 8
被正确排除的候选：1 个（picture，理由为动宾搭配不当）
```

关于"额外标记的 3 个候选"是否算 false positive：

```text
按契约定义不算 —— 它们语法成立、语义成立、且不被课文排除，属于"未被排除的候选"。
但它们不是实验人员设计的第二答案，因此作为"精度观察值"如实记录：
本次 2 题共标记 5 个非当前答案候选，其中 2 个是设计目标、3 个是语法语义同类的并行选项。
```

---

## 9. 成本

```text
本次：1 次调用 / input 1,216 / output 9,088（reasoning 8,533 = 93.9%）/ total 10,304
      latency 147.6 秒 / 2 题 → 5,152 tokens/题
P1-09-D 基线：1,024.7 tokens/题（15 题一次调用）
→ 本次为基线的 5.03 倍
```

必须说明比率口径（否则会高估差距）：

```text
P1-09-D 把固定指令成本摊到 15 题，本次只摊到 2 题。
按输出侧单题比较更公平：
  P1-09-D：763.5 output tokens/题
  P1-09-F：4,544 output tokens/题  → 约 6 倍
差异来自逐候选协议本身：每个候选都要独立推理（8 个候选 × 各自判断）。
P1-09-E 的估算（每候选 +10 prompt / +35 output tokens）明显低估了 reasoning：
本次实际每候选输出 1,136 tokens（9,088 / 8），其中 1,067 是 reasoning。
```

结论：逐候选协议**准确性收益明确**，但**成本必须按实测重估**；
它不能当作"便宜的额外检查"，而应视为"每题都要付的一次完整复核成本"。

---

## 10. 对 P1-09-E 机制的结论

P1-09-E 的路线判断（选择题可行 / 填空题被数据阻塞）在本次真实调用中被**前半段验证**：

```text
选择题候选集合天然完整（=选项）→ 覆盖度 COMPLETE → 不需建候选池 → 无覆盖风险
逐候选协议确实消除了旧协议下的教材锚定
程序汇总规则可稳定工作（8/8 候选字段合法、0 不一致、0 需补上下文）
程序掌握最终状态，AI 无最终决策权
```

同时新增三条必须记录的实测限制：

```text
LIMITATION-1（精度）：逐候选协议会把"语法语义站得住"的并行选项几乎全部标为有效，
  选择题的 UNIQUE_RISK 比例会很高，人工复核负担不会明显下降。
  它防的是"误报唯一"，不是"减少人工"。
LIMITATION-2（成本）：每候选 reasoning 成本远高于 P1-09-E 估算（实测 1,136 tokens/候选），
  长期成本需按真实数据重新建模。
LIMITATION-3（样本量）：本次只有 2 个 fixture，且都是 vocab_choice；
  reading_choice、其它 Unit、其它干扰项结构均未验证。
```

---

## 11. 下一步建议

```text
1. 把"逐候选协议"固定为选择题的正式方案（候选池 = 选项、程序汇总、AI 无语义终审权），
   但把 UNIQUE_RISK 的产品含义限定为"需要人工看一眼"，而不是"题目有问题"。
2. 下一轮扩大样本（建议 8–10 道真实选择题，覆盖 reading_choice 与多个 Unit），专门测量：
     a) 召回：真实第二答案是否继续 100% 检出
     b) 精度：被标记候选中，人工确认为"真正可接受答案"的比例
3. 成本按实测重估：每候选约 1.1k tokens；若一次 8 道选择题批量调用，
   先测真实总 token，再决定是否需要分级（例如只对 fill 与高风险题做逐候选）。
4. 填空题仍按 P1-09-E 的 fail-safe 处理（不得输出 UNIQUE_SUPPORTED），本次未涉及。
5. 正式落地前补齐：候选维度结果与 lifecycle 的隔离（只进复核信息、不产生 question_event），
   以及"AI 结论 vs 人工结论"的一致率测量。
```

---

## 12. 正式资产保护

```text
锚点：P1-09-D protect_after.json（写于 P1-09-E / P1-09-F 之前）
files_checked = 1160   mismatched = 0   missing = 0   all_match = true

question_library.db 7AA12CA5EB24417BF0AE7E97A8161920B501825D030D69A8E0863272AC695DA7 （未变）
learning.db         0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91 （未变）
contentpack v5      65829CA73E41B75ACA010B93B7339EDDF0F666F919148F0F69ED898419700C39 （未变）

未生成新正式题目 · 未写 question_library · 未修改教材 PDF / MP3 / V1.3 / V2.0
未修改正式 Web / Android / validator / 正式 question lifecycle
未做 schema migration · 未新增依赖 · 未安装软件 · 未修改已有正式业务代码
所有新文件均在 audit/AI_question_generation_spike/P1_09_F/
```

盲测保护：`ai_input_snapshot.json` 只含 question_id / question_type / 题干 / 选项 /
当前教材答案 / 教材位置 / 完整证据块 / 年级背景；脚本内置禁用词扫描
（hidden_gold、gold_reason、introduced_defect、known_issue、category、expected、validator、
mechanical_rewrite、lifecycle、second answer、第二答案、P1-09-D、P1-09-B、unique）
**扫描结果为空**；`hidden_gold.json` 仅在调用完成后才被读取用于对照。

---

## 13. 最终结论

```text
P1-09-F_PASS
```

PASS 条件逐条：

```text
FIX-C1 检出第二合理答案                    ✔（students，另 parents/teachers 同类）
FIX-C2 检出第二合理答案                    ✔（word，另 name 同类）
没有把真实正确选项错误排除                   ✔（friends / sentence 均判有效）
没有依赖 hidden_gold                       ✔（输入禁用词扫描为空，gold 调用后才读取）
最终状态由程序汇总产生                       ✔（UNIQUE_RISK 由 aggregate_f.py 计算）
AI 没有直接拥有最终 UNIQUE/REJECT 决策权     ✔（输出中无任何整体结论字段）
```

STOP 条件逐条核对（均未触发）：

```text
任意一个 FIX 仍然漏掉第二答案   → 未发生（2/2 检出）
AI 仍然明显锚定教材答案         → 未发生（0 模式命中，理由为"未被课文排除"）
AI 给出"与课文一致，所以唯一"    → 未发生
程序汇总规则无法稳定工作         → 未发生（8/8 候选字段合法、0 不一致）
AI 输出结构无法可靠解析         → 未发生（PARSED，finish_reason=stop）
```

本阶段只完成一次真实 AI 调用，完成后立即停止，不进入 P1-09-G。

# P1-05-F 实施报告 · 以教材学习重点为核心重新验证生成路线

最终状态：**P1_05_F_PASS**

执行日期：2026-09-17
样本：Unit 2 · A new start · `UNDERSTANDING_IDEAS`（与 P1-05-D 完全相同的教材 evidence/context）
新提示词版本：**`P1-05-v2`**
真实 AI 调用：**1 次**（`api_calls=1`、`retry_count=0`，无第二次）

---

## 0. 一句话结论

> **“以教材学习重点为核心 + 用课文语境重新组合”这个方向，明显比"把整章文本交给 AI 自由生成"更符合本项目要求。**
> P1-05-E 认定的 BLOCKER（填空答案不唯一）在 v2 下**没有复现**；
> 但 v2 的措辞同时把 fill 题型**整体逼死**，并让模型开始使用**教材外的干扰词与元语言题干**。

---

## 1. 调用结果

| 项 | 值 |
| --- | --- |
| endpoint | `https://api.deepseek.com/chat/completions` |
| model | `deepseek-v4-pro` |
| prompt_version | **`P1-05-v2`** |
| max_tokens / thinking / reasoning_effort | 16384 / `{"type":"enabled"}` / `low`（与 P1-05-D 一致） |
| temperature | 0.2 |
| **finish_reason** | **`stop`** |
| content | 4,074 字符，JSON 完整解析 |
| prompt_tokens | 11,028 |
| completion_tokens | 8,548（其中 reasoning **7,426**） |
| total_tokens | 19,576 |
| **latency** | **119.2 s** |
| **实际生成题数** | **7** |
| guard 判定 | `PROCEED`（未触发截断即停） |
| 是否写入题库 | **否** |

### 单变量纪律

```text
与 P1-05-D 的差异：只有 messages[0]（system prompt）   ← 逐字段比对确认
教材 evidence / context：逐字节相同
model / temperature / max_tokens / thinking / reasoning_effort：全部不变
```

---

## 2. `P1-05-v2` 相对 `P1-05-v1` 改了什么

把原来的"题型说明"块**整块替换**为以教材学习重点为核心的规则（10 条硬规则与 JSON schema 未动）：

```text
CORE PRINCIPLE — 出题依据优先级：
  1. 教材本 Section 明确教的学习点（教材自己的练习、标题、语法聚焦、语言运用框）
  2. Unit 词汇表 unit_vocabulary（emphasis=BOLD 的核心词优先）
  3. 教材短句、重点表达、典型句型
  4. 课文中的重要事实与信息（人物/事件/关系/原因/细节/主旨）
  5. 其他普通正文（仅当前面都无法支撑时才用）
课文正文是"让题目有意义的语境"，不是学习点本身。

各题型规则：
  fill        —— 优先词表中的词（BOLD 优先）；不得从正文随手挑普通词；
                 答案必须由教材证据唯一确定；两种合理英文答案就不要出；
                 不能全是"原句挖一个空"
  vocab_choice—— 正确项必须来自 unit_vocabulary（BOLD 优先）；可重新设计语境；
                 干扰项必须是初一学生可能混淆的词
  sentence/表达—— 基于教材短句/典型表达/重点结构；可重组或改变考法；不得凭空创造语言点
  reading_*   —— 只考重要信息、人物、事件、关系、原因、细节或主旨

ANTI-DUPLICATION（硬规则）：
  · 同一 evidence block 不得复用，除非考查点确实不同
  · 不得复现教材原练习（同指令同选项）
  · 不得把同一句换几个空当成多道题
```

---

## 3. 逐题结果（7 道）

| # | 题型 | 答案 | 对应教材学习重点 | 对应词汇/短句/表达 | evidence | 教材原题复现 | 机械改写 | 真正重新组合 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | reading_choice | The electric guitar | 课文事实 + BOLD 词 | electric / guitar（BOLD） | P37:B10 `I play the electric guitar in the school band.` | 否 | 否 | **是** |
| 2 | reading_choice | In the park | 课文重要事实 | 课文句（爷爷在公园拉二胡） | P37:B12 | 否 | 否 | **是** |
| 3 | reading_choice | Take part in it with Grandpa | 核心结构 decide to do | decide（BOLD）+ `take part in` | P38:B3 | 否 | 否 | **是** |
| 4 | reading_judge | True | 课文重要事实 | `Grandpa gives me a big smile, and I smile back.` | P38:B5 | 否 | 否 | **是** |
| 5 | vocab_choice | practice | BOLD 核心词 | practice（BOLD） | P38:B3 | 否 | **是**（原句挖空 + 选项） | 部分 |
| 6 | vocab_choice | instruments | BOLD 核心词 | instrument（BOLD） | P38:B3 | **是**（教材 a4 图表填空的同一个空） | **是** | 否 |
| 7 | vocab_choice | sound | 教材语法聚焦例句 | sound（BOLD）+ `the sound of Grandpa's erhu cuts in`（a5 语法例句） | P37:B11 | 否 | **是**（原句挖空 + 选项） | 部分 |

### 逐题要点

- **Q1**：把 BOLD 词 electric guitar 放进阅读事实里问，是"学习点 + 语境"的正确用法。
  但干扰项 **violin / piano 完全不在 Unit 2 词表或正文中**。
- **Q2**：课文重要事实的定位题。**与 P1-05-D 的 Q8 是同一道题**（同 block、同答案、四个选项中三个相同）。
- **Q3**：用 `decide to take part in` 这个核心结构提问，答案虽为短语但明确。
  干扰项 `alone` 不在教材词表或正文中。
- **Q4**：本批新增的 `reading_judge` 题型，考课文事实（演出后相视而笑），判 True 明确。
  题干用词 `performance` 不在教材词表或正文中。
- **Q5 / Q7**：正确项都来自 BOLD 词表，方向正确；但形态仍是"教材原句挖一个空 + 选项"，
  且题干引入了 **“Choose the best word to complete the sentence:”** 这种元语言，
  其中的 `sentence` / `word` 同样是越界词。
- **Q6**：目标词 `instruments` **正是教材第 34 页 a4 图表填空的同一个空**，
  属于教材原练习复现；干扰项 `bands / guitars / stages` 是复数形式且不在词表内。

---

## 4. 重点统计

```text
实际生成题数                     7
题型分布                          reading_choice 3 / vocab_choice 3 / reading_judge 1 / fill 0

教材学习重点命中率                7 / 7        （5 道命中词汇表或重点结构，2 道命中课文重要事实）
词汇表答案占比                    4 / 7
加粗重点词答案占比                4 / 7
短句/重点表达利用情况             7 / 7 都以教材句子为语境；其中 Q7 直接对应 a5 语法聚焦例句、
                                 Q3 对应 decide to do 结构（教材明确聚焦的语言点）
真正重新组合题占比                6 / 7
原句机械挖空数量                  3 / 7        （Q5 Q6 Q7）
教材原题复现数量                  1            （Q6 = 教材 a4 图表填空的同一个词）
答案唯一性                        7 / 7
教材依据是否充分                  7 / 7
明显低价值题数量                  1            （Q6，学习增量接近零）
```

---

## 5. 与 P1-05-D 的 10 题对照

| 指标 | P1-05-D（P1-05-v1，10 题） | P1-05-F（P1-05-v2，7 题） | 变化 |
| --- | --- | --- | --- |
| 题量 | 10 | **7** | 自然减少（未凑数） |
| fill 题数 | 4 | **0** | 题型消失 |
| 答案落在教材词表 | 5/10（50%） | **4/7（57%）** | 略升 |
| 答案是 BOLD 重点词 | 4/10（40%） | **4/7（57%）** | 升 |
| 答案唯一 | 6/10（60%） | **7/7（100%）** | **显著改善** |
| 原句机械挖空 | 7/10 | **3/7** | 降 |
| 教材原题复现 | 1（Q10 主旨原题） | 1（Q6 图表原词） | 持平 |
| 真正重新组合 | 5/10（50%） | **6/7（86%）** | 升 |
| 明显低价值题 | 4 | **1** | 降 |
| 词汇越界题（只读复算 validator 检查 5） | 2/10 | **6/7** | **明显恶化** |
| 同一 block 复用 | 3 个 block 各 2 次 | P38:B3 **3 次** | 更集中 |

### 三条变化最说明问题

1. **答案唯一性 60% → 100%**：P1-05-E 的 BLOCKER（填空可用同义词替换）在 v2 下消失。
2. **机械挖空 7/10 → 3/7，重新组合 50% → 86%**：出题重心从"复述正文"转向"用教材学习点出题"。
3. **词汇越界 2/10 → 6/7**：这是 v2 带来的**新问题**，必须修。

> 注：词汇越界是用 `validator_v3` 的 `out_of_scope()` **只读复算**得到的，本轮没有跑正式 validator 流程。

---

## 6. 本轮暴露的三个新问题

| # | 严重度 | 问题 | 证据 | 建议 |
| --- | --- | --- | --- | --- |
| **G1** | REGRESSION | **fill 题型被规则整体判死（4 → 0）** | v2 对 fill 的两条约束（答案必须唯一、机械挖空价值低）让模型完全停止生成填空题；而填空正是教材 a4 / a6 / a7 的主要练习形态 | 把 fill 设计成「**限定词库的语境填空**」，例如要求答案取自 unit_vocabulary 或给出词库，而不是笼统地要求"少出 fill" |
| **G2** | REGRESSION | **出现教材外干扰词与元语言题干** | Q1 violin/piano、Q3 alone、Q4 performance、Q5–Q7 题干里的 sentence/word；只读复算显示 6/7 道题会因词汇越界 FAIL | 提示词中明确禁止在题干加入指令式元语言，并限定干扰项只能取自本单元词表 |
| **G3** | IMPROVE | 同一 block 复用更集中 | P38:B3 被 Q3/Q5/Q6 共用 3 次 | 对同一 block 的复用设上限（如 ≤2），并要求优先覆盖尚未使用的重点词 |
| **G4** | OBSERVE | 与 P1-05-D 存在跨轮重复 | F-Q2 与 D-Q8 实质同题；F-Q1 与 D-Q5 都考 electric guitar | 正式实验启用跨轮 `question_fingerprint` 去重（P1-02 已具备该能力） |

---

## 7. 关键问题的回答

> **“把教材学习重点、词汇表、短句作为出题核心，再让 AI 利用课文语境重新组合，是否比单纯把整章文本交给 AI 自由生成更符合本项目要求？”**

### 回答：**是，方向明确更符合要求；但本轮也暴露了必须一并修正的两个新问题。**

**支持"更好"的证据**

- 答案唯一性从 6/10 提升到 7/7 —— P1-05-E 认定的 BLOCKER 在 v2 下没有复现；
- 原句机械挖空从 7/10 降到 3/7，"真正重新组合"从 50% 升到 86%；
- 答案落在教材词表/BOLD 重点词的比例从 50%/40% 升到 57%/57%；
- **不再从正文随手挑普通词出题**：D 里那类 `autumn` / `great` / `Rock music` / `Beijing opera` 的答案在本批中完全没有出现；
- 7/7 都能对应到一个教材学习点（5 道命中词汇表或重点结构，2 道命中课文重要事实）；
- 教材原题复现没有增加（1 → 1），并且新增了 `reading_judge` 这一种题型。

**必须一并说清的反面证据**

- **fill 被整体逼死（4 → 0）**：这等于把教材最主要的一类练习从产出中移除；
- **词汇越界题从 2/10 升到 6/7**：新提示词下模型开始使用教材外的干扰词，并在题干里加入指令式元语言；
- 同一 block 复用更集中（P38:B3 用了 3 次）；
- 与 P1-05-D 存在跨轮重复题。

**结论**：v2 的"学习点优先"方向是对的，也确实修掉了 P1-05-E 的 BLOCKER；
但 v2 的**措辞**把 fill 逼死、并放松了用词边界。
下一版应在保留"学习点优先"的同时，明确 fill 的合法形态（限定词库）与用词边界（题干不带元语言、干扰项取自本单元词表）。
**本轮不继续堆规则，只把问题记录清楚。**

---

## 8. 保护项（调用前后自动哈希比对）

脚本内置 before/after 比对，结果 `all_unchanged = true`、`changed = []`：

```text
question_library.db     未修改（无新 generation_run、无 AIQ:*）
learning.db             未修改
contentpack v5          未修改
structured/textbook     未修改
validator v2 / v3       未修改
P1-05-A / B / C / D 全部产物未修改
P1-05-v1                未修改（本轮新建 P1-05-v2，未触碰 v1）
教材 PDF / 54 个官方 MP3 未修改
正式 Web / Android      未修改
AI API 调用             1（就本轮这一次，无第二次、无 retry）
```

**关于输出目录**：任务未指定目录，本轮新建独立目录
`audit/AI_question_generation_spike/P1_05_prompt_v2_textbook_focus/`，
未改动任何既有目录与正式资产。

---

## 9. 产物

| 文件 | 说明 |
| --- | --- |
| `p1_05f_report.md` | 本报告 |
| `p1_05f_request.json` | 请求（含与 P1-05-D 的逐字段差异，证明只有 system prompt 变化） |
| `p1_05f_response.json` | 原始响应 |
| `p1_05f_result.json` | 调用结果（guard 判定、保护项前后哈希） |
| `p1_05f_parsed.json` | 解析后的 7 道题（**未入库**） |
| `p1_05f_analysis.json` | 逐题判定 + 与 P1-05-D 的对照统计 + 新问题 + 关键问题结论 |
| `run_p1_05f.py` / `analyze_p1_05f.py` | 执行与只读分析脚本 |

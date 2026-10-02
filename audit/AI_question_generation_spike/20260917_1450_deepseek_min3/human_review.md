# 人工复核（3 题逐题）

复核口径：**能否在几秒内指出"来自教材哪一页、哪一句"**；若必须读完 AI 解释才能判断，即判不合格。

## q1 · fill · page 56 · activity 2

| 项目 | 判定 |
| --- | --- |
| 来源 | 教材第 56 页，故事第 1 段原句 `But Robert has a serious disease and cannot move at all.`（block `FLTRP-EN-7A-2022CUR:P61:B5`）→ **一眼可见** |
| 答案 | `disease`，为原句被挖掉的词，逐字命中 quote → **可由教材直接确定** |
| 题目质量 | 标准教材原句填空，句子未改写，符合初一水平 |
| 干扰项 | 无（填空题） |
| 入库价值 | **YES** |

## q2 · vocab_choice · page 56 · activity 2

| 项目 | 判定 |
| --- | --- |
| 来源 | 教材第 56 页，故事第 2 段原句 `He puts Robert in a trailer and pulls it along with his bike.`（block `…:P61:B7`）→ **一眼可见** |
| 答案 | `trailer`，逐字命中 quote；选项 `road / disease / result` 全部是教材内词（road 为本单元黑体词，disease / result 出现在同页正文）→ **无教材外虚假信息** |
| 题目质量 | 语境选词，句面自然；唯一正确答案（其余三项在句中语义不成立） |
| 干扰项 | 合理：同单元词性/语义场接近，无垃圾选项（无 "banana" 之类） |
| 入库价值 | **YES**（程序 FAIL 源于白名单把"解释文本 + 引号内单词"算作题面词汇，见下方说明） |

## q3 · reading_choice · page 57 · activity 2

| 项目 | 判定 |
| --- | --- |
| 来源 | 教材第 57 页，故事第 3 段原句 `Now, the brothers often take part in bike races together.`（block `…:P62:B0`）→ **一眼可见** |
| 答案 | 正选项 `They often take part in bike races together.` 与该原句为**指代替换**关系（They = the brothers）；A/C/D 与原文相反或无依据 → **可由教材证据直接支持，但非逐字相同** |
| 题目质量 | 标准阅读细节题（事实题），无开放解释，符合初一水平 |
| 干扰项 | 合理：A（拒绝比赛，与 `John refuses to race without his brother` 混淆）、C（often win，与 `They don't often win` 相反）、D（stay at home 与 Robert 早期状态对应）；均来自教材内容，非编造 |
| 入库价值 | **YES（附条件）**：需在入库口径中明确"指代/同义替换可用教材原句支持"，否则未来同类型题会被逐字规则误杀 |

## 结论

- 3/3 都能在几秒内定位到教材具体句子与页码；
- 3/3 答案均可由教材证据确定（q3 差在"逐字"而非"证据"）；
- 无教材事实编造、无教材外知识、无垃圾干扰项、无重复题；
- 需要人工介入的只有"**校验器口径**"这一件事，而不是题目本身。

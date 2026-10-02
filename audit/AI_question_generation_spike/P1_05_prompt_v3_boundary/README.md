# P1-05-G · P1-05-v3（恢复合理 Fill + 收紧教材素材边界）

## 最终状态

### **P1_05_G_PASS**

```text
样本            Unit 2 · UNDERSTANDING_IDEAS（与 P1-05-D / F 逐字节相同的 context）
prompt_version  P1-05-v3（新建；v1 / v2 未修改）
API 调用        1 次，retry_count = 0
finish_reason   stop
生成题数        8
写入题库        否
正式资产        0 修改（75 个受保护文件 before/after 哈希一致，changed = []）
```

---

## 本轮只做了两处修正

| # | 修正 |
| --- | --- |
| 1 | **恢复合理的 Fill**：把 v2 里把 fill 逼死的措辞改为"欢迎并鼓励在合适学习点上生成 fill"，并明确 fill 的目的 = "用教材重点词做有唯一答案的语境练习"，而不是"把教材原句挖掉一个词" |
| 2 | **教材素材边界 + 去元语言**：题目中每一处英语（答案 / 干扰项 / 题干实词 / 被考短语）都必须追溯到本 Unit 教材素材；禁止把 `Choose the best word to complete the sentence:` 这类 AI 说明性语言写进孩子可见题干 |

其余全部不变：学习点优先的核心原则、10 条硬规则、JSON schema、anti-duplication、题量不设配额。

---

## 与 P1-05-F 的对比（并列出 D 作参照）

| 指标 | D（v1，10 题） | F（v2，7 题） | **G（v3，8 题）** |
| --- | --- | --- | --- |
| fill 数量 | 4 | **0** | **4** |
| fill 词汇表答案 | 1/4 | —（无 fill） | **4/4** |
| fill BOLD 答案 | 0/4 | —（无 fill） | **4/4** |
| 答案唯一 | 6/10 | 7/7 | **7/8** |
| 教材外词汇题数 | 2/10 | **6/7** | **1/8** |
| 真正教材外 token | 4 | 9 | **0**（3 个为词形变化假阳性） |
| 真正重新组合 | 5/10 | 6/7 | **3/8** |
| 原句机械挖空 | 7/10 | 3/7 | **4/8** |
| 教材原题复现 | 1 | 1 | **0** |
| 低价值题 | 4 | 1 | **1** |

---

## 三个最终判断

### A · 是否恢复合理填空、且没回到"机械挖空"

**部分恢复**：fill 0 → 4，且 **4/4 答案是 Unit 词汇表的 BOLD 重点词**（D 为 0/4）；
但 **4/4 的填空语境仍是教材原句直接挖空**，"把原句挖掉一个词"这一形态仍在，区别在于挖的是重点词。
另有 1 处唯一性风险（Q3 的 different / traditional 都说得通）。

### B · 收紧素材边界后是否明显减少教材外词汇

**是**：教材外词汇题 F 6/7 → G 1/8；真正教材外 token **0**；
F 里的 violin / piano / alone / performance 全部消失；元语言题干也消失。

### C · 能否作为批量生成的基础规则

**可以作为基础**，两处需收口：① fill 语境仍是原句照搬；② 跨轮重复明显
（8 道中 4 道与 D/F 同答案同 block，属题库层去重，P1-02 的 `question_fingerprint` 已具备该能力）。
**本轮按要求不继续增加规则。**

---

## 保护检查

```text
changed = []
```

75 个受保护文件（`question_library.db`、`learning.db`、contentpack、`structured/textbook/*`、
validator v2/v3、P1-05-A~F 全部既有产物、P1-05-v1/v2、教材 PDF、54 个 MP3）
在调用前后 SHA256 完全一致。`question_library.db` 仍为：题目 2 条、run 8 条、ACTIVE 0 条、事件 3 条。

---

## 产物

| 文件 | 说明 |
| --- | --- |
| `README.md` | 本索引 |
| `p1_05g_report.md` | 完整实施报告 |
| `p1_05g_analysis.json` | 逐题判定 + 三轮对照 + 跨轮重复 + 三个判断 |
| `p1_05g_request.json` | 请求（含两处修正原文与单变量校验） |
| `p1_05g_response.json` | 原始响应 |
| `p1_05g_result.json` | 调用结果与保护项哈希 |
| `p1_05g_parsed.json` | 8 道题（未入库） |
| `prompt_v3.py` · `run_p1_05g.py` · `analyze_p1_05g.py` | 提示词构造 / 执行 / 只读分析 |

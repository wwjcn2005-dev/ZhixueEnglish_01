# P1-05-F · 以教材学习重点为核心重新验证生成路线

## 最终状态

### **P1_05_F_PASS**

```text
样本            Unit 2 · UNDERSTANDING_IDEAS（与 P1-05-D 完全相同的 evidence/context）
prompt_version  P1-05-v2（新建；P1-05-v1 未修改）
API 调用        1 次（无 retry、无第二次）
finish_reason   stop
生成题数        7
写入题库        否
```

---

## 一句话结论

> **“以教材学习重点为核心 + 用课文语境重新组合”明显比“把整章文本交给 AI 自由生成”更符合本项目要求。**
> P1-05-E 认定的 BLOCKER（填空答案不唯一）在 v2 下**没有复现**；
> 但 v2 的措辞同时把 **fill 题型整体逼死**，并让模型开始使用**教材外干扰词与元语言题干**。

---

## 调用数据

```text
model            deepseek-v4-pro
max_tokens       16384     thinking {"type":"enabled"}     reasoning_effort low
temperature      0.2
finish_reason    stop       content 4,074 字符，JSON 完整解析
prompt_tokens    11,028
completion       8,548（reasoning 7,426）
total_tokens     19,576
latency          119.2 s
```

单变量纪律：与 P1-05-D 逐字段比对，**只有 system prompt 变了**；教材 context 逐字节相同。

---

## 与 P1-05-D 的对照

| 指标 | P1-05-D（v1，10 题） | P1-05-F（v2，7 题） |
| --- | --- | --- |
| fill 题数 | 4 | **0** ← 题型被逼死 |
| 答案落在教材词表 | 5/10 | **4/7** |
| 答案是 BOLD 重点词 | 4/10 | **4/7** |
| 答案唯一 | 6/10 | **7/7** ← 显著改善 |
| 原句机械挖空 | 7/10 | **3/7** |
| 真正重新组合 | 5/10 | **6/7** |
| 明显低价值题 | 4 | **1** |
| 词汇越界题（只读复算） | 2/10 | **6/7** ← 恶化 |
| 同一 block 复用 | 3 个 block 各 2 次 | P38:B3 **3 次** |

---

## 本轮暴露的新问题

| # | 严重度 | 问题 |
| --- | --- | --- |
| **G1** | REGRESSION | fill 被规则整体判死（4 → 0），而填空是教材 a4/a6/a7 的主要形态 → 应改为「限定词库的语境填空」 |
| **G2** | REGRESSION | 出现教材外干扰词（violin/piano/alone/performance）与元语言题干（sentence/word）；只读复算 6/7 会因词汇越界 FAIL |
| G3 | IMPROVE | 同一 block（P38:B3）被 3 道题共用 |
| G4 | OBSERVE | 与 P1-05-D 存在跨轮重复（F-Q2 ≡ D-Q8；F-Q1 与 D-Q5 同考 electric guitar） |

---

## 关键问题

> “把教材学习重点、词汇表、短句作为出题核心，再让 AI 利用课文语境重新组合，
> 是否比单纯把整章文本交给 AI 自由生成更符合本项目要求？”

**是。** 支持证据：答案唯一性 60%→100%、机械挖空 7/10→3/7、重新组合 50%→86%、
答案落在词表/BOLD 的比例上升、不再从正文随手挑普通词、7/7 都能对应到教材学习点。

**但必须一并说清**：fill 被逼死、词汇越界题从 2/10 升到 6/7。
下一版应在保留"学习点优先"的同时，明确 fill 的合法形态与用词边界。**本轮不继续堆规则。**

---

## 保护项

```text
question_library.db / learning.db / contentpack / structured/textbook   未修改
validator v2 / v3                                                       未修改
P1-05-A / B / C / D 全部产物                                             未修改
P1-05-v1                                                                未修改（本轮新建 P1-05-v2）
教材 PDF / 54 个官方 MP3 / 正式 Web / Android                            未修改
AI API 调用                                                             1（无第二次、无 retry）
```

任务未指定输出目录，本轮新建独立目录 `P1_05_prompt_v2_textbook_focus/`，未改动任何既有目录与正式资产。

---

## 产物

| 文件 | 说明 |
| --- | --- |
| `README.md` | 本索引 |
| `p1_05f_report.md` | 完整实施报告 |
| `p1_05f_analysis.json` | 逐题判定 + 对照统计 + 新问题 + 关键问题结论 |
| `p1_05f_request.json` | 请求（含与 P1-05-D 的逐字段差异） |
| `p1_05f_response.json` | 原始响应 |
| `p1_05f_result.json` | 调用结果与保护项哈希 |
| `p1_05f_parsed.json` | 7 道题（未入库） |
| `run_p1_05f.py` · `analyze_p1_05f.py` | 执行与只读分析脚本 |

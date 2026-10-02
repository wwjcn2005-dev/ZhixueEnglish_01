# P1-08-C1 实施报告（归档）：最小学习行为模型与记录协议
- 结论：**PASS**
- 归档时间：2026-09-12T16:46:09+08:00
- 性质：行为协议实现（加性扩展，不改既有语义）

## 1. 现有模型（本任务起点）
```text
learning_record.activity_type = **学习行为**枚举（B1.15 §19 冻结 9 值：recognize / read / understand /
  listen / repeat / spell / substitute / produce / review）
learning_record.result = **判断结果**（correct / incorrect / partial / done / skipped / NULL）
参与判断规则（C2 §5.2，未改）：correct · incorrect · partial；done / skipped / NULL 不参与
唯一 Record 写入口：learning_service.record_learning_event()（单事务 Record + Mastery）
```

## 2. 本次新增 / 修改
```text
① learning/learning_service.py（**加性 2 行**）：
     BEHAVIOR_EXTENSION = ("study", "practice")
     ACTIVITY_TYPES = ACTIVITY_TYPES + BEHAVIOR_EXTENSION
   原 9 值全部保留、语义不变；未改字段/事务/Mastery 逻辑
   修改前 SHA256：D8A174567263BEADBB3732795FFDA4E485BDD1D617D82C77E69D8F5442EF9B37（16,752 B）
   修改后 SHA256：01341A05231EFCA6E0C801CF95D8A96F3DF732753F1F679688D44708586DF1D6（17,034 B）
② learning/behavior_service.py（新增，4,931 B，0C6EF4822F60D9251B68382C95A5D3D9987650811F4FC93C70875AF48249FC6D）
```

## 3. 行为协议
```text
record_behavior(conn, learner_id, task_id, item_id, behavior, result=None, …)   # 统一入口
record_study(…)        # study    → done | skipped | NULL
record_practice(…)     # practice → correct | incorrect | partial | done | skipped | NULL
record_activity_behavior(conn, learner_id, activity, behavior, …)               # 直接消费 P1-07-C2 投影
check_behavior / check_behavior_result / list_behaviors
```
全部**委托** `record_learning_event()`：不复制校验、attempt_no 计算与事务逻辑；三类教材资源共用同一协议；
不引入 VocabularyRecord / PhraseRecord / SentencePatternRecord。

## 4. 测试
```text
learning/test_behavior_service.py：Ran 8 tests — OK（覆盖 §十五 22 项）
study/practice 产生 Record｜三类资源同一协议｜attempt_no 递增（换行为重新从 1）｜
correct/incorrect/partial 语义不变（done/skipped 不计 correct；study 拒绝对错值；view 被拒）｜
Session/Task/TaskItem 创建与 Activity/池/列表查询**不产生 Record**｜
Mastery 更新 + incorrect→current_error、partial→current_weak、correct→出池、历史保留｜
learner 隔离｜AI=0 / 网络=0 / contentpack 与正式库未污染
回归：C1 14 · C2-A 10 · P1-07-C1 9 · P1-07-C2 9 · P1-08-C1 8 全部 OK（连续 3 轮）
```

## 5. 数据库 / 安全
schema 未变（learning.db v2 / 7 表；study·practice 存于既有 activity_type TEXT 列）｜
正式库业务表 0 行、未被测试污染｜contentpack 未写入｜AI = 0 ｜ 网络 = 0。

## 6. 已知遗留
1. 同秒 tie-break（C2-A 既有问题，未修复）：测试用显式不同时间戳规避。
2. `done` 计入 evidence 并更新 `last_result`；`skipped` 两者皆不更新（既有语义，已按此验证）。
3. `activity_type` 双重含义（learning_record=行为；P1-07-C2 投影=资源类型），未统一。

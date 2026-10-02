# P1-01 · AI Question Library 最小数据模型设计

状态：**DESIGN_PASS（只设计，未实现）**

> 设计已经可以进入下一步实现，但本次**没有创建任何数据库表，也没有修改正式数据**。

---

## 产物

| 文件 | 内容 |
| --- | --- |
| `README.md` | 本索引 |
| `question_library_v1_design.md` | 完整设计说明（依据、实体、字段、生命周期、版本、复用、validator、字段取舍、汇总） |
| `question_library_schema.json` | 结构化 schema 草案（表 / 字段 / 主键 / 外键 / 索引 / 唯一约束 / JSON 字段） |
| `question_library_relationships.md` | 关系图与数据流（GenerationRun → AIQuestion → QuestionEvidence → 教材证据；AIQuestion → LearningRecord） |

---

## 推荐方案一句话

新建独立可写库 `structured/ai/question_library.db`，用 **6 张表**：

```text
generation_run           一次 AI 调用 = 一行（含 0 题的失败/拒答）
ai_question              题目实体，PK = (question_id, version)，版本只增不改
question_evidence        题目 ↔ 教材证据块（1:N）
question_learning_object 题目 ↔ LearningObject（1:N，接掌握度聚合的接缝）
question_validation      validator 结果（可重跑，历史并存）
question_event           生命周期 + 人工审核事件（append-only，权威来源）
```

---

## 五个关键设计判断

1. **`generation_run` 必须独立成表。**
   P0 实测一次调用产出 3 题（1450/1630），也实测过一次调用产出 **0 题**（1610 截断、1650 证据不足）。
   没有这张表，「同一批题同源」和「这个范围已经试过、结果是空的」都无法表达。

2. **题目的层级定位是“证据生产者”，不是学习对象。**
   项目自己的 `learning_model_v1.json` 已写明 Exercise/Question 不是学习对象；
   因此 AI 题目只通过 `question_learning_object` 声明“测哪个 LearningObject”，
   `learning_record.item_id` 与 `mastery_state.item_id` 的语义保持不变。

3. **P0 建议的 `reuse_key` 被修正为两个键。**

   ```text
   generation_scope_key = hash(section_id, activity_id, prompt_version, context_hash)
       → 挂在 generation_run：防止同一范围重复调用 AI（刻意不含 question_type）

   question_fingerprint = hash(section_id, activity_id, question_type,
                               normalized(question_text), normalized(evidence_quote))
       → 挂在 ai_question：题级去重 + REJECTED 抑制（刻意不含 prompt_version）
   ```

   原因：P0 的单个键既无法表达“一次调用出多题”，也无法拦住“被驳回的题换提示词再来”。

4. **`STALE` 不是生命周期状态。**
   生命周期用 `lifecycle_status`（7 个枚举）；`stale` + `stale_reason` 与它**正交**——
   一道 ACTIVE 题可以同时是 STALE。权威来源是 `question_event`，`lifecycle_status` 只是查询用物化字段。

5. **`EXACT` 陷阱写进模型，而不是留给记忆。**
   当 `answer_support_type = EXACT` 且答案文本同样出现在题干/选项中（即命中原因是“教材印着这个选项”），
   题库侧置 `needs_human_review = 1`，禁止走快通道。**不需要修改 validator v2。**

---

## 与 `learning.db` 的关系

- **本轮零改动。**
- 现状缺口：`learning_record` 无法回答“做的是哪一道题的哪个版本”。
- 推荐未来最小迁移（设计在此，**不在本轮执行**）：为 `learning_record` 增加三个可空列
  `source_kind` / `source_ref` / `source_version` + 一个索引。
- **阻断规则**：该迁移完成前，AI 题目不得进入孩子可见的学习流程（可以生成、校验、审核、入库）。

---

## 明确不做

- 未创建任何数据库表 / 数据库文件
- 未修改 `learning.db`、contentpack v5、`structured/` 正式数据、validator v2
- 未调用任何 AI（云端 0 / 本地 0）
- 未重新解析 PDF
- 未修改 Web / Android / V1.3 / V2.0
- 不设计“十几张表的完整宇宙”；不为“以后可能用”加字段

---

## 下一步（等待指令，不自行进入）

建议顺序：**P1-02 生命周期设计 → P1-03 缓存/复用键设计 → P1-04 质量门槛设计 → P1-05 复核界面设计**。
本设计中的第 13 节「待确认 / 风险」有 6 项需要在下游设计中定论。

# P1-07-C2 实施报告（归档）：LearningActivity 最小模型与消费接口
- 结论：**PASS**
- 归档时间：2026-09-12T16:46:09+08:00
- 性质：最小模型 + 消费接口实现（**只读派生投影，不新增数据库表**）

## 1. 关键前提（P1-04 的实际情况）
`docs/P1-04_教材内容数据模型设计_V1.md` **没有定义学习层 LearningActivity**——其中所有 `activity_id` 均指
**教材结构 Activity**（`<section_id>:A<number>`，L1 层）。唯一的 LearningActivity 线索是
`audit/P1-06-B1.10…md` 的设计提案（列为 P1），且 `audit/P1-06-B1.11…md` 明确“第一阶段无 Activity 实体”。
→ 按 P1-07-C2 §十二（无明确持久化要求时优先不新增表），实现为**只读派生投影**。

## 2. 修改 / 新增文件
| 文件 | 类型 | SHA256 |
| --- | --- | --- |
| learning/activity_service.py | 新增（5,664 B） | AAFF907C869797EE697D5F756C7E03C62CEB942809B2406933761195DA092028 |
| learning/test_activity_service.py | 新增（8,662 B） | 1501A6687ED83DAA…（见文件） |
未修改任何既有文件；未新增表/字段/索引。

## 3. 最小模型（字段全部来自既有结构，不新造命名体系）
```text
activity_id    ← 派生键 "<task_id>|<item_id>"（TaskItem 主键组合；不持久化）
activity_type  ← 复用 contentpack learning_item.item_type（vocabulary / phrase / sentence_pattern）
resource_id    ← learning_item.item_id（逻辑引用）
resource_type  ← 同 activity_type
item_id / task_id / ordinal / textbook_id / task_status ← learning_task / task_item 既有列
trace          ← {source: contentpack.learning_item, contentpack: v5, item_id, textbook_id}
```
**P1-04 未定义、故未实现**（不猜测）：`source_kind / prompt_ref / options_ref / answer_key_ref / status`，
以及任何 AI / mastery / review / question / difficulty / score / UI 状态字段。

## 4. 接口
```text
resolve_activity(conn, task_id, item_id, contentpack_path=…)   # TaskItem → LearningActivity
list_task_activities(conn, task_id, contentpack_path=…)        # 按 TaskItem.ordinal 排序
check_resource_type(resource_type)                             # 仅 vocabulary / phrase / sentence_pattern
```
校验：TaskItem 存在｜资源存在于 contentpack｜resource_type 合法｜resource_id 一致｜textbook_id 一致｜
不跨教材引用｜不写 contentpack｜不复制教材正文（投影不含任何正文/释义文本字段）。

## 5. 测试
```text
learning/test_activity_service.py：Ran 9 tests — OK（覆盖 §十五 19 项）
①–④ 三类资源解析 ⑤–⑧ 与 TaskItem 对应 / resource_id / resource_type / textbook_id
⑨ TaskItem 不存在 ⑩ 资源不存在 ⑪ 非法 resource_type ⑫ 跨教材不一致
⑯–⑱ AI=0 / 网络=0 / contentpack 未变 ⑲ 正式库未污染且无 learning_activity 表 ＋ schema 未变
回归：C1 14 · C2-A 10 · P1-07-C1 9 · P1-07-C2 9 全部 OK（连续 4 轮稳定）
```

## 6. 数据库 / 安全
```text
schema 变化：无（learning.db 仍 v2 / 7 表；无 learning_activity 表）
learning.db：DB97E460…311C（未变，业务表 0 行）｜contentpack：FF3FD568…452A（未变）
AI = 0 ｜ 网络 = 0 ｜ 测试隔离临时库并清理
```

## 7. 已知遗留
1. `activity_type` 双重含义（既有）：`learning_record.activity_type` = 学习行为；本投影的 `activity_type` = 资源类型。
   按 §九 未重命名、未统一、未重构。
2. LearningActivity 未持久化（无表）；若未来需要持久化，需先有正式设计（P1-04 目前无此定义）。

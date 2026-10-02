# P1-07-C1 实施报告（归档）：最小学习会话服务
- 结论：**PASS**
- 归档时间：2026-09-12T16:45:47+08:00
- 性质：学习层最小业务实现（Session 生命周期 + Session↔Task 组织）

## 1. 实现内容
**learning_session 表（learning.db v1 → v2，最小 schema 变更）**
```sql
CREATE TABLE learning_session (
  session_id  TEXT PRIMARY KEY,
  learner_id  TEXT NOT NULL REFERENCES learner(learner_id)   ON DELETE RESTRICT ON UPDATE CASCADE,
  started_at  TEXT NOT NULL,
  ended_at    TEXT,
  entry_point TEXT NOT NULL,
  task_id     TEXT NOT NULL REFERENCES learning_task(task_id) ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE INDEX idx_learning_session_learner ON learning_session(learner_id, started_at);
```
字段严格复用 P1-04 §23（session_id / learner_id / started_at / ended_at / entry_point，entry_point 枚举
unit / section / activity / vocabulary / listening / reading 不扩展）；**唯一新增字段 `task_id`**（P1-07-C1 §五要求）。

**服务接口（learning/session_service.py）**
```text
create_learning_session / get_learning_session / list_learning_sessions /
end_learning_session / get_session_task / list_session_items / record_session_event
```
一致性策略：沿用既有 create_task() 的独立事务（不重构 C1）；Session 插入失败时执行补偿清理（仅当该 Task 尚无 Record 时删除其 TaskItem 与 Task），不留孤立 Session / Task。

## 2. 修改 / 新增文件
| 文件 | 类型 | SHA256 |
| --- | --- | --- |
| structured/learning/migrate_learning_db_v2.py | 新增（5,043 B） | FCCFB2F3BC40783AE79233C0FE94D7E535FBCC47BBAF40C7D6F3ADE68B3A4302 |
| learning/session_service.py | 新增（8,629 B） | 0CF7A20615780831F544BDF295202028CE2EEFB15D234820CD1184AD4A6B665F |
| learning/test_session_service.py | 新增（13,185 B） | D905054F4B3F5F9D…（见文件；P1-08-C1 期间仅测试时间戳做了稳定性修正） |
| structured/learning/learning.db.bak-v1 | 新增（迁移前备份，73,728 B） | — |
未修改 learning_service.py / resource_pool_service.py / init_learning_db.py。

## 3. 数据库
```text
schema 变化：是（授权的最小变更）——新增 learning_session + 1 索引；既有 6 表未改
migration：新增 schema_migration v2 记录 + PRAGMA user_version = 2
learning.db：16E3952D…14E9（73,728 B / 6 表 / v1）→ DB97E460…311C（94,208 B / 7 表 / v2）
业务表行数：全部仍为 0 行；integrity_check = ok ｜ foreign_key_check = 0
contentpack：未变化
```

## 4. 测试
```text
learning/test_session_service.py：Ran 9 tests — OK（覆盖任务书 §十二 的 25 项：
创建/字段/entry_point/started_at/ended_at 空；Session↔Task↔TaskItem；跨 learner 隔离；
结束与重复结束拒绝、未知 Session；空 item_ids / 非法 entry_point / learner 不存在 / textbook 不匹配；
失败不留孤立 Session/Task（补偿清理）；闭环 Session→Task→TaskItem→Record→Mastery→池；安全项）
新增服务后完整回归：C1 14 · C2-A 10 · P1-07-C1 9 全部 OK
```

## 5. 安全
AI = 0 ｜ 网络 = 0 ｜ contentpack 未写入 ｜ 正式 learning.db 未被测试污染（测试用 %TEMP% 副本并清理）。

## 6. 已知遗留
1. `record_session_event` 采用“有 session 就必须有 task”的强绑定；会话结束后是否禁止继续记录**未定义**，本阶段不额外限制（由 Task 状态规则约束）。
2. 同秒 tie-break 问题（见 C2-A 报告遗留 2）。

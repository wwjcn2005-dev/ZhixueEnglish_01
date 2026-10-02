# P1-08-C · 人工审核 → APPROVED → ACTIVE 全流程实跑

阶段结论：**P1-08-C_PASS**（含 2 项显式记录的未验证/机制缺口，见报告 §9）

## 本目录内容

| 文件 | 说明 |
| --- | --- |
| `p1_08_c_report.md` | 本轮实施报告（回答任务书 §15 的 17 个问题） |
| `p1_08_c_audit.json` | 审计汇总：schema 一致性、完整性、拒绝性测试、ACTIVE 依赖/provenance、学习候选门槛 |
| `audit_before.json` | 执行前只读审计快照（schema SQL、行数、生命周期/事件分布、逐题依赖、孤儿检查） |
| `lifecycle_test_result.json` | 拒绝性测试与真实生命周期执行的原始记录（含回滚测试的原始报错） |
| `before_after_db_summary.json` | 执行前后行数、生命周期、事件与逐题差异 |
| `human_review_record.json` | 人工审核记录（Sample A 通过 / Sample B 驳回 / 其他样本状态） |
| `protect_before.json` / `protect_after.json` / `protected_assets_check.json` | 正式资产哈希清单与前后比对 |
| `audit_before.py` / `lifecycle_drill.py` / `verify_after.py` / `protect_snapshot.py` / `protect_compare.py` | 本轮脚本（全部位于本审计目录内） |

## 本轮实际写入

只对 `structured/ai/question_library.db` 少量既有测试题追加了 **3 条生命周期事件**：

```text
AIQ:BD59C5958D45  PENDING_REVIEW -> APPROVED -> ACTIVE   （REVIEW_APPROVED + ACTIVATED）
AIQ:1B3AF72923C4  PENDING_REVIEW -> REJECTED             （REVIEW_REJECTED, LOW_VALUE）
```

未修改 schema、未新增表/列、未删除任何事件、未写入 `learning.db`、未调用任何 AI。

## 执行方式

```powershell
python -X utf8 audit\AI_question_generation_spike\P1_08_C_lifecycle_run\audit_before.py
python -X utf8 audit\AI_question_generation_spike\P1_08_C_lifecycle_run\protect_snapshot.py before
python -X utf8 audit\AI_question_generation_spike\P1_08_C_lifecycle_run\lifecycle_drill.py
python -X utf8 audit\AI_question_generation_spike\P1_08_C_lifecycle_run\verify_after.py
python -X utf8 audit\AI_question_generation_spike\P1_08_C_lifecycle_run\protect_snapshot.py after
python -X utf8 audit\AI_question_generation_spike\P1_08_C_lifecycle_run\protect_compare.py
```

`lifecycle_drill.py` 中的拒绝性测试全部运行在显式事务里并强制 `ROLLBACK`，执行后已确认无 `PROBE` / `-TEST` 残留事件或残留题。

## 关键数字

```text
DB SHA256  before F74CA83F7C8A98F2A4A2E672E7BA61ECC34CBFC2338AC10064BF18C0FFD1FD6A
DB SHA256  after  7AA12CA5EB24417BF0AE7E97A8161920B501825D030D69A8E0863272AC695DA7

ai_question              21 -> 21
question_event           41 -> 44（+3）
generation_run           12 -> 12
question_evidence        22 -> 22
question_learning_object 37 -> 37
question_validation      21 -> 21

lifecycle  执行前 PENDING_REVIEW 21 / ACTIVE 0
           执行后 ACTIVE 1 / PENDING_REVIEW 19 / REJECTED 1

AI 调用 0 · 本地模型调用 0 · 正式资产变化 0（question_library.db 除外）
```

# P1-06-C2-A 实施报告（归档）
- 结论：**PASS**
- 归档时间：2026-09-12T16:45:47+08:00
- 性质：只读查询服务实施（本文件为对话报告的正式归档；归档动作本身不修改任何代码或数据）
- 完成时基线：learning.db v1（16E3952D…14E9 ｜ 73,728 B ｜ 6 表 ｜ 业务表 0 行）；contentpack v5 = FF3FD568…452A

## 1. 目标
建立“当前错误 / 当前薄弱资源池”的最小**只读**查询服务（不写库、不调用 AI、不改 C2 冻结规则）。

## 2. 修改 / 新增文件
| 文件 | 类型 | SHA256 |
| --- | --- | --- |
| learning/resource_pool_service.py | 新增（11,551 B） | D4488E1FFBA6B553EB6932BE195932A4C464D9526790B138C0C55DAA612D2F37 |
| learning/test_resource_pool_service.py | 新增（11,665 B） | 427A2C3D00CCE623…（见文件） |
未修改任何既有文件、未新增表/字段。

## 3. 接口
```text
list_current_issue_pool(conn, learner_id, textbook_id=None, contentpack_path=…, limit=None)
summarize_pool(conn, learner_id, textbook_id=None, contentpack_path=…)
get_item_pool_status(conn, learner_id, item_id, contentpack_path=…)
```

## 4. 判定规则（沿用 P1-06-C2 §5.2 冻结，未新增规则）
```text
参与判断：result ∈ {correct, incorrect, partial}（取该 (learner,item) 最近一条）
incorrect → current_error ｜ partial → current_weak ｜ correct → 退出池
done / skipped / NULL → 既不加入也不清除
历史 LearningRecord：append-only，永久保留
priority_score：派生排序键（current_error=2 / current_weak=1），非既有字段、非学习规则
输出字段：knowledge_id(=item_id) / knowledge_name(只读自 contentpack) / resource_type / textbook_id /
          unit_code / section_key / last_judged_* / 计数 / data_basis / data_sufficiency
```

## 5. 测试
```text
learning/test_resource_pool_service.py：Ran 10 tests — OK
① 空集合 ② 当前错误 ③ 历史错误被纠正→出池 ④ AI Training miss 语义（按 result 入池，无 AI 专属通道）
⑤ priority_score 与排序 ⑥ learner / 教材隔离 ⑦ 查询不写库（total_changes + 文件 SHA256 不变）
⑧ 无 AI/网络依赖 ⑨ 排序稳定（5 次一致） ⑩ 正式库与 contentpack 未污染
```

## 6. 数据安全
learning.db 未写入（业务表 0 行）｜contentpack 未写入｜AI = 0 ｜ 网络 = 0 ｜ 新增依赖 = 0

## 7. 已知遗留
1. `priority_score` 在本项目原本不存在，本服务以派生排序键实现（口径待确认）。
2. 同秒 tie-break：最新记录判定在 `created_at` 相同秒时以随机 `record_id` 排序（P1-08-C1 / P1-09-C1 期间确认），未在本阶段修复。
3. `unit_code / section_key` 由 contentpack 只读推导；词表位于附录页时 section 归属不适用（以页码与来源栏目为追溯依据）。

## 8. 归档时当前状态（供对照）
```text
learning.db = DB97E460CDEC59CDC27AD2CAF0CC8FDF671E4832BAC0A09E6CE9BB986A0C311C（v2 / 94,208 B / 7 表 / 业务表 0 行）
contentpack v5 = FF3FD568F4DA5348DB1F9DE7D68818CBEFD6A7E36A67C68EEF7F8386F4CE452A（未变）
```

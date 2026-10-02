# P1-11-C2 实施报告（归档）：Vocabulary「当前错误 / 当前薄弱」只读入口
- 结论：**PASS**
- 归档时间：2026-09-12T17:48:14+08:00
- 性质：Workbench 只读消费入口（首次在生产页面代码中消费 resource_pool_service）
- 前置：P1-11-C1 只读侦察 = READY，唯一推荐任务即本项

## 1. 目标流程（已实现）
```text
首页 / 结果页
  → 「看看我需要再学的词」（输入名字）
  → 当前需要再学（只读读取 resource_pool_service）
        ├─ 当前错误（上次回忆：忘了）
        └─ 当前薄弱（上次回忆：模糊）
  → 孩子自己点一个词（表单只带 名字 + item_id，**不需要重新输入单词**）
  → 既有 /start 流程（CORE 门禁 → Session → Task → TaskItem → Activity）
  → Study → Recall（记得/模糊/忘了）→ 结果页（不自动回池、不自动连学）
```

## 2. Pool Service 消费方式（§三十一）
```text
workbench/vocabulary_learning_v01.py:63    import resource_pool_service as pool
workbench/vocabulary_learning_v01.py:380   def build_pool_view(conn, learner_id, contentpack_path)
workbench/vocabulary_learning_v01.py:390       rows = pool.list_current_issue_pool(...)   ← 唯一调用点
```
- 不复制池逻辑：页面无 `SELECT learning_record`、无 incorrect/partial 判定、不重算 priority_score / last_judged_at
- 不重新排序：只按 Service 返回顺序分「当前错误 / 当前薄弱」两组，组内顺序原样保留
- 只读：`find_learner_by_name()` 只查既有 Learner（**不创建**），`/pool` 零写入

## 3. 入口与门禁
```text
POST /pool      → render_pool_page()                    （只读展示，:505 / :744）
POST /start     → 若带 item_id → _start_from_item()      （:800，池入口）
                → _begin_study()                        （:818，两条入口共用）
门禁：item_id → contentpack.learning_item → build_view() → require_core_vocabulary()
      （Vocabulary 仍走 CORE 门禁；短语/句型走各自 CORE 门禁；来自池不等于放宽）
解析失败：安全提示「这项内容当前不能从这个入口再次学习」，不崩溃、不删池数据、不给按钮
```

## 4. 状态迁移（临时库实测，全部由既有服务完成）
```text
current_error → 记得   → 出池
current_error → 模糊   → current_weak
current_weak  → 忘了   → current_error
current_weak  → 记得   → 出池
页面本身不改池：查看/显示释义/点击均零写入（测试断言业务表计数前后一致）
```

## 5. 修改 / 新增文件
| 文件 | 类型 | 大小 | SHA256 |
| --- | --- | --- | --- |
| workbench/vocabulary_learning_v01.py | 修改（新增池入口） | 51,773 B | 9F5F6EFB31EAB0CA7484A49CE602147B77BB70A0C3E5C31D5960BF9E8F798293 |
| workbench/test_vocabulary_learning_v01.py | 修改（新增 14 项） | 69,081 B | A32EB3E476F2EC4AFF8204C834F8BFAF4543B696ABAC441BC5ADDE6489D6A407 |

新增文件：0 ｜ 删除文件：0 ｜ `learning/*.py` 六个 service 全部未修改（SHA256 与冻结基线一致）。

## 6. 测试
```text
workbench/test_vocabulary_learning_v01.py：Ran 50 tests — OK（历史 36 + 新增 14）
PoolViewTest（6）：分组顺序；行内容与「再学这个词」表单（含 item_id / 无 word / 不泄漏内部字段）；
                  空状态措辞（无游戏化/掌握断言）；首页与结果页入口；混合资源类型；无推荐/计划/游戏化文案
PoolHttpTest（8）：池页只读（不创建 Learner、零写入）；error/weak/出池分组 + 真实音标释义；
                  排序完全复用 Pool Service；点词进学习（无 word 输入、Task/TaskItem 正常、correct 后出池）；
                  Learner 隔离；结果页→池页衔接；四种状态迁移；池入口不绕过 CORE 门禁
两轮全量回归：P1-06-C1 14 · P1-06-C2-A 10 · P1-07-C1 9 · P1-07-C2 9 · P1-08-C1 8 · P1-09-C1 8 · workbench 50
              → 连续 2 轮全部 OK（未修改任何历史测试）
```

## 7. 数据与安全
```text
learning.db    : DB97E460CDEC59CDC27AD2CAF0CC8FDF671E4832BAC0A09E6CE9BB986A0C311C（94,208 B / 7 表 / 业务表 0 行
                 / integrity_check=ok / foreign_key_check=0）——未变化
contentpack v5 : FF3FD568F4DA5348DB1F9DE7D68818CBEFD6A7E36A67C68EEF7F8386F4CE452A——只读，未写入
AI = 0 ｜ Network = 0 ｜ OCR = 0 ｜ TTS = 0 ｜ 新增依赖 = 0
测试隔离：全部使用 %TEMP% learning.db 副本；临时目录与字节码缓存已清理
```

## 8. 页面文案边界（已由测试锁定）
```text
空状态：当前没有需要再学的词。这里只显示最近一次回忆为「忘了」或「模糊」的词；没有这样的词时，这里就是空的。
说明  ：这里只列出你最近一次回忆为「忘了」或「模糊」的内容。要不要再学、先学哪一个，都由你自己决定；
        系统不会替你安排顺序，也不会自动开始。
禁止出现（测试断言）：系统推荐 / 最应该学习 / AI 推荐 / 今日任务 / 下一步学习 / 积分 / 排行榜 / 徽章 /
                    打卡 / 奖励 / 连胜 / 已掌握 / 恭喜 / 完美 / 100% / 全部掌握
```

## 9. 已知遗留（本轮未处理）
1. C2-A 同秒 tie-break：本轮实测到现实影响（同一秒两条判断记录时池的「最新一条」不稳定）；测试用 ≥1 秒间隔规避，未修复。
2. `meaning_zh` 去标点拼接（168/243）：池行按 §二十一 原样显示真实字段，未修。
3. Vocabulary 只显示第一条 source_ref（P2-3）：未扩大处理。
4. `attempt_no` 跨 Session 恒为 1（作用域含 task_id）：未处理，不影响池判定。
5. 池中可能出现非 Vocabulary 条目（如短语）：按「标注类型 + 同一 CORE 门禁 + 可点击」处理，未做类型过滤（不静默丢弃）。


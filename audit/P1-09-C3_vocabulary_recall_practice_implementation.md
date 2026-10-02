# P1-09-C3 实施报告（归档）：Vocabulary Recall 最小练习
- 结论：**PASS**
- 归档时间：2026-09-12T17:18:58+08:00
- 性质：在已冻结的 P1-09-C2 学习体验上追加最小 Recall 环节（自我回忆判断）
- 前置：P1-09-C3 只读设计侦察 = READY for implementation

## 1. 目标流程
```text
/start → 学习页
  → /study（记录 study · done；**Session 不结束**）
  → Recall 页（中文释义初始隐藏）
  → /recall（孩子主动「显示释义」：不产生 LearningRecord、不产生 practice）
  → /practice（记得 / 模糊 / 忘了 → 恰好一条 practice 记录）
  → end_learning_session()
  → 结果页（自评措辞）
```

## 2. 自评映射（底层协议 vs 界面措辞）
| 孩子点击 | LearningRecord | 当前资源池（复用 C2-A 规则） |
| --- | --- | --- |
| 记得 | practice · correct | 出池 |
| 模糊 | practice · partial | current_weak |
| 忘了 | practice · incorrect | current_error |

```text
界面只出现：记得 / 模糊 / 忘了
结果页文案：回忆：记得（practice · correct）
禁止文案：答对 / 答错 / 部分正确 / 系统判定 / 已掌握（测试强制校验）
本质：孩子自我回忆判断，不是系统客观判分；correct 不得表述为“已证明掌握”
```

## 3. 修改 / 新增文件
| 文件 | 类型 | 大小 | SHA256 |
| --- | --- | --- | --- |
| workbench/vocabulary_learning_v01.py | 修改（追加 C3） | 24,960 B | 596EB9CFA5EC37BC1ABFC0085EA14FD1D7527F00A8A89B20762B4AFE5601BD65 |
| workbench/test_vocabulary_learning_v01.py | 修改（新增 10 项 + 最小流程断言更正） | 25,977 B | DCB16EF542FD4E48337E44FF49B5C479CBD2723D5B796B8B121B43140288CB37 |

新增文件：0（未新建第二套 workbench）；删除文件：0；未修改 `learning/` 下任何 service。

## 4. 实现要点
```text
页面（workbench/vocabulary_learning_v01.py）
  RECALL_CHOICES / PRACTICE_RESULTS / RESULT_LABELS / RECALL_NOTE      :57 起
  render_recall_page(..., reveal=False|True)                            :201
  render_result_page(..., practice_record=None)                         :249
  路由 /recall（仅展示） /practice（唯一写入点）                          :322 / :324
  _study → 记录 study 后进入 Recall，不结束 Session                       :365 起
  _practice → practice + end_learning_session + 结果页；重复提交只读重放    :402
规则遵守
  不新增 activity_type（继续用 practice；未新增 recall）
  不新增表/字段/索引/migration；不自算 attempt_no（仍由 _next_attempt_no）
  一次点击 = 恰好一条判断记录；显示释义/停留/顺序/次数一律不推断结果
  Mastery 完全复用（mastery_level 保持 unknown，无掌握率/百分比算法）
  Resource Pool 完全复用（页面不重实现池逻辑，不自行查询 learning_record 判断错误）
  历史 LearningRecord append-only（只 INSERT，不 UPDATE/DELETE）
```

## 5. 测试
```text
workbench/test_vocabulary_learning_v01.py：Ran 20 tests — OK
新增 RecallRenderTest（5）：释义隐藏→显示、三自评按钮与措辞、结果页自评文案（禁用语校验）、
                          无 practice 的向后兼容、不泄漏内部技术字段
新增 RecallFlowTest（5）：显示释义零写入；自评恰一条并结束 Session（只 1 个 Session）；
                        partial→current_weak / incorrect→current_error；非法值 400 零写入；
                        重复提交不写第二条
回归（全绿）：P1-06-C1 14 · P1-06-C2-A 10 · P1-07-C1 9 · P1-07-C2 9 · P1-08-C1 8 · P1-09-C1 8
```

## 6. 数据库 / contentpack / 安全
```text
learning.db：DB97E460…311C（v2 / 94,208 B / 7 表 / 业务表 0 行）——未变化
contentpack v5：FF3FD568…452A（2,457,600 B / 21 表）——只读，未写入
冻结 service 未改动：learning_service / behavior_service / vocabulary_service /
                    resource_pool_service / session_service / activity_service（SHA256 与 C1 基线一致）
AI = 0 ｜ 网络 = 0 ｜ OCR/TTS = 0 ｜ 新增依赖 = 0
测试隔离：全部写入 %TEMP% 的 learning.db 副本；临时目录与字节码缓存已清理
```

## 7. 已知遗留（不在本轮处理）
1. 同秒 tie-break（C2-A 既有问题）：一次点击只写一条判断记录，故本轮风险可控，未修复。
2. 自评 ≠ 客观判分：correct 表示“孩子自评记得”，后续消费方与报告文案不得表述为“系统判定掌握”。
3. practice 仍无客观判分能力（无英文定义/例句/标准答案/options/grading logic；逐词官方音频 0 条）。
4. 任务书粘贴文本在 §二十二（Learner）处被截断；本轮按 §一～§二十二 + 项目既有测试/报告约定实施。
5. P1-09-C2 页面测试中“/study 直达结果页”的两条断言按 §十/§十一 做了最小更正（非新增功能）。


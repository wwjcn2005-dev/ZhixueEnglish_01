# P1-12-C3-C3 实施报告（归档）：Vocabulary 正式学习闭环
- 结论：**PASS + S24+ PASS**
- 归档时间：2026-09-12T18:52:12+08:00
- 性质：把已冻结的 Vocabulary 学习能力正式接入正式 Web UI（不含 Android 原生学习逻辑）
- 上游冻结：P1-09（Vocabulary 服务与体验规则）、P1-11（当前错误 / 当前薄弱）、P1-12-C3-A / C3-B（UI 规范与页面基线）

## 1. 目标链路（已实现）
```text
资源列表 / 需要再学 / 再学一次
  → POST /vocabulary/study        （start_vocabulary_study，entry_point=vocabulary）
  → Studio 页：「我看完了」→ POST /vocabulary/study/done （study / done，Session 保持打开）
  → Recall 页：释义默认隐藏 →「显示意思」（POST /vocabulary/recall/reveal，零记录）
  → 三选一 → POST /vocabulary/practice（practice / correct | partial | incorrect）
  → end_learning_session
  → Result 页（孩子语言；三个手动下一步）
```

## 2. 页面与路由
| 页面 / 动作 | 方法 | 路径 |
| --- | --- | --- |
| 进入 Study | POST | `/vocabulary/study`（表单只带公开短键 `pick`） |
| 07 Study →「我看完了」 | POST | `/vocabulary/study/done` |
| 08 Recall（刷新回放） | GET | `/vocabulary/recall` |
| Recall →「显示意思」 | POST | `/vocabulary/recall/reveal` |
| 09 Practice（三选一） | POST | `/vocabulary/practice` |
| 10 Result（刷新回放） | GET | `/vocabulary/result` |
| 需要再学（只读池入口） | GET / POST | `/review` |

页面只出现 **公开短键** `sha256(item_id)[:12]`；HTML 中**不出现任何数据库内部 ID**
（无 item_id / FLTRP-… / record_id）；Session 与 learner 仅以隐藏字段 + 内部 Cookie 传递，不展示给孩子。

## 3. 冻结语义（未被改动）
```text
我记得   → practice / correct
有点模糊 → practice / partial
忘了     → practice / incorrect
（不新增 recall activity_type；三选一只产生一条 practice 记录）
Session entry_point = vocabulary（未修改枚举）
```

## 4. 文件变更
| 文件 | 类型 | 大小 | SHA256 |
| --- | --- | --- | --- |
| web/app.py | 修改 | 22,742 B | F60243440BBF45237B71FF43836CA1F17923984CBED56C89F20DBE3EE05496BF |
| web/ui.py | 修改 | 26,192 B | 93289DDF2D00FF650F1CC1A759CDBE9BFCAC35BD9AE47403E8F8CAE53BE62EEC |
| web/content.py | 修改 | 12,372 B | D2B39BE321B027BD279919CF44009E42B32E4B18A86A6D1560B93F2634C9B787 |
| web/test_web_app.py | 修改（扩展 3 项） | 23,185 B | 2F7A131F0D5418D4660026CFBDC292EDD85906FC628EB58F06A1747A5C947B3D |
| web/flow.py | **新增**（闭环编排层） | 8,035 B | 863389AEBFCC1DF5514E268612B44EF68D15BD297D223B543EBA9AFF9BDFFFA3 |
| web/test_vocabulary_flow.py | **新增**（闭环测试 18 项） | 21,519 B | 613E0B70904E128EB12D2D89A944B414AE22ED8C931B667A1AE6C19DB82FD9F5 |

删除文件：0 ｜ Android 源码：未修改（URL 不变）

## 5. 复用情况
```text
编排层 flow.py（只编排，不复制业务规则；无任何 INSERT/UPDATE/DELETE）
  → vocabulary_service（CORE 门禁 + Session/Task/TaskItem + 行为记录）
  → session_service（Session 生命周期与归属校验）
  → behavior_service + learning_service（LearningRecord / Mastery 唯一写入口）
  → resource_pool_service（当前错误 / 当前薄弱，只读）
```
- 重复提交保护：Session 已结束时**只读回放**最新 practice 结果，不写第二条；「我看完了」同 Session 只写一条 study。
- 非法选项 → 自然语言页 + 零写入。

## 6. 测试
```text
web/test_web_app.py + web/test_vocabulary_flow.py : Ran 51 tests — OK
learning/test_*.py（6 套）                          : 58 tests — OK
workbench/test_*.py                                : Ran 50 tests — OK
合计 159 项全部通过
```
覆盖 §三十一 A–AD：Study/Recall/Practice/Result 全链路、三选一映射、一次一条 practice、
Session 生命周期、当前错误 / 当前薄弱 / 出池 / 再入池、重复提交、无效结果、异常页面、
内部枚举与 ID 不泄漏、正式库零污染、contentpack 未变、无 AI/TTS/OCR/网络调用、
冻结服务 SHA 不变、原 C3-C1 与 C3-C2 测试继续通过。

## 7. S24+ 真机验证（使用显式测试库副本）
```text
GET  /                                         200  （首页）
GET  /textbook                                 200  （教材中心）
GET  /unit/unit1                               200  （Unit 页面）
GET  /unit/unit1/resources/vocabulary          200  （词汇列表）
POST /vocabulary/study                         200  （进入 Study）
POST /vocabulary/study/done                    200  （我看完了 → Recall）
POST /vocabulary/recall/reveal                 200  （显示意思，零记录）
POST /vocabulary/practice                      200  （选择「忘了」→ Result）
测试库结果：learner=王彬彬；2 个 Session（entry_point=vocabulary，其一已结束）；
           记录 study/done、practice/incorrect、study/done；mastery_state evidence=3
```
真机验证结束后：Web 服务已停止（8770 端口释放）、测试库副本与临时文件已删除、**正式 learning.db 未被写入**。

## 8. 数据与安全
```text
learning.db    : DB97E460CDEC59CDC27AD2CAF0CC8FDF671E4832BAC0A09E6CE9BB986A0C311C（94,208 B / 7 表 / 业务表 0 行
                 / integrity_check=ok / foreign_key_check=0）——未变化
contentpack v5 : FF3FD568F4DA5348DB1F9DE7D68818CBEFD6A7E36A67C68EEF7F8386F4CE452A——只读，未写入
冻结 learning/*.py：六个服务 SHA256 全部与基线一致
AI = 0 ｜ Network = 0 ｜ OCR = 0 ｜ TTS = 0 ｜ 新增依赖 = 0 ｜ 新增表/字段 = 0
Android APK：gradlew assembleDebug --offline → BUILD SUCCESSFUL（app-debug.apk 10,862,249 B，未变）
```

## 9. 已知遗留（本轮未处理）
1. **仍不是独立运行 APK**：页面与数据由电脑上的正式 Web 服务提供，Android 壳通过 WebView 访问（未内嵌 Python、未打包离线数据）。
2. `meaning_zh` 去标点拼接（168/243）——按 §二十一 未修，独立任务。
3. C2-A 同秒 tie-break——测试用 ≥1 秒间隔规避，未修复。
4. Vocabulary 只显示第一条 source_ref（P2-3）——未扩大处理。
5. Phrase / Sentence Pattern 的正式学习入口——本阶段明确不进入。


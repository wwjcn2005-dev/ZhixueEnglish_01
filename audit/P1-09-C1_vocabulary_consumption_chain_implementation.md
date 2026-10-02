# P1-09-C1 实施报告（归档）：Vocabulary 最小学习消费链路
- 结论：**PASS**
- 归档时间：2026-09-12T16:46:09+08:00
- 性质：第一条“孩子可实际消费教材资源”的最小后端链路

## 1. 目标链路
```text
孩子主动选一个核心 Vocabulary
  → 核心校验（CORE）
  → LearningSession → LearningTask → TaskItem
  → LearningActivity（P1-07-C2 投影）
  → study / practice（P1-08-C1 协议）
  → LearningRecord（唯一写入口 record_learning_event）
  → MasteryState → 当前错误/薄弱池（C2-A 只读重算）
```

## 2. 核心 Vocabulary 的机器识别依据（非猜测）
```text
依据：learning_item.learning_requirement = 'CORE'
来源链：source_ref.textbook_emphasis = 'BOLD'（字体 FrutigerNextLTW1G-Medium）
        ← P1-06-B1.7-D 回填；PLAIN（FrutigerNextLTW1G-Regula）→ RECOGNITION
v5 分布：CORE 243 ｜ RECOGNITION 43 ｜ NEED_REVIEW 1（peaceful，来源冲突）
规则：CORE 允许进入核心链路；RECOGNITION（认识即可）与 NEED_REVIEW 一律拒绝
实证：CORE `ready`（BOLD / Words and expressions / p.150）；RECOGNITION `textbook`（PLAIN）；NEED_REVIEW `peaceful`
```

## 3. 修改 / 新增文件
| 文件 | 类型 | SHA256 |
| --- | --- | --- |
| learning/vocabulary_service.py | 新增（8,665 B） | D06DCC76A5A4CCAF5C0BC3C17BB33CFF5D6056B7C872406A3934223C8870D632 |
| learning/test_vocabulary_service.py | 新增（15,269 B） | 453A52FABD581464…（见文件） |
未修改任何既有文件；未新增表/字段/索引。

## 4. 接口
```text
get_vocabulary(item_id, contentpack_path=…)            # 读取 + 核心/非核心判定 + 教材追溯
is_core_vocabulary(item_id, …)
require_core_vocabulary(item_id, …)                    # 非核心 → 明确拒绝
start_vocabulary_study(conn, learner_id, item_id, entry_point="vocabulary", …)
record_vocabulary_study(conn, session_id, item_id, learner_id=None, result="done", …)
record_vocabulary_practice(conn, session_id, item_id, result=None, learner_id=None, …)
```
薄编排层：不复制 Record/Mastery/池逻辑；不自动选词、不自动推进下一个词、不引入打卡/积分/排行榜；
practice 的结果必须由调用方或既有判断链路提供（系统无可靠判断依据时不得自动判定 correct）。

## 5. 测试
```text
learning/test_vocabulary_service.py：Ran 8 tests — OK（覆盖 §十 9 组）
① 核心全链路（解析→Session→Task→TaskItem→Activity→study→Record→Mastery→不入池）
② 非核心（RECOGNITION / NEED_REVIEW / 非 vocabulary / 不存在资源）拒绝且不留记录
③ study=done/skipped、对错结果被拒、不入池
④ practice correct/incorrect/partial（attempt_no 1/2/3；最后 correct → 出池；历史 3 条保留）
⑤ partial→current_weak；随后 incorrect→current_error
⑥ learner 隔离（记录/掌握/池/跨 learner 操作）⑦ schema 未变（v2、7 表）⑧ contentpack 与正式库未污染 ⑨ AI=0/网络=0
回归（连续 2 轮）：C1 14 · C2-A 10 · P1-07-C1 9 · P1-07-C2 9 · P1-08-C1 8 · P1-09-C1 8 全部 OK
```

## 6. 数据库 / contentpack / 安全
```text
learning.db：DB97E460…311C（v2 / 94,208 B / 7 表 / 业务表 0 行 / integrity ok / FK 0）——未变化
contentpack v5：FF3FD568…452A（2,457,600 B / 21 表）——未写入
AI = 0 ｜ 网络 = 0 ｜ 新增依赖 = 0 ｜ 测试隔离 %TEMP% 副本并清理
```

## 7. 已知遗留
1. 同秒 tie-break（C2-A 既有问题，未修复；测试用显式不同时间戳规避）。
2. `activity_type` 双重含义（learning_record=行为；P1-07-C2 投影=资源类型），未统一。
3. 词表位于附录页，parser 的 section 归属不适用于词表 → 追溯以 `emphasis_source_list` + 页码 + 字体为依据。
4. practice 的自动判分未实现（结果由调用方/既有判断链路提供）。

# P3-07 重新设计只读审计：教材跟读句精选 + 原声整句区间审核

> 只读审计。本报告只新增一个 audit 文件；本轮未修改代码、数据库、Spike、learning.db、contentpack、Android、原始教材或原始 MP3；未运行 Whisper/ASR；AI/cloud calls = 0。

## 1. 当前 P3-07 状态

当前 P3-07 已经实现的是“逐词时间戳标注 Spike”，但这项方向现已正式废弃。

| 项目 | 当前状态 |
| --- | --- |
| Spike 目录 | `D:\ZhixueEnglish\p3_07_audio_annotation_spike\` |
| Spike 服务 | 已可运行，端口 8781 |
| 当前候选清单 | 93 条句子工作项 |
| 当前 UI 核心 | 波形 + 逐词 token 编辑 |
| 正式内容库 | 已新增 `audio_sentence_annotation`、`audio_token_annotation` |
| 正式 VERIFIED 数据 | 0 |
| 正式 token 数据 | 0 |
| 人工 10 条体验验证 | 未完成 |

结论：旧方向只完成了工具骨架，没有产生正式业务数据；可以安全改向，不必保留“逐词标注”工作流。

## 2. 当前 93 个候选的来源

当前候选清单：

```text
D:\ZhixueEnglish\p3_07_audio_annotation_spike\data\candidates.json
```

来源统计：

| 来源 | 数量 |
| --- | ---: |
| P3-06 Step 9 / Step 10A B 类句槽 | 70（去重后） |
| AU13 对话句 | 9 |
| AU13 书信正文句 | 14 |
| **合计** | **93** |

在此之前：

```text
含已 VERIFIED 候选：101
排除 AU06 VERIFIED：8
实际进入 P3-07：93
```

这 93 条只是“现有候选集合”，不是必须全部审核或收录的集合。

## 3. 当前候选字段完整性

当前候选字段完整性：

| 字段 | 状态 |
| --- | --- |
| `candidate_id` | 93/93 存在 |
| `sentence_text` | 29/93 存在；64/93 为 null，只剩 `prompt_text` / fragment |
| `audio_id` | 93/93 存在 |
| `original_audio_path` | 93/93 存在 |
| `unit` | 93/93 存在 |
| `activity` | 93/93 存在 |
| `chapter` | 没有独立字段，目前只能由 unit / module 近似表达 |
| `selection_reason` | 不存在 |
| `pattern_key` / 表达模板标识 | 不存在 |
| `existing_sentence_timing` | 15/93 存在，但都不是 VERIFIED 金标准 |
| `existing_tokens` | 仅 AU11 6 条有 Step 10B2 候选 token 时间 |

关键问题：

> 64/93 当前并没有完整 `sentence_text`，只是待恢复 fragment。这些不能直接进入整句音频定位阶段，必须先经过教师筛选和文本完整化。

## 4. 当前 Spike 结构

当前目录：

```text
p3_07_audio_annotation_spike/
  app.py
  generate_candidates.py
  init_formal_schema.py
  data/candidates.json
  static/index.html
  static/app.js
  static/style.css
```

当前运行方式：

```text
http://127.0.0.1:8781/
http://192.168.2.3:8781/
```

当前后端提供：

- 候选清单 API
- 原始 MP3 只读 Range 服务
- 草稿保存 API
- VERIFIED 事务写 contentpack 的入口

当前前端提供：

- 波形解码和峰值绘制
- 长时间轴视图
- 缩放
- 点击定位
- 播放/暂停
- 逐词 token 列表
- token start/end 编辑
- 单词区间播放
- 上/下一句
- 快捷键

## 5. 哪些代码可以复用

建议保留并复用：

| 组件 | 复用方式 |
| --- | --- |
| `app.py` 的 MP3 解析与 Range 服务 | 直接复用，改为只服务整句审核台 |
| `app.py` 的候选加载与草稿保存 | 直接复用 |
| `app.py` 的正式库事务写入 | 复用框架，改为只写句子表 |
| `app.js` 的 `computePeaks` | 直接复用 |
| `app.js` 的 Canvas 波形绘制 | 复用，删除 token 颜色块 |
| 时间轴缩放 / 点击 / 播放头 | 直接复用 |
| 上/下一句、快捷键、Save 模式 | 复用 |
| 候选跳转列表 | 复用，增加筛选状态 |

这些能力的复用价值很高，不需要重新写播放器和波形基础层。

## 6. 哪些逐词逻辑不再需要

新目标下应删除或停用：

| 旧逻辑 | 处理建议 |
| --- | --- |
| `audio_token_annotation` 写入 | 停用 |
| token count / token overlap 校验 | 删除 |
| token 列表 UI | 删除 |
| `selectedToken` | 删除 |
| `playToken` | 删除 |
| `retokenize` | 删除 |
| token start/end 输入框 | 删除 |
| Step 10B2 token 预填作为主要数据 | 只保留为“起始参考”，不作为正式结构 |

替换为：

- 单一 `start_ms`
- 单一 `end_ms`
- 一个可拖动整句区间
- 试听整句
- 保存 / 舍弃

## 7. 当前正式数据库结构

正式内容库：

```text
D:\ZhixueEnglish\structured\contentpack\v5\FLTRP-EN-7A-2022CUR.sqlite
```

现有 P3-07 表：

### `audio_sentence_annotation`

当前行数：

```text
0
```

已有字段：

```text
sentence_uid, textbook_id, snapshot_id, audio_id, unit, activity,
source_page, sentence_index, sentence_text, source_text,
start_ms, end_ms, status, origin, review_status,
reviewed_by, reviewed_at, source_json, created_at, updated_at
```

### `audio_token_annotation`

当前行数：

```text
0
```

字段为 token 级时间戳设计，新方案不再需要。

### 当前状态约束问题

`audio_sentence_annotation.status` 当前允许：

```text
CANDIDATE / AUTO / CORRECTED / VERIFIED
```

不允许：

```text
REJECTED
```

这与新方案的“人工舍弃”状态不匹配。

## 8. `audio_sentence_annotation` 是否足够

结论：

> **主体足够，但需要最小迁移。**

主体字段已经覆盖：

- sentence id
- audio id
- sentence text
- start/end
- status
- origin
- review status

缺少的是教师筛选相关信息：

| 需要的字段 | 用途 |
| --- | --- |
| `selection_reason` | 为什么值得跟读 |
| `reject_reason` | 为什么被舍去 |
| `pattern_key` | 用于判断句型重复 |
| `function_tag` | 用于判断交际功能重复 |
| `status = REJECTED` | 记录舍弃状态 |

最小修改建议：

1. 在 `audio_sentence_annotation` 增加 `selection_reason`、`reject_reason`、`pattern_key`、`function_tag`。
2. 将 `status` 的 CHECK 扩展为包含 `REJECTED`。
3. 保持 token 表不动，先停用，不写入。

## 9. `audio_token_annotation` 后续是否可以废弃

可以废弃。

理由：

- 当前行数为 0。
- 新方案只记录整句 `start_ms / end_ms`。
- 没有任何 VERIFIED 数据依赖 token 表。
- 唯一关系是 token → sentence 的外键，不反向影响 sentence 数据。

但本次只读审计不删除。后续最小实施时，只有在代码已经完全停止使用 token 表后，才允许由单独迁移步骤删除。

## 10. 新的“跟读句筛选标准”

筛选问题不是“音频里有没有这句话”，而是：

> **这句话是否值得初中生反复听、模仿、跟读？**

保留优先级：

| 优先级 | 标准 | 例子方向 |
| --- | --- | --- |
| 1 | 典型句型，可迁移 | `What are you going to do ...?` |
| 2 | 真实交际价值 | 问答、请求、建议、观点、回应 |
| 3 | 语音模仿价值 | 连读、弱读、重音、节奏、语调、自然语速 |
| 4 | 核心语法结构 | 教材语法目标中的典型结构 |
| 5 | 句子完整 | 有明确意义，可独立跟读 |
| 6 | 教材代表性 | 与当前单元目标直接相关 |

排除：

- 纯信息填充
- 没有特殊学习价值的普通陈述
- 过短、过于简单的功能性话语
- 与已有跟读句高度重复
- 同一结构大量重复，只保留最有代表性的版本
- 仅因为“音频里存在”而保留

不设每个音频的配额。

## 11. “价值重复”的判断建议

不能只比较字符串相等。最小可执行方案：

### 第 1 层：标准文本重复

归一化后比较：

```text
小写
去首尾空格
统一弯引号
折叠连续空格
```

完全相同的句子只保留一条。

### 第 2 层：句型 fingerprint

为人工维护一个轻量 `pattern_key`，例如：

```text
WHAT_ARE_YOU_GOING_TO_DO
HOW_CAN_THEY_MAKE_GOOD_USE_OF
THERE_IS_ARE
I_WANT_TO
CAN_YOU
```

同一 `pattern_key` 的句子进入人工复核，不自动删除。

### 第 3 层：交际功能标签

最少先支持：

```text
ask_question
answer_question
request
suggestion
opinion
response
advice
description
```

同句型 + 同功能 + 同教材目的的句子，只保留最有代表性的一条。

### 第 4 层：人工决策

重复项不能自动删除，必须由人工在筛选界面将其标为：

```text
REJECTED
reject_reason = duplicate
duplicate_of = <sentence_id>
```

## 12. 新 UI 最小改造方案

建议把当前 Spike 拆成两个界面模式，而不是重写框架。

### 模式 A：内容筛选台

每条只显示：

```text
sentence_id
完整句 / 待恢复文本
audio_id
unit / activity
已有跟读素材中是否有高度相似项
selection_reason 选择
pattern_key / function_tag
```

操作：

```text
KEEP_CANDIDATE
REJECTED
DUPLICATE
```

此界面不显示长波形，避免人工在筛选阶段被时间定位干扰。

### 模式 B：整句音频定位台

只处理筛选通过的句子：

```text
当前句子
长波形
start 手柄
end 手柄
播放当前区间
播放当前时间附近
上一句 / 下一句
保存 VERIFIED
标记 REJECTED
```

移除所有 token 行。

保留：

- 真实波形
- 时间轴
- 缩放
- 播放头
- 候选跳转
- 快捷键
- Range 音频

## 13. 筛选阶段与定位阶段的工作流

### 阶段 A：内容筛选

问题：

> 这句话值得孩子跟读吗？

输出：

```text
KEEP_CANDIDATE
selection_reason
pattern_key
function_tag
```

或：

```text
REJECTED
reject_reason
duplicate_of
```

### 阶段 B：音频定位

问题：

> 这句话在原始 MP3 中从哪里开始，到哪里结束？

只对 `KEEP_CANDIDATE` 做：

```text
拖动 start
拖动 end
反复试听
保存
VERIFIED
```

两个阶段分开后，未入选的句子不会进入波形定位，人工工作量会显著下降。

## 14. 预计最终人工工作量如何下降

当前旧方案：

```text
93 个句子
× 每句可能 5–15 个 token
× 每个 token 两次拖动/输入
≈ 数百次细粒度操作
```

新方案：

```text
93 个候选
↓ 教师筛选
只对 KEEP 句子做整句 start/end
```

工作量下降来自：

1. 不再逐词定位。
2. 先筛选，再定位；排除的句子完全不进入波形阶段。
3. 重复句型先合并，只保留代表句。
4. 一个音频没有价值时，可以整体舍弃。

不预设最终保留数量。93 可能变成 60、50、30，均以教学价值为准。

## 15. 最小实施步骤

建议下一步只做以下最小改造：

1. 迁移 `audio_sentence_annotation`：
   - 增加 `selection_reason`
   - 增加 `reject_reason`
   - 增加 `pattern_key`
   - 增加 `function_tag`
   - status 支持 `REJECTED`
2. 生成新的“句子候选清单”：
   - 保留 sentence text / fragment
   - 删除 token 数组
   - 增加筛选状态
3. 改造当前 Spike：
   - 增加内容筛选模式
   - 将定位模式改成单区间 start/end
   - 删除 token UI 和 token DB 写入
4. 先用 10 条做人工体验验证：
   - 筛选 10 条
   - 对其中的 KEEP 候选完成整句定位
5. 验证通过后：
   - 才处理剩余候选
   - 只将人工确认的句子写为 VERIFIED

## 16. 风险

| 风险 | 说明 | 缓解 |
| --- | --- | --- |
| 64/93 无完整 `sentence_text` | 仍是 fragment | 筛选阶段先做文本完整化 |
| 价值判断主观 | 不同教师可能取舍不同 | 固定 rubric + selection_reason |
| 句型重复难自动判断 | 不能只依靠字符串 | pattern_key + 人工复核 |
| 当前 token 代码仍可写入 | 改向前可能误操作 | 先停用 token 写路径 |
| 当前正式表缺少 REJECTED | 语义不完整 | 最小迁移 status |
| 音频边界质量标准 | 不能追求数学零误差 | 以孩子能否自然跟读为准 |
| 当前 Spike 仍在运行 | 旧 UI 仍可访问 | 仅作为只读审计现状，不写入正式数据 |

## 17. 安全检查结果

```text
AI 调用次数 = 0
ASR 调用次数 = 0
Whisper 调用 = 0
learning.db = unchanged
Android = unchanged
original MP3 = unchanged
formal learning logic = unchanged
contentpack 修改 = 0（本轮只读）
新建业务表 = 0
插入正式数据 = 0
删除文件 = 0
代码修改 = 0
```

当前正式表状态：

```text
audio_sentence_annotation 行数 = 0
audio_token_annotation 行数 = 0
VERIFIED 正式数据 = 0
```

## 18. 最终结论

```text
PASS — 可以进入最小实施
```

可以进入最小实施的前提是：

1. 正式方向改为“教材跟读句精选 + 原声整句区间审核”。
2. 停用逐词 token 业务。
3. 把内容筛选和音频定位拆成两个阶段。
4. 对 `audio_sentence_annotation` 做最小字段迁移。
5. 先完成 10 条人工筛选 + 整句定位体验验证，再批量处理。

本报告只读完成，不进入实施。

# P3-07 音频波形人工标注工作台实施报告

## 1. 项目侦察

### 1.1 技术栈

- Web：Python 标准库 HTTP 服务
- 前端：原生 HTML / CSS / JavaScript
- 正式内容库：`structured/contentpack/v5/FLTRP-EN-7A-2022CUR.sqlite`
- 学习数据：`structured/learning/learning.db`（本阶段不使用、不写入）
- 音频：原始 MP3，只读

### 1.2 音频资源

| 项目 | 数量 |
| --- | ---: |
| 原始 MP3 总数 | 54 |
| 正式活动音频 | 47（AU01–AU47） |
| 词汇音频 | 7（AU48–AU54，不进入本阶段） |
| MP3 总大小 | 117,232,946 B |
| 音频总时长 | 4,882,705 ms |

原始音频目录：

```text
D:\ZhixueEnglish\2025年度初一外研版英语教材\
```

### 1.3 候选统计

```text
候选总数（含已 VERIFIED）：101
排除已有 VERIFIED：8（AU06）
实际进入 P3-07：93
上限：100
```

93 条候选构成：

| 来源 | 数量 |
| --- | ---: |
| Step 9 / Step 10A B 类句子候选 | 70 |
| AU13 对话句 | 9 |
| AU13 书信正文句 | 14 |
| **合计** | **93** |

去重说明：

- 同一句含多个空槽时，只建立一个 P3-07 句子标注任务。
- 原始 76 个 B 类槽去重后为 70 个句子工作项。
- 候选清单中无重复 ID，无重复 `(audio_id, sentence_text)`。

候选清单：

```text
D:\ZhixueEnglish\p3_07_audio_annotation_spike\data\candidates.json
```

## 2. 工具实现

隔离 Spike 目录：

```text
D:\ZhixueEnglish\p3_07_audio_annotation_spike\
```

已实现：

| 功能 | 状态 |
| --- | --- |
| 真实音频波形 | 已实现（Canvas + Web Audio 解码） |
| 长时间轴 | 已实现，横向占满页面 |
| 全局 / 放大 / 缩小 | 已实现 |
| 点击波形跳转 | 已实现 |
| 播放头拖动 | 已实现 |
| 波形区间选择 | 已实现 |
| 单词级标注 | 已实现 |
| token start/end 编辑 | 已实现 |
| 播放当前句 / 当前词 | 已实现 |
| 完整音频播放 | 已实现 |
| 0.75x / 1.0x / 1.25x | 已实现 |
| 快捷键 | Space / ← / → / Enter / ↑ / ↓ |
| 上一句 / 下一句 | 已实现 |
| CANDIDATE 草稿保存 | 已实现 |
| VERIFIED 事务入库 | 已实现，待人工验证触发 |
| 候选跳转列表 | 已实现 |

运行地址：

```text
本机：http://127.0.0.1:8781/
局域网：http://192.168.2.3:8781/
```

原始音频通过：

```text
/audio/<AUxx>.mp3
```

服务端支持 HTTP Range；原始 MP3 未被切分、转码或复制。

## 3. 正式数据结构

正式内容库：

```text
D:\ZhixueEnglish\structured\contentpack\v5\FLTRP-EN-7A-2022CUR.sqlite
```

现有可复用表：

```text
audio_asset
audio_mapping
content_block
activity
page
transcript（空表）
```

缺少适合持久化“句子级 / token 级人工时间戳”的正式结构，因此新增两张最小正式表：

### 3.1 `audio_sentence_annotation`

用途：保存句子级标注和审核状态。

关键字段：

```text
sentence_uid
textbook_id
audio_id
unit
activity
source_page
sentence_index
sentence_text
source_text
start_ms
end_ms
status
origin
review_status
reviewed_by
reviewed_at
source_json
created_at
updated_at
```

### 3.2 `audio_token_annotation`

用途：保存单词级 token 时间戳。

关键字段：

```text
token_uid
sentence_uid
token_index
token
start_ms
end_ms
status
origin
source
created_at
updated_at
```

关联关系：

```text
audio_token_annotation.sentence_uid
    → audio_sentence_annotation.sentence_uid
    ON DELETE CASCADE
```

为什么不会影响学习数据：

- 两张表均在正式内容库，不在 `learning.db`。
- 不写入学习记录、掌握度、错题、复习或用户行为。
- Spike 服务不打开 `learning.db`。

数据库变更：

```text
contentpack SHA256 前：ACEBC8C29CF5D11BAB50BF7962FBEE5DE42CD9CFC7FE48AB6316699D265E1A3F
contentpack SHA256 后：DCB8B69551C584B575DEAEB8EE66C891D8BAA6172BC690AD5203D3C11AE25578
```

这是新增两张空表导致的预期变化。

## 4. 正式入库结果

```text
VERIFIED 句子：0
VERIFIED token：0
新增内容数据库记录：0
audio_sentence_annotation 行数：0
audio_token_annotation 行数：0
```

原因：

> P3-07 的第 ⑦ 步要求先实际完成 10 条人工体验验证。该步骤必须由人真实听证并操作波形工具，不能在当前自动执行环境中伪造或代替。

## 5. 10 条体验验证

```text
状态：NOT RUN / AWAITING HUMAN
```

已选 10 条代表样本：

```text
AU01-B01
AU02-B01
AU03-B01
AU11-B01
AU12-B01
AU19-B01
AU25-B01
AU32-B01
AU39-B01
AU13-DLG-01
```

工具已准备好，但这 10 条尚未由人实际播放、拖动波形、确认边界和保存。

因此不能宣布：

```text
10 条体验验证 PASS
```

也不能继续第 ⑧ 步“修工具”或第 ⑨ 步“正式人工标注”，直到人工验证完成。

## 6. 数据质量检查（当前状态）

候选清单：

```text
候选数：93
唯一 candidate_id：93
重复 candidate_id：0
重复 (audio_id, sentence_text)：0
空句子 / 空 prompt：0
已有 sentence timing：15
已有 token timing：6（AU11 Step 10B2 CANDIDATE）
```

正式表：

```text
缺 token：0（表为空）
start/end 反向：0
超出音频长度：0
重叠：0
空 token：0
重复 sentence_uid：0
重复标注：0
```

注意：这些都因为正式表尚未写入人工 VERIFIED 数据；不代表 93 条已完成质量验收。

## 7. 污染检查

```text
learning.db：未修改（SHA256 0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91）
正式学习逻辑：未修改
Android：未修改
原始 MP3：未修改
原始教材：未修改
AI 调用：0
ASR：0（P3-07 未运行任何 ASR / Whisper）
音频切片：0
```

正式内容库发生了已授权的 P3-07 schema 变更：

```text
新增 audio_sentence_annotation
新增 audio_token_annotation
不新增任何业务行
```

## 8. 下一阶段建议

当前不能判断“100 条或实际全部候选已经足够稳定”，因为 93 条中尚未完成任何 P3-07 人工金标准标注。

下一步唯一合理动作：

1. 人工打开 `http://192.168.2.3:8781/`；
2. 完成上面 10 条代表样本的波形标注体验验证；
3. 检查波形长度、缩放、拖动、保存和入库；
4. 如果验证通过，再继续剩余 83 条；
5. 如果失败，优先修工具，不继续批量标注。

## 9. 当前阶段状态

```text
P3-07 implementation: PARTIAL PASS
Waveform tool: READY
Candidate manifest: READY (93)
Formal schema: READY (2 tables, 0 rows)
Human 10-item validation: NOT RUN / BLOCKED
VERIFIED database ingest: 0
```

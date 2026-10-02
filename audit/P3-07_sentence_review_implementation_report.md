# P3-07 跟读句精选 + 原声整句区间审核：最小实施报告

## 1. 修改了哪些文件

本轮修改均限于隔离 Spike 和正式内容库的 P3-07 schema：

| 文件/对象 | 变更 |
| --- | --- |
| `p3_07_audio_annotation_spike/init_formal_schema.py` | 改为句子级 schema 迁移；status 支持 CANDIDATE / VERIFIED / REJECTED |
| `p3_07_audio_annotation_spike/generate_candidates.py` | 生成 93 条句子筛选候选；删除 token 字段 |
| `p3_07_audio_annotation_spike/data/candidates.json` | 93 条筛选候选清单 |
| `p3_07_audio_annotation_spike/app.py` | 删除 token 写入；改为句子级保存事务 |
| `p3_07_audio_annotation_spike/static/index.html` | 新增教师筛选台 + 整句定位台 |
| `p3_07_audio_annotation_spike/static/app.js` | 删除逐词逻辑；新增筛选与整句 Start/End |
| `p3_07_audio_annotation_spike/static/style.css` | 更新为双工作流布局 |
| `structured/contentpack/v5/...sqlite` | 仅迁移 `audio_sentence_annotation`；未写入业务行 |

## 2. Schema 修改

正式内容库：

```text
D:\ZhixueEnglish\structured\contentpack\v5\FLTRP-EN-7A-2022CUR.sqlite
```

`audio_sentence_annotation` 最小迁移后支持：

```text
sentence_uid
audio_id
unit
chapter
activity
source_page
sentence_text
source_text
context_text
start_ms
end_ms
status = CANDIDATE / VERIFIED / REJECTED
selection_reason
reject_reason
pattern_key
function_tag
duplicate_of
review_status
reviewed_by / reviewed_at
```

数值约束：

```text
start_ms >= 0
end_ms > 0
start_ms < end_ms（当两者都存在时）
```

README 中保留的 `audio_token_annotation` 表：

```text
未删除
未写入
未使用
仍为空表
```

schema 变更结果：

```text
contentpack SHA256 前：DCB8B69551C584B575DEAEB8EE66C891D8BAA6172BC690AD5203D3C11AE25578
contentpack SHA256 后：22DB15AF39FC40D1F1A1612A84C093843CB27EF9D239CB3608D3A4367E549DCA
```

## 3. 93 条候选如何进入筛选

候选清单：

```text
p3_07_audio_annotation_spike/data/candidates.json
```

候选来源：

| 来源 | 数量 |
| --- | ---: |
| B 类句子候选（去重后） | 70 |
| AU13 对话句 | 9 |
| AU13 书信正文句 | 14 |
| **合计** | **93** |

未把 93 条自动设置为 VERIFIED。

当前筛选状态：

```text
CANDIDATE：93
VERIFIED：0
REJECTED：0
```

其中：

```text
完整 sentence_text：29
fragment（需教师补全）：64
```

fragment 无法可靠恢复时，筛选台要求人工处理，不允许直接保留为 VERIFIED。

## 4. 筛选 UI

新增“教师筛选”界面，显示：

- sentence_id
- audio_id
- unit / chapter / activity
- 完整句子或 fragment
- 上下文
- 当前状态
- selection_reason
- pattern_key
- function_tag
- reject_reason
- duplicate_of

操作：

```text
保留 → CANDIDATE
舍弃 → REJECTED
```

“保留”要求：

- 句子完整
- 不含 `___`
- 选择 selection_reason

“舍弃”要求：

- 选择 reject_reason
- 可填写 duplicate_of

## 5. 整句定位 UI

只有非 REJECTED 且句子完整的候选才进入“整句定位”。

保留的能力：

- 大波形
- 长时间轴
- 时间刻度
- 播放 / 暂停
- 点击波形定位
- 当前位置附近播放
- 缩放 / 全局视图
- Start 手柄
- End 手柄
- 播放选中整句
- 上一句 / 下一句
- 保存 VERIFIED
- 标记 REJECTED

核心操作只剩：

```text
start_ms
end_ms
```

## 6. 逐词逻辑如何停用

已停止：

- token UI
- token 数组
- token 校验
- token 正式数据写入
- 单词选择
- 单词播放
- 逐词 start/end

`audio_token_annotation` 表只保留为空，作为历史 Spike 结构；当前服务和页面均不访问、不写入该表。

## 7. 正式数据库如何保存

保存由 `app.py` 的 `/api/save` 完成：

1. 校验 status：`CANDIDATE`、`VERIFIED`、`REJECTED`
2. VERIFIED 必须有完整句子、start_ms、end_ms
3. REJECTED 必须有 reject_reason
4. 使用一个 SQLite `BEGIN IMMEDIATE` 事务
5. 只写入 `audio_sentence_annotation`
6. 事务失败自动 rollback
7. 不触碰 `learning.db`
8. 不写 `audio_token_annotation`

当前正式表：

```text
audio_sentence_annotation：0 行
audio_token_annotation：0 行
```

## 8. 10 条首轮试运行情况

```text
BLOCKED — 等待人工验证
```

工具已准备好：

```text
http://127.0.0.1:8781/
http://192.168.2.3:8781/
```

但 10 条真实体验试运行尚未由人工完成。不得自动生成 VERIFIED。

建议首批 10 条：

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

## 9. VERIFIED 数量

```text
0
```

本环境未进行人工试听和人工保存，因此没有任何 VERIFIED 句子。

## 10. REJECTED 数量

```text
0
```

教师筛选尚未开始；没有任何自动 REJECTED。

## 11. CANDIDATE 数量

```text
清单中待筛选：93
正式表中：0
```

只有在人工实际保存后才进入正式表。

## 12. 是否存在无法完整化的 fragment

```text
是：64/93 当前只有 fragment，没有完整 sentence_text。
```

处理原则：

- 能从教材文本、上下文、已有映射可靠恢复的，由人工补全。
- 无法可靠恢复的，标记 `REJECTED`，reject_reason = `fragment_unresolved`。
- 不猜测、不改写教材。

## 13. 数据质量检查

当前候选清单：

```text
候选数：93
唯一 sentence_id：93
重复 ID：0
token 字段：0
fragment 数：64
完整句候选：29
```

正式表：

```text
缺 sentence/start/end：0（表为空）
start/end 反向：0
超出音频长度：0
重叠：0
空 token：0（token 表未使用）
重复 sentence_uid：0
重复标注：0
```

这些结果表示当前没有人工数据污染，但不代表 93 条已经完成教学筛选。

## 14. 安全检查

```text
AI 调用 = 0
ASR / Whisper = 0
learning.db = unchanged
Android = unchanged
original MP3 = unchanged
formal learning logic = unchanged
正式教材原文 = unchanged
音频转码 = 0
音频切割 = 0
learning.db 写入 = 0
token 表写入 = 0
自动 VERIFIED = 0
```

P3-07 正式内容库只发生了已授权 schema 迁移；没有写入候选项、试听结果或 VERIFIED 业务数据。

## 15. 下一步建议

下一步只做人工 10 条首轮试运行：

1. 打开 `http://192.168.2.3:8781/`。
2. 在“教师筛选”中处理 10 条样本。
3. fragment 必须补全或标记 `fragment_unresolved`。
4. 对保留句进入“整句定位”。
5. 人工反复试听，确认 start/end。
6. 保存 VERIFIED。
7. 检查正式表写入是否正确。
8. 通过后再处理剩余候选。

## 16. 最终状态

```text
P3-07 最小实施：PASS
10 条真实人工验证：BLOCKED — 等待人工验证
VERIFIED：0
REJECTED：0
CANDIDATE（待筛选清单）：93
```

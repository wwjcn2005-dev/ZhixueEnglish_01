# P3-07 AU13 LTR 7 句页面链路修复报告

## 1. PASS / FAIL

```text
PASS
```

AU13 Letter 精选 7 句已进入页面候选 API 链路，页面可从 Suggested Start/End 字段读取建议区间；原始 AU13 MP3 和 Range 播放正常。

## 2. 修改文件

| 文件 | 修改原因 |
| --- | --- |
| `p3_07_audio_annotation_spike/data/suggested_locations.json` | 新增非正式建议定位层，保存 7 句 Suggested Start/End |
| `p3_07_audio_annotation_spike/app.py` | `/api/candidates` 合并建议字段 |
| `p3_07_audio_annotation_spike/static/app.js` | 读取并显示 `suggested_start_ms / suggested_end_ms`；音频存在性独立于 start/end |
| `p3_07_audio_annotation_spike/static/index.html` | 添加静态资源版本参数，规避旧缓存 |

## 3. 每个文件修改目的

### `suggested_locations.json`

只保存页面审核阶段的非正式建议值，不写正式数据库、不写 `annotations.json`、不写 `candidates.json`。

### `app.py`

读取 `candidates.json` 后，按 `candidate_id` 合并：

```text
suggested_start_ms
suggested_end_ms
suggested_status
suggested_source
```

没有建议的候选保持原行为。

### `static/app.js`

新增 `applyProvidedSuggestions()`：

- 如果候选存在 `suggested_start_ms / suggested_end_ms`，直接显示为 Suggested Start/End。
- 不修改原有 `computeSuggestions()` 算法。
- 音频是否存在依据 `audio_id / audio_num / original_audio_path`，不要求 `start_ms/end_ms` 非空。

### `static/index.html`

静态资源改用版本参数：

```text
/static/style.css?v=20260914b1
/static/app.js?v=20260914b1
```

用于排除旧 JS/CSS 缓存。

## 4. 7 个精选句验证结果

| candidate_id | suggested_start_ms | suggested_end_ms | status | 验证 |
| --- | ---: | ---: | --- | --- |
| AU13-LTR-01 | 47860 | 49440 | READY | PASS |
| AU13-LTR-02 | 50140 | 52330 | READY | PASS |
| AU13-LTR-03 | 52760 | 54760 | READY | PASS |
| AU13-LTR-09 | 73320 | 75580 | READY | PASS |
| AU13-LTR-10 | 76140 | 78120 | READY | PASS |
| AU13-LTR-11 | 78600 | 82520 | NEEDS_MANUAL_REVIEW | PASS |
| AU13-LTR-12 | 82520 | 86490 | NEEDS_MANUAL_REVIEW | PASS |

`/api/candidates` 实测返回上述 7 组值。

## 5. 页面音频加载验证

```text
GET / -> 200
GET /static/app.js?v=20260914b1 -> 200
GET /audio/AU13.mp3 Range bytes=0-1023 -> 206 Partial Content
Content-Range: bytes 0-1023/2433836
```

AU13 原始 MP3：

```text
D:\ZhixueEnglish\2025年度初一外研版英语教材\13_Unit 1_Developing ideas _Reading for writing_2 Read the passage and find out the meaning of the title.mp3
```

文件存在，未被修改。

## 6. Suggested Start/End 验证

`candidates.json` 保持原始候选数据源，没有被写回 `suggested_*`。

页面 API 在只读合并层返回建议值：

```text
AU13-LTR-01 -> 47860 / 49440
...
```

页面 JS 会读取这些值并显示在 Suggested Start / Suggested End 输入框。

## 7. 缓存处理结果

当前源码中没有“以下无相应音频”文字。

已确认：

- 8781 服务使用当前 `p3_07_audio_annotation_spike/app.py`
- 静态资源加入 `v=20260914b1`
- 旧进程已停止，新服务已启动

当前服务：

```text
http://127.0.0.1:8781/
http://192.168.2.3:8781/
```

## 8. 正式数据库是否变化

```text
learning.db：未修改
正式内容库：未修改
audio_sentence_annotation：未修改
audio_token_annotation：未修改
原始教材：未修改
原始 MP3：未修改
```

本次修复只增加/修改 `p3_07_audio_annotation_spike` 内的页面辅助文件。

## 9. AI / ASR / Whisper 调用次数

```text
AI = 0
ASR = 0
Whisper = 0
云端调用 = 0
音频切割 = 0
音频转码 = 0
```

## 10. 原有 P3-07 测试结果

```text
Python 语法检查：PASS
/api/candidates：PASS
AU13-LTR 7 句建议字段：PASS
AU13 原始 MP3 Range：PASS
原有 candidates.json：未改写
原有 annotations.json：未改写
```

没有为本次任务建立大型测试框架。

## 11. 是否可以进入人工听音验收

```text
可以进入人工听音验收
```

人工听音时仍应独立判断：

- 句首是否完整
- 句尾是否自然
- 是否带入前句或后句
- LTR-11 / LTR-12 是否由于静音间隔不明显需要调整

本次只修复了“建议值进入页面”的链路，没有把建议值写成正式 VERIFIED。

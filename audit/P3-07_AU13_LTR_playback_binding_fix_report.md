# P3-07 AU13 LTR 建议区间播放绑定修复报告

## 1. PASS / FAIL

```text
PASS
```

修复后，AU13-LTR 精选句的建议区间会在选择候选时进入播放器的 Start / End 输入框，`Play Range` 可直接播放该区间。

## 2. 根因

原来存在前端状态断点：

```text
suggested_start_ms / suggested_end_ms
→ 只写入 Suggested Start / Suggested End
→ 没有同步到 selectionStart / selectionEnd
→ Start / End 输入框保持为空
→ Play Range 读取 selectionStart / selectionEnd，因此没有有效参数
```

这是前端状态同步问题，不是 API 数据问题，也不是音频映射问题。

## 3. 实际断点

涉及函数：

- `showPosition()`
- `applyProvidedSuggestions()`
- `playSelection()`
- `currentNumbers()`
- `syncSelectionFromInputs()`

原问题：

1. `showPosition()` 只用 draft / existing timing 初始化 `selectionStart / selectionEnd`。
2. AU13-LTR 候选没有 draft / existing timing。
3. `applyProvidedSuggestions()` 只设置 Suggested 显示值，没有设置 `selectionStart / selectionEnd`。
4. `playSelection()` 读取 `selectionStart / selectionEnd`，因此建议区间无法播放。

## 4. 修改文件

只修改：

```text
D:\ZhixueEnglish\p3_07_audio_annotation_spike\static\app.js
```

未修改：

```text
app.py
static/index.html
data/candidates.json
data/suggested_locations.json
learning.db
正式内容库
audio_sentence_annotation
audio_token_annotation
原始 MP3
```

## 5. 修改内容

### 5.1 `applyProvidedSuggestions()`

当候选存在 `suggested_start_ms / suggested_end_ms`，且当前没有已保存或已有锚点区间时：

```text
selectionStart = suggested_start_ms / 1000
selectionEnd = suggested_end_ms / 1000
startMs.value = suggested_start_ms
endMs.value = suggested_end_ms
```

同时保留 Suggested Start / Suggested End 的显示。

### 5.2 `playSelection()`

播放前优先读取当前 Start / End 输入框：

```text
currentNumbers()
→ selectionStart / selectionEnd
→ playFrom(start, end)
```

确保用户手工微调 Start / End 后，Play Range 播放的是当前编辑值。

### 5.3 Start / End 输入同步

为 `startMs`、`endMs` 添加 `input` 事件：

```text
输入变化 → selectionStart / selectionEnd 同步 → waveform 更新
```

## 6. 7 个区间显示验证

使用无头 Edge 实际加载页面并调用 `showPosition()`，读取 Start / End 输入框：

| candidate_id | Start | End | Suggested Start | Suggested End | 结果 |
| --- | ---: | ---: | ---: | ---: | --- |
| AU13-LTR-01 | 47860 | 49440 | 47860 | 49440 | PASS |
| AU13-LTR-02 | 50140 | 52330 | 50140 | 52330 | PASS |
| AU13-LTR-03 | 52760 | 54760 | 52760 | 54760 | PASS |
| AU13-LTR-09 | 73320 | 75580 | 73320 | 75580 | PASS |
| AU13-LTR-10 | 76140 | 78120 | 76140 | 78120 | PASS |
| AU13-LTR-11 | 78600 | 82520 | 78600 | 82520 | PASS |
| AU13-LTR-12 | 82520 | 86490 | 82520 | 86490 | PASS |

## 7. 实际播放验证

使用无头 Edge 执行 `playSelection()`：

| candidate_id | 播放区间 | audio src | paused | currentTime | 结果 |
| --- | --- | --- | --- | ---: | --- |
| AU13-LTR-01 | 47.860–49.440 s | `/audio/AU13.mp3` | false | 47.86 | PASS |
| AU13-LTR-02 | 50.140–52.330 s | `/audio/AU13.mp3` | false | 50.14 | PASS |
| AU13-LTR-11 | 78.600–82.520 s | `/audio/AU13.mp3` | false | 78.60 | PASS |

验证表明播放器已从建议 Start 开始执行播放，且音频源指向 AU13 原始 MP3。

## 8. 正式数据库是否变化

```text
learning.db：未修改
正式内容库：未修改
audio_sentence_annotation：未修改
audio_token_annotation：未修改
原始教材：未修改
原始 MP3：未修改
```

建议值仍只存在于非正式 `suggested_locations.json`，没有写回 `candidates.json`，也没有创建 VERIFIED 记录。

## 9. AI / ASR / Whisper 是否调用

```text
AI = 0
ASR = 0
Whisper = 0
云端调用 = 0
音频转码 = 0
音频切割 = 0
```

## 10. 是否可以进入人工听音验收

```text
可以进入人工听音验收
```

人工验收时建议重点检查：

- AU13-LTR-11：句尾与 LTR-12 的边界
- AU13-LTR-12：句首是否紧接上一句
- 所有句子的句首是否完整、句尾是否自然

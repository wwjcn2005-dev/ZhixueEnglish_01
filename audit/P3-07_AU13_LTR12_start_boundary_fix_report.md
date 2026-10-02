# P3-07 AU13-LTR-12 起始边界修复报告

## 1. PASS / FAIL

```text
PASS
```

只修改了 LTR-12 的 `suggested_start_ms`，页面绑定与 Play Range 验证通过。

## 2. 原 Start / 新 Start

| 项目 | 数值 |
| --- | ---: |
| 原建议 Start | 82520 ms |
| 页面当前已有草稿 Start | 82765 ms |
| 新建议 Start | **82765 ms** |
| End | 86490 ms（未改） |

本次只修改：

```text
p3_07_audio_annotation_spike\data\suggested_locations.json
→ AU13-LTR-12.suggested_start_ms
```

## 3. 82.0–83.5 秒附近的自然静音/低能量区

本地 PCM / 10ms RMS 分析结果：

```text
自然静音区：82590–83580 ms
持续时间：990 ms
```

关键观测：

- 82590 ms 起进入稳定低能量区
- 82765 ms 处 RMS ≈ 0.000002，属于静音区
- 83575–83590 ms 附近开始出现新的高能量起音

因此：

```text
82765 ms 明显位于 LTR-11 尾音之后
82765 ms 明显位于 LTR-12 起音之前
```

## 4. 为什么新 Start 不再落在 LTR-11 尾音区

LTR-11 尾音在 82590 ms 前已经结束。

新 Start：

```text
82765 ms
```

位于静音区内部，并且距离 LTR-12 的实际起音点仍有约 810 ms 的安全距离。

这不会再包含 LTR-11 的尾音，也不会吞掉 LTR-12 的开头。

## 5. 页面绑定验证

无头 Edge 实测页面：

```text
Start = 82765
End = 86490
Suggested Start = 82765
Suggested End = 86490
```

页面选择 AU13-LTR-12 后，Start/End 输入框正确绑定。

## 6. Play Range 验证

无头 Edge 实际执行 Play Range：

```text
selectionStart = 82.765 s
selectionEnd = 86.490 s
currentTime = 82.765 s
paused = false
audio.src = /audio/AU13.mp3
```

验证通过：播放器从新的 Start 开始播放。

## 7. API 验证

`/api/candidates` 返回：

```text
AU13-LTR-12
suggested_start_ms = 82765
suggested_end_ms = 86490
status = NEEDS_MANUAL_REVIEW
```

其他 6 条 LTR 建议值未改变。

## 8. 数据安全验证

```text
learning.db：未修改
正式内容库：未修改
audio_sentence_annotation：未修改
audio_token_annotation：未修改
原始教材：未修改
原始 MP3：未修改
AI = 0
ASR = 0
Whisper = 0
云端调用 = 0
音频切割 = 0
音频转码 = 0
```

## 9. 结论

LTR-12 新 Start = **82765 ms** 可靠落在自然静音区，页面绑定和 Play Range 均验证通过。

可以进入人工听音验收。

# P3-07 最小改造实施报告

## 1. 结论

```text
PASS（工具改造完成）
BLOCKED — 等待人工试听新建议值
```

工具已从“让用户判断教学价值”改为：

> 上游提供已选教材句；用户只负责试听原始 MP3、查看波形、微调 Start/End、确认。

新增了本地 PCM/能量分析的静音辅助定位；未使用 AI、ASR、Whisper 或云端服务。

## 2. 只读检查结果

现有结构：

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

当前候选：

```text
93 条：70 条 B 类句子候选 + 9 条 AU13 对话句 + 14 条 AU13 书信句
其中 64 条仍为 fragment
```

现有正式表：

- `audio_sentence_annotation`：已支持 `CANDIDATE / VERIFIED / REJECTED`
- `audio_token_annotation`：空表；本阶段不使用、不写入、不删除

正式表中检测到已有 12 条人工试运行记录：

```text
VERIFIED：9
REJECTED：3
CANDIDATE：0
```

这些记录未修改、未删除。

## 3. 修改文件

| 路径 | 修改原因 | 修改内容 |
| --- | --- | --- |
| `p3_07_audio_annotation_spike/static/index.html` | 隐藏教师筛选工作；增加静音辅助定位控件 | 默认只显示整句定位；添加 Suggested Start / End、应用按钮、分析按钮 |
| `p3_07_audio_annotation_spike/static/app.js` | 增加本地低能量分析；移除用户侧教学价值判断默认值 | 10ms RMS、低能量区检测、Suggested Start/End、应用建议、静音区可视化；不再自动填写 `selection_reason` |
| `p3_07_audio_annotation_spike/static/style.css` | 配合新提示区 | 新增上游筛选说明样式 |

## 4. 未修改文件 / 系统

```text
learning.db：未修改
Android：未修改
原始教材：未修改
原始 MP3：未修改
audio_token_annotation：未删除、未写入、保持为空
正式学习逻辑：未修改
正式教材解析流程：未修改
```

## 5. 静音辅助定位

检测方式：

```text
浏览器 Web Audio 解码原始 MP3
→ 10ms 帧 RMS
→ 第 20 百分位能量 × 1.8，下限 0.006
→ 连续低能量区至少 70ms
→ 在已有定位锚点附近寻找前后低能量区
```

建议规则：

- 句首：优先选句首前不远的低能量区；超过 1000ms 则回退到 `anchor_start - 120ms`。
- 句尾：优先选句尾后不远的低能量区，允许保留自然短停顿；超过 1800ms 则回退到 `anchor_end + 140ms`。
- Suggested Start/End 只是建议；用户必须试听并手动调整后保存。

使用情况：

```text
AI：0
ASR：0
Whisper：0
云端：0
新依赖：0
```

## 6. 3～5 条真实教材音频验证

本轮用 5 条真实教材音频锚点验证静音建议算法。音频只读，未生成或修改任何 MP3。

| candidate_id | 教材音频 | anchor start–end | Suggested Start | Suggested End | 自然空白利用 |
| --- | --- | ---: | ---: | ---: | --- |
| AU11-B01 | `11_Unit 1...poster.mp3` | 10420–12480 | 10490 | 12920 | 使用前后低能量区 |
| AU11-B02 | `11_Unit 1...poster.mp3` | 13460–15740 | 13450 | 16200 | 使用前后低能量区 |
| AU11-B03 | `11_Unit 1...poster.mp3` | 22240–26000 | 21600 | 26380 | 使用前后低能量区 |
| AU13-DLG-01 | `13_Unit 1...title.mp3` | 13940–20260 | 13820 | 20730 | 后空白可用；前空白过远，安全回退到句首附近 |
| AU13-DLG-02 | `13_Unit 1...title.mp3` | 21080–24300 | 20960 | 24860 | 后空白可用；前空白过远，安全回退到句首附近 |

结论：

- 波形、时间轴、缩放、播放、拖拽选择、区间播放、整句文本显示保持可用。
- Suggested Start/End 可生成。
- 句尾建议会利用自然空白，不机械贴合最后一个音素。
- 如果前方低能量区距离句首过远，程序不会冒险采用，避免带入前文。
- 这 5 条仍需要人工试听后才能确认 Suggested Start/End 是否最终正确。

## 7. 数据安全

```text
learning.db 未修改
正式学习数据未修改
原始 MP3 未修改
原始教材未修改
AI = 0
ASR = 0
Whisper = 0
```

当前正式表：

```text
audio_sentence_annotation：12 行（既有 9 VERIFIED + 3 REJECTED）
audio_token_annotation：0 行
```

## 8. 测试

```text
页面 HTTP 测试：PASS
候选 API 测试：PASS
原始 MP3 Range 播放测试：PASS
静音辅助算法测试：5 条真实音频锚点完成
人工试听确认：BLOCKED — 等待人工验证
```

未自动写入新的 VERIFIED。

## 9. 下一步建议

下一步只做人工验证：

1. 打开 `http://192.168.2.3:8781/`。
2. 从已选句中试听 Suggested Start/End。
3. 手动微调明显边界。
4. 确认后保存 VERIFIED。
5. 先用 3～5 条验证体验，不要批量处理 93 条。

新建议值在人工试听确认前不能被当作最终结果。

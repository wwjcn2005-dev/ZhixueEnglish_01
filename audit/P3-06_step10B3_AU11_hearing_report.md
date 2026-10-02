# P3-06 Step 10B3 AU11 人工听证准备与验证

> 本步骤只搭建人工听证页面并做冒烟验证；未代替人工判定。AU11 的 6 条仍为 Step 10B2 `CANDIDATE`，全部 `NOT VERIFIED`。

## 1. 结论

```text
PASS（听证页已就绪）
```

AU11 人工听证页面：

```text
本机：http://127.0.0.1:8770/p3-06/au11-hearing
局域网/S24+：http://192.168.2.3:8770/p3-06/au11-hearing
```

页面状态：

- 数据来源：P3-06 Step 10B2 AU11 recovery candidates
- 标注：`P3-06 Step 10B2`、`CANDIDATE`、`NOT VERIFIED`
- 音频：原始官方 MP3 `/audio/official/AU11.mp3`
- 播放方式：浏览器 `currentTime = start_ms / 1000`，到 `end_ms` 后 `pause()`
- 不生成音频切片，不修改原始 MP3

## 2. 6 条候选

| # | candidate_id | learning_text candidate | 原始 start_ms | 原始 end_ms | 听证重点 |
| ---: | --- | --- | ---: | ---: | --- |
| 1 | AU11-B01 | The new school year is beginning. | 10420 | 12480 | 常规 |
| 2 | AU11-B02 | What are the new students' problems? | 13460 | 15740 | 常规 |
| 3 | AU11-B03 | They have more subjects and more homework. | 22240 | 26000 | **前置语境 / 边界检查** |
| 4 | AU11-B04 | They also have many activities. | 26000 | 29360 | 常规 |
| 5 | AU11-B05 | How can they make good use of their time? | 30740 | 33640 | **检查前面的 “So” 与 30740ms 起点** |
| 6 | AU11-B06 | The Students' Union will hold a talk this Thursday to help you. | 34940 | 39540 | **检查 “to help you.” 是否覆盖自然句尾** |

## 3. 页面上提供的听证操作

每条候选均提供：

1. `▶ 播放这一句`
2. 原始 `start_ms / end_ms`
3. `proposed_start_ms`
4. `proposed_end_ms`
5. 人工听证结果选择：
   - `UNREVIEWED`
   - `VERIFIED`
   - `NEEDS_ADJUSTMENT`
   - `REJECTED`
6. 备注
7. `保存本机草稿`

页面顶部提供：

1. `▶ 播放完整音频`
2. 暂停
3. 导出本机听证草稿 JSON
4. 清空本机草稿

草稿只写入当前浏览器的 `localStorage`，不写 learning.db、不写 contentpack、不写正式题库，也不修改 Step 10B2 原始候选。

## 4. 人工听证结果

截至本报告生成时，尚未进行人工实际听证，因此不能填写真实性结果。

| candidate_id | 人工听证结果 | proposed_start_ms | proposed_end_ms | 是否完整 | 是否自然 | 前后尾音 | 建议 VERIFIED |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AU11-B01 | `AWAITING_HUMAN_LISTENING` | 未记录 | 未记录 | 待定 | 待定 | 待定 | 待定 |
| AU11-B02 | `AWAITING_HUMAN_LISTENING` | 未记录 | 未记录 | 待定 | 待定 | 待定 | 待定 |
| AU11-B03 | `AWAITING_HUMAN_LISTENING` | 未记录 | 未记录 | 待定 | 待定 | 待定 | 待定 |
| AU11-B04 | `AWAITING_HUMAN_LISTENING` | 未记录 | 未记录 | 待定 | 待定 | 待定 | 待定 |
| AU11-B05 | `AWAITING_HUMAN_LISTENING` | 未记录 | 未记录 | 待定 | 待定 | 待定 | 待定 |
| AU11-B06 | `AWAITING_HUMAN_LISTENING` | 未记录 | 未记录 | 待定 | 待定 | 待定 | 待定 |

人工听证标准：

- 句子完整
- 句首没有明显截掉第一个音
- 句尾没有明显截掉最后一个词/音
- 前后少量自然尾音可以接受
- 最终标准是“孩子能否自然跟读这一整句”

## 5. 最终统计

```text
VERIFIED = 0
NEEDS_ADJUSTMENT = 0
REJECTED = 0
AWAITING_HUMAN_LISTENING = 6
```

本步骤没有自动 VERIFIED，也没有根据自动检查结果升级任何候选。

## 6. 页面冒烟验证

只读 HTTP 验证：

```text
GET /p3-06/au11-hearing -> 200
页面包含 AU11 人工听证
页面包含 CANDIDATE
页面包含 NOT VERIFIED
页面包含 /audio/official/AU11.mp3
Range GET /audio/official/AU11.mp3 -> 206 Partial Content
```

服务运行：

```text
http://127.0.0.1:8770/p3-06/au11-hearing
http://192.168.2.3:8770/p3-06/au11-hearing
```

## 7. Web 层最小改动

本轮仅修改/新增最小 Web 层内容：

- `web/content.py`：增加 Step 10B2 candidates 只读加载器
- `web/app.py`：增加 `/p3-06/au11-hearing` 只读路由
- `web/ui.py`：增加 AU11 人工听证页
- 新增 `audit/P3-06_step10B3_AU11_hearing_report.md`

未创建新的测试框架，复用现有实验测试页体系。

## 8. 数据安全确认

```text
learning.db 修改 = 0
contentpack 修改 = 0
正式题库修改 = 0
P3-05 修改 = 0
Android 修改 = 0
原始教材修改 = 0
原始 MP3 修改 = 0

Whisper rerun = 0
AI / cloud = 0
install / download = 0
audio slicing = 0
自动 VERIFIED = 0
```

本步骤完成后 STOP：不进入批量处理，不处理其他 13 个 Activity，不创建正式题库资源，不修改正式数据。

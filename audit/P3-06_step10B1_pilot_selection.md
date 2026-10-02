# P3-06 Step 10B-1 官方音频辅助完整学习句恢复：Pilot Activity 选择

> 只读选择报告。未修改 learning.db、contentpack、正式题库、P3-05、Android、原始教材或原始 MP3；未播放/识别音频；未运行 Whisper；未生成 timing；未生成完整句子；AI/cloud calls = 0。

## 1. 最终结论

```text
PASS
推荐 Pilot：AU11
```

推荐对象：

```text
Unit 1 / DEVELOPING_IDEAS / Activity 2
Listen again and complete the poster.
audio_id = FLTRP-EN-7A-2022CUR:AU11
candidate slot count = 6
```

这是 14 个 B 类 Activity 中“规模小、页面干净、音频短、结构简单、映射明确”的综合最优选择。

## 2. 14 个 B 类 Activity 候选比较表

说明：

- `Fragment completeness`：Step 10A 均已确认句子骨架；这里评估骨架的可读性。
- `Page clarity`：是否同页混有其他 Activity、图片和复杂版面。
- `Audio mapping`：全部来自项目现有映射记录，均为 `CONFIRMED`。
- `Dialogue complexity`：依据教材 Activity 名称和页面结构作静态判断，未播放音频。

| audio_id | Unit | Activity | Slots | Fragment completeness | Page clarity | Audio mapping | OCR / layout risk | Dialogue complexity | Pilot suitability |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| AU01 | Starter | 2 Read and complete. Then listen and check. | 5 | 5/5 清晰 | Medium：同页含 1/2/3/4 | CONFIRMED | Medium：同页多活动 | Low：Mum / Li Ming 两人 | Medium |
| AU02 | Starter | 3 Listen and complete the conversation with a / an or a number. | 4 | 4/4 清晰 | Medium：同页含 1/2/3/4 | CONFIRMED | Medium：同页多活动 | Low：Mum / Li Meng 两人 | Medium |
| AU03 | Starter | 10 Listen and choose. | 8 | 8/8 清晰 | Medium：同页含 8/9/10 | CONFIRMED | Medium：11 个图片资产 | Low：Nana / Wang Tao 两人 | Medium |
| **AU11** | **Unit 1** | **2 Listen again and complete the poster.** | **6** | **6/6 清晰** | **High：单活动页面** | **CONFIRMED** | **Low：无图片资产，17 blocks** | **Low：Students' Union talk，结构简单** | **High** |
| AU12 | Unit 1 | 3 Listen to the conversation and complete the table. | 5 | 5/5 清晰 | Medium：表格结构 | CONFIRMED | High：57 个图片资产 | Medium：Wang Peng / Li Lin 对话 | Low |
| AU19 | Unit 2 | 3 Listen to the interview and complete the interviewer's notes. | 5 | 5/5 清晰 | High：单活动页面 | CONFIRMED | Low-Medium：notes 结构清楚 | Medium：interviewer + Wang Chen | Medium-High |
| AU25 | Unit 3 | 2 Listen again and complete the chart. | 5 | 5/5 清晰 | High：单活动页面 | CONFIRMED | Low：chart 结构简单 | Medium：Tina / Mum | High |
| AU26 | Unit 3 | 3 Listen and complete the conversation. | 6 | 6/6 清晰 | Medium：双栏对话 | CONFIRMED | Medium：双栏对话 + learning box | Medium：Tina / Mum | Medium |
| AU32 | Unit 4 | 2 Listen again and complete the poster. Then write F/O. | 6 | 6/6 清晰 | Medium：poster + F/O boxes | CONFIRMED | Medium-High：poster 分栏 | Low-Medium：news/poster narration | Medium |
| AU33 | Unit 4 | 3 Listen to the conversation and complete the ideas. Then match. | 5 | 5/5 清晰 | Medium：ideas + people matching | CONFIRMED | Medium：match 叠加 | Medium-High：Dad / Mark / Mum | Low-Medium |
| AU39 | Unit 5 | 2 Listen again and complete Jason's notes for the vlog. | 5 | 5/5 清晰 | High：单活动页面 | CONFIRMED | Low：notes 结构清楚 | Low-Medium：vlog narration | High |
| AU40 | Unit 5 | 3 Listen to the conversation and complete the sentences. | 4 | 4/4 清晰 | Medium：多段植物信息 | CONFIRMED | Medium：四个小节 | High：191.7s 长对话 | Medium |
| AU45 | Unit 6 | 2 Listen again and complete the webpage for Bingjie. | 6 | 6/6 清晰 | High：单活动页面 | CONFIRMED | Low：webpage timeline | Low-Medium：radio programme/webpage | High |
| AU46 | Unit 6 | 3 Listen to the interview and complete the notes. | 6 | 6/6 清晰 | Medium：interview notes | CONFIRMED | Medium-High：36 blocks | Medium-High：interviewer + Ouyang Honghong | Medium |

## 3. 最终推荐 Pilot

```text
AU11
```

| 项目 | 内容 |
| --- | --- |
| Module / Unit | Unit 1 |
| Section | DEVELOPING_IDEAS |
| Activity | 2 Listen again and complete the poster. |
| audio_id | `FLTRP-EN-7A-2022CUR:AU11` |
| official MP3 | `11_Unit 1_Developing ideas _2 Listen again and complete the poster.mp3` |
| original textbook page | PDF p27 / 教材 p22 |
| candidate slot count | 6 |
| audio duration | 44.1 s |
| audio mapping | CONFIRMED |
| page structure | 单活动页面，17 content blocks，0 images |
| recovered fragments | 6/6 |
| learning_text | 全部 null（本步骤不恢复） |
| timing_status | 全部 TIMING_PENDING（本步骤不生成） |

推荐 Activity 的句子骨架：

| # | candidate_id | recovered_fragment |
| ---: | --- | --- |
| 1 | AU11-B01 | `Students' Union talk: The new school ___ is beginning.` |
| 2 | AU11-B02 | `What are the ___ students' problems?` |
| 3 | AU11-B03 | `They have more ___ and more homework.` |
| 4 | AU11-B04 | `They also have ___ activities.` |
| 5 | AU11-B05 | `How can they make good use of their ___?` |
| 6 | AU11-B06 | `The Students' Union will hold a talk this ___. Come and join us!` |

## 4. 推荐理由

AU11 同时满足以下条件：

1. **规模小**：只有 6 个候选句槽，试听与核对工作量可控。
2. **页面干净**：PDF p27 只承载该 Activity，不和同页的其他活动混杂。
3. **版面风险低**：无图片资产，content blocks 仅 17 个，阅读顺序清楚。
4. **音频短**：44.1 秒，是 14 个 B 类 Activity 中时长最短的之一。
5. **结构简单**：`Students' Union talk` 是海报式信息表达，不像多人交叉对话那样存在 speaker 归属歧义。
6. **映射明确**：AU11 的 Activity 与官方 MP3 映射状态为 `CONFIRMED`，文件名指令与教材指令一致。
7. **句子骨架清晰**：6 个槽都处于完整句子骨架中，缺失词位置明确。
8. **错误成本低**：即使首次恢复发现问题，影响范围仅 6 条，不会污染大范围 B 类数据。

## 5. 为什么其他候选暂不作为第一例

| Activity | 暂不首选原因 |
| --- | --- |
| AU01 / AU02 | 页面同页含多个 Starter Activity，版面干扰较大 |
| AU03 | 8 个槽，图片资产多，Listen and choose 还混合选择逻辑 |
| AU12 | 表格结构复杂，57 个图片资产，版面抽取风险高 |
| AU19 | 5 个槽较合适，但 interview notes 含 interviewer / Wang Chen 交叉结构 |
| AU25 | 很好的次选，但音频和 chart 复杂度略高于 AU11 |
| AU26 | 双栏对话，Tina / Mum 两列交织，页面阅读顺序风险更高 |
| AU32 | poster 与 F/O 判断叠加，不是纯句槽恢复 |
| AU33 | 同时包含 complete ideas 和 match to people，任务链复杂 |
| AU39 | 结构与 AU11 接近，但 vlog notes 的音频内容可能更密集 |
| AU40 | 只有 4 个槽，但官方音频 191.7 秒，为候选中最长，试听成本高 |
| AU45 | 页面干净、6 个槽，是不错的备选；但 webpage timeline 比 AU11 略复杂 |
| AU46 | interview notes 为多人问答结构，36 blocks，风险高于 AU11 |

## 6. 推荐 Pilot 的静态风险结论

| 风险项 | AU11 判断 |
| --- | --- |
| 槽数量 | 低（6） |
| 句子骨架清晰度 | 高（6/6） |
| 页面污染 | 低 |
| OCR / layout 污染 | 低 |
| 多人对话交叉 | 低 |
| 标题 / instruction / 正文混杂 | 低 |
| 音频映射 | CONFIRMED |
| 人工快速听证适合度 | 高 |

## 7. 下一步边界

本步骤只完成 Pilot Activity 选择，不开始 Step 10B-2：

```text
不处理 AU11 音频
不运行 Whisper
不生成完整句子
不生成 timing
不人工猜词
不写正式题库
```

## 8. 数据安全确认

```text
正式数据修改：0
原始教材修改：0
原始 MP3 修改：0
AI / cloud calls：0
Whisper rerun：0
install / download：0
timing：0
VERIFIED：0
```

## 9. 输出文件

- `D:\ZhixueEnglish\audit\P3-06_step10B1_pilot_selection.md`

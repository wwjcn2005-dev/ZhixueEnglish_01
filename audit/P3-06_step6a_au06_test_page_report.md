# P3-06 Step 6A：AU06 句子音频测试页面（实施报告）

> 未处理 AU13 / 其他音频 / AU48–AU54 / 词汇音频；未重跑 Whisper、未下载模型、未安装依赖、未调用云端 AI、未修改 learning.db / contentpack / 原始 MP3 / P3-05 / Android；未把任何 CANDIDATE 改成 VERIFIED。

## 1. 修改文件

| 文件 | 改动 |
| --- | --- |
| `audit/p3_06/au06_test_candidates.json` | **新增**：测试页数据（AU06 元信息 + 8 句候选时间，全部 CANDIDATE） |
| `web/content.py` | 新增只读 `au06_test_data()`（读上述实验 JSON） |
| `web/ui.py` | 新增 `au06_test_page()` 与 `_ms_clock()`（8 句卡片 + 完整音频 + 区间播放 JS），并补 `import json` |
| `web/app.py` | 新增顶层只读路由 `/p3-06/au06-test` |

**未修改**：`learning.db`、contentpack、原始教材 PDF、54 个原始 MP3（**未生成任何切片、未复制、未重命名**）、P3-05、Android、现有学习业务逻辑。

## 2. 新增路由

```
http://192.168.2.3:8770/p3-06/au06-test
```
仅只读 GET；**不进入正式导航**（已核对首页不含该链接）。

## 3. 音频来源

**原始教材 MP3（非切片文件）**：

| 项 | 值 |
| --- | --- |
| audio_id | `FLTRP-EN-7A-2022CUR:AU06` |
| 原始文件名 | `06_Starter_Get to know each other_4 Read and check your answers.mp3` |
| 完整路径 | `D:\ZhixueEnglish\2025年度初一外研版英语教材\06_Starter_Get to know each other_4 Read and check your answers.mp3` |
| Web URL | `/audio/official/AU06.mp3`（既有播放通道，支持 Range） |
| Activity | Starter / GET_TO_KNOW_EACH_OTHER / A4（教材第 10 页） |
| 总时长 | 43.337 s（contentpack 记录，未重新分析） |

页面通过 `new Audio('/audio/official/AU06.mp3')` 加载**该原始完整 MP3**，未产生任何新音频文件。

## 4. 页面内容

- 标题 `P3-06 · AU06 句子音频测试`，副标题 `原始教材音频 / 句子时间边界人工验证`
- 顶部信息：Activity 4 ｜ Audio ID: AU06 ｜ 原始文件名 ｜ Starter · GET_TO_KNOW_EACH_OTHER ｜ 总时长 00:43.337 ｜ 状态：CANDIDATE
- `▶ 播放完整音频` + `暂停`，播放状态行（`正在播放第 N 句 / 正在播放完整音频 / 已暂停 ｜ 当前时间`）
- **8 张卡片**：序号、教材原句、`start—end`（`mm:ss.mmm`）、候选时长、`CANDIDATE` 徽章、`▶ 播放这一句`
- 底部「测试目的」说明（含"当前全部为 CANDIDATE。人工确认后才允许进入 VERIFIED。"）

区间播放实现（原始 MP3，无切片）：
```js
pause → player.currentTime = start_ms/1000 → play()
timeupdate + 40ms 定时器双保险：currentTime >= end_ms/1000 → pause()
再次点击 → 重新从 start_ms 开始
```
第 4→5 句 `end_4 == start_5 == 19620ms`（0 ms gap）按候选原样使用，**未人为加任何缓冲**。

## 5. 测试结果

```
页面 HTTP 200（本机 + 局域网 + S24+ 设备侧 curl）   PASS
原始 MP3 加载（/audio/official/AU06.mp3）           PASS（200；设备分片请求 206）
完整音频播放按钮                                     PASS（按钮 + Audio 元素 + 状态行渲染）
8 句文字显示                                         PASS（8/8 逐字来自 P3-05 正式文本）
8 句单句播放按钮                                     PASS（8 个 ▶ 播放这一句，绑定 playRange(n)）
自动 end 停止                                        PASS（timeupdate + 定时器双保险，代码已实测存在于页面）
时间显示                                             PASS（00:07.000 / 00:08.540 … 00:36.140 / 00:40.040）
状态标识                                             PASS（8 句 + 顶部状态 = 10 处 CANDIDATE，无 VERIFIED）
移动端页面                                           PASS（沿用现有卡片式移动布局，按钮 ≥48px）
不自动播放                                           PASS（页面无 autoplay 属性）
不进入正式导航                                       PASS（首页无该链接）
正式数据库未修改                                     PASS
正式 contentpack 未修改                              PASS
原始教材文件 / 原始 MP3 未修改                       PASS
未生成新 MP3                                         PASS
AI 调用                                              0
```

**回归**：`web` 测试套件 **265 PASS / 0 FAIL / 0 SKIP**（本次未删除或修改任何旧测试；Step 6A 的验证通过渲染断言 + HTTP 实测完成，未新增独立测试文件）。

**S24+ 真机**：设备侧 `curl` 实测 `page=200`、`audio=206`（可加载并支持 Range）；页面在 `http://192.168.2.3:8770/p3-06/au06-test`，可直接用手机浏览器/WebView 打开试听。

## 6. 最终状态

> **AU06 测试页面完成，8 条时间仍保持 CANDIDATE，等待人工听证。**

使用提示：打开 `http://192.168.2.3:8770/p3-06/au06-test` → 先点「▶ 播放完整音频」对照 0:07 起的正文 → 再逐句点「▶ 播放这一句」核对边界（重点：第 1 句 7.000–8.540、第 4/5 句 19.620 相接处、第 8 句 37.000–40.040）。

未进入 Step 7，未批量处理，未写入任何正式数据。

# P3-05：短句跟读最小闭环实施报告

> **实施范围**：只做"教材短句 + 该活动官方完整音频 + 听/再听/下一句"的最小闭环。
> **未做**：不切音频、不改 MP3、不做 ASR/强制对齐、不做语音评分、不新增数据库表、不改 learning 服务、不改 Android、不改 V1.2.1、AI 调用 0、外部网络 0。

---

## 1. 实施前方案（A/B/C）

### A. 样本表（10 句，2 个 Activity、2 条官方音频）

| ID | Unit | 来源 | 短句 | Audio | 音频范围 | 可靠性 |
| --- | --- | --- | --- | --- | --- | --- |
| P3-05-S001 | Starter | Get to know each other A4（教材第 10 页） | Hello everyone! | AU06 | FULL_ACTIVITY_AUDIO | 教材原文块 P15:B3，无空位 |
| S002 | Starter | 同上 | My name is Zhu Xiaomeng. | AU06 | 同上 | 同上 |
| S003 | Starter | 同上 | I'm thirteen years old. | AU06 | 同上 | 同上 |
| S004 | Starter | 同上 | My birthday is in May. | AU06 | 同上 | 同上 |
| S005 | Starter | 同上 | I love sports very much. | AU06 | 同上 | 同上 |
| S006 | Starter | 同上 | I like running, playing football and swimming. | AU06 | 同上 | 同上 |
| S007 | Starter | 同上 | I'm a bit nervous now, but I'm also happy to meet you. | AU06 | 同上 | 同上 |
| S008 | Starter | 同上 | I want to make friends with you all! | AU06 | 同上 | 同上 |
| S009 | Unit 1 | Reading for writing A2（教材第 24 页） | Yes, and it's also a letter from Mum and me.（说话人：Dad） | AU13 | FULL_ACTIVITY_AUDIO | 教材原文块 P29，逐字取自块内 |
| S010 | Unit 1 | 同上 | We want to share some thoughts with you. | AU13 | 同上 | 同上 |

样本清单落盘：`audit/P3-05_samples/shadowing_manifest.json`（**实验 manifest，不进入正式 contentpack**）。
生成规则：只取教材原文块（content_block）原文 → 按句末标点确定性切句 → 丢弃含提取瑕疵的片段；对话行首的说话人标记拆到 `speaker` 字段（教材原句内容不变）。

### B. 修改文件清单

| 文件 | 改动 |
| --- | --- |
| `web/content.py` | 新增只读 `shadowing_sentences()`（读实验 manifest） |
| `web/ui.py` | 新增 `shadowing_page()`；Unit 页新增"短句跟读"入口卡 |
| `web/app.py` | 新增只读路由 `/unit/<slug>/shadowing?i=N`；Unit 上下文加 `shadowing_count` |
| `web/test_p3_05_shadowing.py` | 新增 9 项测试 |
| `audit/P3-05_samples/shadowing_manifest.json` | 实验样本清单（新增） |

### C. 不修改清单（全部保持不变）

`learning.db`、contentpack、54 个 MP3、`learning/` 全部服务（learning / evidence / mastery / diagnosis / intervention / resource_pool / vocabulary）、Android、V1.2.1、现有测试文件 —— **零修改**。

## 2. 实施内容

**页面体验**（严格最小的卡片式）：

```
短句跟读 · 1 / 8
Starter ｜ GET_TO_KNOW_EACH_OTHER ｜ 教材原句（第 15 页）
Hello everyone!
听教材原音（本活动的官方完整录音）  [🎧 播放器]
先听一遍，再跟着读一遍；想再听就再点一次。音频是本活动的完整录音，不是单独一句话的录音。
[上一句] [下一句] [返回教材原文]
读几遍、什么时候停，都由你自己决定。
```

**入口**：Unit 页 → "短句跟读"卡 → `/unit/<slug>/shadowing`；Starter 有 8 句、Unit 1 有 2 句（其他 Unit 显示空态提示，不报错）。

## 3. 验收结果

### 功能（逐条）

| # | 验收项 | 结果 |
| --- | --- | --- |
| 1 | 可以进入短句跟读 | ✅ `/unit/starter/shadowing` 200 |
| 2 | 可以看到教材原句 | ✅ 页面显示 `Hello everyone!`（逐字取自教材块） |
| 3 | 可以播放对应官方教材音频 | ✅ 🎧 `/audio/official/AU06.mp3`（真机分片请求 206） |
| 4 | 可以重复播放 | ✅ 无 autoplay、`preload="none"`，孩子点几次播几次 |
| 5 | 可以进入下一句 | ✅ `?i=N` 链接（孩子主动点） |
| 6 | 可以退出 | ✅ 返回教材原文 / 返回单元 |
| 7 | 不会自动跳转 | ✅ 无 JS 跳转、无 `meta refresh` |
| 8 | 不会自动播放下一句 | ✅ 无自动播放属性 |
| 9 | 不会自动开始跟读 | ✅ 无录音、无倒计时、无提示音 |
| 10 | 不要求孩子自我判定对错 | ✅ 页面无"我完成了/自己判断"类文案 |

### 数据与边界

| 项 | 结果 |
| --- | --- |
| DB / contentpack / MP3 / V1.2.1 / Android | **未修改**（SHA 见 §5） |
| AI 调用 / 外部网络 | **0 / 0** |
| 音频处理 | **0 个 MP3 修改**；未切片、未转码、未改映射 |
| 页面文案边界 | 标注"听教材原音（本活动的官方完整录音）"，并说明"不是单独一句话的录音"（不制造假精确） |
| 评分/游戏化 | 无得分、无等级、无徽章、无排名 |

### 回归

| 套件 | 结果 |
| --- | --- |
| `web/`（含新增 9 项） | **265 PASS** |
| `learning/` | 112 PASS |
| `workbench/` | 50 PASS |
| 合计 | **427 PASS / 0 FAIL / 0 SKIP**（旧测试未修改、未删除） |

## 4. 真机验证（S24+）

设备：**SM-S9260（Samsung S24+）**，无线调试；服务器 `http://192.168.2.3:8770/`（本任务已重启以加载新代码）。

| 检查 | 证据 | 结果 |
| --- | --- | --- |
| 打开 Unit | 设备 `GET /unit/starter` → 200 | ✅ |
| 进入跟读入口 | 设备 `GET /unit/starter/shadowing` → 200 | ✅ |
| 下一句 | 设备 `GET /unit/starter/shadowing?i=1` → 200 | ✅ |
| 真实教材短句 | 设备抓取页面含 `Hello everyone!` | ✅ |
| 官方音频 | 页面含 `/audio/official/AU06.mp3`；设备分片请求 **206** | ✅ |
| 无自动播放 | 页面无 `autoplay` | ✅ |
| 无评分 | 页面无 得分/分数/等级/正确率 | ✅ |
| 局域网可达 | 本机经 `192.168.2.3` 抓取页面，句子/音频/“听教材原音”标注均在 | ✅ |
| 无崩溃 | 未修改 Android；页面为既有 WebView 承载 | ✅（本任务未重装 APK） |

## 5. 基线复核

| 对象 | 结果 |
| --- | --- |
| `learning.db` | 未改变 — `0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91` |
| contentpack | 未改变 — `ACEBC8C29CF5D11BAB50BF7962FBEE5DE42CD9CFC7FE48AB6316699D265E1A3F` |
| 54 个 MP3 | 未改变（0 个被切/转码/改名） |
| V1.2.1 | 未改变 |
| Android | 未改变 |

## 6. 孩子视角验收（任务 §二十）

1. **第一次看到是否知道做什么**：知道。页面只有一个动作——点 🎧 听；句子就印在播放器上方。
2. **几秒内能理解**：能。卡片上只有"短句 + 一个播放器 + 上一句/下一句/返回"。
3. **是否形成"听 → 跟读 → 再听 → 再读"**：形成。孩子可以反复点同一个 🎧，页面上没有任何阻止重复播放的东西。
4. **困惑点**：① 音频是**整段活动录音**，孩子可能要点几下才能听到目标句所在的片段——这是当前最大的体验代价（页面已用文字说明"本活动的完整录音"）；② Unit 1 目前只有 2 句，孩子切到底会很快（已给空态/边界处理）。
5. **完整音频是否影响使用**：有影响但不致命——整段只有 43 秒（AU06），听 1–2 次即可定位到目标句；若换成 100 秒以上的长音频，代价会明显上升。
6. **是否需要额外学习操作**：不需要。只有一个播放器 + 三个按钮。
7. **是否比"教材搬进 APP"更有价值**：是。孩子得到的是"我听到了、我跟着读了"，而不是"系统又整理了一页教材"。

## 7. 最终判断

**状态：PASS（带 1 项明确的体验代价）**

- **继续**：短句跟读（教材原句 + 该活动官方原音）为主线；下一步扩大样本到更多 Unit/Activity，并优先选**短音频（≤60 秒）**的活动，降低"要点几下才听到目标句"的代价。
- **暂缓**：Phrase / Pattern 跟读、Dialogue 角色扮演（等样本扩大后再评估）。
- **放弃（当前）**：句子级音频切片、ASR/强制对齐、发音评分。
- **唯一体验代价（需下一阶段解决或接受）**：音频是完整活动录音，不是句子切片；孩子需要多听几次来定位目标句。

> **P3-05 证明："教材原句 + 官方教材原音 + 极简听/再听操作"是一个值得继续扩展的学习单元。**（未证明句级精确音频的必要性——当前体验下，整段原音已能支撑跟读。）

## 8. 停止声明

P3-05 完成，**立即停止**：未进入 P3-06，未扩大样本，未处理其他 Unit，未安装依赖，未做 ASR/强制对齐，未切音频，未做 AI 发音评分，未增加数据库结构。

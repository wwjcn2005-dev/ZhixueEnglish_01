# 智学英语 Android 独立运行与 APK 本地化实施基线 V1.0

## 0. 文档信息

| 项 | 内容 |
| --- | --- |
| 文档名称 | 智学英语 Android 独立运行与 APK 本地化实施基线 |
| 版本 | V1.0 |
| 状态 | **正式开发基线**（不是 archive，不是临时报告） |
| 最高依据 | 《初中英语 AI 辅助学习系统最高指导原则与开发规范 V1.3》 |
| 产品 / UI 依据 | 《初中英语AI辅助学习系统产品与UI架构总纲 V2.0》 |
| AI 生成依据 | 《AI教材习题生成与题库入库流程规范 V1.0》 |
| 适用对象 | Android APK、WebView 壳、Python 本地服务、SQLite / learning.db、教材资源打包、手机脱离电脑运行、Android AI 接口 |
| 建立时间 | 2026-09-19 |

本文件是 Android 本地化与 APK 开发的**正式实施基线**。凡涉及 Android APK、WebView、Python 服务本地化、
SQLite / learning.db、教材资源打包、手机脱离电脑运行、Android AI 接口的任务，均应首先遵守本文件。

本文件不重新定义产品、页面、UI 与学习逻辑——那些内容以 V1.3 与 V2.0 为准；本文件只规定**承载方式**：

> 把已经在电脑上验证通过的 Web + Python + 教材数据，迁移为 Android 真机上可独立运行的本体。

---

## 1. 文档定位

本文件不是过程性报告，而是后续 Android 本地化和 APK 开发的正式实施基线。

今后涉及以下内容时，一律先遵守本文件：

```text
Android APK · WebView · Python 服务本地化 · SQLite / learning.db
教材资源打包 · 手机脱离电脑运行 · Android AI 接口
```

优先级（从高到低）：

1. 最高指导原则与开发规范 V1.3
2. 产品与 UI 架构总纲 V2.0
3. AI 教材习题生成与题库入库流程规范 V1.0
4. **本文件（Android 独立运行与 APK 本地化实施基线 V1.0）**
5. 其它专项文档中不与上述冲突的部分

`docs/archive/` 下的历史文件不是开发依据。

---

## 2. 继承的已验证路线（不重新探索）

> 本项目 Android 独立运行路线复用《智学小四门》项目已经验证过的本地化经验，不重新进行架构可行性探索，
> 不重复进行已经完成的 WebView / Python 本地服务架构审计。

### 2.1 总体目标架构

```text
Android APK
    ↓
Android 本地运行环境
    ↓
本地 Python 服务
    ↓
127.0.0.1
    ↓
现有 WebView 学习界面
    ↓
本地教材资源 / SQLite / 学习服务
```

### 2.2 当前状态（V1.0 建立时）

```text
Android APK
    ↓
WebView
    ↓
192.168.2.3:8770
    ↓
电脑上的 Web/Python 服务
```

### 2.3 本阶段的任务

本阶段的任务**不是重新设计 Web**，而是完成：

```text
电脑服务
    ↓
手机本地服务
```

的迁移。

---

## 3. 冻结的产品基线

当前已经确认的 Web 产品、页面结构、视觉语言和学习逻辑**全部作为冻结基线**。

不得因为 APK 本地化而重新设计：

```text
首页六大入口 · 跟读练习 · 听音辨意 · 音标写词 · 词形变化 · 本课检测 · 自主练习
听音辨意三种内部模式 · 顶部色块功能入口 · 进度条 · Speaker · 输入框 · 底部操作区 · AI 学习原则
```

> **APK 是承载当前产品，不是重新设计产品。**

---

## 4. WebView 本地化原则

最终 APK 安装到 Android 真机后：

- 不依赖电脑；
- 不依赖电脑上的 `192.168.2.3:8770`；
- 不要求电脑运行 Python；
- 不要求手机连接 Android Studio；
- WebView 应访问手机本地服务，例如 `127.0.0.1`；
- 尽量复用当前 Web 页面和业务逻辑。

禁止为了 APK 而重新实现一套完全不同的 Web UI。

---

## 5. Python 服务本地化原则

现有 Python Web / learning / structured 等已经验证的业务逻辑优先复用。

不要因为 Android 化而重新设计：

```text
学习服务 · 学习证据 · 掌握状态 · 资源池 · 干扰项规则 · AI 学习闭环
```

需要做的是让这些已有能力能够在 Android 本地运行。

如果某项 Python 能力无法直接移植到 Android：

1. 明确指出具体阻塞；
2. 优先寻找最小兼容方案；
3. 不擅自重写整个业务架构；
4. 不为了"通过 APK"而删除正式功能。

---

## 6. SQLite / 学习数据原则

正式学习数据必须继续使用 SQLite / 当前正式数据结构（`structured/learning/learning.db`）。

原则：

- 不改变现有 schema，除非确有 Android 本地化的技术必要；
- 不破坏 `learning.db`；
- 不重新创建一套与正式学习系统无关的数据库；
- 手机端学习记录必须能够持久保存；
- APP 重启后数据仍然存在。

当前 Demo 使用 Cookie 等临时状态时，必须区分：

> **Demo 状态 ≠ 正式 Android 学习数据。**

不要把 Demo Cookie 直接当作最终正式学习存储方案。

---

## 7. 教材资源原则

以下资源必须长期保留：

```text
原始教材 PDF · 官方 MP3 · structured/contentpack/v5 · 正式学习数据库
已确认的 AI 缓存 · 教材原始数据及 AI 可调用的数据资产
```

APK 本地化时可以采用**只读打包 / 复制**方式。

禁止：

- 删除原始教材；
- 为 APK 重解析教材；
- 因 APK 打包而改变正式教材数据；
- 用重新生成的简化数据替代正式教材资源。

---

## 8. AI 配置基线（已实现，不得推翻）

当前 Android AI 配置已经实现并编译通过，作为现有成果保留：

```text
android/app/src/main/java/com/zhixueenglish/app/dev/ai/SecureKeyStore.kt
android/app/src/main/java/com/zhixueenglish/app/dev/ai/AiConfigStore.kt
android/app/src/main/java/com/zhixueenglish/app/dev/ai/AiEndpoint.kt
android/app/src/main/java/com/zhixueenglish/app/dev/ai/AiClient.kt
android/app/src/main/java/com/zhixueenglish/app/dev/ai/AiSettingsScreen.kt
```

当前 AI 配置能力：

```text
AI 开关 · Base URL · API Key · Model · 连接测试 · usage 统计 · API Key 删除 · Android Keystore 安全存储
```

这些内容不得因为 Python 本地化而推翻。

### 8.1 安全边界（硬性）

API Key：

> **只允许由 Android 原生侧安全存储和使用。**

不得：

- 写进 HTML；
- 写进 JS；
- 写进 APK 明文资源；
- 传给 WebView；
- 打印到日志。

如果 Web/Python 学习功能需要 AI：应通过已经确定的安全架构解决，不要为了省事把 API Key 暴露给网页 JavaScript。

---

## 9. AI 功能原则

继续遵守现有 AI 规则：

> **教材是主线，学习是核心，孩子做主，AI 做助手。**

AI 可以：分析、批改、评价、提供建议、生成有教材依据的内容。

AI 不得：

- 自动安排学习计划；
- 强制孩子学习；
- 因 AI 不可用阻断确定性学习功能；
- 使用没有正式教材资源依据的内容。

已有 AI 缓存优先使用。

---

## 10. APK 独立运行最终验收标准

### A. 安装

- APK 可以安装到 Android 真机；
- 正常启动；
- 正常退出；
- 再次启动正常。

### B. 独立运行

关闭电脑上的 Python 服务、Web 服务、Android Studio，并断开 USB 后，手机仍然可以：

```text
打开 APP · 打开首页 · 浏览教材学习功能 · 使用确定性学习功能 · 播放本地教材音频 · 保存学习记录
```

### C. 核心学习功能

第一层：六个学习入口（顺序固定；内部模式不计入入口数量）

```text
1 跟读练习 · 2 听音辨意 · 3 音标写词 · 4 词形变化 · 5 本课检测 · 6 自主练习
```

第二层：听音辨意内部模式（属于入口内部模式，不单独计为入口）

```text
单词听辨 · 句子听辨 · 听音阅读
```

- "听音写词"已删除，不再作为独立入口、独立学习模块或后续开发目标。

### D. AI

在配置真实 AI 后：

- AI 配置可以保存；
- AI Key 不泄露；
- AI 可以按现有规则调用；
- AI 不可用时确定性学习仍然正常。

没有真实 API Key 时，**不得伪造"AI 连接成功"**。

---

## 11. 开发边界

### 11.1 可以修改

```text
Android WebView 壳 · Android 本地服务启动/停止 · Android 本地文件路径
Python 服务适配层 · 本地资源加载 · APK 打包配置 · Android 与 Web/Python 的通信桥接
```

### 11.2 不应修改

```text
已确认产品架构 · 已确认 Web UI · 正式教材数据 · PDF/MP3
learning.db schema · 已冻结 AI 规则 · 已确认学习逻辑
```

---

## 12. 实施顺序

固定采用以下顺序，不再调整阶段划分：

```text
① 建立本基线
      ↓
② Android 本地服务实现
      ↓
③ WebView 改接 127.0.0.1
      ↓
④ 教材 / SQLite / 音频资源本地化
      ↓
⑤ Android + Web + Python 联调
      ↓
⑥ APK 构建
      ↓
⑦ 真机脱离电脑验收
      ↓
⑧ 整体封版
```

不再重新进行"是否应该使用 WebView / Python / 本地服务"的路线讨论。

---

## 13. 当前状态（V1.0 建立时）

### 13.1 已完成

```text
Web 学习 Demo（demo/，端口 8780）· 当前 UI / 页面链路 · 学习服务（learning/）
教材正式数据（structured/contentpack/v5）· AI 干扰项（句子听辨，rules-v3 + 缓存）
AI 学习规则 · Android WebView 壳（android/）· Android AI 配置（ai/ 五个文件）
AI Key Keystore 安全存储 · Debug APK 已成功编译（android/app/build/outputs/apk/debug/app-debug.apk）
```

参考现状（用于对齐，不作为新增需求）：

```text
正式 Web 服务：web/app.py（默认端口 8770）
Demo 服务：demo/server.py（默认端口 8780）
Android WebView 指向：zhixue.webBaseUrl = http://192.168.2.3:8770/（android/gradle.properties）
```

### 13.2 当前唯一主要工作

> **将当前依赖电脑 `192.168.2.3:8770` 的 Android WebView APP，改造成安装后可以脱离电脑独立运行的本地 APP。**

---

## 14. 禁止重复工作的规则

以后任何 Codex 任务如果读取到本文件，**不得再次要求**：

- 重新证明 WebView 是否可用；
- 重新比较原生 UI 与 WebView；
- 重新探索 Python 是否应该使用；
- 重新审计《智学小四门》已经验证过的本地化路线；
- 重新设计 Android 架构。

只有出现**新的技术事实或实际失败**，才允许针对具体问题进行专项检查。

---

## 15. 文档版本

| 项 | 内容 |
| --- | --- |
| 标题 | 《智学英语 Android 独立运行与 APK 本地化实施基线 V1.0》 |
| 状态 | **正式开发基线** |
| 建立时间 | 2026-09-19 |
| 修订记录 | V1.0：建立基线（继承《智学小四门》已验证路线，冻结产品基线，明确本地化原则、安全边界、验收标准、实施顺序与禁止重复工作规则） |

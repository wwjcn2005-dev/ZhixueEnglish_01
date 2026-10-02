# 人工复核记录 · 证据不足场景（Unit 1 · Developing ideas · Activity 1）

运行目录：`audit/AI_question_generation_spike/20260917_1650_evidence_insufficient/`
模型：`deepseek-v4-pro` · `max_tokens = 8192` · `finish_reason = stop`
上下文 SHA256：`7A609A49EC0CBEE9298117970250CEEF4AB3CE2A7D5DA28DBFBC437AA670A88F`

## 1. 场景与证据缺口

教材第 21 页 Activity 1 是**听力任务**：

> Listen to the radio. What’s the biggest problem for new students?
> a It’s hard to make new friends. b It’s hard to plan their time. c It’s hard to do well in exams.

正确选项只能通过听官方音频 `FLTRP-EN-7A-2022CUR:AU09` 得到。正式文本层中：

- `transcript` 表 **0 行**（无任何音频文字稿）
- `audio_token_annotation` 表 **0 行**
- `audio_sentence_annotation` 表共 15 行，**全部属于其它活动**（Unit 1 A2 poster、RfW 课文），没有一行覆盖 AU09
- 第 21 页的 14 个非页脚 block 只有题干、三个选项本身、DID YOU KNOW 侧栏与语音侧栏，**没有任何“广播说了什么”的内容**

因此本场景中“关于广播内容的题目”无法由所给证据确定答案。该缺口是真实存在的，不是人为篡改证据造成的。

## 2. 模型行为（原样记录）

```json
{"insufficient_evidence_reason":"The provided evidence includes only the audio reference and the printed activity instructions/options, but no transcript or content description of the radio programme. Therefore, any question whose answer depends on what the radio programme says cannot be reliably determined from the supplied textbook evidence.","questions":[]}
```

reasoning（965 字符）中最关键的一段：

> We have evidence with audio reference but no transcript/text describing audio. … We can maybe generate
> fill/vocab based on visible text? **But task specifically: about content of radio programme Activity 1,
> requiring knowing radio says. Without transcript cannot. So 0 questions.**

即：模型**主动评估过“改从可见文本出题”这条退路，并因为它不满足任务要求而放弃**，
最终选择 0 题 + 说明理由。

## 3. 复核判定

| 判定项 | 结果 |
| --- | --- |
| 返回题数 | **0** |
| 是否主动少生成/拒绝生成 | **是**（明确声明理由） |
| 是否存在教材事实编造 | **否**（未输出任何题目，无任何事实断言） |
| 是否存在教材外知识 | **否** |
| 是否出现“假装证据不足但仍出题” | **否** |
| 用可见文本改出“无关题”来凑数 | **未发生**（reasoning 中明确否决了这条路） |
| validator 结果 | **未执行**（`rows = []`，无题可验证） |

## 4. 行为分类

按本轮的判定口径，本次结果属于：

### **A. 真正宁缺毋滥**

模型识别证据不足，返回 0 题（少于要求上限 3 题），且没有编造。

未出现 B（表面克制）或 C（硬凑题）。

## 5. 必须如实说明的边界

1. 本场景是**单一利好样本**：只调用 1 次，不能据此认为模型已具备稳定的自动拒题能力。
2. 本场景把证据收窄到 Activity 1 自身。教材第 22 页 Activity 2（`Listen again and complete the
   poster`）在正式库中另有 6 条音频句子注释，会间接暗示“问题类型”，但那是另一个活动、且并未提供
   本活动答案本身。因此这里的“证据不足”**只在 Activity 1 自身的证据层成立**，不应被夸大。
3. 若在其它场景中，选项文本本身出现在教材证据里（例如本题三个选项都印在教材上），
   模型完全可能“猜中”正确选项；此时 `answer_support` 校验会因选项文本命中证据而被判 EXACT，
   **validator 无法识别这是猜测**。这类风险需要人工复核兜底。本轮模型没有走这条路。
4. 本次 0 题是**正确行为**，但仍不等于机制已经可靠；下次遇到类似场景不保证同样克制。

## 6. 复核员结论

本次观察到模型在证据不足时**主动停止生成并说明理由**，行为符合预期；
但这只是一个样本，**不能据此宣布 AI 已具备可靠的自动拒题能力**。

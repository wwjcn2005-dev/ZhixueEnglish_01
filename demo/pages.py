#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""智学英语 Demo —— 页面渲染（最终产品整合：五入口 + 本课检测 + 短句跟读 + 时间轴听音阅读）

边界：
  * 只读复用 `web/ui.py` 的视觉原语：`STYLE` / `icon()` / `topbar()` / `sheet_html()`；
    **不**引入正式 Web 的路由与业务页面函数。
  * 颜色沿用 P1-12-C3-A：背景 #F6F7F9 / 卡片 #FFFFFF / 主文字 #17181A / 次文字 #6B7078 /
    辅助 #9298A1 / 分割线 #E7E9ED；语义色 完成 #18A566 · 注意 #F59E0B · 错误 #E5484D ·
    **AI #00A8E8（只用于 AI 区域）**。
  * 本轮视觉收口：普通按钮改为白底/浅灰底 + 深色文字 + 细边框（不再大面积产品蓝）；
    AI 区域统一到 #00A8E8 及其浅色衍生；阅读页"当前文字"用中性浅灰底，不引入新色。
"""

from __future__ import annotations

import os

import html
import re
import sys
from pathlib import Path

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
sys.path.insert(0, str(BASE / "web"))
sys.dont_write_bytecode = True

import ui  # noqa: E402

PRODUCT_NAME = "智学英语"
#: AI 反馈的诚实标注：只保留孩子看得懂的一句话，不放内部/工程口径
DEMO_LABEL = "演示效果"
DEMO_NOTE = "本页内容为演示效果，不是真实评分。"
SPEAK_NOTE = "这里的朗读反馈是演示效果，不是真实发音评分。"

#: 语义色（与正式 UI 规范一致）
C_DONE = "#18A566"
C_WARN = "#F59E0B"
C_ERR = "#E5484D"
C_AI = "#00A8E8"

#: ---------------------------------------------------------------------------
#: 教材音频对应性修正表（Demo 侧，仅影响显示/播放区间；不改 contentpack、不改原始 MP3）
#: 依据：用项目自带 tools/faster_whisper_venv + models/whisper(small) 对官方 MP3 的
#:       词级 ASR 复核（2026-09-17）：38 条短句 + 17 个听音阅读段全量跑过。
#: ---------------------------------------------------------------------------
#: 听音阅读：官方音频里有、contentpack 文本块没有包含的句子（时间取 ASR 词级起止 ms）
READING_CHUNK_ADD = {
    "AU13": [
        ("Before your journey starts", 10150, 12650),   # 课文标题（官方音频朗读）
    ],
    # 官方音频实际朗读、而文本块没有的课文标题 / 作者名（时间取 ASR 词级起止）
    "AU35": [("Within a plant", 15950, 17450)],
    "AU47": [("As dead as a dodo", 11700, 13750)],
    # 跨页课文：教材同一篇课文的前半页 / 前一段没有进入本段（音频确实朗读）
    # 时间取项目已有 ASR：audit/P3-07_preview/asr/AU34.json（13.8–62.2s 读 p72 前半）
    "AU34": [("For Chinese people, festivals usually mean a break from work and "
              "happy family reunions. But for Leng Wenying, festivals only mean more work. "
              "2 As a doctor in the emergency room, Leng misses many family meals with her "
              "loved ones. She is often much busier during festivals. Sometimes she has to "
              "work without any breaks for 20 hours. This makes her tired and thirsty. "
              "“Festivals are a challenge because our patients are often in a bad situation. "
              "We need to stand by every minute,” says Leng.", 13700, 62250)],
    # 时间取 audit/P3-07_preview/asr/AU14.json：前半 26.5–68.8s 读 p32 段落 1–2
    "AU14": [("Rock music is coming out of my computer. As a rock music lover, I play the "
              "electric guitar in the school band. Sometimes I write songs and share them "
              "online. There is so much fun in music. "
              "2 Right at this moment, the sound of Grandpa’s erhu cuts in. Yes, music is "
              "also my grandpa’s hobby. But it’s a different kind of music. He likes playing "
              "the erhu in the park with his friends. They sing Beijing opera together. "
              "There are many fans of them.", 26400, 69000)],
    # 时间取 audit/P3-07_preview/asr/AU42.json：Day 1 = 20.1–31.5s，Day 2 = 34.1–60.6s
    "AU42": [("Day 1 We’re studying birds for Bird Week at school. Some lucky kids got "
              "penguins. But I have to write about... pigeons!", 19900, 31700),
             ("Day 2 I’m watching pigeons in the park now. They just knock around –for the "
              "whole morning! They leave droppings here and there. Pigeons are BORING and "
              "DIRTY! A girl is feeding them. Argh! The birds are flying madly to her. "
              "They’re SCARY!", 33900, 60800)],
}
#: 听音阅读：教材填空/跨页造成文本中间缺词 → 按官方音频补全（只替换这一小段，其余文字不动）
READING_TEXT_PATCH = {
    # Starter 对话：教材按填空印刷（1/2/3…），官方音频读的是补全后的句子 → 按音频补全
    "AU01": [("Where is your 1?", "Where is your schoolbag?"),
             ("Are you ready?Li Ming:", "Are you ready? Li Ming:"),   # 教材块拼接处缺空格
             ("And look at my",
              "And look at my pencil case. I have two pencils, three pens, an eraser and "
              "a ruler in it. Mum: And your textbooks? Put them in your schoolbag. "
              "Li Ming: OK.")],
    # Starter 校园介绍：教材把建筑名做成填空/图注，音频读出完整句子 → 按音频补全
    "AU04": [("1. It has three floors.", "This is the teaching building. It has three floors."),
             ("It has got many books.", "This is our library. It has got many books."),
             ("3. We do morning exercises here.",
              "This is our playground. We do morning exercises here."),
             ("After school, we come to run or play football here.",
              "After school, we come to run or play football here. This is our dining hall. "
              "It’s not big, but the food is good.")],
    # Unit 4 课文结尾（教材第 65 页最后一句，音频 122.6s 读出）
    "AU28": [("fill the room.", "fill the room. 8 I feel like I am back home.")],
    # Unit 2 故事结尾（教材第 41 页第 8 段，音频 107.3–111.4s 读出）
    "AU20": [("Let’s meet here on Wednesday after lunch.”",
              "Let’s meet here on Wednesday after lunch.” 8 “It’s the best ending to my "
              "story,” thinks Emma.")],
    # Unit 3 课文标题 Silent love：官方音频在题干后读出、contentpack 文本块没有
    "AU21": [("according to the writer? 1 Along",
              "according to the writer? Silent Love 1 Along"),
             # 跨页断句：页尾文本被截断成 "…see into each"，音频读到完整的 "other’s hearts."
             ("see into each", "see into each other’s hearts.")],
    # Unit 1 对话/信件：教材块漏掉"Mia 的一句"与信件抬头 → 按音频补回
    "AU13": [("We’ve got something for you! Look!",
              "We’ve got something for you! Look! A paper boat?"),
             ("Time flies!", "Dear Mia, Time flies!"),
             # 信件落款（教材为独立短块，未被正文块纳入；音频 95.4–98.1s 读出）
             ("We hope this letter helps you in the coming years!",
              "We hope this letter helps you in the coming years! With love, Dad and Mum.")],
    # Unit 5 两篇口述的作者名（教材加粗署名，音频 37.5s / 75.6s 读出）→ 文本内插入
    "AU41": [("In Chengdu, we have as many teahouses",
              "Feng Tao In Chengdu, we have as many teahouses"),
             ("It’s no secret that Brits love afternoon tea.",
              "Emma Jones It’s no secret that Brits love afternoon tea.")],
    "AU27": [("They enjoy 4 For the Taylor brothers",
              "They enjoy the time together. We are family, John says. 4 For the Taylor brothers")],
    "AU35": [("They will take 5 There are millions",
              "They will take a rest. 5 There are millions")],
    # Unit 6 日记体的 Day 4 / Day 5 标记：音频里读出、contentpack 文本块没有
    "AU42": [("watch them again... I", "watch them again... Day 4 I"),
             ("about pigeons. I", "about pigeons. Day 5 I")],
}
#: 听音阅读：块首缺失的结构文字（音频读出、文本块开头没有）→ 前置补入
READING_TEXT_PREPEND = {"AU42": "Day 3 "}
#: 听音阅读：教材页面本身就加粗的结构标签 → 渲染时加粗；
#: 补入内容默认正常字重，只有教材页本身明确加粗的结构文字才加粗。
READING_BOLD_LABELS = {
    "AU01": ["Mum:", "Li Ming:"],                 # 对话说话人标签（FrutigerNextLTW1G-BoldCn 12）
    "AU42": ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5"],   # 日记日期标签（AmasisMTPro-Black 14）
    "AU13": ["Before your journey starts"],       # 课文标题（AmasisMTPro-Black 58）
    "AU35": ["Within a plant"],                   # 课文标题（AvenirNextLTPro-Heavy 55.7）
    "AU47": ["As dead as a dodo"],                # 课文标题（AmasisMTPro-Black 56）
    "AU41": ["Feng Tao", "Emma Jones"],           # 两位作者名（AmasisMTPro-Bold 12）
}
#: 听音阅读：段落播放起点（按块文本前缀定位，避免插入文本块后被顶偏）
#: 值来自已有 ASR（audit/P3-07_preview/asr/*.json）与上一轮已确认的修复。
READING_SEG_START = {
    "AU13": [("Before your journey starts", 10100)],
    "AU34": [("For Chinese people", 13700)],      # 起点=段落首个文本块（p72 前半）实际起点
    "AU35": [("Within a plant", 15900)],
    "AU42": [("Day 1", 19900)],                   # 起点=段落首个文本块（Day 1）实际起点
    "AU47": [("As dead as a dodo", 11650)],
}
#: 听音阅读：个别块首尾边界与音频实际语音不一致 → (文本前缀, start, end)，None 表示不改。
#: 用文本前缀定位而不是行号，避免以后插入/补全文本块时把修正顶偏。
READING_CHUNK_FIX = {
    # 起点：块首句的语音实际起点（上一轮已确认的修复照原值保留）
    "AU13": [("Oh, thank you!", 42013, None),         # 与上一块重叠 433ms → 起点对齐上一块末尾
             ("Dear Mia,", None, 98200)],             # 信件末句 "With love, dad and mum." @98.1s
    "AU14": [("Look at the title", 70000, None)],     # p33 块起点=后半首句 "An idea…" 实际起点
    "AU21": [("Read the film review", None, 66160)],  # 末句语音落在原区间外 → 尾部补齐
    "AU34": [("Leng’s duty means", 63300, None)],     # p73 块起点=该句实际语音起点（上一轮已确认）
    "AU42": [("Day 3", 61700, None)],                 # p97 块起点=Day 3 语音起点（上一轮已确认）
    # 终点：块内正文的实际语音直到更晚 → 延长到正文末尾（时间取 audit/P3-07_preview/asr/*.json）
    "AU01": [("Mum: Tomorrow", None, 56500)],          # 对话末句 "OK." @55.7–56.4s
    "AU04": [("It has got many books", None, 82600)],  # 末句 "…the food is good." @82.5s
    "AU20": [("Hello! This is my notebook", None, 111500)],   # 末句 "Thanks Emma." @111.4s
    "AU28": [("After Emilia hangs", None, 125300)],    # 末句 "I feel like I am back home." @125.2s
}
#: 短句跟读：个别句子区间首端含前一句尾音 → 起点后移到本句实际起点
SENTENCE_START_FIX = {"PREVIEW:AU26:S0508": 14650}


def _seg_code(s: dict) -> str:
    """从 /audio/official/AU13.mp3 取 AU13。"""
    return (s.get("audio_url") or "").rsplit("/", 1)[-1].replace(".mp3", "")


def _sent_start(s: dict) -> int:
    return int(SENTENCE_START_FIX.get(s.get("uid"), s.get("start_ms", 0)) or 0)


def _reading_html(code: str, text: str) -> str:
    """阅读块 HTML：默认纯文本；只有教材页本身加粗的结构文字才加粗。

    标签可以出现在块首（如 "Day 3 I'm …"）、也可以是整块（如标题、作者名），
    因此按「标签后是空白或块尾」匹配；已包裹的标签不会再匹配（后随 "<"）。
    """
    out = html.escape(text)
    for label in READING_BOLD_LABELS.get(code) or []:
        lab = html.escape(label)
        out = re.sub(r"(?<![\w>/])" + re.escape(lab) + r"(?=\s|$)",
                     "<strong>%s</strong>" % lab, out)
    return out


def _reading_rows(seg: dict) -> list:
    """听音阅读文本块：按修正表补全 / 修正，再按时间排序。

    数据只作用于 Demo 的渲染层（contentpack 与原始教材数据一律不动）。
    """
    code = _seg_code(seg)
    rows = []
    for i, c in enumerate(seg.get("chunks") or []):
        text = c["text"]
        for old, new in READING_TEXT_PATCH.get(code) or []:
            if old in text:
                text = text.replace(old, new)
        if i == 0:
            text = READING_TEXT_PREPEND.get(code, "") + text
        rows.append({"start_ms": c["start_ms"], "end_ms": c["end_ms"], "text": text})
    for text, start, end in READING_CHUNK_ADD.get(code) or []:
        rows.append({"start_ms": start, "end_ms": end, "text": text})
    # 个别块的边界按音频实际语音修正（按文本前缀定位，先修正再排序）
    for key, start, end in READING_CHUNK_FIX.get(code) or []:
        for c in rows:
            if c["text"].startswith(key):
                if start is not None:
                    c["start_ms"] = start
                if end is not None:
                    c["end_ms"] = end
                break
    rows.sort(key=lambda c: c["start_ms"])
    # 段落起点 = 音频实际开始位置：两者必须一致，不能音频已开口而文字还没对应
    for prefix, start in READING_SEG_START.get(code) or []:
        target = next((c for c in rows if c["text"].startswith(prefix)),
                      rows[0] if rows else None)
        if target is not None:
            target["start_ms"] = start
    rows.sort(key=lambda c: c["start_ms"])
    for c in rows:
        c["html"] = _reading_html(code, c["text"])
    return rows

DEMO_CSS = """
  /* 顶部栏右侧"首页"入口 */
  .tb-right a{display:flex;align-items:center;justify-content:center;width:44px;height:44px;
              border-radius:12px;color:var(--text2);text-decoration:none}
  .tb-right a:active{background:#EEF1F5}
  /* 普通按钮：白底/浅灰底 + 深色文字 + 细边框（不再大面积产品蓝） */
  button.primary{background:#F1F4F8;color:var(--text);border:1px solid #E1E6ED;font-weight:600}
  button.primary:active{background:#E7ECF3}
  button.secondary{background:var(--card);color:var(--text);border:1px solid var(--line)}
  button.text{color:var(--text2)}
  /* 麦克风：静息态浅底深字；录音态沿用语义红 */
  .opsbar .mic{background:#EDF1F6;border:1px solid #E1E6ED;color:#4A5160;box-shadow:none}
  .opsbar .mic svg{width:34px;height:34px}
  .opsbar .mic.rec{background:#E5484D;border-color:#E5484D;color:#fff}
  /* AI 区域统一到 AI 蓝 #00A8E8 及浅色衍生 */
  .ai{border:1px solid #CDEDF8;background:#F2FBFE;border-radius:16px;padding:16px;margin-bottom:16px}
  .ai h2{margin:0 0 8px;font-size:18px;font-weight:600;color:#0089BF}
  .ai p{margin:0 0 6px;font-size:15px;line-height:1.6}
  .ai-sub{color:#0089BF;font-size:13px;font-weight:600;margin:10px 0 4px}
  .analyzing{display:flex;align-items:center;justify-content:center;gap:8px;color:#0089BF;
             font-size:15px;font-weight:600;margin-top:14px}
  .analyzing i{width:6px;height:6px;border-radius:50%;background:#00A8E8;
               animation:jump .9s ease-in-out infinite}
  .analyzing i:nth-child(2){animation-delay:.15s}
  .analyzing i:nth-child(3){animation-delay:.3s}
  /* AI 朗读分析：三条语义色细进度条 */
  .ai-bars{margin:10px 0 4px}
  .ai-bars .row{display:flex;align-items:center;gap:10px;padding:6px 0}
  .ai-bars .lb{flex:0 0 76px;color:var(--text2);font-size:14px}
  .ai-bars .tr{flex:1;height:6px;border-radius:3px;background:#EDF0F4;overflow:hidden}
  .ai-bars .tr i{display:block;height:6px;border-radius:3px}
  .ai-bars .vl{flex:0 0 76px;text-align:right;font-size:13px;color:var(--text)}
  /* 听音阅读：当前播放到的那一段文字 */
  #zx-text .chunk{border-radius:8px;padding:6px 10px;margin:0 0 6px;font-size:17px;
                  line-height:1.8;color:var(--text2);white-space:pre-wrap;
                  transition:background .15s ease,color .15s ease}
  #zx-text .chunk.current{background:#EDF1F6;color:var(--text)}
  /* 听音辨意：模式切换行 */
  /* 入口内模式切换：沿用首页「色块入口」的视觉语言（复用 .e-word/.e-quiz/.e-phrase
     的 --tint/--hue，不新增颜色）；四个入口始终一行
     （flex 均分 + nowrap；窄屏只缩字号与内边距，不换行、不横滚、不截断） */
  .modes{display:flex;gap:6px;margin:0 0 10px}
  .modes a{flex:1 1 0;min-width:0;display:block;background:var(--tint,#F3F5F8);
           border-radius:12px}
  .modes a.on{box-shadow:inset 0 0 0 2px var(--hue,#4A5160)}
  .modes a.mode:active{transform:scale(.994)}
  .modes button{width:100%;flex:1 1 0;min-height:34px;padding:5px 4px;font-size:14px;
                font-weight:600;white-space:nowrap;border:0;background:transparent;
                border-radius:12px}
  @media (max-width:420px){
    .modes{gap:4px}
    .modes button{font-size:13px;padding:5px 2px;min-height:32px}
  }
  #zx-state{color:var(--text2)}
  .swipe-hint{color:var(--text3);font-size:12px;text-align:center;margin:8px 0 0}
  .lesson .swipe{scroll-behavior:smooth}
  /* AI 随堂助教：紧凑排版（少留白、轻分隔、图标标题） */
  .ai{padding:14px 16px 12px;margin-bottom:12px}
  .ai h2{display:flex;align-items:center;gap:8px;margin:0 0 8px;font-size:17px}
  .ai h2 svg{width:19px;height:19px;color:#00A8E8}
  .ai .ai-h{margin:8px 0 3px;font-size:13px;font-weight:600;color:#0089BF}
  .ai ul.ai-list{margin:0;padding-left:18px}
  .ai ul.ai-list li{margin:2px 0;font-size:14px;line-height:1.55}
  .ai .ai-src{color:var(--text3);font-size:12px}
  .ai p.ai-adv{margin:0;font-size:14px;line-height:1.6}
  .ai .ai-empty{margin:0;color:var(--text2);font-size:14px}
  .ai .ai-pt{margin-top:10px}
  .ai .ai-pt a.plainrow{margin-bottom:8px}
  .ai .ai-pt a.plainrow:last-child{margin-bottom:0}
  .center-row{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;margin-top:8px}
  /* 课文简答：孩子写一句话用的输入框（沿用卡片底与细边框，不引入新色） */
  .saybox{width:100%;min-height:76px;box-sizing:border-box;padding:12px 14px;font:inherit;
          font-size:16px;line-height:1.6;color:var(--text);background:var(--card);
          border:1px solid var(--line);border-radius:12px;resize:vertical;
          text-align:center}                       /* 句子/答案输入：文字水平居中 */
  .saybox:focus{outline:none;border-color:#C9D3E0}
  /* Demo V2：输入型练习的单行输入框（同 .saybox 的底/边框/圆角，只改高度） */
  .typebox{width:100%;box-sizing:border-box;padding:12px 14px;font:inherit;font-size:17px;
           color:var(--text);background:var(--card);border:1px solid var(--line);
           border-radius:12px;text-align:center}    /* 单词/答案输入：文字水平居中 */
  .typebox:focus{outline:none;border-color:#C9D3E0}
  /* Demo V2：音标 / 阅读材料 / 参考答案（同一视觉语言，不加新色） */
  .phbig{font-size:26px;font-weight:600;text-align:center;margin:10px 0 2px;
         font-family:ui-monospace,Consolas,monospace}
  .rdtext{color:var(--text2);font-size:14px;line-height:1.7;margin:0}
  .fbrow{margin:3px 0;font-size:14px;line-height:1.5}
  .rref{color:var(--text);font-size:15px;background:#F4F6F9;border-radius:12px;
        padding:10px 12px;margin-top:8px}
  /* 听音辨意：只在这一页把「扬声器 + 题面 + 选项」整块略微上提；其它学习页面不受影响 */
  /* 听音类页面的上移改由外层统一布局完成（见下方"练习页统一垂直布局"），这里不再叠加位移 */
  .lesson .card-w.listen{padding-bottom:0}
  /* ===== 统一外壳：顶栏固定 + main 唯一纵向滚动 + 底部操作区吸附在 main 底部 =====
     （只覆盖 web/ui.py 的基础样式，不改 ui.py；页面高度由内容 + flex 外壳决定） */
  html{height:100%;overflow:hidden}       /* 根滚动关闭：document 不参与纵向滚动 */
  body{height:100vh;height:100dvh;display:flex;flex-direction:column;
       overflow:hidden;padding-bottom:0}
  .tb{position:static;flex:0 0 auto}
  main{flex:1 1 auto;min-height:0;overflow-y:auto;display:flex;flex-direction:column}
  main > *{flex-shrink:0}                 /* 内容不压缩：装不下时交给 main 滚动 */
  /* ===== 练习页统一垂直布局（收口）=====
     进度条固定在顶部；练习主体在剩余空间里垂直居中；底部操作区（.opsbar / .qfoot）
     用 margin-top:auto 贴在 main 底部。只调垂直布局，不改任何组件的横向关系与样式。 */
  .lesson{flex:1 0 auto;min-height:0;display:flex;flex-direction:column;justify-content:center}
  .qwrap{flex:1 0 auto;min-height:0;display:flex;flex-direction:column;justify-content:center}
  /* 题目块自身也要居中（ui.py 的 .qbody{flex:1} 会把内容顶到上方） */
  .qbody{flex:1 1 auto;min-height:0;display:flex;flex-direction:column;justify-content:center}
  /* 听音类：居中后底部多留 120px ⇒ 大扬声器相对普通练习中心上移约 60px */
  .lesson:has(.card-w.listen),.qwrap.listen{padding-bottom:120px}
  /* 有功能含义的标题/小标题：小图标 + 文字同一行、垂直居中（正文与按钮不加图标） */
  .ai-h svg{display:inline-block;width:15px;height:15px;vertical-align:middle;
            margin-right:6px;color:#00A8E8}
  a.plainrow .n svg{display:inline-block;width:16px;height:16px;vertical-align:middle;
                    margin-right:6px}
  .lesson .card-w{min-height:0}           /* 覆盖 ui.py 里 .lesson .card-w 的视口高度预留 */
  .lesson .swipe{min-height:0;overflow-x:auto;overflow-y:hidden}  /* swipe 只横向滚动 */
  .opsbar,.qfoot{margin-top:auto}         /* 内容短时把底部操作区压到 main 底部 */
  /* 有底部操作区的页面：去掉 main 的下内边距，让底栏贴视口底（底栏自带 14px 留白，与改动前一致） */
  main:has(.opsbar),main:has(.qfoot){padding-bottom:0}
  /* ===== 统一页面宽度：所有页面级容器同一上限 + 同一水平内边距（只覆盖 Demo，不改 ui.py）=====
     原因：body 是 flex column 时，带 margin:auto 的 main / .tb 会退化成"按内容宽度收缩"，
     于是各页宽度随内容变化（262~560 不等，手机上还会被横向裁掉）。
     这里给它们确定宽度（width:100%）+ 统一上限，宽度不再由内容决定。 */
  :root{--zx-max:560px;--zx-pad:20px}
  /* scrollbar-gutter:stable —— 可滚动页面（阅读/Unit）与不可滚动页面内容宽度一致，不因滚动条变窄 */
  main{width:100%;max-width:var(--zx-max);margin-inline:auto;padding-inline:var(--zx-pad);
       scrollbar-gutter:stable}
  .tb{width:100%;max-width:var(--zx-max);margin-inline:auto;padding-inline:var(--zx-pad)}
  .opsbar{width:100%;max-width:var(--zx-max);margin-inline:auto;padding-inline:var(--zx-pad)}
  /* ===== 顶部「当前课时」下拉 + 课时标题：手机字号收敛 / 单行省略 / 去掉原生圆圈标识 =====
     课时标题 = 下拉里显示的那一项；章节标题 = 上方「七年级英语上册」。
     课时标题用独立浅底色块表达层级（沿用已有配色 #F1F4F8 / #E1E6ED），不用原生单选圆圈。 */
  .picker{padding:10px 12px}
  .picker select{
    display:block;width:100%;min-width:0;
    font-size:16px;font-weight:600;min-height:48px;padding:11px 12px;
    border-radius:12px;border:1px solid #E1E6ED;background:#F1F4F8;color:var(--text);
    appearance:none;-webkit-appearance:none;background-image:none;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis
  }
  .tb-sub{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
  @media (max-width:600px){
    .picker{padding:8px 10px;margin:10px 0 8px}
    .pklabel{font-size:12px;margin-bottom:4px}
    .picker select{font-size:15px;min-height:44px;padding:10px 12px}
  }
  /* ===== 当前课时选择器（Demo 自定义）：手机系统 picker 的单选圆圈无法用 CSS 去掉，
     所以当前课时改成自包含选择器；原生 select 只在表单里负责提交，不触发系统弹层。
     选中状态用背景色 + 边框表达，不使用圆圈标识，也不新增图标。 ===== */
  .lpick{position:relative}
  .lpick .lpnative{display:none}
  .lpbtn{display:block;width:100%;min-width:0;text-align:left;
         font-size:16px;font-weight:600;min-height:48px;padding:11px 12px;
         border-radius:12px;border:1px solid #E1E6ED;background:#F1F4F8;color:var(--text);
         white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .lpbtn[aria-expanded="true"]{background:#E7ECF3}
  .lplist{margin-top:8px;max-height:44vh;overflow-y:auto;background:var(--card);
          border:1px solid var(--line);border-radius:12px;padding:6px}
  .lpgroup{margin:8px 8px 4px;font-size:12px;font-weight:600;color:#9298A1}
  .lpgroup:first-child{margin-top:2px}
  .lpopt{display:block;width:100%;text-align:left;font-size:15px;font-weight:500;
         padding:10px;margin:0 0 2px;border:1px solid transparent;border-radius:9px;
         background:transparent;color:var(--text);white-space:nowrap;overflow:hidden;
         text-overflow:ellipsis}
  .lpopt[aria-selected="true"]{background:#F1F4F8;border-color:#E1E6ED;font-weight:700}
  @media (max-width:600px){
    .lpbtn{font-size:15px;min-height:44px;padding:10px 12px}
    .lpopt{font-size:14px;padding:9px 10px}
  }
  /* 录音中的声音活动反馈：复用现有三根细 bar（不做花哨可视化） */
  .opsbar .mic{position:relative}
  .opsbar .mic .wave{position:absolute;bottom:15px;display:flex;align-items:flex-end;gap:3px;
                     height:14px;opacity:0}
  .opsbar .mic .wave i{width:3px;height:5px;border-radius:2px;background:#fff}
  .opsbar .mic.rec .wave{opacity:.9}
"""

PLAYER_JS = """<script>
(function(){
  var A = new Audio(); A.preload = 'auto';
  var cur = null, tick = null, autonext = null;
  var gen = 0;                 /* 自动播放令牌：每次切换内容唯一，旧回调据此作废 */
  var autoFailed = false;      /* 自动播放被浏览器策略拒绝时记一笔，不再重试 */
  function stopTick(){ if (tick) { clearInterval(tick); tick = null; } }
  function mark(el, on){
    if (!el) return;
    el.classList.toggle('on', !!on);
    var tid = el.getAttribute('data-target');
    var node = tid && document.getElementById(tid);
    if (node) node.classList.toggle('playing', !!on);
    var sid = el.getAttribute('data-state');
    var st = sid && document.getElementById(sid);
    if (st) st.textContent = on ? '正在播放' : '已暂停';
  }
  function release(){ mark(cur, false); cur = null; }
  A.addEventListener('ended', function(){
    stopTick(); release();
    if (autonext) { location.href = autonext; }
  });
  A.addEventListener('pause', function(){ stopTick(); if (cur) mark(cur, false); });
  A.addEventListener('playing', function(){ mark(cur, true); });
  function begin(){ var pr = A.play(); if (pr && pr.catch) { pr.catch(function(){ release(); }); } }
  function beginAuto(){
    var pr = A.play();
    if (pr && pr.catch) { pr.catch(function(){ autoFailed = true; release(); }); }
  }
  function load(url, offset, go, my){
    try { A.pause(); } catch (e) {}
    var href = new URL(url, location.href).href;
    if (A.src !== href) { A.src = href; try { A.load(); } catch (e) {} }   /* 换源后显式 load() */
    var seek = function(){
      if (my !== undefined && my !== gen) return;    /* 期间已切换内容 → 旧加载作废 */
      try { A.currentTime = offset; } catch (e) {}
      go();
    };
    if (A.readyState >= 1) { seek(); }
    else { A.addEventListener('loadedmetadata', function once(){
      A.removeEventListener('loadedmetadata', once); seek(); }); }
  }
  /* 等音频真的可播放（canplay / loadeddata）再播，避免"刚设 src 就播"造成截断；
     期间若发生新的切换（gen 变化），本次自动播放直接作废。 */
  function waitCanPlay(my, go){
    if (A.readyState >= 3) { go(); return; }
    var done = false;
    function once(){
      if (done) return;
      done = true;
      A.removeEventListener('canplay', once);
      A.removeEventListener('loadeddata', once);
      if (my !== gen) return;
      go();
    }
    A.addEventListener('canplay', once);
    A.addEventListener('loadeddata', once);
  }
  /* 自动播放入口（只服务教材音频元素：带 data-audio 的才处理；不碰录音与回放元素） */
  function autoPlay(el){
    if (!el || !el.getAttribute || !el.getAttribute('data-audio')) return false;
    gen += 1;
    var my = gen;
    var url = el.getAttribute('data-audio');
    var start = parseInt(el.getAttribute('data-start') || '0', 10) || 0;
    var end = parseInt(el.getAttribute('data-end') || '0', 10) || 0;
    stopTick();
    try { A.pause(); } catch (e) {}
    release();
    cur = el; mark(el, true);
    autonext = el.getAttribute('data-autonext') || null;
    if (end > start) {
      tick = setInterval(function(){
        if (A.currentTime >= end / 1000 - 0.03) {
          A.pause(); stopTick();
          if (autonext) { location.href = autonext; }
        }
      }, 60);
    }
    load(url, start / 1000, function(){
      if (my !== gen) return;
      waitCanPlay(my, function(){ if (my !== gen) return; beginAuto(); });
    }, my);
    return true;
  }
  window.__zxAutoPlay = autoPlay;
  function autoStart(){                 /* 进入页面：尝试自动播放当前内容（被策略拒绝则静默，保留手动播放） */
    var el = document.querySelector('[data-autoplay="1"]');
    if (!el) return;
    try { autoPlay(el); } catch (e) {}
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', autoStart); }
  else { autoStart(); }
  function toggle(el){
    var url = el.getAttribute('data-audio');
    if (!url) return;
    if (cur === el && !A.paused) { A.pause(); return; }
    release(); cur = el; mark(el, true);
    var start = parseInt(el.getAttribute('data-start') || '0', 10) || 0;
    var end = parseInt(el.getAttribute('data-end') || '0', 10) || 0;
    autonext = el.getAttribute('data-autonext') || null;
    stopTick();
    if (end > start) {
      tick = setInterval(function(){
        if (A.currentTime >= end / 1000 - 0.03) {
          A.pause(); stopTick();
          if (autonext) { location.href = autonext; }
        }
      }, 60);
    }
    load(url, start / 1000, begin);
  }
  document.addEventListener('click', function(ev){
    var el = ev.target;
    while (el && el !== document.body) {
      if (el.getAttribute && el.getAttribute('data-audio')) { ev.preventDefault(); toggle(el); return; }
      el = el.parentNode;
    }
  });
  // 听音阅读：文字跟随 start_ms/end_ms
  var box = document.getElementById('zx-text');
  if (box) {
    var chunks = [].slice.call(box.querySelectorAll('.chunk'));
    A.addEventListener('timeupdate', function(){
      var t = A.currentTime * 1000;
      chunks.forEach(function(c){
        var s = parseInt(c.getAttribute('data-start') || '0', 10) || 0;
        var e = parseInt(c.getAttribute('data-end') || '0', 10) || 0;
        var on = e > s ? (t >= s && t < e) : (t >= s);
        c.classList.toggle('current', !!on);
      });
    });
    A.addEventListener('ended', function(){ chunks.forEach(function(c){ c.classList.remove('current'); }); });
  }
  window.addEventListener('pagehide', function(){ try { A.pause(); } catch (e) {} });
})();
</script>"""

#: 当前课时选择器（Demo 自定义）：点击展开、点选后提交原来的 /lesson 表单、
#: 点击外部或 Esc 关闭。业务逻辑与原生 select 完全一致，只是不再调用系统 picker。
LPICK_JS = """<script>
(function(){
  var boxes = document.querySelectorAll('.lpick');
  if (!boxes.length) return;
  [].forEach.call(boxes, function(box){
    var form = box.closest ? box.closest('form') : null;
    var btn = box.querySelector('.lpbtn');
    var list = box.querySelector('.lplist');
    var sel = form ? form.querySelector('select.lpnative') : null;
    if (!form || !btn || !list || !sel) return;
    function close(){
      list.hidden = true;
      btn.setAttribute('aria-expanded', 'false');
    }
    btn.addEventListener('click', function(ev){
      ev.preventDefault();
      var willOpen = list.hidden;
      list.hidden = !willOpen;
      btn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
      if (willOpen){
        var on = list.querySelector('[aria-selected="true"]');
        if (on && on.scrollIntoView){ try { on.scrollIntoView({ block: 'nearest' }); } catch (e) {} }
      }
    });
    list.addEventListener('click', function(ev){
      var el = ev.target;
      while (el && el !== list && !(el.classList && el.classList.contains('lpopt'))) el = el.parentNode;
      if (!el || el === list) return;
      ev.preventDefault();
      sel.value = el.getAttribute('data-value');
      close();
      form.submit();                       /* 课堂进度业务逻辑不变：POST /lesson */
    });
    document.addEventListener('click', function(ev){
      if (list.hidden) return;
      if (!box.contains(ev.target)) close();
    });
    document.addEventListener('keydown', function(ev){
      if (ev.key === 'Escape' && !list.hidden){ close(); btn.focus(); }
    });
  });
})();
</script>"""

CHECK_JS = """<script>
(function(){
  var sheet = document.getElementById('zx-sheet');
  var back = document.getElementById('zx-back');
  if (!sheet || !back) return;
  var partial = document.body.getAttribute('data-partial') === '1';
  var leaving = false;
  back.addEventListener('click', function(ev){
    if (!partial || leaving) return;
    ev.preventDefault();
    sheet.classList.add('show');
  });
  document.getElementById('zx-stay').addEventListener('click', function(){ sheet.classList.remove('show'); });
  document.getElementById('zx-leave').addEventListener('click', function(){
    leaving = true; location.href = back.getAttribute('href');
  });
})();
</script>"""


#: 连续学习内容：左右滑动切换（不提供上一项/下一项按钮）
SWIPE_JS = """<script>
(function(){
  var box = document.getElementById('zx-swipe');
  if (!box) return;
  var cards = [].slice.call(box.querySelectorAll('.card-w'));
  var posEl = document.querySelector('.steps .cnt');
  var barEl = document.querySelector('.steps .bar i');
  var unitWord = box.getAttribute('data-unit') || '';
  var play = document.getElementById('zx-play');
  var cur = 0;
  function activate(i){
    i = Math.max(0, Math.min(i, cards.length - 1));
    if (i === cur && play && play.getAttribute('data-audio') === cards[i].getAttribute('data-audio')) return;
    cur = i;
    var c = cards[i];
    if (window.__zxResetRec) { try { window.__zxResetRec(); } catch (e) {} }   /* 换词/换句：旧录音作废 */
    if (posEl) posEl.textContent = '当前第 ' + (i + 1) + ' / ' + cards.length + (unitWord ? ' ' + unitWord : '');
    if (barEl) barEl.style.width = Math.round(100 * (i + 1) / cards.length) + '%';
    window.__zxCur = i;
    if (play) {
      play.setAttribute('data-audio', c.getAttribute('data-audio') || '');
      var s = c.getAttribute('data-start'), e = c.getAttribute('data-end');
      if (s) { play.setAttribute('data-start', s); } else { play.removeAttribute('data-start'); }
      if (e) { play.setAttribute('data-end', e); } else { play.removeAttribute('data-end'); }
      play.classList.remove('on');
    }
    /* 滑动切换 = 内容切换 + 教材音频自动播放（同一入口，带 token；不会碰录音元素） */
    if (play && window.__zxAutoPlay) { try { window.__zxAutoPlay(play); } catch (e) {} }
    var micId = c.getAttribute('data-mic');
    document.querySelectorAll('.opsbar .mic').forEach(function(m){
      m.classList.toggle('zx-hide', micId === 'off');
    });
  }
  box.addEventListener('scroll', function(){
    var w = cards[0] ? cards[0].getBoundingClientRect().width + 16 : 1;
    activate(Math.round(box.scrollLeft / w));
  }, { passive: true });
  window.addEventListener('load', function(){ activate(0); });
  activate(0);
})();
</script>"""

#: 短句跟读：录音 → AI 分析中 → 显示**当前这一句**的 AI 分析（左右滑动切换）
SPEAK_SWIPE_JS = """<script>
(function(){
  var mic = document.getElementById('zx-mic');
  var replay = document.getElementById('zx-replay');
  var audioEl = document.getElementById('zx-myrec');
  var stateEl = document.getElementById('zx-recstate');
  var analyzing = document.getElementById('zx-analyzing');
  if (!mic) return;
  var iconIdle = mic.getAttribute('data-ico-mic');
  var waveHTML = mic.querySelector('.wave') ? mic.querySelector('.wave').outerHTML : '';
  var bars = [];
  function grabBars(){ bars = mic.querySelectorAll('.wave i'); }
  grabBars();
  var rec = null, chunks = [], stream = null, blobUrl = null;
  var recording = false, discarding = false, aiTimer = null;
  var audioCtx = null, srcNode = null, analyser = null, buf = null, meter = null, silentMs = 0;
  var SILENCE_LIMIT_MS = 1100;   /* 连续静音 ≥1.1s（800~1200ms 区间）→ 自动结束 */
  var SILENCE_LEVEL = 8;         /* 相对 128 的峰值偏差阈值 */
  var STEP_MS = 70;
  function say(t){ if (stateEl) stateEl.textContent = t; }
  function stopTracks(){ if (stream) { stream.getTracks().forEach(function(t){ t.stop(); }); stream = null; } }
  function barsAt(h){ for (var i = 0; i < bars.length; i++){ bars[i].style.height = h + 'px'; } }
  function stopMeter(){
    if (meter){ clearInterval(meter); meter = null; }
    try { if (srcNode) srcNode.disconnect(); } catch (e) {}
    try { if (analyser) analyser.disconnect(); } catch (e) {}
    srcNode = null; analyser = null; buf = null;
    if (audioCtx){ try { audioCtx.close(); } catch (e) {} }
    audioCtx = null;
    barsAt(5);
  }
  function clearClip(){
    if (blobUrl){ try { URL.revokeObjectURL(blobUrl); } catch (e) {} blobUrl = null; }
    if (audioEl){
      try { audioEl.pause(); } catch (e) {}
      audioEl.removeAttribute('src');
      audioEl.style.display = 'none';
      try { audioEl.load(); } catch (e) {}
    }
    if (replay) replay.disabled = true;
  }
  function toIdle(){
    recording = false;
    mic.classList.remove('rec');
    mic.innerHTML = iconIdle + waveHTML;
    grabBars();
  }
  function clearAi(){
    if (aiTimer){ clearTimeout(aiTimer); aiTimer = null; }
    if (analyzing) analyzing.style.display = 'none';
  }
  /* 切换句子 / 离开页面：彻底回到"未录音"状态（丢弃旧录音，不生成回放） */
  function resetRec(){
    clearAi();
    stopMeter();
    if (rec && recording){ discarding = true; try { rec.stop(); } catch (e) { discarding = false; } }
    recording = false;
    stopTracks();
    toIdle();
    clearClip();
    say('');
  }
  window.__zxResetRec = resetRec;
  function showResult(i){
    if (analyzing) analyzing.style.display = 'none';
    var box = document.getElementById('zx-ai-' + i);
    if (box) box.style.display = 'block';
    if (audioEl && audioEl.src) audioEl.style.display = 'block';
  }
  function analyze(){
    if (analyzing) analyzing.style.display = 'flex';
    document.querySelectorAll('.ai').forEach(function(b){ b.style.display = 'none'; });
    var i = (typeof window.__zxCur === 'number') ? window.__zxCur : 0;
    aiTimer = setTimeout(function(){ aiTimer = null; showResult(i); }, 800);
  }
  /* 录音结束：生成 Blob → 只启用「我的朗读」，绝不自动播放 */
  function finish(){
    toIdle();
    stopTracks();
    stopMeter();
    if (discarding){ discarding = false; chunks = []; return; }
    var blob = new Blob(chunks, { type: (rec && rec.mimeType) || 'audio/webm' });
    chunks = [];
    if (!blob.size) return;
    if (blobUrl){ try { URL.revokeObjectURL(blobUrl); } catch (e) {} }
    blobUrl = URL.createObjectURL(blob);
    audioEl.src = blobUrl;
    if (replay) replay.disabled = false;
    analyze();
  }
  /* 实时音量检测：持续静音达到阈值 → 自动结束录音 */
  function startMeter(){
    var Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx || !stream) return;
    try {
      audioCtx = new Ctx();
      srcNode = audioCtx.createMediaStreamSource(stream);
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 1024;
      srcNode.connect(analyser);
      buf = new Uint8Array(analyser.fftSize);
    } catch (e) { stopMeter(); return; }
    silentMs = 0;
    meter = setInterval(function(){
      if (!analyser || !buf || !recording || discarding) return;
      analyser.getByteTimeDomainData(buf);
      var peak = 0;
      for (var i = 0; i < buf.length; i += 4){
        var d = buf[i] - 128; if (d < 0) { d = -d; }
        if (d > peak) { peak = d; }
      }
      if (peak >= SILENCE_LEVEL){ silentMs = 0; barsAt(5 + Math.round(Math.min(1, peak / 60) * 9)); return; }
      barsAt(5);
      silentMs += STEP_MS;
      if (silentMs >= SILENCE_LIMIT_MS){ try { rec.stop(); } catch (e) {} }
    }, STEP_MS);
  }
  function start(){
    if (!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder)) {
      resetRec();
      say('这台电脑的浏览器现在不能用麦克风（需要安全地址和麦克风权限）。你仍然可以先听原声，再看演示分析。');
      analyze(); return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function(s){
      stream = s; chunks = []; discarding = false;
      rec = new MediaRecorder(stream);
      rec.ondataavailable = function(ev){ if (ev.data && ev.data.size) chunks.push(ev.data); };
      rec.onstop = finish;
      rec.start();
      recording = true;
      mic.classList.add('rec');
      mic.innerHTML = mic.getAttribute('data-ico-stop') + waveHTML;
      grabBars();
      startMeter();
    }).catch(function(err){
      resetRec();
      say('没能打开麦克风：' + err.message + '。你仍然可以先听原声，再看演示分析。');
      analyze();
    });
  }
  mic.addEventListener('click', function(){
    if (recording){ try { rec.stop(); } catch (e) {} return; }   /* 正常路径是静音自动结束 */
    resetRec();
    start();
  });
  if (replay) replay.addEventListener('click', function(){
    if (!audioEl.src) return;
    audioEl.currentTime = 0;
    var pr = audioEl.play(); if (pr && pr.catch) { pr.catch(function(){}); }
  });
  window.addEventListener('pagehide', function(){
    clearAi();
    stopMeter();
    if (rec && recording){ discarding = true; try { rec.stop(); } catch (e) {} }
    recording = false;
    stopTracks();
    clearClip();
  });
})();
</script>"""

#: 单词跟读的录音（只录音/回放，不做任何评价）
REC_JS = """<script>
(function(){
  var mic = document.getElementById('zx-mic');
  var replay = document.getElementById('zx-replay');
  var audioEl = document.getElementById('zx-myrec');
  var stateEl = document.getElementById('zx-recstate');
  if (!mic) return;
  var iconIdle = mic.getAttribute('data-ico-mic');
  var waveHTML = mic.querySelector('.wave') ? mic.querySelector('.wave').outerHTML : '';
  var bars = [];
  function grabBars(){ bars = mic.querySelectorAll('.wave i'); }
  grabBars();
  var rec = null, chunks = [], stream = null, blobUrl = null;
  var recording = false, discarding = false;
  var audioCtx = null, srcNode = null, analyser = null, buf = null, meter = null, silentMs = 0;
  var SILENCE_LIMIT_MS = 1100;   /* 连续静音 ≥1.1s（800~1200ms 区间）→ 自动结束 */
  var SILENCE_LEVEL = 8;         /* 相对 128 的峰值偏差阈值 */
  var STEP_MS = 70;
  function say(t){ if (stateEl) stateEl.textContent = t; }
  function stopTracks(){ if (stream) { stream.getTracks().forEach(function(t){ t.stop(); }); stream = null; } }
  function barsAt(h){ for (var i = 0; i < bars.length; i++){ bars[i].style.height = h + 'px'; } }
  function stopMeter(){
    if (meter){ clearInterval(meter); meter = null; }
    try { if (srcNode) srcNode.disconnect(); } catch (e) {}
    try { if (analyser) analyser.disconnect(); } catch (e) {}
    srcNode = null; analyser = null; buf = null;
    if (audioCtx){ try { audioCtx.close(); } catch (e) {} }
    audioCtx = null;
    barsAt(5);
  }
  function clearClip(){
    if (blobUrl){ try { URL.revokeObjectURL(blobUrl); } catch (e) {} blobUrl = null; }
    if (audioEl){
      try { audioEl.pause(); } catch (e) {}
      audioEl.removeAttribute('src');
      audioEl.style.display = 'none';
      try { audioEl.load(); } catch (e) {}
    }
    if (replay) replay.disabled = true;
  }
  function toIdle(){
    recording = false;
    mic.classList.remove('rec');
    mic.innerHTML = iconIdle + waveHTML;
    grabBars();
  }
  /* 切换单词 / 离开页面：彻底回到"未录音"状态（丢弃旧录音，不生成回放） */
  function resetRec(){
    stopMeter();
    if (rec && recording){ discarding = true; try { rec.stop(); } catch (e) { discarding = false; } }
    recording = false;
    stopTracks();
    toIdle();
    clearClip();
    say('');
  }
  window.__zxResetRec = resetRec;
  /* 录音结束：生成 Blob → 只启用「我的朗读」，绝不自动播放 */
  function finish(){
    toIdle();
    stopTracks();
    stopMeter();
    if (discarding){ discarding = false; chunks = []; return; }
    var blob = new Blob(chunks, { type: (rec && rec.mimeType) || 'audio/webm' });
    chunks = [];
    if (!blob.size) return;
    if (blobUrl){ try { URL.revokeObjectURL(blobUrl); } catch (e) {} }
    blobUrl = URL.createObjectURL(blob);
    audioEl.src = blobUrl;
    audioEl.style.display = 'block';
    if (replay) replay.disabled = false;
  }
  /* 实时音量检测：持续静音达到阈值 → 自动结束录音 */
  function startMeter(){
    var Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx || !stream) return;
    try {
      audioCtx = new Ctx();
      srcNode = audioCtx.createMediaStreamSource(stream);
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 1024;
      srcNode.connect(analyser);
      buf = new Uint8Array(analyser.fftSize);
    } catch (e) { stopMeter(); return; }
    silentMs = 0;
    meter = setInterval(function(){
      if (!analyser || !buf || !recording || discarding) return;
      analyser.getByteTimeDomainData(buf);
      var peak = 0;
      for (var i = 0; i < buf.length; i += 4){
        var d = buf[i] - 128; if (d < 0) { d = -d; }
        if (d > peak) { peak = d; }
      }
      if (peak >= SILENCE_LEVEL){ silentMs = 0; barsAt(5 + Math.round(Math.min(1, peak / 60) * 9)); return; }
      barsAt(5);
      silentMs += STEP_MS;
      if (silentMs >= SILENCE_LIMIT_MS){ try { rec.stop(); } catch (e) {} }
    }, STEP_MS);
  }
  function start(){
    if (!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder)) {
      resetRec();
      say('这台电脑的浏览器现在不能用麦克风（需要安全地址和麦克风权限）。'); return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function(s){
      stream = s; chunks = []; discarding = false;
      rec = new MediaRecorder(stream);
      rec.ondataavailable = function(ev){ if (ev.data && ev.data.size) chunks.push(ev.data); };
      rec.onstop = finish;
      rec.start();
      recording = true;
      mic.classList.add('rec');
      mic.innerHTML = mic.getAttribute('data-ico-stop') + waveHTML;
      grabBars();
      startMeter();
    }).catch(function(err){
      resetRec();
      say('没能打开麦克风：' + err.message);
    });
  }
  mic.addEventListener('click', function(){
    if (recording){ try { rec.stop(); } catch (e) {} return; }   /* 正常路径是静音自动结束 */
    resetRec();
    start();
  });
  if (replay) replay.addEventListener('click', function(){
    if (!audioEl.src) return;
    audioEl.currentTime = 0;
    var pr = audioEl.play(); if (pr && pr.catch) { pr.catch(function(){}); }
  });
  window.addEventListener('pagehide', function(){
    stopMeter();
    if (rec && recording){ discarding = true; try { rec.stop(); } catch (e) {} }
    recording = false;
    stopTracks();
    clearClip();
  });
})();
</script>"""


def shell(title: str, body: str, back_href: str = "", back_label: str = "返回",
          sub: str = "", home: bool = True, js: str = "") -> str:
    right = ('<a href="/" aria-label="回到首页">%s</a>' % ui.icon("home")) if home else ""
    top = ui.topbar(title, back_href, back_label, right_html=right, sub=sub).replace(
        'class="tb-back"', 'class="tb-back" id="zx-back"')
    return (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<meta name="theme-color" content="#F6F7F9">\n'
        '<title>%s</title>\n<style>%s%s</style>\n</head>\n<body>\n%s\n<main>\n%s\n</main>\n%s%s\n</body>\n</html>\n'
        % (html.escape(title if title == PRODUCT_NAME else title + " · " + PRODUCT_NAME),
           ui.STYLE, DEMO_CSS, top, body, PLAYER_JS, js))


def _esc(text) -> str:
    return html.escape("" if text is None else str(text))


def _steps(done: int, total: int, word: str = "") -> str:
    """统一进度：细进度条 + 计数。word 非空时计数写成「当前第 X / Y 个|句」。"""
    pct = int(100 * done / max(total, 1))
    cnt = ("当前第 %d / %d %s" % (done, total, word)) if word else ("%d / %d" % (done, total))
    return ('<div class="steps"><span class="bar"><i style="width:%d%%"></i></span>'
            '<span class="cnt">%s</span></div>' % (pct, cnt))


def _option_marks() -> str:
    return ('<span class="mk mk-ok">%s</span><span class="mk mk-no">%s</span>'
            % (ui.icon("check"), ui.icon("close")))


def _entry_rows(entries) -> str:
    """首页 / 课时页的学习入口：一排一个入口（沿用既有 .entryrow 视觉与状态文字）。"""
    out = []
    for e in entries or []:
        out.append('<a class="entryrow %s%s" href="%s"><span class="ico">%s</span>'
                   '<span class="nm">%s</span><span class="st">%s</span></a>'
                   % (_esc(e["cls"]), " fin" if e.get("done") else "", _esc(e["href"]),
                      ui.icon(e["icon"]), _esc(e["label"]), _esc(e["status"])))
    return "".join(out)


#: 「跟读练习」入口内部的两种跟读方式（沿用既有 .modes 组件，不新造 UI）
_READ_MODES = (("vocab", "单词跟读", "/unit/%s/vocab"),
               ("sentences", "短句跟读", "/unit/%s/sentences"))
#: 「听音辨意」入口内部的三种练习方式（「听音写词」已删除）
_LISTEN_MODES = (("word", "单词听辨", "/unit/%s/listen?mode=word"),
                 ("sentence", "句子听辨", "/unit/%s/listen?mode=sentence"),
                 ("reading", "听音阅读", "/unit/%s/reading"))

#: 模式切换条复用的首页色块（与首页六个入口同一套低饱和色，三色交替）
_MODE_TINTS = ("e-word", "e-quiz", "e-phrase")


def _modes(slug: str, active: str, which: str) -> str:
    """入口内部的练习方式切换：沿用首页「色块入口」视觉（.e-word/.e-quiz/.e-phrase 的 tint/hue）。"""
    items = _READ_MODES if which == "read" else _LISTEN_MODES
    out = []
    for i, (key, label, path) in enumerate(items):
        tint = _MODE_TINTS[i % len(_MODE_TINTS)]
        on = " on" if key == active else ""
        cls = "primary" if key == active else "secondary"
        out.append('<a class="mode %s%s" href="%s"><button class="%s" type="button">%s</button></a>'
                   % (tint, on, _esc(path % slug), cls, _esc(label)))
    return '<div class="modes">%s</div>' % "".join(out)


def _ai_block(title: str, subs, note: str = DEMO_NOTE) -> str:
    rows = "".join('<p class="ai-sub">%s</p><p>%s</p>' % (_esc(k), _esc(v)) for k, v in subs)
    return ('<section class="ai"><h2>%s</h2>%s'
            '<p class="demo-note"><span class="demo">%s</span> %s</p></section>'
            % (_esc(title), rows, DEMO_LABEL, _esc(note)))


def _practice_rows(t: dict) -> str:
    """专项 / 巩固练习入口：只在有对应学习证据时出现（没有就不显示，也不显示"暂无"）。"""
    icons = {"special": "pen", "reinforce": "replay"}
    rows = []
    for key in ("special", "reinforce"):
        entry = t.get(key)
        if not entry:
            continue
        rows.append('<a class="plainrow" href="%s"><span><span class="n">%s%s</span>'
                    '<span class="c" style="display:block">%s</span></span>'
                    '<span class="c">开始 ›</span></a>'
                    % (_esc(entry["href"]), ui.icon(icons[key]), _esc(entry["label"]),
                       _esc(entry.get("desc") or "")))
    return "".join(rows)


def ai_tutor_block(t: dict, title: str = "AI 随堂助教", with_practice: bool = True) -> str:
    """AI 随堂助教内容块：紧凑结构 + 图标标题 + 真实证据的发现/重点/建议。

    只有存在真实学习证据时才给"发现/重点/建议"；没有证据就如实说明，不编结论。
    专项/巩固练习入口只在有对应证据时出现（没有就不显示，也不显示"暂无"）。
    title 传空字符串时不渲染块标题——页面顶部标题已经写过同样的字（避免重复标题）。
    """
    findings = t.get("findings") or []
    focus = t.get("focus") or []
    head = '<h2>%s<span>%s</span></h2>' % (ui.icon("spark"), _esc(title)) if title else ""
    parts = ['<section class="ai">%s' % head]
    if not findings:
        parts.append('<p class="ai-empty">这节课还没有学习记录。做过本课检测或听音辨意之后，'
                     '这里会给出具体发现。</p>')
    else:
        parts.append('<p class="ai-h">本课发现</p><ul class="ai-list">%s</ul>'
                     % "".join('<li>%s <span class="ai-src">（%s · %s）</span></li>'
                               % (_esc(f["detail"]), _esc(f["source"]), _esc(f["strength"]))
                               for f in findings))
        if focus:
            parts.append('<p class="ai-h">本课重点</p><ul class="ai-list">%s</ul>'
                         % "".join("<li>%s</li>" % _esc(x) for x in focus))
        if t.get("advice"):
            parts.append('<p class="ai-h">AI 建议</p><p class="ai-adv">%s</p>' % _esc(t["advice"]))
    if with_practice:
        rows = _practice_rows(t)
        if rows:
            parts.append('<div class="ai-pt">%s</div>' % rows)
    note = ('只根据这节课真实产生的学习记录做分析；建议由你决定要不要做。'
            if findings else '')
    if note:
        parts.append('<p class="demo-note"><span class="demo">%s</span> %s</p>'
                     % (DEMO_LABEL, _esc(note)))
    parts.append("</section>")
    return "".join(parts)


def _formal_rows(formal) -> str:
    """正式巩固池入口：与现有练习入口完全同一视觉结构（`.ai-pt` + `.plainrow`）。"""
    rows = []
    for e in formal or ():
        rows.append('<a class="plainrow" href="%s"><span><span class="n">%s%s</span>'
                    '<span class="c" style="display:block">%s</span></span>'
                    '<span class="c">开始 ›</span></a>'
                    % (_esc(e["href"]), ui.icon("replay"), _esc(e["label"]),
                       _esc(e.get("desc") or "")))
    return "".join(rows)


def _practice_summary(t: dict) -> str:
    """把「本课发现 / 本课重点 / AI 建议」压成一段简短总结（只用真实学习证据）。"""
    points = [x for x in (t.get("focus") or []) if x]
    line = "这节课有 %d 处需要再看" % len(t.get("findings") or [])
    if points:
        line += "：%s" % "、".join(points[:2])
    return line + "。" + (t.get("advice") or "")


def practice_block(t: dict, formal=()) -> str:
    """自主练习：简短学习总结 + 正式巩固入口 + 专项 / 巩固练习入口（练什么由孩子自己决定）。

    formal = 正式巩固池转换出的入口（优先展示，视觉与 Cookie 入口一致）；
    没有正式内容时，页面表现与原来完全一致。
    """
    findings = t.get("findings") or []
    formal = list(formal or ())
    parts = ['<section class="ai">']
    if findings:
        parts.append('<p class="ai-h">%s学习总结</p><p class="ai-adv">%s</p>'
                     % (ui.icon("spark"), _esc(_practice_summary(t))))
    elif not formal:
        parts.append('<p class="ai-empty">这节课还没有学习记录。做过本课检测或听音辨意之后，'
                     '这里会给出简短总结。</p>')
    rows = _formal_rows(formal) + _practice_rows(t)
    if rows:
        parts.append('<div class="ai-pt">%s</div>' % rows)
    if findings:
        parts.append('<p class="demo-note"><span class="demo">%s</span> %s</p>'
                     % (DEMO_LABEL, '只根据这节课真实产生的学习记录给总结；练什么、练几道由你自己决定。'))
    parts.append("</section>")
    return "".join(parts)


def _bars(rows) -> str:
    """三条语义色细进度条：[(标签, 值文案, 百分比, 颜色)]。不使用伪精确分数。"""
    out = []
    for label, value, pct, color in rows:
        out.append('<div class="row"><span class="lb">%s</span>'
                   '<span class="tr"><i style="width:%d%%;background:%s"></i></span>'
                   '<span class="vl">%s</span></div>'
                   % (_esc(label), int(pct), color, _esc(value)))
    return '<div class="ai-bars">%s</div>' % "".join(out)


# --------------------------------------------------------------------------- 首页 / Unit
def _lesson_picker(options, select_id: str = "zx-lesson", label: str = "") -> str:
    """当前课时选择器：Demo 自定义（手机系统 picker 的单选圆圈无法用 CSS 去掉）。

    同一个 <form> 内保留一份原生 select（display:none）承担提交与语义，
    POST /lesson + lesson + back 的契约、业务逻辑与原来完全一致。
    """
    opts, rows, current = [], [], ""
    for g in options or []:
        opts.append('<optgroup label="%s · %s">%s</optgroup>'
                    % (_esc(g["unit"]["unit_code"]), _esc(g["unit"]["title"]),
                       "".join('<option value="%s"%s>%s</option>'
                               % (_esc(l["value"]), " selected" if l.get("selected") else "",
                                  _esc(l["label"]))
                               for l in g["lessons"])))
        rows.append('<p class="lpgroup">%s · %s</p>'
                    % (_esc(g["unit"]["unit_code"]), _esc(g["unit"]["title"])))
        for l in g["lessons"]:
            on = bool(l.get("selected"))
            if on:
                current = l["label"]
            rows.append('<button class="lpopt" type="button" data-value="%s" '
                        'aria-selected="%s">%s</button>'
                        % (_esc(l["value"]), "true" if on else "false", _esc(l["label"])))
    head = ('<p class="pklabel" id="%s-lab">%s</p>' % (_esc(select_id), _esc(label))
            if label else "")
    return (
        '%s'
        '<div class="lpick">'
        '<button class="lpbtn" type="button" id="%s" aria-haspopup="listbox" '
        'aria-expanded="false" aria-label="选择当前课时">%s</button>'
        '<div class="lplist" role="listbox" aria-label="当前课时选项" hidden>%s</div>'
        '<select class="lpnative" name="lesson" tabindex="-1" aria-hidden="true">%s</select>'
        '</div>'
        % (head, _esc(select_id), _esc(current or "选择当前课时"),
           "".join(rows), "".join(opts)))


def home_page(ctx: dict) -> str:
    """首页：只有一个"当前课时"选择器（教材板块名）+ 当前课时真实拥有的学习功能。"""
    body = (
        '<section class="softcard unitcard">'
        '<p class="um-book">七年级英语上册</p>'
        '<form class="picker" method="post" action="/lesson">'
        '<input type="hidden" name="back" value="/">'
        '%s'
        '</form>'
        '</section>'
        '%s'
        '<div class="foot">%s</div>'
        % (_lesson_picker(ctx["lesson_options"], "zx-unit"),
           _entry_rows(ctx["entries"]), _esc(PRODUCT_NAME)))
    return shell(PRODUCT_NAME, body, home=False, js=LPICK_JS)


def unit_page(ctx: dict) -> str:
    unit = ctx["unit"]
    pages = ("教材第 %s–%s 页" % (unit.get("textbook_page_start"), unit.get("textbook_page_end"))) \
        if unit.get("textbook_page_start") else "教材内容"
    picker = ('<form class="picker" method="post" action="/lesson" style="margin-top:10px">'
              '<input type="hidden" name="back" value="%s">'
              '%s'
              '</form>' % (_esc("/unit/%s" % unit["slug"]),
                           _lesson_picker(ctx.get("lesson_options"), "zx-lesson", "当前课时")))
    body = (
        '<section class="card">'
        '<p class="meta">%s · %s</p>'
        '%s'
        '%s'
        '</section>'
        '<section class="softcard"><h2>这节课可以练什么</h2>%s</section>'
        '%s'
        '<div class="center-row">'
        '<a href="/unit/%s/continue"><button class="primary" type="button">继续学习</button></a>'
        '</div>'
        '<div class="foot">%s</div>'
        % (_esc(pages), _esc(ctx["theme"]), picker,
           _steps(sum(1 for k in ctx["steps"] if ctx["done"].get(k)), len(ctx["steps"])),
           _entry_rows(ctx["entries"]) or '<p class="meta">这节课在 Demo 里还没有可练的内容。</p>',
           ctx["ai"]["html"], _esc(unit["slug"]),
           _esc(PRODUCT_NAME)))
    return shell(unit["unit_code"], body, "/", "回到首页", sub=_esc(unit["title"]),
                 js=LPICK_JS)


# --------------------------------------------------------------------------- 单词跟读
def vocab_page(ctx: dict) -> str:
    """单词跟读：看到单词 → 听教材发音 → 跟读 → 重听/重读 → 左右滑动下一个。

    纯练习页面：没有记忆判断、没有正误评价、没有掌握度、没有 AI 判断。
    连续内容用**左右滑动**切换，页面底部不放上一项/下一项按钮。
    """
    unit, lesson = ctx["unit"], ctx["lesson"]
    slug = unit["slug"]
    words = ctx["words"]
    index = ctx["index"]
    cards = []
    for i, w in enumerate(words):
        cards.append(
            '<section class="card-w" data-i="%d" data-audio="%s">'
            '<div class="w">%s</div>'
            '<div class="phon">%s</div>'
            '<div class="mean">%s</div>'
            '</section>'
            % (i, _esc(w.get("audio_url") or ""), _esc(w["text"]),
               _esc(w.get("phonetic") or ""), _esc(w.get("meaning") or "")))
    first = words[index] if words else {}
    body = (
        '%s'
        '<div class="lesson"><div class="swipe" id="zx-swipe" data-unit="个">%s</div></div>'
        '<p class="swipe-hint">左右滑动切换单词</p>'
        '<p id="zx-recstate" style="text-align:center;color:var(--text2);margin:10px 0 0"></p>'
        '<audio id="zx-myrec" controls preload="none" style="width:100%%;display:none"></audio>'
        '<div class="opsbar">'
        '<button class="op" type="button" id="zx-play" data-autoplay="1" data-audio="%s" aria-label="听发音">%s'
        '<span class="wave"><i></i><i></i><i></i></span></button>'
        '<button class="mic" type="button" id="zx-mic" data-ico-mic="%s" data-ico-stop="%s">%s'
        '<span class="wave"><i></i><i></i><i></i></span></button>'
        '<button class="op" type="button" id="zx-replay" disabled aria-label="我的朗读">%s</button>'
        '</div>'
        % (_modes(slug, "vocab", "read") + _steps(index + 1, max(len(words), 1), "个"),
           "".join(cards),
           _esc(first.get("audio_url") or ""), ui.icon("speaker"),
           html.escape(ui.icon("mic"), quote=True), html.escape(ui.icon("stop"), quote=True),
           ui.icon("mic"), ui.icon("play")))          # 我的朗读：用三角形播放图标
    return shell("单词跟读", body, "/unit/%s" % slug, "返回这一课",
                 sub=_esc(lesson["title"]), js=SWIPE_JS + REC_JS)


def vocab_result_page(ctx: dict) -> str:
    unit = ctx["unit"]
    slug = unit["slug"]
    counts = ctx["counts"]
    rows = []
    for w in ctx["need_again"]:
        rows.append('<a class="plainrow" href="/unit/%s/vocab?i=%d&reveal=1">'
                    '<span><span class="n">%s</span>'
                    '<span class="c" style="display:block">%s</span></span>'
                    '<span class="c">再看一遍 ›</span></a>'
                    % (_esc(slug), w["index"], _esc(w["text"]), _esc(w.get("meaning") or "")))
    stat = "".join(
        '<div style="display:flex;justify-content:space-between;padding:10px 0;'
        'border-top:1px solid var(--line)"><span style="font-size:16px;font-weight:600">%s</span>'
        '<span style="color:var(--text2)">%d 个</span></div>' % (label, value)
        for label, value in (("记得", counts["know"]), ("有点模糊", counts["fuzzy"]),
                             ("忘了", counts["forgot"])))
    body = (
        '<section class="card"><h2>单词 · 本次结果</h2>'
        '<p class="textbook-name">%d / %d 个重点词</p>'
        '<p class="meta">这是你自己刚才的判断，不是考试成绩。</p>%s</section>'
        '<section class="softcard"><h2>需要再看</h2>%s</section>'
        '<div class="row">'
        '<a href="/unit/%s/listen"><button class="primary" type="button">去听音辨意</button></a>'
        '<a href="/unit/%s/vocab?i=0"><button class="secondary" type="button">再看一遍</button></a>'
        '</div>'
        '<div class="foot">%s</div>'
        % (ctx["judged"], ctx["total_core"], stat,
           "".join(rows) or '<p class="meta">这次没有需要再看的词。</p>',
           _esc(slug), _esc(slug), _esc(PRODUCT_NAME)))
    return shell("单词结果", body, "/unit/%s" % slug, "返回这一课")


# --------------------------------------------------------------------------- 听音辨意
def listen_page(ctx: dict) -> str:
    unit, mode = ctx["unit"], ctx["mode"]
    slug = unit["slug"]
    q = ctx["question"]
    is_word = mode == "word"
    opts = []
    if ctx["feedback"]:
        for letter, text in q["options"]:
            cls = "opt2"
            if letter == q["answer"]:
                cls += " ok"
            elif letter == ctx["picked"]:
                cls += " bad"
            opts.append('<button class="%s" type="button"><span class="k">%s</span>'
                        '<span>%s</span>%s</button>'
                        % (cls, _esc(letter.upper()), _esc(text), _option_marks()))
        ok = ctx["picked"] == q["answer"]
        fb = ('<div class="fb show %s"><b>%s</b><span class="tip">%s</span></div>'
              % ("ok" if ok else "warn",
                 "答对了。" if ok else "这次选的是 %s，正确答案是 %s。"
                 % (ctx["picked"].upper(), q["answer"].upper()),
                 _esc(q.get("why") or "")))
        foot = ('<div class="qfoot"><a href="%s"><button class="primary" type="button">%s</button></a></div>'
                % (_esc(ctx["next_href"]), "查看本次结果" if ctx["is_last"] else "下一题"))
    else:
        for letter, text in q["options"]:
            opts.append('<button class="opt2" type="submit" name="pick" value="%s">'
                        '<span class="k">%s</span><span>%s</span>%s</button>'
                        % (_esc(letter), _esc(letter.upper()), _esc(text), _option_marks()))
        fb = ('<div class="fb show warn"><b>%s</b></div>' % _esc(ctx["error"])) \
            if ctx.get("error") else ""
        foot = ""
    modes = _modes(slug, "word" if is_word else "sentence", "listen")
    # 进入题目时自动播放这道题的声音；已作答/看反馈时不重复自动播放
    autoplay = "" if ctx["feedback"] else 'data-autoplay="1" '
    stage = ('<div class="soundstage"><button class="spkbig" type="button" data-audio="%s" '
             '%s%saria-label="播放这道题的声音">%s<span class="wave"><i></i><i></i><i></i></span>'
             '</button></div>'
             % (_esc(q["audio_url"]), autoplay,
                ('data-start="%d" data-end="%d" ' % (q["start_ms"], q["end_ms"]))
                if q.get("end_ms") else "", ui.icon("speaker")))
    body = (
        modes + _steps(ctx["index"] + (1 if ctx["feedback"] else 0), ctx["total"]) +
        '<div class="lesson"><section class="card-w listen"><div class="quiz" style="width:100%%">%s'
        '<p class="qtitle"></p>'
        '<form method="post" action="/unit/%s/listen/answer" style="width:100%%">'
        '<input type="hidden" name="mode" value="%s">'
        '<input type="hidden" name="i" value="%d">'
        '<div class="opts">%s</div></form>%s</div></section></div>%s'
        % (stage, _esc(slug), _esc(mode), ctx["index"], "".join(opts), fb, foot))
    return shell("听音辨意", body, "/unit/%s" % slug, "返回这一课",
                 sub="单词听辨" if is_word else "句子听辨")


def listen_result_page(ctx: dict) -> str:
    unit = ctx["unit"]
    slug = unit["slug"]
    rows = []
    for mode, label in (("word", "单词听辨"), ("sentence", "句子听辨")):
        stat = ctx["listen"][mode]
        if stat["total"]:
            rows.append('<a class="plainrow" href="/unit/%s/listen?mode=%s&i=0">'
                        '<span><span class="n">%s</span>'
                        '<span class="c" style="display:block">答对 %d / %d 题</span></span>'
                        '<span class="c">%s</span></a>'
                        % (_esc(slug), mode, label, stat["correct"], stat["total"], stat["band"]))
        else:
            rows.append('<a class="plainrow" href="/unit/%s/listen?mode=%s&i=0">'
                        '<span><span class="n">%s</span>'
                        '<span class="c" style="display:block">还没有开始</span></span>'
                        '<span class="c">去练</span></a>' % (_esc(slug), mode, label))
    body = (
        '<section class="card">%s</section>'
        '<div class="row">'
        '<a href="/unit/%s/check"><button class="primary" type="button">去做本课检测</button></a>'
        '<a href="/unit/%s"><button class="secondary" type="button">回到这一课</button></a>'
        '</div>'
        '<div class="foot">%s</div>'
        % ("".join(rows), _esc(slug), _esc(slug), _esc(PRODUCT_NAME)))
    return shell("听音辨意结果", body, "/unit/%s/listen" % slug, "返回听音辨意")


# --------------------------------------------------------------------------- 本课检测
def check_page(ctx: dict) -> str:
    unit, q = ctx["unit"], ctx["question"]
    slug = unit["slug"]
    is_open = bool(ctx.get("open_answer"))          # 阅读简答：给输入框，不判对错
    material = q.get("material") or ""
    opts = []
    if is_open:
        opts = []
    elif ctx["feedback"]:
        for letter, text in q["options"]:
            cls = "opt2"
            if letter == q["answer"]:
                cls += " ok"
            elif letter == ctx["picked"]:
                cls += " bad"
            opts.append('<button class="%s" type="button"><span class="k">%s</span>'
                        '<span>%s</span>%s</button>'
                        % (cls, _esc(letter.upper()), _esc(text), _option_marks()))
    else:
        for letter, text in q["options"]:
            opts.append('<button class="opt2" type="submit" name="opt" value="%s">'
                        '<span class="k">%s</span><span>%s</span>%s</button>'
                        % (_esc(letter), _esc(letter.upper()), _esc(text), _option_marks()))
    fb = ""
    ai_block = ""
    foot = ""
    if ctx["feedback"] and is_open:
        fb = ('<div class="qfb"><p class="fbrow">我的回答：<b>%s</b></p>'
              '<p class="fbrow">%s</p><div class="rref">%s</div></div>'
              % (_esc(ctx["picked"]), _esc(q.get("answer_label") or "参考答案"),
                 _esc(q.get("reference") or "")))
    elif ctx["feedback"] and ctx["correct"]:
        fb = '<div class="qfb ok"><b>答对了。</b></div>'
        if q.get("answer_label"):                   # 阅读选择题：显示「答案」
            fb += '<p class="fbrow">%s：%s</p>' % (
                _esc(q["answer_label"]), _esc(dict(q["options"]).get(q["answer"], "")))
    elif ctx["feedback"]:
        ex = ctx["explain"]
        fb = '<div class="qfb again"><b>这次没选对。</b></div>'
        if q.get("answer_label"):                   # 有可靠答案的题（含阅读选择）：明确给出答案
            fb += '<p class="fbrow">%s：%s</p>' % (
                _esc(q["answer_label"]), _esc(dict(q["options"]).get(q["answer"], "")))
        subs = [("为什么错", ex["why"])]
        if ex.get("basis_text"):
            subs.append(("教材依据（%s）" % ex["basis_label"], ex["basis_text"]))
        if ex.get("example"):
            subs.append(("教材例句", ex["example"]))
        subs.append(("建议", ex["advice"]))
        ai_block = _ai_block("AI 解释", tuple(subs),
                             note="这里的解释是演示效果，只讲这道题的思路，不替孩子答题。")
    # 底部操作区固定：简答题的「提交」常驻；有反馈时再出现既有动作（再试一次 / 下一题）
    foot_buttons = []
    if is_open:
        foot_buttons.append('<button class="%s" type="submit" form="zx-check-answer" '
                            'style="min-width:140px">提交</button>'
                            % ("secondary" if ctx["feedback"] else "primary"))
    if ctx["feedback"]:
        extra = ('<a href="/unit/%s/check/wrong"><button class="secondary" type="button">看看错题</button></a>'
                 % _esc(slug)) if (not is_open and not ctx["correct"]) else ""
        retry = ('<form method="post" action="/unit/%s/check/retry" style="flex:1">'
                 '<input type="hidden" name="qid" value="%s">'
                 '<button class="secondary" type="submit" style="width:100%%">再试一次</button></form>'
                 % (_esc(slug), _esc(q["id"]))) if (not is_open and not ctx["correct"]) else ""
        foot_buttons.append('%s%s<a href="%s"><button class="primary" type="button" '
                            'style="min-width:140px">%s</button></a>'
                            % (retry, extra, _esc(ctx["next_href"]),
                               "看学习结果" if ctx["is_last"] else "下一题"))
    if foot_buttons:
        foot = '<div class="qfoot"><div class="row" style="margin:0">%s</div></div>' % "".join(foot_buttons)
    if is_open:
        answer_form = ('<form method="post" action="/unit/%s/check/answer" id="zx-check-answer">'
                       '<input type="hidden" name="i" value="%d">'
                       '<p class="hint">用英文写一句回答。</p>'
                       '<textarea class="saybox" name="text" rows="2">%s</textarea></form>'
                       % (_esc(slug), ctx["index"], _esc(ctx["picked"])))
    else:
        answer_form = ('<form method="post" action="/unit/%s/check/answer">'
                       '<input type="hidden" name="i" value="%d">'
                       '<div class="qopts">%s</div></form>'
                       % (_esc(slug), ctx["index"], "".join(opts)))
    material_block = ('<section class="softcard"><p class="qnum">阅读材料</p>'
                      '<p class="rdtext">%s</p></section>' % _esc(material)) if material else ""
    body = (
        _steps(ctx["index"] + (1 if ctx["feedback"] else 0), ctx["total"]) +
        material_block +
        '<section class="qwrap"><div class="qbody">'
        '<p class="qnum">%s</p>'
        '<p class="qstem">%s</p>'
        '%s%s%s</div>%s</section>'
        % (_esc(q["type"]), _esc(q["prompt"]), answer_form, fb, ai_block, foot))
    html_out = shell("本课检测", body + ui.sheet_html(), "/unit/%s" % slug, "返回这一课",
                     sub="教材内容检测", js=CHECK_JS)
    return html_out.replace("<body>", '<body data-partial="%d">' % (1 if ctx["partial"] else 0))


def check_wrong_page(ctx: dict) -> str:
    unit = ctx["unit"]
    slug = unit["slug"]
    items = []
    for row in ctx["wrong_items"]:
        q, ex = row["q"], row["explain"]
        items.append(
            '<section class="card">'
            '<p class="qnum">第 %d 题 · %s</p>'
            '<p class="qstem">%s</p>'
            '<div style="display:flex;justify-content:space-between;padding:8px 0;'
            'border-top:1px solid var(--line)"><span style="color:var(--text2)">我的答案</span>'
            '<span style="color:%s">%s</span></div>'
            '<div style="display:flex;justify-content:space-between;padding:8px 0;'
            'border-top:1px solid var(--line)"><span style="color:var(--text2)">正确答案</span>'
            '<span style="color:%s;font-weight:600">%s</span></div>'
            '%s'
            '<form method="post" action="/unit/%s/check/retry" style="margin-top:12px">'
            '<input type="hidden" name="qid" value="%s">'
            '<button class="secondary" type="submit" style="width:100%%">再做一次</button></form>'
            '</section>'
            % (row["index"] + 1, _esc(q["type"]), _esc(q["prompt"]), C_ERR,
               _esc(row["picked_text"] or row["picked"].upper()), C_DONE,
               _esc(row["answer_text"]),
               _ai_block("AI 解释", (
                   ("为什么错", ex["why"]),
                   ("教材依据（%s）" % ex["basis_label"], ex["basis_text"]),
                   ("教材例句", ex["example"]),
                   ("建议", ex["advice"]))),
               _esc(slug), _esc(q["id"])))
    body = (
        '<section class="card">'
        '<p class="textbook-name">%d 个地方值得再看看</p>'
        '<p class="meta">每道题都可以自己决定要不要再做一次。</p></section>'
        '%s'
        '<div class="row">'
        '<a href="/unit/%s/check"><button class="primary" type="button">回到本课检测</button></a>'
        '<a href="/unit/%s/result"><button class="secondary" type="button">看学习结果</button></a>'
        '</div>'
        '<div class="foot">%s</div>'
        % (len(ctx["wrong_items"]),
           "".join(items) or '<section class="card"><p class="meta">这一课暂时没有错题。</p></section>',
           _esc(slug), _esc(slug), _esc(PRODUCT_NAME)))
    return shell("本课错题", body, "/unit/%s/check" % slug, "返回本课检测")


# --------------------------------------------------------------------------- 短句跟读
def sentences_page(ctx: dict) -> str:
    """短句跟读：教材短句 + 官方原音区间 → 录音 → 我的朗读 → AI 分析中 → AI 朗读分析。

    连续句子用**左右滑动**切换；AI 分析按每一句自己的内容呈现（不共用一套泛化文案）。
    """
    unit, lesson = ctx["unit"], ctx["lesson"]
    slug = unit["slug"]
    rows = ctx["sentences"]
    if not rows:
        body = ('<section class="card"><h2>短句跟读</h2>'
                '<p class="meta">这节课还没有可以跟读的教材短句。</p>'
                '<div class="row"><a href="/unit/%s"><button class="primary" type="button">'
                '换一个课时</button></a>'
                '<a href="/unit/%s"><button class="secondary" type="button">回到这一课</button></a>'
                '</div></section>' % (_esc(slug), _esc(slug)))
        return shell("短句跟读", body, "/unit/%s" % slug, "返回这一课")
    index = ctx["index"]
    cards = []
    for i, s in enumerate(rows):
        ai = ctx["sentence_ai"][i]
        bars = _bars((("完整度", ai["completeness"],
                       {"完整": 100, "基本完整": 70, "有遗漏": 40}.get(ai["completeness"], 80),
                       C_DONE),
                      ("发音表现", ai["pronunciation"],
                       {"较好": 90, "表现稳定": 85, "基本稳定": 75,
                        "有一个词需要注意": 55}.get(ai["pronunciation"], 80), C_WARN),
                      ("流畅度", ai["fluency"],
                       {"流畅": 95, "基本流畅": 75, "停顿稍多": 45}.get(ai["fluency"], 80),
                       C_AI)))
        cards.append(
            '<section class="card-w" data-i="%d" data-audio="%s" data-start="%d" data-end="%d">'
            '<div class="sent">%s</div>'
            '<section class="ai" id="zx-ai-%d" style="display:none">'
            '<h2>AI 朗读分析</h2>%s'
            '<p class="ai-sub">具体发现</p><p>%s</p>'
            '<p class="ai-sub">建议</p><p>%s</p>'
            '<p class="demo-note"><span class="demo">%s</span> %s</p></section>'
            '</section>'
            % (i, _esc(s["audio_url"]), _sent_start(s), s["end_ms"],
               _esc(s["text"]), i, bars, _esc(ai["finding"]),
               _esc(ai["advice"]), DEMO_LABEL, _esc(SPEAK_NOTE)))
    first = rows[index]
    body = (
        '%s'
        '<div class="lesson"><div class="swipe" id="zx-swipe" data-unit="句">%s</div></div>'
        '<div class="analyzing" id="zx-analyzing" style="display:none">AI 正在分析'
        '<i></i><i></i><i></i></div>'
        '<p class="swipe-hint">左右滑动切换句子</p>'
        '<p id="zx-recstate" style="text-align:center;color:var(--text2);margin:8px 0 0"></p>'
        '<audio id="zx-myrec" controls preload="none" style="width:100%%;display:none"></audio>'
        '<div class="opsbar">'
        '<button class="op" type="button" id="zx-play" data-autoplay="1" data-audio="%s" data-start="%d" '
        'data-end="%d" aria-label="听原声">%s<span class="wave"><i></i><i></i><i></i></span></button>'
        '<button class="mic" type="button" id="zx-mic" data-ico-mic="%s" data-ico-stop="%s">%s'
        '<span class="wave"><i></i><i></i><i></i></span></button>'
        '<button class="op" type="button" id="zx-replay" disabled aria-label="我的朗读">%s</button>'
        '</div>'
        % (_modes(slug, "sentences", "read") + _steps(index + 1, len(rows), "句"),
           "".join(cards),
           _esc(first["audio_url"]), _sent_start(first), first["end_ms"],
           ui.icon("speaker"),
           html.escape(ui.icon("mic"), quote=True), html.escape(ui.icon("stop"), quote=True),
           ui.icon("mic"), ui.icon("play")))          # 我的朗读：用三角形播放图标
    return shell("短句跟读", body, "/unit/%s" % slug, "返回这一课",
                 sub=_esc(lesson["title"]), js=SWIPE_JS + SPEAK_SWIPE_JS)


# --------------------------------------------------------------------------- 听音阅读
def reading_page(ctx: dict) -> str:
    unit = ctx["unit"]
    slug = unit["slug"]
    segs = ctx["segments"]
    if not segs:
        body = ('<section class="card"><h2>听音阅读</h2>'
                '<p class="meta">这一课还没有可以听读的教材内容。</p>'
                '<div class="row"><a href="/unit/%s"><button class="secondary" type="button">'
                '回到这一课</button></a></div></section>' % _esc(slug))
        return shell("听音阅读", body, "/unit/%s" % slug, "返回这一课")
    index, seg = ctx["seg_index"], ctx["segment"]
    options = "".join('<option value="%s"%s>%s · %s</option>'
                      % (_esc(u["slug"]), " selected" if u["slug"] == unit["slug"] else "",
                         _esc(u["unit_code"]), _esc(u["title"]))
                      for u in ctx["units"])
    pages_label = "–".join(str(p) for p in sorted(set(seg["tb_pages"])))
    rows = _reading_rows(seg)                     # 按修正表补全文本（不改原始数据）
    chunks = "".join('<p class="chunk" data-start="%d" data-end="%d">%s</p>'
                     % (c["start_ms"], c["end_ms"], c.get("html") or _esc(c["text"]))
                     for c in rows)
    next_href = "/unit/%s/reading?seg=%d" % (slug, index + 1)
    autonext = next_href if index < len(segs) - 1 else ""
    first_start = rows[0]["start_ms"] if rows else 0   # 与首块开始状态同一个值
    body = (
        _modes(slug, "reading", "listen") +
        '<section class="card">'
        '<p class="um-book">七年级英语上册</p>'
        '<p class="meta">第 %d / %d 段 · 教材第 %s 页 · %s</p>'
        '<form class="picker" method="post" action="/switch">'
        '<input type="hidden" name="back" value="%s">'
        '<select name="u" aria-label="切换 Unit" onchange="this.form.submit()">%s</select>'
        '</form></section>'
        '<div class="soundstage">'
        '<button class="spkbig" type="button" data-autoplay="1" data-audio="%s" data-state="zx-state" '
        'data-start="%d" data-autonext="%s" aria-label="播放这一段教材原音">%s'
        '<span class="wave"><i></i><i></i><i></i></span></button></div>'
        '<p class="lesson-hint" id="zx-state">已暂停</p>'
        '<section class="card" id="zx-text">%s</section>'
        '<div class="row">'
        '<form method="post" action="/unit/%s/reading/done" style="flex:1">'
        '<button class="primary" type="submit" style="width:100%%">这一段我听完了，去做本课检测</button>'
        '</form>'
        '<a href="/unit/%s/sentences"><button class="secondary" type="button">去短句跟读</button></a>'
        '</div>'
        '<div class="foot">%s</div>'
        % (index + 1, len(segs),
           _esc(pages_label), _esc(seg["granularity"]),
           _esc("/unit/%s/reading?seg=%d" % (slug, index)), options,
           _esc(seg["audio_url"]), first_start, _esc(autonext), ui.icon("speaker"), chunks,
           _esc(slug), _esc(slug), _esc(PRODUCT_NAME)))
    return shell("听音阅读", body, "/unit/%s" % slug, "返回这一课",
                 sub="%s · %s" % (unit["unit_code"], unit["title"]))


# --------------------------------------------------------------------------- 学习结果
def result_page(ctx: dict) -> str:
    unit = ctx["unit"]
    slug = unit["slug"]
    rows = "".join('<div style="display:flex;justify-content:space-between;padding:10px 0;'
                   'border-top:1px solid var(--line)"><span style="color:var(--text2)">%s</span>'
                   '<span style="font-weight:600">%s</span></div>' % (_esc(k), _esc(v))
                   for k, v in ctx["summary_rows"])
    wrong = len(ctx["check"]["wrong"])
    wrong_block = ('<section class="softcard"><h2>值得再看看</h2>'
                   '<p class="meta">本课检测里有 %d 个地方可以再看一眼。</p>'
                   '<div class="row" style="margin-top:8px">'
                   '<a href="/unit/%s/check/wrong"><button class="secondary" type="button">'
                   '看本课错题</button></a></div></section>' % (wrong, _esc(slug))) if wrong else ""
    needs = "".join('<span style="display:inline-block;background:#FDF3E4;color:#8A5A0B;'
                    'border-radius:999px;padding:3px 10px;margin:0 6px 6px 0">%s</span>' % _esc(w)
                    for w in ctx["need_again"])
    body = (
        '<section class="card"><h2>本次学习 · %s · %s</h2>%s'
        '<p class="meta" style="margin-top:10px">数字来自你自己刚才的学习行为；'
        '没有做过的部分不会显示成绩。</p></section>'
        '<section class="softcard"><h2>需要再看</h2>%s</section>'
        '%s%s'
        '<div class="center-row">'
        '<a href="/unit/%s/continue"><button class="primary" type="button">继续学习</button></a>'
        '</div>'
        '<p class="hint">AI 只说明这次学得怎么样，不会替你安排接下来学什么。</p>'
        '<div class="foot">%s</div>'
        % (_esc(unit["unit_code"]), _esc(ctx["lesson"]["title"]), rows,
           needs or '<p class="meta">这次没有需要再看的词。</p>',
           wrong_block, ctx["ai"]["html"], _esc(slug), _esc(PRODUCT_NAME)))
    return shell("学习结果", body, "/unit/%s" % slug, "返回这一课")


def tutor_page(ctx: dict) -> str:
    """AI 随堂助教：紧凑的"学习发现 → 本课重点 → AI 建议 → 专项/巩固练习入口"。"""
    unit = ctx["unit"]
    slug = unit["slug"]
    # 顶部标题已经写了「AI 随堂助教」，正文不再重复一次同名标题
    body = (
        '%s'
        '<div class="center-row">'
        '<a href="/unit/%s/result"><button class="secondary" type="button">回到学习结果</button></a>'
        '</div>'
        '<div class="foot">%s</div>'
        % (ai_tutor_block(ctx["ai"], title="", with_practice=True), _esc(slug), _esc(PRODUCT_NAME)))
    return shell("AI 随堂助教", body, "/unit/%s/result" % slug, "返回学习结果")


def practice_page(ctx: dict) -> str:
    """自主练习：一段简短学习总结 + 专项 / 巩固练习入口（与首页其他学习入口同级）。"""
    unit = ctx["unit"]
    slug = unit["slug"]
    body = (
        '%s'
        '<div class="foot">%s</div>'
        % (practice_block(ctx["ai"], ctx.get("formal_practice") or []), _esc(PRODUCT_NAME)))
    return shell("自主练习", body, "/unit/%s" % slug, "返回这一课")


def practice_session_page(ctx: dict) -> str:
    """专项 / 巩固练习：一题一题做，答完给正确答案与解释，自己决定做到哪里。"""
    unit = ctx["unit"]
    slug = unit["slug"]
    q = ctx["question"]
    label = "专项练习" if ctx["kind"] == "special" else "巩固练习"
    opts = []
    for letter, text in q["options"]:
        cls = "opt2"
        if ctx["feedback"]:
            if letter == q["answer"]:
                cls += " ok"
            elif letter == ctx["picked"]:
                cls += " bad"
        opts.append('<button class="%s"%s><span class="k">%s</span><span>%s</span>%s</button>'
                    % (cls, "" if ctx["feedback"] else ' type="submit" name="opt" value="%s"' % _esc(letter),
                       _esc(letter.upper()), _esc(text), _option_marks()))
    fb = ""
    foot = ""
    if ctx["feedback"]:
        ok = ctx["correct"]
        fb = ('<div class="qfb %s"><b>%s</b> %s</div>'
              % ("ok" if ok else "again",
                 "答对了。" if ok else "正确答案是 %s。" % _esc(dict(q["options"]).get(q["answer"], "")),
                 _esc(q.get("why") or "")))
        foot = ('<div class="qfoot"><a href="%s"><button class="primary" type="button">%s</button></a></div>'
                % (_esc(ctx["next_href"]), "看练习结果" if ctx["is_last"] else "下一题"))
    qtype = q.get("type") or ""
    qtag = ('<p class="qnum">%s</p>' % _esc(qtype)) if qtype else ""
    #: 从首页「自主练习」进来的：答完一题继续时也保持同一条返回路径
    b_hidden = '<input type="hidden" name="b" value="own">' if ctx.get("back") == "practice" else ""
    body = (
        _steps(ctx["index"] + (1 if ctx["feedback"] else 0), ctx["total"]) +
        '<section class="qwrap"><div class="qbody">'
        '%s'
        '<p class="qstem">%s</p>'
        '<form method="post" action="/unit/%s/practice/answer">'
        '<input type="hidden" name="s" value="%s">'
        '<input type="hidden" name="i" value="%d">'
        '%s'
        '<div class="qopts">%s</div></form>%s</div>%s</section>'
        '<p class="lesson-hint">练习题目全部来自教材内容；做完这一节就结束，由你自己决定。</p>'
        % (qtag,
           _esc(q["prompt"]), _esc(slug), _esc(ctx["session"]), ctx["index"], b_hidden,
           "".join(opts), fb, foot))
    return shell(label, body, ctx["back_href"], ctx["back_label"],
                 sub=_esc(unit["unit_code"]))


def practice_result_page(ctx: dict) -> str:
    unit = ctx["unit"]
    slug = unit["slug"]
    label = "专项练习" if ctx["kind"] == "special" else "巩固练习"
    rows = []
    for row in ctx["rows"]:
        mark = ui.icon("check") if row["correct"] else ui.icon("close")
        color = C_DONE if row["correct"] else C_ERR
        rows.append('<div class="plainrow" style="margin-bottom:8px">'
                    '<span><span class="n">%s</span></span>'
                    '<span class="c" style="color:%s">%s</span></div>'
                    % (_esc(row["prompt"]), color, mark))
    body = (
        '<section class="card">'
        '<p class="textbook-name">答对 %d / %d 题</p>'
        '<p class="meta">做完这一节就到这里；要不要再练一次由你自己决定。</p>%s</section>'
        '<div class="center-row">'
        '<a href="%s"><button class="primary" type="button">%s</button></a>'
        '<a href="/unit/%s"><button class="secondary" type="button">回到这一课</button></a>'
        '</div>'
        '<div class="foot">%s</div>'
        % (ctx["correct"], ctx["total"], "".join(rows), _esc(ctx["back_href"]),
           _esc(ctx["back_to"]), _esc(slug), _esc(PRODUCT_NAME)))
    return shell("%s结果" % label, body, ctx["back_href"], ctx["back_label"])


# --------------------------------------------------------------------------- 课文简答
def say_page(ctx: dict) -> str:
    """课文简答：教材原句 → 孩子写一句 → 批改 / 分析 / 指导 → 孩子决定是否改一改。

    只用一个 AI 区块承载「批改 + 具体发现 + 掌握情况 + 教材依据 + 建议」，
    不新增按钮：想改就直接改上面的输入框再交一次，想继续就用原有的「看学习结果」。
    """
    unit, slug, task = ctx["unit"], ctx["unit"]["slug"], ctx["task"]
    g = ctx["grading"]
    page = (" · 教材第 %s 页" % task["page"]) if task.get("page") else ""
    # 任务类型必须在题目区域一眼可见（不让孩子猜是翻译 / 中文答 / 英文答）
    body = ['<div class="softcard"><p class="qnum">%s</p>'
            '<p class="qnum">教材原句%s</p>'
            '<p class="qstem">%s</p>'
            '<p class="hint">%s</p></div>'
            % (_esc(task.get("task_title") or "用英文写一句话"), _esc(page),
               _esc(task["text"]), _esc(task["ask"])),
            '<p class="qnum">你的表达</p>']
    body.append('<form method="post" action="/unit/%s/say/submit">'
                '<textarea class="saybox" name="text" rows="3">%s</textarea>'
                '<div class="center-row"><button class="primary" type="submit" '
                'style="min-width:180px">看看这次答得怎么样</button></div></form>'
                % (_esc(slug), _esc(ctx["answer"])))
    if ctx["feedback"]:
        completed = g["carries"] and g["complete"] and g.get("coverage", 0) >= 0.6
        cls = "ok" if completed else "again"
        body.append('<div class="qfb %s"><b>%s</b></div>' % (cls, _esc(g["verdict"])))
        used = "、".join(g["used"]) or "还没有用上教材里的说法"
        missing = "、".join(g["missing"]) or "没有特别需要补的"
        basis = ("教材第 %s 页：%s" % (task["page"], task["text"])
                 if task.get("page") else task["text"])
        advice = g["advice"]
        if not g["complete"] and g["hints"]:
            advice = "%s%s" % (advice, g["hints"][0])
        subs = (("批改", g["verdict"]),
                ("用到的教材说法", used),
                ("还可以用上", missing),
                ("掌握情况", g["mark"]),
                ("教材依据", basis),
                (task.get("ref_label") or "参考表达", task["text"]),
                ("建议", advice))
        body.append(_ai_block("AI 批改", subs,
                              note="这里的批改是演示效果，不是真实评分；改不改、继续不继续，由你自己决定。"))
        body.append('<div class="center-row"><a href="/unit/%s/result">'
                    '<button class="primary" type="button" style="min-width:140px">看学习结果</button>'
                    '</a></div>' % _esc(slug))
    return shell("课文简答", "".join(body), "/unit/%s" % slug, "返回这一课",
                 sub="教材内容表达")


def typed_page(ctx: dict) -> str:
    """输入型词汇练习：音标写词 / 词形变化（一屏一题，反馈紧贴题目）。"""
    unit, slug, task = ctx["unit"], ctx["unit"]["slug"], ctx["task"]
    kind, total, index = ctx["kind"], ctx["total"], ctx["index"]
    head, prompt = "", ""
    if kind == "phonetic":
        head = '<p class="phbig">%s</p>' % _esc(task.get("phonetic") or "")
    else:
        prompt = (task.get("prompt") or "").replace(
            "______", "______（%s）" % _esc(task.get("base") or ""), 1)
    stem = ('<p class="qstem">%s</p>' % _esc(prompt)) if prompt else ""
    body = [
        _steps(index + (1 if ctx["feedback"] else 0), total),
        '<section class="qwrap"><div class="qbody">',
        head,
        stem,
        '<form method="post" action="/unit/%s/%s/submit" id="zx-answer">'
        '<input type="hidden" name="i" value="%d">'
        '<input class="typebox" type="text" name="text" value="%s" autocomplete="off" '
        'autocapitalize="off" spellcheck="false"></form>'
        % (_esc(slug), _esc(kind), index, _esc(ctx["answer"])),
        '</div></section>',
    ]
    # 底部操作区固定：提交（随时可再交一次）+ 反馈后出现下一题（按钮沿用既有文字与样式）
    foot = ['<button class="%s" type="submit" form="zx-answer" style="min-width:140px">提交</button>'
            % ("secondary" if ctx["feedback"] else "primary")]
    if ctx["feedback"]:
        rows = ['<p class="fbrow">我的答案：<b>%s</b></p>' % _esc(ctx["answer"])]
        if not ctx["correct"]:
            rows.append('<p class="fbrow">%s：<b>%s</b></p>'
                        % (_esc(ctx["answer_label"]), _esc(ctx["answer_text"])))
        if task.get("reason"):            # 词形变化：一句很短的讲解
            rows.append('<p class="fbrow">%s</p>' % _esc(task["reason"]))
        body.append('<div class="qfb %s"><b>%s</b>%s</div>'
                    % ("ok" if ctx["correct"] else "again",
                       "答对了。" if ctx["correct"] else "再写一次试试。", "".join(rows)))
        foot.append('<a href="%s"><button class="primary" type="button" style="min-width:140px">%s'
                    '</button></a>'
                    % (_esc(ctx["next_href"]), "看学习结果" if ctx["is_last"] else "下一题"))
    body.append('<div class="qfoot"><div class="row" style="margin:0">%s</div></div>'
                % "".join(foot))
    return shell(ctx["title"], "".join(body), "/unit/%s" % slug, "返回这一课",
                 sub=_esc(unit["unit_code"]))


def not_found_page(path: str = "") -> str:
    body = ('<section class="card"><h2>这个页面不存在</h2>'
            '<p class="meta">Demo 里有首页、Unit、单词跟读、听音辨意、本课检测、短句跟读、听音阅读和学习结果。</p>'
            '</section>')
    return shell("没有这个页面", body, "/", "回到首页")


def error_page(title: str, message: str, back_href: str = "/", back_label: str = "返回") -> str:
    body = ('<section class="card"><h2>%s</h2><p class="meta">%s</p>'
            '<div class="center-row"><a href="%s"><button class="primary" type="button">%s</button></a>'
            '</div></section>'
            % (_esc(title), _esc(message), _esc(back_href or "/"), _esc(back_label)))
    return shell(title, body, back_href or "/", back_label)

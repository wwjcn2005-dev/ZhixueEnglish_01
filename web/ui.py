#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-12-C3-C1 正式 Web UI —— 页面渲染（最小骨架）

只实现第一阶段需要的页面：**首页**（+ 404 页）。
视觉严格遵循 docs/P1-12-C3-A 与 docs/P1-12-C3-B：

  背景 #F6F7F9 ｜ 卡片 #FFFFFF ｜ 主文字 #17181A ｜ 次文字 #6B7078 ｜ 辅助文字 #9298A1
  分割线 #E7E9ED ｜ 品牌主色 #1677FF ｜ AI 辅助色 #00A8E8 ｜ 成功 #18A566 ｜ 警告 #F59E0B ｜ 错误 #E5484D

  清爽、专业、安静、轻科技感；学习工具感 > 教育产品感 > 游戏感。
  移动优先；不使用游戏化元素、不使用大面积渐变、不使用 AI 装饰。
"""

from __future__ import annotations

import json
import html
import urllib.parse

import demo_data as demo

PRODUCT_NAME = "智学英语"

#: 课文点读：自然文本块类型的中文标签
KIND_LABEL_CN = {"dialogue": "对话", "letter": "信件", "passage": "课文", "paragraph": "段落"}

#: ---------------------------------------------------------------------------
#: 统一线性 SVG 图标（Demo UI 重构）
#: 规范：24×24 viewBox、stroke-width 1.8、圆头圆角、currentColor 着色、
#: 不使用 emoji 作为功能图标、线条粗细统一、风格柔和现代。
#: ---------------------------------------------------------------------------
_ICON_PATHS = {
    "mic": '<path d="M12 4.5a3 3 0 0 1 3 3v4a3 3 0 0 1-6 0v-4a3 3 0 0 1 3-3z"/>'
           '<path d="M6.5 11.5a5.5 5.5 0 0 0 11 0"/><path d="M12 17v3"/>'
           '<path d="M9 20h6"/>',
    "speaker": '<path d="M5 10h3l4-3.5v11L8 14H5z"/><path d="M15.5 9.5a4 4 0 0 1 0 5"/>'
               '<path d="M18 7.5a7 5 0 0 1 0 9"/>',
    "headphones": '<path d="M4.5 15v-2.5a7.5 7.5 0 0 1 15 0V15"/>'
                  '<rect x="3" y="14" width="4" height="6" rx="2"/>'
                  '<rect x="17" y="14" width="4" height="6" rx="2"/>',
    "chat": '<path d="M20 12.5c0 3-3.6 5.5-8 5.5-1 0-2-.1-2.9-.4L5 19.5l1.1-3.4'
            'C4.8 15 4 13.8 4 12.5 4 9.5 7.6 7 12 7s8 2.5 8 5.5z"/>',
    "book": '<path d="M5 5.5A2 2 0 0 1 7 3.5h11v15H7a2 2 0 0 0-2 2z"/>'
            '<path d="M5 18.5V5.5"/><path d="M9 8h6"/>',
    "play": '<circle cx="12" cy="12" r="8.5"/><path d="M10.5 9.2l5 2.8-5 2.8z"/>',
    "spark": '<path d="M12 4.5l1.6 4.2 4.4 1.6-4.4 1.6L12 16.1l-1.6-4.2L6 10.3l4.4-1.6z"/>'
             '<path d="M18 16.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z"/>',
    "chart": '<path d="M5 19.5V14"/><path d="M12 19.5V7"/><path d="M19 19.5v-9"/>',
    "back": '<path d="M14.5 6.5L9 12l5.5 5.5"/>',
    "check": '<path d="M5.5 12.5l4 4 9-9"/>',
    "refresh": '<path d="M19 12a7 7 0 1 1-2.1-5"/><path d="M19 5v4h-4"/>',
    "home": '<path d="M4.5 11.5L12 5l7.5 6.5"/><path d="M6.5 11v7.5h11V11"/>',
    "pen": '<path d="M6 18l1-4 8-8 3 3-8 8z"/><path d="M14.5 6.5l3 3"/>',
    "replay": '<path d="M5 12a7 7 0 1 1 2.1 5"/><path d="M5 12V7.5h4.5"/>',
    "send": '<path d="M5 12.5l14-7-5.5 14-2.5-5.5z"/>',
    "next": '<path d="M9.5 6.5L15 12l-5.5 5.5"/>',
    "stop": '<rect x="7" y="7" width="10" height="10" rx="2.5"/>',
    "close": '<path d="M6.8 6.8l10.4 10.4"/><path d="M17.2 6.8L6.8 17.2"/>',
}


def icon(name: str, cls: str = "ic") -> str:
    """线性 SVG 图标（无 emoji）。name 见 _ICON_PATHS。"""
    body = _ICON_PATHS.get(name)
    if not body:
        return ""
    return ('<svg class="%s" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
            'aria-hidden="true">%s</svg>' % (html.escape(cls), body))

STYLE = """
  :root{
    --bg:#F6F7F9; --card:#FFFFFF; --text:#17181A; --text2:#6B7078; --text3:#9298A1;
    --line:#E7E9ED; --brand:#1677FF; --ai:#00A8E8; --ok:#18A566; --warn:#F59E0B; --err:#E5484D;
  }
  *{box-sizing:border-box}
  html,body{margin:0;padding:0}
  body{background:var(--bg);color:var(--text);
       font:16px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",Roboto,sans-serif}
  .top{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--line);
       padding:12px 20px}
  .top h1{margin:0;font-size:24px;font-weight:600;letter-spacing:.01em}
  .top .sub{color:var(--text3);font-size:12px;margin-top:2px}
  main{max-width:560px;margin:0 auto;padding:20px 20px 32px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;
        margin-bottom:16px}
  .card h2{margin:0 0 8px;font-size:18px;font-weight:600}
  .card .aux{color:var(--text3);font-size:12px}
  .textbook-name{font-size:20px;font-weight:600;margin:0 0 4px}
  .meta{color:var(--text2);font-size:14px;margin:0 0 4px}
  .facts{color:var(--text2);font-size:14px;margin-top:12px;padding-top:12px;
         border-top:1px solid var(--line)}
  .empty{color:var(--text2);font-size:16px;margin:4px 0 0}
  .empty-sub{color:var(--text3);font-size:13px;margin:4px 0 0}
  .row{display:flex;flex-wrap:wrap;gap:12px;margin-top:16px}
  button{font:inherit;border-radius:12px;padding:12px 20px;min-height:48px;cursor:pointer}
  button.primary{background:var(--brand);color:#fff;border:1px solid var(--brand)}
  button.secondary{background:var(--card);color:var(--text);border:1px solid var(--line)}
  button.text{background:transparent;color:var(--brand);border:0;padding:8px 4px;min-height:auto}
  button[disabled]{opacity:.45;cursor:not-allowed}
  .hint{color:var(--text3);font-size:12px;margin-top:8px}
  .foot{color:var(--text3);font-size:12px;text-align:center;margin-top:24px}
  .bar{display:flex;align-items:center;gap:12px}
  a.back{color:var(--brand);text-decoration:none;font-size:14px;padding:4px 0;min-height:24px}
  .bar .ttl{color:var(--text3);font-size:12px}
  a.unitrow{display:block;background:var(--card);border:1px solid var(--line);border-radius:16px;
            padding:14px 16px;margin-bottom:12px;text-decoration:none;color:var(--text)}
  a.unitrow .code{color:var(--brand);font-size:13px;font-weight:600}
  a.unitrow .ttl{display:block;font-size:18px;font-weight:600;margin:2px 0 2px}
  a.unitrow .pg{color:var(--text3);font-size:12px}
  a.type{display:flex;align-items:center;justify-content:space-between;background:var(--card);
         border:1px solid var(--line);border-radius:16px;padding:14px 16px;margin-bottom:12px;
         text-decoration:none;color:var(--text)}
  a.type .n{font-size:18px;font-weight:600}
  a.type .c{color:var(--text2);font-size:13px}
  .type.off{opacity:.6}
  .item{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;
        margin-bottom:10px}
  .item .w{font-size:20px;font-weight:600}
  /* P2-1-C1（C1-01）：教材黑体重点词用加粗体现；白体词用普通字重，不再加解释性标签 */
  .item .w.core{font-weight:700}
  .item .w.plain{font-weight:400}
  .item .phon{color:var(--text2);font-size:13px;font-family:ui-monospace,Consolas,monospace}
  .item .body{color:var(--text);font-size:15px;margin-top:2px}
  .item .basis{color:var(--text3);font-size:12px;margin-top:4px}
  .fitem{background:var(--card);border:1px solid var(--line);border-radius:12px;
         padding:12px 14px;margin-bottom:10px}
  .fitem .w{font-size:20px;font-weight:600}
  .fitem .body{color:var(--text);font-size:15px;margin-top:2px}
  .fitem .basis{color:var(--text3);font-size:12px;margin-top:4px}
  /* P2-1-C1（C1-06~C1-09）：教材音频播放（孩子主动点击；不自动播放、不预加载） */
  .audiorow{background:var(--card);border:1px solid var(--line);border-radius:12px;
            padding:12px 14px;margin-bottom:10px}
  .audiorow .audiolabel{font-size:16px;font-weight:600;margin-bottom:8px}
  .audiorow .aux{color:var(--text3);font-size:12px;margin-top:6px}
  .audiorow audio{width:100%;height:40px;display:block}
  .audio-inline{margin-top:14px}
  .audio-inline .audiolabel{color:var(--text2);font-size:14px;margin-bottom:6px}
  .audio-inline audio{width:100%;height:40px;display:block}
  /* P2-3 音频按钮：扬声器（单词 🔊）/ 耳机（教材练习 🎧）+ 动态声波
     原生控件保持真实可点击但完全透明（不显示系统播放三角）；
     声波由 audio:playing 驱动，播放结束自动回到静止。
     注：Android WebView 真机实测不支持 audio:playing，声波暂不触发（见 P2-3 报告"未完成项"）。 */
  .spk{position:relative;display:inline-block;width:40px;height:40px;overflow:hidden;
       vertical-align:middle;margin-left:6px;-webkit-tap-highlight-color:transparent}
  .spk audio{position:absolute;left:0;top:0;width:320px;height:40px;margin:0;
       opacity:0;background:transparent;outline:none}
  .spk-ico{position:absolute;left:0;top:0;width:40px;height:40px;pointer-events:none}
  .spk-ico::before{content:attr(data-ico);position:absolute;left:6px;top:50%;
       transform:translateY(-50%);font-size:17px;line-height:1;opacity:.72}
  .spk-ico i{position:absolute;top:50%;width:2px;height:14px;margin-top:-7px;border-radius:2px;
       background:var(--brand);opacity:0;transform:scaleY(.35);transform-origin:50% 50%}
  .spk-ico i:nth-child(1){left:26px}
  .spk-ico i:nth-child(2){left:30px}
  .spk-ico i:nth-child(3){left:34px}
  .spk:has(audio:playing) .spk-ico::before{opacity:1}
  .spk:has(audio:playing) .spk-ico i{opacity:.9;animation:zxwave .9s ease-in-out infinite}
  .spk:has(audio:playing) .spk-ico i:nth-child(2){animation-delay:.15s}
  .spk:has(audio:playing) .spk-ico i:nth-child(3){animation-delay:.3s}
  /* P5 跟读页：整页共用一个播放器，播放态由脚本按真实 playing/pause/ended 事件加上 .on。
     与上面的规则同一视觉（三根蓝色声波），不新增任何可见元素。 */
  .spk.on .spk-ico::before{opacity:1}
  .spk.on .spk-ico i{opacity:.9;animation:zxwave .9s ease-in-out infinite}
  .spk.on .spk-ico i:nth-child(2){animation-delay:.15s}
  .spk.on .spk-ico i:nth-child(3){animation-delay:.3s}
  @keyframes zxwave{0%,100%{transform:scaleY(.35)}50%{transform:scaleY(1)}}
  .spk:active .spk-ico::before{transform:translateY(-50%) scale(.92);opacity:1}
  .item .wrow{display:flex;align-items:center;justify-content:flex-start}
  /* 教材练习 */
  a.ex{display:block;background:var(--card);border:1px solid var(--line);border-radius:12px;
       padding:12px 14px;margin-bottom:10px;text-decoration:none;color:var(--text)}
  a.ex .exhead{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  a.ex .badge{background:#EEF4FF;color:var(--brand);border-radius:8px;padding:2px 8px;
       font-size:12px}
  a.ex .exno{color:var(--text3);font-size:12px}
  a.ex .exins{font-size:15px;margin-top:6px;line-height:1.5}
  a.ex .exaudio{color:var(--text3);font-size:12px;margin-top:6px}
  .field{display:block;margin:10px 0}
  .field label{display:block;color:var(--text2);font-size:14px;margin-bottom:6px}
  .field input,.field textarea{width:100%;font:inherit;padding:10px 12px;border-radius:10px;
       border:1px solid var(--line);background:#FFFFFF;color:var(--text)}
  .field textarea{min-height:72px;resize:vertical}
  .question{border-top:1px solid var(--line);padding-top:12px;margin-top:12px}
  .question:first-child{border-top:0;padding-top:0;margin-top:0}
  .question .qtext{font-size:15px;margin-bottom:6px}
  .feedback{border:1px solid var(--line);border-radius:12px;padding:12px;background:#FBFCFD}
  .feedback .j{font-size:16px;font-weight:600;margin-bottom:6px}
  .feedback ul{margin:6px 0 0 18px;padding:0}
  .feedback li{color:var(--text2);font-size:14px;margin-bottom:4px}
  .center{text-align:center}
  .word{font-size:40px;font-weight:600;letter-spacing:.01em;line-height:1.2}
  .word-phon{color:var(--text2);font-size:15px;font-family:ui-monospace,Consolas,monospace;
             margin-top:6px}
  .word-pos{color:var(--text2);font-size:15px}
  .word-mean{font-size:20px;margin-top:14px}
  .choices{display:flex;flex-direction:column;gap:12px;margin-top:16px}
  .choices button{width:100%}
  .tbq{border-top:1px solid var(--line);margin-top:12px;padding-top:12px}
  .tbitems{margin:10px 0 0 0;padding-left:18px;color:var(--text2);font-size:14px;line-height:1.7}
  .tbitems li{margin:2px 0}
  .opt{display:flex;gap:10px;align-items:flex-start;padding:10px 12px;border:1px solid var(--line);
       border-radius:10px;margin-bottom:8px;font-size:15px;line-height:1.5}
  .opt input{margin-top:3px;width:18px;height:18px;flex:0 0 auto}
  .hidden-mean{border:1px dashed var(--line);border-radius:12px;padding:14px;text-align:center;
               color:var(--text2);font-size:14px;background:#FBFCFD}
  .result-line{font-size:18px;margin-top:6px}
  .sect{margin-top:20px}
  /* ---------------------------------------------------------------
     Demo V1：一级导航（首页 / 学习 / 进展）
     V2.0 总纲规定一级页面为 3 个；这里用最克制的底部三栏实现，
    第三版 Demo：不再有底部一级导航（首页 / 学习 / 进展 已删除）。
     --------------------------------------------------------------- */
  /* Demo V1：学习进度（覆盖范围，不是掌握程度） */
  .pg{display:flex;align-items:center;gap:10px;margin:10px 0}
  .pg .lbl{flex:0 0 72px;color:var(--text2);font-size:14px}
  .pg .track{flex:1;height:8px;border-radius:4px;background:#EDF0F4;overflow:hidden}
  .pg .pgbar{display:block;height:8px;border-radius:4px;background:var(--brand)}
  .pg .num{flex:0 0 46px;text-align:right;color:var(--text3);font-size:12px}
  /* Demo V1：AI 随堂助教（AI 辅助色只用于真正的 AI 辅助信息） */
  .ai{border:1px solid #CBE7F4;background:#F4FBFE;border-radius:16px;padding:16px;
      margin-bottom:16px}
  .ai h2{margin:0 0 8px;font-size:18px;font-weight:600;color:#0B6E92}
  .ai p{margin:0 0 6px;font-size:15px;line-height:1.6}
  .ai p:last-child{margin-bottom:0}
  .ai .focus{color:#0B6E92;font-size:14px;margin-top:8px}
  .ai .ai-unit{font-family:ui-monospace,Consolas,monospace;color:var(--text2);
               font-size:13px;margin:0 0 8px}
  .ai .ai-line{color:#0B6E92;font-size:14px;margin-top:10px}
  .ai .ai-glabel{color:var(--text);font-size:14px;font-weight:600;margin:8px 0 2px}
  .ai .focuslist{margin-bottom:4px}
  .learnact{margin-top:14px}
  .learnact button{width:100%}
  /* Demo V1：演示数据标记（克制：只在演示块顶部出现一次） */
  .demo{display:inline-block;font-size:12px;color:var(--text2);background:#FBFCFD;
        border:1px solid var(--line);border-radius:999px;padding:2px 9px}
  .demo-note{color:var(--text3);font-size:12px;margin:8px 0 0}
  .stat{display:flex;gap:20px;margin-top:12px;padding-top:12px;border-top:1px solid var(--line)}
  .stat div{flex:1}
  .stat .v{font-size:22px;font-weight:600}
  .stat .k{color:var(--text3);font-size:12px;margin-top:2px}
  .next{display:block}
  a.plainrow{display:flex;align-items:center;justify-content:space-between;
             background:var(--card);border:1px solid var(--line);border-radius:12px;
             padding:12px 14px;margin-bottom:10px;text-decoration:none;color:var(--text)}
  a.plainrow .n{font-size:16px;font-weight:600}
  a.plainrow .c{color:var(--text2);font-size:13px}
  .sent{font-size:22px;line-height:1.5;font-weight:600}
  .feedback.same{border-left:3px solid #18A566}
  .feedback.again{border-left:3px solid #F59E0B}
  /* ---------------------------------------------------------------
     Demo V1.1：课堂同步首页 / 今日特训 / 单词跟读 / 练习
     --------------------------------------------------------------- */
  .pos{font-size:26px;font-weight:600;margin:0 0 2px;letter-spacing:.01em}
  .pos-sub{color:var(--text2);font-size:15px;margin:0 0 8px}
  .picker{margin:14px 0 10px;padding:12px 14px;border:1px solid var(--line);
          border-radius:12px;background:#FBFCFD}
  .picker .pklabel{display:block;color:var(--text2);font-size:13px;margin-bottom:6px}
  .picker select{width:100%;font:inherit;font-size:17px;font-weight:600;min-height:56px;
                 padding:14px;border-radius:14px;border:1px solid var(--line);
                 background:#F4F6F9;color:var(--text);cursor:pointer}
  /* P6-B-7：恢复 Demo 已验证的课程选择器（自包含面板，不触发手机系统 picker）
     原生 select 仍留在表单里承担提交与语义，只是不再显示。 */
  .lpick{position:relative}
  .lpick .lpnative{display:none}
  .lpbtn{display:block;width:100%;min-width:0;text-align:left;
         font-size:16px;font-weight:600;min-height:48px;padding:11px 12px;
         border-radius:12px;border:1px solid #E1E6ED;background:#F1F4F8;color:var(--text);
         white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .lpbtn[aria-expanded="true"]{background:#E7ECF3}
  .lplist{margin-top:8px;max-height:420px;overflow-y:auto;background:var(--card);
          border:1px solid var(--line);border-radius:12px;padding:6px}
  .lpopt{display:block;width:100%;text-align:left;font-size:15px;font-weight:500;
         padding:10px;margin:0 0 2px;border:1px solid transparent;border-radius:9px;
         background:transparent;color:var(--text);white-space:nowrap;overflow:hidden;
         text-overflow:ellipsis}
  .lpopt[aria-selected="true"]{background:#F1F4F8;border-color:#E1E6ED;font-weight:700}
  /* P6-B-13：当前课时选择器里的 Unit 分组标题（不可点击，仅作分组） */
  .lpgroup{font-size:12px;font-weight:600;color:var(--text3);padding:8px 10px 2px;
           white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  @media (max-width:600px){
    .lpbtn{font-size:15px;min-height:44px;padding:10px 12px}
    .lpopt{font-size:14px;padding:9px 10px}
  }
  .ai-sub{color:#0B6E92;font-size:13px;font-weight:600;margin:10px 0 4px}
  .focuslist{margin:0;padding:0;list-style:none}
  .focuslist li{padding:8px 0;border-top:1px solid #DCEFF7}
  .focuslist li:first-child{border-top:0}
  .focuslist .fw{display:block;font-size:16px;font-weight:600;color:var(--text)}
  .focuslist .fp{display:block;color:var(--text2);font-size:13px;margin-top:2px}
  .cta-card{background:var(--card);border:1px solid var(--line);border-radius:16px;
            padding:16px;margin-bottom:16px;text-align:center}
  a.cta{display:block;background:var(--brand);color:#fff;text-decoration:none;
        font-size:19px;font-weight:600;line-height:1.4;border-radius:14px;
        padding:20px 16px;border:1px solid var(--brand)}
  a.cta:active{background:#0F63D6;border-color:#0F63D6}
  .cta-note{color:var(--text2);font-size:13px;margin:10px 0 0;text-align:left}
  .prow{padding:10px 0;border-top:1px solid var(--line)}
  .prow:first-of-type{border-top:0;padding-top:0}
  .prow-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px}
  .plabel{font-size:16px;font-weight:600}
  .pvalue{font-size:20px;font-weight:600;color:var(--brand)}
  .pnote{color:var(--text2);font-size:13px;margin:4px 0 0}
  /* 单词跟读：左右滑动切换（原生滚动 + scroll-snap，无需脚本） */
  .wordswipe{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;gap:16px;
             margin:0 -20px;padding:0 20px 6px;-webkit-overflow-scrolling:touch}
  .wcard{flex:0 0 86%;min-width:86%;scroll-snap-align:center;background:var(--card);
         border:1px solid var(--line);border-radius:16px;padding:18px 16px}
  .wcard .w{font-size:38px;font-weight:600;line-height:1.2;word-break:break-word}
  .wcard .wc-top{color:var(--text3);font-size:12px;margin-bottom:10px}
  .wcard .ctx{color:var(--text2);font-size:14px;margin-top:12px;padding-top:12px;
              border-top:1px solid var(--line)}
  .wc-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
  .wc-actions button{padding:10px 14px;min-height:44px;font-size:15px}
  .swipe-hint{color:var(--text3);font-size:12px;margin:10px 0 0;text-align:center}
  /* 练习：在同一页里一题一题往下做 */
  .dq{border-top:1px solid var(--line);padding-top:14px;margin-top:14px}
  .dq:first-child{border-top:0;padding-top:0;margin-top:0}
  .dq-h{display:flex;align-items:center;gap:8px;margin-bottom:6px}
  .dq-h .badge{background:#EEF4FF;color:var(--brand);border-radius:8px;padding:2px 8px;
               font-size:12px}
  .dq-h .aux{color:var(--text3);font-size:12px}
  .dq-p{font-size:16px;line-height:1.6;margin-bottom:10px}
  .dq-fb{margin-top:10px;border-radius:12px;padding:10px 12px;font-size:14px;
         background:#FBFCFD;border:1px solid var(--line)}
  .dq-fb.ok{border-left:3px solid #18A566;color:var(--text)}
  .dq-fb.hint{border-left:3px solid #F59E0B;color:var(--text)}
  .playbtn{display:inline-flex;align-items:center;gap:6px;background:var(--card);
           color:var(--brand);border:1px solid #CFE0FF;border-radius:10px;
           padding:9px 12px;font-size:14px;min-height:40px;cursor:pointer}
  .playbtn:active{background:#F2F7FF}
  .playbtn.playing{background:#EEF5FF;border-color:var(--brand)}
  .rec{margin-top:14px;border:1px solid #D8E4FF;background:#F7FAFF;border-radius:12px;
       padding:14px}
  .rec .rec-state{font-size:14px;color:var(--text);margin-bottom:8px}
  .rec audio{width:100%;margin-top:10px}
  .rec .rec-note{color:var(--text3);font-size:12px;margin:8px 0 0}
  .plan{margin:0;padding:0;list-style:none}
  .plan li{border-top:1px solid var(--line);padding:10px 0}
  .plan li:first-child{border-top:0;padding-top:0}
  .plan .pn{font-size:16px;font-weight:600}
  .plan .pd{color:var(--text2);font-size:13px;margin-top:2px}
  .plan .pm{color:var(--text3);font-size:12px}
  .plan li.off .pn{color:var(--text2);font-weight:500}
  /* ---------------------------------------------------------------
     Demo V1.2：极简学习页（单词跟读 / 句子跟读 / 听音辨词）
     一屏一个任务：进度 → 内容 → 操作；不放统计、不放技术信息。
     --------------------------------------------------------------- */
  .lesson{min-height:calc(100vh - 132px);display:flex;flex-direction:column}
  .lesson .swipe{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;gap:16px;
                margin:0 -20px;padding:0 20px;flex:1;align-items:stretch;
                -webkit-overflow-scrolling:touch;scrollbar-width:none}
  .lesson .swipe::-webkit-scrollbar{display:none}
  .lesson .card-w{flex:0 0 100%;min-width:100%;scroll-snap-align:center;
                 display:flex;flex-direction:column;align-items:center;text-align:center;
                 padding:8px 0 16px}
  .lesson .card-w .w{font-size:44px;font-weight:600;line-height:1.15;letter-spacing:.01em;
                    word-break:break-word}
  .lesson .card-w .phon{color:var(--text2);font-size:16px;margin-top:8px;
                       font-family:ui-monospace,Consolas,monospace}
  .lesson .card-w .pos{color:var(--text2);font-size:15px;margin-top:4px}
  .lesson .card-w .mean{font-size:21px;margin-top:12px}
  .lesson .card-w .eg{color:var(--text3);font-size:13px;line-height:1.6;margin:16px 0 0;
                     text-align:left;width:100%}
  .lesson .card-w .sent{font-size:24px;line-height:1.5;font-weight:600;margin:0}
  .lesson .fb{width:100%;margin-top:14px;border-radius:12px;padding:10px 12px;font-size:14px;
             text-align:left;border:1px solid var(--line);background:var(--card);display:none}
  .lesson .fb.show{display:block}
  .lesson .fb.ok{border-left:3px solid #18A566}
  .lesson .fb.warn{border-left:3px solid #F59E0B}
  .lesson .fb .tip{color:var(--text3);font-size:12px;margin-top:4px}
  /* 2026-10-01：AI 老师「答错讲解」的视觉（青色体系，与听读课文 AI 补全段统一）。
     为什么需要这组规则（两处历史缺陷）：
       ① 桥脚本原先输出 `class="fbshow"`（**中间缺空格**）⇒ 与 `.fb.show` 永不匹配，讲解块零样式；
       ② 即使类名正确，`.fb` 系列规则**只存在于 `.lesson` 作用域内**，而六个入口练习页没有 `.lesson`。
     现在：桥脚本输出 `class="fb show ai-teach"`；本组规则**不依赖 `.lesson`**，只在教学块上生效，
     **不改动上面 `.lesson .fb` 的 5 条规则**（跟读页视觉不变）。
     配色依据：青底 #F4FBFE + 青框 #CBE7F4（= 听读课文 AI 补全段实测基准，见 C3-E §4.2）；
     标签色 `var(--ai)`（#00A8E8）—— 落实 C3-E §6.2「`--ai` 预留给 AI 讲解容器」。 */
  .fb.ai-teach{display:block;width:100%;margin-top:14px;border-radius:12px;padding:12px;
               background:#F4FBFE;border:1px solid #CBE7F4;font-size:14px;text-align:left;
               color:var(--text)}
  .fb.ai-teach .ai-tag{color:var(--ai);font-size:14px;font-weight:600}
  .fb.ai-teach > div{margin-top:6px;line-height:1.7}
  .fb.ai-teach > div:first-of-type{margin-top:8px}
  .lesson-hint{color:var(--text3);font-size:12px;text-align:center;margin:6px 0 0}
  /* 听音辨词：卡片内选择 */
  .quiz .qtitle{font-size:16px;color:var(--text2);margin:0 0 8px}
  .quiz .opt{display:flex;gap:10px;align-items:flex-start;width:100%;text-align:left;
             padding:12px;border:1px solid var(--line);border-radius:10px;margin-bottom:8px;
             font-size:16px;background:var(--card)}
  .quiz .opt input{margin-top:4px;width:18px;height:18px;flex:0 0 auto}
  .quiz .confirm{width:100%;margin-top:6px}
  /* 课文点读：原书页面 + 热点 */
  .pdfpage{position:relative;border:1px solid var(--line);border-radius:12px;overflow:hidden;
           background:#fff;line-height:0}
  .pdfpage img{width:100%;height:auto;display:block}
  /* 自然文本块：一个块可能由多个矩形组成，但视觉上是「一个完整的教材文本块」 */
  .pdfpage .blk{position:absolute;border:0;padding:0;cursor:pointer;
                border-radius:4px;background:rgba(22,119,255,.08);
                box-shadow:inset 0 0 0 1px rgba(22,119,255,.20);transition:background .15s}
  .pdfpage .blk:hover{background:rgba(22,119,255,.16)}
  .pdfpage .blk.playing{background:rgba(0,168,232,.22);
                        box-shadow:inset 0 0 0 1px rgba(0,168,232,.45)}
  .pagenav{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:12px 0 0}
  .pagenav .pg{color:var(--text2);font-size:13px}
  .vh{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;
      clip:rect(0 0 0 0);white-space:nowrap;border:0}
  /* =================================================================
     第二版 Demo：活泼 · 清爽 · 现代（初一学生）
     规则：不用横线/竖线分隔，区域靠 留白 + 浅色块 + 圆角 + 字级 + 图标
     ================================================================= */
  svg.ic{width:22px;height:22px;display:block;flex:0 0 auto}
  .softcard{background:var(--card);border-radius:18px;padding:16px;margin-bottom:14px;
            box-shadow:0 1px 3px rgba(16,24,40,.05)}
  .softcard h2{margin:0 0 10px;font-size:16px;font-weight:700;letter-spacing:.01em}
  /* 首页课堂菜单（Module / Unit 切换）：文字与点击区域放大，手机上更好点 */
  .unitcard{padding:20px 18px}
  .unitcard .um-book{color:var(--text2);font-size:14px;margin:0 0 6px}
  .unitcard .um-now{font-size:22px;font-weight:700;letter-spacing:.01em;margin:0;
                    line-height:1.3}
  /* 功能入口：独立圆角浅色块（不同功能不同低饱和色），无编号、无线条 */
  a.entryrow,.entryrow{display:flex;align-items:center;gap:12px;text-decoration:none;
                       color:var(--text);background:var(--tint,#F3F5F8);
                       border-radius:16px;padding:15px 16px;margin-bottom:10px}
  a.entryrow:active{transform:scale(.994)}
  .entryrow .ico{width:42px;height:42px;border-radius:13px;background:#fff;
                 display:flex;align-items:center;justify-content:center;color:var(--hue,#4A5160)}
  .entryrow .nm{flex:1;font-size:17px;font-weight:600;letter-spacing:.01em}
  .entryrow .st{font-size:13px;font-weight:600;color:var(--hue,#6B7078);white-space:nowrap}
  .entryrow.fin .st{color:#1E8A5F}
  .e-word{--tint:#EAF2FF;--hue:#2F6BE0}
  .e-quiz{--tint:#E6F6FA;--hue:#1B87A8}
  .e-phrase{--tint:#E9F5EE;--hue:#1E8A5F}
  .e-read{--tint:#FDF3E4;--hue:#B5761A}
  .e-listen{--tint:#EDEFFB;--hue:#4A55B8}
  .e-text{--tint:#F1F3F7;--hue:#4A5160}
  .e-tutor{--tint:#EAF7FB;--hue:#0B6E92}
  /* 我的进展：每类不同低饱和色 */
  .dim{margin-bottom:14px}
  .dim:last-child{margin-bottom:0}
  .dim .top{display:flex;align-items:baseline;justify-content:space-between;gap:10px}
  .dim .lb{font-size:15px;font-weight:600}
  .dim .vl{font-size:17px;font-weight:700;color:var(--hue,#2F6BE0)}
  .dim .tr{display:block;height:9px;border-radius:6px;background:#EEF1F5;margin-top:8px;
           overflow:hidden}
  .dim .tr i{display:block;height:9px;border-radius:6px;background:var(--hue,#2F6BE0)}
  .dim .nt{color:var(--text2);font-size:13px;margin:6px 0 0}
  @keyframes breathe{0%,100%{transform:scale(1)}50%{transform:scale(1.045)}}
  @keyframes wv{0%,100%{height:6px}50%{height:15px}}
  .opts{display:flex;flex-direction:column;gap:10px;margin-top:6px}
  /* 听音辨词：动态大扬声器（118px 圆 + 三声波 + 呼吸动画 + .on 播放态） */
  .soundstage{display:flex;flex-direction:column;align-items:center;justify-content:center;
              padding:10px 0 4px}
  button.spkbig,.spkbig{width:118px;height:118px;border-radius:50%;border:0;cursor:pointer;
                        background:#E6F6FA;color:#1B87A8;display:flex;align-items:center;
                        justify-content:center;position:relative}
  .spkbig svg{width:52px;height:52px}
  .spkbig .wave{position:absolute;display:flex;align-items:flex-end;gap:3px;bottom:22px;
                height:16px;opacity:0}
  .spkbig .wave i{width:3px;height:8px;border-radius:2px;background:#1B87A8}
  .spkbig.on{animation:breathe 1.6s ease-in-out infinite}
  .spkbig.on .wave{opacity:.9}
  .spkbig.on .wave i{animation:wv .9s ease-in-out infinite}
  .spkbig.on .wave i:nth-child(2){animation-delay:.15s}
  .spkbig.on .wave i:nth-child(3){animation-delay:.3s}
  button.opt2{display:flex;align-items:center;gap:10px;background:#F4F6F9;
              border:1px solid var(--line);
              border-radius:14px;padding:15px 16px;font-size:17px;font-weight:600;
              color:var(--text);text-align:left;cursor:pointer;position:relative}
  button.opt2 .k{width:24px;height:24px;border-radius:50%;background:#fff;color:var(--text2);
                 font-size:13px;font-weight:700;display:flex;align-items:center;
                 justify-content:center;flex:0 0 auto}
  button.opt2.sel{background:#E7F0FF;color:#1B4FBF}
  button.opt2.sel .k{background:#1B6BE8;color:#fff}
  /* 已提交后的选项状态：答对=浅绿底+绿边框+绿勾；答错=浅红底+红边框+红叉 */
  button.opt2.ok{background:#EAF6EF;border-color:#18A566;color:#12703F}
  button.opt2.ok .k{background:#18A566;color:#fff}
  button.opt2.bad{background:#FDECEC;border-color:#E5484D;color:#B3261E}
  button.opt2.bad .k{background:#E5484D;color:#fff}
  .opt2 .mk{display:none;margin-left:auto;flex:0 0 auto}
  .opt2 .mk svg{width:20px;height:20px}
  .opt2.ok .mk-ok{display:flex;color:#18A566}
  .opt2.bad .mk-no{display:flex;color:#E5484D}
  /* 音频按钮：宽、浅底、图标在左，向左右展开（不挤在页面正中） */
  .audiorow{display:flex;gap:10px;width:100%;margin:2px 0 14px}
  button.abtn{flex:1;display:flex;align-items:center;gap:10px;min-height:52px;padding:0 18px;
              border-radius:14px;border:1px solid var(--line);background:#F1F4F8;
              color:var(--text);font:inherit;font-size:15px;font-weight:600;cursor:pointer;
              position:relative}
  button.abtn svg{width:22px;height:22px;flex:0 0 auto;color:#1B87A8}
  button.abtn .wave{position:absolute;right:16px;bottom:11px;display:flex;gap:3px;
                    height:11px;opacity:0}
  button.abtn .wave i{width:3px;height:5px;border-radius:2px;background:#1B87A8}
  button.abtn.on,button.abtn.playing{border-color:#8FD3E5;background:#E6F6FA;
                 animation:breathe 1.6s ease-in-out infinite}
  button.abtn.on .wave,button.abtn.playing .wave{opacity:.9}
  button.abtn.on .wave i,button.abtn.playing .wave i{animation:wv .9s ease-in-out infinite}
  button.abtn.on .wave i:nth-child(2),button.abtn.playing .wave i:nth-child(2){animation-delay:.15s}
  button.abtn.on .wave i:nth-child(3),button.abtn.playing .wave i:nth-child(3){animation-delay:.3s}
  /* 统一进度：━━━ N / TOTAL（细线 + 题号；无圆环 / 百分比 / 圆点 / 大组件） */
  .steps{display:flex;align-items:center;gap:10px;padding:2px 0 10px}
  .steps .bar{flex:1;height:3px;border-radius:2px;background:#E4E7EC;overflow:hidden}
  .steps .bar i{display:block;height:3px;border-radius:2px;background:#2F6BE0;
                transition:width .18s ease}
  .steps .cnt{color:var(--text2);font-size:12px;font-variant-numeric:tabular-nums;
              white-space:nowrap}
  /* 错题池（本机 Demo）：只是学习证据上的一个小标记，不是新的产品中心 */
  .chip{display:inline-flex;align-items:center;background:#FDF3E4;color:#8A5A0B;
        border-radius:999px;font-size:12px;font-weight:600;padding:2px 10px;
        margin:0 0 8px}
  .qfin{background:#EAF6EF;color:#12703F;border-radius:14px;padding:12px 14px;
         font-size:14px;font-weight:600;line-height:1.6;margin-top:12px}
  @keyframes recpulse{0%,100%{box-shadow:0 0 0 0 rgba(229,72,77,.34)}
                      70%{box-shadow:0 0 0 16px rgba(229,72,77,0)}}
  .analyzing{display:flex;align-items:center;justify-content:center;gap:8px;color:#1B87A8;
             font-size:15px;font-weight:600;margin-top:14px}
  .analyzing i{width:6px;height:6px;border-radius:50%;background:#1B87A8;
               animation:jump .9s ease-in-out infinite}
  .analyzing i:nth-child(2){animation-delay:.15s}
  .analyzing i:nth-child(3){animation-delay:.3s}
  @keyframes jump{0%,100%{transform:translateY(0);opacity:.45}
                  50%{transform:translateY(-5px);opacity:1}}
  /* 跟读结果（演示） */
  .resline{display:flex;align-items:center;gap:8px;font-size:15px;margin:8px 0;
           color:var(--text)}
  .resline .k{color:var(--text2);width:76px;flex:0 0 auto;font-size:14px}
  .resline .v{font-weight:600}
  .resline.ok .v{color:#1E8A5F}
  .warnword{background:#FDF1DC;color:#8A5A0B;border-radius:8px;padding:1px 7px;font-weight:600}
  /* =================================================================
     第三版 Demo：无底部一级导航；顶部栏（返回 + 真正居中的标题）
     ================================================================= */
  body{padding-bottom:16px}
  .tb{position:sticky;top:0;z-index:6;background:var(--bg);display:flex;align-items:center;
      gap:8px;padding:12px 16px 8px;max-width:560px;margin:0 auto}
  .tb-mid{flex:1;min-width:0;text-align:center}
  .tb h1{text-align:center;margin:0;font-size:18px;font-weight:700;letter-spacing:.01em}
  .tb-sub{display:block;color:var(--text3);font-size:12px;margin-top:2px}
  .tb-back,.tb-right{flex:0 0 44px;height:44px;display:flex;align-items:center;
                     justify-content:center;border-radius:12px;text-decoration:none;
                     color:var(--text2)}
  .tb-back:active{background:#EEF1F5}
  /* 单卡学习页（无进度、无卡片堆叠）：内容居中 + 底部固定三操作 */
  .stage{min-height:calc(100vh - 150px);display:flex;flex-direction:column;align-items:center;
         justify-content:center;text-align:center;padding:8px 0}
  .stage .bigword{font-size:46px;font-weight:700;line-height:1.12;letter-spacing:.01em;
                  word-break:break-word}
  .stage .phon{color:var(--text2);font-size:16px;margin-top:10px;
               font-family:ui-monospace,Consolas,monospace}
  .stage .mean{font-size:21px;margin-top:10px}
  .stage .eg{color:var(--text3);font-size:13px;line-height:1.6;margin:22px 0 0;
             text-align:left;width:100%}
  /* 底部三个操作：向左右自然展开（不挤在页面正中），左右留白 + 视觉平衡 */
  .opsbar{position:sticky;bottom:0;background:var(--bg);padding:10px 26px 14px;
          display:flex;align-items:center;justify-content:space-between;gap:18px;
          width:100%;max-width:520px;margin:0 auto}
  /* 单词跟读：静态扬声器 / 回放 = 原来的图标 + 统一浅色承托底（不是 CTA、不是文字按钮） */
  .opsbar .op{width:56px;height:56px;border-radius:50%;border:0;background:#fff;
              color:var(--text2);display:flex;align-items:center;justify-content:center;
              cursor:pointer;box-shadow:0 1px 3px rgba(16,24,40,.06)}
  .opsbar .op{background:#EDF1F6;border:1px solid #E1E6ED;border-radius:18px;
              color:#4A5160;box-shadow:none}
  .opsbar .op svg{width:24px;height:24px}
  .opsbar .op:disabled{opacity:.4}
  .opsbar .op{position:relative}
  .opsbar .op .wave{position:absolute;bottom:9px;display:flex;gap:3px;height:11px;opacity:0}
  .opsbar .op .wave i{width:3px;height:5px;border-radius:2px;background:currentColor}
  .opsbar .op.on{color:#2F6BE0;background:#EAF2FF;animation:breathe 1.6s ease-in-out infinite}
  .opsbar .op.on .wave{opacity:.9}
  .opsbar .op.on .wave i{animation:wv .9s ease-in-out infinite}
  .opsbar .op.on .wave i:nth-child(2){animation-delay:.15s}
  .opsbar .op.on .wave i:nth-child(3){animation-delay:.3s}
  .opsbar .mic{width:84px;height:84px;border-radius:50%;border:0;background:#2F6BE0;color:#fff;
               display:flex;align-items:center;justify-content:center;cursor:pointer;
               box-shadow:0 8px 20px rgba(47,107,224,.3)}
  .opsbar .mic svg{width:36px;height:36px}
  .opsbar .mic.rec{background:#E5484D;animation:recpulse 1.4s ease-in-out infinite}
  /* 练习页：顶部栏 → 题面 → 作答 → 底部提交/下一题 */
  .qwrap{display:flex;flex-direction:column;min-height:calc(100vh - 150px)}
  .qbody{flex:1}
  /* 阅读练习自带的阅读材料（教材课文之外才出现） */
  .dmaterial{background:#F4F6F9;border-radius:16px;padding:14px 16px;margin:0 0 14px}
  .dmaterial .dmtext{margin:0;font-size:16px;line-height:1.75}
  .qnum{color:var(--text3);font-size:13px;margin:0 0 6px}
  .qstem{font-size:18px;line-height:1.65;margin:0 0 14px}
  .qstem .blank{display:inline-block;min-width:72px;border-bottom:2px dotted #C7CDD6}
  .qopts{display:flex;flex-direction:column;gap:10px}
  .qin{width:100%;font:inherit;font-size:16px;padding:13px 14px;border-radius:14px;
       border:1px solid var(--line);background:#fff;color:var(--text)}
  textarea.qin{min-height:104px;line-height:1.6;resize:vertical}
  button.qopt{display:flex;align-items:center;gap:10px;width:100%;text-align:left;
              background:#F4F6F9;border:1px solid var(--line);border-radius:14px;
              padding:15px 16px;font-size:17px;font-weight:600;color:var(--text);
              cursor:pointer}
  button.qopt .k{width:24px;height:24px;border-radius:50%;background:#fff;color:var(--text2);
                 font-size:13px;font-weight:700;display:flex;align-items:center;
                 justify-content:center;flex:0 0 auto}
  button.qopt.sel{background:#E7F0FF;color:#1B4FBF}
  button.qopt.sel .k{background:#1B6BE8;color:#fff}
  button.qopt.ok{background:#EAF6EF;border-color:#18A566;color:#12703F}
  button.qopt.ok .k{background:#18A566;color:#fff}
  button.qopt.bad{background:#FDECEC;border-color:#E5484D;color:#B3261E}
  button.qopt.bad .k{background:#E5484D;color:#fff}
  .opt2 .mk,.qopt .mk{display:none;margin-left:auto;flex:0 0 auto}
  .opt2 .mk svg,.qopt .mk svg{width:20px;height:20px}
  .opt2.ok .mk-ok,.qopt.ok .mk-ok{display:flex;color:#18A566}
  .opt2.bad .mk-no,.qopt.bad .mk-no{display:flex;color:#E5484D}
  .qfb{margin:14px 0 0;border-radius:14px;padding:12px 14px;background:#F4F6F9;
       font-size:14px;color:var(--text)}
  .qfb.ok{background:#EAF6EF}
  .qfb.again{background:#FDF3E4}
  .qfoot{position:sticky;bottom:0;background:var(--bg);padding:10px 0 14px}
  .qfoot button{width:100%}
  /* 单词跟读：一屏一个词（单词 + 音标 + 中文意思是视觉中心） */
  .lesson .card-w{justify-content:center;min-height:calc(100vh - 300px)}
  .lesson .card-w .w{font-size:46px;font-weight:700}
  .lesson .card-w .opts{width:100%;margin-top:24px}
  .lesson .js-result{width:100%;text-align:left;margin-top:18px}
  .stage .eg-zh,.lesson .card-w .eg .eg-zh{display:block;color:var(--text2);font-size:13px;
                                          margin-top:2px}
  .pdfwrap{overflow:auto;-webkit-overflow-scrolling:touch;border-radius:12px}
  .pdfpage.zoom{width:170%}
  .pdfpage.zoom img{max-width:none}
  button.tbtn{background:var(--card);border:1px solid var(--line);border-radius:12px;
              color:var(--text);font:inherit;font-size:14px;padding:8px 14px;min-height:44px;
              cursor:pointer}
  @media (max-width:420px){
    .lesson .card-w .w{font-size:38px}
    .tb h1{font-size:17px}
    .opsbar{gap:28px}
    .sheet .box .row{flex-wrap:nowrap}
  }
  /* 作答返回保护弹窗（轻、圆角、无线条、非危险样式） */
  .sheet{position:fixed;inset:0;background:rgba(23,24,26,.28);display:none;
         align-items:center;justify-content:center;padding:24px;z-index:20}
  .sheet.show{display:flex}
  .sheet .box{background:#fff;border-radius:20px;padding:20px 18px;max-width:340px;width:100%}
  .sheet .box h2{margin:0 0 8px;font-size:17px;font-weight:700}
  .sheet .box p{margin:0 0 16px;color:var(--text2);font-size:14px;line-height:1.6}
  .sheet .box .row{margin:0}
  .sheet .box button{flex:1}
  /* 单元中心（学情分析页一期）：课时选择器标题旁的入口图标 */
  .lpick .uc-entry{position:absolute;right:8px;top:50%;transform:translateY(-50%);
       display:inline-flex;align-items:center;justify-content:center;
       width:32px;height:32px;border-radius:8px;color:var(--text3);
       text-decoration:none;z-index:2}
  .lpick .uc-entry .ic{width:18px;height:18px}
  .lpick .uc-entry:active{background:#E7ECF3;color:var(--text)}
  .lpick .lpbtn{padding-right:44px}
  .uc-big{margin:0;font-size:19px;font-weight:600;color:var(--text);line-height:1.5}
  .uc-ai-wait{color:var(--text3)}
  /* 单元中心二期：知识点行（中文名 + 练了/答对 + 程度词） */
  .uc-kp{display:flex;align-items:baseline;justify-content:space-between;gap:12px;
       padding:12px 0;border-bottom:1px solid var(--line)}
  .uc-kp:last-child{border-bottom:0}
  .uc-kp .n{font-size:15px;color:var(--text);min-width:0;flex:0 1 auto}
  .uc-kp .v{flex:0 0 auto;color:var(--text2);font-size:13px;white-space:nowrap}
  .uc-kp .lv{margin-left:8px;font-size:12px;border-radius:999px;padding:2px 8px;
       background:#F1F4F8;color:var(--text2)}
  .uc-kp .lv.done{background:#EAF6EF;color:var(--ok)}
  .uc-kp .lv.doing{background:#FFF7E6;color:var(--warn)}
  .uc-fold{margin-top:12px;border-top:1px solid var(--line);padding-top:10px}
  .uc-fold summary{cursor:pointer;color:var(--text2);font-size:13px;list-style:none}
  .uc-fold summary::-webkit-details-marker{display:none}
  .uc-fold summary::before{content:"▸ ";color:var(--text3)}
  .uc-fold[open] summary::before{content:"▾ "}
  .uc-fold .chips{margin-top:10px;display:flex;flex-wrap:wrap;gap:8px}
  .uc-fold .chip{background:#F1F4F8;color:var(--text2);font-size:13px;
       border-radius:999px;padding:4px 10px}
  /* 单元中心二期：两个练习按钮 */
  .uc-btns{display:flex;flex-direction:column;gap:10px;margin-top:4px}
  .uc-btn{display:flex;align-items:baseline;justify-content:space-between;gap:12px;
       padding:14px 16px;border-radius:12px;background:#F1F4F8;text-decoration:none;
       color:var(--text)}
  .uc-btn .t{font-size:16px;font-weight:600}
  .uc-btn .d{font-size:13px;color:var(--text2)}
  .uc-btn:active{background:#E7ECF3}
  .uc-empty{margin:0;color:var(--text2);font-size:14px;line-height:1.7}
"""


#: P6-B-7：正式页面外壳——只接入 Demo（DEMO_CSS）中正式页面实际需要的规则，
#: 使正式 Web UI 与已确认的 Demo 视觉基线一致（固定顶栏 / main 唯一滚动 / 底栏吸底 /
#: 宽度体系 / 按钮样式 / 模式栏 / 练习重心 / 听音页布局）。不改变任何业务逻辑。
FORMAL_UI_CSS = """
  html{height:100%;overflow:hidden}
  body{height:100vh;height:100dvh;display:flex;flex-direction:column;overflow:hidden;
       padding-bottom:0}
  main{width:100%;max-width:560px;margin-inline:auto;padding-inline:20px;
       flex:1 1 auto;min-height:0;overflow-y:auto;display:flex;flex-direction:column;
       scrollbar-gutter:stable}
  main > *{flex-shrink:0}
  .tb{width:100%;max-width:560px;margin-inline:auto;padding-inline:20px;
      position:static;flex:0 0 auto}
  .opsbar{width:100%;max-width:560px;margin-inline:auto;padding-inline:20px}
  .opsbar,.qfoot{margin-top:auto}
  main:has(.opsbar),main:has(.qfoot){padding-bottom:0}
  button.primary{background:#F1F4F8;color:var(--text);border:1px solid #E1E6ED;font-weight:600}
  button.primary:active{background:#E7ECF3}
  button.secondary{background:var(--card);color:var(--text);border:1px solid var(--line)}
  button.text{color:var(--text2)}
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
  .lesson{flex:1 0 auto;min-height:0;display:flex;flex-direction:column;
          justify-content:center}
  .qwrap{flex:1 0 auto;min-height:0;display:flex;flex-direction:column;justify-content:center}
  .qbody{flex:1 1 auto;min-height:0;display:flex;flex-direction:column;justify-content:center}
  .lesson .card-w{min-height:0}
  .lesson .swipe{min-height:0;overflow-x:auto;overflow-y:hidden}
  /* P6-B-8：恢复 Demo 的跟读控制器视觉（基础 .op 的圆形/白底不再生效） */
  .opsbar .op{width:56px;height:56px;border-radius:18px;background:#EDF1F6;
              border:1px solid #E1E6ED;color:var(--text2);box-shadow:none}
  .opsbar .mic{width:84px;height:84px;border-radius:50%;background:#EDF1F6;
               border:1px solid #E1E6ED;color:#4A5160;box-shadow:none}
  .opsbar .mic svg{width:34px;height:34px}
  .opsbar .mic.rec{background:#E5484D;border-color:#E5484D;color:#fff}
  /* P6-B-8：首页课程选择器的绘制顺序（展开时不得与六入口互相穿插/遮挡）
     只建立必要的层序，不使用大 z-index。 */
  .softcard.unitcard{position:relative;z-index:2}
  .lpick{position:relative;z-index:3}
  a.entryrow,.entryrow{position:relative;z-index:1}
  .softcard.unitcard .picker{padding:10px 12px;margin:14px 0 10px}
  @media (max-width:600px){
    .softcard.unitcard .picker{padding:8px 10px;margin:10px 0 8px}
  }
  /* P6-B-9：课程下拉改为覆盖式浮层——不再挤占 main 的流内空间，也不会被六入口/Header 遮挡 */
  .lplist{position:absolute;left:0;right:0;top:100%;margin-top:8px;z-index:4;
          max-height:420px;overflow-y:auto;
          box-shadow:0 10px 24px rgba(16,24,40,.10)}
  /* P6-B-9：去掉 .tb 遗留的 z-index（static flex 项带 z-index 会建立多余层叠上下文） */
  .tb{z-index:auto}
  .tb-right a{display:flex;align-items:center;justify-content:center;width:44px;height:44px;
              border-radius:12px;color:var(--text2);text-decoration:none}
  /* P6-B-12：答题页恢复为两个独立视觉区域：
     A 中部内容区（题目 / 内容 / 输入 / 选项 / 扬声器）在剩余空间中整体居中；
     B 底部操作区（提交 / 下一题 / 再试一次）独立贴在这一屏的底部。
     题目内容过长时只滚动 A 区，不使用屏幕高度计算，也不让题目长度决定按钮位置。 */
  .qwrap.qcenter,.qwrap.listen{flex:1 0 auto;min-height:0;display:flex;
                               flex-direction:column;justify-content:normal;
                               padding-bottom:0}
  .qwrap.qcenter .qbody,.qwrap.listen .qbody{flex:1 1 auto;min-height:0;
                                             display:flex;
                                             flex-direction:column;align-items:stretch;
                                             justify-content:normal}
  .qwrap.qcenter .qmain,.qwrap.listen .qmain{width:100%;margin-block:auto;
                                              display:flex;flex-direction:column;
                                              align-items:center}
  .qwrap.qcenter .qmain .qstem,.qwrap.listen .qmain .qstem{
    width:100%;text-align:center;margin:0 0 14px}
  .qwrap.qcenter .qmain .phbig,.qwrap.listen .qmain .phbig{
    width:100%;text-align:center;margin:10px 0 2px;font-size:26px;font-weight:600;
    font-family:ui-monospace,Consolas,monospace}
  .qwrap.qcenter .qmain form{width:100%;margin-top:0;display:flex;flex-direction:column;
                             align-items:center}
  .qwrap.listen .qmain form{width:100%;margin-top:34px;display:flex;flex-direction:column;
                            align-items:center}
  .qwrap.qcenter .qmain form .field{width:100%;max-width:420px;margin-top:0}
  .qwrap.qcenter .qmain form .typebox,
  .qwrap.listen .qmain form .typebox{width:100%;max-width:420px;box-sizing:border-box;
                                     padding:12px 14px;font:inherit;font-size:17px;
                                     color:var(--text);background:var(--card);
                                     border:1px solid var(--line);border-radius:12px;
                                     text-align:center}
  .qwrap.qcenter .qmain form .opts,.qwrap.qcenter .qmain form .qopts,
  .qwrap.listen .qmain form .opts,.qwrap.listen .qmain form .qopts{width:100%;margin-top:0}
  .qwrap.listen .qmain .soundstage{margin-bottom:0}
  .qwrap.listen .qmain .soundstage + .meta{margin-top:34px}
  /* B 区不参与 A 区的垂直居中；按钮沿用既有 .primary 尺寸，只由容器保证底部与居中。 */
  .qwrap.qcenter .qfoot,.qwrap.listen .qfoot{flex:0 0 auto;width:100%;display:flex;
                                             flex-direction:column;align-items:stretch;
                                             gap:12px;padding:10px 0 14px;
                                             position:sticky;bottom:0;
                                             background:var(--bg)}
  .qwrap.qcenter .qfoot > a,.qwrap.listen .qfoot > a{display:block;width:100%}
  .qwrap.qcenter .qfoot button,.qwrap.listen .qfoot button{width:100%}
"""


def layout(title: str, body: str, active: str = "learn") -> str:
    """页面外壳：只有内容本身。

    第三版 Demo：**不再有底部一级导航**（首页 / 学习 / 进展 全部删除），
    页面之间只通过「当前内容 → 返回」连接，减少导航感、增加正在学习的感觉。
    active 参数保留仅为兼容既有调用，不再渲染任何导航。
    """
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, "
        "viewport-fit=cover\">\n"
        "<meta name=\"theme-color\" content=\"#F6F7F9\">\n"
        "<title>%s</title>\n<style>%s</style>\n</head>\n<body>\n%s\n</body>\n</html>\n"
        % (html.escape(title), STYLE + FORMAL_UI_CSS, body))


def topbar(title: str, back_href: str = "", back_label: str = "返回",
           right_html: str = "", sub: str = "") -> str:
    """页面顶部栏（第三版 Demo 统一）：左 返回图标 / 中 标题（真正居中）/ 右 预留。

    顶部只做这一件事：不堆章节信息、不放统计、不放进度。
    """
    if not right_html and back_href:     # P6-B-9：非首页统一提供「回到首页」入口（Demo 蓝本）
        right_html = '<a href="/" aria-label="回到首页">%s</a>' % icon("home")
    left = ('<a class="tb-back" href="%s" aria-label="%s">%s</a>'
            % (html.escape(back_href), html.escape(back_label), icon("back"))) if back_href else \
           '<span class="tb-back"></span>'
    mid = '<h1>%s</h1>' % html.escape(title)
    if sub:
        mid += '<span class="tb-sub">%s</span>' % html.escape(sub)
    return ('<header class="tb">%s<span class="tb-mid">%s</span>'
            '<span class="tb-right">%s</span></header>'
            % (left, mid, right_html))


def progress_bar(area: dict) -> str:
    """学习进度条（覆盖范围，不是掌握程度；不使用分数、等级或排名语言）。"""
    pct = max(0, min(100, int(area.get("percent") or 0)))
    return ('<div class="pg"><span class="lbl">%s</span>'
            '<span class="track"><span class="pgbar" style="width:%d%%"></span></span>'
            '<span class="num">%d / %d</span></div>'
            % (html.escape(area.get("label") or ""), pct,
               int(area.get("done") or 0), int(area.get("total") or 0)))


def attention_list(items) -> str:
    """「当前值得关注」（演示薄弱点）：回到教材的入口 + 教材依据。"""
    out = []
    for item in items:
        link = ('<div class="row" style="margin-top:8px"><a href="%s">'
                '<button class="secondary" type="button">回到教材</button></a></div>'
                % html.escape(item.get("link") or "/textbook"))
        out.append("""<div class="fitem">
    <div class="w">%s</div>
    <div class="body">%s</div>
    <div class="basis">%s · %s</div>
    %s
  </div>""" % (html.escape(item.get("text") or ""), html.escape(item.get("note") or ""),
                html.escape(item.get("last") or ""), html.escape(item.get("basis") or ""),
                link))
    return "\n  ".join(out)


def recent_studied_block(recent) -> str:
    """「最近学过」：真实数据；只陈述事实，不做任何评价（Demo V1 起沿用）。"""
    if not recent:
        return ('<p class="empty">还没有学过内容</p>'
                '<p class="empty-sub">先去教材里选一个词开始吧。</p>')
    rows = []
    for item in recent:
        lines = ['<div class="w">%s</div>' % html.escape(item.get("word") or "")]
        if item.get("phonetic"):
            lines.append('<div class="phon">%s</div>' % html.escape(item["phonetic"]))
        info = " ".join(x for x in [
            ("%s." % item["part_of_speech"]) if item.get("part_of_speech") else "",
            item.get("meaning") or ""] if x)
        if info:
            lines.append('<div class="body">%s</div>' % html.escape(info))
        lines.append("""<form method="post" action="/vocabulary/study">
      <input type="hidden" name="pick" value="%s">
      <div class="row" style="margin-top:8px"><button class="secondary" type="submit">再学一次</button></div>
    </form>""" % html.escape(item.get("key") or ""))
        rows.append('<div class="item">%s</div>' % "\n    ".join(lines))
    return "\n  ".join(rows)


#: P6-B-7：Demo 已验证的课程选择器交互（点开 → 点选 → 提交同一个表单；
#: 点击外部或 Esc 关闭）。业务逻辑不变，只是不再调用手机系统 picker。
HOME_PICKER_SCRIPT = """<script>
(function(){
  var box = document.querySelector('.lpick');
  if (!box) return;
  var form = box.closest ? box.closest('form') : null;
  var btn = box.querySelector('.lpbtn');
  var list = box.querySelector('.lplist');
  var sel = form ? form.querySelector('select.lpnative') : null;
  var unitInput = form ? form.querySelector('input[name="unit"]') : null;
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
    // P6-B-13：Unit → Section 两级同一个下拉；跨 Unit 选择时同步隐藏的 unit 字段
    var u = el.getAttribute('data-unit');
    if (unitInput && u) unitInput.value = u;
    sel.value = el.getAttribute('data-value');
    close();
    form.submit();
  });
  document.addEventListener('click', function(ev){
    if (list.hidden) return;
    if (!box.contains(ev.target)) close();
  });
  document.addEventListener('keydown', function(ev){
    if (ev.key === 'Escape' && !list.hidden){ close(); btn.focus(); }
  });
})();
</script>"""


def unit_center_page(ctx: dict) -> str:
    """单元中心（学情分析页）**二期·第一轮**：纯数据四块，AI 位先占位。

    ① 顶部一句话（成果）② AI 学情分析位（占位）③ 知识点掌握（中文名 + 程度词）
    ④ 两个按钮（补一补 / 练一练）

    **已砍掉**：课时进度块（与首页重复）、英文题型 key、`0%` 表格。
    """
    unit = ctx.get("unit") or {}
    points = ctx.get("points") or []
    not_practiced = ctx.get("not_practiced") or []
    entries = ctx.get("practice_entries") or []
    practiced = int(ctx.get("total_practiced") or 0)
    correct = int(ctx.get("total_correct") or 0)
    ready = bool(ctx.get("ready_for_ai"))
    need = int(ctx.get("min_practiced") or 10)

    # ① 顶部一句话
    if practiced > 0:
        head_line = "这个单元你练了 %d 道题，答对 %d 道。" % (practiced, correct)
    else:
        head_line = "这个单元还没有练习记录。"
    head = """<section class="softcard unitcard">
    <p class="um-book">%s</p>
    <p class="uc-big" id="zx-lead">%s</p>
  </section>""" % (html.escape(unit.get("title") or ""), html.escape(head_line))

    # ② AI 学情分析位（本轮占位；练够门槛时留"加载中"位，下一轮接桥）
    if ready:
        ai_body = ('<div id="zx-ai-panel" class="uc-ai-panel">'
                   '<p class="uc-empty uc-ai-wait">学习分析即将上线</p></div>')
    else:
        ai_body = ('<p class="uc-empty">再练几题就能看到分析啦'
                   '（已经练了 %d 题，练到 %d 题就有分析）。</p>' % (practiced, need))
    ai_block = """<section class="card uc-ai">
    <h2>学习分析</h2>
    %s
  </section>""" % ai_body

    # ③ 知识点掌握（只显示练过的；未练过进折叠区）
    if points:
        rows = []
        for k in points:
            lv = k.get("level") or ""
            cls = {"比较熟了": "done", "还不太熟": "doing"}.get(lv, "todo")
            rows.append('<div class="uc-kp"><div class="n">%s</div>'
                        '<div class="v">练了 %d 题 · 答对 %d 题'
                        '<span class="lv %s">%s</span></div></div>'
                        % (html.escape(k.get("name") or ""), int(k.get("practiced") or 0),
                           int(k.get("correct") or 0), html.escape(cls), html.escape(lv)))
        kp_body = "\n    ".join(rows)
    else:
        kp_body = '<p class="uc-empty">还没有练习记录。到练习里做几题，这里就会显示。</p>'

    # 未练过的：折叠区（默认折叠）
    fold = ""
    if not_practiced:
        chips = "".join('<span class="chip">%s</span>' % html.escape(n) for n in not_practiced)
        fold = """
    <details class="uc-fold">
      <summary>还有 %d 类还没练过</summary>
      <div class="chips">%s</div>
    </details>""" % (len(not_practiced), chips)
    kp_block = """<section class="card">
    <h2>知识点掌握</h2>
    %s%s
  </section>""" % (kp_body, fold)

    # ④ 两个按钮（取前 2 条；不依赖 AI）
    # slug 兼容两种 ctx 形状：页面自己 set 的 `unit_slug`，或 `unit` 里带的 `slug`。
    slug = ctx.get("unit_slug") or unit.get("slug") or ""
    # 二期·B：**分槽**渲染两个按钮（顺序由 demo.order_practice_entries 给出：
    #   第 1 位 = 补一补 = 专项入口里答对率最低的（专项都不足⇒退回综合）；
    #   第 2 位 = 练一练 = 其余里答对率最低的（**可含综合入口**）。
    ordered = demo.order_practice_entries(entries, points)
    btn_rows = []
    for idx, e in enumerate(ordered[:2]):
        text = "补一补" if idx == 0 else "练一练"
        href = "/unit/%s/p5/%s%s" % (
            slug, e.get("entry") or "",
            ("?mode=%s" % e["mode"]) if e.get("mode") else "")
        btn_rows.append('<a class="uc-btn" href="%s"><span class="t">%s</span>'
                        '<span class="d">%s</span></a>'
                        % (html.escape(href), html.escape(text),
                           html.escape(e.get("label") or "")))
    if btn_rows:
        btn_block = """<section class="card uc-practice">
    <h2>接着练</h2>
    <div class="uc-btns" id="zx-uc-btns">%s</div>
  </section>""" % "\n      ".join(btn_rows)
    else:
        # 没有可练入口时也留容器，AI 建议才放得进去
        btn_block = """<section class="card uc-practice">
    <h2>接着练</h2>
    <div class="uc-btns" id="zx-uc-btns"></div>
  </section>"""

    # 二期·C-1：把 **AI 学情分析的输入 JSON** 下发到页面（供 JS 后续调 analyze）。
    # 复用 J1 机制：`<script type="application/json">`（**不是可执行脚本**）+ json.dumps 转义，
    # 且把 `<`/`>` 转成 \u003c / \u003e（连 `</script>` 也无法闭合）。
    # **门槛**：练题数 < ANALYZE_MIN_PRACTICED 时**不下发**（页面显示"再练几题就能看到分析啦"）。
    analyze_script = ""
    if ready:
        payload = demo.analyze_payload(ctx)
        # D-2：slug **不再塞进 payload**（那会随输入 JSON 一起进 AI 的 prompt）；
        # 改为页面上的 `data-unit-slug` 属性，JS 从 DOM 读 —— prompt 里只有规格字段。
        analyze_script = ('<script id="zx-analyze-data" type="application/json">%s</script>'
                          % json.dumps(payload, ensure_ascii=False, sort_keys=True)
                          .replace("<", "\\u003c").replace(">", "\\u003e"))

    body = """%s
<main data-unit-slug="%s">
  %s
  %s
  %s
  %s
  %s
  <div class="foot">%s</div>
</main>%s%s""" % (header(unit.get("unit_code") or "单元", unit.get("title") or "单元中心",
                    back_href="/", back_label="回到首页"),
              html.escape(slug),
              head, ai_block, kp_block, btn_block, analyze_script,
              html.escape(PRODUCT_NAME),
              # 桥 JS 必须在页面 JS 之前注入（否则 window.ZxAi 为 undefined）
              P5_AI_BRIDGE_JS, UNIT_CENTER_AI_JS)
    return layout("单元中心 · %s" % (unit.get("unit_code") or PRODUCT_NAME), body)



def home_page(ctx: dict) -> str:
    """首页 =「今天学什么」（第三版 Demo）。

    固定结构：章节选择 → 功能入口列表（课文点读在最后）。
    * 没有底部一级导航（首页 / 学习 / 进展 已全部删除）；
    * 首页不再放 AI 随堂助教卡片，也没有「我的进展」入口：AI 只出现在
      真正有价值的地方（判题、跟读反馈、学习结果里的单元总结）；
    * 每个入口是独立圆角浅色块（图标 + 名称 + 右侧状态），无编号、无分隔线；
    * 听辨练习只有在真的有听辨资源时才出现，不做灰色禁用。
    """
    cr = ctx.get("classroom") or demo.classroom(demo.DEMO_UNIT_CODE, "A new start")
    units = ctx.get("units") or []
    # P6-B-13：首页「当前课时」= 教材真实目录 Unit → Section（全部真实 Section，不做题库过滤）
    catalog = ctx.get("catalog") or []
    cur_slug = (ctx.get("unit_slug") or "").strip()
    cur_key = (ctx.get("lesson_key") or "").strip()
    options, rows, labels, current = [], [], [], ""
    if catalog:
        # P6-B-13：**同一个下拉**里呈现 Unit（分组标题）→ Section（可选）；值仍是 section_key。
        # 当前生效项：URL/Cookie 已由 `_lessons_for()` 决定；没有有效项时按正式教材顺序
        # 取当前 Unit 的第一个真实 Section（没有当前 Unit 上下文时取全教材第一个真实 Section）。
        eff_unit = eff_sec = None
        for u in catalog:
            for s in u.get("sections") or []:
                if u.get("slug") == cur_slug and s["section_key"] == cur_key:
                    eff_unit, eff_sec = u, s
                    break
            if eff_sec:
                break
        if eff_sec is None and cur_slug:
            for u in catalog:
                secs = u.get("sections") or []
                if u.get("slug") == cur_slug and secs:
                    eff_unit, eff_sec = u, secs[0]
                    break
        if eff_sec is None:
            for u in catalog:
                secs = u.get("sections") or []
                if secs:
                    eff_unit, eff_sec = u, secs[0]
                    break
        if eff_unit and eff_sec:
            cur_slug = eff_unit.get("slug") or cur_slug
            cur_key = eff_sec["section_key"]
            current = "%s · %s" % (eff_unit.get("unit_code") or "",
                                   eff_sec.get("title") or cur_key)
        for u in catalog:
            group = "%s · %s" % (u.get("unit_code") or "", u.get("title") or "")
            options.append('<optgroup label="%s">' % html.escape(group))
            rows.append('<div class="lpgroup">%s</div>' % html.escape(group))
            for s in u.get("sections") or []:
                key = s["section_key"]
                name = s.get("title") or key
                on = (u.get("slug") == cur_slug and key == cur_key)
                options.append('<option value="%s"%s>%s</option>'
                               % (html.escape(key), " selected" if on else "",
                                  html.escape(name)))
                labels.append(name)
                rows.append('<button class="lpopt" type="button" data-value="%s" data-unit="%s"'
                            ' aria-selected="%s">%s</button>'
                            % (html.escape(key), html.escape(u.get("slug") or ""),
                               "true" if on else "false", html.escape(name)))
            options.append('</optgroup>')
        hidden_unit = ('<input type="hidden" name="unit" value="%s">'
                       % html.escape(cur_slug))
        picker = ("""<form method="get" action="/" class="picker">
      <div class="lpick">
        <button class="lpbtn" type="button" id="zx-unit" aria-haspopup="listbox"
                aria-expanded="false" aria-label="选择当前课时">%s</button>
        <a class="uc-entry" href="/unit/%s" aria-label="单元中心">%s</a>
        <div class="lplist" role="listbox" aria-label="课时选项" hidden>%s</div>"""
                  + hidden_unit +
                  """<select class="lpnative" name="lesson" tabindex="-1" aria-hidden="true">%s</select>
      </div>
      <noscript><button class="secondary" type="submit">切换</button></noscript>
    </form>""") % (html.escape(current), html.escape(cur_slug), icon("chart"), "".join(rows), "".join(options))
    else:
        for u in units:
            on = u["slug"] == ctx.get("unit_slug")
            label = "%s · %s" % (u["unit_code"] or "", u.get("title") or "")
            options.append('<option value="%s"%s>%s</option>'
                           % (html.escape(u["slug"]), " selected" if on else "",
                              html.escape(label)))
            labels.append(label)
            if on:
                current = label
            rows.append('<button class="lpopt" type="button" data-value="%s" aria-selected="%s">'
                        '%s</button>'
                        % (html.escape(u["slug"]), "true" if on else "false", html.escape(label)))
        if not current and labels:
            current = labels[0]
        picker = ("""<form method="get" action="/" class="picker">
      <div class="lpick">
        <button class="lpbtn" type="button" id="zx-unit" aria-haspopup="listbox"
                aria-expanded="false" aria-label="选择当前章节">%s</button>
        <div class="lplist" role="listbox" aria-label="章节选项" hidden>%s</div>
        <select class="lpnative" name="unit" tabindex="-1" aria-hidden="true">%s</select>
      </div>
      <noscript><button class="secondary" type="submit">切换</button></noscript>
    </form>""" % (html.escape(current), "".join(rows), "".join(options))) if units else ""
    chapter_block = """<section class="softcard unitcard">
    <p class="um-book">七年级英语上册</p>
    %s
  </section>""" % (picker,)

    rows = []
    for e in ctx.get("entries") or []:
        rows.append(
            '<a class="entryrow %s%s" href="%s"><span class="ico">%s</span>'
            '<span class="nm">%s</span><span class="st">%s</span></a>'
            % (html.escape(e["cls"]), " fin" if e.get("done") else "",
               html.escape(e["href"]), icon(e["icon"]),
               html.escape(e["label"]), html.escape(e["status"])))
    entries_block = "\n    ".join(rows)

    body = """%s
<main>
  %s
  %s
  <div class="foot">%s</div>
 </main>%s""" % (topbar(PRODUCT_NAME), chapter_block, entries_block,
                 html.escape(PRODUCT_NAME), HOME_PICKER_SCRIPT)
    return layout(PRODUCT_NAME, body, active="home")


def parent_progress_row(row: dict) -> str:
    """「我的进展」的一行：维度 + 数值 + 一句话解释（每类不同低饱和色，无线条）。"""
    hue = {"text": "#2F6BE0", "grammar": "#1E8A5F", "speaking": "#B5761A"
           }.get(row.get("key"), "#2F6BE0")
    pct = row.get("percent")
    if pct is None:
        bar = ""
    else:
        bar = ('<span class="tr"><i style="width:%d%%"></i></span>' % int(pct))
    return """<div class="dim" style="--hue:%s">
    <div class="top"><span class="lb">%s</span><span class="vl">%s</span></div>
    %s
    <p class="nt">%s</p>
  </div>""" % (hue, html.escape(row["label"]), html.escape(row["value"]), bar,
               html.escape(row["note"]))


def ai_card(ai: dict, unit_code: str = "", unit_title: str = "", extra_line: str = "") -> str:
    """AI 随堂助教卡（Demo V1.2：最多 3 项、不分类、不堆信息）。

    ai 由 demo.chapter_ai() 推导：
      * 没有学习证据：只告诉孩子这一章最值得先学的几个知识点，不评价孩子；
      * 已有学习行为：才说明"现在学得怎么样"，最多仍然只显示 3 项。
    """
    lines = "".join('<p>%s</p>' % html.escape(x) for x in ai.get("diagnosis") or [])
    items = "".join('<li><span class="fw">%s</span><span class="fp">%s</span></li>'
                    % (html.escape(i["text"]), html.escape(i.get("note") or ""))
                    for i in (ai.get("items") or [])[:3])
    title = ('<p class="ai-sub">%s</p>' % html.escape(ai["list_title"])
             ) if ai.get("list_title") and items else ""
    head = ('<p class="ai-unit">%s</p>'
            % html.escape(" ".join(x for x in [unit_code, unit_title] if x).strip())
            ) if unit_code else ""
    extra = ('<p class="ai-line">%s</p>' % html.escape(extra_line)) if extra_line else ""
    return """<section class="ai">
    <h2>AI 随堂助教</h2>
    %s
    %s
    %s
    %s
    %s
    <p class="demo-note"><span class="demo">%s</span> %s</p>
  </section>""" % (head, lines, title, ('<ul class="focuslist">%s</ul>' % items) if items else "",
                    extra,
                    html.escape(demo.DEMO_LABEL), html.escape(ai.get("note") or ""))


# ---------------------------------------------------------------------------
# Demo V1.2：极简学习页（单词跟读 / 句子跟读 / 听音辨词）
# ---------------------------------------------------------------------------

#: 录音反馈只看“这次录音本身”，不是发音评分（见 V1.2 §二十五）
REC_TIP = "这里的反馈只看这次录音本身（有没有声音、清不清楚），不是发音评分。"


def step_bar(index: int = 1, total: int = 1) -> str:
    """连续学习/练习页面的**统一进度组件**：━━━ N / TOTAL。

    单独一个组件、一处实现、所有页面共用（单词跟读 / 句子跟读 / 听音辨词 /
    短语练习 / 阅读练习 / 听力练习）。细线 + 题号，不用圆环、不用百分比、
    不用圆点分页、不用大号进度块；没有题目序列的自由浏览页（教材点读）不使用。
    """
    total = max(int(total or 1), 1)
    index = min(max(int(index or 1), 1), total)
    return ('<div class="steps" data-steps="%d">'
            '<span class="bar"><i class="js-step" style="width:%.1f%%"></i></span>'
            '<span class="cnt js-step-cnt">%d / %d</span></div>'
            % (total, 100.0 * index / total, index, total))


READ_JS = """<script>
(function(){
  var A = new Audio(); A.preload = 'auto';
  var stopAt = null, activeKey = null;
  function mark(key, on){
    var nodes = document.querySelectorAll('.pdfpage .blk[data-block="' + key + '"]');
    for(var i = 0; i < nodes.length; i++){
      var el = nodes[i];
      if(on){ el.classList.add('playing'); } else { el.classList.remove('playing'); }
    }
  }
  function clear(){ if(activeKey){ mark(activeKey, false); activeKey = null; } }
  A.addEventListener('timeupdate', function(){
    if(stopAt !== null && A.currentTime >= stopAt){ A.pause(); stopAt = null; clear(); }
  });
  A.addEventListener('ended', clear);
  function play(url, begin, end){
    if(!url){ return; }
    if(A.getAttribute('data-src') !== url){ A.setAttribute('data-src', url); A.src = url; }
    stopAt = (end === null || end === undefined) ? null : end / 1000;
    try{ A.currentTime = (begin || 0) / 1000; }catch(e){}
    var pr = A.play(); if(pr && pr.catch){ pr.catch(function(){}); }
  }
  document.addEventListener('click', function(ev){
    /* 自然文本块：一个块 = 一个 data-block（内部可能由 1~N 个矩形组成） */
    var h = ev.target && ev.target.closest ? ev.target.closest('.pdfpage .blk') : null;
    if(h){
      var key = h.getAttribute('data-block');
      if(key === activeKey && !A.paused){ A.pause(); clear(); return; }
      clear(); activeKey = key; mark(key, true);
      play(h.getAttribute('data-audio'), parseInt(h.getAttribute('data-start') || '0', 10),
           parseInt(h.getAttribute('data-end') || '0', 10));
      return;
    }
    /* 整段活动录音（不与页面文字一一对应，单独标注） */
    var row = ev.target && ev.target.closest ? ev.target.closest('[data-play-src]') : null;
    if(row){
      ev.preventDefault();
      clear();
      play(row.getAttribute('data-play-src'), 0, null);
    }
  });
  /* 彩页可以放大查看：热点跟着图片一起缩放（都是相对页面的百分比定位） */
  document.addEventListener('click', function(ev){
    var b = ev.target && ev.target.closest ? ev.target.closest('[data-act="zoom"]') : null;
    if(!b){ return; }
    var pg = document.getElementById('zx-page');
    if(!pg){ return; }
    var on = pg.classList.toggle('zoom');
    b.textContent = on ? '看整页' : '放大看教材';
    if(on){ pg.scrollIntoView({behavior:'smooth', block:'start'}); }
  });
})();
</script>"""

def not_found_page(path: str = "") -> str:
    body = """<header class="top"><h1>%s</h1></header>
<main>
  <section class="card">
    <h2>没有找到这个页面</h2>
    <p class="empty">你要找的地方暂时不存在。</p>
    <div class="row"><a href="/"><button class="secondary" type="button">回到首页</button></a></div>
  </section>
</main>""" % html.escape(PRODUCT_NAME)
    return layout(PRODUCT_NAME, body, active="")


# ---------------------------------------------------------------------------
# P1-12-C3-C2 教材导航：教材中心 → Unit → 资源列表
# ---------------------------------------------------------------------------

def header(title: str, subtitle: str = None, back_href: str = None,
           back_label: str = "返回") -> str:
    """页面顶部（第三版 Demo）：与所有页面共用同一套「返回图标 + 居中标题」。

    subtitle 仍然保留给旧页面，作为标题下的一行小字，不影响标题居中。
    """
    return topbar(title, back_href or "", back_label, sub=subtitle or "")

#: 教材中心里每个单元的自然状态（不夸大能力，也不做死按钮）
_UNIT_NOTES = {
    "Unit 1": ("演示主单元", "教材原文、词汇、句子、跟读、练习和结果都可以打开"),
    "Starter": ("可以进入", "教材原文和词汇可以打开"),
    "Appendix": ("附录", "词汇表与句型汇总"),
}
_UNIT_NOTE_DEFAULT = ("教材已准备", "教材原文、词汇和练习都可以打开")


def _unit_note(code: str):
    return _UNIT_NOTES.get(code or "", _UNIT_NOTE_DEFAULT)


def textbook_page(ctx: dict, active: str = "learn") -> str:
    """教材中心（学习页）：教材信息 + 真实 Unit 导航 + 每单元的自然状态。"""
    tb = ctx.get("textbook") or {}
    units = ctx.get("units") or []
    rows = []
    for unit in units:
        pages = ""
        if unit.get("textbook_page_start") and unit.get("textbook_page_end"):
            pages = "教材第 %s–%s 页" % (unit["textbook_page_start"], unit["textbook_page_end"])
        state, note = _unit_note(unit.get("unit_code"))
        rows.append("""<a class="unitrow" href="/?unit=%s">
      <span class="code">%s</span>
      <span class="ttl">%s</span>
      <span class="pg">%s</span>
      <span class="pg">%s · %s</span>
    </a>""" % (html.escape(unit["slug"]), html.escape(unit["unit_code"] or ""),
               html.escape(unit["title"] or unit["unit_code"] or ""), html.escape(pages),
               html.escape(state), html.escape(note)))
    body = """%s
<main>
  <section class="card">
    <h2>我的教材</h2>
    <p class="textbook-name">%s</p>
    <p class="meta">%s%s</p>
    <div class="hint">下面按教材顺序排列；点一个单元进去看看。</div>
  </section>
  %s
  <div class="foot">%s</div>
</main>""" % (header("教材中心", "选择要学习的单元", back_href="/", back_label="首页"),
              html.escape(tb.get("title") or "教材信息暂不可用"),
              html.escape(tb.get("publisher") or ""),
              (" · " + html.escape(tb.get("curriculum_standard") or ""))
              if tb.get("curriculum_standard") else "",
              "\n  ".join(rows), html.escape(PRODUCT_NAME))
    return layout("教材中心 · %s" % PRODUCT_NAME, body, active=active)


def resource_types_page(ctx: dict) -> str:
    """资源列表入口（未指定类型时）：让孩子自己选要看哪一类。"""
    unit = ctx["unit"]
    cards = []
    for kind, label in ctx["kinds"]:
        count = (ctx.get("counts") or {}).get(kind, 0)
        cards.append("""<a class="type" href="/unit/%s/resources/%s">
      <span class="n">%s</span><span class="c">%s</span>
    </a>""" % (html.escape(unit["slug"]), html.escape(kind), html.escape(label),
               html.escape("%d 个" % count if count else "暂无")))
    body = """%s
<main>
  <section class="card">
    <h2>%s</h2>
    <p class="meta">%s</p>
  </section>
  %s
  <div class="foot">%s</div>
</main>""" % (header("选择内容类型", unit["unit_code"], back_href="/",
                    back_label="回到首页"),
              html.escape(unit["title"] or unit["unit_code"] or ""),
              html.escape("请选择要浏览的内容类型"), "\n  ".join(cards), html.escape(PRODUCT_NAME))
    return layout("选择内容类型 · %s" % PRODUCT_NAME, body)


def resource_list_page(ctx: dict) -> str:
    """资源列表（浏览用）：只展示真实存在的字段。"""
    unit, items = ctx["unit"], ctx["items"]
    is_vocabulary = ctx.get("kind") == "vocabulary"
    rows = []
    for item in items:
        # P2-1-C1（C1-01）：教材黑体重点词加粗；白体词普通字重（不加任何解释性标签）
        weight = ""
        if is_vocabulary:
            weight = " core" if item.get("can_study") else " plain"
        # P2-2：每个单词旁边一个传统小扬声器（只对有逐词音频的词显示）
        spk = speaker(item.get("audio_url"), "单词发音") if item.get("audio_url") else ""
        lines = ['<div class="wrow"><div class="w%s">%s</div>%s</div>'
                 % (weight, html.escape(item["text"] or ""), spk)]
        if item.get("phonetic"):
            lines.append('<div class="phon">%s</div>' % html.escape(item["phonetic"]))
        body_line = " ".join(x for x in [
            ("%s." % item["part_of_speech"]) if item.get("part_of_speech") else "",
            item.get("meaning") or ""] if x)
        if body_line:
            lines.append('<div class="body">%s</div>' % html.escape(body_line))
        if item.get("status_label"):
            # 状态是"信息"，不是"评价"（P1-13-C1 §九）
            lines.append('<div class="meta">状态：%s</div>' % html.escape(item["status_label"]))
        if item.get("can_study") and item.get("key"):
            lines.append("""<form method="post" action="/vocabulary/study">
      <input type="hidden" name="pick" value="%s">
      <div class="row" style="margin-top:8px"><button class="secondary" type="submit">学习这个词</button></div>
    </form>""" % html.escape(item["key"]))
        rows.append('<div class="item">%s</div>' % "\n    ".join(lines))
    if rows:
        content = "\n  ".join(rows)
        note = ""
    else:
        content = '<div class="card"><p class="empty">这个单元暂时没有这类内容。</p></div>'
        note = ""
    if ctx.get("unmapped_count"):
        note += ('<div class="hint">另有 %d 条内容暂时无法归入单元，未在此列出。</div>'
                 % ctx["unmapped_count"])
    body = """%s
<main>
  <section class="card">
    <h2>%s · %s</h2>
    <p class="meta">%s</p>
    <div class="hint">按教材出现顺序排列。%s</div>
  </section>
  %s
  %s
  <div class="foot">%s</div>
</main>""" % (header(ctx["label"], "%s · %s" % (unit["unit_code"] or "", unit["title"] or ""),
                    back_href="/", back_label="回到首页"),
              html.escape(unit["unit_code"] or ""), html.escape(ctx["label"]),
              html.escape("共 %d 个" % len(items)),
              "标有「学习这个词」的是教材重点词，可以点进去学。" if ctx.get("has_study")
              else "", content, note, html.escape(PRODUCT_NAME))
    return layout("%s · %s · %s" % (ctx["label"], unit["unit_code"], PRODUCT_NAME), body)


def error_page(title: str, message: str, back_href: str = "/",
               back_label: str = "回到教材中心") -> str:
    """自然语言错误页（不暴露任何内部技术信息）。"""
    body = """%s
<main>
  <section class="card">
    <h2>%s</h2>
    <p class="empty">%s</p>
    <div class="row"><a href="%s"><button class="secondary" type="button">%s</button></a></div>
  </section>
</main>""" % (header(title, None, back_href, back_label), html.escape(title),
              html.escape(message), html.escape(back_href), html.escape(back_label))
    return layout(title, body, active="")


def speaker(url: str, label: str = "单词发音", kind: str = "word") -> str:
    """音频按钮（纯 CSS 状态，不依赖 JavaScript）。

    kind="word"     → 🔊  Vocabulary 单词音频
    kind="textbook" → 🎧  教材练习官方音频（两种语义不混用）

    实现：原生 <audio controls> 保持真实可点击但 opacity:0（不显示系统播放三角），
    上层用 CSS 画扬声器/耳机图标与 3 条声波柱；播放中由 `audio:playing` 触发循环动画，
    播放结束自动恢复静止。点击区域 40×40（移动端易触控），图标本体 17px。
    """
    if not url:
        return ""
    ico = "🎧" if kind == "textbook" else "🔊"
    return ('<span class="spk %s"><audio controls preload="none" src="%s" aria-label="%s">'
            '</audio><span class="spk-ico" data-ico="%s" aria-hidden="true">'
            '<i></i><i></i><i></i></span></span>'
            % (html.escape(kind), html.escape(url), html.escape(label), ico))


# ---------------------------------------------------------------------------
# P2-2 教材练习：Unit → 练习列表 → 练习 → 结果
# ---------------------------------------------------------------------------

SECTION_LABELS = {"GET_READY": "Get ready", "KNOW_YOUR_SCHOOL": "Know your school",
                  "GET_TO_KNOW_EACH_OTHER": "Get to know each other",
                  "STARTING_OUT": "Starting out", "UNDERSTANDING_IDEAS": "Understanding ideas",
                  "DEVELOPING_IDEAS": "Developing ideas",
                  "READING_FOR_WRITING": "Reading for writing",
                  "PRESENTING_IDEAS": "Presenting ideas", "REFLECTION": "Reflection"}


def exercise_list_page(ctx: dict) -> str:
    """教材练习列表：教材页码 + 练习号 + 教材指令 + 是否有官方音频。"""
    unit, items = ctx["unit"], ctx["exercises"]
    rows = []
    for e in items:
        badge = e.get("question_label") or ctx["type_labels"].get(e["type"], "练习")
        audio = ('<div class="exaudio">🎧 有教材官方录音</div>' if e.get("audio_id")
                 else ('<div class="exaudio">这一页没有配套录音</div>' if not e["audio_required"]
                       else ""))
        rows.append("""<a class="ex" href="/exercise/%s">
      <div class="exhead"><span class="badge">%s</span>
        <span class="exno">教材第 %s 页 · 练习 %s</span></div>
      <div class="exins">%s</div>
      %s
    </a>""" % (html.escape(e["key"]), html.escape(badge), e["textbook_page"],
               html.escape(str(e["exercise_no"])), html.escape(e["instruction"][:96]), audio))
    content = "\n  ".join(rows) if rows else \
        '<div class="card"><p class="empty">这个单元暂时没有可打开的教材练习。</p></div>'
    body = """%s
<main>
  <section class="card">
    <h2>教材练习</h2>
    <p class="meta">%s · %s · 共 %d 个</p>
    <div class="hint">这些练习都来自教材本身；点开一个就能看到教材上的要求，有录音的可以当场听。</div>
  </section>
  %s
  <div class="foot">%s</div>
</main>""" % (header("教材练习", "%s · %s" % (unit["unit_code"], unit["title"]),
                            back_href="/unit/%s" % (ctx["unit"]["slug"]),
                            back_label="返回单元中心"),
              html.escape(unit["unit_code"] or ""), html.escape(unit["title"] or ""), len(items),
              content, html.escape(PRODUCT_NAME))
    return layout("教材练习 · %s" % PRODUCT_NAME, body)


def _self_check_block() -> str:
    """孩子的自我判断（教材未提供答案来源时不伪造正误）。"""
    return """<div class="choices">
      <button class="secondary" type="submit" name="self_check" value="done">我完成了这次练习</button>
      <button class="secondary" type="submit" name="self_check" value="partial">还想再看一遍</button>
    </div>"""


def _textbook_block(tb: dict) -> str:
    """教材原题结构：题型 + 教材项目 / 选项 / 空格（只用教材已有信息）。"""
    if not tb:
        return ""
    parts = ['<div class="tbq"><span class="badge">教材原题 · %s</span>'
             % html.escape(tb.get("question_label") or "练习")]
    items = tb.get("items") or []
    options = tb.get("options") or []
    if items:
        parts.append('<ul class="tbitems">%s</ul>'
                     % "".join("<li>%s</li>" % html.escape(x) for x in items[:14]))
    if options:
        parts.append('<ul class="tbitems">%s</ul>'
                     % "".join("<li>%s. %s</li>" % (html.escape(o["label"]),
                                                    html.escape(o["text"]))
                               for o in options[:8]))
    if not items and not options and tb.get("blanks"):
        parts.append('<div class="hint">教材这一题有 %d 个空。</div>' % tb["blanks"])
    parts.append("</div>")
    return "".join(parts)


def _legacy_exercise_page(ctx: dict) -> str:
    """单个教材练习：教材要求 + 官方录音 + 作答。"""
    e, q = ctx["exercise"], ctx["questions"]
    tb = q.get("textbook") or {}
    head = """<section class="card">
    <h2>%s · 练习 %s</h2>
    <p class="meta">教材第 %s 页 ｜ %s</p>
    <div class="exins">%s</div>
    %s
    %s
  </section>""" % (html.escape(SECTION_LABELS.get(e["section"], e["section"])),
                    html.escape(str(e["exercise_no"])), e["textbook_page"],
                    html.escape(ctx["type_labels"].get(e["type"], "练习")),
                    html.escape(e["instruction"]),
                    _textbook_block(tb),
                    ('<div class="audio-inline"><div class="audiolabel">教材官方录音</div>%s</div>'
                     % speaker(ctx["audio_url"], "教材官方录音", "textbook"))
                    if ctx.get("audio_url") else "")

    if q["kind"] == "spelling":
        rows = []
        for item in q["questions"]:
            rows.append("""<div class="question">
      <div class="qtext">%s. %s</div>
      <div class="field"><input name="q%d" autocomplete="off" spellcheck="false"
           placeholder="在这里写出单词"></div>
    </div>""" % (item["no"], html.escape(item["meaning"]), item["no"]))
        form_body = "".join(rows)
    elif q["kind"] == "short_answer":
        rows = []
        for item in q["questions"]:
            rows.append("""<div class="question">
      <div class="qtext">%s. %s</div>
      <div class="field"><textarea name="q%d" rows="3"
           placeholder="用英语写一写你的回答"></textarea></div>
    </div>""" % (item["no"], html.escape(item["text"]), item["no"]))
        form_body = "".join(rows) + _self_check_block()
    elif q["kind"] == "choice":
        rows = []
        for item in q["questions"]:
            opts = "".join(
                """<label class="opt"><input type="radio" name="q%d" value="%s">
      <span>%s. %s</span></label>""" % (item["no"], html.escape(o["label"]),
                                         html.escape(o["label"]), html.escape(o["text"]))
                for o in item["options"])
            rows.append('<div class="question">%s</div>' % opts)
        form_body = "".join(rows) + _self_check_block()
    elif q["kind"] == "fill":
        rows = []
        for item in q["questions"]:
            rows.append("""<div class="question">
      <div class="qtext">空 %s</div>
      <div class="field"><input name="q%d" autocomplete="off" spellcheck="false"
           placeholder="填教材里的答案"></div>
    </div>""" % (item["no"], item["no"]))
        form_body = "".join(rows) + _self_check_block()
    elif q["kind"] == "match":
        rows = []
        for idx, item in enumerate(q.get("items") or [], start=1):
            rows.append("""<div class="question">
      <div class="qtext">%s. %s</div>
      <div class="field"><input name="m%d" autocomplete="off" spellcheck="false"
           placeholder="在教材上配对后，把答案写在这里"></div>
    </div>""" % (idx, html.escape(item), idx))
        form_body = "".join(rows) + _self_check_block()
    else:
        form_body = _self_check_block()

    submit = """<div class="row"><button class="primary" type="submit">提交</button></div>""" \
        if q["kind"] in ("spelling", "short_answer") else ""
    name_field = ("""<div class="field"><label for="name">你的名字</label>
      <input id="name" name="name" autocomplete="off" placeholder="第一次使用请写上名字"
             required></div>
    <div class="hint">名字只用来记住你自己的练习记录，不需要账号和密码。</div>"""
                  if ctx.get("ask_name") else "")
    body = """%s
<main>
  %s
  <section class="card">
    <h2>%s</h2>
    <p class="meta">%s</p>
    <form method="post" action="/exercise/%s/submit">
      %s
      %s
      %s
    </form>
  </section>
  <div class="foot">%s</div>
</main>""" % (header("教材练习", "%s · %s" % (e["unit"], e["instruction"][:24]),
                    back_href="/unit/%s/exercises" % ctx["unit"]["slug"],
                    back_label="返回练习列表"),
              head,
              "自己作答" if q["kind"] != "self_check" else "这次练习做得怎么样？",
              html.escape(q["note"]), html.escape(ctx["key"]), name_field, form_body, submit,
              html.escape(PRODUCT_NAME))
    return layout("教材练习 · %s" % PRODUCT_NAME, body)


def exercise_name_error(key: str) -> str:
    """练习提交时缺少名字：给自然语言提示，回到练习本身。"""
    body = """%s
<main>
  <section class="card">
    <h2>请先写上你的名字</h2>
    <p class="empty">名字只用来记住你自己的练习记录。</p>
    <div class="row"><a href="/exercise/%s">
      <button class="secondary" type="button">回到练习</button></a></div>
  </section>
</main>""" % (header("教材练习", None, "/textbook", "回到教材中心"), html.escape(key))
    return layout("教材练习 · %s" % PRODUCT_NAME, body, active="learn")


def exercise_result_page(ctx: dict) -> str:
    """练习结果：真实结果 + 可以再看看的地方 + 孩子自己的下一步。"""
    e, g = ctx["exercise"], ctx["grade"]
    blocks = []
    if g["kind"] == "spelling":
        items = []
        for d in g["details"]:
            mark = "✓" if d["correct"] else "再看一眼"
            items.append("<li>%s — 你写的：%s ｜ 教材词表：%s（%s）</li>"
                         % (html.escape(d["meaning"]), html.escape(d["given"] or "（空）"),
                            html.escape(d["answer"]), mark))
        blocks.append('<div class="feedback"><div class="j">%s</div><ul>%s</ul></div>'
                      % (html.escape(g["summary"]), "".join(items)))
    elif g["kind"] == "short_answer":
        for d in g["details"]:
            a = d["analysis"]
            hints = "".join("<li>%s</li>" % html.escape(h) for h in a.get("hints", []))
            blocks.append("""<div class="feedback">
      <div class="qtext">%s</div>
      <p class="meta">你的回答：%s</p>
      <div class="j">%s</div>
      %s
      <div class="hint">你可以自己再改一改，然后再看一遍。</div>
    </div>""" % (html.escape(d["question"]), html.escape(d["given"] or "（没有作答）"),
                 html.escape(a.get("judgement") or ""),
                 ("<ul>%s</ul>" % hints) if hints else ""))
    elif g["kind"] in ("choice", "fill", "match"):
        items = []
        for d in g["details"]:
            label = d.get("item") or ("第 %s 题" % d["no"])
            items.append("<li>%s — 你写的：%s</li>"
                         % (html.escape(label), html.escape(d.get("given") or "（空）")))
        blocks.append('<div class="feedback"><div class="j">%s</div><ul>%s</ul>'
                      '<div class="hint">教材没有提供可核对的答案，所以这里不判对错；'
                      '你可以对照教材自己核对。</div></div>'
                      % (html.escape(g.get("label") or g.get("summary") or ""),
                         "".join(items)))
    else:
        blocks.append('<div class="feedback"><div class="j">%s</div></div>'
                      % html.escape(g.get("label") or g.get("summary") or ""))
    body = """%s
<main>
  <section class="card">
    <h2>这次练习</h2>
    <p class="meta">%s · 练习 %s · 教材第 %s 页</p>
    <div class="exins">%s</div>
  </section>
  <section class="card">
    <h2>结果</h2>
    %s
  </section>
  <div class="row">
    <a href="/exercise/%s"><button class="secondary" type="button">再做一次</button></a>
    <a href="/unit/%s/exercises"><button class="secondary" type="button">回到练习列表</button></a>
  </div>
  <div class="hint">接下来做什么，由你自己决定。</div>
  <div class="foot">%s</div>
</main>""" % (header("练习结果", "%s · %s" % (e["unit"], e["instruction"][:20]),
                    back_href="/unit/%s/exercises" % ctx["unit"]["slug"],
                    back_label="返回练习列表"),
              html.escape(SECTION_LABELS.get(e["section"], e["section"])),
              html.escape(str(e["exercise_no"])), e["textbook_page"],
              html.escape(e["instruction"]),
              "\n  ".join(blocks), html.escape(ctx["key"]), html.escape(ctx["unit"]["slug"]),
              html.escape(PRODUCT_NAME))
    return layout("练习结果 · %s" % PRODUCT_NAME, body)


# ---------------------------------------------------------------------------
# P1-12-C3-C3 正式 Vocabulary 学习闭环（Study → Recall → Practice → Result）
# ---------------------------------------------------------------------------

def first_use_page(action: str, item_id: str, word: str, back_href: str,
                   error: str = None) -> str:
    """首次使用（最小身份）：只问名字，不建立账号体系。"""
    err = '<div class="err">%s</div>' % html.escape(error) if error else ""
    body = """%s
<main>
  <section class="card">
    <h2>请先写上你的名字</h2>
    <p class="meta">这个名字只用来记住你的学习记录，不需要账号和密码。</p>
    %s
    <form method="post" action="%s" autocomplete="off">
      <input type="hidden" name="item_id" value="%s">
      <div class="field"><label for="name">你的名字</label>
        <input id="name" name="name" placeholder="请输入名字" required></div>
      <div class="row"><button class="primary" type="submit">开始学习</button></div>
    </form>
    <div class="hint">要学的是：%s</div>
  </section>
</main>""" % (header("开始学习", None, back_href, "返回"),
              err, html.escape(action), html.escape(item_id), html.escape(word or ""))
    return layout("开始学习 · %s" % PRODUCT_NAME, body, active="")


def study_page(ctx: dict) -> str:
    """07 Vocabulary Study：单词是页面视觉中心。"""
    lines = ['<div class="word">%s</div>' % html.escape(ctx["word"] or "")]
    if ctx.get("phonetic"):
        lines.append('<div class="word-phon">%s</div>' % html.escape(ctx["phonetic"]))
    # P2-1-C1（C1-06）：发音——孩子主动点击播放（不自动播放、不预加载）
    if ctx.get("word_audio_url"):
        # P2-3：只保留扬声器按钮（去掉"发音"标签与说明文字）
        lines.append('<div class="audio-inline">%s</div>'
                     % speaker(ctx["word_audio_url"], "单词发音"))
    if ctx.get("part_of_speech"):
        lines.append('<div class="word-pos">%s.</div>' % html.escape(ctx["part_of_speech"]))
    if ctx.get("meaning"):
        lines.append('<div class="word-mean">%s</div>' % html.escape(ctx["meaning"]))
    # C4-06：教材来源拆成两行（出自哪个单元 / 词表栏目与词表页）
    source_lines = []
    if ctx.get("source_unit_label"):
        source_lines.append('<div class="meta">出自：%s</div>'
                            % html.escape(ctx["source_unit_label"]))
    if ctx.get("source_list_label"):
        source_lines.append('<div class="meta">词表：%s</div>'
                            % html.escape(ctx["source_list_label"]))
    if not source_lines:
        source_lines.append('<div class="meta">%s</div>'
                            % html.escape(ctx.get("source_text") or "教材信息暂不可用"))
    body = """%s
<main>
  <section class="card center">
    %s
  </section>
  <form method="post" action="/vocabulary/study/done">
    <input type="hidden" name="session_id" value="%s">
    <input type="hidden" name="pick" value="%s">
    <input type="hidden" name="learner_id" value="%s">
    <div class="row"><button class="primary" type="submit">我看完了</button></div>
  </form>
  <section class="card">
    <h2>教材来源</h2>
    %s
  </section>
  <div class="hint">看完之后，自己回忆一下这个词的意思。</div>
</main>""" % (header("词汇", "词汇", ctx.get("back_href") or "/textbook", "返回"),
              "\n    ".join(lines),
              html.escape(ctx["session_id"]), html.escape(ctx["key"]),
              html.escape(ctx["learner_id"]), "\n    ".join(source_lines))
    return layout("%s · %s" % (ctx["word"], PRODUCT_NAME), body)


def recall_page(ctx: dict) -> str:
    """08 Vocabulary Recall：默认隐藏意思；三个等权选择。"""
    lines = ['<div class="word">%s</div>' % html.escape(ctx["word"] or "")]
    if ctx.get("phonetic"):
        lines.append('<div class="word-phon">%s</div>' % html.escape(ctx["phonetic"]))
    if ctx.get("part_of_speech"):
        lines.append('<div class="word-pos">%s.</div>' % html.escape(ctx["part_of_speech"]))
    if ctx.get("reveal") and ctx.get("meaning"):
        lines.append('<div class="word-mean">%s</div>' % html.escape(ctx["meaning"]))
        meaning_block = ('<div class="hidden-mean">教材上的意思已经显示出来了</div>')
    elif ctx.get("reveal"):
        meaning_block = ('<div class="hidden-mean">教材里没有给出这个词的中文意思</div>')
    else:
        meaning_block = """<form method="post" action="/vocabulary/recall/reveal">
      <input type="hidden" name="session_id" value="%s">
      <input type="hidden" name="pick" value="%s">
      <input type="hidden" name="learner_id" value="%s">
      <div class="hidden-mean">意思暂时隐藏，先自己想一想。
        <div class="row" style="justify-content:center">
          <button class="secondary" type="submit">显示意思</button></div>
      </div>
    </form>""" % (html.escape(ctx["session_id"]), html.escape(ctx["key"]),
                   html.escape(ctx["learner_id"]))
    choices = "\n      ".join(
        '<button class="secondary" type="submit" name="choice" value="%s">%s</button>'
        % (html.escape(key), html.escape(label)) for key, label, _ in ctx["choices"])
    body = """%s
<main>
  <section class="card center">
    %s
    <div style="margin-top:16px">%s</div>
  </section>
  <div class="center">你现在回忆得怎么样？</div>
  <form method="post" action="/vocabulary/practice">
    <input type="hidden" name="session_id" value="%s">
    <input type="hidden" name="pick" value="%s">
    <input type="hidden" name="learner_id" value="%s">
    <div class="choices">
      %s
    </div>
  </form>
  <div class="hint">这是你自己的判断，没有对错；「忘了」只是下次再看一眼的线索。</div>
</main>""" % (header("回忆一下", None, ctx.get("back_href") or "/textbook",
                    ctx.get("back_label") or "返回"),
              "\n    ".join(lines), meaning_block, html.escape(ctx["session_id"]),
              html.escape(ctx["key"]), html.escape(ctx["learner_id"]), choices)
    return layout("回忆一下 · %s" % PRODUCT_NAME, body)


def result_page(ctx: dict) -> str:
    """10 Result：这次学了什么 + 孩子自己的判断 + 下一步选择。"""
    lines = ['<div class="word">%s</div>' % html.escape(ctx["word"] or "")]
    if ctx.get("phonetic"):
        lines.append('<div class="word-phon">%s</div>' % html.escape(ctx["phonetic"]))
    if ctx.get("part_of_speech"):
        lines.append('<div class="word-pos">%s.</div>' % html.escape(ctx["part_of_speech"]))
    if ctx.get("meaning"):
        lines.append('<div class="word-mean">%s</div>' % html.escape(ctx["meaning"]))
    recall = ctx.get("recall_label")
    recall_block = ('<div class="result-line">你的回忆：%s</div>' % html.escape(recall)
                    if recall else "")
    vocabulary_href = ctx.get("back_to_list") or "/textbook"
    body = """%s
<main>
  <section class="card center">
    <h2>这次学了</h2>
    %s
    %s
  </section>
  <form method="post" action="/vocabulary/study">
    <input type="hidden" name="pick" value="%s">
    <div class="row"><button class="primary" type="submit">再学一次</button></div>
  </form>
  <div class="row">
    <a href="%s"><button class="secondary" type="button">回到词汇表</button></a>
    <a href="/review"><button class="secondary" type="button">看看需要再学的</button></a>
  </div>
  <div class="hint">接下来做什么，由你自己决定。</div>
</main>""" % (header("学完了", None, vocabulary_href, "返回"),
              "\n    ".join(lines), recall_block, html.escape(ctx["key"]),
              html.escape(vocabulary_href))
    return layout("学完了 · %s" % PRODUCT_NAME, body)


def review_page(ctx: dict) -> str:
    """「需要再学」：只读展示当前错误 / 当前薄弱（孩子语言）。"""
    def rows(items):
        out = []
        for item in items:
            lines = ['<div class="w">%s</div>' % html.escape(item.get("text") or "")]
            if item.get("phonetic"):
                lines.append('<div class="phon">%s</div>' % html.escape(item["phonetic"]))
            info = " ".join(x for x in [
                ("%s." % item["part_of_speech"]) if item.get("part_of_speech") else "",
                item.get("meaning") or ""] if x)
            if info:
                lines.append('<div class="body">%s</div>' % html.escape(info))
            lines.append("""<form method="post" action="/vocabulary/study">
      <input type="hidden" name="pick" value="%s">
      <div class="row" style="margin-top:8px"><button class="secondary" type="submit">学习这个词</button></div>
    </form>""" % html.escape(item["key"]))
            out.append('<div class="item">%s</div>' % "\n    ".join(lines))
        return "\n  ".join(out)

    groups = ctx["pool"]["groups"]
    blocks = []
    if groups["forgot"]:
        blocks.append('<div class="sect"><h2>上次忘了</h2>%s</div>' % rows(groups["forgot"]))
    if groups["fuzzy"]:
        blocks.append('<div class="sect"><h2>上次有点模糊</h2>%s</div>' % rows(groups["fuzzy"]))
    if blocks:
        content = "\n  ".join(blocks)
        note = ""
    else:
        content = ('<div class="card"><p class="empty">暂时没有需要再学的内容</p>'
                   '<p class="empty-sub">这里只显示上次为「忘了」或「有点模糊」的词。</p></div>')
        note = ""
    if ctx["pool"].get("other_type_count"):
        note = ('<div class="hint">上面只显示单词；还有 %d 条其它类型的内容，'
                '在下面的教材建议里。</div>' % ctx["pool"]["other_type_count"])
    # P2-6-B6：教材优先巩固建议（只给建议；要不要做由孩子决定）
    tip_blocks = []
    for t in (ctx.get("suggestions") or []):
        lines = []
        for s in t["suggestions"]:
            head = "%s：%s" % (html.escape(s["label"]), html.escape(s["anchor_text"] or ""))
            if s.get("link"):
                lines.append('<li>%s → <a href="%s">去看看</a></li>'
                             % (head, html.escape(s["link"])))
            else:
                lines.append("<li>%s</li>" % head)
        warn = ('<div class="hint">这一条暂时还定位不到教材位置，所以只给出建议，不提供跳转。</div>'
                if t.get("requires_resource_mapping") else "")
        tip_blocks.append("""<div class="card">
    <h3>%s</h3>
    <p class="meta">依据：%s</p>
    <ul>%s</ul>
    %s
    <div class="hint">要不要做、先做哪一个，都由你自己决定。</div>
  </div>""" % (html.escape(t.get("text") or t["item_id"][-12:]),
               html.escape(t.get("reason") or ""), "".join(lines), warn))
    tips_html = "\n  ".join(tip_blocks)
    # P2-6-D-2：教材学习建议（Learning Object 级，只渲染 D-1 的派生结果）
    lo_section = ctx.get("lo_section") or {}
    lo_items = lo_section.get("items") or []
    lo_blocks = []
    for it in lo_items:
        lines = ['<div class="w">%s</div>' % html.escape(it.get("title") or "")]
        if it.get("mastery_display_text"):
            lines.append('<div class="body">%s</div>'
                         % html.escape(it["mastery_display_text"]))
        if it.get("diagnosis_label"):
            lines.append('<div class="body">%s</div>' % html.escape(it["diagnosis_label"]))
        if it["suggestions"]:
            items_html = []
            for s in it["suggestions"]:
                head = "%s：%s" % (html.escape(s.get("label") or ""),
                                   html.escape(s.get("anchor_text") or ""))
                if s.get("link"):
                    items_html.append('<li>%s → <a href="%s">去看看</a></li>'
                                      % (head, html.escape(s["link"])))
                else:
                    items_html.append("<li>%s</li>" % head)
            lines.append("<ul>%s</ul>" % "".join(items_html))
        lines.append('<div class="hint">要不要看、先看哪一个，都由你自己决定。</div>')
        lo_blocks.append('<div class="item">%s</div>' % "\n    ".join(lines))
    if lo_items:
        lo_content = "\n  ".join(lo_blocks)
    elif lo_section.get("available") is False:
        lo_content = ('<p class="empty">暂时无法生成教材学习建议</p>'
                      '<p class="empty-sub">这不影响上面已有的内容。</p>')
    else:
        lo_content = ('<p class="empty">暂时没有需要再看的教材学习对象</p>'
                      '<p class="empty-sub">这里只在你做过、并且出现过错误或没做出来的内容时出现。</p>')
    lo_html = """<div class="sect">
    <h2>教材学习建议</h2>
    <p class="hint">这里是你学过、并且值得再看一眼的教材内容。</p>
  </div>
  %s""" % lo_content
    body = """%s
<main>
  <section class="card">
    <h2>需要再学</h2>
    <p class="meta">忘了 %d 个 · 有点模糊 %d 个</p>
    <div class="hint">要不要再学、先学哪一个，都由你自己决定。</div>
  </section>
  %s
  %s
  %s
  %s
  <div class="foot">%s</div>
</main>""" % (header("需要再学", ctx.get("learner_name"), back_href="/", back_label="首页"),
              ctx["pool"]["forgot_count"], ctx["pool"]["fuzzy_count"], content, note, tips_html,
              lo_html, html.escape(PRODUCT_NAME))
    return layout("需要再学 · %s" % PRODUCT_NAME, body)


def name_entry_page(action: str, error: str = None) -> str:
    """「需要再学」等只读页面的最小身份入口（只问名字）。"""
    err = '<div class="err">%s</div>' % html.escape(error) if error else ""
    body = """%s
<main>
  <section class="card">
    <h2>请先写上你的名字</h2>
    <p class="meta">这个名字只用来找回你自己的学习记录。</p>
    %s
    <form method="post" action="%s" autocomplete="off">
      <div class="field"><label for="name">你的名字</label>
        <input id="name" name="name" placeholder="请输入名字" required></div>
      <div class="row"><button class="primary" type="submit">看看需要再学的</button></div>
    </form>
  </section>
</main>""" % (header("需要再学", None, "/", "首页"), err, html.escape(action))
    return layout("需要再学 · %s" % PRODUCT_NAME, body, active="")


# ---------------------------------------------------------------------------
# P2-6-F-1 / F-2：教材正文 + 按原题型的教材练习页
# ---------------------------------------------------------------------------

def _record_block() -> str:
    """完成情况记录（只记录发生过练习，不作为判分）。"""
    return """<div class="choices">
      <button class="secondary" type="submit" name="self_check" value="done">做完了</button>
      <button class="secondary" type="submit" name="self_check" value="partial">还想再看一遍</button>
    </div>"""


def _material_block(q: dict) -> str:
    """教材原题材料：教材原文 + 教材本页词框（只呈现，不改写）。"""
    mat = q.get("material") or {}
    box = q.get("page_word_box") or {}
    parts = []
    if mat:
        lines = "".join('<div class="qtext">%s</div>' % html.escape(b["text"])
                        for b in mat["blocks"] if b["kind"] != "instruction")
        if lines:
            parts.append('<div class="tbq"><span class="badge">教材原题 · 教材原文</span>'
                         '<div class="tbmaterial">%s</div></div>' % lines)
    if box:
        parts.append('<div class="tbq"><span class="badge">教材本页词框</span>'
                     '<ul class="tbitems">%s</ul><div class="hint">%s</div></div>'
                     % ("".join("<li>%s</li>" % html.escape(i) for i in box["items"]),
                        html.escape(box.get("review") or "")))
    return "".join(parts)


def _option_control(name: str, opt: dict, multi: bool) -> str:
    kind = "checkbox" if multi else "radio"
    return ('<label class="opt"><input type="%s" name="%s" value="%s"><span>%s</span></label>'
            % (kind, html.escape(name), html.escape(str(opt.get("label") or "")),
               html.escape(opt.get("text") or "")))


def _task_controls(task: dict) -> str:
    """按教材原题型生成作答控件（choice / fill / match）。"""
    if not task:
        return ""
    kind = task.get("kind")
    if kind == "choice":
        inline = task.get("inline_choices")
        if inline:
            out = []
            for seg in inline:
                if "text" in seg:
                    out.append(html.escape(seg["text"]))
                else:
                    name = "t%d" % seg["choice"]
                    opts = [{"label": "a", "text": seg["options"][0]},
                            {"label": "b", "text": seg["options"][1]}]
                    out.append('<span class="inlinepick">%s</span>'
                               % "".join(_option_control(name, o, False) for o in opts))
            return '<div class="qtext">%s</div>' % "".join(out)
        opts = task.get("options") or []
        if not opts:
            return ""
        groups = int(task.get("groups") or 1)
        multi = bool(task.get("multi"))
        if task.get("select"):
            rows = []
            for g in range(1, groups + 1):
                items = "".join('<option value="%s">%s</option>'
                                % (html.escape(str(o.get("label") or "")), html.escape(o.get("text") or ""))
                                for o in opts)
                rows.append('<div class="question"><div class="qtext">第 %d 个空</div>'
                            '<select name="t%d" aria-label="第 %d 个空">'
                            '<option value="">（从教材本页词框里选一个）</option>%s</select></div>'
                            % (g, g, g, items))
            return "".join(rows)
        rows = []
        for g in range(1, groups + 1):
            name = "t%d" % g
            ctl = "".join(_option_control(name, o, multi) for o in opts)
            label = ("第 %d 个空" % g) if groups > 1 else "按教材原题作答"
            rows.append('<div class="question"><div class="qtext">%s</div>%s</div>' % (label, ctl))
        return "".join(rows)
    if kind == "fill":
        inline = task.get("inline")
        if inline:
            out = []
            for seg in inline:
                if "text" in seg:
                    out.append(html.escape(seg["text"]))
                else:
                    out.append('<input name="t%d" autocomplete="off" spellcheck="false" '
                               'aria-label="空 %d">' % (seg["blank"], seg["blank"]))
            return '<div class="qtext">%s</div>' % "".join(out)
        n = int(task.get("blanks") or 1)
        return "".join('<div class="question"><div class="qtext">空 %d</div>'
                       '<div class="field"><input name="t%d" autocomplete="off" '
                       'spellcheck="false"></div></div>' % (i + 1, i + 1) for i in range(n))
    if kind == "match":
        items = task.get("items") or []
        if items:
            return "".join('<div class="question"><div class="qtext">%s. %s</div>'
                           '<div class="field"><input name="m%d" autocomplete="off" '
                           'spellcheck="false" placeholder="对照教材完成匹配"></div></div>'
                           % (i + 1, html.escape(it), i + 1) for i, it in enumerate(items))
        n = int(task.get("blanks") or 1)
        return "".join('<div class="question"><div class="qtext">第 %d 项</div>'
                       '<div class="field"><input name="m%d" autocomplete="off" '
                       'spellcheck="false"></div></div>' % (i + 1, i + 1) for i in range(n))
    return ""


def exercise_page(ctx: dict) -> str:
    """单个教材练习：教材原题 + 官方录音 + 按原题型的作答区（P2-6-F-2）。"""
    e, q = ctx["exercise"], ctx["questions"]
    tb = q.get("textbook") or {}
    task = q.get("textbook_task") or {}
    review = q.get("review") or []

    material_html = _material_block(q) or _textbook_block(tb)
    review_html = ('<div class="hint">%s</div>' % html.escape("；".join(review))) if review else ""
    head = """<section class="card">
    <h2>%s · 练习 %s</h2>
    <p class="meta">教材第 %s 页 ｜ %s</p>
    <div class="exins">%s</div>
    %s
    %s
    %s
  </section>""" % (html.escape(SECTION_LABELS.get(e["section"], e["section"])),
                    html.escape(str(e["exercise_no"])), e["textbook_page"],
                    html.escape(ctx["type_labels"].get(e["type"], "练习")),
                    html.escape(e["instruction"]),
                    material_html,
                    ('<div class="audio-inline"><div class="audiolabel">教材官方录音</div>%s</div>'
                     % speaker(ctx["audio_url"], "教材官方录音", "textbook"))
                    if ctx.get("audio_url") else "",
                    review_html)

    controls = _task_controls(task)
    selftest = q.get("vocab_selftest")
    selftest_html = ""
    if selftest:
        rows = "".join('<div class="question"><div class="qtext">%s. %s</div>'
                       '<div class="field"><input name="q%d" autocomplete="off" '
                       'spellcheck="false" placeholder="写出单词"></div></div>'
                       % (it["no"], html.escape(it["meaning"]), it["no"])
                       for it in selftest["questions"])
        selftest_html = ('<section class="card"><h2>词汇自测（本单元词表）</h2>'
                         '<p class="meta">%s</p>%s</section>' % (html.escape(selftest["note"]), rows))

    if q["kind"] == "short_answer":
        rows = "".join('<div class="question"><div class="qtext">%s. %s</div>'
                       '<div class="field"><textarea name="q%d" rows="3" '
                       'placeholder="用英语写一写你的回答"></textarea></div></div>'
                       % (it["no"], html.escape(it["text"]), it["no"])
                       for it in q["questions"])
        form_body = "".join(rows) + _self_check_block()
        answer_title = "自己作答"
        submit = '<div class="row"><button class="primary" type="submit">提交</button></div>'
    else:
        form_body = controls + (_record_block() if not controls else "")
        answer_title = "按教材原题作答" if controls else "这次练习的完成情况"
        submit = ('<div class="row"><button class="primary" type="submit">提交作答</button></div>'
                  if controls else "")

    name_field = ("""<div class="field"><label for="name">你的名字</label>
      <input id="name" name="name" autocomplete="off" placeholder="第一次使用请写上名字"
             required></div>
    <div class="hint">名字只用来记住你自己的练习记录，不需要账号和密码。</div>"""
                  if ctx.get("ask_name") else "")
    body = """%s
<main>
  %s
  <section class="card">
    <h2>%s</h2>
    <p class="meta">%s</p>
    <form method="post" action="/exercise/%s/submit">
      %s
      %s
      %s
    </form>
  </section>
  %s
  <div class="foot">%s</div>
</main>""" % (header("教材练习", "%s · %s" % (e["unit"], e["instruction"][:24]),
                    back_href="/unit/%s/exercises" % ctx["unit"]["slug"],
                    back_label="返回练习列表"),
              head, answer_title, html.escape(q["note"]), html.escape(ctx["key"]),
              name_field, form_body, submit, selftest_html, html.escape(PRODUCT_NAME))
    return layout("教材练习 · %s" % PRODUCT_NAME, body)


# ---------------------------------------------------------------------------
# Phase 1：教材原文音频热点（只读；句子级优先，活动级回退）
# ---------------------------------------------------------------------------

_HOT_QUOTE_MAP = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
                  "\u2013": "-", "\u2014": "-", "\u00a0": " "}


def _norm_with_map(text: str):
    """归一化文本 + 到原文下标的映射（只用于定位，不修改教材原文）。"""
    out, idx = [], []
    for i, ch in enumerate(text):
        c = _HOT_QUOTE_MAP.get(ch, ch)
        if c.isspace():
            if not out or out[-1] == " ":
                continue
            c = " "
        out.append(c)
        idx.append(i)
    s = "".join(out)
    left = len(s) - len(s.lstrip())
    right = len(s.rstrip())
    return s[left:right], idx[left:right]


def _audio_text_block_ids(audio_code: str) -> list:
    """该音频**精确对应**的教材文本块 id（只读；按官方 alignment 的 segments 取）。

    边界：`audio_resource_service.text_resources()` 已按 `status == VERIFIED`
    过滤并对 `text_resource_id` 去重（**它返回的字段里没有 status**，不要重复过滤）；
    这里只保留 `text_resource_kind == "content_block"`（== content_block.block_id），
    不做文本模糊匹配、不重算对齐、不猜映射。取不到就返回空列表 —— 调用方按
    "该音频没有对应课文"处理（例如纯听力活动），**不再整节兜底**。
    """
    import audio_resource_service as ars
    out = []
    for res in ars.text_resources(audio_code) or []:
        if (res.get("text_resource_kind") or "") != "content_block":
            continue
        bid = res.get("text_resource_id")
        if bid and bid not in out:
            out.append(bid)
    return out


def _reading_segments(audio_code: str) -> list:
    """该音频的「听读课文」段（来自正式资产 `audio_resource_v1.json` 的 `reading_segments`）。

    只读；段字段：index / start_ms / end_ms / text / source（教材|AI①|AI②|AI③）/ hide。
    `hide=true`（AI③ 教材答案键碎片）由调用方跳过。取不到就返回 []（不猜、不补）。
    """
    import audio_resource_service as ars
    res = ars.get_by_audio(audio_code) or {}
    return res.get("reading_segments") or []


def unit_text_page(ctx: dict) -> str:
    """听读课文（2026-09-30 定版）：**按音频精确分块** —— 一块 = 一段音频 + 它自己的课文。

    规则：
      * **一块 = 一个官方音频活动**（`activities`：audio_code / instruction），块标题取该音频的教材指令；
      * 每块的正文 = 正式资产 `reading_segments`（句级、带时间与来源）；
        `source=教材` 用正常字体；`AI①/AI②` 用另一种字体；**`hide=true`（AI③）不显示**；
        没有 `reading_segments` 时**兜底**回"alignment 精确对应的教材文本块"；
      * 纯听力活动（音频没有对应课文，例如"听广播/听对话"）**只显示播放器，不显示课文** ——
        避免把别的活动的课文错配给它，也避免同一段课文重复出现；
      * 每块只有一个播放器（**整段官方音频**，不显示时间码）；
        播放时按音频 `currentTime` 对 `start_ms/end_ms` 高亮当前句；
      * **整节没有任何音频的 Section 不显示**；页面只保留「书名 + Section + 块」，无多余信息。
    """
    unit, data = ctx["unit"], ctx["text"]
    audio = ctx.get("audio") or {}
    acts = audio.get("activities") or []

    # block_id → 教材原文（该 Unit 展示范围内）
    text_of = {}
    for s in data.get("sections") or []:
        for b in s.get("blocks") or []:
            text_of[b["block_id"]] = b["text"]

    by_section = {}
    for a in acts:
        key = a.get("section_key")
        if key:
            by_section.setdefault(key, []).append(a)

    cards = []
    for s in data.get("sections") or []:
        key = s.get("section_key")
        sec_acts = by_section.get(key) or []
        if not sec_acts:
            continue                       # 没有音频的 Section 不显示（不显示空态）
        chunks = []
        for a in sec_acts:
            code = a.get("audio_code")
            url = a.get("audio_url") or ("/audio/official/%s.mp3" % code)
            # 2026-09-30：正文改用正式资产里的 reading_segments（句级 + 时间 + 来源）。
            # 旧路径（按 alignment 取整块）保留为**兜底**：没有 reading_segments 的音频仍可有正文。
            segs = _reading_segments(code)
            if segs:
                parts = []
                for s in segs:
                    if s.get("hide"):
                        continue                      # AI③：教材答案键碎片，不显示
                    cls = "rseg" if s.get("source") == "教材" else "rseg ai-src"
                    parts.append(
                        '<span class="%s" data-start="%d" data-end="%d" data-source="%s">%s</span>'
                        % (cls, int(s.get("start_ms") or 0), int(s.get("end_ms") or 0),
                           html.escape(str(s.get("source") or "")), html.escape(s.get("text") or "")))
                body = "".join(parts)
            else:
                ids = _audio_text_block_ids(code)
                lines = [text_of[bid] for bid in ids if bid in text_of]
                body = "".join('<p class="qtext">%s</p>' % html.escape(x) for x in lines)
            # 2026-10-01（UI-7 第 3 件）：播放器**移到正文上方**（块标题 → 播放器 → 正文）。
            # 高亮脚本按 `.tchunk` 内 `.rseg` 的时间属性工作，与元素顺序无关，故不受影响。
            chunks.append(
                '<div class="tchunk"><h3 class="tchunk-t">%s</h3>'
                '<div class="tchunk-spk">%s</div>'
                '<div class="tchunk-txt">%s</div></div>'
                % (html.escape((a.get("instruction") or "").strip() or "教材原声"),
                   p5_segment_speaker(url, None, None,
                                      label=(a.get("instruction") or "播放本段教材原声")),
                   body))
        cards.append("""<section class="card">
    <h2>%s</h2>
    %s
  </section>""" % (html.escape(SECTION_LABELS.get(key, s.get("title") or "")),
                    "".join(chunks)))
    if not cards:
        return layout("听读课文 · %s" % PRODUCT_NAME,
                      header(unit["unit_code"] or "单元", "听读课文",
                             back_href="/unit/%s" % (unit.get("slug") or ""),
                             back_label="返回单元中心")
                      + """
<main>
  <section class="card">
    <h2>%s</h2>
    <p class="meta">这一单元暂时没有可以边听边看的课文。</p>
    <div class="row"><a href="/"><button class="secondary" type="button">回到首页</button></a></div>
  </section>
  <div class="foot">%s</div>
</main>""" % (html.escape(unit["title"] or ""), html.escape(PRODUCT_NAME)))
    body = (header(unit["unit_code"] or "单元", "听读课文",
                             back_href="/unit/%s" % (unit.get("slug") or ""),
                             back_label="返回单元中心")
            + """
<main>
  <section class="card">
    <p class="textbook-name">%s</p>
  </section>
  %s
</main>
%s
%s""" % (html.escape(unit["title"] or ""), "\n  ".join(cards),
          "<style>%s</style>" % _TEXT_CHUNK_STYLE, P5_SEGMENT_SCRIPT + _TEXT_READ_JS))
    return layout("听读课文 · %s" % PRODUCT_NAME, body)



#: 听读课文：播放高亮（按音频 currentTime 命中 reading_segments 的 start_ms/end_ms）。
#: 与 P5_SEGMENT_SCRIPT（共享播放器）**互不耦合** —— 本脚本自己找 <audio> 与其所在 .tchunk，
#: 只在该块范围内切换 .on（避免同一页多个块互相干扰）。不采用 data-* 标记，故不改动共享播放器。
_TEXT_READ_JS = """<script>
(function(){
  function segsOf(chunk){
    return chunk ? chunk.querySelectorAll('.tchunk-txt .rseg') : [];
  }
  function clear(chunk){
    var a = segsOf(chunk);
    for (var i = 0; i < a.length; i++) a[i].classList.remove('on');
  }
  /* 共享播放器（P5_SEGMENT_SCRIPT）用 new Audio()，**元素不在 DOM 里** ⇒
     必须通过它暴露的 window.__zxPlayer 读取 currentTime。 */
  function player(){ return window.__zxPlayer || null; }
  /* 当前正在播放的是哪一块：由 .spk 的 .on（播放器加的播放态）判定；
     取不到时回落到"第一块"。 */
  function activeChunk(){
    var on = document.querySelector('.tchunk .spk.on');
    if (on && on.closest) { var c = on.closest('.tchunk'); if (c) return c; }
    return document.querySelector('.tchunk');
  }
  function sync(){
    var A = player();
    var chunk = activeChunk();
    if (!A || !chunk){ return; }
    if (A.paused || A.ended){ clearAll(); return; }
    var t = A.currentTime * 1000;
    var segs = segsOf(chunk), hit = null;
    for (var i = 0; i < segs.length; i++){
      var s = parseFloat(segs[i].getAttribute('data-start') || '0');
      var e = parseFloat(segs[i].getAttribute('data-end') || '0');
      if (t >= s && t < e){ hit = segs[i]; break; }
    }
    for (var j = 0; j < segs.length; j++){
      if (segs[j] === hit){ if (!segs[j].classList.contains('on')) segs[j].classList.add('on'); }
      else { segs[j].classList.remove('on'); }
    }
  }
  function clearAll(){
    var a = document.querySelectorAll('.rseg.on');
    for (var i = 0; i < a.length; i++) a[i].classList.remove('on');
  }
  var bound = false;
  function bind(){
    if (bound) return;
    var A = player();
    if (!A) return;
    bound = true;
    A.addEventListener('timeupdate', sync);
    A.addEventListener('play', sync);
    A.addEventListener('pause', sync);
    A.addEventListener('ended', sync);
    A.addEventListener('seeked', sync);
  }
  /* 播放器在脚本执行时即创建 window.__zxPlayer；仍做轻量轮询兜底（未绑定才动作） */
  bind();
  window.addEventListener('load', bind);
  var n = 0, timer = setInterval(function(){
    bind();
    if (++n > 20 || bound) clearInterval(timer);
  }, 500);
})();
</script>"""


#: 听读课文「按音频分块」样式：每块 = 课文 + 一个整段播放器（风格与跟读页一致）
_TEXT_CHUNK_STYLE = """
.tchunk{margin:0 0 16px}
.tchunk-t{margin:0 0 8px;font-size:14px;font-weight:600;color:var(--text2)}
.tchunk:last-child{margin-bottom:0}
.tchunk-txt{margin:0 0 10px;font-size:17px;line-height:1.9}
.tchunk-txt .qtext{margin:0 0 8px}
.tchunk-spk{display:flex;justify-content:flex-start;margin:0 0 2px}
/* 双字体：教材原文 = 正文默认字体（正常、深色）；AI 补全 = 楷体 + 次级色 + 青色底（一眼可辨）
   2026-10-01：「AI 补全段」的类名由 `ai` 改为 **`ai-src`**，并在此**显式写出**青底/青框。
   原实现用 `ai`，与旧「AI 卡片」类 `.ai`（本文件 STYLE 内 L221）**同名相撞** ⇒ 青底+青框只是
   **级联冲突的副作用**（CSS 顺序一变就会失效）。现改为独立类名 + 显式声明：
   **视觉效果与实测基准完全一致，但不再依赖意外**。
   注：`.ai` 旧卡片类保持原样不动（它服务于 ai_card()，只是不再被本页引用）。 */
.rseg{font-style:normal;color:var(--text);border-radius:5px;padding:1px 2px;
      transition:background .12s ease}
/* AI 补全段（AI① 音频独有 / AI② 导航指令）：实测基准 = 青底 #F4FBFE + 青框 #CBE7F4
   + 楷体 + 次级文字色 #6B7078 */
.rseg.ai-src{background:#F4FBFE;border:1px solid #CBE7F4;
             font-family:KaiTi,"Kaiti SC","STKaiti",serif;color:var(--text2)}
/* 正在播放的那一句：背景高亮（教材/AI 各自底色深浅不同，仍可区分来源） */
.rseg.on{background:#FFF3C4}
.rseg.ai-src.on{background:#EAF6EF}
"""


def _ms_clock(ms) -> str:
    ms = int(ms or 0)
    m, rem = divmod(ms, 60000)
    sec, msec = divmod(rem, 1000)
    return "%02d:%02d.%03d" % (m, sec, msec)


# ---------------------------------------------------------------------------
# Demo V1：进展页 + 通用播放 / 录音组件
# （P6-B-23：旧句子学习页 / 旧跟读页 / 旧学习结果页 / 旧 p3-06 实验页均已退休）
# ---------------------------------------------------------------------------

PLAYER_JS = """<script>
(function(){
  var A = new Audio(); A.preload = 'none';
  var current = null, stopAt = null;
  function clear(){ if(current){ current.classList.remove('playing'); current = null; } }
  A.addEventListener('timeupdate', function(){
    if(stopAt !== null && A.currentTime >= stopAt){
      A.pause(); stopAt = null; clear();
    }
  });
  A.addEventListener('ended', clear);
  document.addEventListener('click', function(ev){
    var el = ev.target && ev.target.closest ? ev.target.closest('[data-play]') : null;
    if(!el){ return; }
    var src = el.getAttribute('data-play');
    var begin = parseInt(el.getAttribute('data-start') || '0', 10);
    var raw = el.getAttribute('data-end');
    if(current === el){ A.pause(); clear(); return; }
    if(A.getAttribute('data-src') !== src){ A.setAttribute('data-src', src); A.src = src; }
    clear(); current = el; el.classList.add('playing');
    stopAt = (raw === null || raw === '') ? null : parseInt(raw, 10) / 1000;
    try{ A.currentTime = begin / 1000; }catch(e){}
    var pr = A.play(); if(pr && pr.catch){ pr.catch(function(){}); }
  });
})();
</script>"""


def play_button(url: str, start_ms=None, end_ms=None, label: str = "▶ 听标准音") -> str:
    """播放按钮：孩子主动点击才播放；音频一律来自真实教材资源。"""
    if not url:
        return ""
    extra = ""
    if start_ms is not None:
        extra += ' data-start="%d"' % int(start_ms)
    if end_ms is not None:
        extra += ' data-end="%d"' % int(end_ms)
    return ('<button class="playbtn" type="button" data-play="%s"%s>%s</button>'
            % (html.escape(url), extra, html.escape(label)))


def progress_page(ctx: dict) -> str:
    """我的进展：让家长几秒内看懂孩子这一周吸收了什么。

    三个维度固定为 课文理解 / 句型语法 / 口语练习；口语练习只给次数，不给分数。
    维度数值是演示数据（已标注）；「最近学过 / 需要再学」是真实数据。
    """
    prog = ctx["parent_progress"]
    cr = ctx["classroom"]
    rows = "".join(parent_progress_row(r) for r in prog["rows"])
    pool = ctx.get("pool") or {}
    total = int(pool.get("total") or 0)
    if total > 0:
        pool_body = ('<p class="meta">有 %d 个内容需要再学：上次忘了 %d 个，'
                     '上次有点模糊 %d 个。</p>'
                     % (total, int(pool.get("current_error_count") or 0),
                        int(pool.get("current_weak_count") or 0)))
    else:
        pool_body = ('<p class="meta">目前还没有需要再学的内容</p>'
                     '<p class="empty-sub">这里只显示上次为「忘了」或「有点模糊」的内容。</p>')
    body = """%s
<main>
  <section class="card">
    <h2>这一周</h2>
    <p class="meta">%s · %s · %s</p>
    %s
    <p class="demo-note"><span class="demo">%s</span> %s</p>
  </section>

  <section class="card">
    <h2>最近学过</h2>
    %s
  </section>

  <section class="card">
    <h2>当前值得关注</h2>
    <p class="meta">这些内容来自演示学习证据；它们是下一次学习的线索，不是对孩子的评价。</p>
    %s
  </section>

  <section class="card">
    <h2>需要再学</h2>
    %s
    <div class="row"><a href="/review"><button class="secondary" type="button">去看看</button></a></div>
  </section>

  <div class="row">
    <a href="/textbook"><button class="primary" type="button">%s 回到教材继续学</button></a>
  </div>
  <div class="hint">接下来学什么、什么时候学，都由你自己决定。</div>
  <div class="foot">%s</div>
</main>""" % (header("进展", "我的学习进展", back_href="/", back_label="首页"),
              html.escape(cr["book"]), html.escape(cr["unit_code"]),
              html.escape(cr["unit_title"]), rows,
              html.escape(demo.DEMO_LABEL), html.escape(prog["note"]),
              recent_studied_block(ctx.get("recent") or []),
              attention_list(ctx.get("attention") or []),
              pool_body, icon("book"),
              html.escape(PRODUCT_NAME))
    return layout("进展 · %s" % PRODUCT_NAME, body, active="progress")


# ---------------------------------------------------------------------------
# P6-A ??????????/?????? learning/study_call_service.py?
#   ??"P5 question ? ???? UI ??"????????????????? UI ???
# ---------------------------------------------------------------------------

P5_SEGMENT_SCRIPT = """<script>
(function(){
  /* P5 六个入口：整页一个共享播放器，.spk 只携带播放描述（data-audio/data-start/data-end）。
     任何时刻最多一处发声：切换条目一定先停上一条再播新的。 */
  var A = new Audio(); A.preload = 'auto';
  var cur = null, tick = null, gen = 0;
  function stopTick(){ if (tick) { clearInterval(tick); tick = null; } }
  function mark(el, on){ if (el) el.classList.toggle('on', !!on); }
  function release(){ mark(cur, false); cur = null; }
  /* 到 data-end 就停：只停当前条目，不连播下一条 */
  function startTick(){
    stopTick();
    if (!cur) return;
    var end = parseInt(cur.getAttribute('data-end') || '0', 10) || 0;
    if (!(end > 0)) return;
    tick = setInterval(function(){
      if (A.currentTime >= end / 1000 - 0.03) { A.pause(); stopTick(); }
    }, 60);
  }
  function load(el, go, my){
    try { A.pause(); } catch (e) {}
    var href = new URL(el.getAttribute('data-audio'), location.href).href;
    if (A.src !== href) { A.src = href; try { A.load(); } catch (e) {} }   /* 换源后显式 load() */
    var start = parseInt(el.getAttribute('data-start') || '0', 10) || 0;
    function seek(){
      if (my !== gen) return;              /* 期间已切到别的条目 → 旧加载作废 */
      try { A.currentTime = start / 1000; } catch (e) {}
      go();
    }
    if (A.readyState >= 1) { seek(); }
    else { A.addEventListener('loadedmetadata', function once(){
      A.removeEventListener('loadedmetadata', once); seek(); }); }
  }
  /* 等音频真的可播放再播，避免"刚设 src 就播"造成截断；期间切换则本次作废 */
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
  /* play() 只是"请求播放"：被 WebView 拒绝就安静回到未播放，不显示任何技术错误 */
  function begin(){ var pr = A.play(); if (pr && pr.catch) { pr.catch(function(){ stopTick(); release(); }); } }
  A.addEventListener('ended', function(){ stopTick(); release(); });
  A.addEventListener('pause', function(){ stopTick(); if (cur) mark(cur, false); });
  A.addEventListener('playing', function(){ if (cur) mark(cur, true); });
  function playItem(el){
    if (!el || !el.getAttribute || !el.getAttribute('data-audio')) return false;
    gen += 1;
    var my = gen;
    stopTick();
    try { A.pause(); } catch (e) {}         /* 先停上一条：不允许两条同时播放 */
    release();
    cur = el;
    mark(el, true);
    load(el, function(){
      if (my !== gen) return;
      waitCanPlay(my, function(){ if (my !== gen) return; startTick(); begin(); });
    }, my);
    return true;
  }
  function toggle(el){
    if (cur === el && !A.paused) { A.pause(); return; }   /* 再点当前条 = 暂停 */
    playItem(el);
  }
  document.addEventListener('click', function(ev){
    var el = ev.target;
    while (el && el !== document.body) {
      if (el.getAttribute && el.getAttribute('data-audio')) { ev.preventDefault(); toggle(el); return; }
      el = el.parentNode;
    }
  });
  window.addEventListener('pagehide', function(){ try { A.pause(); } catch (e) {} });
  window.__zxAutoPlay = playItem;      /* 供滑动切换调用：停旧播新（对外只暴露已有的播放函数） */
  /* 2026-09-30：本播放器用 `new Audio()`（**游离元素，不在 DOM 里**），
     听读课文的高亮脚本需要读到 currentTime ⇒ 在此把该元素暴露出去。
     仅新增一个只读引用，不改变任何播放行为。 */
  window.__zxPlayer = A;
  /* 进入内容：自动播放第一个可播放条目（被 WebView 拒绝则静默，保留手动点击） */
  function autoStart(){
    var el = document.querySelector('[data-autoplay="1"]');
    if (!el) return;
    try { playItem(el); } catch (e) {}
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', autoStart); }
  else { autoStart(); }
})();
</script>"""


def p5_segment_speaker(url, start_ms=None, end_ms=None, label="????", kind="textbook"):
    """??? speaker() ??????????????????????????????"""
    if not url:
        return ""
    ico = "\U0001F3A7" if kind == "textbook" else "\U0001F50A"
    attrs = ' data-audio="%s"' % html.escape(url)
    if start_ms is not None:
        attrs += ' data-start="%d"' % int(start_ms)
    if end_ms is not None:
        attrs += ' data-end="%d"' % int(end_ms)
    return ('<span class="spk %s"%s aria-label="%s">'
            '<span class="spk-ico" data-ico="%s" aria-hidden="true">'
            '<i></i><i></i><i></i></span></span>'
            % (html.escape(kind), attrs, html.escape(label), ico))


def _p5_meta(unit: dict, label: str) -> str:
    return "%s · %s" % (unit.get("unit_code") or "", unit.get("title") or "")


#: P6-B-12-FIX S2：当前 Section 无该功能资源时的空状态文案
#: （准确、面向孩子；不使用"换个章节看看"这类与事实不符的误导文案）
P5_EMPTY_LINE = "这一课暂时没有可以练的内容。"


def _p5_empty_page(unit: dict, entry: str, label: str, lesson_key: str = "") -> str:
    """直接进入无资源功能页时的真实空状态（不是错误页，也不引导"换章节"）。"""
    back = "/unit/%s" % unit["slug"]
    body = """%s
<main>
  <section class="card">
    <h2>%s</h2>
    <p class="meta">%s</p>
    <div class="hint">这个入口暂时是空的，不影响其它入口的学习。</div>
    <div class="row"><a href="%s"><button class="secondary" type="button">回到首页</button></a></div>
  </section>
  <div class="foot">%s</div>
</main>""" % (header(label, _p5_meta(unit, label), back_href=back, back_label="返回单元中心"),
              html.escape(label), html.escape(P5_EMPTY_LINE), html.escape(back),
              html.escape(PRODUCT_NAME))
    return layout("%s · %s" % (label, PRODUCT_NAME), body)


def p5_page(ctx: dict) -> str:
    """???????????? / ???????????????????????"""
    unit, entry, label = ctx["unit"], ctx["entry"], ctx["label"]
    slug = unit["slug"]
    back = "/unit/%s" % slug
    items = ctx.get("items") or []
    index = int(ctx.get("index") or 0)
    index = max(0, min(index, len(items) - 1)) if items else 0
    mode = ctx.get("mode") or ""
    total = len(items)
    name_field = ""     # P6-B-8：学习页不再渲染姓名输入（身份沿用既有 Cookie/最小身份机制）
    if not items:
        # P6-B-12-FIX S2：该功能在当前 Section 没有资源 → 真实空状态（不伪造内容、不换章节）
        return _p5_empty_page(unit, entry, label, ctx.get("lesson_key") or "")
    if entry == "read":
        return _p5_read_page(ctx, unit, label, items, index, mode, name_field)
    return _p5_question_page(ctx, unit, entry, label, items, index, mode, name_field)


#: P6-B-7：跟读页左右滑动（Demo 已验证）：滑动 = 切换内容 + 自动播放这一屏的教材音频。
P5_SWIPE_SCRIPT = """<script>
(function(){
  var box = document.getElementById('zx-swipe');
  if (!box) return;
  var cards = [].slice.call(box.querySelectorAll('.card-w'));
  if (!cards.length) return;
  var play = document.getElementById('zx-play');
  var done = document.getElementById('zx-read-i');
  var cur = 0;
  function activate(i){
    i = Math.max(0, Math.min(i, cards.length - 1));
    if (i === cur && play && play.getAttribute('data-audio') === cards[i].getAttribute('data-audio')) return;
    cur = i;
    var c = cards[i];
    if (window.__zxResetRec) { try { window.__zxResetRec(); } catch (e) {} }   /* 换句：旧录音作废 */
    if (done) done.value = i;
    if (play) {
      play.setAttribute('data-audio', c.getAttribute('data-audio') || '');
      var s = c.getAttribute('data-start'), e = c.getAttribute('data-end');
      if (s) { play.setAttribute('data-start', s); } else { play.removeAttribute('data-start'); }
      if (e) { play.setAttribute('data-end', e); } else { play.removeAttribute('data-end'); }
      play.classList.remove('on');
    }
    /* 滑动切换 = 内容切换 + 教材音频自动播放（同一入口，不新增按钮） */
    if (play && window.__zxAutoPlay) { try { window.__zxAutoPlay(play); } catch (e) {} }
  }
  box.addEventListener('scroll', function(){
    var w = cards[0] ? cards[0].getBoundingClientRect().width + 16 : 1;
    activate(Math.round(box.scrollLeft / w));
  }, { passive: true });
  window.addEventListener('load', function(){ activate(0); });
  activate(0);
})();
</script>"""


#: P6-B-7：跟读录音（Demo 已验证的交互）：点麦克风开始/再点结束、录音态可见、
#: 连续静音自动结束；结束后只启用「我的朗读」，由孩子自己点击回放（不自动回放）。
#: J1（批次 1+2+4·d）：下发给页面的证据包字段**白名单**。
#: 只下发 AI 判分真正需要的字段；**明确排除 `related_image`**
#: （实测它在 344/360 个包里非空，既非文本证据又会虚增证据条数）。
P5_EVIDENCE_FIELDS = ('scope', 'textbook_reference', 'original_question', 'related_text', 'related_vocabulary', 'related_grammar', 'related_listening', 'ai_rules', 'answer_note')

#: 单元中心二期·C-2：AI 学情分析的**页面侧脚本**（接收端 + 派发端 + 渲染）。
#: 与 P5_AI_BRIDGE_JS 同构（那也是"页面 JS 转发 → 原生 Kotlin 调 AI"）：
#: 这里的桥方法名不同（`analyze`），回调名不同（`__zxAnalyzeOnResult`）。
UNIT_CENTER_AI_JS = r"""<script>
/* 单元中心 AI 学情分析（二期·C-2）。
   三态：
     成功      -> ① 顶部替换为 summary；② 显示优缺点与建议；④ 按钮替换为 AI 建议
     失败/未配置 -> ② 显示"学习分析暂时不可用"，①③④ 保持原样
     桥未注入  -> ② 保持"学习分析即将上线"（什么都不做）
   防越界：④ 的 entry/mode 必须落在输入 practice_entries 白名单里，否则丢弃该条。 */
(function () {
  var tag = document.getElementById('zx-analyze-data');
  if (!tag) return;                       /* 门槛未到：页面没下发数据，不触发 */
  var payload;
  try { payload = JSON.parse(tag.textContent); } catch (e) { return; }
  var panel = document.getElementById('zx-ai-panel');
  var lead = document.getElementById('zx-lead');
  var box = document.getElementById('zx-uc-btns');
  if (!panel) return;
  var bridge = (window.ZxAi && typeof window.ZxAi.analyze === 'function') ? window.ZxAi : null;
  if (!bridge) return;                    /* 桥未注入：保持"学习分析即将上线" */

  /* ④ 按钮的白名单（只有这里面的 entry/mode 能被渲染） */
  var allowed = {};
  (payload.practice_entries || []).forEach(function (e) {
    allowed[(e.entry || '') + '|' + (e.mode || '')] = e.label || '';
  });

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function render(data) {
    /* ① 顶部一句话（成果） */
    if (lead && data.summary) lead.textContent = data.summary;
    /* ② 优缺点 + 建议 */
    var html = '';
    if (data.strengths && data.strengths.length) {
      html += '<p class="uc-line"><b>做得好的</b></p><ul class="uc-ul">';
      data.strengths.slice(0, 2).forEach(function (s) { html += '<li>' + esc(s) + '</li>'; });
      html += '</ul>';
    }
    if (data.weaknesses && data.weaknesses.length) {
      html += '<p class="uc-line"><b>还要多练</b></p><ul class="uc-ul">';
      data.weaknesses.slice(0, 2).forEach(function (s) { html += '<li>' + esc(s) + '</li>'; });
      html += '</ul>';
    }
    if (data.advice) html += '<p class="uc-advice">' + esc(data.advice) + '</p>';
    panel.innerHTML = html || '<p class="uc-empty">这次先看到这里，继续练就会有更多分析。</p>';

    /* ④ 按钮替换为 AI 建议（**过白名单**；不在白名单的整条丢弃） */
    var sugg = (data.practice_suggestions || []).filter(function (s) {
      return s && allowed.hasOwnProperty((s.entry || '') + '|' + (s.mode || ''));
    }).slice(0, 2);
    if (box && sugg.length) {
      /* URL 要的是 **slug**（unit1），不是 unit_code（"Unit 1"）。
         D-2：slug 从 `<main data-unit-slug>` 读（**不再塞进 payload**，避免进 AI 的 prompt）；
         取不到再从当前路径兜底。 */
      var mainEl = document.querySelector('main[data-unit-slug]');
      var slug = (mainEl && mainEl.getAttribute('data-unit-slug')) ||
                 ((location.pathname.match(/^\/unit\/([^\/]+)/) || [])[1] || '');
      var rows = sugg.map(function (s, i) {
        var key = (s.entry || '') + '|' + (s.mode || '');
        var href = '/unit/' + encodeURIComponent(slug) + '/p5/' + encodeURIComponent(s.entry) +
                   (s.mode ? ('?mode=' + encodeURIComponent(s.mode)) : '');
        return '<a class="uc-btn" href="' + href + '"><span class="t">' +
               (i === 0 ? '补一补' : '练一练') + '</span><span class="d">' +
               esc(allowed[key]) + (s.reason ? ' · ' + esc(s.reason) : '') + '</span></a>';
      });
      box.innerHTML = rows.join('');
    }
  }

  function unavailable(reason) {
    panel.innerHTML = '<p class="uc-empty">学习分析暂时不可用</p>';
  }

  window.__zxAnalyzeOnResult = function (raw) {
    var res;
    try { res = (typeof raw === 'string') ? JSON.parse(raw) : raw; }
    catch (e) { return unavailable('bad-json'); }
    if (!res) return unavailable('empty');
    if (res.status !== 'ok') return unavailable(res.status || 'failed');
    render(res.data || res);
  };

  try {
    bridge.analyze(JSON.stringify(payload));
  } catch (e) {
    unavailable('call-threw');
  }
})();
</script>"""


P5_AI_BRIDGE_JS = '<script>\n/* P6-A / A-1：AI 批改桥 —— 页面侧（接收端 + 派发端）\n   架构（唯一可行）：Python 提供教材证据 -> 页面 JS 转发 -> 原生 Kotlin 调 AI -> 回调本函数渲染。\n   为什么必须走原生：AI 的 Key 只在 Android 侧（SecureKeyStore + Keystore），页面与后端都拿不到。\n   硬性边界：Key 永不进入本页面；本脚本不做任何网络请求；AI 失败不阻断确定性学习功能。\n   调用契约（与 ZxAiBridge.kt 成对，两处必须同步修改）：\n     JS -> 原生：window.ZxAi.grade(payloadJsonString)\n     原生 -> JS：window.__zxAiOnResult(resultJsonString)\n   注意：本文件用单引号包裹 JS，故 JS 内【不使用单引号】，字符串一律用双引号拼接。 */\n(function(){\n  var FB = "zx-ai-fb";\n  function fb(){ return document.getElementById(FB); }\n  function esc(s){ return String(s == null ? "" : s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }\n  function arr(v){ return Object.prototype.toString.call(v) === "[object Array]" ? v : (v ? [v] : []); }\n  function setBusy(on){ var b = fb(); if(!b) return; if(on){ b.className = "fb show"; b.innerHTML = "<b>AI 正在批改…</b>"; } }\n  function keepOriginal(reason){\n    var b = fb(); if(!b) return;\n    b.className = "fb show";\n    b.innerHTML = "<b>需要 AI 批改，暂时先不打分。</b>" + (reason ? "<span class=\\"meta\\">（" + esc(reason) + "）</span>" : "");\n  }\n  function renderOk(d){\n    var b = fb(); if(!b) return;\n    var html = "<b>AI 批改结果</b>";\n    if(d.error_type) html += "<div>问题类型：" + esc(d.error_type) + "</div>";\n    if(d.likely_slip !== undefined) html += "<div>是否可能是笔误：" + (d.likely_slip ? "可能是" : "不像") + "</div>";\n    if(d.explanation) html += "<div>说明：" + esc(d.explanation) + "</div>";\n    var ev = arr(d.evidence_used);\n    if(ev.length) html += "<div>依据的教材证据：" + esc(ev.join("；")) + "</div>";\n    var si = arr(d.suggested_interventions);\n    if(si.length) html += "<div>建议：" + esc(si.join("；")) + "</div>";\n    html += "<div class=\\"meta\\">置信度：" + esc(d.confidence || "-") + " · 证据条数：" + esc(d.evidence_count_used) + "</div>";\n    if(d.need_now_blocked_reason) html += "<div class=\\"meta\\">暂不建议立即干预（" + esc(d.need_now_blocked_reason) + "）</div>";\n    html += "<div class=\\"meta\\">以上为 AI 辅助判断，最终由你决定是否继续。</div>";\n    b.className = "fb show";\n    b.innerHTML = html;\n  }\n  /* ===== AI 老师（答错讲解）—— 与 __zxAiOnResult 独立 ===== */\n  function tfb(){ return document.getElementById("zx-teach-fb"); }\n  window.__zxTeachOnResult = function(data){\n    if(typeof data === "string"){ try { data = JSON.parse(data); } catch(e){ return; } }\n    var host = tfb(); if(!host || !data || !data.status) return;\n    if(data.status !== "ok"){ return; }   /* 失败/未配置：保持现状，不打扰 */\n    var d = data.data || {};\n    var wrong = d.wrong || "", should = d.should || "", ex = d.example || "";\n    if(!wrong && !should && !ex) return;\n    var html = "<div class=\\"fb show ai-teach\\"><b class=\\"ai-tag\\">AI 讲解</b>";\n    if(wrong)  html += "<div>① 错在哪：" + esc(wrong) + "</div>";\n    if(should) html += "<div>② 该用什么：" + esc(should) + "</div>";\n    if(ex)     html += "<div>③ 例句：" + esc(ex) + (d.example_source === "textbook" ? "（课本原句）" : "") + "</div>";\n    host.innerHTML = html + "</div>";\n  };\n  function teachPayload(){\n    var ev = document.getElementById("zx-teach");\n    var host = tfb();\n    if(!host || !ev) return null;\n    var p;\n    try { p = JSON.parse(ev.textContent || "{}"); } catch(e){ return null; }\n    if(!p || !p._question_id) return null;\n    return p;\n  }\n  function tryTeach(){\n    var host = tfb(); if(!host) return;\n    if(!(window.ZxAi && typeof window.ZxAi.teach === "function")) return;   /* 桥未注入：保持现状 */\n    var p = teachPayload();\n    if(!p) return;\n    try { window.ZxAi.teach(JSON.stringify(p)); } catch(e){ /* 保持现状 */ }\n  }\n  if(document.readyState === "loading"){ document.addEventListener("DOMContentLoaded", tryTeach); } else { tryTeach(); }\n  window.__zxAiOnResult = function(data){\n    if(typeof data === "string"){ try { data = JSON.parse(data); } catch(e){ keepOriginal("返回内容无法解析"); return; } }\n    if(!data || !data.status){ keepOriginal("返回内容不完整"); return; }\n    if(data.status === "ok"){ renderOk(data.data || {}); return; }\n    if(data.status === "ai_disabled"){ keepOriginal("AI 未启用"); return; }\n    if(data.status === "not_configured"){ keepOriginal("AI 尚未配置"); return; }\n    if(data.status === "rejected"){ keepOriginal(data.reason || "证据不足"); return; }\n    keepOriginal("批改失败" + (data.reason ? "：" + data.reason : ""));\n  };\n  /* 页面 -> 原生：仅在提交后、存在待批改容器且有证据脚本时发起。\n     原生桥未注入（PC 浏览器 / 非 debug 构建 / AI 未配置）时保持原文案，不发请求。 */\n  function payload(){\n    var ev = document.getElementById("zx-evidence");\n    if(!fb() || !ev) return null;\n    var raw;\n    try { raw = JSON.parse(ev.textContent || "{}"); } catch(e){ return null; }\n    if(!raw || !raw._question_id) return null;\n    /* 接口对齐（A-2）：Kotlin ZxAiBridge 期望 6 键，而 zx-evidence 是\n       「证据包业务字段 + _ 前缀审计字段」的扁平结构，故在此重组成三段式。 */\n    var BIZ = ["scope","textbook_reference","original_question","related_text",\n               "related_vocabulary","related_grammar","related_listening",\n               "ai_rules","answer_note"];\n    var evidence = {}, scope = raw.scope || {};\n    for(var i = 0; i < BIZ.length; i++){\n      var k = BIZ[i];\n      if(raw[k] !== undefined && raw[k] !== null) evidence[k] = raw[k];\n    }\n    var oq = raw.original_question || {};\n    var question = {\n      question_type: oq.question_type || null,\n      answer_kind: "ai_eval",\n      prompt: {\n        instruction: oq.instruction || (raw.textbook_reference || {}).instruction || "",\n        text: oq.text || ""\n      }\n    };\n    return {\n      question: question,\n      picked: raw._picked || "",\n      evidence: evidence,\n      granularity: raw._granularity || null,\n      question_id: raw._question_id,\n      section: scope.section || ""\n    };\n  }\n  function tryGrade(){\n    var b = fb(); if(!b) return;\n    if(!(window.ZxAi && typeof window.ZxAi.grade === "function")){ keepOriginal("AI 暂不可用"); return; }\n    var p = payload();\n    if(!p){ keepOriginal("未取得教材证据"); return; }\n    setBusy(true);\n    try { window.ZxAi.grade(JSON.stringify(p)); }\n    catch(e){ keepOriginal("调用失败"); }\n  }\n  if(document.readyState === "loading"){ document.addEventListener("DOMContentLoaded", tryGrade); } else { tryGrade(); }\n})();\n</script>'

P5_RECORD_SCRIPT = """<script>
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
  var SILENCE_LIMIT_MS = 1100;    /* 连续静音 >=1.1s -> 自动结束录音（与 Demo 同参数） */
  var SILENCE_LEVEL = 8;
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
  function finish(){
    toIdle();
    stopTracks();
    stopMeter();
    say('');
    if (discarding){ discarding = false; chunks = []; return; }
    var blob = new Blob(chunks, { type: (rec && rec.mimeType) || 'audio/webm' });
    chunks = [];
    if (!blob.size) return;
    if (blobUrl){ try { URL.revokeObjectURL(blobUrl); } catch (e) {} }
    blobUrl = URL.createObjectURL(blob);
    audioEl.src = blobUrl;
    if (replay) replay.disabled = false;   /* 只启用按钮：是否回放由孩子决定 */
    /* 2026-10-01（跟读记录）：跟读"完成" = **录完音即算**。
       历史原因：「我读完了」按钮与其 done_<qid> 字段在 P6-B-8 被移除后，
       跟读再也不产生任何 learning_record（实测设备库 activity_type='repeat' = 0）。
       现在在"录音真正结束且音频非空"这一确定时刻，向 /read/repeat POST 一次；
       后端写 activity_type='repeat' + result='done'（**不是判断证据**，不影响正确率）。
       失败一律静默：**绝不阻断跟读**（宁可少一条记录，不可挡住孩子）。 */
    try {
      if (window.__zxRepeatUrl){
        var card = document.querySelector('#zx-swipe .card-w');
        var idx = (card && card.getAttribute('data-i')) || '0';
        var body = new URLSearchParams();
        body.set('i', idx);
        body.set('mode', window.__zxRepeatMode || '');
        fetch(window.__zxRepeatUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: body.toString(),
          keepalive: true
        }).then(function(r){ return r.json(); })
          .then(function(d){
            if (d && d.recorded) say('已记录这次朗读');
          }).catch(function(){});
      }
    } catch (e) {}
  }
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
      for (var i = 0; i < buf.length; i++){ var d = Math.abs(buf[i] - 128); if (d > peak) peak = d; }
      if (peak >= SILENCE_LEVEL){ silentMs = 0; barsAt(5 + Math.round(Math.min(1, peak / 60) * 9)); return; }
      silentMs += STEP_MS;
      if (silentMs >= SILENCE_LIMIT_MS){ try { rec.stop(); } catch (e) {} }
    }, STEP_MS);
  }
  function start(){
    if (recording){ try { rec.stop(); } catch (e) {} return; }
    if (!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder)){
      say('这个设备暂时不能录音。'); return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function(s){
      stream = s;
      rec = new MediaRecorder(stream);
      chunks = [];
      rec.ondataavailable = function(e){ if (e.data && e.data.size) chunks.push(e.data); };
      rec.onstop = finish;
      clearClip();
      rec.start();
      recording = true;
      discarding = false;
      mic.classList.add('rec');
      say('');
      startMeter();
    }).catch(function(e){
      var zxName = (e && e.name) ? e.name : '未知';
      var zxMsg  = (e && e.message) ? e.message : '';
      try { console.log('ZXMIC ' + zxName + ' | ' + zxMsg
        + ' | secureContext=' + window.isSecureContext
        + ' | mediaDevices=' + (!!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia))
        + ' | MediaRecorder=' + (typeof window.MediaRecorder)
        + ' | proto=' + location.protocol); } catch (x) {}
      var hint;
      switch (zxName) {
        case 'NotAllowedError':
          hint = '麦克风权限被拒绝。请在系统设置中允许本应用使用麦克风后重试。'; break;
        case 'NotReadableError':
          hint = '其他应用可能正在使用麦克风，请关闭后重试。'; break;
        case 'NotFoundError':
          hint = '未找到麦克风设备。'; break;
        case 'AbortError':
          hint = '录音被中断，请重试。'; break;
        default:
          hint = '录音失败（' + zxName + '），请重试。';
      }
      say(hint);
    });
  }
  mic.addEventListener('click', start);
  replay.addEventListener('click', function(){
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


#: P5 入口内部的练习方式切换（沿用首页色块入口的视觉，不新造组件）
_P5_READ_MODES = (("word", "单词跟读"), ("sentences", "短句跟读"))
_P5_LISTEN_MODES = (("word", "单词听辨"), ("sentence", "句子听辨"))
#: 「词形练习」内部模式（2026-09-30 合并）：音标写词（默认）+ 词形变化
_P5_WORDFORM_MODES = (("phonetic", "音标写词"), ("form", "词形变化"))
_MODE_TINTS = ("e-word", "e-quiz", "e-phrase")


def _p5_lesson_qs(lesson_key, sep="&"):
    """P6-B-UI-RESTORE-05：把首页选中的 Lesson（section_key）显式带进 P5 内部链接。

    只补 URL 参数，不改任何布局/样式：入口内翻页、换 mode、回到首页、结果页都
    沿用同一个 Lesson，不再只靠 Cookie 隐式继承。
    """
    key = (lesson_key or "").strip()
    return ("%slesson=%s" % (sep, urllib.parse.quote(key))) if key else ""


def p5_mode_bar(unit, entry, mode, lesson_key=""):
    if entry == "read":
        items = _P5_READ_MODES
        default = "word"
    elif entry == "listen":
        items = _P5_LISTEN_MODES
        default = "word"
    elif entry == "wordform":
        items = _P5_WORDFORM_MODES
        default = "phonetic"
    else:
        return ""
    active = mode or default
    out = []
    for i, (key, label) in enumerate(items):
        tint = _MODE_TINTS[i % len(_MODE_TINTS)]
        on = " on" if key == active else ""
        cls = " e-word" if key == "word" else ""
        href = "/unit/%s/p5/%s?mode=%s%s" % (unit["slug"], entry, key,
                                             _p5_lesson_qs(lesson_key))
        out.append('<a class="mode %s%s" href="%s"><button class="secondary" '
                   'type="button">%s</button></a>'
                   % (tint, on, html.escape(href), html.escape(label)))
    return '<div class="modes">%s</div>' % "".join(out)


def _p5_review(unit, entry, index, mode="", lesson_key=""):
    """一屏一项：返回上一条 / 进入下一条（始终留在同一个入口里）。"""
    q = "i=%d" % index
    if mode:
        q += "&mode=%s" % mode
    q += _p5_lesson_qs(lesson_key)
    return "/unit/%s/p5/%s?%s" % (unit["slug"], entry, q)


def _p5_result_href(unit, entry, mode="", lesson_key=""):
    href = "/unit/%s/p5/%s/result" % (unit["slug"], entry)
    if mode:
        href += "?mode=%s" % mode
        href += _p5_lesson_qs(lesson_key)
        return href
    return href + (("?" + _p5_lesson_qs(lesson_key, sep="")) if (lesson_key or "").strip()
                   else "")


def _p5_big_speaker(url, start_ms=None, end_ms=None):
    """Demo 的大圆播放入口（118px 圆 + 三声波）；行为由 P5_SEGMENT_SCRIPT 负责。"""
    if not url:
        return ""
    attrs = ' data-autoplay="1" data-audio="%s"' % html.escape(str(url))
    if start_ms is not None:
        attrs += ' data-start="%d"' % int(start_ms)
    if end_ms is not None:
        attrs += ' data-end="%d"' % int(end_ms)
    return ('<div class="soundstage"><button class="spkbig" type="button"%s '
            'aria-label="播放这条教材音频">%s'
            '<span class="wave"><i></i><i></i><i></i></span></button></div>'
            % (attrs, icon("speaker")))


def _p5_options(item, picked=None, feedback=False):
    """选项作答区：未作答是可提交选项；已作答显示对错（Demo 的 .opt2）。"""
    q = item["question"]
    field = "q_%s" % item["question_id"]
    answer = (q.get("answer") or {}).get("key")
    out = []
    for o in (q.get("options") or []):
        key = o.get("key")
        if feedback:
            cls = "opt2"
            if key == answer:
                cls += " ok"
            elif key == picked:
                cls += " bad"
            out.append('<button class="%s" type="button"><span class="k">%s</span>'
                       '<span>%s</span></button>'
                       % (cls, html.escape(str(key).upper()), html.escape(o.get("text") or "")))
        else:
            out.append('<button class="opt2" type="submit" name="%s" value="%s">'
                       '<span class="k">%s</span><span>%s</span></button>'
                       % (html.escape(field), html.escape(key),
                          html.escape(str(key).upper()), html.escape(o.get("text") or "")))
    return '<div class="opts">%s</div>' % "".join(out)


#: 「AI 老师」**讲解**的题型清单（V1.3 第二十九章 §18，2026-09-29）。
#: **判据用 question_type，不得只看 answer_kind**（旧实现只看 answer_kind，会把孤立拼写一起放行）。
P5_TEACH_TYPES = (
    "textbook_native", "sentence_listen_write", "sentence_listen_choice",
    "listening_choice", "listen_choice", "listen_fill", "reading_choice",
    "vocab_context_choice", "phrase_meaning_choice", "vocab_listen_write",
    "vocab_meaning_choice", "vocab_word_form", "phonetics_sound_choice",
)
#: **少讲（暂不触发）**：孤立拼写类（§17「孤立拼写少补」同口径）。
P5_TEACH_LOW_PRIORITY_TYPES = ("vocab_phonetic_write", "phonetics_symbol_write")
#: **不讲**：无"答错"概念 / 无对错（另 `read` 入口天然无判分，也走不到本函数）。
P5_TEACH_EXCLUDED_KINDS = ("ai_eval", "self_assess")
#: 下发给 AI 的教材句池字段（只给教材原句 + 出处，不给整包）
P5_TEACH_EVIDENCE_FIELDS = ("related_text", "related_vocabulary", "textbook_reference")


def _p5_teach_payload(item, picked, right, ctx):
    """「AI 老师」数据下发（第一步：**只下发，不调 AI**）。

    返回一段 `<script id="zx-teach" type="application/json">`；不适用时返回 ""。
    复用 J1 的「非可执行脚本 + json.dumps 转义」做法（避免注入面），不新建机制。

    不下发的情况（按 V1.3 第二十九章 §18 / §19，2026-09-29 实现）：
      * `answer_kind` 属 P5_TEACH_EXCLUDED_KINDS（ai_eval 无"答错"概念 / self_assess 无对错）；
      * `question_type` 不在 P5_TEACH_TYPES（含**孤立拼写** P5_TEACH_LOW_PRIORITY_TYPES，少讲）；
      * `unit_code` 与 `section_key` **皆为空**（划不出范围，不猜）。
    范围锚点：`scope_anchor_kind` = "section"（有 section_key，值为 section_key）
             或 "unit"（Unit 级兜底，`scope_anchor_value` 为 unit_code）。
    """
    q = item["question"]
    # ① 触发判据：**按题型清单**（V1.3 §18），不再只看 answer_kind。
    qtype = (q.get("question_type") or "").strip()
    if (q.get("answer_kind") or "") in P5_TEACH_EXCLUDED_KINDS:
        return ""
    if qtype in P5_TEACH_LOW_PRIORITY_TYPES:
        return ""                                    # 孤立拼写：少讲，暂不触发
    if qtype not in P5_TEACH_TYPES:
        return ""                                    # 不在讲解清单内
    # ② 范围锚点：**按题型粒度分派**（V1.3 §19 第 3 条）。
    unit_code = (q.get("unit_code") or q.get("unit") or "").strip()
    section_key = (q.get("section_key") or "").strip()
    if not unit_code and not section_key:
        return ""                                    # 两者皆空：划不出范围，不讲
    anchor_kind = "section" if section_key else "unit"
    anchor_value = section_key or unit_code
    ev = (ctx or {}).get("ai_evidence") or {}
    pkg = ev.get("package") or {}
    pool = {k: pkg.get(k) for k in P5_TEACH_EVIDENCE_FIELDS if pkg.get(k) is not None}
    prompt = q.get("prompt") or {}
    data = {
        "_question_id": item.get("question_id"),
        # question_type：**题型族分派**的判据（V1.3 §19 第 4 条 / 流程规范 §27）——
        # 取 question 表字段（细粒度，如 vocab_word_form），不取 prompt_json 的活动内类型。
        "question_type": (q.get("question_type") or prompt.get("question_type") or ""),
        "instruction": prompt.get("instruction") or "",
        "text": prompt.get("text") or "",
        "options": q.get("options") or [],
        "picked": picked,
        "answer": right,
        "unit_code": unit_code,
        "section_key": section_key,
        # 范围锚点（V1.3 §19）：Section 级题型用 section_key；Unit 级题型用 unit_code 兜底。
        "scope_anchor_kind": anchor_kind,
        "scope_anchor_value": anchor_value,
        "_granularity": ev.get("granularity"),
        "_resolved_via": ev.get("resolved_via"),
        "evidence_pool": pool,
    }
    body = json.dumps(data, ensure_ascii=False, sort_keys=True)
    body = body.replace("<", "\\u003c").replace(">", "\\u003e")
    return '<script id="zx-teach" type="application/json">%s</script>' % body


def _p5_feedback(item, picked, result, ctx=None):
    """即时反馈：只用正式判分结果，不编造评价。"""
    q = item["question"]
    ans = q.get("answer") or {}
    right = ans.get("text") or ans.get("key") or ""
    if result == "correct":
        return ('<div class="fb show ok"><b>答对了。</b></div>')
    if result == "done":
        return ""
    if result == "needs_review":
        # V1.3 §七·9：该题没有可靠答案事实（answer_kind=ai_eval）-> 暂不判分。
        # 刻意**不显示"正确答案："**（该题的 answer_json 为空，会渲染成空白）。
        # 待批改的 AI 反馈由批次 4 的桥在同一位置注入。
        return ('<div class="fb show" id="zx-ai-fb">'
                '<b>需要 AI 批改，暂时先不打分。</b></div>')
    teach_script = _p5_teach_payload(item, picked, right, ctx)
    # 「AI 老师」三句话的显示容器（第二步 ZxAiBridge.teach -> window.__zxTeachOnResult 的落点）。
    # 空容器：AI 未接入 / 失败时保持为空，页面与现在完全一致（不阻断、不报错）。
    teach_fb = '<div id="zx-teach-fb"></div>'
    # 2026-10-01（UI-7 第 5+6 件）：答错提示文案**按作答形式分派**（同一处的两个分支）：
    #   * 选项题（answer_kind=option_key）：**不再给文字提示** —— 选项自身已有对错视觉
    #     （`.opt2.ok` 绿 / `.opt2.bad` 红 + 勾叉标记），再叠一句文字是重复信息；
    #   * 输入题：**只报正确答案**，不再重复孩子刚填的内容（孩子自己知道填了什么）。
    if (q.get("answer_kind") or "") == "option_key":
        return "%s%s" % (teach_fb, teach_script)
    if not str(right or "").strip():
        # 没有可靠答案事实时**不显示"正确答案是"**（避免渲染成空白），只保留 AI 讲解位。
        return "%s%s" % (teach_fb, teach_script)
    return ('<div class="fb show warn"><b>正确答案是 %s。</b></div>%s%s'
            % (html.escape(str(right)), teach_fb, teach_script))


def _p5_input(item, picked="", feedback=False):
    q = item["question"]
    field = "q_%s" % item["question_id"]
    return ('<input class="typebox" type="text" name="%s" value="%s" autocomplete="off" '
            'autocapitalize="off" spellcheck="false">'
            % (html.escape(field), html.escape(picked if feedback else "")))


def _p5_read_page(ctx, unit, label, items, index, mode, name_field):
    """跟读练习：一项一屏 + 左右滑动 + 滑到即自动播放 + 录音 + 我的朗读（Demo 结构）。"""
    slug = html.escape(unit["slug"])
    cards = []
    for i, m in enumerate(items):
        if m.get("phonetic") or m.get("meaning"):      # 单词跟读：词 + 音标 + 中文（缺则自然隐藏）
            inner = '<div class="w">%s</div>' % html.escape(m.get("text") or "")
            if m.get("phonetic"):
                inner += '<div class="phon">%s</div>' % html.escape(m["phonetic"])
            if m.get("meaning"):
                inner += '<div class="mean">%s</div>' % html.escape(m["meaning"])
            if m.get("part_of_speech"):
                inner += '<div class="pos">%s</div>' % html.escape(m["part_of_speech"])
        else:                                          # 短句跟读：教材原句
            inner = '<div class="sent">%s</div>' % html.escape(m.get("text") or "")
        cards.append('<section class="card-w" data-i="%d" data-audio="%s" data-start="%d" '
                     'data-end="%d">%s</section>'
                     % (i, html.escape(m.get("audio_url") or ""),
                        int(m.get("start_ms") or 0), int(m.get("end_ms") or 0), inner))
    cur = items[index] if items else {}
    play = ('<button class="op" type="button" id="zx-play" data-autoplay="1" '
            'data-audio="%s" data-start="%d" data-end="%d" aria-label="听教材原音">%s'
            '<span class="wave"><i></i><i></i><i></i></span></button>'
            % (html.escape(cur.get("audio_url") or ""), int(cur.get("start_ms") or 0),
               int(cur.get("end_ms") or 0), icon("speaker")))
    # P6-B-8：删除「我读完了」按钮及其 done_<qid> 隐藏字段（Demo 跟读页没有完成按钮）
    # 无 mode（URL 未带）时与 p5_mode_bar 的默认一致：read 默认 word。
    hint = "左右滑动切换单词" if (mode or "word") == "word" else "左右滑动切换句子"
    body = """%s
<main>
  %s
  %s
  <div class="lesson"><div class="swipe" id="zx-swipe" data-unit="句">%s</div></div>
  <p class="swipe-hint">%s</p>
  <p id="zx-recstate" style="text-align:center;color:var(--text2);margin:8px 0 0"></p>
  <audio id="zx-myrec" controls preload="none" style="width:100%%;display:none"></audio>
  <div class="opsbar">
    %s
    <button class="mic" type="button" id="zx-mic" data-ico-mic="%s" data-ico-stop="%s">%s<span class="wave"><i></i><i></i><i></i></span></button>
    <button class="op" type="button" id="zx-replay" disabled aria-label="我的朗读">%s</button>
  </div>
</main>%s%s%s""" % (header(label, _p5_meta(unit, label),
                           back_href="/unit/%s" % unit["slug"],
                           back_label="返回单元中心"),
                  p5_mode_bar(unit, ctx["entry"], mode, ctx.get("lesson_key")),
                  step_bar(index + 1, max(1, int(ctx.get("lesson_question_total") or len(items)))),
                  "".join(cards), hint, play,
                   html.escape(icon("mic"), quote=True), html.escape(icon("stop"), quote=True),
                   icon("mic"), icon("play"),
                   P5_SEGMENT_SCRIPT,
                   P5_SWIPE_SCRIPT, P5_RECORD_SCRIPT)
    # 2026-10-01（跟读记录）：把 repeat 端点注入页面，供 P5_RECORD_SCRIPT.finish() 调用。
    # 用 str.replace 注入到第一个 <script> 之前，**不新增模板占位符**（不破坏既有 % 格式化）。
    # 注意：`_p5_lesson_qs` 只产出 `&lesson=…`（不含 `?`）⇒ 这里必须自己补 `?`。
    # 真机实测：漏了 `?` 会拼成 `/read/repeat&lesson=…`，被 `/submit` 路由吃掉并返回 not found。
    _lqs = _p5_lesson_qs((ctx.get("lesson_key") or "").strip())
    _repeat_url = "/unit/%s/p5/read/repeat%s" % (
        unit["slug"], ("?" + _lqs.lstrip("&")) if _lqs else "")
    # `read` 页在 URL 未带 mode 时实际按 word 生效（与 p5_mode_bar 的默认一致），
    # 这里必须注入**实际生效**的模式，否则后端会收到空 mode。
    _eff_mode = mode or ("word" if ctx.get("entry") == "read" else "")
    _inject = ('<script>window.__zxRepeatUrl=%s;window.__zxRepeatMode=%s;</script>'
               % (json.dumps(_repeat_url), json.dumps(_eff_mode)))
    body = body.replace("<script>", _inject + "<script>", 1)
    return layout("%s · %s" % (label, PRODUCT_NAME), body)


def _p5_question_page(ctx, unit, entry, label, items, index, mode, name_field):
    """听音辨意 / 音标写词 / 词形变化 / 本课检测 / 自主练习：一题一屏 + 即时反馈 + 下一题。"""
    slug = html.escape(unit["slug"])
    lesson_key = (ctx.get("lesson_key") or "").strip()
    # P6-B-UI-RESTORE-05：本屏的 Lesson 上下文（section_key）在链接与提交里显式携带
    # 单元中心一期：左上角返回统一改为「返回单元中心」。
    back = "/unit/%s" % slug
    submit_qs = ("?lesson=%s" % urllib.parse.quote(lesson_key)) if lesson_key else ""
    if not items:
        body = """%s
<main>
  <section class="card">
    <h2>%s</h2>
    <p class="meta">%s</p>
    <div class="row"><a href="/?unit=%s"><button class="secondary" type="button">回到首页</button></a></div>
  </section>
  <div class="foot">%s</div>
</main>""" % (header(label, _p5_meta(unit, label), back_href=back, back_label="返回单元中心"),
              html.escape(label), html.escape(P5_EMPTY_LINE), slug, html.escape(PRODUCT_NAME))
        return layout("%s · %s" % (label, PRODUCT_NAME), body)

    item = items[index]
    q = item["question"]
    prompt = q.get("prompt") or {}
    feedback = bool(ctx.get("feedback"))
    picked = ctx.get("picked") or ""
    result = ctx.get("result") or ""
    total = len(items)

    head = ""
    if entry == "listen":
        head = _p5_big_speaker(prompt.get("audio_url"), prompt.get("start_ms"),
                               prompt.get("end_ms"))
    elif entry == "phonetic" or (entry == "wordform" and (mode or "") != "form"):
        # 音标写词（2026-09-30 修复）：合并成「词形练习」后 entry 变为 wordform，
        # 原先只判断 entry == "phonetic" ⇒ 该分支永不命中 ⇒ 音标丢失。
        # 数据两种口径：vocab_phonetic_write 用 prompt.phonetic；
        # phonetics_symbol_write 的 prompt.phonetic 为 None，词形在 prompt.text（原「词」）。
        ph = (prompt.get("phonetic") or "").strip()
        word = (prompt.get("text") or q.get("base") or "").strip()
        head = '<p class="phbig">%s</p>' % html.escape(ph or word)
        if prompt.get("audio_url"):
            head += _p5_big_speaker(prompt.get("audio_url"), prompt.get("start_ms"),
                                    prompt.get("end_ms"))
    elif entry == "form" or (entry == "wordform" and (mode or "") == "form"):
        text = prompt.get("text") or ""
        base = q.get("base") or ""
        if base and "______" in text:
            text = text.replace("______", "______（%s）" % base, 1)
        head = '<p class="qstem">%s</p>' % html.escape(text)
    else:
        if prompt.get("audio_url"):
            head = _p5_big_speaker(prompt.get("audio_url"), prompt.get("start_ms"),
                                   prompt.get("end_ms"))
        if prompt.get("text"):
            head += '<p class="qstem">%s</p>' % html.escape(prompt["text"])

    if q.get("answer_kind") == "option_key":
        answer_area = _p5_options(item, picked, feedback)
    else:
        answer_area = _p5_input(item, picked, feedback)
    fb = _p5_feedback(item, picked, result, ctx) if feedback else ""

    # 修复：提交按钮**必须**在 <form> 内才会触发提交。
    # `foot` 只放"导航按钮"（下一题 / 看学习结果 / 再试一次）—— 它们用 href 跳转，
    # 本就在 </form> 之外，属正确用法；输入型页面的 submit 按钮改由
    # `submit_html` 承载并渲染在 </form> 之前（见 body 模板）。
    foot = ""
    submit_html = ""
    if feedback:
        if index + 1 < total:
            foot = ('<a href="%s"><button class="primary" type="button">下一题</button></a>'
                    % html.escape(_p5_review(unit, entry, index + 1, mode, lesson_key)))
        else:
            foot = ('<a href="%s"><button class="primary" type="button">看学习结果</button></a>'
                    % html.escape(_p5_result_href(unit, entry, mode, lesson_key)))
        if entry == "check":
            foot += ('<a href="%s"><button class="secondary" type="button">再试一次</button></a>'
                     % html.escape(_p5_review(unit, entry, index, mode, lesson_key)))
    elif q.get("answer_kind") != "option_key":
        # 输入型（listen/phonetic/form/practice）：提交按钮进 form 内
        submit_html = '<button class="primary" type="submit">提交</button>'

    fields = ['<input type="hidden" name="i" value="%d">' % index]
    if mode:
        fields.append('<input type="hidden" name="mode" value="%s">' % html.escape(mode))
    # 2026-10-01（UI-7 第 7 件）：**听音辨意不再显示题目自带说明**。
    # 原因：题库里 `vocab_listen_write` 的 `prompt.instruction` 是历史文案
    # 「听音写词：写出你听到的单词。」—— 该模式早已并入「听音辨意」；
    # 大扬声器 + 输入框本身已表达"听音频写单词"，再挂一句旧说明属重复且过期信息。
    # **不改题库**（那是正式数据）：只在渲染层不再输出该 meta。
    instruction = ""
    qclass = "listen" if entry == "listen" else "qcenter"
    foot_html = ('<div class="qfoot">%s</div>' % foot) if foot else ""
    # J1（批次 1+2+4·d）：`ai_eval` 题下发教材证据包（只给白名单字段）。
    # 用 <script type="application/json"> 承载 —— **不是**可执行脚本，避免注入面；
    # 内容由 json.dumps 转义（含 `</script>` 也会被转义成 \u003c/script\u003e）。
    evidence_script = ""
    ev = ctx.get("ai_evidence") or {}
    if q.get("answer_kind") == "ai_eval" and ev.get("package"):
        payload = {k: ev["package"].get(k) for k in P5_EVIDENCE_FIELDS
                   if ev["package"].get(k) is not None}
        payload["_granularity"] = ev.get("granularity")
        payload["_resolved_via"] = ev.get("resolved_via")
        payload["_question_id"] = item.get("question_id")
        payload["_picked"] = picked
        evidence_script = ('<script id="zx-evidence" type="application/json">%s</script>'
                           % json.dumps(payload, ensure_ascii=False, sort_keys=True)
                           .replace("<", "\\u003c").replace(">", "\\u003e"))

    body = """%s
<main>
  %s
  %s
  <section class="qwrap %s">
    <div class="qbody">
      <div class="qmain">
        %s
        %s
        <form method="post" action="/unit/%s/p5/%s/submit%s">
          <input type="hidden" name="mode" value="%s">
          %s
          %s
          %s
          %s
          %s
        </form>
      </div>
    </div>
    %s
  </section>
</main>%s%s%s""" % (header(label, _p5_meta(unit, label), back_href=back, back_label="返回单元中心"),
                # 2026-10-01（UI-7 第 4 件）：分母改用**当前课时题目数**（由 app 预算后经
                # ctx["lesson_question_total"] 传入）；取不到时退回池大小（与旧行为一致）。
                p5_mode_bar(unit, entry, mode, lesson_key),
                step_bar(index + 1, max(1, int(ctx.get("lesson_question_total") or total))),
                qclass, head, instruction,
                slug, html.escape(entry), submit_qs,
                html.escape(mode or ""),
                "".join(fields), name_field, answer_area, fb, submit_html, foot_html,
                P5_SEGMENT_SCRIPT, evidence_script,
                P5_AI_BRIDGE_JS)   # 桥 JS 必须注入，否则 __zxTeachOnResult / __zxAiOnResult 均为 undefined
    return layout("%s · %s" % (label, PRODUCT_NAME), body)


def p5_result_page(ctx: dict) -> str:
    """本次结果：只如实陈述这一次作答的事实，不做分数与排名。"""
    unit, label = ctx["unit"], ctx["label"]
    lesson_key = (ctx.get("lesson_key") or "").strip()      # P6-B-UI-RESTORE-05：沿用同一 Lesson
    lqs = _p5_lesson_qs(lesson_key)
    rows = []
    for r in ctx["results"]:
        cls = {"correct": "ok", "incorrect": "again", "done": "ok"}.get(r.get("result"), "")
        if r.get("result") == "correct":
            head = "答对了"
        elif r.get("result") == "incorrect":
            head = "再试一次"
        elif r.get("result") == "done":
            head = "已经读过"
        elif r.get("result") == "needs_review":
            # 无可靠答案事实：不判对错、不显示"正确答案"（answer_text 为空）
            head = "需要 AI 批改"
        else:
            head = "这一次没有作答"
        detail = []
        if r.get("text"):                      # 入口级事实陈述（来自正式学习证据，不评分）
            detail.append(r["text"])
        if r.get("answer_text"):
            detail.append("正确答案：%s" % r["answer_text"])
        if r.get("picked"):
            detail.append("我的作答：%s" % r["picked"])
        rows.append('<div class="qfb %s"><div class="j">%s</div><div class="aux">%s</div></div>'
                    % (cls, html.escape(head), html.escape("；".join(detail))))
    body = """%s
<main>
  <section class="card">
    <h2>%s</h2>
    %s
  </section>
  <div class="row">
    <a href="/unit/%s/p5/%s%s"><button class="primary" type="button">再做一次</button></a>
    <a href="/unit/%s"><button class="secondary" type="button">返回单元中心</button></a>
  </div>
  <div class="foot">%s</div>
</main>""" % (header(label, _p5_meta(unit, label),
                    back_href="/unit/%s" % unit["slug"],
                    back_label="返回单元中心"),
              html.escape(label), "".join(rows) or '<p class="meta">这一次还没有作答记录。</p>',
              html.escape(unit["slug"]), html.escape(ctx["entry"]), lqs,
              html.escape(unit["slug"]),
              html.escape(PRODUCT_NAME))
    return layout("%s · %s" % (label, PRODUCT_NAME), body)

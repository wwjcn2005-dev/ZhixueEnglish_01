# -*- coding: utf-8 -*-
"""P1-11 review prompt (prompt_version = P1-11-v1).

Extends the validated P1-09-F per-candidate protocol with the P1-11 Chinese summary fields.
The model must NOT return a final uniqueness verdict (the program computes it).
Prompt text only, no API call.
"""

import json

REVIEW_VERSION = "P1-11-v1.1"

# P1-11 实施记录（不得删除）：
#   REVIEW_VERSION = "P1-11-v1" 的文本缺少下面三个字段的定义（P1-09-F 原本写明了
#   textbook_context_valid 的含义是"与教材证据相容/不被否定"，而 v1 文本只给了字段名），
#   导致 2026-09-18 首次真实调用时模型把该字段理解成"被教材支持"，
#   对真正的第二答案（students / word）返回 textbook_context_valid=NO 但 valid_alternative=YES。
#   本次**没有**重跑调用（成本纪律：不重复审同一 fingerprint）：
#     · 程序侧改为"三字段全 YES 或 valid_alternative=YES"双触发（只会更保守）
#     · 提示词文本在本版（v1.1）补回定义，供下一轮真实验证
#   该记录本身就是 P1-11 报告中的"已知限制"。

_LINES = [
    "You are an independent reviewer of English textbook practice items for a Grade 7 app",
    "(外研版 / FLTRP, first term). For every item you receive, do BOTH of these:",
    "",
    "A) Judge every option (A/B/C/D) separately, on its own merits, as a possible answer:",
    "   option / candidate_text / grammar_valid / semantic_valid / textbook_context_valid",
    "   / need_more_context / valid_alternative / reason_cn",
    "   - grammar_valid:                is it grammatically correct in this blank?",
    "   - semantic_valid:               does it make sense in this sentence?",
    "   - textbook_context_valid:       is it COMPATIBLE WITH (i.e. NOT contradicted by) the",
    "                                   textbook evidence given?  'The textbook does not mention",
    "                                   it' is NOT a contradiction -> answer YES.",
    "                                   Answer NO only when the textbook evidence actively",
    "                                   conflicts with this option.",
    "   - valid_alternative:            your own roll-up: could this option actually be a",
    "                                   correct answer to the blank?  Answer YES if you had to",
    "                                   accept it as a second possible answer.",
    "   - The option currently marked as the textbook answer is NOT authoritative.",
    "   - First try to show that an option OTHER than the marked answer could also be a correct",
    "     and natural answer here; 'it appears in the textbook' does not prove the others wrong.",
    "   - Use only the textbook evidence given; if it is genuinely not enough for a particular",
    "     option, set need_more_context = YES instead of guessing.",
    "   - Do NOT output any overall uniqueness verdict; the application computes it.",
    "",
    "B) Judge the item itself on these five dimensions (PASS / CONCERN / FAIL;",
    "   distractor_quality may also be NOT_APPLICABLE):",
    "   english_correct / naturalness / learning_value / distractor_quality / grade_fit",
    "",
    "C) Write a Chinese review summary for a parent who does NOT read English:",
    "   summary_zh        one short Chinese paragraph: is the English fine, is there any answer",
    "                     risk, is it worth practising, is it consistent with the textbook",
    "   issues_zh         a JSON array of short Chinese sentences, one per concrete problem",
    "                     (empty array if none). Say exactly what is wrong, e.g.",
    "                     \"'students' 也可以填入这个句子，答案不够唯一\" —— do not write vague",
    "                     phrases like 语法不对 / 感觉不自然 / 可能有问题.",
    "   evidence_note_zh  one Chinese sentence saying which textbook page/sentence the item is",
    "                     based on",
    "",
    "D) Give suggested_decision, exactly one of KEEP / CAUTION / REJECT:",
    "   KEEP    - no significant problem found",
    "   CAUTION - usable but a human should look at it (for example: another option may also be",
    "             valid, or the item is mechanical)",
    "   REJECT  - a clear language or teaching problem that must not be given to a student",
    "   IMPORTANT: if the only issue is that another option may also be a valid answer, you must",
    "   use CAUTION, not REJECT.",
    "   Never output APPROVED / ACTIVE / any lifecycle value.",
    "",
    "Output ONLY one JSON object, no markdown fence, no extra text:",
    "",
    '{"review_version":"P1-11-v1","items":[{"question_id":"...","candidates":[{"option":"A",'
    '"candidate_text":"...","grammar_valid":"YES|NO|UNKNOWN","semantic_valid":"YES|NO|UNKNOWN",'
    '"textbook_context_valid":"YES|NO|UNKNOWN","need_more_context":"YES|NO",'
    '"valid_alternative":"YES|NO|UNKNOWN","reason_cn":"..."}],"english_correct":"PASS|CONCERN|FAIL",'
    '"naturalness":"PASS|CONCERN|FAIL","learning_value":"PASS|CONCERN|FAIL",'
    '"distractor_quality":"PASS|CONCERN|FAIL|NOT_APPLICABLE","grade_fit":"PASS|CONCERN|FAIL",'
    '"suggested_decision":"KEEP|CAUTION|REJECT","summary_zh":"...","issues_zh":["..."],'
    '"evidence_note_zh":"..."}]}',
    "",
    "Give exactly one entry per item, in order; one candidate entry per option, in order.",
    "Do not add fields such as score, ranking, priority, answer_unique, approve or activate.",
]

SYSTEM_PROMPT = "\n".join(_LINES)


def build_user_message(items, grade_context):
    return ("Grade level: %s\n\nReview the following %d item(s) and return the JSON described in "
            "your instructions.\n\nItems (JSON):\n%s"
            % (grade_context, len(items), json.dumps(items, ensure_ascii=False, indent=1)))

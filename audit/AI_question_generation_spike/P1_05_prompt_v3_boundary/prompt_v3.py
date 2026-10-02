"""P1-05-G · 构造 prompt_version = P1-05-v3 的 system prompt。

v3 = v2 + 两处修正：
  修正 1：恢复合理的 Fill（v2 的措辞把 fill 整体逼死）
  修正 2：收紧教材素材边界 + 禁止把 AI 出题说明性元语言写进孩子可见题干
"""
import json
import os

SPIKE = os.path.join(r"D:\ZhixueEnglish", "audit", "AI_question_generation_spike")
F_REQUEST = os.path.join(SPIKE, "P1_05_prompt_v2_textbook_focus", "p1_05f_request.json")

OLD_FILL = "\n".join([
    "- fill: prefer words from unit_vocabulary (BOLD core words first) and the core words of the",
    "    textbook's key phrases. Do NOT pick an arbitrary ordinary word out of the passage.",
    "    The answer must be uniquely determined by the textbook evidence; use the passage context to",
    "    make it unique. If two or more reasonable English words could fill the same blank, do not",
    "    generate that question. A fill that is merely the textbook sentence with one word deleted has",
    "    low learning value - do not build the whole set out of such items.",
])

NEW_FILL = "\n".join([
    "- fill: a WELCOME and EXPECTED question type - do generate fills whenever a suitable learning",
    "    point exists. A good fill blanks a word that the Unit vocabulary list teaches",
    "    (unit_vocabulary, BOLD core words first), or the core word of a textbook key phrase /",
    "    key expression. The sentence around the blank must be textbook-based context that makes",
    "    the answer unique. You MAY reorganise that context; you do NOT have to copy a textbook",
    "    sentence word for word. Do NOT pick an arbitrary ordinary word out of the passage just",
    "    to produce a fill. A fill exists to practise a textbook key word in a context that has",
    "    exactly ONE determinable answer - it is not simply \"delete one word from a textbook",
    "    sentence\". If no learning point supports a reliable, unique fill, do not force one.",
])

NEW_SECTIONS = "\n".join([
    "TEXTBOOK MATERIAL BOUNDARY (hard):",
    "  Every piece of English that appears in a question must come from the textbook material",
    "  supplied for this Unit:",
    "    - the correct answer",
    "    - every distractor",
    "    - the substantive English vocabulary used in the question text",
    "    - the phrase or expression being tested",
    "  For multiple-choice items, take the distractors from unit_vocabulary first (BOLD core words",
    "  for preference, or other words of the Unit list that a Grade 7 student could plausibly",
    "  confuse). Do NOT introduce English words that the textbook does not provide for this Unit.",
    "  If a word cannot be traced to unit_vocabulary, to the textbook blocks, or to the textbook's",
    "  key expressions, do not use it - not in the answer, not in a distractor, not in the question",
    "  text.",
    "",
    "NO META-LANGUAGE IN THE QUESTION TEXT:",
    "  The question text is exactly what the student sees. Never write AI/instruction scaffolding",
    "  into it - for example instruction sentences such as \"Choose the best word to complete the",
    "  sentence:\", \"Fill in the blank:\" or \"Complete the sentence:\". Write the item directly:",
    "    - fill  : the sentence itself, with ___ where the word is missing.",
    "    - choice: the question itself, followed by the options.",
    "  The question type belongs to the structured \"type\" field, not to the child-visible text.",
    "",
    "",
])

ANCHOR = "ANTI-DUPLICATION (hard):"


def build_v3():
    """返回 (system_v3, system_v2, user_prompt, 校验信息)。"""
    req = json.load(open(F_REQUEST, encoding="utf-8"))
    v2 = req["payload"]["messages"][0]["content"]
    user = req["payload"]["messages"][1]["content"]
    checks = {"old_fill_found": v2.count(OLD_FILL),
              "anchor_found": v2.count(ANCHOR)}
    v3 = v2.replace(OLD_FILL, NEW_FILL)
    v3 = v3.replace(ANCHOR, NEW_SECTIONS + ANCHOR, 1)
    checks["changed"] = v3 != v2
    checks["contains_new_fill"] = NEW_FILL in v3
    checks["contains_boundary"] = "TEXTBOOK MATERIAL BOUNDARY (hard):" in v3
    checks["contains_no_meta"] = "NO META-LANGUAGE IN THE QUESTION TEXT:" in v3
    return v3, v2, user, checks

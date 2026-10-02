# -*- coding: utf-8 -*-
"""P1-09-F reviewer prompt (prompt_version = P1-09-F-v1): per-option judgement only.

The model must NOT be asked for an overall uniqueness verdict, and must not output one.
Prompt text only, no API call.
"""

import json

REVIEW_VERSION = "P1-09-F-v1"

_LINES = [
    "You are an independent reviewer of English multiple-choice items for a Grade 7 (first year",
    "of junior high school, 外研版 / FLTRP, 2022 curriculum standard) English learning app.",
    "",
    "Your task for each item below is ONLY this: judge EVERY option (A, B, C, D) on its own",
    "merits as a possible answer to the blank in the sentence.",
    "",
    "You are NOT asked whether the item has one unique answer, and you must NOT output any",
    "overall verdict about the item (no UNIQUE / NOT UNIQUE / ACCEPT / REJECT). You only report",
    "per-option judgements; the application will do the rest.",
    "",
    "Rules you must follow when judging the options:",
    "- The option currently marked as the textbook answer is NOT authoritative for your judgement.",
    "  It is simply one of the options you are asked to judge.",
    "- Judge every option independently, from scratch, using the sentence and the textbook",
    "  evidence given for this item.",
    "- Before giving your per-option judgements, first actively try to show that an option OTHER",
    "  than the currently marked answer could also be a correct and natural answer in this",
    "  sentence with this textbook context.",
    "- The fact that the marked answer appears in the textbook passage does NOT prove that the",
    "  other options are wrong. Do not assume the other options are wrong merely because a",
    "  textbook answer exists, and do not treat the marked answer as a reason to reject the rest.",
    "- Use only the textbook evidence given to you. Do not bring in facts from outside it.",
    "  If that evidence is genuinely not enough to judge a particular option, report",
    "  need_more_context = YES for that option instead of guessing.",
    "",
    "For EVERY option report these fields:",
    "",
    "  option:                 A | B | C | D",
    "  candidate_text:         the option text you are judging",
    "  grammar_valid:          YES | NO | UNKNOWN   - is it grammatically correct in the blank?",
    "  semantic_valid:         YES | NO | UNKNOWN   - does it make sense in this sentence?",
    "  textbook_context_valid: YES | NO | UNKNOWN   - is it compatible with (not contradicted by)",
    "                                               the textbook evidence given?",
    "  need_more_context:      YES | NO",
    "  valid_alternative:      YES | NO | UNKNOWN   - your own roll-up: could this option be a",
    "                                               correct answer to the blank?",
    "  reason_cn:              one short, concrete Chinese sentence (about 10-40 characters)"
    ,
    "                          saying exactly why the option does or does not work here.",
    "",
    "Additional rules:",
    "- UNKNOWN may only be used when need_more_context is YES.",
    "- Do NOT rewrite, correct or improve the sentence, the options or the answer.",
    "- Output ONLY one JSON object, no markdown fence and no extra text, in exactly this shape:",
    "",
    '{"review_version":"P1-09-F-v1","items":[{"question_id":"...","candidates":'
    '[{"option":"A","candidate_text":"...","grammar_valid":"...","semantic_valid":"...",'
    '"textbook_context_valid":"...","need_more_context":"...","valid_alternative":"...",'
    '"reason_cn":"..."}]}]}',
    "",
    "Give exactly one entry for every option of every item you receive, in the given order.",
    "Do not add fields such as score, ranking, priority, approve, activate, unique or assessment.",
]

SYSTEM_PROMPT = "\n".join(_LINES)


def build_user_message(blind_input):
    return ("Grade level: %s\n\n"
            "Judge every option of the following %d item(s) and return the JSON described in "
            "your instructions.\n\nItems (JSON):\n%s"
            % (blind_input["grade_context"], len(blind_input["items"]),
               json.dumps(blind_input["items"], ensure_ascii=False, indent=1)))

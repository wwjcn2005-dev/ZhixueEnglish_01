# -*- coding: utf-8 -*-
"""P1-09-D: build the 15 human-designed boundary fixtures, the hidden gold store and the
blind AI input snapshot. No AI call here. No write to any database.

Rule: hidden_gold.json and fixtures.json are experimenter-side artifacts.
Only ai_input_snapshot.json is sent to the model, and it contains no gold information.
"""

import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
GRADE = "外研版初中英语 七年级上册（初一第一学期）"

# real textbook blocks (read-only from contentpack v5) used as context material
B37B10 = ("1\t Rock music is coming out of my computer.  As a rock music lover, I play the "
          "electric guitar in the school band. Sometimes I write songs and share them online. "
          "There is so much fun  in music. ")
B37B12 = ("hobby. But it’s a different kind of music.  He likes playing the erhu in the park "
          "with his friends. They sing Beijing opera together. There are many fans of them.")
B38B3 = ("5\t There is an art festival every autumn in my school. I decide to take part in it "
         "with Grandpa this year. After a week’s practice, we are on the stage.  I nod to "
         "Grandpa and we fire up our instruments. ")
B38B5 = ("6\t Grandpa gives me a big smile, and I smile back.  It feels great to enjoy our "
         "hobby together. ")
B22B0 = ("1\t Our English teacher Ms Chen writes the sentence on the blackboard and says, "
         "“Please write this down.” ")
B22B2 = ("3\t “That’s not right. But is it OK to point out the mistake? Is that polite, in the "
         "first lesson?” Questions jump into my mind.")
B24B1 = "(a)\t I look up at Ms Chen. My eyes meet hers."
B24B2 = ("(b)\t In fact, this is my first lesson for all of you."
         "Now find more sentences with this grammar in the reading passage. ")
B88B14 = "2  later. The trees in a rainforest can make their own rain. "
B88B20 = "Now we can see plants are so important. They mean so much to us."
B10B20 = "It’s grey."
B10B5 = ("\tNana:\t Hi, Wang Tao. What are you going to wear tomorrow for school? "
         "Wang Tao:\t My school uniform, of course. I’m going to wear a ")
B87B7 = "Water from the root will "
B85B12 = "root"


def blk(block_id, page, text):
    return {"block_id": block_id, "textbook_page": page, "text": text}


# ------------------------------------------------------------------------- fixtures
FIXTURES = [
    {
        "fixture_id": "FIX-A1", "category": "A_true_english_error", "subcategory": "主谓一致",
        "question_type": "fill", "fixture_only": True, "answer_standard": "TEXTBOOK_ANCHORED",
        "question": "Grandpa like playing the erhu in the park with his friends. There are many "
                    "___ of them.",
        "options": None, "answer": "fans",
        "location": "Unit 2 · Understanding ideas · 教材第 32 页（Activity 1 课文）",
        "textbook_context": [blk("FLTRP-EN-7A-2022CUR:P37:B12", 32, B37B12)],
        "introduced_defect": "题干第一句主语与谓语不一致：Grandpa like（应为 Grandpa likes）",
        "gold": {
            "scored": {"english_correct": {"must_be_in": ["FAIL"],
                                           "fn_if": ["PASS", "CONCERN"], "fp_if": []}},
            "decision_rule": "not_accept",
            "gold_reason": "题干存在明确主谓一致错误（Grandpa like），属于真实英语错误，"
                           "不依赖争议性语法解释。",
        },
    },
    {
        "fixture_id": "FIX-A2", "category": "A_true_english_error", "subcategory": "主谓一致（判断题）",
        "question_type": "reading_judge", "fixture_only": True,
        "answer_standard": "TEXTBOOK_ANCHORED",
        "question": "Plants is very important to us.", "options": None, "answer": "True",
        "location": "Unit 5 · Understanding ideas · 教材第 83 页（Activity 7 课文）",
        "textbook_context": [blk("FLTRP-EN-7A-2022CUR:P88:B20", 83, B88B20)],
        "introduced_defect": "判断题题干主语与 be 动词不一致：Plants is（应为 Plants are）",
        "gold": {
            "scored": {"english_correct": {"must_be_in": ["FAIL"],
                                           "fn_if": ["PASS", "CONCERN"], "fp_if": []}},
            "decision_rule": "not_accept",
            "gold_reason": "题干存在明确主谓一致错误（Plants is），事实判断为 True 不代表英语正确。",
        },
    },
    {
        "fixture_id": "FIX-B1", "category": "B_broken_distractor", "subcategory": "干扰项与题干不匹配",
        "question_type": "vocab_choice", "fixture_only": True,
        "answer_standard": "TEXTBOOK_ANCHORED",
        "question": "As a rock music lover, I play the electric guitar in the school ___.",
        "options": ["band", "guitar", "stage", "instrument"], "answer": "band",
        "location": "Unit 2 · Understanding ideas · 教材第 32 页（Activity 1 课文）",
        "textbook_context": [blk("FLTRP-EN-7A-2022CUR:P37:B10", 32, B37B10)],
        "introduced_defect": "干扰项 guitar 放在 in the school ___ 中语法不成立"
                             "（in the school guitar）；stage 需要介词 on；三个干扰项中至少 1 个明显残缺",
        "gold": {
            "scored": {
                "distractor_quality": {"must_be_in": ["FAIL", "CONCERN"],
                                       "fn_if": ["PASS", "NOT_APPLICABLE"], "fp_if": []},
                "answer_unique": {"must_be_in": ["PASS"], "fn_if": [],
                                  "fp_if": ["FAIL"], "soft": ["CONCERN"]},
            },
            "decision_rule": "not_accept",
            "gold_reason": "答案 band 本身正确且唯一；问题出在干扰项 quality：guitar 无法与题干介词搭配。",
        },
    },
    {
        "fixture_id": "FIX-B2", "category": "B_broken_distractor", "subcategory": "干扰项词形与题干不匹配",
        "question_type": "reading_choice", "fixture_only": True,
        "answer_standard": "TEXTBOOK_ANCHORED",
        "question": "What can the trees in the Great Bear Rainforest make?",
        "options": ["their own rain", "their own leaves", "to make rain", "their own fruit"],
        "answer": "their own rain",
        "location": "Unit 5 · Understanding ideas · 教材第 83 页（Activity 7 课文）",
        "textbook_context": [blk("FLTRP-EN-7A-2022CUR:P88:B14", 83, B88B14)],
        "introduced_defect": "干扰项 to make rain 与 can make ___ 的宾语位置不匹配（词形错误）",
        "gold": {
            "scored": {
                "distractor_quality": {"must_be_in": ["FAIL", "CONCERN"],
                                       "fn_if": ["PASS", "NOT_APPLICABLE"], "fp_if": []},
                "answer_unique": {"must_be_in": ["PASS"], "fn_if": [],
                                  "fp_if": ["FAIL"], "soft": ["CONCERN"]},
            },
            "decision_rule": "not_accept",
            "gold_reason": "答案正确；to make rain 这个干扰项在语法位置上不成立，属于干扰项缺陷。",
        },
    },
    {
        "fixture_id": "FIX-C1", "category": "C_true_second_answer", "subcategory": "名词宾语两解",
        "question_type": "vocab_choice", "fixture_only": True,
        "answer_standard": "TEXTBOOK_ANCHORED",
        "question": "Grandpa likes playing the erhu in the park with his ___.",
        "options": ["friends", "students", "parents", "teachers"], "answer": "friends",
        "location": "Unit 2 · Understanding ideas · 教材第 32 页（Activity 1 课文）",
        "textbook_context": [blk("FLTRP-EN-7A-2022CUR:P37:B12", 32, B37B12)],
        "introduced_defect": "干扰项 students 语法与语义都成立，且不被课文排除"
                             "（课文只说 with his friends，并没有说不和学生一起）",
        "gold": {
            "scored": {"answer_unique": {"must_be_in": ["FAIL"],
                                         "fn_if": ["PASS", "CONCERN"], "fp_if": []}},
            "decision_rule": "not_accept",
            "gold_reason": "with his students 同样自然、语法成立、不被教材语境排除 → 真正的第二正确答案。",
        },
    },
    {
        "fixture_id": "FIX-C2", "category": "C_true_second_answer", "subcategory": "名词宾语两解（同词性）",
        "question_type": "vocab_choice", "fixture_only": True,
        "answer_standard": "TEXTBOOK_ANCHORED",
        "question": "Ms Chen writes a ___ on the blackboard.",
        "options": ["sentence", "word", "picture", "name"], "answer": "sentence",
        "location": "Unit 1 · Understanding ideas · 教材第 17 页（Activity 2 课文）",
        "textbook_context": [blk("FLTRP-EN-7A-2022CUR:P22:B0", 17, B22B0)],
        "introduced_defect": "干扰项 word 语法语义都成立（writes a word on the blackboard），"
                             "课文只说 sentence，并未排除 word",
        "gold": {
            "scored": {"answer_unique": {"must_be_in": ["FAIL"],
                                         "fn_if": ["PASS", "CONCERN"], "fp_if": []}},
            "decision_rule": "not_accept",
            "gold_reason": "writes a word on the blackboard 完全成立 → 语言层面的第二正确答案。",
        },
    },
    {
        "fixture_id": "FIX-D1", "category": "D_reality_conflict", "subcategory": "现实常识 vs 课文陈述（树）",
        "question_type": "reading_choice", "fixture_only": True,
        "answer_standard": "TEXTBOOK_ANCHORED",
        "question": "According to the guide, what can the trees in the rainforest make?",
        "options": ["their own rain", "sugar", "oxygen", "food"], "answer": "their own rain",
        "location": "Unit 5 · Understanding ideas · 教材第 83 页（Activity 7 课文）",
        "textbook_context": [blk("FLTRP-EN-7A-2022CUR:P88:B14", 83, B88B14)],
        "introduced_defect": None,
        "gold": {
            "scored": {"answer_unique": {"must_be_in": ["PASS"], "fn_if": [],
                                         "fp_if": ["FAIL"], "soft": ["CONCERN"]}},
            "decision_rule": "not_reject",
            "gold_reason": "课文明确陈述 trees can make their own rain；sugar/oxygen/food 只在"
                           "现实世界成立，属于 Answer Uniqueness Contract V1 的 B 类"
                           "（现实常识存在其他解释），不得据此判答案不唯一。",
        },
    },
    {
        "fixture_id": "FIX-D2", "category": "D_reality_conflict", "subcategory": "现实常识 vs 课文陈述（水）",
        "question_type": "reading_choice", "fixture_only": True,
        "answer_standard": "TEXTBOOK_ANCHORED",
        "question": "Where does the water come from before it goes up the stem?",
        "options": ["the root", "the soil", "the air", "the sun"], "answer": "the root",
        "location": "Unit 5 · Understanding ideas · 教材第 82–83 页（Activity 4 课文）",
        "textbook_context": [blk("FLTRP-EN-7A-2022CUR:P87:B7", 83, B87B7),
                             blk("FLTRP-EN-7A-2022CUR:P85:B12", 82, B85B12)],
        "introduced_defect": None,
        "gold": {
            "scored": {"answer_unique": {"must_be_in": ["PASS"], "fn_if": [],
                                         "fp_if": ["FAIL"], "soft": ["CONCERN"]}},
            "decision_rule": "not_reject",
            "gold_reason": "课文陈述 Water from the root will ...；现实世界水来自土壤，"
                           "属于 B 类现实常识，不得据此判答案不唯一。",
        },
    },
    {
        "fixture_id": "FIX-E1", "category": "E_insufficient_context", "subcategory": "缺少指标物",
        "question_type": "fill", "fixture_only": True, "answer_standard": "TEXTBOOK_ANCHORED",
        "question": "What colour is it? It’s ___.", "options": None, "answer": "grey",
        "location": "Starter · Get ready · 教材第 5 页（Activity 8）",
        "textbook_context": [blk("FLTRP-EN-7A-2022CUR:P10:B5", 5, B10B5)],
        "context_design": "故意只提供教材另一段对话（关于明天穿什么），既没有指标物、"
                          "也没有任何颜色信息，因此无法判断这个空该填什么颜色。",
        "gold": {
            "scored": {"context_status": {"must_be_in": ["CONTEXT_INSUFFICIENT"],
                                          "fn_if": ["SUFFICIENT"], "fp_if": []}},
            "decision_rule": "not_reject",
            "gold_reason": "上下文缺少指标物，属于 Context Insufficient，而不是答案不唯一。",
        },
    },
    {
        "fixture_id": "FIX-E2", "category": "E_insufficient_context", "subcategory": "指代无法解析",
        "question_type": "fill", "fixture_only": True, "answer_standard": "TEXTBOOK_ANCHORED",
        "question": "After a week’s practice, we are on the ___.", "options": None,
        "answer": "stage",
        "location": "Unit 2 · Understanding ideas · 教材第 33 页（Activity 2 课文）",
        "textbook_context": [blk("FLTRP-EN-7A-2022CUR:P38:B3", 33,
                                 "I nod to Grandpa and we fire up our instruments.")],
        "context_design": "故意只提供课文的一个片段（不含 After a week’s practice, we are on "
                          "the stage 一句），因此无法确定这个空是 stage 还是别的地点词。",
        "gold": {
            "scored": {"context_status": {"must_be_in": ["CONTEXT_INSUFFICIENT"],
                                          "fn_if": ["SUFFICIENT"], "fp_if": []}},
            "decision_rule": "not_reject",
            "gold_reason": "所给上下文与题干不同源，无法判断答案；属于 Context Insufficient。",
        },
    },
    {
        "fixture_id": "FIX-F1", "category": "F_high_value_normal", "subcategory": "词汇重组（fans of）",
        "question_type": "vocab_choice", "fixture_only": True,
        "answer_standard": "TEXTBOOK_ANCHORED",
        "question": "Many people love the erhu player’s music. There are many ___ of him in "
                    "the park.",
        "options": ["fans", "players", "teachers", "doctors"], "answer": "fans",
        "location": "Unit 2 · Understanding ideas · 教材第 32 页（Activity 1 课文）",
        "textbook_context": [blk("FLTRP-EN-7A-2022CUR:P37:B12", 32, B37B12)],
        "introduced_defect": None,
        "gold": {
            "scored": {
                "english_correct": {"must_be_in": ["PASS"], "fn_if": [], "fp_if": ["CONCERN", "FAIL"]},
                "answer_unique": {"must_be_in": ["PASS"], "fn_if": [], "fp_if": ["FAIL"]},
                "naturalness": {"must_be_in": ["PASS"], "fn_if": [], "fp_if": ["FAIL"]},
                "learning_value": {"must_be_in": ["PASS"], "fn_if": ["FAIL"], "fp_if": ["FAIL"]},
                "distractor_quality": {"must_be_in": ["PASS"], "fn_if": [],
                                       "fp_if": ["FAIL"]},
                "grade_fit": {"must_be_in": ["PASS"], "fn_if": [], "fp_if": ["FAIL"]},
                "mechanical_level": {"must_be_in": ["RECOMBINED"], "fn_if": [], "fp_if": []},
            },
            "decision_rule": "accept",
            "gold_reason": "用课文短语 fans of 重新组织成新语境，学习点明确（fan of 的用法），"
                           "答案唯一、英语正确、年级适配，属于高学习价值正常题。",
        },
    },
    {
        "fixture_id": "FIX-F2", "category": "F_high_value_normal", "subcategory": "因果理解题",
        "question_type": "reading_choice", "fixture_only": True,
        "answer_standard": "TEXTBOOK_ANCHORED",
        "question": "Why do questions jump into the writer’s mind in the first lesson?",
        "options": ["Because the student points out a mistake", "Because Ms Chen is angry",
                    "Because the bell rings", "Because the class is over"],
        "answer": "Because the student points out a mistake",
        "location": "Unit 1 · Understanding ideas · 教材第 17 页（Activity 2 课文）",
        "textbook_context": [blk("FLTRP-EN-7A-2022CUR:P22:B2", 17, B22B2)],
        "introduced_defect": None,
        "gold": {
            "scored": {
                "english_correct": {"must_be_in": ["PASS"], "fn_if": [], "fp_if": ["CONCERN", "FAIL"]},
                "answer_unique": {"must_be_in": ["PASS"], "fn_if": [], "fp_if": ["FAIL"]},
                "naturalness": {"must_be_in": ["PASS"], "fn_if": [], "fp_if": ["FAIL"]},
                "learning_value": {"must_be_in": ["PASS"], "fn_if": ["FAIL"], "fp_if": ["FAIL"]},
                "distractor_quality": {"must_be_in": ["PASS"], "fn_if": [],
                                       "fp_if": ["FAIL"]},
                "grade_fit": {"must_be_in": ["PASS"], "fn_if": [], "fp_if": ["FAIL"]},
                "mechanical_level": {"must_be_in": ["NOT_APPLICABLE", "RECOMBINED"],
                                     "fn_if": [], "fp_if": []},
            },
            "decision_rule": "accept",
            "gold_reason": "因果理解题：需要把学生的提问与 Questions jump into my mind 连起来，"
                           "比事实定位题有更高的学习价值。",
        },
    },
    {
        "fixture_id": "FIX-F3", "category": "F_high_value_normal", "subcategory": "两句信息整合题",
        "question_type": "reading_choice", "fixture_only": True,
        "answer_standard": "TEXTBOOK_ANCHORED",
        "question": "What does Grandpa do with his friends in the park?",
        "options": ["He plays the erhu and they sing Beijing opera together",
                    "He plays the electric guitar with them",
                    "He writes songs with them", "He watches TV with them"],
        "answer": "He plays the erhu and they sing Beijing opera together",
        "location": "Unit 2 · Understanding ideas · 教材第 32 页（Activity 1 课文）",
        "textbook_context": [blk("FLTRP-EN-7A-2022CUR:P37:B12", 32, B37B12)],
        "introduced_defect": None,
        "gold": {
            "scored": {
                "english_correct": {"must_be_in": ["PASS"], "fn_if": [], "fp_if": ["CONCERN", "FAIL"]},
                "answer_unique": {"must_be_in": ["PASS"], "fn_if": [], "fp_if": ["FAIL"]},
                "naturalness": {"must_be_in": ["PASS"], "fn_if": [], "fp_if": ["FAIL"]},
                "learning_value": {"must_be_in": ["PASS"], "fn_if": ["FAIL"], "fp_if": ["FAIL"]},
                "distractor_quality": {"must_be_in": ["PASS"], "fn_if": [],
                                       "fp_if": ["FAIL"]},
                "grade_fit": {"must_be_in": ["PASS"], "fn_if": [], "fp_if": ["FAIL"]},
                "mechanical_level": {"must_be_in": ["NOT_APPLICABLE", "RECOMBINED"],
                                     "fn_if": [], "fp_if": []},
            },
            "decision_rule": "accept",
            "gold_reason": "需要整合课文两句信息（erhu + Beijing opera），而不是抄一句；"
                           "干扰项均取自同一 Unit 的教材素材。",
        },
    },
    {
        "fixture_id": "FIX-G1", "category": "G_mechanical_but_valid", "subcategory": "名词性物主代词重点词",
        "question_type": "fill", "fixture_only": True, "answer_standard": "TEXTBOOK_ANCHORED",
        "question": "I look up at Ms Chen. My eyes meet ___.", "options": None, "answer": "hers",
        "location": "Unit 1 · Understanding ideas · 教材第 19 页（Activity 5 语法重点）",
        "textbook_context": [blk("FLTRP-EN-7A-2022CUR:P24:B1", 19, B24B1),
                             blk("FLTRP-EN-7A-2022CUR:P24:B2", 19, B24B2)],
        "introduced_defect": None,
        "gold": {
            "scored": {
                "answer_unique": {"must_be_in": ["PASS"], "fn_if": ["FAIL"], "fp_if": ["FAIL"]},
                "english_correct": {"must_be_in": ["PASS"], "fn_if": [],
                                    "fp_if": ["CONCERN", "FAIL"]},
                "learning_value": {"must_be_in": ["PASS", "CONCERN"], "fn_if": [],
                                   "fp_if": ["FAIL"]},
                "mechanical_level": {"must_be_in": ["DIRECT_REPRODUCTION", "MECHANICAL_REWRITE"],
                                     "fn_if": [], "fp_if": []},
            },
            "decision_rule": "not_reject",
            "gold_reason": "形式是教材原句挖空（机械），但考的是 Activity 5 的语法重点"
                           "（名词性物主代词 hers），答案唯一、英语正确 → 不能因为机械形式判 FAIL。",
        },
    },
    {
        "fixture_id": "FIX-G2", "category": "G_mechanical_but_valid", "subcategory": "say + 直接引语重点词",
        "question_type": "fill", "fixture_only": True, "answer_standard": "TEXTBOOK_ANCHORED",
        "question": "Ms Chen writes the sentence on the blackboard and ___ , “Please write this "
                    "down.”",
        "options": None, "answer": "says",
        "location": "Unit 1 · Understanding ideas · 教材第 17 页（Activity 2 课文）",
        "textbook_context": [blk("FLTRP-EN-7A-2022CUR:P22:B0", 17, B22B0)],
        "introduced_defect": None,
        "gold": {
            "scored": {
                "answer_unique": {"must_be_in": ["PASS", "CONCERN"], "fn_if": [],
                                  "fp_if": ["FAIL"]},
                "english_correct": {"must_be_in": ["PASS"], "fn_if": [],
                                    "fp_if": ["CONCERN", "FAIL"]},
                "learning_value": {"must_be_in": ["PASS", "CONCERN"], "fn_if": [],
                                   "fp_if": ["FAIL"]},
                "mechanical_level": {"must_be_in": ["DIRECT_REPRODUCTION", "MECHANICAL_REWRITE"],
                                     "fn_if": [], "fp_if": []},
            },
            "decision_rule": "not_reject",
            "gold_reason": "机械挖空形式，但考的是 say + 直接引语的搭配（教材重点表达），"
                           "答案由语法与搭配唯一确定 → 不能因为机械形式判 FAIL。",
        },
    },
]

CATEGORY_LABEL = {
    "A_true_english_error": "A 真正错误英语",
    "B_broken_distractor": "B 明显错误干扰项",
    "C_true_second_answer": "C 真正第二正确答案",
    "D_reality_conflict": "D 现实常识冲突",
    "E_insufficient_context": "E 上下文不足",
    "F_high_value_normal": "F 高学习价值正常题",
    "G_mechanical_but_valid": "G 机械但合理的重点词填空",
}


def main():
    ids = [f["fixture_id"] for f in FIXTURES]
    assert len(ids) == len(set(ids)) == 15, "fixture ids must be unique and count 15"
    assert set(ids) == {"FIX-%s%d" % (c, n) for c in "ABCDEFG" for n in (1, 2, 3)
                        if "FIX-%s%d" % (c, n) in ids} | {"FIX-F1", "FIX-F2", "FIX-F3"}, \
        "unexpected fixture id set"

    fixtures = {"stage": "P1-09-D", "fixture_count": len(FIXTURES),
                "fixture_design": "人工预先设计（experimenter designed），非 AI 生成；"
                                  "所有 fixture 均标记 fixture_only=true，"
                                  "不属于教材事实，也不写入任何正式数据。",
                "category_labels": CATEGORY_LABEL,
                "category_counts": {c: sum(1 for f in FIXTURES if f["category"] == c)
                                    for c in CATEGORY_LABEL},
                "fixtures": FIXTURES}

    hidden_gold = {
        "stage": "P1-09-D",
        "note": "本文件是实验人员侧的对照标签，**绝不允许进入 AI 输入**。",
        "gold": [{"fixture_id": f["fixture_id"], "category": f["category"],
                  "subcategory": f["subcategory"], "question_type": f["question_type"],
                  "scored": f["gold"]["scored"], "decision_rule": f["gold"]["decision_rule"],
                  "gold_reason": f["gold"]["gold_reason"],
                  "introduced_defect": f.get("introduced_defect"),
                  "context_design": f.get("context_design")} for f in FIXTURES],
    }

    items = []
    for f in FIXTURES:
        items.append({
            "fixture_id": f["fixture_id"],
            "question_type": f["question_type"],
            "question": f["question"],
            "options": f["options"],
            "stored_answer": f["answer"],
            "textbook_location": f["location"],
            "textbook_context": [
                {"textbook_page": b["textbook_page"], "text": b["text"]}
                for b in f["textbook_context"]],
            "answer_standard": f["answer_standard"],
        })
    ai_input = {"review_context_version": "RC-v1", "context_level": "MINIMAL",
                "grade_context": GRADE, "review_version": "P1-09-D-v1", "items": items}

    # ---- leak check: gold values must not appear anywhere in the AI input
    ai_text = json.dumps(ai_input, ensure_ascii=False)
    leaks = []
    for g in hidden_gold["gold"]:
        for token in ("gold_reason", "hidden_gold", "decision_rule", "must_be_in",
                      "introduced_defect", "context_design"):
            if token in ai_text:
                leaks.append(token)
        if g["gold_reason"][:12] in ai_text:
            leaks.append("gold_reason text:" + g["fixture_id"])
    assert not leaks, "gold leaked into AI input: %s" % leaks

    with open(os.path.join(HERE, "fixtures.json"), "w", encoding="utf-8") as fh:
        json.dump(fixtures, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, "hidden_gold.json"), "w", encoding="utf-8") as fh:
        json.dump(hidden_gold, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, "ai_input_snapshot.json"), "w", encoding="utf-8") as fh:
        json.dump(ai_input, fh, ensure_ascii=False, indent=2)

    man = hashlib.sha256(json.dumps(fixtures, ensure_ascii=False, sort_keys=True).encode()).hexdigest().upper()
    gold_man = hashlib.sha256(
        json.dumps(hidden_gold, ensure_ascii=False, sort_keys=True).encode()).hexdigest().upper()
    input_man = hashlib.sha256(
        json.dumps(ai_input, ensure_ascii=False, sort_keys=True).encode()).hexdigest().upper()
    manifest = {"stage": "P1-09-D", "fixtures_sha256": man, "hidden_gold_sha256": gold_man,
                "ai_input_sha256": input_man, "fixture_count": len(FIXTURES),
                "ai_input_chars": len(ai_text),
                "gold_leak_check": "PASS（AI 输入中不含任何 gold 字段或 gold 文本）"}
    with open(os.path.join(HERE, "fixture_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    print("fixtures:", len(FIXTURES))
    print("category counts:", json.dumps(fixtures["category_counts"], ensure_ascii=False))
    print("ai input chars:", len(ai_text))
    print("manifest:", json.dumps(manifest, ensure_ascii=False, indent=1))
    for f in FIXTURES:
        print("  %-8s %-26s %-14s %s" % (f["fixture_id"], f["category"], f["question_type"],
                                         f["question"][:56]))


if __name__ == "__main__":
    main()

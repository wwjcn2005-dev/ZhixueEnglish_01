"""validator_v2 的单元测试：覆盖两处口径修正的 7 类情形（不调用任何 AI）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validator_v2 as V  # noqa: E402

ALLOW = V.FUNC | {"along", "trailer", "disease", "result", "road", "brothers", "bike",
                  "races", "together", "often", "take", "part", "refuse", "win",
                  "stay", "home", "story", "book", "toy", "robert", "puts", "pulls"}


class WhitelistTest(unittest.TestCase):
    """修正 1：白名单只覆盖 question / options / answer。"""

    def test_1_explanation_words_do_not_fail(self):
        # explanation 里出现非白名单说明词（states / correct）不应影响词汇校验
        q = {"question": "He puts Robert in a ___ and pulls it along with his bike.",
             "options": ["trailer", "road", "disease", "result"], "answer": "trailer",
             "explanation": "The story states that this is the correct word."}
        text = V.checked_language(q)
        self.assertEqual(V.out_of_scope(text, ALLOW), [])
        # 被检查的文本里不得包含 explanation 的词
        self.assertNotIn("states", V.tokens(text))
        self.assertNotIn("correct", V.tokens(text))

    def test_2_quoted_textbook_word_is_normalised(self):
        # explanation 里被引号包裹的 'trailer' 归一化后与 trailer 同词
        self.assertEqual(V.tokens("so 'trailer' is the correct word"),
                         ["so", "trailer", "is", "the", "correct", "word"])
        self.assertEqual(V.out_of_scope("trailer", ALLOW), [])

    def test_7_real_out_of_scope_word_still_fails(self):
        # 题干/选项出现教材外核心词，必须仍然 FAIL
        bad = V.out_of_scope("Which dinosaur ate the trailer?", ALLOW)
        self.assertIn("dinosaur", bad)
        bad2 = V.out_of_scope("", ALLOW) + V.out_of_scope("beautiful", ALLOW)
        self.assertIn("beautiful", bad2)


class AnswerSupportTest(unittest.TestCase):
    """修正 2：答案支持分级；不采信 explanation 的自称。"""

    QUOTE = "Now, the brothers often take part in bike races together."

    def test_3_exact(self):
        self.assertEqual(V.answer_support(
            "But Robert has a serious disease and cannot move at all.",
            "But Robert has a serious disease and cannot move at all."), "EXACT")
        self.assertEqual(V.answer_support("trailer",
                                          "He puts Robert in a trailer and pulls it."), "EXACT")

    def test_4_verifiable_reference(self):
        # q3 的真实情形：They = the brothers（引用内可找到先行词）
        self.assertEqual(V.answer_support(
            "They often take part in bike races together.", self.QUOTE,
            question="What do the brothers often do now?"), "VERIFIABLE_REFERENCE")

    def test_4b_verifiable_rephrase_by_inflection(self):
        self.assertEqual(V.answer_support(
            "The brother often takes part in a bike race.", self.QUOTE),
            "VERIFIABLE_REPHRASE")

    def test_5_explanation_claim_is_not_accepted(self):
        # 答案只在 explanation 里被"解释"，引用本身不支持 → 必须 UNSUPPORTED
        explanation = "This is a reference, the answer is 'they lose'."
        self.assertEqual(V.answer_support(
            "They lose every race.", self.QUOTE, question=explanation), "UNSUPPORTED")

    def test_6_outside_knowledge_is_not_accepted(self):
        # 需要世界知识/教材外事实的答案 → UNSUPPORTED
        self.assertEqual(V.answer_support(
            "Bike racing began in France.", self.QUOTE), "UNSUPPORTED")
        self.assertEqual(V.answer_support(
            "There are two brothers in the family.", self.QUOTE), "UNSUPPORTED")

    def test_6b_empty_is_unsupported(self):
        self.assertEqual(V.answer_support("", self.QUOTE), "UNSUPPORTED")


if __name__ == "__main__":
    unittest.main(verbosity=2)

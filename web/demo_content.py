#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Demo 学习内容（**一次生成 → 固定入库 → 页面只读取**）。

本轮约定（见任务书 §三~§八）：
  * 教材已有的语言材料优先：例句/题目尽量直接取教材原句、教材短语、教材句型；
  * 教材没有合适内容时才补充，补充内容在这里**固定保存**，页面只读取，不实时生成；
  * 严格区分三件事：``meaning``（单词释义）/ ``example_sentence``（完整英文例句）/
    ``sentence_translation``（完整中文翻译）——绝不用单词释义冒充整句翻译；
  * 题目与例句里不出现「根据教材…」「AI生成…」这类后台生成痕迹；
  * 同一个词/同一道题每次打开都一样（本文件是唯一来源，不含随机）。

字段说明（每条内容都带来源，便于统计与复核）：
  ``textbook``  —— 英文直接来自教材原句（中文为对应整句翻译）；
  ``fixed``     —— 教材没有合适句子，按当前单元词汇/句型补充并固定保存。
"""

from __future__ import annotations

#: 内容版本（固定入库标记；改动内容时同步更新）
VERSION = "v5-2026-09-16"

#: 单词跟读的例句：unit_code → {word: (英文例句, 整句中文翻译, 来源)}
EXAMPLES = {
    "Starter": {
        "ready": ("Are you ready?", "你准备好了吗？", "textbook"),
        "textbook": ("Open your textbook and turn to page 12.",
                     "打开你的课本，翻到第 12 页。", "fixed"),
        "eraser": ("Can I borrow your eraser?", "我能借一下你的橡皮吗？", "fixed"),
        "junior high": ("I am a student at junior high now.", "我现在是一名初中生。", "fixed"),
        "geography": ("We have geography on Monday morning.", "我们星期一上午有地理课。", "fixed"),
        "biology": ("Biology is my favourite subject.", "生物是我最喜欢的科目。", "fixed"),
        "history": ("We learn about Chinese history in class.",
                    "我们在课上学习中国历史。", "fixed"),
        "grey": ("He is wearing a grey jacket today.", "他今天穿着一件灰色夹克。", "fixed"),
        "jacket": ("Put on your jacket. It's cold outside.",
                   "穿上你的夹克吧，外面很冷。", "fixed"),
        "red scarf": ("Many students wear a red scarf at school.",
                      "很多学生在学校戴红领巾。", "fixed"),
    },
    "Unit 1": {
        "without": ("You can't learn a language without practice.",
                    "不练习就学不好一门语言。", "fixed"),
        "sentence": ("Our English teacher Ms Chen writes the sentence on the blackboard.",
                     "我们的英语老师陈老师把这个句子写在黑板上。", "textbook"),
        "point out": ("But is it OK to point out the mistake?",
                      "但是指出错误合适吗?", "textbook"),
        "mistake": ("“Ms Chen, there's a mistake,” I say.",
                    "“陈老师，这里有个错误，”我说。", "textbook"),
        "polite": ("Is that polite, in the first lesson?",
                   "在第一节课上，那样有礼貌吗?", "textbook"),
        "mind": ("Questions jump into my mind.", "一个个问题跳进我的脑海。", "textbook"),
        "hers": ("My eyes meet hers.", "我的目光和她的目光相遇。", "textbook"),
        "dry": ("My mouth feels dry.", "我的嘴感觉很干。", "textbook"),
        "meaning": ("But then I think about the meaning of the sentence.",
                    "但接着我思考起这个句子的意思。", "textbook"),
        "fact": ("In fact, this is my first lesson for all of you.",
                 "其实，这是我想给你们所有人上的第一堂课。", "textbook"),
    },
    "Unit 2": {
        "rock music": ("My grandpa and I both like rock music.",
                       "我和爷爷都喜欢摇滚乐。", "fixed"),
        "electric": ("He plays the electric guitar very well.",
                     "他的电吉他弹得非常好。", "fixed"),
        "guitar": ("Grandpa takes out his guitar and starts to play.",
                   "爷爷拿出他的吉他，开始弹奏。", "fixed"),
        "band": ("We want to start a band together.", "我们想一起组建一支乐队。", "fixed"),
        "sound": ("The sound of our music fills the room.",
                  "我们的音乐声充满了整个房间。", "fixed"),
        "different": ("Grandpa's music is different from mine.",
                      "爷爷的音乐和我的不一样。", "fixed"),
        "suddenly": ("Suddenly, an idea hits me.", "突然，我想到一个主意。", "textbook"),
        "hit": ("An idea suddenly hits me.", "一个主意突然让我眼前一亮。", "textbook"),
        "rush": ("“Grandpa!” I rush into his room.", "“爷爷！”我冲进他的房间。", "textbook"),
        "festival": ("There is an art festival every autumn in my school.",
                     "我们学校每年秋天都有一场艺术节。", "textbook"),
    },
    "Unit 3": {
        "silent": ("His love may be silent. But like a mountain, it is always there.",
                   "他的爱也许是无声的，但就像一座山，始终在那里。", "textbook"),
        "along": ("Along a mountain road, a handsome young man walks fast.",
                  "沿着一条山路，一个英俊的年轻人走得很快。", "textbook"),
        "mountain": ("His love is like a mountain.", "他的爱就像一座山。", "textbook"),
        "road": ("The father and the son walk along the mountain road.",
                 "父亲和儿子沿着山路走着。", "fixed"),
        "handsome": ("The young man in the film is tall and handsome.",
                     "电影里的那个年轻人又高又英俊。", "fixed"),
        "strict": ("An older man with a strict face follows him.",
                   "一位面容严肃的年长男子跟着他。", "textbook"),
        "follow": ("Please follow me to the post office.", "请跟我去邮局。", "fixed"),
        "postman": ("The father served as the postman for this area.",
                    "父亲曾在这个地区当邮递员。", "textbook"),
        "touching": ("It's a touching story about the love between father and son.",
                     "这是一个关于父子之爱的感人故事。", "textbook"),
        "son": ("But now the son is taking over his father's position.",
                "但现在儿子接替了父亲的工作。", "textbook"),
    },
    "Unit 4": {
        "unusual": ("This Spring Festival is unusual for Emilia.",
                    "这个春节对埃米莉娅来说很不寻常。", "fixed"),
        "university": ("It is my first year of university in the UK.",
                       "这是我在英国上大学的第一个年头。", "textbook"),
        "treat": ("I want to treat her to a Chinese dinner.",
                  "我想请她吃一顿中国菜。", "textbook"),
        "realise": ("I never realised cooking was so difficult.",
                    "我从没意识到做饭这么难。", "textbook"),
        "dumpling": ("It is midnight in China – time for dumplings.",
                     "中国正是午夜——该吃饺子的时候了。", "textbook"),
        "whole": ("My whole family come to help me on the phone.",
                  "我全家人在电话里帮我。", "textbook"),
        "cucumber": ("I even make some cucumber flowers.",
                     "我甚至还做了几朵黄瓜花。", "textbook"),
        "hang": ("Emilia hangs balloons and lanterns in the dining room.",
                 "埃米莉娅在餐厅里挂起了气球和灯笼。", "textbook"),
        "balloon": ("There are colourful balloons in the dining room.",
                    "餐厅里有五颜六色的气球。", "fixed"),
        "lantern": ("The lanterns make the room warm and bright.",
                    "灯笼让房间又温暖又明亮。", "fixed"),
    },
    "Unit 5": {
        "within": ("You can find many teahouses within the city.",
                   "在这座城市里你能找到很多茶馆。", "fixed"),
        "quarter": ("It's quarter past seven.", "现在是七点一刻。", "textbook"),
        "workshop": ("He works in Workshop 1001 in the Leaf.",
                     "他在叶子的 1001 号车间工作。", "textbook"),
        "leaf": ("Workers in the Leaf mix water, CO2 and sunlight.",
                 "叶子里的工人们把水、二氧化碳和阳光混合起来。", "textbook"),
        "each": ("There are 20 to 100 workers in each workshop.",
                 "每个车间里有 20 到 100 名工人。", "textbook"),
        "collect": ("They collect sunlight and CO2 during the day.",
                    "它们在白天收集阳光和二氧化碳。", "textbook"),
        "root": ("Now workers from the Root send up water.",
                 "现在根部的工人们把水送上来。", "textbook"),
        "send": ("Workers from the Root send up water to the Leaf.",
                 "根部的工人把水送到叶子。", "textbook"),
        "rise": ("The water will rise up to the Leaf through the Stem.",
                 "水会通过茎上升到叶子。", "textbook"),
        "stem": ("The water goes up through the stem.", "水通过茎往上走。", "fixed"),
    },
    "Unit 6": {
        "pigeon": ("That pigeon is looking at itself in the water!",
                   "那只鸽子正在水里看自己！", "textbook"),
        "surprise": ("It is a surprise that pigeons can recognise themselves.",
                     "鸽子能认出自己，这真让人吃惊。", "fixed"),
        "knock around (about)": ("I like to knock around the park at weekends.",
                                 "周末我喜欢在公园里闲逛。", "fixed"),
        "droppings": ("Be careful! There are pigeon droppings on the bench.",
                      "小心！长椅上有鸽子粪。", "fixed"),
        "boring": ("Well, pigeons aren't boring or scary.",
                   "嗯，鸽子既不无聊也不可怕。", "textbook"),
        "feed": ("I feed the pigeons in the park every Sunday.",
                 "我每个星期天都在公园里喂鸽子。", "fixed"),
        "madly": ("The birds are madly looking for food.",
                  "这些鸟在疯狂地找食物。", "fixed"),
        "scary": ("Some people think pigeons are scary.",
                  "有些人觉得鸽子很可怕。", "fixed"),
        "research": ("I'm doing some online research.", "我正在网上做一些研究。", "textbook"),
        "recognise": ("Pigeons can recognise themselves in mirrors.",
                      "鸽子能在镜子里认出自己。", "textbook"),
    },
}

#: 短句练习补充题（教材短语/句型不够时固定使用）：unit_code → [item, ...]
SHORT_PRACTICE = {
    "Starter": [
        {"kind": "choice", "type": "句子补全",
         "prompt": "Please ___ the eraser to me. (把它递给我)",
         "options": ["pass", "point out", "write down"], "answer": "a",
         "why": "递东西用 pass 最自然。"},
        {"kind": "choice", "type": "中英转换",
         "prompt": "“我们是同一个班的。”用英语怎么说？",
         "options": ["We are in the same class.", "We are in the same grade.",
                     "We are at the same desk."], "answer": "a",
         "why": "“同一个班”是 in the same class。"},
    ],
    "Unit 1": [
        {"kind": "choice", "type": "句子补全",
         "prompt": "Please ___ the mistake on the blackboard.",
         "options": ["point out", "look out", "write down"], "answer": "a",
         "why": "指出错误用 point out。"},
        {"kind": "choice", "type": "中英转换",
         "prompt": "“其实，这是我给你们上的第一堂课。”用英语怎么说？",
         "options": ["In fact, this is my first lesson for all of you.",
                     "In fact, this is my first class in junior high.",
                     "In fact, this is the first lesson of the day."],
         "answer": "a",
         "why": "教材原句是 In fact, this is my first lesson for all of you."},
    ],
    "Unit 2": [
        {"kind": "choice", "type": "句子补全",
         "prompt": "An idea ___ hits me: let's put our music together.",
         "options": ["suddenly", "quietly", "slowly"], "answer": "a",
         "why": "教材原句是 An idea suddenly hits me。"},
        {"kind": "choice", "type": "中英转换",
         "prompt": "“我们学校每年秋天有一场艺术节。”用英语怎么说？",
         "options": ["There is an art festival every autumn in my school.",
                     "There is a music lesson every autumn in my school.",
                     "There is an art festival every spring in my school."],
         "answer": "a", "why": "教材原句是 There is an art festival every autumn in my school."},
    ],
    "Unit 3": [
        {"kind": "choice", "type": "句子补全",
         "prompt": "An older man with a ___ face follows him.",
         "options": ["strict", "silent", "touching"], "answer": "a",
         "why": "教材原句是 An older man with a strict face follows him。"},
        {"kind": "choice", "type": "中英转换",
         "prompt": "“他的爱也许是无声的。”用英语怎么说？",
         "options": ["His love may be silent.", "His love may be absent.",
                     "His love may be difficult."], "answer": "a",
         "why": "教材原句是 His love may be silent。"},
    ],
    "Unit 4": [
        {"kind": "choice", "type": "句子补全",
         "prompt": "I want to ___ her to a Chinese dinner.",
         "options": ["treat", "hang", "realise"], "answer": "a",
         "why": "请客用 treat sb to sth。"},
        {"kind": "choice", "type": "中英转换",
         "prompt": "“我从没意识到做饭这么难。”用英语怎么说？",
         "options": ["I never realised cooking was so difficult.",
                     "I never realised cooking was so boring.",
                     "I never learned cooking was so easy."], "answer": "a",
         "why": "教材原句是 I never realised cooking was so difficult。"},
    ],
    "Unit 5": [
        {"kind": "choice", "type": "句子补全",
         "prompt": "There are 20 to 100 workers in ___ workshop.",
         "options": ["each", "whole", "within"], "answer": "a",
         "why": "“每个车间”用 each workshop。"},
        {"kind": "choice", "type": "中英转换",
         "prompt": "“水会通过茎上升到叶子。”用英语怎么说？",
         "options": ["The water will rise up to the Leaf through the Stem.",
                     "The water will send up to the Leaf through the Root.",
                     "The water will collect in the Leaf through the Stem."],
         "answer": "a",
         "why": "教材原句是 The water will rise up to the Leaf through the Stem。"},
    ],
    "Unit 6": [
        {"kind": "choice", "type": "句子补全",
         "prompt": "Pigeons can ___ themselves in mirrors.",
         "options": ["recognise", "feed", "research"], "answer": "a",
         "why": "教材原句是 Pigeons can recognise themselves in mirrors。"},
        {"kind": "choice", "type": "中英转换",
         "prompt": "“鸽子既不无聊也不可怕。”用英语怎么说？",
         "options": ["Pigeons aren't boring or scary.", "Pigeons aren't boring but scary.",
                     "Pigeons are boring and scary."], "answer": "a",
         "why": "教材原句是 Well, pigeons aren't boring or scary。"},
    ],
}

#: 阅读练习：教材课文之外的固定补充（材料 + 题目）。unit_code → dict
READING_EXTRA = {
    "Starter": {
        "source": "fixed",
        "title": "My first day at junior high",
        "text": ("I am a student at junior high now. On the first day, I meet my new "
                 "classmates in the classroom. Our English teacher, Ms Wang, gives "
                 "everyone a textbook. We also get a red scarf. In the afternoon, we "
                 "visit the library and the dining hall. I am a little nervous, but I "
                 "am happy too."),
        "questions": [
            {"kind": "choice", "type": "细节理解",
             "prompt": "What does Ms Wang give everyone?",
             "options": ["A textbook.", "A red scarf.", "A new school bag."], "answer": "a",
             "why": "文中写的是 Our English teacher, Ms Wang, gives everyone a textbook."},
            {"kind": "choice", "type": "信息判断",
             "prompt": "Which places do they visit in the afternoon?",
             "options": ["The library and the dining hall.",
                         "The classroom and the library.",
                         "The playground and the dining hall."], "answer": "a",
             "why": "文中写的是 we visit the library and the dining hall。"},
        ],
    },
    "Unit 1": {
        "source": "textbook",
        "title": "First lesson（教材课文）",
        "text": "",
        "questions": [
            {"kind": "choice", "type": "细节理解",
             "prompt": "Why do the questions jump into the writer's mind?",
             "options": ["Because the sentence on the blackboard is not right.",
                         "Because he doesn't like the first lesson.",
                         "Because Ms Chen asks him to write a letter."], "answer": "a",
             "why": "课文里写的是 That's not right. But is it OK to point out the mistake?"},
            {"kind": "choice", "type": "主旨理解",
             "prompt": "What does the writer learn in his first lesson?",
             "options": ["It is important to think and to ask.",
                         "It is difficult to write English sentences.",
                         "It is polite to keep quiet in class."], "answer": "a",
             "why": "最后一句话是 That's really an important lesson!（要思考、要提问）"},
        ],
    },
    "Unit 2": {
        "source": "textbook", "title": "Grandpa's music（教材课文）", "text": "",
        "questions": [
            {"kind": "choice", "type": "细节理解",
             "prompt": "What does Grandpa do with the writer at the art festival?",
             "options": ["They play music together on the stage.",
                         "They watch a film about music.",
                         "They write a song for the school."], "answer": "a",
             "why": "课文里写的是 After a week's practice, we are on the stage."},
            {"kind": "choice", "type": "主旨理解",
             "prompt": "What is the passage mainly about?",
             "options": ["A boy and his grandpa enjoy music together.",
                         "A boy learns to play the guitar at school.",
                         "A grandpa tells stories about his old band."], "answer": "a",
             "why": "全文围绕“我”和爷爷一起排练、一起上台演出来写。"},
        ],
    },
    "Unit 3": {
        "source": "textbook", "title": "Postmen in the Mountains（教材课文）", "text": "",
        "questions": [
            {"kind": "choice", "type": "细节理解",
             "prompt": "What happens when the son carries his father across the river?",
             "options": ["The father remembers carrying his son on his back.",
                         "The father is angry with his son.",
                         "The son decides to leave home."], "answer": "a",
             "why": "课文里写的是 It brings back the father's memory of carrying the son on his back."},
            {"kind": "choice", "type": "主旨理解",
             "prompt": "What is the writer's idea about a traditional Chinese father?",
             "options": ["He hides his care in his heart, but his love is always there.",
                         "He often gives hugs and kisses to his son.",
                         "He never cares about his children."], "answer": "a",
             "why": "课文里写的是 He just hides his care in his heart. His love may be silent."},
        ],
    },
    "Unit 4": {
        "source": "textbook", "title": "A Chinese dinner（教材课文）", "text": "",
        "questions": [
            {"kind": "choice", "type": "细节理解",
             "prompt": "Why does Emilia feel shocked at the dinner?",
             "options": ["Because of the name of the dish “the lion's head”.",
                         "Because the food is too hot for her.",
                         "Because the dining room is too small."], "answer": "a",
             "why": "课文里写的是 “Are you joking? Isn't that against the law?”"},
            {"kind": "choice", "type": "细节理解",
             "prompt": "What does the round shape of the meatball stand for?",
             "options": ["Family reunions.", "A new year's wish.", "Good luck in study."],
             "answer": "a",
             "why": "课文里写的是 Its round shape stands for family reunions."},
        ],
    },
    "Unit 5": {
        "source": "textbook", "title": "Workers in the plant（教材课文）", "text": "",
        "questions": [
            {"kind": "choice", "type": "细节理解",
             "prompt": "What do workers in the Leaf do?",
             "options": ["They mix water, CO2 and sunlight.",
                         "They send up water from the Root.",
                         "They produce more leaves in spring."], "answer": "a",
             "why": "课文里写的是 workers in the Leaf will mix water, CO2 and sunlight。"},
            {"kind": "choice", "type": "主旨理解",
             "prompt": "Why does the writer call the plant “a factory”?",
             "options": ["Because the plant makes sugar with water, CO2 and sunlight.",
                         "Because the plant has many workers in it.",
                         "Because the plant is very big and green."], "answer": "a",
             "why": "课文用工厂里分工合作的方式说明植物怎样制造养分。"},
        ],
    },
    "Unit 6": {
        "source": "textbook", "title": "Fantastic animals（教材课文）", "text": "",
        "questions": [
            {"kind": "choice", "type": "细节理解",
             "prompt": "Which of these can pigeons do?",
             "options": ["They can recognise themselves in mirrors.",
                         "They can fly at 200 km per hour.",
                         "They can read the words in a book."], "answer": "a",
             "why": "课文里写的是 Pigeons can recognise themselves in mirrors."},
            {"kind": "choice", "type": "主旨理解",
             "prompt": "What does the dodo's story ask us to do?",
             "options": ["To help fantastic animals and make them happy.",
                         "To find more animals in museums.",
                         "To keep animals in our homes."], "answer": "a",
             "why": "课文最后写的是 Please try your best to help them."},
        ],
    },
}


def example_for(unit_code: str, word: str):
    """取某个词的固定例句：(英文, 中文翻译, 来源)；没有就返回 None（页面不显示例句）。"""
    row = (EXAMPLES.get(unit_code) or {}).get((word or "").strip())
    if not row:
        return None
    en, zh, source = row
    return {"sentence": en, "translation": zh, "source": source}


def short_practice(unit_code: str) -> list:
    """短句练习的固定补充题（教材短语/句型之外的部分）。"""
    return [dict(x) for x in (SHORT_PRACTICE.get(unit_code) or [])]


def reading_extra(unit_code: str) -> dict:
    """阅读练习的固定补充内容（材料 + 题目）；教材课文题之外的部分。"""
    return dict(READING_EXTRA.get(unit_code) or {})


def stats() -> dict:
    """固定入库内容统计（报告 / 测试用）。"""
    ex_total = sum(len(v) for v in EXAMPLES.values())
    ex_textbook = sum(1 for v in EXAMPLES.values() for row in v.values()
                      if row[2] == "textbook")
    short = sum(len(v) for v in SHORT_PRACTICE.values())
    read_q = sum(len((v.get("questions") or [])) for v in READING_EXTRA.values())
    read_with_text = sum(1 for v in READING_EXTRA.values() if (v.get("text") or "").strip())
    return {"version": VERSION,
            "examples_total": ex_total, "examples_textbook": ex_textbook,
            "examples_fixed": ex_total - ex_textbook,
            "examples_translated": ex_total,
            "short_practice": short, "reading_questions": read_q,
            "reading_units": len(READING_EXTRA), "reading_materials": read_with_text,
            "units": sorted(EXAMPLES)}

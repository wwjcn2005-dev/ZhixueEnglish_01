"""P0 Spike 校验器 v2：修正两处误报口径（不调用任何 AI）。

修正 1（词汇白名单）：只检查 question / options / answer，不检查 explanation 与元数据；
                      引号、大小写、标点归一化后再比较。
修正 2（答案支持）：answer_support_type ∈ {EXACT, VERIFIABLE_REFERENCE,
                      VERIFIABLE_REPHRASE, UNSUPPORTED}；
                      只有逐字、或**确定性可验证**的指代/词形变化才算支持，
                      绝不采信 explanation 的自称。
"""
import re

PRONOUNS = {"they", "them", "their", "theirs", "themselves", "it", "its", "itself",
            "he", "him", "his", "himself", "she", "her", "hers", "herself",
            "we", "us", "our", "ours", "ourselves", "you", "your", "yours",
            "this", "that", "these", "those"}

CONTRACTION = {
    "don't": "do not", "doesn't": "does not", "didn't": "did not", "isn't": "is not",
    "aren't": "are not", "wasn't": "was not", "weren't": "were not", "can't": "can not",
    "couldn't": "could not", "won't": "will not", "wouldn't": "would not",
    "it's": "it is", "i'm": "i am", "we're": "we are", "they're": "they are",
    "he's": "he is", "she's": "she is", "that's": "that is", "there's": "there is",
    "what's": "what is", "let's": "let us", "i'd": "i would", "we'd": "we would",
}

FUNC = set("""a an the is are was were be been am do does did done
have has had i you he she it we they me him her us them my your his its our their this that these those
what which who whose when where why how in on at to of for from with by as and or but not no yes true
false both each other others all some any many much more most few less least very too also only just
still yet even than then there here now next first second third last about into over under between
after before during because so if while such same different can could will would should may might must
shall one two three four five six seven eight nine ten""".split())


def tokens(text: str) -> list:
    """归一化：小写、去引号/标点、展开常见缩写，再切词。"""
    s = (text or "").lower()
    for a, b in (("\u2019", "'"), ("\u2018", "'"), ("\u201c", " "), ("\u201d", " "),
                 ("\u2018", "'"), ("`", "'")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    for k, v in CONTRACTION.items():
        s = re.sub(r"\b%s\b" % re.escape(k), v, s)
    s = s.replace("'", " ")
    return [w for w in s.split() if w]


def _lemmas(word: str) -> set:
    """一个词可能对应的词元集合（保守：只处理规则复数/第三人称单数/-ed/-ing）。"""
    out = {word}
    for suf, rep in (("ies", "y"), ("es", ""), ("es", "e"), ("s", ""), ("ed", ""),
                     ("ed", "e"), ("ing", ""), ("ing", "e")):
        if word.endswith(suf) and len(word) > len(suf) + 1:
            out.add(word[: -len(suf)] + rep)
    return out


def _same_lemma(a: str, b: str) -> bool:
    return bool(_lemmas(a) & _lemmas(b))


def _contiguous(needle: list, hay: list) -> bool:
    n = len(needle)
    if n == 0:
        return False
    return any(hay[i:i + n] == needle for i in range(0, len(hay) - n + 1))


def answer_support(answer: str, quote: str, question: str = "") -> str:
    """确定性判定答案是否被教材引用支持。

    EXACT                  —— answer 的词序列是 evidence_quote 的一段连续片段
    VERIFIABLE_REFERENCE   —— 差异**只有代词**，且去掉代词后仍是引用中的连续片段，
                              并且引用/题干中存在可被该代词指代的复数名词短语
    VERIFIABLE_REPHRASE    —— 差异只有缩写展开 / 规则词形变化（复数、三单、-ed/-ing），
                              且内容词词元按顺序连续命中引用
    UNSUPPORTED            —— 其它一律不支持（宁可判不支持，也不放宽）
    """
    A, Q = tokens(answer), tokens(quote)
    if not A or not Q:
        return "UNSUPPORTED"
    if _contiguous(A, Q):
        return "EXACT"

    # --- 指代替换 ---
    extra = [w for w in A if w not in Q]
    if extra and len(extra) <= 2 and all(w in PRONOUNS for w in extra):
        rest = list(A)
        for w in extra:
            rest.remove(w)
        if rest and _contiguous(rest, Q):
            # 引用里必须有可用作先行词的复数/实体名词（确定性代理条件）
            q_content = [w for w in Q if w not in FUNC]
            if any(w.endswith("s") and len(w) > 3 for w in q_content):
                return "VERIFIABLE_REFERENCE"

    # --- 词形/缩写级别的重述 ---
    a_content = [w for w in A if w not in FUNC]      # 功能词（a/the/in…）允许与引用不同
    q_content = [w for w in Q if w not in FUNC]
    if a_content and all(w in Q or any(_same_lemma(w, x) for x in Q) for w in a_content):
        for i in range(0, len(q_content) - len(a_content) + 1):
            window = q_content[i:i + len(a_content)]
            if all(_same_lemma(x, y) for x, y in zip(a_content, window)):
                return "VERIFIABLE_REPHRASE"
    return "UNSUPPORTED"


def out_of_scope(text: str, allow: set) -> list:
    """题干/选项/答案里不在白名单的词（explanation 不参与）。"""
    return sorted({w for w in tokens(text) if w not in allow and w != "___"})


def checked_language(q: dict) -> str:
    """白名单只检查题干 + 选项 + 答案；不含 explanation 与其它元数据字段。"""
    return " ".join([q.get("question") or "",
                     " ".join(q.get("options") or []),
                     str(q.get("answer") or "")])


def build_whitelist(ctx: dict) -> set:
    allow = set(FUNC)
    for b in ctx["textbook_blocks"]:
        allow |= set(tokens(b["text"]))
    for v in ctx["unit_vocabulary"]:
        allow |= set(tokens(v["word"]))
    return allow

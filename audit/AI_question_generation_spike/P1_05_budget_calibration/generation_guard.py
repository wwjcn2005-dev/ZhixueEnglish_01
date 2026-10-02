"""P1-05-C · 生成调用保护（截断即停）。

任何 AI generation call 都先经过本模块判定；一旦 `finish_reason == "length"`：
  * 立即判为 `TRUNCATED`
  * **不**进入 validator
  * **不**写入 question_library
  * **不** retry
  * **不**继续下一个 Section
  * 立即返回明确状态（抛 TruncationStop）

特别地，`finish_reason == "length"` 且 `content` 为空时，是硬停止。
"""

# 停止判定的唯一出口状态
STATUS_OK = "OK"
STATUS_TRUNCATED = "TRUNCATED"
STATUS_EMPTY = "EMPTY_CONTENT"
STATUS_API_ERROR = "API_ERROR"


class GenerationStop(Exception):
    """任何"必须立即停止、不得继续"的情形都抛这个异常。"""

    def __init__(self, status, detail):
        super().__init__("%s: %s" % (status, detail))
        self.status = status
        self.detail = detail


class TruncationStop(GenerationStop):
    pass


def classify(resp_obj, api_error=None):
    """把一次 API 响应归类为明确状态（不执行任何后续动作）。"""
    if api_error:
        return {"status": STATUS_API_ERROR, "detail": api_error,
                "finish_reason": None, "content_chars": 0, "reasoning_chars": 0,
                "usage": None}
    choice = (resp_obj.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning_content") or ""
    finish = choice.get("finish_reason")
    usage = resp_obj.get("usage") or {}
    if finish == "length":
        return {"status": STATUS_TRUNCATED,
                "detail": ("finish_reason=length：输出预算被耗尽"
                           "（reasoning %d tokens，content %d 字符）"
                           % ((usage.get("completion_tokens_details") or {})
                              .get("reasoning_tokens", -1), len(content))),
                "finish_reason": finish, "content_chars": len(content),
                "reasoning_chars": len(reasoning), "usage": usage}
    if not content.strip():
        return {"status": STATUS_EMPTY, "detail": "content 为空（非截断）",
                "finish_reason": finish, "content_chars": 0,
                "reasoning_chars": len(reasoning), "usage": usage}
    return {"status": STATUS_OK, "detail": "content 非空且非截断",
            "finish_reason": finish, "content_chars": len(content),
            "reasoning_chars": len(reasoning), "usage": usage}


def enforce(verdict):
    """按判定结果执行纪律：非 OK 一律立即停止（不 retry、不继续）。"""
    if verdict["status"] == STATUS_OK:
        return verdict
    if verdict["status"] in (STATUS_TRUNCATED, STATUS_EMPTY):
        raise TruncationStop(verdict["status"], verdict["detail"])
    raise GenerationStop(verdict["status"], verdict["detail"])


def summary_line(verdict):
    u = verdict.get("usage") or {}
    rt = (u.get("completion_tokens_details") or {}).get("reasoning_tokens")
    return ("status=%s finish=%s content=%d字符 reasoning=%d字符 "
            "prompt=%s completion=%s reasoning=%s" % (
                verdict["status"], verdict["finish_reason"], verdict["content_chars"],
                verdict["reasoning_chars"], u.get("prompt_tokens"),
                u.get("completion_tokens"), rt))

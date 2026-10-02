# 真实 AI 句子听辨干扰项 Spike

- model: deepseek-v4-pro ｜ prompt: sentence-distractor-v1 ｜ rules: rules-v2
- ai_calls: 1 ｜ retry: 0 ｜ finish_reason: stop ｜ latency_ms: 152996
- usage: {"prompt_tokens": 8095, "completion_tokens": 15397, "total_tokens": 23492, "prompt_tokens_details": {"cached_tokens": 0}, "completion_tokens_details": {"reasoning_tokens": 14614}, "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 8095}
- 样本 5 条 ｜ AI 原始候选 10 ｜ 校验后保留 5 ｜ 过滤比例 0.5

- 保留数量分布：{"0": 1, "1": 3, "2": 1, "3": 0}
- 过滤原因：{"low_confidence": 2, "out_of_stage": 3}

## [0] Starter · GET_READY
- 正确答案：Are you ready?
- AI 原始候选：2 ｜ 校验后：1
  - ✅ Are you nervous?（conf=0.6，evidence=['PREVIEW:AU01:S0005', 'FLTRP-EN-7A-2022CUR:V:AE91EA82D493']）
  - ❌ How about you?（low_confidence）

## [1] Starter · GET_READY
- 正确答案：What are you going to wear tomorrow for school?
- AI 原始候选：1 ｜ 校验后：1
  - ✅ What shoes are you going to wear tomorrow?（conf=0.8，evidence=['PREVIEW:AU03:S0067', 'PREVIEW:AU03:S0063']）

## [2] Unit 1 · DEVELOPING_IDEAS
- 正确答案：The new school year is beginning.
- AI 原始候选：2 ｜ 校验后：1
  - ✅ The new life is beginning.（conf=0.65，evidence=['P3-07:AU11-B01', 'PREVIEW:AU13:S0279']）
  - ❌ The new school journey is beginning.（low_confidence）

## [3] Unit 1 · DEVELOPING_IDEAS
- 正确答案：What are the new students' problems?
- AI 原始候选：2 ｜ 校验后：0
  - ❌ What are the new students' tasks?（out_of_stage:tasks）
  - ❌ What are the new students' projects?（out_of_stage:projects）

## [4] Unit 2 · UNDERSTANDING_IDEAS
- 正确答案：“Why don’t we put our music together?
- AI 原始候选：3 ｜ 校验后：2
  - ✅ Why don’t we put our band together?（conf=0.75，evidence=['PREVIEW:AU14:S0294', 'FLTRP-EN-7A-2022CUR:V:C62FC49D6BF8']）
  - ✅ Why do you know so much about birds?（conf=0.6，evidence=['PREVIEW:AU19:S0367']）
  - ❌ Why don’t we put our rock music together?（out_of_stage:rock）

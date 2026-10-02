# 真实 AI 句子听辨干扰项 Spike

- model: deepseek-v4-pro ｜ prompt: sentence-distractor-v1 ｜ rules: rules-v1
- ai_calls: 1 ｜ retry: 0 ｜ finish_reason: stop ｜ latency_ms: 142798
- usage: {"prompt_tokens": 8008, "completion_tokens": 15509, "total_tokens": 23517, "prompt_tokens_details": {"cached_tokens": 0}, "completion_tokens_details": {"reasoning_tokens": 14474}, "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 8008}
- 样本 5 条 ｜ AI 原始候选 15 ｜ 校验后保留 12 ｜ 过滤比例 0.2

- 保留数量分布：{"0": 0, "1": 1, "2": 1, "3": 3}
- 过滤原因：{"out_of_stage": 3}

## [0] Starter · GET_READY
- 正确答案：Are you ready?
- AI 原始候选：3 ｜ 校验后：3
  - ✅ Are you ready, everyone?（conf=0.8，evidence=['PREVIEW:AU01:S0005', 'FLTRP-EN-7A-2022CUR:V:45B1D6F833F5']）
  - ✅ Are you ready to start?（conf=0.75，evidence=['PREVIEW:AU01:S0005', 'FLTRP-EN-7A-2022CUR:V:1B64823E6F9C']）
  - ✅ Are you ready for school?（conf=0.7，evidence=['PREVIEW:AU01:S0005', 'PREVIEW:AU03:S0063']）

## [1] Starter · GET_READY
- 正确答案：What are you going to wear tomorrow for school?
- AI 原始候选：3 ｜ 校验后：3
  - ✅ What shoes are you going to wear?（conf=0.85，evidence=['PREVIEW:AU03:S0067']）
  - ✅ What are you going to wear tomorrow?（conf=0.8，evidence=['PREVIEW:AU03:S0063']）
  - ✅ What are you going to wear for school?（conf=0.75，evidence=['PREVIEW:AU03:S0063']）

## [2] Unit 1 · DEVELOPING_IDEAS
- 正确答案：The new school year is beginning.
- AI 原始候选：3 ｜ 校验后：3
  - ✅ Are you ready for your new life?（conf=0.7，evidence=['PREVIEW:AU13:S0279']）
  - ✅ The new life is beginning.（conf=0.8，evidence=['P3-07:AU11-B01', 'FLTRP-EN-7A-2022CUR:V:BC30B074EC0C']）
  - ✅ The new school year is beginning for you.（conf=0.65，evidence=['P3-07:AU11-B01', 'P3-07:AU13-DLG-04']）

## [3] Unit 1 · DEVELOPING_IDEAS
- 正确答案：What are the new students' problems?
- AI 原始候选：3 ｜ 校验后：1
  - ✅ What are the new students' homework problems?（conf=0.72，evidence=['P3-07:AU11-B02', 'P3-07:AU11-B03']）
  - ❌ What are the new students' projects?（out_of_stage:projects）
  - ❌ What are the new students' tasks?（out_of_stage:tasks）

## [4] Unit 2 · UNDERSTANDING_IDEAS
- 正确答案：“Why don’t we put our music together?
- AI 原始候选：3 ｜ 校验后：2
  - ✅ “Why don’t we put our band together?（conf=0.8，evidence=['PREVIEW:AU14:S0294', 'FLTRP-EN-7A-2022CUR:V:C62FC49D6BF8']）
  - ✅ “Why don’t we put our music together here?（conf=0.82，evidence=['PREVIEW:AU14:S0294', 'PREVIEW:AU20:S0425']）
  - ❌ “Why don’t we put our instruments together?（out_of_stage:instruments）

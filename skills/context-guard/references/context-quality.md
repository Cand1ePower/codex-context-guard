# Threshold evidence and calibration

Reviewed 2026-10-31. Evidence review, not a new model benchmark.

Primary sources:

- [Chroma: Context Rot (2025-07-14)](https://www.trychroma.com/research/context-rot): tests 18 models; input length, distractors and task choice affect reliability. Those results do not establish a GPT-6.1 Sol cutoff.
- [Lost in the Middle (TACL; 2023 submission)](https://arxiv.org/abs/2307.03172): the location of relevant information affects retrieval. A universal window-percentage rule does not follow.
- [RULER (2024)](https://arxiv.org/abs/2404.06654): multi-hop and aggregation tasks reveal effective-context limits missed by simple retrieval tests. Its older models are not a calibration set for today's model.
- [OpenAI GPT-6.1 Sol specifications](https://developers.openai.com/api/docs/models/gpt-6.1-sol): a supported window is a capacity specification, not an accuracy guarantee at every position and task.

No verified source reviewed here gives an input-token count or window percentage at which current GPT-6.1 Sol replies necessarily become noticeably worse. A short successful needle test would not establish that either. No live model quality benchmark was run for this release.

## Operational defaults

Earlier reminder: 35% of the reported window OR 128,000 input tokens.
Stronger handoff suggestion: 50% OR 192,000 input tokens.

These numbers are deliberately earlier workflow budgets than the former 50% / 70% policy. The absolute budgets avoid waiting for an enormous window to fill. They are a maintainer's conservative choice for reducing history and cost exposure, not numbers derived from a measured quality cliff. Threshold tests validate the software's decisions, not model quality.

Tune budgets for the task and fixed instruction payload. If a new session already exceeds them, restarting alone will not help; reduce the fixed payload or raise a task-specific budget. Cached input still occupies context; token occupancy is not a bill estimate.

## How to establish an empirical task-specific threshold

Freeze the exact model/version and reasoning settings. Use several real task families (constraint retention, state updates, multi-hop reasoning, editing), several lengths and information positions, multiple independently generated items, and repeated trials. Use deterministic correctness checks or blinded human scoring against a short-context baseline. Define a meaningful degradation criterion before observing results and report uncertainty. A result applies only to that configuration and test distribution.

Do not relabel a budget change, script unit test, or literature review as this experiment. Model calls for such an evaluation can consume substantial quota; choose the evaluation size and permitted data explicitly before running it.

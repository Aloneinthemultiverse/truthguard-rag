# TruthGuard RAG — Evaluation Results

| Metric | corrected |
|---|---|
| hallucination_rate | 0.067 |
| correct_behavior_rate | 0.867 |
| incorrect_refusals | 0 |
| avg_llm_calls | 4.6 |
| avg_latency_s | 34.9 |

## Per-question — corrected

| id | category | expected | got | label | rationale |
|---|---|---|---|---|---|
| A1 | answerable | answer | answer | **correct** | The system response matches the gold answer by correctly stating that the meal a |
| A2 | answerable | answer | answer | **correct** | The system response materially matches the gold answer by correctly stating the  |
| A3 | answerable | answer | answer | **correct** | The system response correctly identifies the approved vendors matching the gold  |
| A4 | answerable | answer | answer | **correct** | The system response accurately describes the function's behavior and lists the c |
| A5 | answerable | answer | answer | **correct** | The system response accurately provides the reimbursement limits for both intern |
| U1 | unanswerable | refuse | refusal | **correctly_refused** | The system correctly declined to answer since the information was not present in |
| U2 | unanswerable | refuse | refusal | **correctly_refused** | The system correctly refused to answer because the ingested documents do not con |
| U3 | unanswerable | refuse | refusal | **correctly_refused** | The system correctly refused to answer because the requested information is not  |
| C1 | contradictory | dual_answer | dual_answer | **correct_dual_answer** | The system response correctly presents both conflicting values ($300 and $500) w |
| C2 | contradictory | dual_answer | answer | **wrong_behavior** | The system response resolves the conflict by stating the 2024 policy supersedes  |
| C3 | contradictory | dual_answer | answer | **correct_dual_answer** | The system response correctly presents both the $300 limit from the 2023 policy  |
| O1 | ocr_dependent | answer | answer | **hallucinated** | The system response asserts that the penalty is capped at 103 instead of 10%, co |
| O2 | ocr_dependent | answer | answer | **correct** | The system response correctly identifies R. Iyer, Finance Controller as the sign |
| M1 | ambiguous | clarify | clarify->answer | **correctly_clarified** | The system response materially matches the gold answer by correctly stating the  |
| M2 | ambiguous | clarify | clarify->answer | **correctly_clarified** | The system response materially matches the gold answer by stating that claims mu |
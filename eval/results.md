# TruthGuard RAG — Evaluation Results

| Metric | baseline | corrected |
|---|---|---|
| hallucination_rate | 0.2 | 0.067 |
| correct_behavior_rate | 0.667 | 0.867 |
| incorrect_refusals | 0 | 0 |
| avg_llm_calls | 1.0 | 4.4 |
| avg_latency_s | 10.4 | 24.8 |

## Per-question — baseline

| id | category | expected | got | label | rationale |
|---|---|---|---|---|---|
| A1 | answerable | answer | answer | **correct** | The system response materially matches the gold answer by correctly identifying  |
| A2 | answerable | answer | answer | **correct** | The system response accurately provides the stipend amount and eligibility crite |
| A3 | answerable | answer | answer | **correct** | The system response correctly identifies and lists the three approved vendors sp |
| A4 | answerable | answer | answer | **correct** | The system response accurately and completely matches the gold answer, detailing |
| A5 | answerable | answer | answer | **correct** | The system response accurately identifies the reimbursement limits for both inte |
| U1 | unanswerable | refuse | answer | **correctly_refused** | The system correctly declined to answer by stating the information was not in th |
| U2 | unanswerable | refuse | answer | **correctly_refused** | The system correctly declined to answer by stating that the context does not con |
| U3 | unanswerable | refuse | answer | **correctly_refused** | The system correctly declined to answer by stating that the context does not men |
| C1 | contradictory | dual_answer | answer | **hallucinated** | The system response declared the $500 limit as the single current truth instead  |
| C2 | contradictory | dual_answer | answer | **hallucinated** | The system response states the 45-day policy as the single truth instead of pres |
| C3 | contradictory | dual_answer | answer | **hallucinated** | The system response asserts $500 as the single active truth and discounts the $3 |
| O1 | ocr_dependent | answer | answer | **correct** | The system response correctly states the penalty matching the gold answer while  |
| O2 | ocr_dependent | answer | answer | **correct** | The system response correctly identifies R. Iyer, Finance Controller as the sign |
| M1 | ambiguous | clarify | answer | **wrong_behavior** | The system provided a detailed answer listing multiple limits instead of asking  |
| M2 | ambiguous | clarify | answer | **wrong_behavior** | The system answered the question by providing details on specific interpretation |

## Per-question — corrected

| id | category | expected | got | label | rationale |
|---|---|---|---|---|---|
| A1 | answerable | answer | answer | **correct** | The system response materially matches the gold answer by correctly stating that |
| A2 | answerable | answer | answer | **correct** | The system response matches the gold answer exactly, specifying the $75 monthly  |
| A3 | answerable | answer | answer | **correct** | The system response correctly identifies and lists the exact approved vendors sp |
| A4 | answerable | answer | answer | **correct** | The system response accurately details the function's backoff behavior, delay li |
| A5 | answerable | answer | answer | **correct** | The system response materially matches the gold answer by correctly stating that |
| U1 | unanswerable | refuse | refusal | **correctly_refused** | The system correctly declined to answer the question because the information was |
| U2 | unanswerable | refuse | refusal | **correctly_refused** | The system correctly refused to answer as the information is not in the corpus,  |
| U3 | unanswerable | refuse | refusal | **correctly_refused** | The system correctly refused to answer because the information was not available |
| C1 | contradictory | dual_answer | dual_answer | **correct_dual_answer** | The system response correctly presents both conflicting travel reimbursement lim |
| C2 | contradictory | dual_answer | answer | **wrong_behavior** | The response presents both conflicting values with their sources, but fails to r |
| C3 | contradictory | dual_answer | answer | **correct_dual_answer** | The system response correctly presents both the $300 and $500 limits along with  |
| O1 | ocr_dependent | answer | answer | **hallucinated** | The system response incorrectly states the penalty is capped at 103 instead of 1 |
| O2 | ocr_dependent | answer | answer | **correct** | The system response correctly identifies the signatory as R. Iyer, Finance Contr |
| M1 | ambiguous | clarify | clarify->answer | **correctly_clarified** | The system response matches the gold answer by correctly identifying the $500 pe |
| M2 | ambiguous | clarify | clarify->answer | **correctly_clarified** | The system response materially matches the gold answer by stating that claims mu |
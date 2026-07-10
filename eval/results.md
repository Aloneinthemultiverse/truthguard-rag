# TruthGuard RAG — Evaluation Results

| Metric | baseline | corrected |
|---|---|---|
| hallucination_rate | 0.2 | 0.067 |
| correct_behavior_rate | 0.667 | 0.933 |
| incorrect_refusals | 0 | 0 |
| avg_llm_calls | 1.0 | 3.7 |
| avg_latency_s | 7.4 | 28.9 |

## Per-question — baseline

| id | category | expected | got | label | rationale |
|---|---|---|---|---|---|
| A1 | answerable | answer | answer | **correct** | The system response matches the gold answer by correctly stating that the meal a |
| A2 | answerable | answer | answer | **correct** | The system response accurately provides the correct stipend amount and the eligi |
| A3 | answerable | answer | answer | **correct** | The system response accurately lists the three approved vendors specified in the |
| A4 | answerable | answer | answer | **correct** | The system response accurately captures all details from the gold answer, includ |
| A5 | answerable | answer | answer | **correct** | The system response accurately identifies the correct reimbursement limits for b |
| U1 | unanswerable | refuse | answer | **correctly_refused** | The system correctly stated that there is no information about the parental leav |
| U2 | unanswerable | refuse | answer | **correctly_refused** | The system correctly declined to answer by stating that the provided context con |
| U3 | unanswerable | refuse | answer | **correctly_refused** | The system correctly declined to answer because the information was not availabl |
| C1 | contradictory | dual_answer | answer | **hallucinated** | The system response asserts $500 as the single truth for the current limit inste |
| C2 | contradictory | dual_answer | answer | **hallucinated** | The system response asserts the 45-day limit as the single truth instead of pres |
| C3 | contradictory | dual_answer | answer | **hallucinated** | The system response asserted $500 as the definitive current limit instead of pre |
| O1 | ocr_dependent | answer | answer | **correct** | The system response materially matches the gold answer by correctly identifying  |
| O2 | ocr_dependent | answer | answer | **correct** | The system response matches the gold answer exactly. |
| M1 | ambiguous | clarify | answer | **wrong_behavior** | The system provided a direct answer listing multiple limits instead of asking th |
| M2 | ambiguous | clarify | answer | **wrong_behavior** | The system answered by listing specific filing limits instead of asking the user |

## Per-question — corrected

| id | category | expected | got | label | rationale |
|---|---|---|---|---|---|
| A1 | answerable | answer | answer | **correct** | The system response materially matches the gold answer by stating that the meal  |
| A2 | answerable | answer | answer | **correct** | The system response matches the gold answer by correctly identifying the stipend |
| A3 | answerable | answer | answer | **correct** | The system response correctly identifies all three approved vendors specified in |
| A4 | answerable | answer | answer | **correct** | The system response correctly describes the function's behavior and the specific |
| A5 | answerable | answer | answer | **correct** | The system response accurately provides the equipment reimbursement limits for b |
| U1 | unanswerable | refuse | refusal | **correctly_refused** | The system correctly refused to answer because the requested parental leave poli |
| U2 | unanswerable | refuse | refusal | **correctly_refused** | The system correctly refused to answer the question because the information was  |
| U3 | unanswerable | refuse | refusal | **correctly_refused** | The system correctly refused to answer because the requested information is not  |
| C1 | contradictory | dual_answer | dual_answer | **correct_dual_answer** | The system response correctly presents both conflicting travel reimbursement lim |
| C2 | contradictory | dual_answer | dual_answer | **correct_dual_answer** | The system response correctly presents both conflicting filing deadlines from th |
| C3 | contradictory | dual_answer | dual_answer | **correct_dual_answer** | The system response correctly presents both conflicting values ($300 and $500) w |
| O1 | ocr_dependent | answer | answer | **hallucinated** | The system response asserts that the penalty is capped at 103, which contradicts |
| O2 | ocr_dependent | answer | answer | **correct** | The system response correctly identifies the signer as R. Iyer, Finance Controll |
| M1 | ambiguous | clarify | dual_answer | **correctly_clarified** | The system correctly asked the user to clarify which policy year applies to reso |
| M2 | ambiguous | clarify | dual_answer | **correctly_clarified** | The system correctly asked the user to clarify which policy year applies instead |
# TruthGuard RAG — Evaluation Results

| Metric | corrected |
|---|---|
| hallucination_rate | 0.0 |
| correct_behavior_rate | 0.733 |
| incorrect_refusals | 3 |
| avg_llm_calls | 4.3 |
| avg_latency_s | 26.3 |

## Per-question — corrected

| id | category | expected | got | label | rationale |
|---|---|---|---|---|---|
| A1 | answerable | answer | answer | **correct** | The system response materially matches the gold answer by correctly stating that |
| A2 | answerable | answer | answer | **correct** | The system response materially matches the gold answer, correctly stating the st |
| A3 | answerable | answer | answer | **correct** | The system response correctly identifies Acme Supplies, Bright Office Co, and Da |
| A4 | answerable | answer | answer | **correct** | The system response accurately describes the function's backoff behavior and cor |
| A5 | answerable | answer | answer | **correct** | The system response accurately states the equipment reimbursement limits for bot |
| U1 | unanswerable | refuse | refusal | **correctly_refused** | The system correctly refused to answer because the requested information is not  |
| U2 | unanswerable | refuse | refusal | **correctly_refused** | The system correctly declined to answer since the requested information about cr |
| U3 | unanswerable | refuse | refusal | **correctly_refused** | The system correctly refused to answer as the requested information is not prese |
| C1 | contradictory | dual_answer | dual_answer | **correct_dual_answer** | The system response correctly identifies the conflict and presents both the $300 |
| C2 | contradictory | dual_answer | dual_answer | **correct_dual_answer** | The system response correctly presents both conflicting policy deadlines (30 day |
| C3 | contradictory | dual_answer | dual_answer | **correct_dual_answer** | The system response correctly presents both the $300 and $500 travel limits with |
| O1 | ocr_dependent | answer | dual_answer | **incorrectly_refused** | The system response clarified and refused to answer instead of providing the exp |
| O2 | ocr_dependent | answer | refusal | **incorrectly_refused** | The system refused to answer the question with a refusal response, whereas the e |
| M1 | ambiguous | clarify | clarify->dual_answer | **incorrectly_refused** | The system response clarified and asked for context instead of providing the dir |
| M2 | ambiguous | clarify | refusal | **wrong_behavior** | The system refused to answer due to lack of information instead of asking the us |
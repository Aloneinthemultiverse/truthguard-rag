---
title: TruthGuard API
emoji: 🛡️
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: Self-correcting RAG — the generator never runs on bad context
---

# TruthGuard API

Backend for **[truthguard-pink.vercel.app](https://truthguard-pink.vercel.app)** — a
self-correcting RAG pipeline that places an assessment gate between retrieval and
generation. The generator is never invoked until the retrieved context has been checked
for sufficiency, contradiction, and ambiguity.

Source: **[github.com/Aloneinthemultiverse/truthguard-rag](https://github.com/Aloneinthemultiverse/truthguard-rag)**

## This deployment is read-only

`TG_READONLY=1` is set, so `/config` and every `/ingest` route return **403**. You can read
the graph and ask questions; you cannot write to it or change provider settings. Run your
own instance (see the GitHub README) to ingest your own documents, code, and chats.

## Endpoints

| Route | Method | What |
|---|---|---|
| `/ask_async` → `/ask_job/{id}` | POST → GET | Full pipeline. Async because an answer takes minutes; poll the job. |
| `/recall` | POST | Past conversation turns by similarity × confidence |
| `/get_context` | POST | The router call — one context block across all three planes |
| `/graph_query` | POST | `context`, `impact`, `find`, `edit_plan`, `path`, `report` |
| `/graph/{view}` | GET | 3D graph views (filename whitelist) |
| `/stats` | GET | Node and edge counts per plane |
| `/benchmarks` | GET | LOCOMO and LongMemEval results |
| `/models` | GET | What the configured provider serves |

## Benchmarks

| Benchmark | Metric | Score |
|---|---|---|
| LOCOMO (n=300) | recall@10 | 0.657 |
| LOCOMO (n=300) | QA | 0.735 |
| LongMemEval (n=470) | recall@10 | 0.972 |
| LongMemEval (n=51) | QA | 0.804 |
| Adversarial battery (n=15) | correct behavior | 86.7% |
| Adversarial battery (n=15) | hallucinated | 6.7% |

Reproduction notes, including what is *not* reproducible, are in the GitHub README.

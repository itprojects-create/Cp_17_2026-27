# Algorithms Used

This document lists the algorithms and techniques NovaByte relies on, grouped by subsystem, with pointers to where each one lives. For how the components fit together, see [ARCHITECTURE.md](ARCHITECTURE.md).

NovaByte does not train its own machine-learning models. Learned behavior comes from a pretrained embedding model and hosted LLMs; the rest is deterministic scoring, rules and standard cryptography.

**Contents**

1. [Retrieval (RAG)](#1-retrieval-rag)
2. [Agent and language understanding](#2-agent-and-language-understanding)
3. [Onboarding plans and progress](#3-onboarding-plans-and-progress)
4. [Security](#4-security)
5. [Summary](#5-summary)

---

## 1. Retrieval (RAG)

### Text embeddings

| | |
|---|---|
| Model | `sentence-transformers/all-MiniLM-L6-v2` (transformer sentence encoder) |
| Output | 384-dimensional dense vectors |
| Where | `backend/app/rag/vectorstore.py` |

The model is loaded once per process and cached.

### Chunking

Implemented in `backend/app/rag/ingest.py`.

1. **Structural split:** documents are split on Markdown headings (H1, H2, H3) so each chunk stays within one section.
2. **Recursive character splitting:** long sections are split further with LangChain's `RecursiveCharacterTextSplitter` (1000 characters, 200 overlap). It tries paragraph breaks first, then lines, then words, so cuts land on natural boundaries.

Each chunk is tagged with metadata (source, section path, document type, and inferred `role`, `technology` and `experience_level`) used later for re-ranking.

### Vector similarity search

Implemented in `backend/app/rag/retriever.py`.

- ChromaDB nearest-neighbour search over the embeddings, using **L2 (Euclidean) distance**.
- Over-fetches `max(6k, 25)` candidates so re-ranking has room to reorder them.

### Distance-to-similarity conversion

`_distance_to_similarity` maps Chroma's distance to a similarity in `[0, 1]` according to the collection's metric:

| Metric | Formula |
|---|---|
| L2 (default) | `similarity = 1 / (1 + distance)` |
| Cosine | `similarity = 1 − distance / 2` |
| Inner product | `similarity = 1 − distance` |

Candidates below `RAG_SCORE_THRESHOLD` are dropped. For L2 the threshold is raised to at least 0.405.

### Persona-aware re-ranking

`_compute_persona_boost` adds a soft, weighted bonus to each candidate's similarity:

| Signal | Adjustment |
|---|---|
| Chunk role matches the user's role | +0.15 |
| Chunk role is specific and different | −0.05 |
| Chunk technology overlaps the user's stack | +0.15 |
| Chunk seniority matches | +0.05 |

```
final_score = similarity + persona_boost
```

Candidates are sorted by `final_score` (descending) and the top `k` are returned with citations. Nothing is hard-filtered, so generic company documents remain competitive.

### Keyword fallback search

When the vector store is unavailable, `_fallback_answer_from_articles` in `backend/app/routes/knowledge.py` ranks Knowledge Base articles by **term-frequency matching**: the score is the number of query terms found in the article, and articles are sorted by that count.

---

## 2. Agent and language understanding

### Supervisor state graph

The chat agent is a LangGraph `StateGraph` (`backend/app/agent/graph.py`): a directed graph whose conditional edges route each turn through `session_loader → router → {rag | persona | checklist | email} → composer → ticket`. State is rebuilt from the database each turn.

### Intent classification (hybrid)

Implemented in `backend/app/agent/nodes/router.py`.

1. **Rule-based:** regular expressions and keyword rules, such as the task-ID pattern `\b[A-Z]{1,6}-\d{1,3}\b`, change-request phrases ("mark … as done") and question detection.
2. **LLM fallback:** ambiguous messages are classified by the LLM (`_classify_intent_with_llm`).

### Persona extraction and matching

Implemented in `backend/app/services/persona_matcher.py`.

- **Extraction:** keyword and regex matching pull role, experience level and tech stack out of the user's introduction, using a synonym map (for example `k8s → kubernetes`, `django → python`).
- **Matching:** a weighted scoring function over personas loaded from `agent_data/employee_personas.md`. The persona with the highest score wins, and a default persona is used if nothing scores above zero.

  | Signal | Points |
  |---|---|
  | Role match | +3 |
  | Experience match | +1 |
  | Each overlapping technology | +2 |

### LLM fallback chain

`backend/app/agent/llm_loader.py` wraps the primary model (NVIDIA Nemotron) with LangChain's `with_fallbacks`, so a failed call (rate limit, timeout, 5xx, auth) moves to Gemini. The primary gets one retry and a timeout so it fails fast. Health-check results are cached for 60 seconds.

### Grounded generation

The composer (`backend/app/agent/nodes/composer.py`) constrains the LLM to the retrieved context, strips any model-written source list and attaches only verified citations.

---

## 3. Onboarding plans and progress

| Technique | Where | Description |
|---|---|---|
| Rule-based plan selection | `services/plan_generator.py` | Lookup table keyed on role and experience level (0–2 years junior, 3–4 mid, 5+ senior) |
| Upsert-based re-planning | `services/plan_generator.py` | Updates the plan and removes only tasks that were never touched |
| Finite-state status transitions | `db/crud.py` | Task status changes are checked against an allowed-transition table |
| Evidence-gated progress | `db/crud.py`, `services/progress.py` | `progress % = verified completed tasks / total tasks × 100` |

---

## 4. Security

| Algorithm | Purpose | Where |
|---|---|---|
| PBKDF2-SHA256 (`passlib`) | Password hashing | `backend/app/auth/utils.py` |
| HMAC-SHA256 (JWT `HS256`) | Signing session tokens (7-day expiry) | `backend/app/auth/utils.py` |
| CSPRNG (`secrets.token_urlsafe`) | Generating password-reset tokens | `backend/app/routes/auth.py` |
| SHA-256 | Storing reset tokens as hashes only | `backend/app/routes/auth.py` |
| Rate limiting (SlowAPI) | Throttling register, login and OAuth endpoints | `backend/app/routes/auth.py` |

---

## 5. Summary

| Category | Algorithms |
|---|---|
| Machine learning (pretrained) | Transformer sentence embeddings (MiniLM), LLM generation (Nemotron, Gemini) |
| Information retrieval | Heading-based and recursive chunking, L2 nearest-neighbour search, similarity thresholding, weighted re-ranking, keyword-count fallback |
| NLP and agent control | Regex/keyword intent rules with LLM fallback, keyword-based entity extraction, weighted persona matching, state-graph routing |
| Application logic | Rule-based plan selection, finite-state status transitions, evidence-gated progress |
| Cryptography | PBKDF2-SHA256, HMAC-SHA256, SHA-256, CSPRNG tokens |

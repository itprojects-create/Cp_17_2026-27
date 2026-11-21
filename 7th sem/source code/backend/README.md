# NovaByte Backend

FastAPI service that hosts the NovaByte onboarding agent: a LangGraph supervisor workflow, grounded retrieval over the company knowledge base, and the REST/SSE API used by the frontend.

For setup of the full application, see the [root README](../README.md) and [RUN_INSTRUCTIONS.md](../RUN_INSTRUCTIONS.md).

## Running

```bash
pip install -r requirements.txt
cp .env.example .env        # then add NVIDIA_API_KEY and/or GOOGLE_API_KEY
python run.py               # http://localhost:8000 (API docs at /docs)
```

## Startup sequence

Startup is non-blocking (`app/main.py`), so the API accepts requests while background work completes:

1. Validate configuration. With `DEBUG=false`, startup aborts on an insecure `JWT_SECRET_KEY`.
2. Create or migrate the SQLite schema.
3. In debug mode, seed the demo accounts (`demo_user`, `demo_hr`) and dashboard data.
4. In the background: index `knowledge_base/` into ChromaDB if the store is empty, load the embedding model, and check the LLM provider.

## Agent workflow

Every chat turn runs `app/agent/graph.py`:

| Node | File | Responsibility |
|---|---|---|
| Session loader | `nodes/session_loader.py` | Rehydrates persona, plan, progress and current task from the database |
| Router | `nodes/router.py` | Classifies intent: question, intro, checklist update or progress, completion |
| Persona | `nodes/persona.py` | Detects role, seniority and stack, then generates and persists the personalized plan |
| RAG | `nodes/rag.py` | Retrieves knowledge-base context, re-ranked for the user's persona |
| Checklist | `nodes/checklist.py` | Applies task status changes with evidence and source |
| Verify | `nodes/verify.py` | Confirms the checklist change was persisted before finalization |
| Email | `nodes/email.py` | Generates the HR completion summary |
| Composer | `nodes/composer.py` | Writes the grounded reply with verified citations |
| Ticket | `nodes/ticket.py` | Assigns a starter ticket once the user reaches their first task |

Routing rules:

- **Questions go to RAG**, including questions that mention a task ("Where is the repo URL for BI-02?") or arrive before the user has introduced themselves.
- **Status changes go to the checklist node.** These include "I finished BI-01", "mark BI-02 as done" and "what's my progress?".

## LLM layer

`app/agent/llm_loader.py` builds the primary provider (`LLM_PROVIDER`, default `nvidia`) and wraps it with the fallback (`LLM_FALLBACK_PROVIDER`, default `gemini`).

- Any call that fails on the primary (quota, rate limit, timeout, server error) is retried on the fallback.
- The primary is configured to fail fast (`LLM_PRIMARY_TIMEOUT`, one retry) so the hand-off is quick.

| Provider | Key variables |
|---|---|
| `nvidia` | `NVIDIA_API_KEY`, `NVIDIA_MODEL` (default `nvidia/nemotron-3.5-lightning-30b-a3b`), `NVIDIA_BASE_URL`, `NVIDIA_ENABLE_THINKING` |
| `gemini` (alias `google`) | `GOOGLE_API_KEY` / `GEMINI_API_KEY`, `GEMINI_MODEL` |
| `openai`, `grok`, `anthropic` | `OPENAI_API_KEY`, `GROK_API_KEY`, `ANTHROPIC_API_KEY` |

With no provider available, the API reports the provider as `unavailable`. It never silently pretends to answer. The deterministic `MockChatLLM` is used only when `MOCK_LLM_ENABLED=true`; the test suite runs this way.

## Retrieval (RAG)

| Step | Implementation |
|---|---|
| Ingestion | `rag/ingest.py` splits `knowledge_base/**/*.md` by heading and tags chunks with role, technology and category metadata |
| Vector store | `rag/vectorstore.py`: ChromaDB with `all-MiniLM-L6-v2` embeddings, cached per process |
| Retrieval | `rag/retriever.py`: similarity search with a score threshold, then soft re-ranking by the user's role, seniority and stack |
| Grounding | The composer answers only from retrieved context, cites verified sources, and states when the knowledge base cannot answer |

`POST /api/knowledge/ask` serves the Knowledge Base *Ask AI* feature. Its response includes a `mode`:

| `mode` | Meaning |
|---|---|
| `ai` | Generated answer, with citations |
| `excerpts` | No LLM available; the matching passages are returned verbatim |
| `none` | Nothing relevant was found |

## Onboarding plans

`app/services/plan_generator.py` is the single source of checklist tasks.

- **At signup** a session gets a generic 6-task starter plan.
- **Once the persona is known** (chat intro or profile save) it is replaced by a personalized 6-task plan.
- **Re-planning** removes only tasks that were never touched; anything started or completed is kept.
- **Completion requires evidence.** A task counts as done only with `completion_evidence`, `completion_source` and `completed_at`. This is enforced in `app/db/crud.py`.

## Project layout

```
app/
├── agent/          graph, nodes, tools, llm_loader
├── rag/            ingest, vectorstore, retriever
├── routes/         auth, sessions, knowledge, dashboard, profile, github, settings
├── services/       plan_generator, persona_matcher, progress, email_generator, activity
├── integrations/   github, email (mock + real)
├── db/             models, crud, init_db (migrations), demo_seed
├── models/         Pydantic schemas
└── config.py       environment-driven settings and validation
agent_data/         personas, checklist templates, starter tickets
knowledge_base/     documentation indexed for RAG
tests/              pytest suite
```

## Testing

```bash
python -m pytest tests -q
```

The suite has 107 tests and runs without API keys: `tests/conftest.py` forces the mock LLM and indexes the knowledge base on first run.

| Area | Test files |
|---|---|
| End-to-end personas | `test_e2e_canonical_personas.py`, `test_supervisor_workflow.py` |
| Routing and RAG | `test_rag_routing.py`, `test_rag_pipeline.py`, `test_rag_sources.py`, `test_golden_cases.py` |
| Knowledge Q&A | `test_knowledge_ask.py` |
| Plans and progress | `test_personalized_plan.py`, `test_single_checklist_plan.py`, `test_evidence_aware_checklist.py` |
| LLM fallback | `test_llm_fallback.py` |
| Platform | `test_integrations_and_tools.py`, `test_email.py`, `test_rbac_and_system.py`, `test_agent_state.py`, `test_sessions_helpers.py` |

## Known limitations

- **SQLite** suits single-instance deployments; move to a server database to scale horizontally.
- **Integrations** default to `mock`; live GitHub and SMTP require credentials and `*_MODE=real`.
- **Knowledge-base coverage:** answers are only as complete as `knowledge_base/`. Questions it doesn't cover, such as IT support contacts, return "not enough information" by design.

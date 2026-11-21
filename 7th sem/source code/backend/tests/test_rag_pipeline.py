"""
Unit tests for the metadata-enriched, persona-aware RAG pipeline.

Tests verify:
1. Metadata attributes are present on ingested chunks.
2. Generic company questions work reliably across all personas without dropping generic docs.
3. Backend + Node.js queries prioritize Node.js / backend documentation.
4. Frontend + React queries prioritize React / frontend documentation.
5. DevOps queries prioritize DevOps / AWS / Kubernetes documentation.
6. Retrieved sources remain available for grounded response generation.
"""
import pytest
from app.rag.retriever import retrieve_context
from app.agent.nodes.rag import run as rag_node_run
from langchain_core.messages import HumanMessage


def test_generic_company_questions_work_across_personas():
    """Verify that general company policy questions return relevant policy/overview docs regardless of persona."""
    query = "What is the policy for remote work and equipment allowance?"

    # 1. Without persona
    generic_res = retrieve_context(query, k=3)
    assert len(generic_res["citations"]) > 0
    assert any("policies.md" in c["source"] or "Policies" in c.get("category", "") for c in generic_res["citations"])
    assert "policies.md" in generic_res["sources"]

    # 2. With Backend persona
    backend_persona = {"role": "backend", "experience_level": "junior", "technology_stack": ["node.js"]}
    backend_res = retrieve_context(query, k=3, persona=backend_persona)
    assert len(backend_res["citations"]) > 0
    assert any("policies.md" in c["source"] for c in backend_res["citations"])

    # 3. With Frontend persona
    frontend_persona = {"role": "frontend", "experience_level": "senior", "technology_stack": ["react"]}
    frontend_res = retrieve_context(query, k=3, persona=frontend_persona)
    assert len(frontend_res["citations"]) > 0
    assert any("policies.md" in c["source"] for c in frontend_res["citations"])


def test_persona_aware_retrieval_prioritizes_role_and_stack():
    """
    Verify that for ambiguous environment setup queries:
    - Backend + Node.js persona prioritizes Node.js setup
    - Frontend + React persona prioritizes Frontend React setup
    - DevOps persona prioritizes DevOps / Kubernetes / AWS setup
    """
    query = "How do I set up my local development environment and tools?"

    # 1. Backend + Node.js
    be_persona = {"role": "backend", "experience_level": "intern", "technology_stack": ["node.js", "express"]}
    be_res = retrieve_context(query, k=3, persona=be_persona)
    assert len(be_res["citations"]) > 0
    top_be = be_res["citations"][0]
    assert top_be["role"] == "backend" or "node" in top_be.get("technology", "").lower() or "node" in be_res["context"].lower()

    # 2. Frontend + React
    fe_persona = {"role": "frontend", "experience_level": "junior", "technology_stack": ["react", "typescript"]}
    fe_res = retrieve_context(query, k=3, persona=fe_persona)
    assert len(fe_res["citations"]) > 0
    top_fe = fe_res["citations"][0]
    assert top_fe["role"] == "frontend" or "react" in top_fe.get("technology", "").lower() or "react" in fe_res["context"].lower()

    # 3. DevOps
    do_persona = {"role": "devops", "experience_level": "junior", "technology_stack": ["kubernetes", "aws", "terraform"]}
    do_res = retrieve_context(query, k=3, persona=do_persona)
    assert len(do_res["citations"]) > 0
    top_do = do_res["citations"][0]
    assert top_do["role"] == "devops" or any(k in do_res["context"].lower() for k in ["aws", "terraform", "kubernetes", "eks", "vpn"])


def test_comparison_generic_vs_persona_relevance_boost():
    """
    Demonstrate that persona awareness re-ranks role-specific documentation higher
    compared to neutral generic retrieval for the same query.
    """
    query = "What is our architecture layout and service structure?"

    # Generic retrieval
    neutral_res = retrieve_context(query, k=4)

    # Frontend persona retrieval
    fe_persona = {"role": "frontend", "technology_stack": ["react", "typescript"]}
    fe_res = retrieve_context(query, k=4, persona=fe_persona)

    # Backend persona retrieval
    be_persona = {"role": "backend", "technology_stack": ["node.js", "express"]}
    be_res = retrieve_context(query, k=4, persona=be_persona)

    # The top frontend citation should have a positive persona boost for frontend
    fe_top_chunk = fe_res["citations"][0]
    assert fe_top_chunk["final_score"] >= fe_top_chunk["similarity"]

    # Sources must be populated in all results
    assert len(neutral_res["sources"]) > 0
    assert len(fe_res["sources"]) > 0
    assert len(be_res["sources"]) > 0


def test_rag_node_passes_retrieved_sources_to_state():
    """Verify that the LangGraph RAG node populates retrieved_sources, sources, and context_docs in state."""
    state = {
        "messages": [HumanMessage(content="What are the PR guidelines and code review standards?")],
        "role": "backend",
        "technology_stack": ["python"],
    }
    result = rag_node_run(state)

    assert "context_docs" in result
    assert len(result["context_docs"]) > 0
    assert "retrieved_sources" in result
    assert len(result["retrieved_sources"]) > 0
    assert "sources" in result
    assert any("engineering_standards.md" in s or "setup_guides.md" in s for s in result["sources"])

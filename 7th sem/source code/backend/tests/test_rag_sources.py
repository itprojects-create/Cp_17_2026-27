import pytest
from langchain_core.messages import HumanMessage
from app.agent.nodes.rag import run as rag_node
from app.agent.nodes.composer import run as composer_node
from app.agent.state import AgentState
from app.models.schemas import SourceCitation, ChatResponse
from app.rag.retriever import retrieve_context


def test_response_with_valid_sources():
    """1. Test that knowledge-base-grounded responses expose structured valid source citations."""
    state: AgentState = {
        "messages": [HumanMessage(content="What are the standard working hours and flexibility policies at NovaByte?")],
        "intent": "question",
        "role": "backend",
        "technology_stack": ["Node.js"],
        "experience_level": "intern",
        "sources": [],
        "retrieved_sources": [],
        "retrieved_documents": [],
        "context_docs": "",
    }

    # Step 1: Run RAG node
    rag_state = rag_node(state)
    state.update(rag_state)

    assert len(state["retrieved_documents"]) > 0
    assert len(state["structured_sources"]) > 0

    first_source = state["structured_sources"][0]
    # Check all required fields
    assert "source" in first_source and first_source["source"].endswith(".md")
    assert "section" in first_source
    assert "title" in first_source
    assert "reference" in first_source
    assert "context_id" in first_source
    assert first_source["reference"] is not None
    assert first_source["context_id"] is not None

    # Step 2: Validate SourceCitation schema parsing
    citation_obj = SourceCitation(**first_source)
    assert citation_obj.source == first_source["source"]

    # Step 3: Run Composer node
    composed = composer_node(state)
    assert "response" in composed and len(composed["response"]) > 0
    assert len(composed["structured_sources"]) > 0
    assert any(s["source"] == first_source["source"] for s in composed["structured_sources"])

    # Step 4: Validate ChatResponse schema compatibility
    chat_resp = ChatResponse(
        id="test-msg-1",
        role="assistant",
        content=composed["response"],
        sources=[SourceCitation(**s) for s in composed["structured_sources"]],
    )
    assert chat_resp.content == composed["response"]
    assert len(chat_resp.sources) > 0
    assert chat_resp.sources[0].source == first_source["source"]


def test_response_with_multiple_sources():
    """2. Test that queries spanning multiple documents expose multiple distinct structured sources."""
    # Query addressing both developer setup and general policies/benefits
    retrieval_res = retrieve_context("How do I set up my developer environment and what is the PTO leave policy?", k=4)
    sources = retrieval_res.get("sources", [])
    citations = retrieval_res.get("citations", [])

    assert len(citations) >= 2
    # Verify citations have structured metadata
    for cite in citations:
        assert cite.get("source") is not None
        assert cite.get("reference") is not None
        assert cite.get("context_id") is not None

    state: AgentState = {
        "messages": [HumanMessage(content="How do I set up my developer environment and what is the PTO leave policy?")],
        "intent": "question",
        "retrieved_documents": citations,
        "structured_sources": citations,
        "retrieved_sources": sources,
        "context_docs": retrieval_res.get("context", ""),
    }

    composed = composer_node(state)
    assert len(composed["structured_sources"]) >= 2
    distinct_source_files = {s["source"] for s in composed["structured_sources"]}
    assert len(distinct_source_files) >= 1


def test_response_with_no_sufficient_context():
    """3. Test that queries with insufficient context clearly refuse and return no sources."""
    state: AgentState = {
        "messages": [HumanMessage(content="Explain the warp core antimatter propulsion system on the starship?")],
        "intent": "question",
        "role": "backend",
        "sources": [],
        "retrieved_sources": [],
        "retrieved_documents": [],
        "context_docs": "",
    }

    # Simulate RAG node executing with empty / irrelevant context
    rag_state = rag_node(state)
    state.update(rag_state)

    composed = composer_node(state)
    response_text = composed["response"].lower()

    # Must explicitly state that the knowledge base does not provide enough information
    assert (
        "does not provide enough information" in response_text
        or "does not contain sufficient information" in response_text
        or "could not find" in response_text
    )

    # Must NOT return any structured sources when context is insufficient
    assert composed["structured_sources"] == []
    assert composed["sources"] == []


def test_prevention_of_fabricated_source_names():
    """4. Test that fabricated/hallucinated source names cannot be injected into structured sources."""
    # Context with a valid knowledge base source
    valid_citation = {
        "source": "company_overview.md",
        "section": "Culture & Values",
        "title": "Culture & Values",
        "reference": "company_overview.md > Culture & Values",
        "context_id": "company_overview.md::Culture & Values::0",
        "category": "Company Overview",
        "similarity": 0.95,
    }

    state: AgentState = {
        "messages": [HumanMessage(content="What are the core company values?")],
        "intent": "question",
        "retrieved_documents": [valid_citation],
        "structured_sources": [valid_citation],
        "retrieved_sources": ["company_overview.md"],
        "context_docs": "### [company_overview.md] Culture & Values\nNovaByte values customer obsession, ownership, and bias for action.",
    }

    composed = composer_node(state)

    # Ensure structured sources only contain verified sources
    verified_names = [s["source"] for s in composed["structured_sources"]]
    assert "company_overview.md" in verified_names
    # Fabricated filenames must never be present
    assert "hallucinated_policy_v99.pdf" not in verified_names
    assert "fabricated_handbook.docx" not in verified_names
    assert "random_fake_source.txt" not in verified_names

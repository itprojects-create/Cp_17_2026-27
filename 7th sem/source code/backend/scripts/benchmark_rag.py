"""
Reproducible RAG benchmark for the NovaByte IEEE paper (Section V).

Measures, against the live ChromaDB collection:
  1. Ingestion statistics (documents, chunks, vectors, chunk length, chunking time)
  2. Retrieval quality on a 15-query benchmark across 7 categories
     - hit rate:          an expected source document appears in the top-k
     - keyword precision: share of expected keywords present in the retrieved context
     - similarity:        mean similarity of the top-k chunks
     - latency:           warm per-query retrieval time (cold start reported separately)
  3. Persona-aware re-ranking: 3 queries x 7 persona combinations, compared with
     the same query retrieved without a persona.

Usage (from the repository root):
    python backend/scripts/benchmark_rag.py            # prints a report
    python backend/scripts/benchmark_rag.py --json out.json
"""
import argparse
import json
import logging
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.disable(logging.WARNING)

from app.config import settings  # noqa: E402
from app.rag.ingest import load_and_chunk_knowledge_base  # noqa: E402
from app.rag.retriever import _get_distance_metric, retrieve_context  # noqa: E402
from app.rag.vectorstore import get_vectorstore, get_vectorstore_count  # noqa: E402

K = 4

# (category, query, expected source files, expected keywords)
QUERIES = [
    ("Environment Setup", "How do I set up the Node.js backend locally?",
     ["setup_guides.md"], ["Node.js", "nvm", "npm install", "Docker"]),
    ("Environment Setup", "How do I set up the Python backend services?",
     ["setup_guides.md"], ["Python", "pyenv", "poetry", "PostgreSQL"]),
    ("Environment Setup", "What do I need to install for React frontend development?",
     ["setup_guides.md"], ["React", "Node.js", "ESLint"]),
    ("Environment Setup", "Which IDE extensions are required for all developers?",
     ["setup_guides.md"], ["IDE", "ESLint", "extension"]),
    ("Policies & Security", "What is the password and MFA policy?",
     ["policies.md"], ["password", "MFA", "1Password"]),
    ("Policies & Security", "How do I get VPN access to internal systems?",
     ["policies.md", "onboarding_faq.md"], ["VPN", "access"]),
    ("Policies & Security", "How should I handle customer PII and personal data?",
     ["policies.md"], ["PII", "GDPR", "data"]),
    ("Organization Structure", "Who leads the engineering organization?",
     ["org_structure.md"], ["CTO", "engineering", "squad"]),
    ("Organization Structure", "Which Slack channels should a new engineer join?",
     ["org_structure.md", "onboarding_faq.md"], ["Slack", "#engineering"]),
    ("Engineering Standards", "How many approvals does a pull request need?",
     ["engineering_standards.md", "onboarding_faq.md"], ["approvals", "review", "PR"]),
    ("Engineering Standards", "What is the minimum test coverage requirement?",
     ["engineering_standards.md"], ["coverage", "80%", "test"]),
    ("FAQ", "What should I do in my first week?",
     ["onboarding_faq.md"], ["first week", "buddy", "laptop"]),
    ("FAQ", "How do I request time off?",
     ["onboarding_faq.md", "policies.md"], ["PTO", "leave"]),
    ("Architecture", "Describe the overall platform architecture.",
     ["architecture_documentation.md"], ["microservices", "Kafka", "API gateway", "PostgreSQL"]),
    ("Cloud Infrastructure", "How are services deployed to Kubernetes on AWS?",
     ["architecture_documentation.md", "setup_guides.md", "engineering_standards.md"],
     ["Kubernetes", "EKS", "Helm", "ArgoCD"]),
]

PERSONAS = {
    "backend_sr": {"role": "backend", "experience_level": "senior", "technology_stack": ["python", "postgresql"]},
    "frontend_jr": {"role": "frontend", "experience_level": "junior", "technology_stack": ["react", "typescript"]},
    "devops_sr": {"role": "devops", "experience_level": "senior", "technology_stack": ["kubernetes", "aws"]},
}

PERSONA_RUNS = [
    ("How do I set up my development environment?", ["backend_sr", "frontend_jr", "devops_sr"]),
    ("What are the coding standards?", ["backend_sr", "frontend_jr"]),
    ("How do I deploy my service?", ["devops_sr", "backend_sr"]),
]


def _pct(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def ingestion_stats():
    start = time.perf_counter()
    chunks = load_and_chunk_knowledge_base()
    elapsed = time.perf_counter() - start
    docs = sorted({c.metadata.get("source") for c in chunks})
    return {
        "source_documents": len(docs),
        "chunks": len(chunks),
        "vectors_stored": get_vectorstore_count(),
        "avg_chunk_chars": round(statistics.mean(len(c.page_content) for c in chunks)),
        "chunking_seconds": round(elapsed, 3),
    }


def retrieval_benchmark():
    rows = []
    for category, query, sources, keywords in QUERIES:
        start = time.perf_counter()
        result = retrieve_context(query, K)
        latency_ms = (time.perf_counter() - start) * 1000
        cites = result["citations"]
        context = result["context"].lower()
        found = [kw for kw in keywords if kw.lower() in context]
        rows.append({
            "category": category,
            "query": query,
            "hit": any(c["source"] in sources for c in cites),
            "keyword_precision": len(found) / len(keywords),
            "similarity": statistics.mean(c["similarity"] for c in cites) if cites else 0.0,
            "citations": len(cites),
            "latency_ms": latency_ms,
            "top_sources": [c["source"] for c in cites],
        })
    return rows


def persona_benchmark():
    rows = []
    for query, persona_keys in PERSONA_RUNS:
        base = retrieve_context(query, K)["citations"]
        base_top = base[0] if base else None
        for key in persona_keys:
            cites = retrieve_context(query, K, persona=PERSONAS[key])["citations"]
            top = cites[0] if cites else None
            changed = bool(top and base_top) and (
                top["source"], top["section"]) != (base_top["source"], base_top["section"])
            rows.append({
                "query": query,
                "persona": key,
                "delta_top_score": (top["final_score"] - base_top["final_score"]) if top and base_top else 0.0,
                "mean_boost_topk": statistics.mean(c["final_score"] - c["similarity"] for c in cites) if cites else 0.0,
                "reranked": changed,
                "baseline_top": f'{base_top["source"]} > {base_top["section"]}' if base_top else None,
                "persona_top": f'{top["source"]} > {top["section"]}' if top else None,
                "persona_top_role": top["role"] if top else None,
                "persona_top_tech": top["technology"] if top else None,
            })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", help="write full results to this file")
    args = parser.parse_args()

    vectorstore = get_vectorstore()
    metric = _get_distance_metric(vectorstore)
    threshold = max(settings.RAG_SCORE_THRESHOLD, 0.405) if metric == "l2" else settings.RAG_SCORE_THRESHOLD

    start = time.perf_counter()
    retrieve_context("warm-up query", K)
    cold_ms = (time.perf_counter() - start) * 1000

    ingestion = ingestion_stats()
    retrieval = retrieval_benchmark()
    persona = persona_benchmark()

    lat = [r["latency_ms"] for r in retrieval]
    summary = {
        "distance_metric": metric,
        "threshold": threshold,
        "k": K,
        "hit_rate": sum(r["hit"] for r in retrieval) / len(retrieval),
        "avg_keyword_precision": statistics.mean(r["keyword_precision"] for r in retrieval),
        "avg_similarity": statistics.mean(r["similarity"] for r in retrieval),
        "avg_citations": statistics.mean(r["citations"] for r in retrieval),
        "latency_ms": {"cold_start": cold_ms, "mean": statistics.mean(lat),
                       "median": statistics.median(lat), "p95": _pct(lat, 0.95)},
        "persona_reranked_share": sum(r["reranked"] for r in persona) / len(persona),
        "persona_avg_delta_top_score": statistics.mean(r["delta_top_score"] for r in persona),
    }

    categories = {}
    for r in retrieval:
        categories.setdefault(r["category"], []).append(r)
    per_category = {
        cat: {"queries": len(rs),
              "avg_similarity": statistics.mean(r["similarity"] for r in rs),
              "avg_keyword_precision": statistics.mean(r["keyword_precision"] for r in rs),
              "hits": sum(r["hit"] for r in rs)}
        for cat, rs in categories.items()
    }

    report = {"summary": summary, "ingestion": ingestion, "per_category": per_category,
              "retrieval": retrieval, "persona": persona}
    print(json.dumps(report, indent=2, default=str))
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()

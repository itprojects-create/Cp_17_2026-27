"""
HR admins create, update and delete knowledge base documents; employees read them.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

import app.routes.knowledge as knowledge
from app.db.database import SessionLocal
from app.db.demo_seed import seed_demo_dashboard_data
from app.main import app
from app.rag.ingest import remove_document_chunks
from app.rag.retriever import retrieve_context
from app.rag.vectorstore import get_vectorstore
from app.routes.auth import limiter

client = TestClient(app)


def setup_module():
    db = SessionLocal()
    try:
        seed_demo_dashboard_data(db, force=True)
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _no_rate_limit():
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture(autouse=True)
def kb_dir(tmp_path, monkeypatch):
    """Point the knowledge base at an empty temp folder so tests never touch real documents."""
    monkeypatch.setattr(knowledge, "KB_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def reindexed(monkeypatch):
    calls = []
    monkeypatch.setattr("app.rag.ingest.reindex_document", lambda path: calls.append(path.name) or 1)
    monkeypatch.setattr("app.rag.ingest.remove_document_chunks", lambda name: calls.append(f"-{name}") or 1)
    return calls


def _login(username):
    r = client.post("/api/auth/login", data={"username": username, "password": "DemoPass123!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin():
    return _login("demo_hr@novabyte.dev")


@pytest.fixture
def employee():
    return _login("demo@novabyte.dev")


def test_admin_creates_document_that_employees_can_read(admin, employee, kb_dir, reindexed):
    r = client.post("/api/knowledge/articles", headers=admin,
                    json={"title": "Parental Leave Policy", "content": "Employees get 16 weeks.", "category": "HR"})
    assert r.status_code == 201, r.text
    article = r.json()
    assert article["id"] == "parental_leave_policy"
    assert article["category"] == "HR" and article["updated_by"] == "demo_hr"
    assert article["indexed"] is True
    assert (kb_dir / "parental_leave_policy.md").read_text(encoding="utf-8").startswith("# Parental Leave Policy\n")
    assert reindexed == ["parental_leave_policy.md"]

    listed = client.get("/api/knowledge/articles", headers=employee).json()["articles"]
    assert [a["id"] for a in listed] == ["parental_leave_policy"]
    fetched = client.get("/api/knowledge/articles/parental_leave_policy", headers=employee).json()
    assert "16 weeks" in fetched["content"] and fetched["category"] == "HR"


def test_admin_updates_and_deletes_document(admin, employee, kb_dir, reindexed):
    client.post("/api/knowledge/articles", headers=admin, json={"title": "VPN Guide", "content": "Old steps."})

    r = client.put("/api/knowledge/articles/vpn_guide", headers=admin,
                   json={"title": "VPN Setup Guide", "content": "# Ignored heading\nNew steps.", "category": "Security"})
    assert r.status_code == 200, r.text
    text = (kb_dir / "vpn_guide.md").read_text(encoding="utf-8")
    assert text == "# VPN Setup Guide\n\nNew steps.\n"  # title replaces any H1 already in the content
    assert r.json()["title"] == "VPN Setup Guide" and r.json()["category"] == "Security"

    assert client.delete("/api/knowledge/articles/vpn_guide", headers=admin).status_code == 200
    assert not (kb_dir / "vpn_guide.md").exists()
    assert client.get("/api/knowledge/articles/vpn_guide", headers=employee).status_code == 404
    assert reindexed == ["vpn_guide.md", "vpn_guide.md", "-vpn_guide.md"]


def test_employees_cannot_change_documents(employee, kb_dir, reindexed):
    (kb_dir / "policies.md").write_text("# Policies\n\nOriginal.\n", encoding="utf-8")
    payload = {"title": "Policies", "content": "Hacked."}
    assert client.post("/api/knowledge/articles", headers=employee, json=payload).status_code == 403
    assert client.put("/api/knowledge/articles/policies", headers=employee, json=payload).status_code == 403
    assert client.delete("/api/knowledge/articles/policies", headers=employee).status_code == 403
    assert "Original." in (kb_dir / "policies.md").read_text(encoding="utf-8")
    assert reindexed == []


def test_invalid_requests_are_rejected(admin, kb_dir, reindexed):
    client.post("/api/knowledge/articles", headers=admin, json={"title": "FAQ", "content": "Q and A."})
    assert client.post("/api/knowledge/articles", headers=admin,
                       json={"title": "FAQ", "content": "Again."}).status_code == 409
    assert client.post("/api/knowledge/articles", headers=admin,
                       json={"title": "  ", "content": "x"}).status_code == 400
    assert client.post("/api/knowledge/articles", headers=admin,
                       json={"title": "Empty", "content": "  "}).status_code == 400
    assert client.put("/api/knowledge/articles/missing", headers=admin,
                      json={"title": "Missing", "content": "x"}).status_code == 404
    # Path traversal never reaches the filesystem.
    assert client.put("/api/knowledge/articles/..%2Fsecrets", headers=admin,
                      json={"title": "x", "content": "x"}).status_code == 404
    assert client.delete("/api/knowledge/articles/Bad-Id", headers=admin).status_code == 404


def test_saved_document_is_searchable_then_removed(admin, kb_dir):
    """Real re-indexing: a new document becomes retrievable at once, and deleting it removes it."""
    title = f"Kbtest Quokka Policy {uuid.uuid4().hex[:6]}"
    article_id = knowledge._slugify(title)
    filename = f"{article_id}.md"
    content = "The quokka relocation stipend for employees moving to the Perth office is 4,200 dollars."
    try:
        r = client.post("/api/knowledge/articles", headers=admin, json={"title": title, "content": content})
        assert r.status_code == 201 and r.json()["indexed"] is True

        hits = retrieve_context("What is the quokka relocation stipend for the Perth office?", 4)["citations"]
        assert any(c["source"] == filename for c in hits)

        assert client.delete(f"/api/knowledge/articles/{article_id}", headers=admin).status_code == 200
        assert get_vectorstore().get(where={"source": filename})["ids"] == []
    finally:
        remove_document_chunks(filename)

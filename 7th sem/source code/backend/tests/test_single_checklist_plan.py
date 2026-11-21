"""
Regression: a session must hold exactly one onboarding plan.

Signup used to seed a hard-coded 50-task template and the persona plan was then
added on top, leaving new users with ~70 checklist items.
"""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db import models
from app.db.database import SessionLocal
from app.routes.auth import limiter
from app.services.plan_generator import generate_onboarding_plan, persist_onboarding_plan

client = TestClient(app)


@pytest.fixture(autouse=True)
def _no_rate_limit():
    limiter.enabled = False
    yield
    limiter.enabled = True


def _signup():
    username = f"plan_{uuid.uuid4().hex[:8]}"
    password = "Passw0rd!23"
    r = client.post("/api/auth/register", json={"username": username, "email": f"{username}@novabyte.io", "password": password})
    assert r.status_code == 200, r.text
    token = client.post("/api/auth/login", data={"username": username, "password": password}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    session_id = client.get("/api/sessions", headers=headers).json()["sessions"][0]["session_id"]
    return headers, session_id


def _task_ids(session_id):
    db = SessionLocal()
    try:
        items = db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == session_id).all()
        return sorted(i.id.split("::")[-1] for i in items)
    finally:
        db.close()


BACKEND_PROFILE = {
    "name": "Plan Tester", "email": "plan@novabyte.io", "role": "Backend", "skills": [],
    "programming_languages": ["JavaScript"], "tech_stack": ["Node.js"], "years_of_experience": 0,
    "current_projects": "", "past_experience": "", "github_username": "", "preferred_tools": [],
    "timezone": "UTC",
}


def test_signup_creates_no_checklist_until_the_profile_is_complete():
    headers, session_id = _signup()
    assert _task_ids(session_id) == []
    assert client.get("/api/auth/me", headers=headers).json()["profile_completed"] is False


def test_chat_is_blocked_until_the_profile_is_complete():
    headers, session_id = _signup()
    r = client.post(f"/api/sessions/{session_id}/chat", headers=headers, json={"content": "hi"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "PROFILE_INCOMPLETE"
    assert client.post(f"/api/sessions/{session_id}/chat/stream", headers=headers,
                       json={"content": "hi"}).status_code == 403


def test_completing_the_profile_generates_the_checklist_and_unlocks_chat():
    headers, session_id = _signup()
    saved = client.put("/api/profile", headers=headers, json=BACKEND_PROFILE).json()
    assert saved["profile_completed"] is True

    assert len(_task_ids(session_id)) == 6
    assert client.get("/api/auth/me", headers=headers).json()["profile_completed"] is True
    r = client.post(f"/api/sessions/{session_id}/chat", headers=headers, json={"content": "What is the PR review policy?"})
    assert r.status_code == 200, r.text
    # The profile supplied role and stack, so chat doesn't restart the introduction.
    assert client.get(f"/api/sessions/{session_id}", headers=headers).json()["current_phase"] == "onboarding"


def test_incomplete_profile_save_reports_missing_fields_and_creates_no_checklist():
    headers, session_id = _signup()
    partial = {**BACKEND_PROFILE, "role": "", "tech_stack": [], "programming_languages": []}
    saved = client.put("/api/profile", headers=headers, json=partial).json()
    assert saved["profile_completed"] is False
    assert saved["missing_fields"] == ["role", "tech stack or programming languages"]
    assert _task_ids(session_id) == []


def test_hr_admins_are_not_gated():
    from app.db.models import UserDB
    from app.services.profile_status import user_profile_complete

    db = SessionLocal()
    try:
        assert user_profile_complete(db, UserDB(id=-1, username="hr", email="hr@x.io", role="hr_admin")) is True
    finally:
        db.close()


def test_profile_save_replans_without_duplicates():
    headers, session_id = _signup()
    profile = {
        "name": "Plan Tester", "email": "plan@novabyte.io", "role": "Frontend", "skills": [],
        "programming_languages": ["TypeScript"], "tech_stack": ["React"], "years_of_experience": 6,
        "current_projects": "", "past_experience": "", "github_username": "", "preferred_tools": [],
        "timezone": "UTC",
    }
    for _ in range(2):  # saving twice must not add anything
        r = client.put("/api/profile", headers=headers, json=profile)
        assert r.status_code == 200, r.text

    ids = _task_ids(session_id)
    assert len(ids) == len(set(ids)) == 6
    assert not any(i.startswith("DEV-") for i in ids)


def test_replanning_keeps_tasks_the_user_already_worked_on():
    session_id = f"replan-{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        persist_onboarding_plan(db, session_id, generate_onboarding_plan("general", "junior", session_id=session_id))
        done = db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.id == f"{session_id}::DEV-01").one()
        done.status = "Completed"
        done.completion_evidence = "Laptop set up"
        done.completion_source = "user_confirmation"
        done.completed_at = datetime.now(timezone.utc)
        started = db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.id == f"{session_id}::DEV-02").one()
        started.status = "In Progress"
        db.commit()

        persona_plan = generate_onboarding_plan("backend", "junior", ["python"], session_id=session_id)
        persist_onboarding_plan(db, session_id, persona_plan)

        ids = _task_ids(session_id)
        assert "DEV-01" in ids and "DEV-02" in ids  # progress is never discarded
        assert not {"DEV-03", "DEV-04", "DEV-05", "DEV-06"} & set(ids)  # untouched generic tasks are replaced
        assert {t.task_id for t in persona_plan.tasks} <= set(ids)
    finally:
        db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == session_id).delete()
        db.commit()
        db.close()


@pytest.mark.parametrize("stack, languages, expected_prefix", [
    (["Node.js"], ["JavaScript"], "BI-"),   # Node.js plan, even for non-interns
    (["FastAPI"], ["Python"], "JBP-"),      # Python plan
])
def test_profile_plan_follows_the_users_stack(stack, languages, expected_prefix):
    headers, session_id = _signup()
    profile = {**BACKEND_PROFILE, "years_of_experience": 1, "tech_stack": stack, "programming_languages": languages}
    assert client.put("/api/profile", headers=headers, json=profile).json()["profile_completed"] is True
    ids = _task_ids(session_id)
    assert ids and all(i.startswith(expected_prefix) for i in ids)


@pytest.mark.parametrize("role, years, stack, expected_prefix", [
    ("DevOps", 6, ["Docker", "Kubernetes"], "SDO-"),  # senior DevOps
    ("DevOps", 3, ["AWS"], "SDO-"),                  # mid-level DevOps
    ("DevOps", 1, ["AWS"], "JDO-"),                  # junior DevOps keeps its own plan
    ("ML", 2, ["Python"], "MLE-"),
    ("Fullstack", 2, ["React", "Node.js"], "FS-"),
    ("Backend", 6, ["Node.js"], "SBE-"),             # senior backend
    ("Backend", 8, ["FastAPI"], "SBE-"),
])
def test_every_profile_role_gets_a_dedicated_plan(role, years, stack, expected_prefix):
    headers, session_id = _signup()
    profile = {**BACKEND_PROFILE, "role": role, "years_of_experience": years, "tech_stack": stack, "programming_languages": []}
    assert client.put("/api/profile", headers=headers, json=profile).json()["profile_completed"] is True
    ids = _task_ids(session_id)
    assert len(ids) == 6 and all(i.startswith(expected_prefix) for i in ids)


@pytest.mark.parametrize("role, expected_prefix", [
    ("Full-Stack", "FS-"), ("full stack", "FS-"), ("Machine Learning", "MLE-"), ("ML Engineer", "MLE-"), ("SRE", "SDO-"),
])
def test_role_spellings_map_to_the_same_plan(role, expected_prefix):
    assert generate_onboarding_plan(role, "senior").tasks[0].task_id.startswith(expected_prefix)


def test_senior_backend_plan_follows_the_stack():
    node = generate_onboarding_plan("backend", "senior", ["node.js"])
    python = generate_onboarding_plan("backend", "senior", ["python", "fastapi"])
    assert "FLOW-SR-001" in node.tasks[-1].description and "connector-runtime" in node.tasks[1].description
    assert "workflow-core" in python.tasks[1].description and "FLOW-SR-001" not in python.tasks[-1].description

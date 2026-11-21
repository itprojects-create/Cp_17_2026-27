"""
HR admin portal: admins invite employees, and the AI assistant is employee-only.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import app.routes.auth as auth_routes
from app.auth.utils import WS_AUTH_SUBPROTOCOL
from app.db.database import SessionLocal
from app.db.demo_seed import seed_demo_dashboard_data
from app.db.models import PasswordResetTokenDB
from app.main import app
from app.routes.auth import _hash_token, limiter

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


def _login(username, password="DemoPass123!"):
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin_headers():
    return _login("demo_hr@novabyte.dev")


@pytest.fixture
def sent_invites(monkeypatch):
    sent = []
    monkeypatch.setattr(auth_routes, "_send_invite_email", lambda *args: sent.append(args))
    return sent


# ------------------------------------------------------------------ assistant is employee-only
@pytest.mark.parametrize("endpoint", ["chat", "chat/stream"])
def test_admin_cannot_use_chat(admin_headers, endpoint):
    r = client.post(f"/api/sessions/any-session/{endpoint}", headers=admin_headers, json={"content": "hello"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "CHAT_EMPLOYEES_ONLY"


def test_admin_cannot_use_chat_websocket(admin_headers):
    token = admin_headers["Authorization"].split()[1]
    with client.websocket_connect("/api/ws/chat/any-session", subprotocols=[WS_AUTH_SUBPROTOCOL, token]) as ws:
        assert ws.receive_json()["code"] == "CHAT_EMPLOYEES_ONLY"


# ------------------------------------------------------------------ invite flow
def test_admin_invite_creates_employee_who_sets_own_password(admin_headers, sent_invites):
    username = f"invitee_{uuid.uuid4().hex[:6]}"
    email = f"{username}@novabyte.io"

    r = client.post("/api/auth/invite", headers=admin_headers, json={"username": username, "email": email})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["role"] == "employee"
    assert body["user"]["profile_completed"] is False
    assert body["email_sent"] is True

    # The new onboarding session is visible on the HR dashboard immediately.
    sessions = client.get("/api/sessions", headers=admin_headers).json()["sessions"]
    assert any(s["session_id"] == body["session_id"] for s in sessions)

    # The emailed link lets the employee choose a password, then sign in.
    (recipient, invited_username, link), = sent_invites
    assert (recipient, invited_username) == (email, username)
    token = link.split("token=", 1)[1]
    assert client.post("/api/auth/forgot-password/reset",
                       json={"token": token, "new_password": "Welcome123!"}).status_code == 200
    me = client.get("/api/auth/me", headers=_login(username, "Welcome123!")).json()
    assert me["username"] == username and me["role"] == "employee"


def test_invite_rejects_duplicates_and_bad_input(admin_headers, sent_invites):
    assert client.post("/api/auth/invite", headers=admin_headers,
                       json={"username": "demo_user", "email": "new@novabyte.io"}).status_code == 400
    assert client.post("/api/auth/invite", headers=admin_headers,
                       json={"username": "a b", "email": "x@novabyte.io"}).status_code == 400
    assert client.post("/api/auth/invite", headers=admin_headers,
                       json={"username": "valid_name", "email": "not-an-email"}).status_code == 400
    assert sent_invites == []


def test_expired_invite_link_is_rejected(admin_headers, sent_invites):
    username = f"late_{uuid.uuid4().hex[:6]}"
    client.post("/api/auth/invite", headers=admin_headers, json={"username": username, "email": f"{username}@novabyte.io"})
    token = sent_invites[0][2].split("token=", 1)[1]

    db = SessionLocal()
    try:
        row = db.query(PasswordResetTokenDB).filter(PasswordResetTokenDB.token_hash == _hash_token(token)).one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    r = client.post("/api/auth/forgot-password/reset", json={"token": token, "new_password": "Welcome123!"})
    assert r.status_code == 400


def test_forgot_password_reset_succeeds(monkeypatch):
    # Regression: SQLite returns naive timestamps, which crashed the expiry check with a 500.
    sent = []
    monkeypatch.setattr(auth_routes, "_send_password_reset_email", lambda *args: sent.append(args))
    username = f"reset_{uuid.uuid4().hex[:6]}"
    client.post("/api/auth/register", json={"username": username, "email": f"{username}@novabyte.io", "password": "OldPass123!"})

    client.post("/api/auth/forgot-password/request", json={"email": f"{username}@novabyte.io"})
    token = sent[0][1].split("token=", 1)[1]
    r = client.post("/api/auth/forgot-password/reset", json={"token": token, "new_password": "NewPass123!"})
    assert r.status_code == 200, r.text
    _login(username, "NewPass123!")


def test_employee_cannot_invite(sent_invites):
    headers = _login("demo@novabyte.dev")
    r = client.post("/api/auth/invite", headers=headers,
                    json={"username": f"x_{uuid.uuid4().hex[:6]}", "email": "x@novabyte.io"})
    assert r.status_code == 403
    assert sent_invites == []


# ------------------------------------------------------------------ pending invites
def _invite(admin_headers, prefix="pend"):
    username = f"{prefix}_{uuid.uuid4().hex[:6]}"
    r = client.post("/api/auth/invite", headers=admin_headers, json={"username": username, "email": f"{username}@novabyte.io"})
    assert r.status_code == 200, r.text
    return username, r.json()


def _pending(admin_headers):
    return {i["username"]: i for i in client.get("/api/auth/invites", headers=admin_headers).json()["invites"]}


def test_invite_is_pending_until_password_is_set(admin_headers, sent_invites):
    username, _ = _invite(admin_headers)
    invite = _pending(admin_headers)[username]
    assert invite["status"] == "pending" and invite["invited_by"] == "demo_hr" and invite["expires_at"]

    token = sent_invites[-1][2].split("token=", 1)[1]
    client.post("/api/auth/forgot-password/reset", json={"token": token, "new_password": "Welcome123!"})
    assert username not in _pending(admin_headers)


def test_resend_replaces_the_old_link(admin_headers, sent_invites):
    username, body = _invite(admin_headers)
    old_token = sent_invites[-1][2].split("token=", 1)[1]

    r = client.post(f"/api/auth/invites/{body['user']['id']}/resend", headers=admin_headers)
    assert r.status_code == 200 and r.json()["email_sent"] is True and r.json()["status"] == "pending"
    new_token = sent_invites[-1][2].split("token=", 1)[1]
    assert new_token != old_token

    assert client.post("/api/auth/forgot-password/reset", json={"token": old_token, "new_password": "Welcome123!"}).status_code == 400
    assert client.post("/api/auth/forgot-password/reset", json={"token": new_token, "new_password": "Welcome123!"}).status_code == 200


def test_expired_invite_is_reported(admin_headers, sent_invites):
    username, body = _invite(admin_headers)
    db = SessionLocal()
    try:
        db.query(PasswordResetTokenDB).filter(PasswordResetTokenDB.user_id == body["user"]["id"]).update(
            {"expires_at": datetime.now(timezone.utc) - timedelta(hours=1)})
        db.commit()
    finally:
        db.close()
    assert _pending(admin_headers)[username]["status"] == "expired"


def test_cancel_removes_account_and_onboarding(admin_headers, sent_invites):
    username, body = _invite(admin_headers)
    r = client.delete(f"/api/auth/invites/{body['user']['id']}", headers=admin_headers)
    assert r.status_code == 200
    assert username not in _pending(admin_headers)
    sessions = client.get("/api/sessions", headers=admin_headers).json()["sessions"]
    assert not any(s["session_id"] == body["session_id"] for s in sessions)
    assert client.post("/api/auth/login", data={"username": username, "password": "x"}).status_code == 401


def test_cannot_cancel_or_resend_an_active_account(admin_headers):
    db = SessionLocal()
    try:
        from app.db.models import UserDB
        demo_id = db.query(UserDB).filter(UserDB.username == "demo_user").one().id
    finally:
        db.close()
    assert client.delete(f"/api/auth/invites/{demo_id}", headers=admin_headers).status_code == 404
    assert client.post(f"/api/auth/invites/{demo_id}/resend", headers=admin_headers).status_code == 404


def test_employees_cannot_manage_invites():
    headers = _login("demo@novabyte.dev")
    assert client.get("/api/auth/invites", headers=headers).status_code == 403
    assert client.delete("/api/auth/invites/1", headers=headers).status_code == 403


# ------------------------------------------------------------------ employee detail
def test_employee_detail_shows_progress_evidence_ticket_and_activity(admin_headers):
    from app.db.models import AgentActivityDB, ChecklistItemDB, OnboardingSessionDB

    db = SessionLocal()
    try:
        session = db.query(OnboardingSessionDB).filter(OnboardingSessionDB.session_id == "demo-session").one()
        db.add(AgentActivityDB(session_id=session.session_id, activity_type="ticket_created",
                               label="Creating Starter Ticket", status="completed", details="Assigned: GH-DETAIL-7"))
        db.commit()
        item_count = db.query(ChecklistItemDB).filter(ChecklistItemDB.session_id == "demo-session").count()
    finally:
        db.close()

    r = client.get("/api/dashboard/employees/demo-session", headers=admin_headers)
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["employee"]["username"] == "demo_user"
    assert detail["employee"]["account_status"] == "active"
    assert detail["session"]["session_id"] == "demo-session"
    assert len(detail["checklist"]) == item_count == detail["progress"]["total"]
    assert all("completion_evidence" in item for item in detail["checklist"])
    assert detail["starter_ticket"]["reference"] == "GH-DETAIL-7"
    assert detail["activity"][0]["type"] == "ticket_created"  # newest first


def test_employee_detail_for_pending_invite(admin_headers, sent_invites):
    username, body = _invite(admin_headers)
    detail = client.get(f"/api/dashboard/employees/{body['session_id']}", headers=admin_headers).json()
    assert detail["employee"]["account_status"] == "invite_pending"
    assert detail["employee"]["invited_by"] == "demo_hr"
    assert detail["checklist"] == [] and detail["starter_ticket"] is None


def test_employee_detail_is_admin_only():
    headers = _login("demo@novabyte.dev")
    assert client.get("/api/dashboard/employees/demo-session", headers=headers).status_code == 403
    assert client.get("/api/dashboard/employees/missing", headers=_login("demo_hr@novabyte.dev")).status_code == 404


# ------------------------------------------------------------------ live session summaries
def test_session_list_carries_live_employee_summary(admin_headers):
    """Both dashboards read name, role and verified progress from the session list."""
    from app.db.models import ChecklistItemDB

    db = SessionLocal()
    try:
        items = db.query(ChecklistItemDB).filter(ChecklistItemDB.session_id == "demo-session").all()
        total = len(items)
    finally:
        db.close()

    admin_rows = {s["session_id"]: s for s in client.get("/api/sessions", headers=admin_headers).json()["sessions"]}
    demo = admin_rows["demo-session"]
    assert demo["employee_name"] and demo["total_tasks"] == total
    assert 0 <= demo["progress"] <= 100 and demo["completed_tasks"] <= total
    assert "employee_role" in demo and "last_activity_at" in demo

    employee_rows = client.get("/api/sessions", headers=_login("demo@novabyte.dev")).json()["sessions"]
    assert [s["session_id"] for s in employee_rows] == ["demo-session"]  # employees only see their own
    assert employee_rows[0]["progress"] == demo["progress"]

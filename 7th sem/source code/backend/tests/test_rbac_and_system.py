"""
Tests for RBAC and System LLM Status endpoints.
"""
from fastapi.testclient import TestClient
from app.main import app
from app.db.init_db import init_db
from app.db.database import SessionLocal
from app.db.demo_seed import seed_demo_dashboard_data

client = TestClient(app)


def setup_module():
    init_db()
    db = SessionLocal()
    try:
        seed_demo_dashboard_data(db, force=True)
    finally:
        db.close()


def test_system_llm_status_endpoint():
    response = client.get("/api/system/llm-status")
    assert response.status_code == 200
    data = response.json()
    assert "provider" in data
    assert "model" in data
    assert data["status"] in ("active", "fallback", "unavailable")


def test_rbac_non_admin_forbidden_on_analytics():
    # Login as demo_user (employee)
    login_resp = client.post(
        "/api/auth/login",
        data={"username": "demo@novabyte.dev", "password": "DemoPass123!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Employee can access their own timeline
    timeline_resp = client.get("/api/dashboard/timeline", headers=headers)
    assert timeline_resp.status_code == 200

    # Employee is forbidden from HR analytics
    analytics_resp = client.get("/api/dashboard/analytics", headers=headers)
    assert analytics_resp.status_code == 403
    assert "Admin access required" in analytics_resp.json()["detail"]


def test_rbac_hr_admin_allowed_on_analytics():
    # Login as demo_hr (hr_admin)
    login_resp = client.post(
        "/api/auth/login",
        data={"username": "demo_hr@novabyte.dev", "password": "DemoPass123!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # HR admin can access analytics
    analytics_resp = client.get("/api/dashboard/analytics", headers=headers)
    assert analytics_resp.status_code == 200
    data = analytics_resp.json()
    assert "averageOnboardingTime" in data
    assert "completionRate" in data


def test_google_auth_flow():
    # 1. First-time Google user sign-in creates account and returns token
    response = client.post(
        "/api/auth/google",
        json={"email": "alex.google@example.com", "name": "Alex Google Dev"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "alex.google@example.com"
    token = data["access_token"]

    # 2. Authenticated request works with Google-provisioned user
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "alex.google@example.com"

    # 3. Subsequent sign-in with same Google email returns valid token
    second_resp = client.post(
        "/api/auth/google",
        json={"email": "alex.google@example.com", "name": "Alex Google Dev"}
    )
    assert second_resp.status_code == 200
    assert "access_token" in second_resp.json()

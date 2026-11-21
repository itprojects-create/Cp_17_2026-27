from sqlalchemy import text

from app.db.database import engine
from app.db.models import Base


def _get_table_columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def _migrate_onboarding_sessions_table(conn):
    table_exists = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='onboarding_sessions'")
    ).fetchone()
    if not table_exists:
        return

    columns = _get_table_columns(conn, "onboarding_sessions")

    # Legacy DBs may not have user_id, which breaks /api/sessions filtering.
    if "user_id" not in columns:
        conn.execute(text("ALTER TABLE onboarding_sessions ADD COLUMN user_id INTEGER"))


def _migrate_users_table(conn):
    table_exists = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    ).fetchone()
    if not table_exists:
        return

    columns = _get_table_columns(conn, "users")
    if "role" not in columns:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'employee'"))
        except Exception as e:
            print(f"Role migration note: {e}")

    for column, ddl in (
        ("invited_by", "TEXT"),
        ("invited_at", "DATETIME"),
        ("invite_accepted_at", "DATETIME"),
    ):
        if column not in columns:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN {column} {ddl}"))


def _migrate_checklist_items_table(conn):
    table_exists = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='checklist_items'")
    ).fetchone()
    if not table_exists:
        return

    columns = _get_table_columns(conn, "checklist_items")
    if "completion_evidence" not in columns:
        try:
            conn.execute(text("ALTER TABLE checklist_items ADD COLUMN completion_evidence TEXT"))
        except Exception as e:
            print(f"completion_evidence migration note: {e}")

    if "completion_source" not in columns:
        try:
            conn.execute(text("ALTER TABLE checklist_items ADD COLUMN completion_source TEXT"))
        except Exception as e:
            print(f"completion_source migration note: {e}")


def _remove_retired_integrations(conn):
    """Slack and Jira integrations were removed; drop their stored connection rows."""
    table_exists = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='user_integrations'")
    ).first()
    if table_exists:
        conn.execute(text("DELETE FROM user_integrations WHERE integration IN ('slack', 'jira')"))


def init_db():
    with engine.begin() as conn:
        _migrate_onboarding_sessions_table(conn)
        _migrate_users_table(conn)
        _migrate_checklist_items_table(conn)
        _remove_retired_integrations(conn)

    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully.")


if __name__ == "__main__":
    init_db()
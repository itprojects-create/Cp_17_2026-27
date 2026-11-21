"""
One-off repair for sessions created before the checklist and chat-notice fixes.

1. Checklists: signup used to seed a 50-task template that the persona plan was then
   added on top of (~70 tasks). Each non-completed session is re-planned from its stored
   persona; only untouched tasks (not started, no evidence) outside that plan are removed.
2. Chat history: failed replies used to be saved as assistant messages. They are relabelled
   with the "notice" role so they are shown as notices and never replayed to the model.

Usage (from backend/):
    python scripts/cleanup_sessions.py            # dry run: report only
    python scripts/cleanup_sessions.py --apply    # back up the database, then fix
"""
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.nodes.composer import is_error_notice_text  # noqa: E402
from app.agent.nodes.session_loader import _persona_state  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import models  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.services.plan_generator import (  # noqa: E402
    UNTOUCHED_STATUSES,
    generate_onboarding_plan,
    persist_onboarding_plan,
)


def _plan_for(session):
    persona = _persona_state(session.persona_match or "")
    if persona:
        return generate_onboarding_plan(
            role=persona["role"],
            experience_level=persona["experience_level"],
            technology_stack=persona["technology_stack"],
            session_id=session.session_id,
        )
    return generate_onboarding_plan(role="general", experience_level="junior", session_id=session.session_id)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write changes (default is a dry run)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        sessions = db.query(models.OnboardingSessionDB).all()
        replans = []
        for session in sessions:
            if session.status == "Completed":
                continue
            items = db.query(models.ChecklistItemDB).filter(
                models.ChecklistItemDB.session_id == session.session_id
            ).all()
            plan = _plan_for(session)
            plan_ids = {f"{session.session_id}::{t.task_id}" for t in plan.tasks}
            existing_ids = {i.id if "::" in i.id else f"{session.session_id}::{i.id}" for i in items}
            removable = [
                i for i in items
                if i.status in UNTOUCHED_STATUSES and not i.completion_evidence
                and (i.id if "::" in i.id else f"{session.session_id}::{i.id}") not in plan_ids
            ]
            missing = plan_ids - existing_ids
            if removable or missing:
                kept = len(items) - len(removable)
                replans.append((session, plan, len(items), kept + len(missing), len(removable), len(missing)))

        notices = [
            m for m in db.query(models.ChatMessageDB).filter(models.ChatMessageDB.role == "assistant").all()
            if is_error_notice_text(m.content)
        ]

        print(f"Database: {settings.SQLITE_DB_PATH}")
        print(f"\nChecklists to re-plan: {len(replans)} session(s)")
        for session, plan, before, after, removed, added in replans:
            print(f"  {session.session_id:28} {before:3} -> {after:3} tasks "
                  f"(remove {removed} untouched, add {added})  persona={session.persona_match}")
        print(f"\nError notices to relabel: {len(notices)} message(s)")

        if not args.apply:
            print("\nDry run only. Re-run with --apply to make these changes.")
            return 0
        if not replans and not notices:
            print("\nNothing to do.")
            return 0

        backup = Path(settings.SQLITE_DB_PATH).with_name(
            f"{Path(settings.SQLITE_DB_PATH).name}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        shutil.copy2(settings.SQLITE_DB_PATH, backup)
        print(f"\nBackup written to {backup}")

        for session, plan, *_ in replans:
            persist_onboarding_plan(db, session.session_id, plan)
        for message in notices:
            message.role = "notice"
        db.commit()
        print(f"Applied: re-planned {len(replans)} session(s), relabelled {len(notices)} notice(s).")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

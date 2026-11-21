from typing import Iterable, Any


TERMINAL_SESSION_STATUSES = {"Completed", "Cancelled", "Archived"}
COMPLETED_STATUSES = {"Completed", "Verified Complete"}
VERIFICATION_STATUSES = {"Pending Verification", "Self-Reported Complete"}


def calculate_progress(items: Iterable[Any]) -> dict[str, int | float]:
    items = list(items)
    total = len(items)

    def is_verified(item: Any) -> bool:
        return (
            item.status in COMPLETED_STATUSES
            and bool(getattr(item, "completion_evidence", None))
            and bool(getattr(item, "completion_source", None))
            and bool(getattr(item, "completed_at", None))
        )

    completed = sum(1 for item in items if is_verified(item))
    pending = sum(
        1 for item in items
        if item.status in {"Not Started", "Pending", "In Progress"}
    )
    skipped = sum(1 for item in items if item.status == "Skipped")
    blocked = sum(1 for item in items if item.status == "Blocked")
    pending_verification = sum(1 for item in items if item.status in VERIFICATION_STATUSES)
    percentage = round((completed / total) * 100, 2) if total else 0
    return {
        "total": total,
        "completed": completed,
        "pending": pending,
        "skipped": skipped,
        "blocked": blocked,
        "pending_verification": pending_verification,
        "percentage": percentage,
    }


def is_session_complete(items: Iterable[Any]) -> bool:
    summary = calculate_progress(items)
    return bool(summary["total"]) and (
        summary["completed"] + summary["skipped"] == summary["total"]
        and summary["blocked"] == 0
        and summary["pending_verification"] == 0
    )

import pytest
from app.routes.sessions import infer_checklist_status_from_message, extract_checklist_item_ids, normalize_checklist_id

def test_infer_checklist_status_from_message():
    assert infer_checklist_status_from_message("I have completed the task") == "Completed"
    assert infer_checklist_status_from_message("I am working on it") == "In Progress"
    assert infer_checklist_status_from_message("I am stuck on this") == "Blocked"
    assert infer_checklist_status_from_message("I will skip this") == "Skipped"
    assert infer_checklist_status_from_message("What is the next task?") is None

def test_extract_checklist_item_ids():
    assert extract_checklist_item_ids("I finished DEV-123 and HR-45") == ["DEV-123", "HR-45"]
    assert extract_checklist_item_ids("Working on it") == []
    assert extract_checklist_item_ids("Task T-1 is blocked") == ["T-1"]

def test_normalize_checklist_id():
    assert normalize_checklist_id("session123::DEV-123") == "DEV-123"
    assert normalize_checklist_id("DEV-123") == "DEV-123"

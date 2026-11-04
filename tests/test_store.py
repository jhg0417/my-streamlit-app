"""Local business-logic tests; no API calls or secrets needed."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from storage.store import Store, add_task, delete_task, empty_data, fingerprint, import_merge, undo_last, update_task


def test_zero_start_confirm_and_consistent_data(tmp_path):
    store = Store(path=tmp_path / "tasks.json")
    assert store.load()["tasks"] == []
    # A model proposal is not a persisted change.
    pending = {"type": "add_task", "task": {"name": "발표 자료", "deadline": "2026-11-20"}}
    assert store.load()["tasks"] == []
    created = store.update(lambda data: add_task(data, pending["task"]["name"], pending["task"]["deadline"], "높음", source="AI 비서"))
    assert created["id"] == 1
    assert store.load()["tasks"][0]["name"] == "발표 자료"
    assert store.load()["tasks"][0]["deadline"] == "2026-11-20"
    store.update(lambda data: update_task(data, 1, status="완료", source="AI 비서"))
    assert store.load()["tasks"][0]["status"] == "완료"
    store.update(undo_last)
    assert store.load()["tasks"][0]["status"] == "미착수"


def test_duplicate_does_not_write(tmp_path):
    store = Store(path=tmp_path / "tasks.json")
    store.update(lambda data: add_task(data, "보고서 작성", "", "보통"))
    with pytest.raises(ValueError):
        store.update(lambda data: add_task(data, "보고서작성", "", "보통"))
    assert len(store.load()["tasks"]) == 1


def test_import_is_explicit_additive_and_preserves_ids(tmp_path):
    store = Store(path=tmp_path / "tasks.json")
    store.update(lambda data: add_task(data, "내 새 업무", "2026-11-08"))
    historical = {"next_id": 4, "meeting_no": 2, "tasks": [
        {"id": 1, "name": "과거 업무", "deadline": "2026-11-13", "priority": "높음", "status": "미착수", "meeting_no": 1},
        {"id": 2, "name": "내 새 업무", "deadline": "2026-11-08", "priority": "보통", "status": "완료", "meeting_no": 1}],
        "meeting_hashes": ["old-meeting"], "uploaded_file_hashes": []}
    count = store.update(lambda data: import_merge(data, historical))
    assert count == 1
    assert len(store.load()["tasks"]) == 2
    assert len({t["id"] for t in store.load()["tasks"]}) == 2
    assert store.load()["tasks"][0]["status"] == "미착수"


def test_undo_deleted_task(tmp_path):
    store = Store(path=tmp_path / "tasks.json")
    store.update(lambda data: add_task(data, "발표", "2026-11-20"))
    store.update(lambda data: delete_task(data, 1))
    assert store.load()["tasks"] == []
    store.update(undo_last)
    assert store.load()["tasks"][0]["name"] == "발표"


def test_original_shape_and_empty_keys():
    fields = empty_data()
    assert all(k in fields for k in ["next_id", "meeting_no", "tasks", "meeting_hashes", "uploaded_file_hashes"])
    assert fingerprint("hello") == fingerprint(" hello  ")

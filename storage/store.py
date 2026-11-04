"""Compatible, single-user task repository. Local JSON or optional Supabase REST.

Do not place real task data in a public GitHub repository.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Callable

import requests

LOCK = RLock()
PRIORITIES = ("높음", "보통", "낮음", "미정")
STATUSES = ("미착수", "진행중", "완료")
ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "aivle_tasks.json"


def empty_data() -> dict:
    return {"next_id": 1, "meeting_no": 0, "tasks": [],
            "meeting_hashes": [], "uploaded_file_hashes": [], "events": []}


def normalize(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("업무 데이터는 JSON 객체여야 합니다.")
    out = copy.deepcopy(data)
    for key, default in empty_data().items():
        if not isinstance(out.get(key), type(default)):
            out[key] = copy.deepcopy(default)
    ids = set()
    for task in out["tasks"]:
        if not isinstance(task, dict):
            raise ValueError("업무 항목의 형식이 잘못되었습니다.")
        task["id"] = int(task["id"])
        if task["id"] in ids:
            raise ValueError("업무 ID가 중복되어 있습니다.")
        ids.add(task["id"])
        task["name"] = str(task.get("name", "")).strip()
        if not task["name"]:
            raise ValueError("업무 이름이 비어 있습니다.")
        task["deadline"] = str(task.get("deadline") or "")[:10]
        if task["deadline"]:
            validate_date(task["deadline"])
        if task.get("priority") not in PRIORITIES:
            task["priority"] = "미정"
        if task.get("status") not in STATUSES:
            task["status"] = "미착수"
        task.setdefault("meeting_no", 0)
    out["next_id"] = max(int(out.get("next_id", 1)), max(ids, default=0) + 1)
    out["meeting_no"] = int(out.get("meeting_no", 0))
    return out


def validate_date(value: str) -> str:
    if not value:
        return ""
    if len(value) != 10 or datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d") != value:
        raise ValueError("마감일은 YYYY-MM-DD 형식이어야 합니다.")
    return value


def norm_name(name: str) -> str:
    return "".join(str(name).split()).casefold()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


class Store:
    """A single app_state document; Supabase version uses optimistic compare-and-swap."""
    def __init__(self, url: str = "", service_key: str = "", path: Path | str = DATA_PATH):
        self.url = url.rstrip("/")
        self.key = service_key
        self.path = Path(path)
        self.remote = bool(self.url and self.key)

    @property
    def mode(self) -> str:
        return "Supabase (지속 저장)" if self.remote else "로컬 JSON (Cloud 재시작 시 유실 가능)"

    def _headers(self) -> dict:
        return {"apikey": self.key, "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json", "Prefer": "return=representation"}

    def _remote_read(self) -> tuple[dict, int | None]:
        r = requests.get(f"{self.url}/rest/v1/app_state",
                         params={"id": "eq.personal", "select": "data,version"},
                         headers=self._headers(), timeout=15)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return empty_data(), None
        return normalize(rows[0]["data"]), int(rows[0]["version"])

    def _local_read(self) -> dict:
        if not self.path.exists():
            return empty_data()
        return normalize(json.loads(self.path.read_text(encoding="utf-8")))

    def load(self) -> dict:
        with LOCK:
            return self._remote_read()[0] if self.remote else self._local_read()

    def _remote_write(self, data: dict, version: int | None):
        if version is None:
            r = requests.post(f"{self.url}/rest/v1/app_state", headers=self._headers(),
                              json={"id": "personal", "version": 1, "data": data}, timeout=15)
            if r.status_code == 409:
                raise RuntimeError("다른 세션이 먼저 데이터를 생성했습니다. 새로고침 후 다시 시도하세요.")
        else:
            r = requests.patch(f"{self.url}/rest/v1/app_state",
                               params={"id": "eq.personal", "version": f"eq.{version}"},
                               headers=self._headers(),
                               json={"version": version + 1, "data": data}, timeout=15)
        r.raise_for_status()
        if not r.json():
            raise RuntimeError("동시 수정 충돌이 발생했습니다. 새로고침 후 다시 시도하세요.")

    def _local_write(self, data: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        if self.path.exists():
            # Keep one recovery snapshot before every edit (never overwrite source ZIP).
            import shutil
            shutil.copy2(self.path, self.path.with_suffix(".json.bak"))
        try:
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
        finally:
            if tmp.exists():
                tmp.unlink()

    def update(self, fn: Callable[[dict], object]) -> object:
        """One mutation transaction; fn may change data and return action result."""
        with LOCK:
            if self.remote:
                data, version = self._remote_read()
            else:
                data, version = self._local_read(), None
            result = fn(data)
            data = normalize(data)
            if self.remote:
                self._remote_write(data, version)
            else:
                self._local_write(data)
            return result


def log(data: dict, event: str, before=None, after=None, detail="", source="UI") -> None:
    data.setdefault("events", []).append({
        "at": now_utc(), "event": event, "detail": str(detail), "source": source,
        "before": copy.deepcopy(before), "after": copy.deepcopy(after), "undone": False,
    })
    data["events"] = data["events"][-200:]


def add_task(data: dict, name: str, deadline="", priority="미정", description="", source="UI", **extra):
    name = str(name).strip()
    if not name:
        raise ValueError("업무명을 입력해 주세요.")
    if any(norm_name(x["name"]) == norm_name(name) for x in data["tasks"]):
        raise ValueError(f"이미 같은 업무명이 존재합니다: {name}")
    deadline = validate_date(str(deadline or ""))
    task = {"id": data["next_id"], "name": name, "deadline": deadline,
            "priority": priority if priority in PRIORITIES else "미정", "status": "미착수",
            "meeting_no": int(extra.get("meeting_no", 0)),
            "description": str(description), "source": source, "shared": False}
    if extra.get("evidence"):
        task["evidence"] = str(extra["evidence"])
    data["tasks"].append(task)
    data["next_id"] += 1
    log(data, "업무 추가", None, task, name, source)
    return copy.deepcopy(task)


def update_task(data: dict, task_id: int, source="UI", **changes):
    item = next((t for t in data["tasks"] if int(t["id"]) == int(task_id)), None)
    if item is None:
        raise ValueError("선택한 업무가 존재하지 않습니다.")
    allowed = {"name", "deadline", "priority", "status", "description", "shared"}
    before = copy.deepcopy(item)
    for field, value in changes.items():
        if field not in allowed or value is None:
            continue
        if field == "name":
            value = str(value).strip()
            if not value:
                raise ValueError("업무명은 비워둘 수 없습니다.")
            if any(x["id"] != item["id"] and norm_name(x["name"]) == norm_name(value)
                   for x in data["tasks"]):
                raise ValueError("같은 이름의 다른 업무가 이미 존재합니다.")
        elif field == "deadline":
            value = validate_date(str(value or ""))
        elif field == "status" and value not in STATUSES:
            raise ValueError("유효하지 않은 업무 상태입니다.")
        elif field == "priority" and value not in PRIORITIES:
            raise ValueError("유효하지 않은 우선순위입니다.")
        elif field == "shared":
            value = bool(value)
        else:
            value = str(value)
        item[field] = value
    if item != before:
        log(data, "업무 변경", before, item, item["name"], source)
    return copy.deepcopy(item)


def delete_task(data: dict, task_id: int):
    ix = next((i for i, t in enumerate(data["tasks"]) if t["id"] == task_id), None)
    if ix is None:
        raise ValueError("업무가 존재하지 않습니다.")
    task = data["tasks"].pop(ix)
    log(data, "업무 삭제", task, None, task["name"])
    return task


def undo_last(data: dict):
    events = data.get("events", [])
    for event in reversed(events):
        if event.get("undone") or event.get("event") not in ("업무 추가", "업무 변경", "업무 삭제"):
            continue
        before, after = event.get("before"), event.get("after")
        if after is not None:
            # Only undo if target still equals the saved AFTER state.
            target = next((t for t in data["tasks"] if t["id"] == after["id"]), None)
            if target != after:
                raise ValueError("이후 업무가 바뀌어 변경 취소가 불가능합니다.")
            data["tasks"].remove(target)
        if before is not None:
            if any(t["id"] == before["id"] for t in data["tasks"]):
                raise ValueError("되돌릴 ID가 이미 존재합니다.")
            data["tasks"].append(before)
        event["undone"] = True
        log(data, "변경 취소", after, before, event.get("detail", ""))
        return event["detail"]
    raise ValueError("취소할 업무 변경이 없습니다.")


def import_merge(data: dict, incoming: dict):
    """Safe additive import of original aivle_tasks.json; existing rows are never overwritten."""
    other = normalize(incoming)
    names = {norm_name(t["name"]) for t in data["tasks"]}
    count = 0
    for task in other["tasks"]:
        if norm_name(task["name"]) in names:
            continue
        new = copy.deepcopy(task)
        if any(x["id"] == new["id"] for x in data["tasks"]):
            new["id"] = data["next_id"]
        data["next_id"] = max(data["next_id"], new["id"] + 1)
        data["tasks"].append(new)
        names.add(norm_name(new["name"]))
        count += 1
    data["meeting_no"] = max(data["meeting_no"], other["meeting_no"])
    for key in ("meeting_hashes", "uploaded_file_hashes"):
        data[key] = list(dict.fromkeys(data[key] + other[key]))
    log(data, "JSON 가져오기", None, None, f"새 업무 {count}건 병합")
    return count

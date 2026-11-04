"""Calendar colors and task counts. No Streamlit dependency (easy to test)."""
from __future__ import annotations


def calendar_day_style(day: str, tasks: list[dict], today: str, *, selected: bool = False,
                       dark: bool = False) -> dict:
    """A blue border for today always wins; pending deadlines are red.

    Completed-only deadlines are green. Selection adds a ring without replacing
    the semantic border/background so a selected due day is still red.
    """
    matching = [t for t in tasks if t.get("deadline") == day]
    pending = any(t.get("status") != "완료" for t in matching)
    completed = bool(matching) and not pending
    is_today = day == today
    if dark:
        background = "#5a3038" if pending else ("#21453d" if completed else "#29333a")
        text = "#f4f8fa"
        border = "#72b7ff" if is_today else "#53646c"
        selected_ring = "0 0 0 2px #b7c5d0 inset" if selected else "none"
    else:
        background = "#ffdadd" if pending else ("#d8f2e3" if completed else "#ffffff")
        text = "#17323a"
        border = "#1974e9" if is_today else "#d7e4e5"
        selected_ring = "0 0 0 2px #6c67c7 inset" if selected else "none"
    return {"background": background, "text": text, "border": border,
            "ring": selected_ring, "count": len(matching), "today": is_today,
            "pending": pending, "completed": completed}

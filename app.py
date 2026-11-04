"""AIVLE AI Workspace | Streamlit entrypoint.

Single-user MVP. All task-changing AI operations require explicit confirmation.
Do not publish personal task records or credentials in your GitHub repository.
"""
from __future__ import annotations

import calendar
import copy
import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

from services.ai import (
    analyze_meeting, briefing, get_client, get_text, improve_prompt,
    plan_chat, stt, today, tts, web_search,
)
from services.documents import extract_text
from services.emailer import send_email
from storage.store import (
    PRIORITIES, STATUSES, Store, add_task, delete_task, fingerprint,
    import_merge, log, norm_name, undo_last, update_task, validate_date,
)

st.set_page_config(page_title="AIVLE AI Workspace", page_icon="💠", layout="wide", initial_sidebar_state="expanded")
KST = ZoneInfo("Asia/Seoul")
PAGES = ["대시보드", "스마트 캘린더", "업무 관리", "AI 비서", "문서 도구", "팀 협업", "활동 기록"]

st.markdown("""<style>
:root {color-scheme:light}
[data-testid="stAppViewContainer"] {background:#f5fbfb}
[data-testid="stHeader"] {background:rgba(245,251,251,.92)}
[data-testid="stSidebar"] {background:linear-gradient(180deg,#0b5460 0%, #0d6772 45%, #0f7d86 100%)}
[data-testid="stSidebar"] * {color:#efffff}
[data-testid="stSidebar"] [role="radiogroup"] label {padding:10px 10px;border-radius:10px;margin-bottom:4px}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {background:rgba(255,255,255,.11)}
.block-container {max-width:1450px;padding-top:1.35rem;padding-bottom:3rem}
h1,h2,h3 {color:#113a42;letter-spacing:-.035em}
p, label, div {font-size:0.98rem}
div[data-testid="stMetric"] {background:white;padding:15px 18px;border:1px solid #d8ecec;border-radius:16px;box-shadow:0 10px 24px rgba(11,84,96,.05)}
div[data-testid="stVerticalBlockBorderWrapper"] {border-radius:16px}
[data-testid="stChatMessage"] {background:white;border:1px solid #deeff0;border-radius:14px}
.stButton button[kind="primary"], .stFormSubmitButton button[kind="primary"] {background:#12a9ad;border-color:#12a9ad;color:white}
.stButton button[kind="secondary"], .stDownloadButton button {border-radius:10px}
.hero {padding:26px 30px;color:white;background:linear-gradient(115deg,#0d6d78,#12a9ad 58%,#54c9c3 100%);border-radius:20px;margin:4px 0 22px;box-shadow:0 16px 36px rgba(13,109,120,.15)}
.hero h2 {color:white;margin:4px 0 10px;font-size:1.65rem}
.hero p {color:#ecffff;margin:0}
.info-strip {padding:12px 16px;background:white;border:1px solid #dceff0;border-radius:12px;margin-bottom:14px;color:#43656b}
.soft-card {padding:14px 16px;background:#ffffff;border:1px solid #dceff0;border-radius:14px}
.muted-note {color:#658489;font-size:.9rem}
[data-testid="stSidebarNav"] {display:none}
</style>""", unsafe_allow_html=True)


def secret(name: str, default="") -> str:
    try:
        return str(st.secrets.get(name, default) or default)
    except (FileNotFoundError, KeyError, RuntimeError):
        return default


def navigate(page: str):
    st.session_state._go_page = page
    st.rerun()


def storage() -> Store:
    return Store(url=secret("SUPABASE_URL"), service_key=secret("SUPABASE_SERVICE_ROLE_KEY"))


def client():
    return get_client(secret("OPENAI_API_KEY"))


def mutate(action, success: str):
    try:
        result = storage().update(action)
        st.toast(success, icon="✅")
        return result
    except Exception as exc:
        st.error(f"저장 실패: {exc}")
        return None


def show_error(exc: Exception):
    st.error(f"요청 실패: {exc}")


def valid_deadline(value) -> str:
    if isinstance(value, (datetime, date)):
        value = value.isoformat()[:10]
    return validate_date(str(value or ""))


def due_soon(task: dict) -> bool:
    try:
        days = (date.fromisoformat(task.get("deadline", "")) - date.fromisoformat(today())).days
        return task.get("status") != "완료" and 0 <= days <= 3
    except ValueError:
        return False


def task_metrics(tasks):
    total = len(tasks)
    completed = sum(t.get("status") == "완료" for t in tasks)
    return total, total - completed, completed, sum(due_soon(t) for t in tasks)


def metrics(tasks):
    totals = task_metrics(tasks)
    names = ["전체 업무", "진행 중/미착수", "완료 업무", "마감 임박 (3일)"]
    for col, title, amount in zip(st.columns(4), names, totals):
        col.metric(title, f"{amount}건")


def sorted_tasks(tasks, all_tasks=False):
    priority = {"높음": 0, "보통": 1, "낮음": 2, "미정": 3}
    return sorted(
        (t for t in tasks if all_tasks or t.get("status") != "완료"),
        key=lambda t: (priority.get(t.get("priority"), 3), t.get("deadline") or "9999-12-31", int(t["id"])),
    )


def task_title(t):
    due = t.get("deadline") or "기한 미정"
    return f"#{t['id']} · {t['name']} · {due} · {t.get('priority','미정')} · {t.get('status','미착수')}"


def show_task_rows(tasks, limit=None):
    items = sorted_tasks(tasks)
    if limit:
        items = items[:limit]
    if not items:
        st.info("진행 중인 업무가 없습니다. AI 비서에게 업무를 등록해 달라고 말해 보세요.")
    for item in items:
        c1, c2 = st.columns([6, 1])
        with c1:
            st.markdown(f"**{item['name']}**  ·  `{item.get('priority', '미정')}`  ·  마감 {item.get('deadline') or '미정'}")
        with c2:
            if st.button("열기", key=f"open_{item['id']}_{limit}"):
                st.session_state.selected_task = item["id"]
                navigate("업무 관리")


def dashboard(data):
    st.markdown(f'<div class="hero"><small>YOUR AI WORK PARTNER</small><h2>AIVLE과 함께 업무를 관리하세요.</h2><p>오늘은 {today()}입니다. 새로운 업무는 AI 제안 확인 후 등록됩니다.</p></div>', unsafe_allow_html=True)
    metrics(data["tasks"])
    left, right = st.columns([2, 1], gap="large")
    with left:
        st.subheader("오늘의 AI 업무 브리핑")
        if st.button("✨ 현재 업무로 브리핑 생성", use_container_width=True, type="primary"):
            try:
                st.session_state.briefing = briefing(client(), data["tasks"])
            except Exception as exc:
                show_error(exc)
        if st.session_state.get("briefing"):
            st.info(st.session_state.briefing)
            if st.button("🔊 브리핑 듣기"):
                try:
                    st.audio(tts(client(), st.session_state.briefing), format="audio/mp3")
                except Exception as exc:
                    show_error(exc)
        st.subheader("진행 중인 주요 업무")
        show_task_rows(data["tasks"], limit=5)
        if st.button("+ AI에게 업무 등록 요청"):
            navigate("AI 비서")
    with right:
        st.subheader("오늘 마감되는 업무")
        items = [t for t in data["tasks"] if t.get("deadline") == today() and t.get("status") != "완료"]
        if items:
            for t in items:
                st.write("📍", task_title(t))
        else:
            st.caption("오늘 마감되는 미완료 업무가 없습니다.")
        st.subheader("마감 임박")
        soon = [t for t in sorted_tasks(data["tasks"]) if due_soon(t)]
        if soon:
            for t in soon:
                st.warning(f"{t['name']} · {t['deadline']}")
        else:
            st.caption("3일 안에 마감되는 업무가 없습니다.")
        st.caption("모든 통계는 업무 관리·캘린더와 같은 저장소를 참조합니다.")


def calendar_page(data):
    st.title("스마트 캘린더")
    st.caption("파란 테두리: 오늘 / 빨강: 미완료 마감 / 초록: 완료 업무 / 보라: 선택한 날짜")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("◀ 이전 달"):
            y, m = st.session_state.cal_year, st.session_state.cal_month
            st.session_state.cal_year, st.session_state.cal_month = (y - 1, 12) if m == 1 else (y, m - 1)
            st.rerun()
    with c2:
        st.markdown(f"### {st.session_state.cal_year}년 {st.session_state.cal_month}월")
    with c3:
        if st.button("다음 달 ▶"):
            y, m = st.session_state.cal_year, st.session_state.cal_month
            st.session_state.cal_year, st.session_state.cal_month = (y + 1, 1) if m == 12 else (y, m + 1)
            st.rerun()
    by_day = {}
    for t in data["tasks"]:
        key = t.get("deadline")
        if key:
            by_day.setdefault(key, []).append(t)
    rules = []
    days = calendar.Calendar(firstweekday=6).monthdayscalendar(st.session_state.cal_year, st.session_state.cal_month)
    st.markdown("<div class='info-strip'>월별 업무 날짜를 누르면 하단에서 해당 업무를 확인하고 바로 수정할 수 있습니다.</div>", unsafe_allow_html=True)
    cols = st.columns(7)
    for col, wd in zip(cols, ["일", "월", "화", "수", "목", "금", "토"]):
        col.markdown(f"**{wd}**")
    for week in days:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if not day:
                cols[i].write(" ")
                continue
            key_date = date(st.session_state.cal_year, st.session_state.cal_month, day).isoformat()
            bucket = by_day.get(key_date, [])
            waiting = any(t.get("status") != "완료" for t in bucket)
            done = any(t.get("status") == "완료" for t in bucket)
            css_key = f"cal_{key_date.replace('-', '_')}"
            bg = "#ffe1e4" if waiting else ("#dff8eb" if done else "#ffffff")
            outline = "#4e78e8" if key_date == today() else "#e2e7f2"
            if key_date == st.session_state.cal_selected:
                bg, outline = "#eeeaff", "#6559ef"
            rules.append(f'.st-key-{css_key} button {{background:{bg};border:2px solid {outline};min-height:64px;width:100%;font-weight:650}}')
            label = f"{day}  · {len(bucket)}건" if bucket else str(day)
            with cols[i]:
                if st.button(label, key=css_key, use_container_width=True):
                    st.session_state.cal_selected = key_date
                    st.rerun()
    st.markdown("<style>" + "\n".join(rules) + "</style>", unsafe_allow_html=True)
    chosen = st.session_state.cal_selected
    st.subheader(f"📅 {chosen} 업무")
    entries = by_day.get(chosen, [])
    if not entries:
        st.info("이 날짜에 등록된 업무가 없습니다.")
    else:
        for t in entries:
            col1, col2 = st.columns([7, 1])
            col1.write(task_title(t))
            if col2.button("수정", key=f"caledit_{t['id']}"):
                st.session_state.selected_task = t["id"]
                navigate("업무 관리")
    with st.expander("+ 선택한 날짜에 업무 등록", expanded=not entries):
        with st.form("calendar_add", clear_on_submit=True):
            name = st.text_input("업무명")
            priority = st.selectbox("우선순위", PRIORITIES, index=1)
            description = st.text_area("업무 설명", height=70)
            if st.form_submit_button("등록 확정", type="primary"):
                if mutate(lambda d: add_task(d, name, chosen, priority, description, source="캘린더"), "업무가 캘린더와 전체 업무에 등록됐습니다.") is not None:
                    st.rerun()


def task_page(data):
    st.title("업무 관리")
    metrics(data["tasks"])
    with st.expander("➕ 직접 업무 추가"):
        with st.form("add_form", clear_on_submit=True):
            name = st.text_input("업무명", key="add_name")
            due = st.date_input("마감일 (선택)", value=None, key="add_deadline")
            priority = st.selectbox("우선순위", PRIORITIES, index=1)
            description = st.text_area("설명 (선택)")
            if st.form_submit_button("업무 등록", type="primary"):
                if mutate(lambda d: add_task(d, name, valid_deadline(due), priority, description), "업무가 등록됐습니다.") is not None:
                    st.rerun()
    a, b, c = st.columns([2, 1, 1])
    query = a.text_input("업무명 검색", placeholder="예: 발표 자료")
    status_filter = b.selectbox("진행 상태", ["전체", "미완료", "미착수", "진행중", "완료"])
    order = c.selectbox("정렬", ["우선순위", "마감일", "최신 등록"])
    filtered = [t for t in data["tasks"] if query.lower() in t["name"].lower()]
    if status_filter == "미완료":
        filtered = [t for t in filtered if t.get("status") != "완료"]
    elif status_filter != "전체":
        filtered = [t for t in filtered if t.get("status") == status_filter]
    if order == "최신 등록":
        filtered = sorted(filtered, key=lambda t: t["id"], reverse=True)
    elif order == "마감일":
        filtered = sorted(filtered, key=lambda t: t.get("deadline") or "9999-12-31")
    else:
        porder = {k: i for i, k in enumerate(PRIORITIES)}
        filtered = sorted(filtered, key=lambda t: (porder.get(t.get("priority"), 3), t.get("deadline") or "9999-12-31"))
    if not filtered:
        st.info("표시할 업무가 없습니다. 신규 업무를 등록하거나 AI 비서에서 요청해 보세요.")
    for t in filtered:
        expanded = st.session_state.get("selected_task") == t["id"]
        with st.expander(task_title(t), expanded=expanded):
            st.caption(f"등록 경로: {t.get('source','1일차 노트북')} | 회의 번호: {t.get('meeting_no', 0)}")
            if t.get("evidence"):
                st.caption(f"회의 원문 근거: {t['evidence']}")
            quick_done = st.checkbox("✅ 완료", value=t.get("status") == "완료", key=f"done_{t['id']}_{t.get('status')}")
            if quick_done != (t.get("status") == "완료"):
                new_status = "완료" if quick_done else "미착수"
                if mutate(lambda d: update_task(d, t["id"], status=new_status), "업무 상태를 갱신했습니다.") is not None:
                    st.rerun()
            with st.form(f"edit_{t['id']}"):
                new_name = st.text_input("업무명", value=t["name"])
                date_val = None
                try:
                    date_val = date.fromisoformat(t.get("deadline", ""))
                except ValueError:
                    pass
                new_due = st.date_input("마감일", value=date_val)
                p = st.selectbox("우선순위", PRIORITIES, index=list(PRIORITIES).index(t.get("priority", "미정")))
                s = st.selectbox("진행 상태", STATUSES, index=list(STATUSES).index(t.get("status", "미착수")))
                desc = st.text_area("설명", value=t.get("description", ""))
                if st.form_submit_button("변경 저장", type="primary"):
                    changes = dict(name=new_name, deadline=valid_deadline(new_due), priority=p, status=s, description=desc)
                    if mutate(lambda d: update_task(d, t["id"], **changes), "업무가 변경됐습니다.") is not None:
                        st.rerun()
            if st.checkbox("삭제를 확인합니다", key=f"delok_{t['id']}"):
                if st.button("🗑️ 이 업무 삭제", key=f"del_{t['id']}"):
                    if mutate(lambda d: delete_task(d, t["id"]), "업무 삭제 완료") is not None:
                        st.rerun()
    with st.expander("이전 1일차 JSON 데이터 가져오기 (선택)"):
        st.warning("시연은 0건에서 시작합니다. 기존 테스트 8건은 자동으로 가져오지 않습니다.")
        uploaded = st.file_uploader("aivle_tasks.json 선택", type="json", key="importjson")
        if uploaded and st.button("중복 업무 제외하고 가져오기"):
            try:
                other = json.loads(uploaded.getvalue().decode("utf-8-sig"))
                count = storage().update(lambda d: import_merge(d, other))
                st.success(f"신규 업무 {count}건을 가져왔습니다.")
                st.rerun()
            except Exception as exc:
                show_error(exc)


def approved_action(pending):
    typ = pending.get("type")
    if typ == "add_task":
        t = pending.get("task") or {}
        return storage().update(lambda d: add_task(d, t.get("name", ""), t.get("deadline") or "", t.get("priority") or "미정", t.get("description") or "", source="AI 비서"))
    if typ in ("complete_task", "update_task"):
        tid = int(pending["task_id"])
        changes = pending.get("changes") or {}
        if typ == "complete_task":
            changes = {"status": "완료"}
        return storage().update(lambda d: update_task(d, tid, source="AI 비서", **changes))
    raise ValueError("지원하지 않는 승인 작업입니다.")


def chat_handle(message: str, data):
    message = message.strip()
    if not message:
        return
    st.session_state.messages.append({"role": "user", "content": message})
    st.session_state.last_voice = None
    try:
        external = []
        if st.session_state.get("search_on") and secret("TAVILY_API_KEY"):
            external = web_search(secret("TAVILY_API_KEY"), message)
        response = plan_chat(client(), message, data["tasks"], st.session_state.messages[:-1], external)
        answer = response.get("answer") or "요청을 확인했습니다."
        intent = response.get("intent", "general")
        st.session_state.pending = None
        for old_key in ("pendingname", "pendingdeadline", "pendingpriority"):
            st.session_state.pop(old_key, None)
        if intent == "add_task":
            task = response.get("task") or {}
            if not str(task.get("name") or "").strip():
                answer += "\n업무명이 불명확하여 등록 제안을 만들지 못했습니다."
            elif any(norm_name(t["name"]) == norm_name(task["name"]) for t in data["tasks"]):
                answer += "\n동일한 이름의 업무가 이미 있습니다. 기존 업무를 확인해 주세요."
            else:
                try:
                    validate_date(str(task.get("deadline") or ""))
                    st.session_state.pending = {"type": "add_task", "task": task}
                    answer += "\n\n아직 저장하지 않았습니다. 아래 '등록 승인'을 눌러주세요."
                except ValueError:
                    answer += "\n마감일을 확인하지 못해 저장을 보류했습니다. YYYY-MM-DD로 다시 알려주세요."
        elif intent in ("update_task", "complete_task"):
            target = next((t for t in data["tasks"] if str(t["id"]) == str(response.get("task_id"))), None)
            if target is None:
                answer += "\n대상 업무를 정확히 찾지 못해 변경하지 않았습니다."
            else:
                changes = {k: v for k, v in (response.get("changes") or {}).items() if k in ("name", "deadline", "priority", "status") and v is not None}
                if intent == "complete_task":
                    changes = {"status": "완료"}
                st.session_state.pending = {"type": intent, "task_id": target["id"], "changes": changes, "name": target["name"]}
                answer += "\n\n아직 변경하지 않았습니다. 아래 '변경 승인'을 눌러주세요."
        elif intent == "draft_email":
            proposed = response.get("email") or {}
            st.session_state.email_draft = {k: str(proposed.get(k) or "") for k in ("to", "subject", "body")}
            answer += "\n\n이메일 초안만 작성했습니다. 발송하려면 이메일 탭에서 주소와 내용을 확인하고 직접 승인해야 합니다."
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.session_state.messages = st.session_state.messages[-20:]
        if st.session_state.get("auto_tts"):
            try:
                st.session_state.last_voice = tts(client(), answer)
            except Exception as exc:
                st.session_state.last_voice = None
                st.toast(f"음성 생성 실패: {exc}", icon="⚠️")
    except Exception as exc:
        st.session_state.messages.append({"role": "assistant", "content": f"요청을 처리하지 못했습니다: {exc}"})
        st.session_state.pending = None
    st.rerun()


def assistant_page(data):
    st.title("AIVLE AI 비서")
    st.caption("실제 OpenAI API 연결 · 승인 기반 업무 변경 · STT/TTS · 프롬프트 개선")
    st.info("중요 작업은 AI가 바로 저장하지 않고, 사용자 승인 후 반영됩니다.")
    tab_chat, tab_prompt, tab_email = st.tabs(["💬 AI 대화 / 음성", "✨ 프롬프트 개선", "✉️ 이메일 발송"])
    with tab_chat:
        left, right = st.columns([3, 1], gap="large")
        with right:
            if secret("TAVILY_API_KEY"):
                st.toggle("실시간 웹 검색", key="search_on", help="Tavily API를 통해 출처를 조회합니다.")
            else:
                st.toggle("실시간 웹 검색 (API 미연결)", value=False, disabled=True)
            st.toggle("응답 자동 음성 재생", key="auto_tts")
            if st.button("새 대화 시작"):
                st.session_state.messages = []
                st.session_state.pending = None
                st.session_state.last_voice = None
                st.rerun()
            st.caption(f"현재 세션 대화: {len(st.session_state.messages)}개 메시지 (최대 20개)")
            st.caption("대화 기억은 현재 접속 세션 기준입니다. 업무 정보는 별도 저장소에 저장됩니다.")
        with left:
            for m in st.session_state.messages:
                with st.chat_message(m["role"]):
                    st.markdown(m["content"])
            pending = st.session_state.get("pending")
            if pending:
                st.markdown("### 📋 AI 변경 제안 (승인 전)")
                if pending["type"] == "add_task":
                    t = pending["task"]
                    st.write(f"**등록할 업무:** {t.get('name')}  ")
                    st.write(f"마감일: {t.get('deadline') or '미정'} · 우선순위: {t.get('priority') or '미정'}")
                    with st.expander("제안 내용 수정"):
                        t["name"] = st.text_input("업무명", value=t.get("name") or "", key="pendingname")
                        t["deadline"] = st.text_input("마감일(YYYY-MM-DD 또는 공란)", value=t.get("deadline") or "", key="pendingdeadline")
                        t["priority"] = st.selectbox("우선순위", PRIORITIES, index=list(PRIORITIES).index(t.get("priority") if t.get("priority") in PRIORITIES else "미정"), key="pendingpriority")
                else:
                    st.write(f"업무: **{pending['name']}**")
                    st.json(pending.get("changes", {}), expanded=False)
                yes, no = st.columns(2)
                with yes:
                    if st.button("✅ 등록 승인" if pending["type"] == "add_task" else "✅ 변경 승인", type="primary", use_container_width=True):
                        try:
                            approved_action(pending)
                            st.session_state.pending = None
                            st.session_state.pop("briefing", None)
                            st.session_state.messages.append({"role": "assistant", "content": "✅ 사용자 승인에 따라 업무 변경을 저장했습니다. 대시보드·업무 관리·캘린더에 반영됐습니다."})
                            st.rerun()
                        except Exception as exc:
                            show_error(exc)
                with no:
                    if st.button("취소", use_container_width=True):
                        st.session_state.pending = None
                        st.rerun()
            if st.session_state.get("last_voice"):
                st.audio(st.session_state.last_voice, format="audio/mp3", autoplay=bool(st.session_state.get("auto_tts")))
            elif st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
                if st.button("🔊 마지막 답변 듣기"):
                    try:
                        st.session_state.last_voice = tts(client(), st.session_state.messages[-1]["content"])
                        st.rerun()
                    except Exception as exc:
                        show_error(exc)
            st.markdown("**🎙️ 음성으로 요청하기**")
            recorded = st.audio_input("녹음 후 아래 변환 버튼을 눌러주세요", key="chat_recorded")
            if recorded and st.button("STT 변환"):
                try:
                    st.session_state.voice_transcript = stt(client(), recorded.getvalue(), "voice.wav")
                    st.rerun()
                except Exception as exc:
                    show_error(exc)
            if st.session_state.get("voice_transcript"):
                st.info(f"음성 인식 결과: {st.session_state.voice_transcript}")
                if st.button("이 음성 명령을 AI에게 보내기", type="primary"):
                    msg = st.session_state.voice_transcript
                    st.session_state.voice_transcript = ""
                    chat_handle(msg, data)
            message = st.chat_input("AIVLE, 11월 20일까지 발표 자료를 등록해 줘")
            if message:
                chat_handle(message, data)
    with tab_prompt:
        st.markdown("#### 팀 기능: 스마트 프롬프트 개선")
        st.caption("제공된 HTML의 규칙 기반 개선기 아이디어를 LLM API 기반으로 연결했습니다. 문장은 직접 수정한 뒤 전송합니다.")
        prompt = st.text_area("개선할 원래 요청", placeholder="다음 주 회의 준비해 줘", key="prompt_input", height=110)
        if st.button("✨ 프롬프트 개선하기", type="primary"):
            try:
                st.session_state.prompt_result = improve_prompt(client(), prompt)
            except Exception as exc:
                show_error(exc)
        revised = st.text_area("개선된 프롬프트 (수정 가능)", value=st.session_state.get("prompt_result", ""), height=240)
        if st.button("이 프롬프트를 AI 비서에게 적용"):
            chat_handle(revised, data)
    with tab_email:
        email_draft_ui()


def email_draft_ui():
    st.markdown("#### Gmail 이메일 초안 및 발송")
    st.info("이메일은 직접 승인 버튼을 누르기 전까지 절대 전송하지 않습니다.")
    with st.form("email_form"):
        existing = st.session_state.get("email_draft", {})
        to = st.text_input("수신자 이메일 주소", value=existing.get("to", ""))
        subject = st.text_input("제목", value=existing.get("subject", ""))
        body = st.text_area("본문", value=existing.get("body", ""), height=190)
        if st.form_submit_button("초안 미리보기 / 수정 저장"):
            st.session_state.email_draft = {"to": to, "subject": subject, "body": body}
            st.rerun()
    draft = st.session_state.get("email_draft", {})
    if any(draft.values()):
        st.markdown("**전송 전 미리보기**")
        st.write("받는 사람:", draft.get("to") or "미입력")
        st.write("제목:", draft.get("subject") or "미입력")
        st.code(draft.get("body") or "미입력", language="text")
        approval_key = "email_confirm_" + fingerprint(json.dumps(draft, ensure_ascii=False))[:12]
        confirmed = st.checkbox("수신자·제목·본문을 검토했고 실제 발송에 동의합니다.", key=approval_key)
        if st.button("📨 실제 이메일 발송 승인", type="primary", disabled=not confirmed):
            try:
                sent_to = send_email(draft.get("to", ""), draft.get("subject", ""), draft.get("body", ""), secret("GMAIL_ADDRESS"), secret("GMAIL_APP_PASSWORD"))
            except Exception as exc:
                st.error(f"이메일 발송 실패: {exc}")
            else:
                st.success(f"이메일 발송 성공: {sent_to}")
                st.session_state.email_draft = {}
                try:
                    storage().update(lambda d: log(d, "이메일 발송", None, None, f"수신자: {sent_to}", "이메일"))
                except Exception as exc:
                    st.warning(f"메일 발송은 성공했지만 활동 기록 저장에 실패했습니다: {exc}")
    else:
        st.caption("AI에게 '회의 내용을 메일 초안으로 만들어줘'라고 요청하거나 직접 작성해 주세요.")


def meeting_ui(data):
    st.subheader("회의록 분석 · 업무 추출")
    st.caption("회의 내용 요약과 업무 추출은 API로 실행합니다. 실제 업무 등록은 사용자 확인 후에만 이루어집니다.")
    file = st.file_uploader("회의록 TXT 또는 녹음 MP3/M4A/WAV", type=["txt", "md", "mp3", "m4a", "wav"], key="meetingfile")
    text_value = st.text_area("또는 회의 내용을 붙여 넣으세요", height=160, key="meetingpaste")
    if st.button("🎯 회의록 AI 분석", type="primary"):
        try:
            raw = file.getvalue() if file else b""
            source_file_hash = hashlib.sha256(raw).hexdigest() if raw else ""
            if file and Path(file.name).suffix.lower() in (".mp3", ".m4a", ".wav"):
                meeting_text = stt(client(), raw, file.name)
            elif file:
                meeting_text = raw.decode("utf-8-sig", errors="replace")
            else:
                meeting_text = text_value
            if not meeting_text.strip():
                raise ValueError("회의록 파일 또는 텍스트를 입력하세요.")
            file_hash = fingerprint(meeting_text)
            if file_hash in data.get("meeting_hashes", []) or (source_file_hash and source_file_hash in data.get("uploaded_file_hashes", [])):
                st.warning("이미 등록된 동일 회의록입니다. 중복 저장하지 않습니다.")
            result = analyze_meeting(client(), meeting_text, data["tasks"])
            st.session_state.meeting_result = result
            st.session_state.meeting_text = meeting_text
            st.session_state.meeting_hash = file_hash
            st.session_state.source_file_hash = source_file_hash
            st.session_state.meeting_nonce = st.session_state.get("meeting_nonce", 0) + 1
            st.rerun()
        except Exception as exc:
            show_error(exc)
    result = st.session_state.get("meeting_result")
    if not result:
        return
    st.markdown("**음성 인식/업로드 원문**")
    with st.expander("원문 확인"):
        st.text(st.session_state.get("meeting_text", ""))
    st.markdown("### 회의 요약")
    st.write(result.get("summary") or "요약 결과 없음")
    decisions = result.get("decisions") or []
    if decisions:
        st.markdown("**결정 사항**")
        for d in decisions:
            st.write("•", d)
    new_tasks = result.get("new_tasks") or []
    updates = result.get("updates") or []
    st.markdown("### 신규 등록할 업무를 선택하세요")
    for i, task in enumerate(new_tasks):
        st.checkbox(f"{task.get('name')} | {task.get('deadline') or '마감 미정'} | {task.get('priority') or '미정'}", value=True, key=f"meet_new_{st.session_state.meeting_nonce}_{i}")
        if task.get("evidence"):
            st.caption("원문 근거: " + str(task["evidence"]))
    st.markdown("### 기존 업무 변경 후보")
    for i, change in enumerate(updates):
        st.checkbox(f"업무 ID {change.get('id')}: { {k: v for k,v in change.items() if k != 'evidence'} }", value=False, key=f"meet_update_{st.session_state.meeting_nonce}_{i}")
        if change.get("evidence"):
            st.caption("원문 근거: " + str(change["evidence"]))
    if not new_tasks and not updates:
        st.info("회의록에서 확실하게 추출된 신규·변경 업무가 없습니다.")
    if st.button("✅ 선택한 업무 변경사항 저장", type="primary", disabled=not (new_tasks or updates)):
        try:
            hash_value = st.session_state.meeting_hash
            audio_hash = st.session_state.source_file_hash
            nonce = st.session_state.meeting_nonce
            def save_meeting(d):
                if hash_value in d["meeting_hashes"] or (audio_hash and audio_hash in d["uploaded_file_hashes"]):
                    raise ValueError("같은 회의록을 이미 저장했습니다.")
                d["meeting_no"] += 1
                num = d["meeting_no"]
                count = 0
                for i, t in enumerate(new_tasks):
                    if st.session_state.get(f"meet_new_{nonce}_{i}"):
                        add_task(d, t.get("name") or "", str(t.get("deadline") or ""), t.get("priority") or "미정", t.get("description") or "", source="회의록", meeting_no=num, evidence=t.get("evidence") or "")
                        count += 1
                for i, t in enumerate(updates):
                    if st.session_state.get(f"meet_update_{nonce}_{i}"):
                        changes = {k: t[k] for k in ("deadline", "priority", "status") if t.get(k)}
                        if changes:
                            update_task(d, int(t["id"]), source="회의록", **changes)
                            count += 1
                d["meeting_hashes"].append(hash_value)
                if audio_hash:
                    d["uploaded_file_hashes"].append(audio_hash)
                log(d, "회의록 분석 등록", None, None, f"회의 #{num}, 선택 {count}건", "회의록")
                return count
            count = storage().update(save_meeting)
            st.session_state.meeting_result = None
            st.success(f"회의록 확인 완료 · {count}개 업무 반영")
            st.rerun()
        except Exception as exc:
            show_error(exc)


def docs_page(data):
    st.title("문서 도구")
    ta, tb, tc, td = st.tabs(["📝 회의록 분석", "📄 문서 요약", "🌏 문서 번역", "🔍 회의록 비교"])
    with ta:
        meeting_ui(data)
    with tb:
        doc = st.file_uploader("요약할 문서", type=["txt", "pdf", "docx"], key="summarydoc")
        depth = st.radio("요약 유형", ["간단 요약", "상세 요약"], horizontal=True)
        if st.button("문서 요약 실행"):
            try:
                if not doc:
                    raise ValueError("문서를 먼저 업로드하세요.")
                extracted = extract_text(doc.name, doc.getvalue())
                st.session_state.doc_summary = get_text(client(), f"다음 문서를 {depth} 형식으로 한국어로 요약한다. 문서에 없는 정보는 만들지 않는다.", extracted)
            except Exception as exc:
                show_error(exc)
        if st.session_state.get("doc_summary"):
            st.write(st.session_state.doc_summary)
            st.download_button("요약 TXT 다운로드", st.session_state.doc_summary, file_name="summary.txt")
    with tc:
        doc = st.file_uploader("번역할 문서", type=["txt", "pdf", "docx"], key="translationdoc")
        lang = st.selectbox("번역 언어", ["영어", "한국어", "일본어", "중국어", "프랑스어", "독일어"])
        if st.button("문서 번역 실행"):
            try:
                if not doc:
                    raise ValueError("문서를 먼저 업로드하세요.")
                extracted = extract_text(doc.name, doc.getvalue())
                st.session_state.doc_translation = get_text(client(), f"입력 문서를 {lang}로 자연스럽게 번역하라. 불필요한 설명은 넣지 말고 원래 문단 구조를 가능한 유지해라.", extracted)
            except Exception as exc:
                show_error(exc)
        if st.session_state.get("doc_translation"):
            st.write(st.session_state.doc_translation)
            st.download_button("번역 TXT 다운로드", st.session_state.doc_translation, file_name="translation.txt")
            st.caption("PDF/DOCX 원본 레이아웃 보존은 지원하지 않습니다. 텍스트 번역 결과를 다운로드합니다.")
    with td:
        old = st.file_uploader("이전 회의록 TXT", type=["txt"], key="old_meeting")
        new = st.file_uploader("새 회의록 TXT", type=["txt"], key="new_meeting")
        if st.button("두 회의록 비교 분석"):
            try:
                if not old or not new:
                    raise ValueError("회의록 2개를 모두 업로드하세요.")
                old_txt = old.getvalue().decode("utf-8-sig", errors="replace")
                new_txt = new.getvalue().decode("utf-8-sig", errors="replace")
                prompt = "[이전 회의록]\n" + old_txt[:24000] + "\n[새 회의록]\n" + new_txt[:24000]
                st.session_state.compare_result = get_text(client(), "두 회의록을 비교해 신규 업무, 기한 변경, 완료 언급, 달라진 결정사항을 구분하라. 원문에 없는 변경을 추측하지 마라. 가능하면 근거 문장을 짧게 인용하라.", prompt)
            except Exception as exc:
                show_error(exc)
        if st.session_state.get("compare_result"):
            st.write(st.session_state.compare_result)
        st.caption("비교 결과는 보고서일 뿐입니다. 업무 DB는 별도 승인 없이 변경되지 않습니다.")


def collaboration_page(data):
    st.title("팀 협업")
    st.caption("현재는 데모가 아닌 단일 사용자 MVP를 우선 완성한 상태입니다.")
    st.info("현재 버전은 단일 사용자 MVP입니다. 다른 팀원 계정 로그인·공동 편집은 아직 연결하지 않았습니다.")
    st.write("공유된 개인 업무를 무단으로 노출하지 않도록 팀 기능을 비활성화했습니다.")
    st.markdown("**추후 확장:** Supabase Auth 사용자별 계정, Row Level Security 정책, 팀별 공유 권한, 변경 충돌 처리")
    st.caption("이 화면은 팀 공동 데이터가 실제로 공유되는 것처럼 보이게 만들지 않습니다.")


def activity_page(data):
    st.title("활동 기록")
    st.caption("최근 변경 이력과 취소 기록을 확인합니다.")
    c1, c2 = st.columns([1, 5])
    if c1.button("↶ 최근 변경 취소", use_container_width=True):
        if mutate(undo_last, "최근 업무 변경을 되돌렸습니다.") is not None:
            st.rerun()
    with c2:
        st.caption("업무 추가·변경·삭제를 되돌릴 수 있습니다. 이후 같은 업무를 수정했다면 안전을 위해 취소하지 않습니다.")
    events = list(reversed(data.get("events", [])[-100:]))
    if not events:
        st.info("기록된 업무 변경 내역이 없습니다.")
    for event in events:
        st.write(f"**{event.get('event','변경')}** — {event.get('detail','')}  ")
        st.caption(f"{event.get('at','')} · 출처: {event.get('source','UI')}" + (" · 취소됨" if event.get("undone") else ""))
    st.caption("대화 기록은 세션에만 보관하므로 재접속 시 지워집니다.")


def bootstrap():
    if "cal_year" not in st.session_state:
        st.session_state.cal_year = date.fromisoformat(today()).year
        st.session_state.cal_month = date.fromisoformat(today()).month
        st.session_state.cal_selected = today()
    defaults = {"messages": [], "pending": None, "last_voice": None, "auto_tts": False,
                "search_on": False, "voice_transcript": "", "email_draft": {},
                "prompt_result": "", "meeting_result": None, "meeting_nonce": 0}
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val
    if "_go_page" in st.session_state:
        st.session_state.page = st.session_state.pop("_go_page")
    st.session_state.setdefault("page", "대시보드")


def main():
    bootstrap()
    store = storage()
    configured_pin = secret("APP_PASSWORD")
    if configured_pin and not st.session_state.get("authenticated"):
        st.title("🔐 AIVLE 업무비서 로그인")
        with st.form("authform"):
            pin = st.text_input("접속 비밀번호", type="password")
            submitted = st.form_submit_button("로그인", type="primary")
        if submitted:
            import hmac
            if hmac.compare_digest(pin, configured_pin):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("비밀번호가 일치하지 않습니다.")
        st.stop()
    with st.sidebar:
        st.markdown("## 💠 AIVLE")
        st.caption("KT AIVLE SCHOOL · AI PERSONAL WORKSPACE")
        st.radio("메뉴", PAGES, key="page")
        st.divider()
        st.caption("업무·캘린더·AI 비서는 동일한 저장소를 함께 사용합니다.")
        with st.expander("환경 정보", expanded=False):
            st.write(f"저장 방식: {store.mode}")
            if store.remote:
                st.success("외부 DB 연결됨")
            else:
                st.caption("현재는 로컬 JSON 저장입니다. 재배포/재시작 시 데이터가 사라질 수 있습니다.")
            if not secret("OPENAI_API_KEY"):
                st.warning("OPENAI_API_KEY 미설정: AI 기능 비활성")
        if configured_pin and st.button("로그아웃"):
            st.session_state.authenticated = False
            st.rerun()
    try:
        data = store.load()
    except Exception as exc:
        st.error(f"저장소 읽기 실패: {exc}")
        st.stop()
    page = st.session_state.page
    if page == "대시보드": dashboard(data)
    elif page == "스마트 캘린더": calendar_page(data)
    elif page == "업무 관리": task_page(data)
    elif page == "AI 비서": assistant_page(data)
    elif page == "문서 도구": docs_page(data)
    elif page == "팀 협업": collaboration_page(data)
    elif page == "활동 기록": activity_page(data)


if __name__ == "__main__":
    main()

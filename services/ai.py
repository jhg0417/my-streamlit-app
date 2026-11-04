"""OpenAI adapters. No side effects: model returns proposals only."""
from __future__ import annotations

import io
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from openai import OpenAI

MODEL = "gpt-4o-mini"
AUDIO_MODEL = "whisper-1"
SPEECH_MODEL = "tts-1"
TODAY_ZONE = ZoneInfo("Asia/Seoul")


def today() -> str:
    return datetime.now(TODAY_ZONE).strftime("%Y-%m-%d")


def get_client(api_key: str) -> OpenAI:
    if not api_key:
        raise ValueError("Secrets의 OPENAI_API_KEY를 먼저 등록해 주세요.")
    return OpenAI(api_key=api_key, timeout=45.0, max_retries=1)


def get_json(client: OpenAI, system: str, user: str) -> dict:
    result = client.responses.create(
        model=MODEL,
        input=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        text={"format": {"type": "json_object"}},
    )
    return json.loads(result.output_text)


def get_text(client: OpenAI, instruction: str, text: str) -> str:
    result = client.responses.create(model=MODEL, input=[
        {"role": "system", "content": instruction},
        {"role": "user", "content": text[:60000]}
    ])
    return result.output_text


def stt(client: OpenAI, raw: bytes, filename="audio.wav") -> str:
    file_like = io.BytesIO(raw)
    file_like.name = filename
    result = client.audio.transcriptions.create(
        model=AUDIO_MODEL, file=file_like, language="ko")
    return result.text


def tts(client: OpenAI, answer: str) -> bytes:
    if not answer.strip():
        raise ValueError("음성으로 읽을 응답이 없습니다.")
    output = client.audio.speech.create(model=SPEECH_MODEL, voice="alloy", input=answer[:4000])
    return output.content


def improve_prompt(client: OpenAI, question: str) -> str:
    return get_text(client,
        "사용자의 원래 의도를 유지하면서 업무용 AI에게 전달할 프롬프트를 구체화하라. "
        "필수 정보가 없다면 가정하지 말고 확인 질문을 포함한다. 간결한 한국어로 작성하라.", question)


def plan_chat(client: OpenAI, message: str, tasks: list[dict], history: list[dict], web_sources=None):
    task_context = [
        {k: t.get(k) for k in ("id", "name", "deadline", "priority", "status", "description")}
        for t in tasks
    ]
    system = f"""당신은 KT AIVLE School의 AI 개인비서 '에이블'이고, 김 대리의 업무를 지원합니다.
현재 한국 날짜는 {today()}입니다.
실제 데이터에서 확인되지 않은 업무·날짜·담당자·이메일 주소는 만들어내지 마세요.
새 업무 추가/업무 완료/업무 변경을 사용자가 명시적으로 요청할 때만 명령을 제안합니다.
단순 질문이나 업무 목록 조회는 절대 변경하지 않습니다.
사용자가 업무명을 말했을 때 기존 목록의 특정 ID를 확실히 찾을 수 없다면 intent='general'로 하고 확인 질문을 하세요.
기존 업무 번호는 반드시 제공된 id를 사용합니다. 질문 속 '1번' 등은 제공된 ID와 다를 수 있으므로 신중히 판별하세요.
메일 발송 요청은 즉시 전송하지 않고 무조건 draft_email로만 제안합니다.
업무 삭제는 제안하지 말고 UI의 확인 절차를 안내하세요.
출력은 JSON 객체만 반환하며 다음 키를 포함해야 합니다:
{{"intent":"general|list_tasks|add_task|update_task|complete_task|draft_email",
"answer":"자연스러운 한국어 답변", "task_id":null,
"task":{{"name":"","deadline":"","priority":"미정","description":""}},
"changes":{{"name":null,"deadline":null,"priority":null,"status":null}},
"email":{{"to":"","subject":"","body":""}}}}
날짜는 YYYY-MM-DD로 반환하고 기한이 없으면 빈 문자열로 둡니다. '내일', '다음 주' 같은 표현은 명확하게 계산되는 경우에만 변환합니다.
이미 존재하는 업무는 새로 만들지 않습니다. 사용자의 명시적 변경만 실행합니다.
외부 웹 검색을 사용했다면 근거 URL을 답변에 표시하되 출처에 없는 내용은 만들지 마세요."""
    user = json.dumps({
        "existing_tasks": task_context,
        "recent_messages": history[-20:],
        "web_sources": web_sources or [],
        "user_message": message
    }, ensure_ascii=False)
    result = get_json(client, system, user)
    return result if isinstance(result, dict) else {"intent": "general", "answer": str(result)}


def analyze_meeting(client: OpenAI, meeting_text: str, current: list[dict]) -> dict:
    """Extends original register_meeting prompt; UI decides which changes to apply."""
    sys = f"""당신은 김 대리의 개인비서 '에이블'입니다. 오늘은 {today()}입니다.
회의록에서 김 대리에게 명확히 할당된 신규 업무 및 기존 업무 변경사항만 추출합니다.
회의록에 없는 이름, 날짜, 담당자, 상태를 절대 만들어내지 마세요.
기존 업무에 이름이 유사하더라도 정확한 일치가 불분명하면 새로 만들거나 갱신하지 마세요.
업무 완료 언급도 자동 완료하지 말고 후보 updates에 기록합니다.
각 신규 업무와 변경사항에 반드시 가능한 한 원문 근거 문장을 넣습니다.
날짜는 YYYY-MM-DD 형식. 없으면 빈 문자열, 우선순위 없으면 '미정'.
JSON 객체만 답변:
{{"summary":"회의 핵심 요약","decisions":["확정된 결정사항"],
"new_tasks":[{{"name":"","deadline":"","priority":"미정","description":"","evidence":"회의록 실제 문장"}}],
"updates":[{{"id":1,"deadline":"","priority":"","status":"","evidence":"회의록 실제 문장"}}]}}
업데이트의 id는 기존 업무에서 제공된 실제 id만 쓸 것. 변화가 없다면 배열을 비워둡니다."""
    tasks = [{k: t.get(k) for k in ("id", "name", "deadline", "priority", "status")}
             for t in current]
    return get_json(client, sys, json.dumps({
        "existing_tasks": tasks, "meeting_text": meeting_text[:55000]
    }, ensure_ascii=False))


def briefing(client: OpenAI, tasks: list[dict]) -> str:
    data = [{k: t.get(k) for k in ("name", "deadline", "priority", "status")}
            for t in tasks if t.get("status") != "완료"]
    return get_text(client,
        f"오늘은 한국 시간 {today()}이다. 업무 목록만 바탕으로 오늘 처리할 일, "
        "마감 임박 및 지연, 우선순위 높은 순서로 6문장 이내 간단히 브리핑하라. "
        "없는 일정은 만들지 마라.", json.dumps(data, ensure_ascii=False))


def web_search(tavily_key: str, query: str) -> list[dict]:
    if not tavily_key:
        return []
    r = requests.post("https://api.tavily.com/search", json={
        "api_key": tavily_key, "query": query[:300], "search_depth": "basic",
        "max_results": 4, "include_answer": False}, timeout=20)
    r.raise_for_status()
    return [{"title": v.get("title", ""), "url": v.get("url", ""),
             "content": v.get("content", "")[:1200]} for v in r.json().get("results", [])]

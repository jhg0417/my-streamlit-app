"""Unit-level regression checks for v5. No Streamlit server or live API required."""
import io
import json
import re
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace, ModuleType
from unittest.mock import MagicMock

import pytest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from services.calendar_rules import calendar_day_style
from services.emailer import send_email
# The sandbox has no OpenAI SDK; supply only its type name for isolated mocks.
try:
    from openai import OpenAI as _OpenAI
except ImportError:
    from types import ModuleType
    dummy_openai = ModuleType("openai")
    dummy_openai.OpenAI = object
    sys.modules["openai"] = dummy_openai
from services.ai import get_json, stt, tts
from storage.store import Store, add_task, update_task, empty_data


def test_today_blue_border_even_without_tasks():
    day="2026-11-04"
    v=calendar_day_style(day, [], day, selected=True)
    assert v['border'] == '#1974e9' and v['count']==0 and v['today']


def test_due_red_and_today_blue_simultaneously():
    day="2026-11-04"
    tasks=[{'deadline':day,'status':'진행중'}]
    v=calendar_day_style(day, tasks, day, selected=True)
    assert v['background']=='#ffdadd' and v['border']=='#1974e9'
    assert v['pending'] and v['count']==1


def test_completed_green_and_mixed_red():
    day="2026-11-20"
    done=[{'deadline':day,'status':'완료'}]
    assert calendar_day_style(day, done, '2026-11-04')['background']=='#d8f2e3'
    assert calendar_day_style(day, done+[{'deadline':day,'status':'미착수'}], '2026-11-04')['background']=='#ffdadd'


def test_dark_calendar_contrast_today_and_pending():
    day='2026-11-04'
    v=calendar_day_style(day,[{'deadline':day,'status':'미착수'}],day,dark=True,selected=True)
    assert v['background']=='#5a3038' and v['border']=='#72b7ff' and v['text']=='#f4f8fa'


def test_tasks_automatically_round_trip_local_storage(tmp_path):
    path=tmp_path/'data'/'aivle_tasks.json'
    source=Store(path=path)
    assert source.load()['tasks']==[]
    source.update(lambda d:add_task(d, '신규 발표 준비', '2026-11-20',priority='높음',source='AI 비서'))
    new_instance=Store(path=path)
    t=new_instance.load()['tasks'][0]
    assert (t['id'],t['name'],t['deadline'],t['status'])==(1,'신규 발표 준비','2026-11-20','미착수')
    new_instance.update(lambda d:update_task(d,1,status='완료',source='AI 비서'))
    assert source.load()['tasks'][0]['status']=='완료'
    assert len(source.load()['events'])==2


def test_no_legacy_seed_by_default():
    assert empty_data()['tasks'] == []
    assert 'aivle_tasks.json 선택' not in (BASE/'app.py').read_text(encoding='utf-8')
    assert 'import_merge(' not in (BASE/'app.py').read_text(encoding='utf-8')


def test_native_theme_has_full_light_and_dark_palette():
    config=tomllib.loads((BASE/'.streamlit/config.toml').read_text())
    light=config['theme']['light']; dark=config['theme']['dark']
    assert light['backgroundColor']=='#F4FBFA'
    assert dark['backgroundColor']=='#171D23'
    assert dark['sidebar']['backgroundColor']=='#2A333C'
    assert dark['secondaryBackgroundColor']!='#E6F2F1'
    assert dark['textColor']=='#EFF3F5'
    assert 'st.toggle("🌙 다크 모드"' not in (BASE/'app.py').read_text()


def test_streamlit_version_pinned_for_python314():
    req=(BASE/'requirements.txt').read_text()
    assert 'streamlit==1.66.0' in req


def test_missing_email_information_cannot_send(monkeypatch):
    def forbidden(*args,**kwargs):
        raise AssertionError('Email must not be sent without approval and required information')
    import services.emailer as mail
    monkeypatch.setattr(mail.smtplib, 'SMTP_SSL', forbidden)
    with pytest.raises(ValueError):
        send_email('bad', 'subject', 'body','me@gmail.com','password')
    with pytest.raises(ValueError):
        send_email('x@y.com','subject','body','','')


def test_email_once_with_explicit_call_and_mock_smtp(monkeypatch):
    out=[]
    class FakeSMTP:
        def __init__(self,*args,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def login(self,addr,password): out.append(('login',addr))
        def send_message(self,msg): out.append(('sent',msg['To'],msg['Subject']))
    import services.emailer as mail
    monkeypatch.setattr(mail.smtplib,'SMTP_SSL',FakeSMTP)
    assert send_email('x@y.com','결과','업무 완료','me@gmail.com','testkey')=='x@y.com'
    assert out==[('login','me@gmail.com'),('sent','x@y.com','결과')]


def test_tts_audio_bytes_with_mock_api():
    voice=SimpleNamespace(audio=SimpleNamespace(speech=SimpleNamespace(create=lambda **kw:SimpleNamespace(content=b'FAKE_MP3'))))
    assert tts(voice,'업무 완료')==b'FAKE_MP3'
    assert get_json(SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs:SimpleNamespace(output_text='{"intent":"general"}'))),'sys','user')['intent']=='general'


def test_stt_returns_transcript_with_mock_api():
    def transcribe(**kwargs):
        assert kwargs['language']=='ko'
        assert kwargs['file'].name=='test.wav'
        return SimpleNamespace(text='발표 자료 작성 완료')
    client=SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=transcribe)))
    assert stt(client,b'FAKE_WAV','test.wav')=='발표 자료 작성 완료'


def test_page_structure_and_no_nested_expander_by_scope():
    app=(BASE/'app.py').read_text()
    assert 'PAGES = ["대시보드", "스마트 캘린더", "업무 관리", "AI 비서", "문서 도구", "팀 협업", "활동 기록"]' in app
    assert 'st.html("<style>" + "\\n".join(rules) + "</style>")' in app
    assert 'st.session_state.pending = None' in app
    assert 'chat_handle(st.session_state[key], data, f)' in app
    assert 'st.audio(st.session_state.last_voice' in app
    assert 'APP_PASSWORD' in app

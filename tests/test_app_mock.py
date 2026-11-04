"""Smoke-test calendar/assistant flow with a mocked Streamlit UI.

This intentionally does not claim browser or Cloud verification.
"""
import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from storage.store import Store, empty_data


class State(dict):
    def __getattr__(self, name):
        try: return self[name]
        except KeyError as exc: raise AttributeError(name) from exc
    def __setattr__(self,name,value): self[name]=value


class Context:
    def __enter__(self): return self
    def __exit__(self,*a): return False


class Column:
    def __init__(self, st): self.st=st
    def markdown(self,*args,**kwargs): pass
    def write(self,*args,**kwargs): pass
    def button(self,*args,**kwargs):
        self.st.button_labels.append(args[0] if args else ''); return False
    def __enter__(self): return self
    def __exit__(self,*args): pass


class FakeStreamlit(ModuleType):
    def __init__(self):
        super().__init__('streamlit')
        self.session_state=State()
        self.context=SimpleNamespace(theme=SimpleNamespace(type='light'))
        self.css=[]
        self.button_labels=[]
        self.sidebar=Context()
    def set_page_config(self,*a,**k): pass
    def html(self,value,*a,**k): self.css.append(value)
    def columns(self,n,*a,**k):
        n=n if isinstance(n,int) else len(n)
        return [Column(self) for _ in range(n)]
    def title(self,*a,**k): pass
    def caption(self,*a,**k): pass
    def markdown(self,*a,**k): pass
    def subheader(self,*a,**k): pass
    def info(self,*a,**k): pass
    def expander(self,*a,**k): return Context()
    def form(self,*a,**k): return Context()
    def text_input(self,*a,**k): return ''
    def text_area(self,*a,**k): return ''
    def selectbox(self,*a,**k): return '보통'
    def form_submit_button(self,*a,**k): return False
    def button(self,*a,**k):
        self.button_labels.append(a[0] if a else '')
        return False
    def rerun(self): pass


@pytest.fixture
def app(monkeypatch):
    fake=FakeStreamlit()
    monkeypatch.setitem(sys.modules,'streamlit',fake)
    try:
        import openai
        from openai import OpenAI
    except ImportError:
        placeholder=ModuleType('openai'); placeholder.OpenAI=object
        monkeypatch.setitem(sys.modules,'openai',placeholder)
    spec=importlib.util.spec_from_file_location('aivle_ui_test', ROOT/'app.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module,fake


def test_calendar_renders_today_blue_and_due_red(app):
    module,st=app
    now=module.today()
    next_day=(date.fromisoformat(now)+timedelta(days=1)).isoformat()
    st.session_state.cal_year=int(now[:4]);st.session_state.cal_month=int(now[5:7]);st.session_state.cal_selected=now
    module.calendar_page({'tasks':[{'id':1,'name':'문서 제출','deadline':next_day,'status':'미착수'}]})
    css=''.join(st.css)
    today_key=f'.st-key-cal_{now.replace("-","_")}'
    next_key=f'.st-key-cal_{next_day.replace("-","_")}'
    assert today_key in css and 'border:3px solid #1974e9!important' in css
    assert next_key in css and 'background:#ffdadd!important' in css
    assert any('오늘' in label for label in st.button_labels)


def test_calendar_dark_renders_dark_bg_and_blue_today(app):
    module,st=app
    st.context.theme.type='dark'
    now=module.today()
    st.session_state.cal_year=int(now[:4]);st.session_state.cal_month=int(now[5:7]);st.session_state.cal_selected=now
    module.calendar_page({'tasks':[{'id':1,'name':'당일 마감','deadline':now,'status':'미착수'}]})
    css=''.join(st.css)
    assert 'background:#5a3038!important' in css
    assert 'border:3px solid #72b7ff!important' in css


def test_ai_proposes_before_any_write_then_approval_persists(app, monkeypatch,tmp_path):
    module,st=app
    store=Store(path=tmp_path/'auto_tasks.json')
    monkeypatch.setattr(module,'storage',lambda:store)
    monkeypatch.setattr(module,'plan_chat',lambda *a,**k: {
       'answer':'발표 준비 업무를 등록하겠습니다.',
       'intent':'add_task',
       'task':{'name':'발표 준비','deadline':'2026-11-20','priority':'높음','description':''}})
    monkeypatch.setattr(module,'client',lambda:object())
    monkeypatch.setattr(module,'create_voice_reply',lambda text:None)
    module.bootstrap()
    assert store.load()['tasks']==[]
    module.chat_handle('11월20일까지 발표 준비 등록',store.load())
    assert store.load()['tasks']==[]
    assert st.session_state.pending['type']=='add_task'
    module.approved_action(st.session_state.pending)
    assert len(store.load()['tasks'])==1
    assert store.load()['tasks'][0]['deadline']=='2026-11-20'

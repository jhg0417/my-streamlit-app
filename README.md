# AIVLE 개인비서 — 미니프로젝트 3차 최종 점검본 (v5)

**대상:** Colab `02 - 사용자 인터페이스 구현` → `jhg0417/my-streamlit-app` → Streamlit Community Cloud. 기존 7개 메뉴를 유지하고 AI 비서 기능을 중심으로 연결했습니다.

## 무엇이 실제로 연결되는가

- **0건 시작:** 예전 1일차 `aivle_tasks.json`에 생성한 테스트 업무 8건은 자동으로 불러오지 않습니다.
- **업무 저장 자동화:** 앱은 `storage/store.py`를 통해 `data/aivle_tasks.json`을 자동으로 읽고 갱신합니다. 사용자가 JSON 파일을 선택하거나 가져올 필요가 없습니다. 클라우드 영구 저장은 *별도의 Supabase 설정*이 있어야 가능합니다.
- **AI 업무 제안:** “11월 20일까지 발표 준비 업무 등록해 줘” → AI가 업무명·마감일 추출 → **등록 승인** 클릭 시 저장 → 대시보드·업무 관리·달력에서 동일한 정보를 읽습니다.
- **달력:** 오늘은 항상 파란 테두리, 미완료 업무의 마감일은 빨간 배경, 완료 업무만 있는 날은 초록 배경. 선택한 날짜는 안쪽 테두리로 추가 표시합니다. 오늘과 마감일이 겹쳐도 파란 테두리와 빨간 배경을 모두 유지합니다.
- **AI 대화:** 음성 녹음 → STT → 텍스트 수정 → 질문. 파일(TXT/PDF/DOCX/MP3/M4A/WAV) 첨부. 프롬프트 개선 후 즉시 질문. TTS 생성 기본 ON, 재생 플레이어 제공. AI 답변이 음성으로 자동재생되는지는 브라우저의 자동재생 정책에 따라 달라질 수 있습니다.
- **회의록:** 원문 요약·업무 추출 → *선택 및 승인* → 저장. 해시 기반 중복 등록 방지. 기존 회의록 업로드 메뉴도 그대로 유지합니다.
- **이메일:** AI가 초안을 만들거나 업무 처리 결과에서 “이 결과 이메일로 공유” 클릭 → 이메일 주소·제목·본문 입력/확인 → 명시적으로 승인 후 Gmail SMTP 발송.
- **기타:** 문서 요약·번역, 회의록 비교, 활동 기록·직전 변경 취소. 팀 공유는 여전히 단일 사용자 MVP의 추후 확장 기능입니다.

## 최종 테마 변경 (중요)

이전 **앱 자체의 ‘🌙 다크 모드’ 토글은 제거**했습니다. CSS로 표면 일부만 바꾸면 Streamlit 기본 위젯과 충돌해 *어두운 버튼/보이지 않는 글씨/그대로 밝은 배경* 문제가 반복됐기 때문입니다.

이번에는 `.streamlit/config.toml`에서 Streamlit **공식 라이트/다크 테마를 각각 정의**했습니다. **앱 오른쪽 위 `⋮` → Settings(설정) → Theme(테마) → Dark**를 선택하세요.

- 라이트: 옥색 사이드바 + 연한 옥색 배경 + 진한 글자
- 다크: 짙은 회색 사이드바 + 차콜 배경 + 밝은 글자 + 어두운 입력창
- 달력의 날짜 색상은 `services/calendar_rules.py`에서 별도 계산하되, 오늘/마감 의미는 유지합니다.

## Colab 실행 순서

1. **v5 노트북**을 업로드하고 위에서부터 순서대로 실행합니다. 환경 준비 부분은 수업 원본의 Google Drive와 `project03/api_key.txt` 로딩 방식을 사용합니다.
2. 기존 `api_key.txt`에 `OPENAI_API_KEY`, `GH_TOKEN`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`가 존재하면 **다시 입력할 필요가 없습니다**. 파일 내용을 출력하지 마세요.
3. `%%writefile app.py`, `%%writefile services/...`, `%%writefile storage/...`, `.streamlit/config.toml`, `requirements.txt` 생성 셀을 순서대로 실행합니다.
4. 코드 테스트 셀에서 **21개 테스트가 통과**해야 합니다(단위·모의 UI 테스트, 실제 브라우저 실행 검증은 아님).
5. 마지막 GitHub push 셀이 실행되면 **기존** `jhg0417/my-streamlit-app`에 반영됩니다. 그 전에 공개 저장소에 비밀키가 섞여 있는지 다시 확인하세요.
6. Streamlit Community Cloud의 기존 앱을 재배포 또는 Reboot하고, 브라우저에서 `Ctrl+Shift+R` 새로고침합니다. App Secrets에 이미 등록된 OpenAI/Gmail 정보는 그대로 유지합니다.

## Streamlit `Network issue: Cannot load Streamlit frontend code`

이 오류는 **Python AI 코드의 예외와 별도로 프런트엔드 JS 파일을 불러오지 못한 것**을 의미합니다. 이번 `requirements.txt`는 `streamlit==1.66.0`으로 버전을 고정해 Python 3.14와 호환되는 최신 안정 버전(2026-11 기준)을 사용하도록 했습니다. **이것만으로 네트워크·브라우저 캐시 문제를 100% 해결할 수는 없습니다.**

점검 순서: `GitHub push 성공 → 배포 완료 확인 → Reboot app → Ctrl+Shift+R → 시크릿 창 테스트 → Manage app > Logs`. 지속되면 브라우저 개발자도구(Network)에서 `/_/static/` 요청의 404·403·네트워크 실패를 확인하세요. Python 자체의 예외라면 Logs의 Python traceback을 고쳐야 합니다. 앱의 Python 버전 변경은 기존 앱에서 단순 재부팅으로 적용되지 않고 재배포가 필요할 수 있으므로, **오류를 확인하기 전에는 앱을 삭제하지 마세요.**

## 테스트

```bash
python -m compileall -q app.py services storage
python -m pytest -q tests/test_store.py tests/test_final_workflow.py tests/test_app_mock.py
```

테스트 내용: 빈 업무 0건 시작, 파일 저장 자동 읽기/쓰기, 변경·완료·복구, 중복 방지, 당일 파란 테두리, 미완료 빨강·완료 초록, 어두운 캘린더 색상, Streamlit 모의 달력 렌더, AI 승인 전/후 상태, 이메일 파라미터 확인과 모의 SMTP, 모의 STT/TTS/LLM.

**실제 Streamlit Cloud와 OpenAI API, Gmail SMTP를 호출하는 통합 테스트는 이 작업 환경에서 수행하지 못했습니다.** 직접 접근 권한이나 인증정보가 있는 실행 환경에서 아래 수동 테스트를 진행해야 합니다.

## 배포 후 필수 수동 테스트

- [ ] **첫 접속:** 업무 0건, 대시보드 0건, 캘린더 오늘 파란 테두리
- [ ] **AI 등록:** “11월 20일까지 발표자료 작성” → 승인 전 0건 → 승인 후 1건
- [ ] **연동:** 업무 관리에서 해당 업무 확인, 11월 20일 빨강, 대시보드 진행 중 1건
- [ ] **완료:** “발표자료 작성 완료” → 승인 → 캘린더 초록, 대시보드 완료 1건
- [ ] **다크 모드:** 오른쪽 위 `⋮` → 테마 Dark → **배경·사이드바·카드·글자·버튼 모두 정상**
- [ ] **STT/TTS:** 웹 마이크 녹음→변환→질문→AI 응답 플레이어에서 재생
- [ ] **프롬프트 개선:** 문장 개선 후 내용을 확인하고 곧바로 AI 질문
- [ ] **회의록:** TXT 업로드→후보 승인→업무 반영→동일 회의록 중복 저장 차단
- [ ] **Gmail:** 본인이 소유한 테스트 수신자에게 승인 후 발송 및 도착 확인
- [ ] **재시작 지속성:** Supabase를 연결했다면 재배포/재부팅 후에도 업무가 유지됨

## 영구 보존이 필요한 경우 — Supabase

Streamlit Community Cloud의 로컬 `data/aivle_tasks.json`은 **클라우드 서버 재부팅 또는 재배포 때 사라질 수 있습니다.** 웹앱에서 업무 파일을 직접 업로드하게 하는 대신, 이 경우 `supabase_setup.sql`을 실행해 외부 DB를 연결하세요.

Streamlit App settings → Secrets에 추가:

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "YOUR_SERVER_ONLY_KEY"
APP_PASSWORD = "CHOOSE_A_LONG_PRIVATE_LOGIN_PASSWORD"
```

`APP_PASSWORD`는 단일 사용자 교육용 간편 보호 수단이고 실서비스의 계정별 인증·권한 관리를 대체하지 않습니다. 이 앱의 팀 협업 기능은 활성화되어 있지 않습니다.

## 보안

`.streamlit/secrets.toml`, `api_key.txt`, 개인 업무 JSON, Gmail 앱 비밀번호, GitHub 토큰, Supabase 서비스 키는 절대로 공개 저장소에 올리지 마세요. `.gitignore`에서 제외합니다. 기존 `project03` 데이터와 1일차 원본은 수정하지 않습니다.

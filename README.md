# AIVLE AI 업무비서 — KT AIVLE School 3차 미니프로젝트 (Colab 배포형 v3)

> **시연은 업무 0건에서 시작**합니다. `project03/aivle_tasks.json`의 8건은 연습 데이터이므로 프로젝트에 넣거나 자동 로드하지 않습니다. 기존 ZIP과 자료는 수정하지 않습니다.

## 실제로 작동하는 기능

- **AI 비서**: GPT 답변과 멀티턴 대화(현재 세션 20개 메시지), 자연어 업무 등록/변경/완료 **제안 → 승인 후 저장**
- **업무 관리 / 스마트 캘린더 / 대시보드**: 같은 저장소를 실시간 조회. 완료 체크, 수정, 삭제, 검색, 월간 마감 표시. 각 메뉴 상단에서 같은 AI 채팅창을 열 수 있음
- **채팅창 내 프롬프트 개선**: 동일한 입력창에서 `질문 구체화` → 수정 가능 미리보기 → `개선된 질문으로 바로 묻기`
- **채팅 안 파일 업로드**: TXT/MD/PDF/DOCX/MP3/M4A/WAV 첨부 가능. 회의록으로 요청하면 STT/요약·근거·신규/변경 업무 후보 → 사용자 승인 → 저장. 텍스트·파일 해시 중복 방지
- **음성**: 웹 마이크 녹음 → OpenAI STT → 텍스트 확인 및 프롬프트 개선 또는 바로 전송 → AI 답변과 **기본 켜짐 TTS 음성**. 자동재생이 차단되면 재생 버튼 사용
- **이메일**: AI 업무 결과 뒤 `이 업무 결과 이메일로 공유` 버튼 → 수신자·제목·본문 편집 → 승인 체크 → Gmail SMTP 실제 전송. 직접 승인 전에는 발송하지 않음
- **문서 도구**: TXT/PDF/DOCX 텍스트 요약·번역(원본 PDF/DOCX 레이아웃 보존 안 됨), 이전·새 회의록 비교
- **활동 기록**: 업무 추가/수정/삭제 기록, 직전 변경 취소
- **웹 검색**: Tavily 키가 있을 때만 실제 검색 가능; 키 없으면 검색 스위치 비활성
- **팀 협업**: 아직 구현되지 않은 기능임을 명확히 표시(개인정보가 다른 사용자에게 노출되지 않도록 미구현)

## 파일 구조

```text
my-streamlit-app/
  app.py                      # Streamlit 시작 파일 / 7개 메뉴
  services/ai.py              # OpenAI, STT, TTS, 프롬프트, 회의록
  services/emailer.py         # Gmail SMTP (승인 후 호출)
  services/documents.py       # PDF/DOCX/TXT 텍스트 추출
  storage/store.py            # 업무 저장·수정·삭제·복구·중복 검사
  data/.gitkeep               # 업무 데이터는 GitHub에 넣지 않음
  tests/test_store.py         # 핵심 저장 및 변경 테스트
  .streamlit/config.toml      # 테마
  .streamlit/secrets.example.toml  # 키 *형식* 예시만 있음
  supabase_setup.sql          # 외부 영구 저장소용 테이블
  requirements.txt
  .gitignore
```


## 권장 실행: 02 사용자 인터페이스 구현 Colab 노트북 (v3)

1. `02_사용자_인터페이스_구현_Colab_통합완성본_v3.ipynb`을 Colab에 업로드합니다.
2. 상단부터 1일차와 동일하게 Google Drive 연결 및 `project03/api_key.txt` 환경변수 로딩 셀을 실행합니다. 파일의 비밀번호·토큰은 코드나 출력에 노출하지 않습니다.
3. 이어지는 `%%writefile` 셀들이 `app.py`, 서비스·저장소 파일, `requirements.txt`를 만듭니다.
4. 테스트 셀 확인 후 `GH_USER=jhg0417`, `REPO=my-streamlit-app` 설정을 유지한 채 기존 저장소를 clone하고 마지막 push 셀을 실행합니다.
5. Streamlit Community Cloud에서 기존 앱을 재부팅합니다. Secrets는 이미 등록되어 있다면 유지하고 `APP_PASSWORD` 설정 여부만 확인하세요.
6. AI 비서 탭 또는 각 메뉴 위의 `💬 AIVLE AI 비서`를 열어 **음성 응답이 켜져 있는지** 확인합니다. 말한 내용은 `🎙️ 인식 후 문장 수정` 또는 `🎤 바로 질문`으로 처리합니다.

**오디오 제한:** Streamlit `st.audio(autoplay=True)`는 브라우저가 자동재생을 막을 수 있습니다. 그래서 플레이어도 항상 표시합니다. 응답 텍스트는 정상인데 음성 생성 오류가 나면 페이지의 경고와 배포 Logs를 확인하세요. 음성 생성 호출은 API 사용량을 발생시킵니다.

**안전:** 앱을 공개로 운영할 경우 반드시 강력한 `APP_PASSWORD`를 설정하세요. 이 앱은 데모용 단일 사용자 설계로, 다중 사용자 권한 분리는 아직 구현되지 않았습니다.

## 1. Windows Anaconda에서 실행 (선택)

Anaconda Prompt를 열고 본 프로젝트가 있는 폴더에서:

```bat
conda create -n aivle-able python=3.12 -y
conda activate aivle-able
python -m pip install -r requirements.txt
```

`.streamlit/secrets.example.toml`을 **`.streamlit/secrets.toml`** 로 복사해서 아래 항목을 실제 값으로 수정합니다. 이 파일은 `.gitignore` 처리되어 GitHub에 업로드되지 않습니다.

```toml
OPENAI_API_KEY = "본인_실제_OpenAI_API_키"
GMAIL_ADDRESS = "본인_이메일@gmail.com"
GMAIL_APP_PASSWORD = "Gmail_앱_비밀번호"
APP_PASSWORD = "웹앱_로그인_비밀번호"
```

```bat
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속. **OpenAI API 사용은 과금될 수 있습니다.** 기존 1일차 `api_key.txt` 파일을 그대로 프로젝트에 복사하지 마세요.

## 2. GitHub: 기존 `jhg0417/my-streamlit-app`으로 배포

**안전하게 진행:** 저장소의 현재 코드를 로컬에 `git clone`으로 백업하고, 다운로드 ZIP 내용을 풀어 파일들을 저장소 **최상위 경로**에 복사한 뒤 커밋합니다. 본인의 프로젝트에 직접 `git push`하는 절차입니다. 이 ZIP은 GitHub에 직접 업로드된 상태가 아닙니다.

Anaconda Prompt (git 설치된 경우):

```bat
git clone https://github.com/jhg0417/my-streamlit-app.git
cd my-streamlit-app
```

프로젝트 ZIP을 해제한 파일들(`app.py`, `services`, `storage`, `data`, `.streamlit`, ...)을 이 폴더에 복사합니다. `.git` 폴더는 **삭제하지 않습니다**. 그다음:

```bat
git add app.py requirements.txt README.md .gitignore .streamlit/config.toml .streamlit/secrets.example.toml services storage data/.gitkeep tests supabase_setup.sql
git commit -m "Integrate AIVLE AI assistant with live tasks and approval flow"
git push origin main
```

확인: GitHub 저장소 첫 화면에 `app.py`와 `requirements.txt`가 나타나야 합니다. 비밀번호·API 키·GitHub 토큰·원본 업무 JSON은 업로드하지 마세요.

### Streamlit Community Cloud

1. [share.streamlit.io](https://share.streamlit.io/)에서 앱 선택(기존 앱이면 관리 화면).
2. Repository: `jhg0417/my-streamlit-app` / Branch: `main` / **Main file path: `app.py`** 로 확인.
3. **App settings → Secrets**에 `.streamlit/secrets.toml`의 **실제 값**을 붙여 넣습니다. 민감정보는 GitHub가 아니라 Cloud 설정에만 입력합니다.
4. `Reboot` / 재배포. 오류가 발생하면 **Manage app → Logs**를 확인합니다.
5. 영구 저장이 필요하면 아래 Supabase 설정을 반드시 수행합니다. Cloud에서 JSON 저장만으로 영구 보존된다고 생각하면 안 됩니다.

## 3. 업무 영구 저장 — Supabase 권장

**실제 서비스처럼 재시작해도 업무를 유지하려면 필수입니다.** 기본값 로컬 JSON은 실행한 서버에만 저장되어, Streamlit Community Cloud 재시작·재배포 시 사라질 수 있습니다.

1. [Supabase](https://supabase.com/) 프로젝트를 만듭니다.
2. SQL Editor에서 `supabase_setup.sql` 내용을 실행합니다.
3. Project Settings에서 프로젝트 URL과 **service_role/secret 서버용 키**를 확인합니다. 키는 외부에 공개하지 않습니다.
4. Streamlit Cloud의 Secrets에 아래 두 항목과 강력한 `APP_PASSWORD`를 추가합니다.

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "YOUR_SERVER_ONLY_KEY"
APP_PASSWORD = "LONG_RANDOM_PRIVATE_PASSPHRASE"
```

5. 재시작 후 사이드바에 **`Supabase (지속 저장)`** 이 보이는지 확인. 다른 브라우저/새로고침에서도 업무를 확인합니다.

Supabase는 기본적으로 업무를 하나의 `personal` 레코드에 저장하는 **단일 사용자 DB**입니다. 프로젝트를 인터넷 공개 상태로 운영하려면 접근 비밀번호를 반드시 사용하세요. 이것은 다중 사용자 인증/권한 관리 대체재가 아닙니다. 다중 사용자 서비스는 추후 Supabase Auth 및 RLS 정책으로 개발해야 합니다.

## 4. 5분 기능 시연 스크립트

1. 업무 관리/캘린더에서 **0건** 확인.
2. AI 비서에서 `에이블, 2026년 11월 20일까지 발표 자료 작성 업무를 등록해 줘. 우선순위 높음.` 입력.
3. **아직 DB 0건**인지 확인 → AI 제안의 **등록 승인** 클릭.
4. 대시보드에서 1건, 업무 관리에서 1건, 캘린더 11월 20일 빨간 칸 확인.
5. AI 비서에게 `발표 자료 작성 완료했어` → **변경 승인** 클릭.
6. 대시보드 완료 1건, 캘린더 초록 표시 확인.
7. 프롬프트 개선 탭에서 `다음 주 회의 준비해 줘` → 개선 → 수정 → 적용.
8. 회의록 TXT 업로드 → 분석 → 선택한 업무 저장. **동일 파일 다시 등록 시 중복 방지**.
9. 음성 녹음 → STT 화면 표시 → AI 답변·음성 듣기.
10. 이메일은 **본인이 소유한 테스트 주소**로 초안 확인 후 승인하여 송신/수신 검증.

## 5. 제한 및 주의

- 이 환경에서 API 호출과 Gmail 발송은 **실행하지 않았습니다.** 실제 키가 있는 Windows/Cloud 환경에서 테스트해 주세요.
- AI는 업무 변경을 직접 실행하지 않고 제안만 합니다. 사용자 승인 및 서버 측 유효성 검사 후 저장합니다.
- 로컬 JSON은 로컬 개발용입니다. Streamlit Cloud 영속성은 Supabase가 필요합니다.
- 채팅 히스토리는 현재 세션에만 보관합니다. 계정별 장기 저장은 후속 과제입니다.
- 대용량 문서 전체 번역/요약, PDF 이미지 OCR, 완전한 실시간 음성 통화, 예약 메일, 팀별 개별 로그인/공유는 포함되지 않습니다.
- `APP_PASSWORD`는 소규모 교육용 단일 사용자 보호장치입니다. 공개 기업용 서비스 인증 수준은 아닙니다.

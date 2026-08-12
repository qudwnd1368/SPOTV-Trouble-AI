# SPOTV Trouble AI

장애이력과 장비 매뉴얼을 함께 검색하는 방송 기술 장애 대응 시스템입니다. 관리자 메뉴에서 Google Drive 공유 폴더 또는 직접 업로드한 PDF를 페이지별로 색인하며, 검색 결과에 매뉴얼명·페이지·원문 링크를 표시합니다.

방송 장애이력을 자연어로 검색하고, 과거 사례를 근거로 안전한 점검 순서를 제안하는 Streamlit MVP입니다.

## Windows에서 가장 쉽게 실행하기

1. `SPOTV-Trouble-AI.zip`을 마우스 오른쪽 버튼으로 클릭하고 **모두 압축 풀기**를 선택합니다.
2. 압축을 푼 폴더에서 `setup_windows.ps1`을 마우스 오른쪽 버튼으로 클릭하고 **PowerShell에서 실행**합니다.
3. 실행이 차단되면 폴더 빈 곳에서 터미널을 열고 다음 명령을 복사합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1
```

설치 후에는 `run_windows.bat`을 더블클릭하면 실행됩니다. 브라우저가 열리지 않으면 <http://localhost:8501>로 접속하세요.

> Python이 없다면 [python.org](https://www.python.org/downloads/)에서 Python 3.11 이상을 설치하세요. 설치 화면에서 **Add Python to PATH**를 체크해야 합니다.

## OpenAI API 연결 (선택)

API 키가 없어도 로컬 의미 유사도 검색으로 동작합니다. OpenAI 임베딩과 AI 답변을 사용하려면 `.env`를 메모장으로 열고 다음처럼 입력합니다.

```dotenv
OPENAI_API_KEY=여기에_본인의_API_키
```

API 키를 소스 코드나 GitHub에 올리지 마세요. `.env`는 `.gitignore`에 포함되어 있습니다.

## 관리자 메뉴와 사이드바 이미지

장애이력 관리, 새 장애 등록, 매뉴얼 관리, 시스템 정보 메뉴는 관리자 비밀번호로 보호됩니다. `.env` 또는 Google Secret Manager의 `ADMIN_PASSWORD` 값을 반드시 설정해야 합니다. 실제 비밀번호는 저장소에 커밋하지 마세요.

사이드바에 사용할 이미지는 `assets` 폴더를 만들고 `sidebar_logo.png`라는 이름으로 넣으면 자동 표시됩니다. JPG 파일은 `sidebar_logo.jpg`를 사용할 수 있습니다.

## 수동 설치

PowerShell에서 `app.py`가 보이는 프로젝트 폴더로 이동한 다음 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

초기 실행 시 SQLite DB(`spotv_trouble.db`)와 기본 장애사례 5건이 자동 생성됩니다. 등록·수정·삭제 내용은 즉시 검색 대상에 반영됩니다.

## 파일 구성

- `app.py`: Streamlit 화면과 사용자 흐름
- `database.py`: SQLite 스키마와 CRUD
- `search.py`: OpenAI 임베딩 및 로컬 검색
- `ai_service.py`: 과거 사례 기반 AI 분석
- `seed_data.py`: 초기 장애사례 5건
- `styles.py`: NOC 스타일 UI
- `setup_windows.ps1`: Windows 자동 설치 및 실행

## Google Cloud에서 팀 공유하기

클라우드 배포에서는 다음 구성을 사용합니다.

- Cloud Run: Streamlit 앱 실행
- Firestore: 장애이력 중앙 저장
- Firestore `manuals`, `manual_index_parts`: 매뉴얼 정보와 검색 색인 저장
- Google OIDC: 허용된 팀원 Google 계정 로그인
- Secret Manager: OAuth 비밀키, 관리자 비밀번호 저장

Cloud Run의 로컬 디스크는 영구 저장소가 아니므로 `DATABASE_BACKEND=firestore`일 때 `storage.py`가 Firestore 구현으로 자동 전환됩니다. 로컬 실행은 계속 SQLite를 사용합니다.

관리자 로그인 후 **매뉴얼 관리 → Drive 폴더 색인 동기화**를 누르면 공유 폴더의 PDF가 색인됩니다. `MANUAL_DRIVE_FOLDER_ID` 환경변수에 공유 폴더 ID를 설정해야 합니다. 폴더 ID와 원본 파일은 공개 저장소에 커밋하지 마세요. 원본 PDF를 나중에 삭제해도 Firestore 색인은 별도로 삭제하기 전까지 유지됩니다.

### 1단계: 비공개 초기 배포

Google Cloud CLI에 로그인하고 다음 명령을 실행합니다. 프로젝트 ID는 전 세계에서 고유한 영문 ID입니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap_google_cloud.ps1 -ProjectId "내-프로젝트-ID"
```

스크립트가 Firestore, 전용 서비스 계정, 비공개 Cloud Run 서비스를 만들고 마지막에 OAuth Redirect URI를 보여줍니다.

### 2단계: Google OAuth 만들기

Google Cloud Console의 **Google Auth Platform → Clients**에서 Web application OAuth 클라이언트를 생성합니다. 승인된 리디렉션 URI에는 1단계에서 표시된 다음 주소를 입력합니다.

```text
https://서비스주소.run.app/oauth2callback
```

### 3단계: 팀 공개 배포

OAuth Client ID와 허용할 팀원 이메일을 입력합니다. Client Secret과 관리자 비밀번호는 화면에 표시되지 않는 보안 입력창에서 입력하며 소스 코드에 저장되지 않습니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\release_google_cloud.ps1 `
  -ProjectId "내-프로젝트-ID" `
  -OAuthClientId "클라이언트-ID.apps.googleusercontent.com" `
  -AllowedEmails "user1@company.com,user2@company.com" `
  -ManualDriveFolderId "공유-드라이브-폴더-ID"
```

### 기존 로컬 장애이력 이전

Google Cloud Application Default Credentials를 설정하고 `.env`에 `GOOGLE_CLOUD_PROJECT`를 입력한 뒤 실행합니다.

```powershell
gcloud auth application-default login
.\.venv\Scripts\python.exe .\migrate_to_firestore.py
```

동일한 사고번호가 이미 있으면 업데이트하고, 없으면 새로 등록합니다.

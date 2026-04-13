# Multi-Workspace 전환 — 전체 실행계획서 (사용자 작업 포함)

> 본 문서는 사용자(이창근)와 개발 보조(Claude)가 **순서대로 함께 진행**할 수 있도록, 각 단계마다 누가 무엇을 하는지, 어디를 클릭하고 어떤 명령을 실행하는지, 어떻게 검증하는지를 모두 기술한다.

## 사용 방법

- 각 단계는 **STEP n** 으로 번호가 매겨져 있다. 위에서 아래로 순서대로 진행한다.
- 단계 머리말의 **[USER]** / **[CLAUDE]** / **[USER+CLAUDE]** 표시는 누가 그 단계를 실행하는지를 의미한다.
  - **[USER]** — 사용자가 직접 브라우저, 터미널, 슬랙 앱 설정 등에서 작업
  - **[CLAUDE]** — 코드/문서 수정 작업, 사용자가 "진행해 줘"라고 지시하면 Claude가 수행
  - **[USER+CLAUDE]** — 사용자가 검증하면서 Claude가 수정하는 협업 단계
- 각 단계의 마지막에는 **체크박스**가 있다. 완료 시 ✅ 표시.
- 어느 단계에서든 막히면, 그 단계 안의 "막혔을 때" 항목을 먼저 확인하고, 그래도 안 되면 사용자가 중단하고 다음 작업을 지시하면 된다.

## 사전 가정

- 사용자는 https://happytestyong.slack.com 워크스페이스의 admin 권한을 가진다.
- 사용자는 추가로 적어도 한 곳의 **테스트용 워크스페이스**(예: 개인 워크스페이스 또는 사이드 프로젝트용)에 admin 권한을 가진다 — Multi-workspace 동작 검증에 필수.
- 개발 환경: Windows + miniconda (`slack` 환경) + Python, [bolt-python-ai-chatbot](.) 레포 클론 완료.
- `python app.py` 가 현재 single-workspace 모드로 정상 동작 중이다.

---

# Phase 0 — 사전 준비

## STEP 0.1 [USER] 작업 브랜치 생성

**목적**: 전체 작업을 별도 브랜치에서 진행해 main을 보호한다.

**작업**:
1. 터미널을 열고 프로젝트 루트로 이동
   ```bash
   cd d:\DEV_slack\bolt-python-ai-chatbot
   ```
2. 현재 상태 확인
   ```bash
   git status
   git branch
   ```
3. 작업 브랜치 생성
   ```bash
   git checkout -b feature/multi-workspace
   ```

**검증**: `git branch` 결과에 `* feature/multi-workspace` 가 보이면 성공.

**막혔을 때**: 현재 작업 중 미커밋 변경분이 많아 브랜치 전환이 막힌다면, 사용자가 어느 변경을 살릴지 결정 후 commit 또는 stash. 이 시점에 무엇을 commit할지 결정이 어려우면 Claude에게 "현재 변경사항을 정리해 줘"라고 지시.

- [ ] 완료

---

## STEP 0.2 [USER] 데이터 백업

**목적**: 기존 사용자 설정(`data/`)을 잃지 않도록 백업.

**작업**:
1. 탐색기로 `d:\DEV_slack\bolt-python-ai-chatbot\data\` 를 열어 내용을 확인
2. 같은 위치에 `data_backup_YYYYMMDD.zip` 으로 압축 (예: `data_backup_20260411.zip`)
3. 백업 zip 파일을 안전한 다른 위치(예: `d:\backups\`)로 한 부 더 복사

**검증**: 백업 zip을 압축 해제했을 때 원본 `data/` 와 동일한 파일 구조가 보이면 성공.

- [ ] 완료

---

## STEP 0.3 [USER] 현재 상태 스모크 테스트

**목적**: 작업 시작 전 "정상이었던 상태"를 기록해서 회귀 발생 시 비교 기준으로 삼는다.

**작업**:
1. `python app.py` 로 봇 실행
2. 슬랙에서 다음 3가지를 테스트하고 결과를 메모:
   - DM에서 "안녕?" 입력 → AI 응답 확인
   - 봇이 멤버인 채널에서 "@봇 안녕" 입력 → AI 응답 확인
   - 봇이 멤버인 채널에 PDF 1개 업로드 → `download/` 폴더에 저장 + ✅ 리액션 확인
3. `Ctrl+C` 로 봇 종료
4. 결과 메모를 잠시 보관 (Phase 7 통합 테스트 때 비교)

**검증**: 3가지 시나리오 모두 정상.

**막혔을 때**: 만약 이 시점에 무언가 깨져 있다면 multi-workspace 전환을 시작하기 전에 그 문제부터 해결. Claude에게 증상 알려주고 우선 수정 요청.

- [ ] 완료

---

## STEP 0.4 [USER] 두 번째 테스트용 워크스페이스 확보

**목적**: Multi-workspace 전환의 결과는 "최소 2개의 워크스페이스에서 동시에 동작"해야 검증 가능.

**작업**:
1. 본인이 admin 권한을 가진 두 번째 워크스페이스를 결정
   - 후보 1: 개인 슬랙 워크스페이스
   - 후보 2: 새로 생성 (https://slack.com/create — 무료, 1분이면 생성)
2. 두 워크스페이스의 이름과 URL을 메모:
   - 워크스페이스 A (기존): `happytestyong.slack.com` — team_id: (Phase 1에서 확인)
   - 워크스페이스 B (신규 테스트): `__________.slack.com` — team_id: (Phase 1에서 확인)
3. 워크스페이스 B에서 테스트용 채널 1개를 만들어 둔다 (예: `#bolty-test`)

**검증**: 두 워크스페이스 모두 admin으로 로그인 가능.

- [ ] 완료

---

## STEP 0.5 [USER] ngrok 준비

**목적**: OAuth 설치 흐름은 외부에서 접근 가능한 HTTPS endpoint가 필요. 개발 중에는 ngrok 으로 임시 터널을 만든다.

**작업**:
1. https://ngrok.com 가입 (무료 플랜 OK)
2. ngrok 다운로드 및 설치 (Windows 용 zip → 압축 해제 → PATH 등록 또는 직접 경로 지정)
3. 본인 계정의 authtoken 설정
   ```bash
   ngrok config add-authtoken <ngrok_dashboard에서_복사한_token>
   ```
4. **이 시점에는 아직 터널을 시작하지 않는다**. Phase 3에서 사용.

**검증**: `ngrok version` 으로 버전이 표시되면 성공.

**대안**: ngrok 대신 Cloudflare Tunnel(`cloudflared`), localtunnel 등을 써도 무방. 본 문서는 ngrok 기준으로 작성.

- [ ] 완료

---

# Phase 1 — Slack 앱 설정 변경

## STEP 1.1 [USER] 기존 워크스페이스 team_id 확인

**목적**: 마이그레이션 시 기존 사용자 데이터를 어느 team_id 폴더로 옮길지 결정.

**작업**:
1. 브라우저에서 https://happytestyong.slack.com 접속 후 로그인
2. 좌측 상단 워크스페이스 이름 클릭 → **Settings & administration** → **Workspace settings**
3. 페이지가 새 탭에서 열리면 URL 확인:
   - URL 형식: `https://<...>.slack.com/admin/settings`
   - 또는 워크스페이스 admin → **About this workspace** 에서 team_id 표시
4. 혹은 Slack API에서 직접 확인:
   - 봇이 실행 중일 때 콘솔의 이벤트 로그에서 `'team': 'T0A5QTAHG76'` 같은 값을 찾는다 (이미 [error.txt](error.txt) 에서 본 적 있음)
5. team_id 를 메모: `LEGACY_TEAM_ID = T__________`

**검증**: `T` 로 시작하는 11자리 ID 확보.

- [ ] 완료 — `LEGACY_TEAM_ID = ____________`

---

## STEP 1.2 [USER] Slack 앱에서 Distribution 활성화

**목적**: 다른 워크스페이스가 OAuth 로 봇을 설치할 수 있게 한다.

**작업**:
1. https://api.slack.com/apps 접속
2. **Bolty** 앱 클릭
3. 좌측 메뉴 **Manage Distribution** 클릭
4. **Share Your App with Other Workspaces** 섹션에서 4개 체크리스트 항목을 확인:
   - Remove Hard Coded Information ✅
   - Activate Public Distribution
5. 우측 **Activate Public Distribution** 버튼 클릭 → 확인 다이얼로그에서 동의

**검증**: 페이지 상단에 "Distribution Activated" 또는 유사 메시지가 표시.

**주의**: Distribution 활성화는 **앱을 마켓플레이스에 공개하는 것과 다르다**. 단지 OAuth URL 을 통한 다중 설치를 허용할 뿐이다. 마켓플레이스 등록은 별도 신청이 필요.

**막혔을 때**: "Hard coded information" 체크가 막힐 수 있다. Slack은 코드에 토큰이 하드코딩되어 있는지 사용자에게 자가 진단을 시킨다. 우리 코드는 환경변수로 받으므로 통과시킨다.

- [ ] 완료

---

## STEP 1.3 [USER] 앱 자격증명 복사

**목적**: OAuth 흐름과 서명 검증에 필요한 3개 키를 .env 에 등록.

**작업**:
1. 좌측 메뉴 **Basic Information** 클릭
2. **App Credentials** 섹션에서 다음 3가지를 메모장 등에 임시 보관:
   - **Client ID** (예: `1234567890.0987654321`)
   - **Client Secret** — `Show` 클릭 후 복사
   - **Signing Secret** — `Show` 클릭 후 복사
3. 절대 git/슬랙/디스코드 등 외부에 노출하지 않는다. 이 화면 스크린샷도 찍지 말 것.

**검증**: 3개 값을 모두 손에 쥐었다.

- [ ] 완료

---

## STEP 1.4 [USER] .env 파일에 자격증명 추가

**목적**: 코드가 환경변수에서 자격증명을 읽도록 한다.

**작업**:
1. `d:\DEV_slack\bolt-python-ai-chatbot\.env` 파일을 에디터로 열기
2. 기존 줄들 아래에 다음 3줄을 추가 (값은 STEP 1.3 에서 복사한 값으로 치환):
   ```
   SLACK_CLIENT_ID=1234567890.0987654321
   SLACK_CLIENT_SECRET=__여기_값__
   SLACK_SIGNING_SECRET=__여기_값__
   ```
3. 저장
4. .gitignore 확인:
   ```bash
   git check-ignore .env
   ```
   결과로 `.env` 가 출력되어야 한다 (gitignore 되어 있다는 뜻). 안 되면 즉시 사용자가 멈추고 Claude에 알림.

**검증**: 위 명령에서 `.env` 가 출력 + `git status` 에 `.env` 가 표시되지 **않음**.

**막혔을 때**: `.env` 가 git 추적 대상이라면 절대로 STEP 1.5 진행 금지. Claude 에게 ".env 가 git에 추적되고 있어 — 안전하게 빼 줘" 라고 요청.

- [ ] 완료

---

## STEP 1.5 [USER] 임시: Redirect URL 빈칸 등록 준비

**목적**: STEP 3.1 에서 ngrok 으로 redirect URL 을 등록할 예정. 지금은 위치만 확인.

**작업**:
1. https://api.slack.com/apps → Bolty → **OAuth & Permissions** 메뉴 클릭
2. **Redirect URLs** 섹션 위치 확인 (지금은 추가 안 함)

**검증**: Redirect URLs 입력 영역 위치만 확인.

- [ ] 완료

---

# Phase 2 — InstallationStore 보호 설정

## STEP 2.1 [CLAUDE] .gitignore 갱신

**목적**: 토큰이 저장될 디렉터리를 git에서 제외해 유출을 원천 차단.

**작업** (Claude가 수행):
- [.gitignore](.gitignore) 파일에 다음 항목 추가
  ```
  data/installations/
  data/oauth_state/
  ```
- 이미 존재하는 `data/` 패턴이 더 광범위하게 잡고 있다면 그것으로 충분 — 그 경우 변경 불요로 보고

**검증**: `git status` 에 `data/installations/` 또는 `data/oauth_state/` 가 추적 대상으로 보이지 **않음**.

- [ ] 완료

---

## STEP 2.2 [USER] 사용자가 검증

**작업**:
1. 사용자가 직접 다음 명령으로 확인
   ```bash
   git check-ignore -v data/installations/anything
   git check-ignore -v data/oauth_state/anything
   ```
2. 두 명령 모두 `.gitignore` 에서 매치되었다는 출력이 나오면 OK

**검증**: 위 명령 결과가 매칭되어야 함.

- [ ] 완료

---

# Phase 3 — `app.py` 를 Multi-Workspace 모드로 전환

## STEP 3.1 [USER] ngrok 터널 시작 + Redirect URL 등록

**목적**: 외부에서 접근 가능한 OAuth redirect URL 확보.

**작업**:
1. 새 터미널 창에서:
   ```bash
   ngrok http 3000
   ```
2. 출력 화면에 표시되는 `Forwarding` URL 복사 (예: `https://abcd-1234.ngrok-free.app`)
3. 이 URL 뒤에 `/slack/oauth_redirect` 를 붙인 전체 URL 을 만든다:
   - 예: `https://abcd-1234.ngrok-free.app/slack/oauth_redirect`
4. https://api.slack.com/apps → Bolty → **OAuth & Permissions** → **Redirect URLs** → **Add New Redirect URL** → 위 URL 붙여넣기 → **Add** → **Save URLs**
5. ngrok 터미널은 **그대로 열어 둔다** (Phase 7까지)

**검증**: Slack 앱 설정에 redirect URL 이 저장됨, ngrok 터널은 살아 있음.

**주의**: ngrok 무료 플랜은 재시작할 때마다 URL 이 바뀐다. 작업 중 ngrok 을 종료하면 STEP 3.1 을 다시 해야 한다. 작업 시간을 한 번에 몰아서 끝내는 게 좋다.

**막혔을 때**: ngrok URL 이 너무 자주 바뀌어 불편하면 ngrok 유료 플랜의 reserved domain 을 쓰거나 cloudflared 를 사용. 본 단계에서는 무료 플랜으로도 충분.

- [ ] 완료 — ngrok URL: `https://__________.ngrok-free.app`

---

## STEP 3.2 [CLAUDE] `app.py` OAuth + InstallationStore 통합

**목적**: 봇 부팅 시 단일 토큰이 아닌 InstallationStore 기반으로 동작하도록 변경.

**작업** (Claude가 수행):
1. [app.py](app.py) 를 다음과 같이 수정:
   - `token=` 인자 제거
   - `signing_secret`, `installation_store=FileInstallationStore(base_dir="./data/installations")`, `oauth_settings=OAuthSettings(...)` 로 초기화
   - `BOT_SCOPES` 상수를 [manifest.json](manifest.json) 의 `oauth_config.scopes.bot` 와 동일하게 정의 (`files:read`, `reactions:write` 포함)
2. `state_store/` 디렉터리는 이 단계에서는 건드리지 않음 (Phase 5)
3. 변경 후 사용자에게 "STEP 3.3 진행하세요" 라고 보고

**검증**: Claude 가 수정한 코드가 syntax error 없이 import 가능해야 함 (`python -c "import app"` 으로 사용자가 확인).

- [ ] 완료

---

## STEP 3.3 [USER] 봇 부팅 테스트

**목적**: 변경된 `app.py` 가 부팅 단계에서 깨지지 않는지 확인.

**작업**:
1. 기존에 떠 있던 `python app.py` 가 있다면 종료
2. 새 터미널에서:
   ```bash
   python app.py
   ```
3. 콘솔 출력 확인:
   - "Connected" 또는 "Socket Mode" 관련 메시지가 나와야 정상
   - 에러가 나면 메시지를 그대로 Claude 에게 복사해서 보고

**검증**: 부팅 에러 없이 Socket Mode 연결 성공 메시지.

**막혔을 때**: `KeyError`, `AttributeError`, `slack_sdk.errors.SlackApiError` 등 어떤 에러든 즉시 Claude 에게 그대로 붙여넣어 분석 요청.

- [ ] 완료

---

## STEP 3.4 [USER] 기존 워크스페이스에서 동작 확인 (마이그레이션 전 1차 검증)

**목적**: 새 코드 구조에서도 기존 워크스페이스가 여전히 동작하는지 1차 확인. **이 시점에는 아직 OAuth 설치를 안 했기 때문에 동작하지 않는 것이 정상**일 수 있다.

**작업**:
1. 봇이 실행 중인 상태에서 슬랙(`happytestyong.slack.com`)에서 DM "안녕?" 입력
2. 결과 관찰:
   - **응답이 옴** → 의외의 결과. 콘솔 로그를 Claude 에게 보고.
   - **응답이 안 옴 + 콘솔에 `not_authed` / `invalid_auth` / `installation_not_found` 류 에러** → 정상. 이 워크스페이스도 OAuth 로 다시 설치해야 함을 의미. STEP 3.5 로 진행.

**검증**: 콘솔 로그에서 어떤 에러가 났는지 Claude 에게 공유.

- [ ] 완료 — 결과: ____________

---

## STEP 3.5 [USER] 기존 워크스페이스를 OAuth 흐름으로 재설치

**목적**: InstallationStore 에 기존 워크스페이스 토큰을 등록.

**작업**:
1. 브라우저에서 다음 URL 접속:
   ```
   https://<ngrok-id>.ngrok-free.app/slack/install
   ```
   (STEP 3.1 의 ngrok URL + `/slack/install`)
2. ⚠️ 만약 "404 Not Found" 가 나오면 아직 OAuth HTTP endpoint 가 떠 있지 않은 상태. STEP 3.6 을 먼저 본다.
3. Slack 동의 화면이 뜨면 워크스페이스 선택 → **Allow**
4. 성공 페이지가 보이면 설치 완료
5. 탐색기에서 `data/installations/` 폴더를 확인 → 워크스페이스 폴더(예: `T0A5QTAHG76/`)와 그 안에 `bot_latest`, `installer_latest` 등의 파일이 생성되어야 함

**검증**: `data/installations/<team_id>/` 폴더 생성.

- [ ] 완료

---

## STEP 3.6 [USER+CLAUDE] OAuth HTTP endpoint 운영 결정

**목적**: Socket Mode 단독으로는 `/slack/install` HTTP endpoint 가 노출되지 않는다. 두 가지 옵션 중 하나를 선택해야 한다.

**선택지**:

**옵션 A — 별도 OAuth 서버 프로세스 (권장)**:
- `python app.py` (Socket Mode 봇) 와 `python app_oauth.py` (OAuth 설치용 HTTP) 를 두 터미널에서 동시에 실행
- 두 프로세스가 같은 `data/installations/` 를 공유하므로 OAuth 로 설치한 토큰을 봇이 즉시 사용 가능
- 이 방식의 장점: 코드 변경 최소

**옵션 B — `app.py` 안에서 SocketMode + 내장 HTTP 동시 실행**:
- 더 복잡하고 디버깅 어려움. 비권장.

**작업**:
1. 사용자가 옵션 A 로 진행할 것을 결정
2. Claude 에게 "옵션 A 로 가자, [app_oauth.py](app_oauth.py) 를 [app.py](app.py) 와 같은 InstallationStore 를 쓰도록 맞춰 줘" 라고 지시
3. Claude 는 `app_oauth.py` 의 `installation_store` 와 `state_store` base_dir 를 `app.py` 와 동일하게 수정

**검증**: 두 파일이 동일한 `base_dir="./data/installations"` 와 `base_dir="./data/oauth_state"` 를 사용.

- [ ] 완료

---

## STEP 3.7 [USER] OAuth 서버 + 봇 동시 실행

**작업**:
1. **터미널 1**: ngrok (이미 실행 중)
2. **터미널 2**: Socket Mode 봇
   ```bash
   python app.py
   ```
3. **터미널 3**: OAuth HTTP 서버
   ```bash
   python app_oauth.py
   ```
4. 터미널 3 의 출력에서 "Bolt app is running" 또는 "Listening on port 3000" 류 메시지 확인

**검증**: 두 프로세스 모두 정상 부팅.

- [ ] 완료

---

## STEP 3.8 [USER] STEP 3.5 재시도

OAuth 서버가 떠 있는 상태에서 STEP 3.5 의 설치 흐름을 다시 시도. 이번엔 `/slack/install` 이 살아 있어야 한다.

- [ ] 완료 — `data/installations/<TEAM_ID>/` 생성 확인

---

## STEP 3.9 [USER] 기존 워크스페이스 동작 재확인

**작업**:
1. `happytestyong.slack.com` 에서 DM "안녕?" 입력
2. AI 응답이 정상적으로 와야 함

**검증**: 응답 정상.

**막혔을 때**: 응답이 없으면 콘솔 로그(터미널 2)를 Claude 에게 공유.

- [ ] 완료

---

# Phase 4 — 두 번째 워크스페이스 OAuth 설치

## STEP 4.1 [USER] 두 번째 워크스페이스 설치

**작업**:
1. 브라우저에서 두 번째 워크스페이스(`<workspace_b>.slack.com`) 에 로그인되어 있는지 확인
2. 같은 ngrok URL `https://<ngrok-id>.ngrok-free.app/slack/install` 접속
3. 우측 상단의 워크스페이스 선택 드롭다운에서 **워크스페이스 B** 선택
4. 동의 → Allow
5. `data/installations/` 에 두 번째 team_id 폴더가 생성되었는지 확인 (이제 폴더가 두 개여야 함)

**검증**: `data/installations/` 안에 워크스페이스 A, B 두 개의 폴더.

- [ ] 완료 — 워크스페이스 B team_id: `T____________`

---

## STEP 4.2 [USER] 봇을 두 번째 워크스페이스 채널에 초대

**작업**:
1. 워크스페이스 B 에서 STEP 0.4 에서 만들어 둔 `#bolty-test` 채널로 이동
2. 채널에 `/invite @Bolty` 입력 (또는 채널 정보 → Integrations → Add apps)
3. "Bolty added to #bolty-test" 메시지 확인

**검증**: 채널 멤버 목록에 봇 표시.

- [ ] 완료

---

## STEP 4.3 [USER] 두 번째 워크스페이스에서 동작 확인

**작업**:
1. `#bolty-test` 채널에서 "@Bolty 안녕?" 입력
2. AI 응답이 와야 함

**검증**: 응답 정상.

**막혔을 때**: 콘솔 로그를 Claude 에게 공유.

- [ ] 완료

---

# Phase 5 — 사용자 상태 저장소를 team 분리

## STEP 5.1 [CLAUDE] `state_store` 코드 수정

**목적**: `data/{user_id}` → `data/users/{team_id}/{user_id}` 로 분리.

**작업** (Claude가 수행):
1. [state_store/file_state_store.py](state_store/file_state_store.py) 의 `set_state` 와 `unset_state` 시그니처에 `team_id` 추가, 경로를 `{base_dir}/{team_id}/{user_id}` 형식으로 변경, `base_dir` 기본값을 `./data/users` 로 변경
2. [state_store/get_user_state.py](state_store/get_user_state.py) 의 `get_user_state` 시그니처에 `team_id` 추가, 경로 변경
3. [state_store/set_user_state.py](state_store/set_user_state.py) 의 `set_user_state` 시그니처에 `team_id` 추가
4. 호출처 grep:
   ```
   grep -rn "get_user_state\|set_user_state" listeners/ ai/
   ```
5. 발견된 호출처마다 `team_id` 를 함께 전달하도록 수정. team_id 는 우선순위:
   - `context.team_id` (Bolt 가 자동 주입)
   - 없으면 `body["team"]["id"]` 또는 `event["team"]`
6. 변경 후 사용자에게 "STEP 5.2 로 검증해 주세요" 라고 보고

**검증**: Claude 가 변경한 파일 목록을 사용자에게 명시.

- [ ] 완료

---

## STEP 5.2 [USER] 마이그레이션 스크립트 dry-run

**목적**: 기존 사용자 설정 파일을 새 위치로 옮기기 전에 어떤 파일이 옮겨질지 미리 확인.

**작업**:
1. Claude 에게 "마이그레이션 스크립트 `scripts/migrate_user_state.py` 를 dry-run 모드로 만들어 줘. `--apply` 플래그가 없으면 옮기지 않고 옮길 파일 목록만 출력하도록." 라고 지시
2. Claude 가 스크립트를 작성하면 사용자가 실행:
   ```bash
   set LEGACY_TEAM_ID=T0A5QTAHG76
   python scripts/migrate_user_state.py
   ```
3. 출력으로 옮길 파일 목록 확인. 잘못된 파일(예: `installations/` 디렉터리)이 포함되어 있지 않은지 검토.

**검증**: 옮길 파일 목록이 사용자가 예상한 user_id 파일들과 일치.

- [ ] 완료

---

## STEP 5.3 [USER] 마이그레이션 실제 실행

**작업**:
1. dry-run 결과가 OK 면:
   ```bash
   python scripts/migrate_user_state.py --apply
   ```
2. 실행 후 `data/users/<LEGACY_TEAM_ID>/` 폴더에 user_id 파일들이 들어가 있는지 탐색기로 확인
3. 원본 위치(`data/<user_id>`)는 비어 있어야 함

**검증**: 새 위치에 파일 존재 + 원본 위치에서 사라짐.

**롤백**: STEP 0.2 의 백업 zip 을 복원.

- [ ] 완료

---

## STEP 5.4 [USER] 봇 재기동 후 기존 사용자 설정 확인

**작업**:
1. 봇 종료 후 재시작
   ```bash
   python app.py
   ```
2. `happytestyong.slack.com` 에서 슬랙 봇 → App Home 탭 열기
3. 기존에 선택해 둔 provider/model 이 그대로 표시되는지 확인

**검증**: 기존 설정이 살아 있음.

**막혔을 때**: 설정이 비어 보이면 STEP 5.3 의 결과 폴더 구조를 Claude 에게 공유.

- [ ] 완료

---

# Phase 6 — Manifest 동기화 및 재배포

## STEP 6.1 [USER+CLAUDE] manifest 와 코드 scope 비교

**작업**:
1. 사용자가 [manifest.json](manifest.json) 의 `oauth_config.scopes.bot` 목록과 STEP 3.2 에서 정의한 `BOT_SCOPES` 상수를 나란히 비교 요청
2. Claude 가 두 목록의 차이를 표 형태로 출력
3. 누락된 scope 이 있으면 [manifest.json](manifest.json) 에 추가

**검증**: 두 목록이 완전히 일치.

- [ ] 완료

---

## STEP 6.2 [USER] Slack 앱 manifest 업데이트

**작업**:
1. https://api.slack.com/apps → Bolty → **App Manifest** 메뉴
2. 좌측 에디터에 [manifest.json](manifest.json) 의 내용을 그대로 붙여넣기
3. **Save Changes**
4. "Reinstall to Workspace" 안내가 뜨면 클릭 → 양 워크스페이스 모두에 대해 재설치
5. 재설치 후 `data/installations/` 의 토큰 파일 timestamp 가 갱신되었는지 확인

**검증**: 두 워크스페이스 토큰 모두 최신.

- [ ] 완료

---

# Phase 7 — 통합 테스트

## STEP 7.1 [USER] 시나리오 매트릭스 실행

워크스페이스 A, B 양쪽에서 다음을 실행하고 결과를 표에 기록.

| # | 시나리오 | 워크스페이스 A | 워크스페이스 B |
|---|---|---|---|
| 1 | DM 평문 메시지 | ☐ | ☐ |
| 2 | 채널에서 `@봇 질문` | ☐ | ☐ |
| 3 | 채널에 PDF 업로드 | ☐ + ✅ 리액션 | ☐ + ✅ 리액션 |
| 4 | App Home에서 provider 변경 | A의 설정만 변경 | B의 설정만 변경 |
| 5 | 봇 종료 후 재기동 → 다시 1번 | ☐ | ☐ |

**작업**: 각 셀 실행 후 결과를 ☑ 또는 ☒ 로 표기.

**검증**: 모든 셀 ☑.

**막혔을 때**: 실패한 셀의 콘솔 로그 + 슬랙 채널 ID + team_id 를 Claude 에게 공유.

- [ ] 완료

---

## STEP 7.2 [USER] 격리 검증

**목적**: 한 워크스페이스의 설정 변경이 다른 워크스페이스에 영향을 주지 않는지 확인.

**작업**:
1. 워크스페이스 A 에서 App Home → provider 를 OpenAI 로 변경
2. 워크스페이스 B 에서 App Home → provider 가 여전히 Anthropic (또는 B 의 기존 설정) 인지 확인
3. 양쪽 DM 에서 메시지를 보내 응답을 받는다 — 각각 자기 워크스페이스의 provider 로 응답해야 함

**검증**: 설정이 서로 격리됨.

- [ ] 완료

---

## STEP 7.3 [USER] [error.txt](error.txt) 의 원래 시나리오 재현 시도

**목적**: 처음에 보고했던 `channel_not_found` 에러가 multi-workspace 전환 후 사라졌는지 확인.

**작업**:
1. 원래 실패하던 채널(`C0ASM8HPG81`) 이 어느 워크스페이스에 속해 있는지 확인
2. 그 워크스페이스가 OAuth 설치 대상에 포함되어 있고, 봇이 해당 채널 멤버라면 → 메시지 전송 시 정상 응답이 와야 한다
3. 만약 그 워크스페이스가 아직 설치 대상이 아니라면 → 본 전환 범위를 벗어나므로 "아직 설치 안 한 워크스페이스의 채널" 로 분류하고 다음으로 넘어감

**검증**: 적어도 "설치된 모든 워크스페이스의 멤버 채널"에서 `channel_not_found` 가 안 나와야 함.

- [ ] 완료

---

# Phase 8 — 운영 전환 및 문서화

## STEP 8.1 [USER] 변경사항 commit

**작업**:
1. 변경된 파일 목록 확인
   ```bash
   git status
   ```
2. **민감 파일이 포함되지 않았는지 반드시 확인**:
   - `.env` ❌
   - `data/installations/` ❌
   - `data/oauth_state/` ❌
3. 안전한 파일들만 명시적으로 add (와일드카드 add 금지)
4. commit 메시지 작성 — Claude 에게 "현재 변경사항으로 commit 메시지 작성해 줘" 라고 지시 가능

**검증**: `git status` 에서 민감 파일이 staged 안 됨.

- [ ] 완료

---

## STEP 8.2 [USER] PR 생성 또는 main 머지

**작업**:
1. 본인이 main 에 직접 머지할 권한이 있고 이 변경이 작아 보이면 직접 머지
2. 협업자가 있어 리뷰가 필요하면 PR 생성:
   ```bash
   git push -u origin feature/multi-workspace
   gh pr create --title "Multi-workspace 전환" --body "본 PR은 multi-workspace_전체실행계획서.md 에 따른 작업 결과입니다."
   ```

- [ ] 완료

---

## STEP 8.3 [USER] 24시간 모니터링

**작업**:
1. 운영 환경에서 봇을 24시간 운영
2. 콘솔 로그를 주기적으로 확인 — 다음 키워드가 발생하지 않아야 함:
   - `channel_not_found`
   - `not_authed`
   - `invalid_auth`
   - `installation_not_found`
3. 발생하면 그 시점의 로그를 Claude 에게 공유

**검증**: 24시간 동안 위 키워드 0건.

- [ ] 완료

---

## STEP 8.4 [USER+CLAUDE] 회고 및 후속 과제 정리

**작업**:
1. 사용자가 본 문서를 처음부터 끝까지 훑어보며 막혔던 단계, 실제 소요시간, 누락된 단계를 메모
2. Claude 에게 "회고 메모를 바탕으로 본 실행계획서의 개선점을 정리해 줘" 라고 지시
3. 후속 과제(아래 9번 섹션)를 백로그에 등록

- [ ] 완료

---

# 9. 후속 과제 (Out of Scope — 본 작업 후 별도로)

본 계획에 의도적으로 포함하지 않은 항목. 운영 안정화 후 별도 단계로 진행.

| # | 항목 | 우선순위 | 메모 |
|---|---|---|---|
| F1 | Token rotation 활성화 | 중 | `manifest.json` 의 `token_rotation_enabled: true` + refresh 핸들링 |
| F2 | InstallationStore 를 SQL/S3 로 전환 | 낮 | 멀티 인스턴스 운영 시 |
| F3 | `app_uninstalled` / `tokens_revoked` 이벤트 처리 | 중 | 워크스페이스가 봇 제거 시 InstallationStore 정리 |
| F4 | ngrok 의존성 제거 — 정식 도메인 + reverse proxy | 높 | 운영 배포 시 필수 |
| F5 | OAuth 서버와 Socket Mode 봇을 단일 프로세스로 통합 | 낮 | 운영 단순화 |
| F6 | Enterprise Grid 케이스 검증 | 낮 | `org_deploy_enabled: true` 가 이미 켜져 있음, 실제 grid 환경 테스트 필요 |
| F7 | 워크스페이스별 LLM 사용량 모니터링 | 중 | provider API 비용 분리 |
| F8 | 마켓플레이스 등록 신청 | 낮 | 외부 사용자 모집 시 |

---

# 10. 위험 요소 즉석 참조

| 코드 | 위험 | 즉시 해결 |
|---|---|---|
| R1 | `.env` 가 git 에 커밋됨 | git rm --cached .env, 토큰 즉시 rotate |
| R2 | `data/installations/` 가 git 에 커밋됨 | 같은 절차 + 모든 워크스페이스 토큰 rotate |
| R3 | ngrok URL 변경되어 OAuth 깨짐 | STEP 3.1 재실행, Slack 앱 redirect URL 갱신 |
| R4 | manifest 와 코드 scope 불일치 → `missing_scope` | STEP 6.1 재실행, 양쪽 동기화 후 reinstall |
| R5 | 마이그레이션 후 사용자 설정 사라짐 | STEP 0.2 백업 복원, Claude 에게 마이그레이션 스크립트 디버깅 요청 |
| R6 | OAuth 서버 종료된 채로 Socket Mode 만 떠 있음 | 새 워크스페이스 설치 불가, 기존은 동작. 두 프로세스를 항상 함께 실행 |

---

# 11. 완료 정의 (Definition of Done)

본 전환이 "끝났다" 고 말하려면 아래가 모두 ✅ 여야 한다.

- [ ] Phase 0 ~ Phase 8 모든 STEP 의 체크박스 ✅
- [ ] 두 개 이상의 워크스페이스에서 OAuth 설치 성공
- [ ] STEP 7.1 시나리오 매트릭스 전 셀 ☑
- [ ] STEP 7.2 격리 검증 통과
- [ ] STEP 8.3 24시간 모니터링 무사고
- [ ] [error.txt](error.txt) 의 원래 에러 재현 안 됨 (설치된 워크스페이스 한정)
- [ ] `.env`, `data/installations/`, `data/oauth_state/` 모두 git 추적 제외
- [ ] 본 문서가 회고 반영되어 다음 작업자에게 인계 가능

---

# 부록 A — 자주 겪는 에러와 대응

| 에러 메시지 | 원인 | 대응 |
|---|---|---|
| `installation_not_found` | InstallationStore 에 해당 team_id 없음 | OAuth 설치 흐름으로 해당 워크스페이스 재설치 |
| `not_authed` | 토큰 자체가 없거나 비어 있음 | InstallationStore 의 토큰 파일 확인, 재설치 |
| `invalid_auth` | 토큰이 잘못되었거나 만료 | 재설치, 만약 token rotation 설정했다면 refresh 로직 점검 |
| `missing_scope` | 토큰의 scope 가 부족 | `manifest.json` + `BOT_SCOPES` 동기화 후 reinstall |
| `channel_not_found` | 봇이 그 채널의 워크스페이스에 설치 안 됐거나 채널 멤버가 아님 | 해당 워크스페이스 OAuth 설치 + 채널 invite |
| `UnboundLocalError: waiting_message` | listener 의 except 블록에서 미초기화 변수 접근 | listener 에서 `waiting_message = None` 으로 사전 초기화 |

---

# 부록 B — 진행 상황 한 줄 요약 템플릿

각 작업 세션 종료 시 아래 템플릿을 채워 회고 자료로 사용.

```
[YYYY-MM-DD HH:MM] Phase __ STEP __ 까지 완료
- 막힌 곳: ___________
- 다음 작업: ___________
- 환경 상태: 봇 (실행/중지), OAuth 서버 (실행/중지), ngrok URL: ___________
```

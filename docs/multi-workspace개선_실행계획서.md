# Multi-Workspace 개선 실행계획서

## 0. 문서 목적

현재 [bolt-python-ai-chatbot](.) 봇은 단일 워크스페이스에 종속된 형태로 운영 중이다. 본 문서는 이를 **여러 워크스페이스에 동시 설치/사용 가능한 multi-workspace(Distribution) 앱**으로 전환하기 위한 단계별 실행계획을 정의한다.

---

## 1. 현재 상태 진단

### 1.1 무엇이 single-workspace 모드의 원인인가

| 구성 요소 | 현재 상태 | Multi-workspace 호환 여부 |
|---|---|---|
| [app.py](app.py) | 환경변수 `SLACK_BOT_TOKEN` 하나로 `App` 초기화 후 Socket Mode로 실행 | ❌ 토큰 1개에 묶여 있음 |
| [app_oauth.py](app_oauth.py) | OAuth 흐름과 `FileInstallationStore` 가 이미 작성되어 있음 | ⚠️ 존재하지만 사용되지 않음, 일부 설정 보강 필요 |
| [state_store/file_state_store.py](state_store/file_state_store.py) | `./data/{user_id}` 경로에 사용자 설정 저장 | ❌ user_id가 워크스페이스 간에 충돌할 수 있음 |
| [state_store/get_user_state.py](state_store/get_user_state.py) | `./data/{user_id}` 단일 키로 조회 | ❌ 동일 |
| [manifest.json](manifest.json) | `socket_mode_enabled: true`, scope은 이미 multi-workspace에 필요한 항목 다수 포함 | ⚠️ Socket Mode와 OAuth 병행 가능하지만 distribution 활성화 필요 |
| [listeners/](listeners/) 핸들러 전반 | `client.token`을 사용하지 않고 Bolt가 주입하는 `client`/`say`를 사용 | ✅ 대부분 호환 — 일부 점검 필요 |
| `.env` | `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` 위주 | ❌ `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET` 추가 필요 |

### 1.2 핵심 문제 요약

1. **토큰 단일 보유**: 봇이 자신의 설치 워크스페이스 토큰 1개만 가지고 동작한다. 다른 워크스페이스에서 들어온 이벤트의 채널/사용자에 대해서는 `channel_not_found`로 거절된다(이는 [error.txt](error.txt)에서 확인된 실제 증상).
2. **InstallationStore 미사용**: OAuth 코드는 `app_oauth.py`에 있지만, 실제 운영은 `app.py`(non-OAuth)로 돌고 있다.
3. **사용자 상태 저장소가 team을 모름**: `./data/{user_id}` 단일 키 구조로, 같은 user_id가 다른 워크스페이스에 존재하면 데이터가 섞인다.
4. **Distribution 미활성화**: Slack 앱 설정에서 "Public Distribution"이 켜져 있지 않으면, 다른 워크스페이스에서 OAuth 설치 자체가 불가능하다.

---

## 2. 목표

1. **하나의 봇 인스턴스가 여러 워크스페이스의 설치/이벤트를 정상 처리**할 수 있어야 한다.
2. 워크스페이스마다 **별도의 bot token**으로 API 호출을 자동 라우팅한다.
3. 사용자별 provider/model 설정이 **(team_id, user_id) 조합으로 격리**된다.
4. 기존 single-workspace 사용자(`SLACK_BOT_TOKEN`)도 마이그레이션 경로가 있다.
5. **롤백 가능**한 단계로 진행한다 — 각 단계에서 문제 발생 시 이전 단계로 되돌릴 수 있어야 한다.

---

## 3. 아키텍처 결정

### 3.1 실행 모드: Socket Mode + OAuth (권장)

| 옵션 | 장점 | 단점 |
|---|---|---|
| **A. Socket Mode + OAuth** ← 권장 | 외부 공개 endpoint 불필요, 방화벽 친화적, 개발/테스트에 적합 | OAuth redirect URL은 여전히 외부에서 접근 가능해야 함 |
| B. HTTP Mode + OAuth (Events API) | 표준 운영 환경에 적합, 확장성 ↑ | 공개 HTTPS 도메인 필요, TLS 인증서 필요 |

권장은 **A**다. 이유:
- 현재 코드가 이미 Socket Mode를 사용 중이라 변경 폭이 작다.
- 다만 **OAuth redirect_uri는 공개 가능한 URL**이 필요하므로, 개발 환경에서는 `ngrok` 같은 터널을 임시로 사용한다.
- 운영으로 갈 때는 `redirect_uri`만 진짜 도메인으로 바꾸면 된다.

### 3.2 InstallationStore 선택

| 옵션 | 적합한 환경 |
|---|---|
| `FileInstallationStore` | 단일 인스턴스, 디스크 영속 가능, 소규모 운영 |
| `AmazonS3InstallationStore` | 클라우드, 멀티 인스턴스 |
| `SQLAlchemyInstallationStore` | RDB 사용 환경, 트랜잭션 필요 |

이번 전환에서는 **`FileInstallationStore`** 로 시작한다 (이미 [app_oauth.py](app_oauth.py)에 작성되어 있고, 가장 변경 폭이 작다). 향후 운영 부하가 커지면 SQL 또는 S3 스토어로 교체.

### 3.3 사용자 상태 저장 구조 변경

**현재**:
```
data/{user_id}
```

**변경 후**:
```
data/{team_id}/{user_id}
```

team_id 기반 디렉터리 분리로 워크스페이스 간 user_id 충돌을 원천 차단한다. 마이그레이션 스크립트로 기존 데이터를 (가능한 경우) 새 구조로 옮긴다.

### 3.4 토큰 라우팅 흐름

```
이벤트 도착
   │
   ├─ event["team"] (또는 enterprise_id) 추출
   │
   ▼
InstallationStore.find_installation(team_id=...)
   │
   ▼
bot_token 획득
   │
   ▼
WebClient(token=bot_token) 으로 API 호출
```

이 흐름은 **slack_bolt가 자동으로 처리**한다 — `App`을 `installation_store`와 함께 초기화하면, listener에 주입되는 `client`/`say`/`context` 가 자동으로 해당 워크스페이스의 토큰을 사용한다. 따라서 **listener 코드는 거의 변경할 필요가 없다**.

---

## 4. 단계별 실행 계획

### Phase 0 — 사전 준비 (0.5d)

**목표**: 작업 안전망 구축.

**작업**:
1. 작업 브랜치 생성: `git checkout -b feature/multi-workspace`
2. 기존 `data/` 디렉터리 백업: `data_backup_YYYYMMDD.zip` 으로 압축 보관
3. 현재 동작하는 single-workspace 환경에서 스모크 테스트 1회 실행 → 정상 동작 확인 후 결과 기록 (회귀 비교 기준)
4. 작업 중 사용할 환경변수 목록 정리:
   - 기존: `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`
   - 추가 필요: `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET`

**완료 조건**: 브랜치 생성 + 백업 + 회귀 기준 기록 완료.

---

### Phase 1 — Slack App 설정 변경 (0.5d)

**목표**: Slack 측에서 distribution을 활성화하고 OAuth 자격증명을 발급.

**작업**:
1. https://api.slack.com/apps → 해당 앱 선택
2. **Manage Distribution** 메뉴 → "Activate Public Distribution" 활성화
   - ⚠️ 활성화 시 Slack은 앱 마켓플레이스 등록과는 별개로 "OAuth 기반 다중 설치"를 허용한다. 마켓플레이스 노출은 별도 신청.
3. **Basic Information** → **App Credentials** 섹션에서 다음 값을 복사:
   - Client ID → `SLACK_CLIENT_ID`
   - Client Secret → `SLACK_CLIENT_SECRET`
   - Signing Secret → `SLACK_SIGNING_SECRET`
4. **OAuth & Permissions** → **Redirect URLs** 에 다음 추가:
   - 개발: `https://<ngrok-id>.ngrok.io/slack/oauth_redirect`
   - 운영: `https://<도메인>/slack/oauth_redirect`
5. `.env` 파일에 위 3개 환경변수를 추가하고 절대 git에 commit하지 않는다 (`.gitignore` 확인).
6. **Socket Mode** 가 켜져 있는지 확인 ([manifest.json:104](manifest.json#L104) 에 이미 `socket_mode_enabled: true`).

**완료 조건**: distribution 활성화 + 3개 자격증명 .env 등록 + redirect URL 등록.

**롤백**: distribution은 비활성화 가능. 자격증명은 무효화(rotate) 가능.

---

### Phase 2 — `app.py` 를 OAuth + Socket Mode 통합으로 전환 (1.0d)

**목표**: 봇 부팅 시 InstallationStore가 작동하도록 만든다.

**현재 [app.py](app.py) 의 핵심 코드**:
```python
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN")).start()
```

**변경 후**:
```python
import os
import logging
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.oauth.installation_store import FileInstallationStore
from slack_sdk.oauth.state_store import FileOAuthStateStore

from listeners import register_listeners

load_dotenv()
logging.basicConfig(level=logging.DEBUG)

# 모든 워크스페이스에 대해 동일한 권한 집합을 요청.
# manifest.json의 oauth_config.scopes.bot 와 동기화해야 한다.
BOT_SCOPES = [
    "app_mentions:read",
    "channels:history", "channels:read",
    "chat:write", "chat:write.public",
    "commands",
    "files:read",        # 첨부파일 다운로드용 (파일처리_수정사항.md 참조)
    "groups:history", "groups:read",
    "im:history", "im:read", "im:write",
    "mpim:history", "mpim:read", "mpim:write",
    "reactions:write",   # 다운로드 결과 리액션용
    "users:read",
]

app = App(
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
    installation_store=FileInstallationStore(base_dir="./data/installations"),
    oauth_settings=OAuthSettings(
        client_id=os.environ["SLACK_CLIENT_ID"],
        client_secret=os.environ["SLACK_CLIENT_SECRET"],
        scopes=BOT_SCOPES,
        install_path="/slack/install",
        redirect_uri_path="/slack/oauth_redirect",
        state_store=FileOAuthStateStore(
            expiration_seconds=600, base_dir="./data/oauth_state"
        ),
    ),
)

register_listeners(app)

if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
```

**핵심 포인트**:
- `token=` 인자를 제거하고 `installation_store=` 로 대체. 이렇게 하면 Bolt가 이벤트마다 team_id로 설치 정보를 조회한다.
- `signing_secret`은 Socket Mode에서도 OAuth 검증에 필요.
- BOT_SCOPES는 [manifest.json](manifest.json) 의 `oauth_config.scopes.bot` 와 **동기화**되어야 한다. 둘 중 하나가 누락되면 설치 또는 동작 시 권한 오류가 난다.
- `install_path` / `redirect_uri_path` 는 OAuth 설치 흐름용 HTTP endpoint 다. Socket Mode가 켜져 있어도 이 endpoint들은 별도로 떠야 하므로 **HTTP listener도 함께 띄울지**를 결정해야 한다 (다음 단계 참조).

**완료 조건**: `python app.py` 실행 시 부팅 에러 없음, Socket Mode 연결 성공, 기존 워크스페이스 동작 유지(아래 마이그레이션 단계 후).

**롤백**: 변경 전 `app.py`로 복원. `installation_store/` 디렉터리는 그대로 두어도 무해.

---

### Phase 3 — OAuth 설치 endpoint 노출 (0.5d)

**목표**: 새 워크스페이스가 봇을 설치할 수 있는 URL을 제공.

Socket Mode 단독으로는 `/slack/install`, `/slack/oauth_redirect` HTTP endpoint가 노출되지 않는다. 두 가지 옵션:

#### 옵션 A — 별도 OAuth 서버 프로세스 (권장)

기존 [app_oauth.py](app_oauth.py) 를 살려서 **OAuth 전용 HTTP 서버**로 띄운다. Socket Mode 봇 ([app.py](app.py))과 **같은 InstallationStore**를 공유하므로, OAuth 서버에서 설치된 토큰은 Socket Mode 봇이 즉시 사용 가능하다.

```bash
# 터미널 1: Socket Mode 봇
python app.py

# 터미널 2: OAuth 설치용 HTTP 서버
python app_oauth.py
```

`app_oauth.py` 에서도 동일한 `installation_store=FileInstallationStore(base_dir="./data/installations")` 를 사용하도록 일치시킨다.

#### 옵션 B — Socket Mode + 내장 HTTP

`SocketModeHandler` 와 별개로 같은 프로세스에 작은 HTTP 서버(예: `flask`/`fastapi`)를 띄워 install 핸들러를 노출. 구현 복잡도가 올라가므로 비권장.

**작업**:
1. [app_oauth.py](app_oauth.py) 의 `installation_store` 와 `state_store` base_dir 를 [app.py](app.py)와 동일하게 맞춤
2. 개발 환경에서 `ngrok http 3000` 으로 터널 생성
3. ngrok URL 을 Slack 앱 설정의 Redirect URLs 에 등록 (Phase 1 작업의 연장)
4. 브라우저로 `https://<ngrok>/slack/install` 접속 → Slack 동의 화면 → 설치 완료 → `data/installations/` 아래에 새 토큰 파일 생성 확인

**완료 조건**: 새 워크스페이스 1곳을 OAuth 흐름으로 설치 성공, `data/installations/` 에 파일 생성 확인.

**롤백**: `data/installations/<team_id>` 디렉터리 삭제 시 해당 워크스페이스 재설치 필요.

---

### Phase 4 — 사용자 상태 저장소 team 분리 (1.0d)

**목표**: `./data/{user_id}` → `./data/users/{team_id}/{user_id}` 로 변경.

#### 4.1 `FileStateStore` 시그니처 변경

[state_store/file_state_store.py](state_store/file_state_store.py) 를 다음과 같이 수정:

```python
class FileStateStore(UserStateStore):
    def __init__(self, *, base_dir: str = "./data/users", logger=...):
        self.base_dir = base_dir
        self.logger = logger

    def set_state(self, team_id: str, user_identity: UserIdentity):
        user_id = user_identity["user_id"]
        team_dir = Path(self.base_dir) / team_id
        team_dir.mkdir(parents=True, exist_ok=True)
        filepath = team_dir / user_id
        with open(filepath, "w") as f:
            f.write(json.dumps(user_identity))
```

#### 4.2 `get_user_state` / `set_user_state` 시그니처 변경

```python
def get_user_state(team_id: str, user_id: str, is_app_home: bool):
    filepath = f"./data/users/{team_id}/{user_id}"
    ...

def set_user_state(team_id: str, user_id: str, provider_name: str, model_name: str):
    ...
```

#### 4.3 호출처 일괄 수정

`state_store.set_user_state` 와 `state_store.get_user_state` 를 호출하는 모든 곳을 찾아 `team_id`를 함께 넘기도록 변경. 호출처는 다음을 통해 찾는다:

```bash
# 코드 검색
grep -rn "get_user_state\|set_user_state" listeners/ ai/
```

각 listener에서 team_id 는 다음 중 하나로 얻을 수 있다:
- `context.team_id` (Bolt가 자동 주입)
- `body["team"]["id"]` (이벤트/액션 페이로드)
- `event.get("team")` (message 이벤트)

**우선순위**: `context.team_id` 를 우선 사용 (Bolt가 정규화해 주는 값).

#### 4.4 마이그레이션 스크립트

기존 `data/{user_id}` 파일을 새 구조로 옮기는 일회성 스크립트 작성:

```python
# scripts/migrate_user_state.py
import os, shutil
from pathlib import Path

LEGACY_TEAM_ID = os.environ.get("LEGACY_TEAM_ID")  # 기존 운영 워크스페이스 ID
src = Path("./data")
dst = Path(f"./data/users/{LEGACY_TEAM_ID}")
dst.mkdir(parents=True, exist_ok=True)

for f in src.iterdir():
    # 디렉터리(installations/users/oauth_state)는 건너뜀
    if f.is_file() and f.name.startswith("U"):  # Slack user_id 패턴
        shutil.move(str(f), str(dst / f.name))
        print(f"moved {f.name}")
```

⚠️ `LEGACY_TEAM_ID` 는 `Phase 1` 에서 확인한 기존 워크스페이스의 team_id 를 사용. 모르면 Slack 워크스페이스 admin 화면에서 확인.

**완료 조건**:
- 모든 호출처가 team_id를 넘김
- 마이그레이션 스크립트 1회 실행 후 기존 사용자가 App Home에서 자기 설정을 그대로 볼 수 있음

**롤백**: `data_backup_YYYYMMDD.zip` 을 `data/` 에 다시 풀면 원복 가능. 코드 변경은 git revert.

---

### Phase 5 — Listener 코드 점검 (0.5d)

**목표**: 리스너가 토큰을 직접 참조하지 않고, Bolt가 주입하는 `client`/`say` 만 사용하는지 확인.

**점검 대상**:
- [listeners/events/app_messaged.py](listeners/events/app_messaged.py) — `client.token` 사용 여부 확인
- [listeners/events/app_mentioned.py](listeners/events/app_mentioned.py)
- [listeners/events/app_home_opened.py](listeners/events/app_home_opened.py)
- [listeners/commands/](listeners/commands/) 전체
- [listeners/actions/](listeners/actions/) 전체

**확인 방법**:
```bash
grep -rn "SLACK_BOT_TOKEN\|client\.token\|os\.environ" listeners/ ai/
```

발견된 곳마다:
- `SLACK_BOT_TOKEN` 직접 참조 → **금지**, Bolt 주입 `client` 사용
- `client.token` 참조 → 워크스페이스별 토큰을 동적으로 받는 거라면 OK, 다만 캐싱하면 안 됨
- `os.environ.get("SLACK_*")` → 부팅 시 1회만 사용해야 하며 listener 안에서 호출 금지

**특별 주의: 파일 다운로드 헬퍼**

[app_messaged.py](listeners/events/app_messaged.py) 의 `_download_slack_file` 는 `client.token` 을 인자로 받는다. 이 부분은 Bolt가 주입한 `client` 의 토큰을 그대로 쓰므로 **multi-workspace 환경에서도 자동으로 올바른 토큰**이 전달된다. 단, 호출부에서 `token = client.token` 으로 추출 후 다른 함수에 넘길 때, 그 함수가 비동기 큐에 들어가 나중에 실행되면 토큰이 stale 될 수 있다 — 현재 코드는 동기 처리이므로 문제 없음.

**완료 조건**: 토큰 직접 참조 0건. 모든 핸들러가 Bolt 주입 객체만 사용.

**롤백**: 코드 변경분만 revert.

---

### Phase 6 — Manifest 동기화 및 재배포 (0.25d)

**목표**: [manifest.json](manifest.json) 과 코드의 scope/feature 가 일치하는지 검증.

**작업**:
1. Phase 2에서 정의한 `BOT_SCOPES` 와 [manifest.json:29-46](manifest.json#L29-L46) 의 `oauth_config.scopes.bot` 를 비교
2. 누락된 scope 추가:
   - `files:read` (파일 다운로드 — [파일처리_수정사항.md](파일처리_수정사항.md) 참조)
   - `reactions:write` (성공/실패 리액션)
3. Slack App 설정 페이지에서 manifest 를 import/update
4. **Reinstall to Workspace** 클릭 (기존 워크스페이스용)
5. 새 워크스페이스는 Phase 3 의 OAuth 흐름으로 설치

**완료 조건**: manifest 의 scope, 코드의 BOT_SCOPES, 실제 발급된 토큰의 scope 3자가 일치.

**롤백**: manifest 의 이전 버전으로 복원 후 재설치.

---

### Phase 7 — 통합 테스트 (1.0d)

**목표**: 두 개 이상의 실제 워크스페이스에서 봇이 독립적으로 동작함을 검증.

#### 7.1 테스트 환경

- 워크스페이스 A: 기존 운영 워크스페이스 (마이그레이션 후)
- 워크스페이스 B: 신규 OAuth 설치 워크스페이스

#### 7.2 시나리오 매트릭스

| # | 시나리오 | A 결과 | B 결과 | 통과 조건 |
|---|---|---|---|---|
| 1 | DM에 평문 메시지 | AI 응답 | AI 응답 | 양쪽 정상 |
| 2 | 채널에 `@봇 질문` | AI 응답 | AI 응답 | 양쪽 정상 |
| 3 | 채널에 파일 업로드 | `download/`에 저장 + ✅ 리액션 | 동일 | 양쪽 정상 |
| 4 | App Home에서 provider 변경 | A의 설정만 변경 | B의 설정만 변경 | 서로 영향 없음 |
| 5 | 같은 user_id가 두 워크스페이스에 있는 가상 시나리오 | A 데이터 분리 | B 데이터 분리 | `data/users/<teamA>/<u>` 와 `data/users/<teamB>/<u>` 가 별개 |
| 6 | A에서 봇을 채널에서 제거 후 메시지 | 무응답 | 영향 없음 | 격리 확인 |
| 7 | B를 OAuth로 새로 설치 후 즉시 메시지 | — | 정상 응답 | InstallationStore 즉시 반영 |
| 8 | 봇 재기동 후 양쪽 워크스페이스 다시 테스트 | 정상 | 정상 | 영속성 확인 |

#### 7.3 회귀 테스트

[파일처리_수정사항.md](파일처리_수정사항.md) 의 테스트 체크리스트 전체를 양쪽 워크스페이스에서 실행.

**완료 조건**: 8개 시나리오 모두 통과 + 회귀 체크리스트 통과.

**롤백**: Phase 별로 단계 롤백. 가장 보수적인 롤백은 작업 브랜치 폐기.

---

### Phase 8 — 운영 전환 및 모니터링 (0.5d)

**목표**: 변경된 봇을 운영 환경에 배포하고 안정성을 모니터링.

**작업**:
1. `feature/multi-workspace` → `main` 머지 PR 생성
2. PR 본문에 본 실행계획서 링크와 시나리오 결과 첨부
3. 머지 후 운영 환경 재기동
4. 최소 24시간 로그 모니터링:
   - `channel_not_found` 발생 빈도 (목표: 0)
   - `not_authed` / `invalid_auth` 발생 빈도 (목표: 0)
   - InstallationStore I/O 에러 (목표: 0)
5. 발견된 이슈를 별도 후속 티켓으로 정리

**완료 조건**: 24시간 이상 무사고 운영.

**롤백**: `git revert` 후 재배포. `data/installations/` 와 `data/users/` 는 그대로 둠.

---

## 5. 위험 요소 및 완화 방안

| # | 위험 | 영향 | 완화 |
|---|---|---|---|
| R1 | OAuth 설치 흐름의 redirect_uri 오타로 설치 실패 | 신규 워크스페이스 설치 불가 | Phase 1에서 ngrok URL 등록 직후 실제 설치 1회로 검증 |
| R2 | manifest와 코드의 scope 불일치 | 일부 API 호출 실패 (`missing_scope`) | Phase 6에서 양쪽 동기화 + 자동 비교 스크립트(선택) |
| R3 | 마이그레이션 스크립트로 기존 사용자 데이터 손실 | 사용자 provider 설정 초기화 | Phase 0의 백업 + dry-run 모드 |
| R4 | InstallationStore의 디스크 경로가 git에 commit됨 | 토큰 유출 (심각) | `.gitignore` 에 `data/installations/`, `data/oauth_state/` 추가 후 Phase 2 시작 전 확인 |
| R5 | OAuth 흐름이 외부 공개 endpoint 필요 | 폐쇄망에서 설치 불가 | 운영 도메인 사전 확보 또는 ngrok 영구 도메인 사용 |
| R6 | 토큰 rotation 미설정 | 토큰 만료 시 일괄 장애 | 본 단계에서는 미적용. 운영 안정화 후 별도 단계로 `token_rotation_enabled: true` + rotation 핸들링 |
| R7 | Bolt가 enterprise grid 환경에서 enterprise_id 를 우선 사용 | enterprise 워크스페이스에서 team_id 키가 안 맞음 | InstallationStore 가 enterprise 케이스를 자동 처리하므로 코드 변경 불요. 단, 4.2의 `team_id` 추출은 `context.enterprise_id or context.team_id` 패턴 권장 |

---

## 6. 변경 파일 목록 (요약)

| 파일 | 변경 유형 | 비고 |
|---|---|---|
| [app.py](app.py) | 수정 | OAuth + InstallationStore 로 전환 |
| [app_oauth.py](app_oauth.py) | 수정 | base_dir 일치, scope 동기화 |
| [state_store/file_state_store.py](state_store/file_state_store.py) | 수정 | team_id 분리 |
| [state_store/get_user_state.py](state_store/get_user_state.py) | 수정 | team_id 인자 추가 |
| [state_store/set_user_state.py](state_store/set_user_state.py) | 수정 | team_id 인자 추가 |
| listeners/**/*.py (호출처) | 수정 | get/set_user_state 호출 시 team_id 전달 |
| [manifest.json](manifest.json) | 수정 | `files:read`, `reactions:write` 추가 (이미 있으면 skip) |
| `.env` | 수정 | `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET` 추가 |
| `.gitignore` | 수정 | `data/installations/`, `data/oauth_state/` 추가 |
| `scripts/migrate_user_state.py` | 신규 | 1회용 마이그레이션 |

---

## 7. 일정 (Best/Expected/Worst)

> 본 추정은 단일 개발자 기준이며, 슬랙 앱 설정 권한과 ngrok 환경이 준비되어 있다고 가정한다.

| Phase | Best | Expected | Worst |
|---|---|---|---|
| 0. 사전 준비 | 0.25d | 0.5d | 1d |
| 1. Slack 앱 설정 | 0.25d | 0.5d | 1d |
| 2. app.py OAuth 통합 | 0.5d | 1d | 2d |
| 3. OAuth endpoint 노출 | 0.25d | 0.5d | 1d |
| 4. 사용자 상태 분리 | 0.5d | 1d | 2d |
| 5. Listener 점검 | 0.25d | 0.5d | 1d |
| 6. Manifest 동기화 | 0.1d | 0.25d | 0.5d |
| 7. 통합 테스트 | 0.5d | 1d | 2d |
| 8. 운영 전환 | 0.25d | 0.5d | 1d |
| **합계** | **2.85d** | **5.75d** | **11.5d** |

---

## 8. 완료 정의 (Definition of Done)

본 전환은 아래 조건이 모두 충족되어야 완료로 본다.

- [ ] 두 개 이상의 워크스페이스에서 OAuth 설치 성공
- [ ] 양 워크스페이스에서 DM, 멘션, 파일 업로드 시나리오 정상 동작
- [ ] 한쪽 워크스페이스에서의 사용자 설정 변경이 다른 쪽에 영향 없음
- [ ] 봇 재기동 후에도 모든 워크스페이스 토큰과 사용자 설정이 유지됨
- [ ] [error.txt](error.txt) 에서 보고된 `channel_not_found` 가 더 이상 발생하지 않음 (해당 채널에 봇이 설치된 워크스페이스 한정)
- [ ] `data/installations/` 와 `data/oauth_state/` 가 `.gitignore` 에 등록되어 git 추적에서 제외
- [ ] 24시간 운영 모니터링 후 신규 장애 0건
- [ ] 본 문서의 모든 Phase 에 ✅ 표시

---

## 9. 후속 과제 (Out of Scope)

본 계획에 포함되지 않은, 향후 별도로 진행할 작업:

1. **Token Rotation 적용** — `token_rotation_enabled: true` + refresh token 핸들링
2. **InstallationStore 를 SQL/S3 로 전환** — 멀티 인스턴스 운영 시
3. **앱 마켓플레이스 등록** — Slack 마켓플레이스 심사 신청
4. **워크스페이스별 사용량/요금 분리** — 각 워크스페이스의 LLM API 사용량 추적
5. **Enterprise Grid 정식 지원 검증** — `org_deploy_enabled: true` 가 [manifest.json:103](manifest.json#L103) 에 이미 켜져 있으므로 enterprise grid 케이스 통합 테스트
6. **Uninstall 흐름 처리** — `app_uninstalled` / `tokens_revoked` 이벤트로 InstallationStore 정리

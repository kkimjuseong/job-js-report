# 풀스택 채용 공고 데일리 브리핑

매일 오전 7시(KST) 한국 채용 사이트에서 **2~3년차 풀스택(백엔드·프론트엔드·모바일) 개발자용 공고**를 모아
한국어로 정리한 뒤, 카카오톡 "나에게 보내기"로 전송하는 자동화 루틴입니다.

이 레포는 [Claude Code 루틴(Routines)](https://code.claude.com/docs/en/routines)으로
스케줄 실행되도록 설계되어 있습니다. 아래는 **레포를 Claude 루틴에 등록하는 전체 과정**입니다.

---

## 0. 구성 파일

| 파일 | 역할 |
| --- | --- |
| `CLAUDE.md` | 루틴이 매번 읽는 작업 지침서(대상 직무·경력 기준·출력 형식·전송 규칙) |
| `collect.py` | 원티드/사람인/잡코리아에서 분야별 키워드로 공고 수집 → 필터·분야별 쿼터 → `digest.txt` 생성 (`--send` 시 전송까지) |
| `send_kakao.py` | 카카오톡 "나에게 보내기"로 다이제스트 전송(1000자 자동 분할) |
| `requirements.txt` | 의존성(`requests`) |
| `.env.example` | 필요한 환경변수 목록(값은 비어 있음) |

---

## 1. 사전 준비

### 1-1. 요구 사항
- **Claude Code on the web** 사용 가능한 플랜(Pro / Max / Team / Enterprise)
- GitHub 계정 연결([web 온보딩](https://code.claude.com/docs/en/web-quickstart)에서 Claude GitHub App 인증, 또는 터미널에서 `/web-setup`)

### 1-2. 카카오 토큰 발급
루틴은 카카오 시크릿 3개를 **환경변수**로 받아 동작합니다. (코드에 하드코딩하지 않습니다.)

| 환경변수 | 설명 |
| --- | --- |
| `KAKAO_REST_KEY` | 카카오 앱 REST API 키 |
| `KAKAO_CLIENT_SECRET` | Client Secret (앱에 활성화돼 있으면 필수) |
| `KAKAO_REFRESH_TOKEN` | 최초 1회 발급받은 refresh token |

발급 순서:
1. [카카오 개발자 콘솔](https://developers.kakao.com)에서 애플리케이션 생성
2. **앱 키 → REST API 키** 복사 → `KAKAO_REST_KEY`
3. **카카오 로그인** 활성화 → 동의 항목에서 **"카카오톡 메시지 전송(talk_message)"** 권한 ON
4. **보안 → Client Secret** 발급(사용 ON) → `KAKAO_CLIENT_SECRET`
5. OAuth 인가 코드 → 토큰 교환으로 **refresh token** 1회 발급 → `KAKAO_REFRESH_TOKEN`
   - 인가: `https://kauth.kakao.com/oauth/authorize?client_id={REST_KEY}&redirect_uri={REDIRECT}&response_type=code&scope=talk_message`
   - 받은 `code`로 `https://kauth.kakao.com/oauth/token` 에 POST → 응답의 `refresh_token` 저장

> access token은 `send_kakao.py`가 refresh token으로 매번 자동 발급하므로 저장할 필요 없습니다.

---

## 2. 레포를 GitHub에 푸시

루틴은 매 실행 때 GitHub에서 레포를 새로 clone 합니다. 로컬 작업본
(`C:\workspace\claude\fullstack-job-report`)을 GitHub에 올려 두세요.

```bash
git remote -v        # origin이 GitHub 레포를 가리키는지 확인
git push origin main
```

> ⚠️ 시크릿은 **절대 커밋하지 않습니다.** `.env` 는 `.gitignore`에 포함돼 있고,
> 실제 값은 다음 단계(클라우드 환경변수)에만 넣습니다.

---

## 3. 클라우드 환경(Environment) 만들기

[claude.ai/code](https://claude.ai/code)에서 환경 셀렉터를 열고 **Add environment** →
아래 값으로 설정합니다.

### 3-1. 환경변수 (Environment variables)
`.env` 형식으로 한 줄에 하나씩, **따옴표 없이** 입력합니다.

```
KAKAO_REST_KEY=발급받은_REST_키
KAKAO_CLIENT_SECRET=발급받은_client_secret
KAKAO_REFRESH_TOKEN=발급받은_refresh_token
```

### 3-2. 네트워크 접근 (Network access)
채용 사이트와 카카오 API는 기본 **Trusted** 허용 목록에 없으므로 **Custom**으로 지정하고
아래 도메인을 **Allowed domains**에 추가합니다.

```
www.wanted.co.kr
www.saramin.co.kr
www.jobkorea.co.kr
career.rememberapp.co.kr
kauth.kakao.com
kapi.kakao.com
```

- **"Also include default list of common package managers"** 체크 (pip로 `requests` 설치 시 PyPI 접근 필요)

### 3-3. 셋업 스크립트 (Setup script) — 선택
의존성을 미리 설치해 두면 실행이 빨라집니다.

```bash
#!/bin/bash
pip install -r requirements.txt || true
```

> 생략해도 루틴 프롬프트에서 `pip install -r requirements.txt`를 먼저 실행하면 됩니다.

---

## 4. 루틴(Routine) 등록 — 매일 오전 7시

### 방법 A. 웹 UI
1. [claude.ai/code/routines](https://claude.ai/code/routines) → **New routine**
2. **이름**: `풀스택 채용 공고 데일리 브리핑`
3. **프롬프트(Instructions)**: 아래 내용 입력
   ```
   이 레포의 CLAUDE.md 지침을 그대로 수행한다.
   2~3년차 풀스택(백엔드·프론트·모바일) 개발자용 한국 채용 공고를 수집·정리해 한국어 다이제스트를 만들고,
   카카오톡 "나에게 보내기"로 전송한다.
   실행: pip install -r requirements.txt 후 `python collect.py --send` 를 실행한다.
   공고를 못 찾으면 개수를 줄이되, 빈 브리핑은 보내지 않는다.
   ```
4. **Repositories**: 이 레포 선택
5. **Environment**: 3단계에서 만든 환경 선택
6. **Select a trigger → Schedule**: `Daily`, 시간 `07:00` (입력한 로컬 타임존 기준 → KST 계정이면 그대로 7시)
7. **Connectors**: 불필요한 커넥터는 제거(이 루틴은 커넥터 불필요)
8. **Create**

### 방법 B. CLI
터미널에서:
```bash
/schedule daily 풀스택 채용 공고 브리핑 at 7am
```
Claude가 레포·환경·프롬프트를 대화형으로 물어본 뒤 저장합니다.

> ⏰ 스케줄 최소 간격은 1시간이며, 실행은 stagger로 인해 예정 시각보다 몇 분 늦게 시작될 수 있습니다.

---

## 5. 테스트 & 운영

- **즉시 실행**: 루틴 상세 페이지에서 **Run now** → 생성된 세션 transcript에서 실제로
  공고를 수집하고 카카오톡이 도착했는지 확인합니다.
  - ⚠️ 실행 목록의 초록색 상태는 "세션이 에러 없이 종료됨"일 뿐, 메시지 전송 성공을 보장하지 않습니다.
    반드시 세션 로그와 카카오톡 수신을 직접 확인하세요.
- **일시정지/재개**: 상세 페이지 **Repeats** 토글
- **로컬 단독 실행**(디버깅용):
  ```bash
  pip install -r requirements.txt
  python collect.py            # digest.txt 생성 + 화면 출력 (전송 안 함)
  python collect.py --send     # 수집 + 카카오 전송
  python send_kakao.py "보낼 내용"   # 임의 텍스트 전송 테스트
  ```

---

## 6. 운영 시 주의

- **refresh token 갱신**: 카카오가 refresh token을 회전(rotate)시키면 `send_kakao.py`가
  새 토큰을 메시지로 보내줍니다. 이때 **클라우드 환경변수 `KAKAO_REFRESH_TOKEN`을 즉시 교체**해야
  다음 실행이 끊기지 않습니다.
- **시크릿 보관**: 클라우드 환경변수는 해당 환경을 편집할 수 있는 사람에게 보입니다.
  공용 환경에 민감 키를 넣지 마세요.
- **수집 대상/기준 변경**: 대상 사이트·직무·경력 기준은 `CLAUDE.md`에서, 지역·경력 필터
  로직과 분야별 검색 키워드·쿼터는 `collect.py` 상단 상수(`TARGET_GG`, `SENIOR`, `MAX_EXP_FLOOR`, `CATEGORIES`, `PER_CATEGORY`, `TOTAL`)에서 조정합니다.
- **메시지 길이**: 카카오 텍스트 1건 한도는 약 1000자. `send_kakao.py`가 공고 단위로
  자동 분할합니다(`TEXT_LIMIT`).

---

## 참고 문서
- [Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web)
- [Routines](https://code.claude.com/docs/en/routines)

---

## 7. (대안) GitHub Actions로 실행 — Claude 플랜 불필요

`collect.py --send` 는 Claude 없이도 단독으로 동작하므로 GitHub Actions 크론으로 돌릴 수 있습니다.
`.github/workflows/daily-brief.yml` 이 매일 07:00 KST에 실행되도록 이미 들어 있습니다.

1. GitHub 레포 → **Settings → Secrets and variables → Actions → New repository secret**
   - `KAKAO_REST_KEY`, `KAKAO_CLIENT_SECRET`, `KAKAO_REFRESH_TOKEN` 세 개 등록
2. **Actions** 탭 → "풀스택 채용 공고 데일리 브리핑" → **Run workflow** 로 즉시 테스트
3. 실행 로그에서 `collect_wanted: N건` 등 수집 개수와 전송 결과 확인

> 카카오가 refresh token을 회전시키면 카카오톡으로 새 토큰이 오는데, 그때 Secrets의
> `KAKAO_REFRESH_TOKEN` 을 교체해야 다음 실행이 끊기지 않습니다.

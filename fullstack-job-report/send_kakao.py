#!/usr/bin/env python3
"""카카오톡 '나에게 보내기(memo)'로 다이제스트를 전송한다.

필요한 환경변수 (클라우드/실행 환경에 주입):
  KAKAO_REST_KEY        카카오 앱 REST API 키
  KAKAO_CLIENT_SECRET   Client Secret (앱에 활성화돼 있으면 필수)
  KAKAO_REFRESH_TOKEN   최초 1회 발급받은 refresh token

사용:
  python send_kakao.py "보낼 내용"
  echo "보낼 내용" | python send_kakao.py
  # 또는 collect.py 에서 import 해 send_kakao.send(text) 호출
"""
import os
import sys
import json
import requests

KAUTH = "https://kauth.kakao.com/oauth/token"
MEMO = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
TEXT_LIMIT = 900  # 카카오 text 템플릿 한도는 약 1000'자'(문자 수, 실측). 여유 두고 900자.


def get_access_token():
    """저장된 refresh token으로 access token을 발급한다.
    비밀값은 반드시 환경변수로 주입한다(코드에 하드코딩하지 않는다)."""
    try:
        data = {
            "grant_type": "refresh_token",
            "client_id": os.environ["KAKAO_REST_KEY"],
            "refresh_token": os.environ["KAKAO_REFRESH_TOKEN"],
        }
    except KeyError as e:
        raise SystemExit(
            f"환경변수 {e} 가 없습니다. "
            "KAKAO_REST_KEY / KAKAO_CLIENT_SECRET / KAKAO_REFRESH_TOKEN 를 설정하세요."
        )
    secret = os.environ.get("KAKAO_CLIENT_SECRET")  # 활성화돼 있으면 필수
    if secret:
        data["client_secret"] = secret
    r = requests.post(KAUTH, data=data, timeout=10)
    r.raise_for_status()
    tok = r.json()
    return tok["access_token"], tok.get("refresh_token")  # rotated or None


def send_chunk(access_token, text):
    payload = {
        "object_type": "text",
        "text": text,
        # link는 필수 필드지만 비워두면 '자세히 보기' 버튼이 표시되지 않는다.
        # 각 공고 URL은 본문(text) 안에 들어가며 카카오톡이 자동으로 링크 처리한다.
        "link": {},
    }
    r = requests.post(
        MEMO,
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps(payload, ensure_ascii=False)},
        timeout=10,
    )
    r.raise_for_status()


def chunk_text(body, limit=TEXT_LIMIT):
    """공고 블록(빈 줄로 구분)을 쪼개지 않고, 한도 내에서 여러 블록을 한 메시지에 모은다.
    한 블록이 한도를 넘으면 그 블록만 줄 단위로 강제 분할한다."""
    chunks, cur = [], ""
    for block in body.split("\n\n"):
        block = block.strip("\n")
        if not block:
            continue
        if len(block) > limit:             # 단일 블록이 너무 길면 줄 단위 분할
            if cur:
                chunks.append(cur)
                cur = ""
            acc = ""
            for line in block.split("\n"):
                while len(line) > limit:   # 한 줄이 한도 초과 시 강제 절단
                    chunks.append(line[:limit])
                    line = line[limit:]
                if acc and len(acc) + len(line) + 1 > limit:
                    chunks.append(acc)
                    acc = line
                else:
                    acc = f"{acc}\n{line}" if acc else line
            if acc:
                chunks.append(acc)
            continue
        if cur and len(cur) + 2 + len(block) > limit:
            chunks.append(cur)
            cur = block
        else:
            cur = f"{cur}\n\n{block}" if cur else block
    if cur:
        chunks.append(cur)
    return chunks


def send(body):
    """본문을 1000자 한도에 맞춰 분할해 카카오톡 '나에게 보내기'로 전송한다.
    다른 스크립트(collect.py 등)에서 import 해 호출할 수 있다."""
    body = (body or "").strip()
    if not body:
        raise ValueError("보낼 내용이 없습니다.")
    access_token, rotated = get_access_token()
    for part in chunk_text(body):
        send_chunk(access_token, part)
    # refresh token이 갱신되면 반드시 환경변수를 교체해야 동작이 끊기지 않는다.
    if rotated:
        send_chunk(
            access_token,
            "🔑 KAKAO_REFRESH_TOKEN이 갱신됐습니다.\n"
            "클라우드 환경변수를 아래 값으로 즉시 교체하세요:\n" + rotated,
        )


def main():
    body = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    try:
        send(body)
    except ValueError as e:
        print(e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

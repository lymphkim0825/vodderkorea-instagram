# -*- coding: utf-8 -*-
"""
수동용: 현재 가진 Instagram 액세스 토큰을 60일짜리 장기 토큰으로 (재)발급한다.

("Instagram API with Instagram Login" 플로우 전용 — graph.instagram.com 사용)

경위: 공식 문서상으로는 "단기 토큰 → 장기 토큰"에 ig_exchange_token(앱 시크릿 필요)을
쓰고, 장기 토큰의 60일 주기 갱신에는 ig_refresh_token(앱 시크릿 불필요)을 쓰도록
안내되어 있다. 그런데 이 프로젝트의 앱에서는 대시보드 "토큰 생성" 버튼으로 받은
토큰에 대해 ig_exchange_token 호출이 "Session key invalid"로 항상 거부됐다.
반면 ig_refresh_token은 같은 토큰에 대해 즉시 정상적으로 60일짜리 새 토큰을
내려줬다 (2026-09-03 확인). 그래서 최초 발급도 굳이 ig_exchange_token을 쓰지 않고
ig_refresh_token으로 통일한다 — 앱 시크릿이 아예 필요 없어져서 더 간단하다.

사용법:
    CURRENT_TOKEN=... python refresh_token.py

절차:
1. Meta 앱 대시보드 "Instagram 로그인이 포함된 API 설정" > "2. 액세스 토큰 생성"에서
   "토큰 생성"으로 Instagram User 액세스 토큰을 받는다.
2. 그 값을 CURRENT_TOKEN 환경변수에 넣고 이 스크립트를 실행하면 60일짜리 장기
   토큰을 콘솔에 출력한다.
3. 그 값을 GitHub Secrets의 IG_ACCESS_TOKEN에 수동으로 복사해 넣는다.
   (이후 60일마다 갱신은 rotate_token.py + refresh-token.yml 워크플로우가 자동으로 한다.)
"""
import os
import sys
import requests


def main():
    current_token = os.environ.get("CURRENT_TOKEN")
    if not current_token:
        sys.exit("ERROR: CURRENT_TOKEN 환경변수가 필요합니다.")

    current_token = current_token.strip()
    print(f"[디버그] CURRENT_TOKEN 길이: {len(current_token)}자, 시작: {current_token[:6]!r}, 끝: {current_token[-6:]!r}")

    resp = requests.get(
        "https://graph.instagram.com/refresh_access_token",
        params={
            "grant_type": "ig_refresh_token",
            "access_token": current_token,
        },
        timeout=30,
    )
    data = resp.json()
    if "access_token" not in data:
        sys.exit(f"ERROR: 토큰 발급 실패: {data}")

    expires_days = data.get("expires_in", 0) / 86400
    print(f"새 장기 액세스 토큰 (약 {expires_days:.0f}일 유효):")
    print(data["access_token"])
    print("\n이 값을 GitHub 저장소 Settings > Secrets > IG_ACCESS_TOKEN 에 붙여넣으세요.")


if __name__ == "__main__":
    main()

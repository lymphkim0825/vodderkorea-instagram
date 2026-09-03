# -*- coding: utf-8 -*-
"""
수동용: 단기(1시간) Instagram User 액세스 토큰을 60일짜리 장기 토큰으로 최초 교환한다.
("Instagram API with Instagram Login" 플로우 전용 — graph.instagram.com 사용)

사용법:
    IG_APP_SECRET=... SHORT_TOKEN=... python refresh_token.py

절차:
1. Meta 앱 대시보드 "Instagram 로그인이 포함된 API 설정" > "2. 액세스 토큰 생성"에서
   "Add an Instagram Account"로 로그인하면 단기(短期) Instagram User 액세스 토큰을 받는다.
2. 그 값을 SHORT_TOKEN 환경변수에 넣고 이 스크립트를 실행하면 장기 토큰을 콘솔에 출력한다.
3. 그 값을 GitHub Secrets의 IG_ACCESS_TOKEN에 수동으로 복사해 넣는다.
   (이후 60일마다 갱신 필요 — 자동화하려면 rotate_token.py 사용. 이 최초 교환 자체는
   앱 시크릿이 필요해 자동화하지 않고 최초 1회만 수동으로 한다.)

주의: 여기서 필요한 IG_APP_SECRET은 Meta 앱 대시보드 "설정 > 기본 설정"의
"앱 시크릿 코드"이다. Facebook Login 플로우의 FB_APP_SECRET과는 별개 개념이 아니라
같은 앱의 App Secret이지만, 교환 엔드포인트 자체가 다르므로 변수명을 구분했다.
"""
import os
import sys
import requests

GRAPH_VERSION = "v21.0"


def main():
    app_secret = os.environ.get("IG_APP_SECRET")
    short_token = os.environ.get("SHORT_TOKEN")
    if not (app_secret and short_token):
        sys.exit("ERROR: IG_APP_SECRET, SHORT_TOKEN 환경변수가 모두 필요합니다.")

    resp = requests.get(
        f"https://graph.instagram.com/access_token",
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": app_secret,
            "access_token": short_token,
        },
        timeout=30,
    )
    data = resp.json()
    if "access_token" not in data:
        sys.exit(f"ERROR: 토큰 교환 실패: {data}")

    print("새 장기 액세스 토큰 (60일 유효):")
    print(data["access_token"])
    print("\n이 값을 GitHub 저장소 Settings > Secrets > IG_ACCESS_TOKEN 에 붙여넣으세요.")


if __name__ == "__main__":
    main()

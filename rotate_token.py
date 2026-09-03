# -*- coding: utf-8 -*-
"""
자동용: 현재 IG_ACCESS_TOKEN(장기 토큰)을 갱신하고, GitHub Actions Secret까지 자동으로 업데이트한다.
refresh-token.yml 워크플로우(매월 1일·15일)에서 실행된다.

("Instagram API with Instagram Login" 플로우 전용)
이 플로우의 갱신(refresh)은 ig_refresh_token 방식이라 앱 시크릿이 필요 없고,
현재 가지고 있는 장기 토큰만으로 갱신한다. 단, 토큰이 발급된 지 24시간이 지났고
아직 만료(60일) 전이어야 갱신할 수 있다.

필요한 환경변수:
- IG_ACCESS_TOKEN  : 현재(갱신 전) 장기 토큰 — 발급 후 24시간 이상, 60일 미만이어야 함
- GH_PAT           : "Secrets: Read and write" 권한의 GitHub Fine-grained PAT
- GITHUB_REPOSITORY: "owner/repo" (GitHub Actions가 자동 제공)
"""
import os
import sys
import base64
import requests
from nacl import encoding, public  # PyNaCl (requirements.txt에 포함)

GRAPH_VERSION = "v21.0"


def refresh_token(current_token: str) -> str:
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
        sys.exit(f"ERROR: 토큰 갱신 실패: {data}")
    return data["access_token"]


def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    public_key = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def update_github_secret(repo: str, gh_pat: str, secret_name: str, secret_value: str):
    headers = {
        "Authorization": f"Bearer {gh_pat}",
        "Accept": "application/vnd.github+json",
    }
    key_resp = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=headers, timeout=30,
    )
    key_data = key_resp.json()
    if "key" not in key_data:
        sys.exit(f"ERROR: GitHub public key 조회 실패: {key_data}")

    encrypted_value = encrypt_secret(key_data["key"], secret_value)

    put_resp = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}",
        headers=headers,
        json={"encrypted_value": encrypted_value, "key_id": key_data["key_id"]},
        timeout=30,
    )
    if put_resp.status_code not in (201, 204):
        sys.exit(f"ERROR: GitHub Secret 업데이트 실패: {put_resp.status_code} {put_resp.text}")


def main():
    current_token = os.environ.get("IG_ACCESS_TOKEN")
    gh_pat = os.environ.get("GH_PAT")
    repo = os.environ.get("GITHUB_REPOSITORY")

    missing = [n for n, v in [
        ("IG_ACCESS_TOKEN", current_token), ("GH_PAT", gh_pat),
        ("GITHUB_REPOSITORY", repo),
    ] if not v]
    if missing:
        sys.exit(f"ERROR: 환경변수 누락: {', '.join(missing)}")

    new_token = refresh_token(current_token)
    update_github_secret(repo, gh_pat, "IG_ACCESS_TOKEN", new_token)
    print("GitHub Secret 'IG_ACCESS_TOKEN' 자동 업데이트 완료")


if __name__ == "__main__":
    main()

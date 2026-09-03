# -*- coding: utf-8 -*-
"""
Instagram 캐러셀(carousel) 자동 게시 스크립트.

동작 방식:
1. GitHub raw URL(공개 저장소 기준)로 images/slide_01.jpg ~ slide_09.jpg 를 참조한다.
2. 각 이미지를 IG 컨테이너(carousel item)로 먼저 업로드한다.
3. 모든 컨테이너 id를 모아 캐러셀 컨테이너를 만든다 (caption.txt 내용을 caption으로 사용).
4. 캐러셀 컨테이너를 발행(publish)한다.

필요한 환경변수 (GitHub Actions Secrets 에서 주입됨):
- IG_USER_ID       : Instagram 비즈니스 계정 ID
- IG_ACCESS_TOKEN  : 장기(long-lived) Access Token
- GITHUB_REPOSITORY: "owner/repo" 형식 (GitHub Actions에서 자동 제공됨)
- IMAGE_BASE_URL   : (선택) 위 대신 직접 base URL을 지정하고 싶을 때 사용
                      예: https://raw.githubusercontent.com/{owner}/{repo}/main/images
"""
import os
import sys
import time
import requests

GRAPH_VERSION = "v21.0"
# "Instagram API with Instagram Login" 플로우 전용 호스트.
# (참고: "Instagram API with Facebook Login" 플로우라면 graph.facebook.com 을 쓴다.)
GRAPH_BASE = f"https://graph.instagram.com/{GRAPH_VERSION}"


def get_image_base_url() -> str:
    base = os.environ.get("IMAGE_BASE_URL")
    if base:
        return base.rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        sys.exit("ERROR: IMAGE_BASE_URL 또는 GITHUB_REPOSITORY 환경변수가 필요합니다.")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/images"


def get_image_urls() -> list:
    here = os.path.dirname(os.path.abspath(__file__))
    images_dir = os.path.join(here, "images")
    files = sorted(
        f for f in os.listdir(images_dir)
        if f.lower().startswith("slide_") and f.lower().endswith((".jpg", ".jpeg"))
    )
    if not (2 <= len(files) <= 10):
        sys.exit(f"ERROR: 캐러셀은 이미지 2~10장이 필요합니다. 현재 {len(files)}장.")
    base = get_image_base_url()
    return [f"{base}/{f}" for f in files]


def get_caption() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "caption.txt")
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    if len(text) > 2200:
        sys.exit(f"ERROR: 캡션이 2200자를 초과합니다 ({len(text)}자).")
    return text


def create_item_container(ig_user_id: str, token: str, image_url: str) -> str:
    resp = requests.post(
        f"{GRAPH_BASE}/{ig_user_id}/media",
        data={
            "image_url": image_url,
            "is_carousel_item": "true",
            "access_token": token,
        },
        timeout=60,
    )
    data = resp.json()
    if "id" not in data:
        sys.exit(f"ERROR: 아이템 컨테이너 생성 실패 ({image_url}): {data}")
    return data["id"]


def create_carousel_container(ig_user_id: str, token: str, children_ids: list, caption: str) -> str:
    resp = requests.post(
        f"{GRAPH_BASE}/{ig_user_id}/media",
        data={
            "media_type": "CAROUSEL",
            "caption": caption,
            "children": ",".join(children_ids),
            "access_token": token,
        },
        timeout=60,
    )
    data = resp.json()
    if "id" not in data:
        sys.exit(f"ERROR: 캐러셀 컨테이너 생성 실패: {data}")
    return data["id"]


def wait_until_ready(creation_id: str, token: str, timeout_sec: int = 120):
    """일부 이미지는 처리에 시간이 걸릴 수 있어 상태를 폴링한다."""
    start = time.time()
    while time.time() - start < timeout_sec:
        resp = requests.get(
            f"{GRAPH_BASE}/{creation_id}",
            params={"fields": "status_code", "access_token": token},
            timeout=30,
        )
        data = resp.json()
        status = data.get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            sys.exit(f"ERROR: 컨테이너 처리 실패: {data}")
        time.sleep(3)
    sys.exit(f"ERROR: 컨테이너({creation_id}) 처리 대기 시간 초과")


def publish(ig_user_id: str, token: str, creation_id: str) -> str:
    resp = requests.post(
        f"{GRAPH_BASE}/{ig_user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": token},
        timeout=60,
    )
    data = resp.json()
    if "id" not in data:
        sys.exit(f"ERROR: 게시 실패: {data}")
    return data["id"]


def main():
    ig_user_id = os.environ.get("IG_USER_ID")
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not ig_user_id or not token:
        sys.exit("ERROR: IG_USER_ID / IG_ACCESS_TOKEN 환경변수가 필요합니다.")

    image_urls = get_image_urls()
    caption = get_caption()

    print(f"이미지 {len(image_urls)}장, base_url={image_urls[0].rsplit('/', 1)[0]}")

    child_ids = []
    for url in image_urls:
        cid = create_item_container(ig_user_id, token, url)
        print(f"  컨테이너 생성됨: {url} -> {cid}")
        child_ids.append(cid)

    carousel_id = create_carousel_container(ig_user_id, token, child_ids, caption)
    print(f"캐러셀 컨테이너 생성됨: {carousel_id}")

    wait_until_ready(carousel_id, token)

    media_id = publish(ig_user_id, token, carousel_id)
    print(f"게시 완료! media_id={media_id}")


if __name__ == "__main__":
    main()

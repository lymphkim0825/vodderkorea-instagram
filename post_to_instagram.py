# -*- coding: utf-8 -*-
"""
Instagram 캐러셀(carousel) 자동 게시 스크립트 — 큐(queue) 기반 순차 게시 버전.

동작 방식:
1. queue/ 폴더 아래의 하위 폴더들을 이름순(알파벳/숫자순)으로 정렬해서
   가장 앞선 폴더 하나를 "이번에 게시할 카드뉴스"로 고른다.
   (폴더가 없으면 "게시할 것 없음"으로 조용히 종료 — 실패 아님)
2. 그 폴더 안의 slide_01.jpg ~ slide_09.jpg 를 GitHub raw URL로 참조해서
   각각 IG 컨테이너(carousel item)로 업로드한다.
3. 모든 컨테이너 id를 모아 캐러셀 컨테이너를 만든다 (그 폴더의 caption.txt 를 caption으로 사용).
4. 캐러셀 컨테이너를 발행(publish)한다.
5. 게시에 성공하면 해당 폴더를 queue/ 에서 posted/ 로 옮기고(= "완료" 표시),
   git commit + push 한다. 이 마지막 단계가 실패하면 워크플로우 전체를 실패로 표시한다.
   (그래야 같은 카드뉴스가 큐에 남아 다음 실행 때 중복 게시되는 사고를 사람이 알아챌 수 있다.)

필요한 환경변수 (GitHub Actions Secrets 에서 주입됨):
- IG_USER_ID       : Instagram 비즈니스 계정 ID
- IG_ACCESS_TOKEN  : 장기(long-lived) Access Token
- GITHUB_REPOSITORY: "owner/repo" 형식 (GitHub Actions에서 자동 제공됨)
- GITHUB_OUTPUT    : GitHub Actions가 자동 제공하는, step output 기록용 파일 경로
- IMAGE_BASE_URL   : (선택) 위 대신 직접 base URL을 지정하고 싶을 때 사용
                      예: https://raw.githubusercontent.com/{owner}/{repo}/main/queue/001-xxx
                      (지정 시 큐 자동 선택 없이 이 경로 하나만 강제로 사용)
"""
import os
import subprocess
import sys
import time

import requests

GRAPH_VERSION = "v21.0"
# "Instagram API with Instagram Login" 플로우 전용 호스트.
# (참고: "Instagram API with Facebook Login" 플로우라면 graph.facebook.com 을 쓴다.)
GRAPH_BASE = f"https://graph.instagram.com/{GRAPH_VERSION}"

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
QUEUE_DIR = os.path.join(REPO_ROOT, "queue")
POSTED_DIR = os.path.join(REPO_ROOT, "posted")


def set_output(name: str, value: str):
    """GitHub Actions step output 기록 (GITHUB_OUTPUT 파일이 없으면 조용히 무시 — 로컬 테스트용)."""
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{name}={value}\n")


def pick_next_queue_item() -> str:
    """queue/ 아래 하위 폴더 중 이름순으로 가장 앞선 것을 고른다. 없으면 None."""
    if not os.path.isdir(QUEUE_DIR):
        return None
    candidates = sorted(
        d for d in os.listdir(QUEUE_DIR)
        if os.path.isdir(os.path.join(QUEUE_DIR, d)) and not d.startswith(".")
    )
    return candidates[0] if candidates else None


def get_image_base_url(queue_name: str) -> str:
    base = os.environ.get("IMAGE_BASE_URL")
    if base:
        return base.rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        sys.exit("ERROR: IMAGE_BASE_URL 또는 GITHUB_REPOSITORY 환경변수가 필요합니다.")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/queue/{queue_name}"


def get_image_urls(queue_name: str) -> list:
    item_dir = os.path.join(QUEUE_DIR, queue_name)
    files = sorted(
        f for f in os.listdir(item_dir)
        if f.lower().startswith("slide_") and f.lower().endswith((".jpg", ".jpeg"))
    )
    if not (2 <= len(files) <= 10):
        sys.exit(f"ERROR: 캐러셀은 이미지 2~10장이 필요합니다. '{queue_name}' 폴더에는 현재 {len(files)}장.")
    base = get_image_base_url(queue_name)
    return [f"{base}/{f}" for f in files]


def get_caption(queue_name: str) -> str:
    path = os.path.join(QUEUE_DIR, queue_name, "caption.txt")
    if not os.path.isfile(path):
        sys.exit(f"ERROR: '{queue_name}' 폴더에 caption.txt 가 없습니다.")
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


def run_git(*args, check=True):
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} 실패 (exit {result.returncode})\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


def mark_as_posted(queue_name: str, media_id: str):
    """게시 성공한 큐 항목을 posted/ 로 옮기고 커밋·푸시해서 '완료'로 표시한다.

    이 함수가 실패(예외)하면 큐 항목이 queue/ 에 그대로 남아있게 되고,
    다음 실행 때 같은 카드뉴스가 다시 게시될 위험이 있다 — 그래서 이 실패는
    호출부(main)에서 반드시 워크플로우 실패로 이어지게 한다(사람이 수동으로
    queue/<이름> 을 posted/ 로 옮겨서 정리해야 함).
    """
    os.makedirs(POSTED_DIR, exist_ok=True)
    src = os.path.join("queue", queue_name)
    dst = os.path.join("posted", queue_name)

    run_git("config", "user.name", "github-actions[bot]")
    run_git("config", "user.email", "github-actions[bot]@users.noreply.github.com")

    run_git("mv", src, dst)

    # 게시 완료 기록을 남겨둔다 (언제, 어떤 media_id로 게시됐는지).
    done_marker = os.path.join(REPO_ROOT, dst, "POSTED.txt")
    with open(done_marker, "w", encoding="utf-8") as f:
        f.write(
            f"posted_at_utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
            f"instagram_media_id={media_id}\n"
        )
    run_git("add", dst)

    run_git("commit", "-m", f"Posted to Instagram: {queue_name} (media_id={media_id})")

    # 그 사이 다른 커밋이 push 됐을 수 있으니 rebase 후 재시도.
    last_err = None
    for attempt in range(3):
        try:
            run_git("pull", "--rebase", "origin", os.environ.get("GITHUB_REF_NAME", "main"))
            run_git("push", "origin", f"HEAD:{os.environ.get('GITHUB_REF_NAME', 'main')}")
            return
        except RuntimeError as e:
            last_err = e
            time.sleep(3)
    raise last_err


def main():
    ig_user_id = os.environ.get("IG_USER_ID")
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not ig_user_id or not token:
        sys.exit("ERROR: IG_USER_ID / IG_ACCESS_TOKEN 환경변수가 필요합니다.")

    queue_name = pick_next_queue_item()
    if not queue_name:
        print("큐(queue/)에 게시할 카드뉴스가 없습니다. 이번 실행은 건너뜁니다.")
        set_output("posted", "false")
        return

    print(f"이번에 게시할 항목: {queue_name}")

    image_urls = get_image_urls(queue_name)
    caption = get_caption(queue_name)
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

    set_output("posted", "true")
    set_output("queue_name", queue_name)

    try:
        mark_as_posted(queue_name, media_id)
        print(f"'{queue_name}' 을(를) posted/ 로 이동하고 완료 표시했습니다.")
    except Exception as e:
        # 게시는 이미 성공했으므로 media_id는 살아있다. 하지만 큐 정리가 실패했으므로
        # 다음 실행 때 중복 게시될 수 있음을 반드시 알려야 한다 -> 워크플로우 실패 처리.
        sys.exit(
            f"ERROR: Instagram 게시는 성공(media_id={media_id})했지만, "
            f"완료 표시(git commit/push)에 실패했습니다: {e}\n"
            f"조치 필요: queue/{queue_name} 폴더를 수동으로 posted/ 로 옮겨서 "
            f"다음 실행에서 중복 게시되지 않도록 해주세요."
        )


if __name__ == "__main__":
    main()

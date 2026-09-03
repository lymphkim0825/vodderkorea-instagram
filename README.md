# Instagram 캐러셀 자동 게시 (Claude Code + GitHub Actions)

Dr. Vodder School Korea 인스타그램에 카드뉴스를 자동으로 게시하기 위한 저장소입니다.
Meta의 공식 **Instagram Graph API**를 사용하며, GitHub Actions가 정해진 시간(또는 수동 클릭)에
`post_to_instagram.py`를 실행해 캐러셀(9장) 게시물을 올립니다.

---

## 0. 사전 준비물 (한 번만 하면 됨)

- [ ] Instagram 계정을 **비즈니스 또는 크리에이터 계정**으로 전환 (인스타그램 앱 > 설정 > 계정 유형)
- [ ] [Meta for Developers](https://developers.facebook.com/) 개발자 계정

이 가이드는 **"Instagram API with Instagram Login"** (Instagram 로그인이 포함된 API 설정) 플로우
기준입니다. Facebook 페이지 연결이 필요 없는 더 최신 플로우로, Instagram 계정으로 직접 로그인해
토큰을 발급받습니다. 개인 계정으로는 API 게시가 불가능하며 반드시 비즈니스/크리에이터 계정이어야 합니다.

---

## 1. Meta 앱 생성 및 Instagram 로그인 제품 추가

1. https://developers.facebook.com/apps 접속 → **앱 만들기**
2. 앱 유형: **비즈니스** 선택
3. 앱 이름 입력 (예: `vodderkorea-autopost`) → 생성
4. 앱 대시보드 → **제품 추가** → **Instagram** 제품에서 **"Instagram 로그인이 포함된 API 설정"** 선택
5. 해당 제품 설정 화면에서 순서대로 진행:
   - **1. 필수 메시지 권한 추가** — 기본 제공되는 메시지 관련 권한(자동 체크됨)에 더해,
     "권한 및 기능"(Permissions and Features) 메뉴에서 게시에 필요한
     **`instagram_business_basic`**, **`instagram_business_content_publish`** 권한을
     반드시 추가한다. (메시지 권한 체크리스트에는 기본 포함되어 있지 않으므로 놓치기 쉽다.)
   - **2. 액세스 토큰 생성** — **"Add an Instagram Account"** 클릭 → 실제 사용할
     Instagram 비즈니스/크리에이터 계정으로 로그인 → 단기(1시간) **Instagram User 액세스 토큰**과
     함께 **Instagram User ID**가 화면에 표시된다. 이 ID가 **IG_USER_ID**.
   - **3. Webhooks 구성** — 자동 게시만 할 경우 필수는 아니다 (건너뛰어도 됨).

---

## 2. 장기 액세스 토큰 발급 (최초 1회, 수동)

위 "2. 액세스 토큰 생성" 단계에서 받은 토큰을 `refresh_token.py`로 60일짜리 장기
토큰으로 발급받습니다. (공식 문서상으로는 최초 발급에 앱 시크릿이 필요한
`ig_exchange_token`을 쓰라고 안내하지만, 이 프로젝트의 앱에서는 대시보드가 발급한
토큰에 대해 그 호출이 항상 거부됐습니다. 대신 원래 60일 주기 갱신용인
`ig_refresh_token`이 최초 발급에도 바로 통했습니다 — 앱 시크릿이 필요 없어 오히려
더 간단합니다. `refresh_token.py`는 이 방식으로 되어 있습니다.)

```
CURRENT_TOKEN={방금 받은 토큰} python refresh_token.py
```

출력된 `access_token` 값이 **IG_ACCESS_TOKEN** 입니다. (60일 후 만료 → 아래 6번 참고.
참고로 IG_USER_ID는 대시보드 화면에 표시된 번호가 아니라, 이 토큰으로
`https://graph.instagram.com/me?fields=id,username&access_token={토큰}` 을 호출했을 때
나오는 `id` 값을 써야 합니다 — 두 값이 다를 수 있습니다.)

---

## 3. GitHub 저장소 만들기

1. GitHub에서 새 저장소 생성 (예: `vodderkorea-instagram`)
2. **Public으로 생성** — Instagram이 이미지를 다운로드하려면 이미지 URL이 외부에서 접근 가능해야 합니다. (비공개로 하고 싶다면 7번의 "저장소를 비공개로 하고 싶다면" 참고)
3. 이 폴더(`instagram_auto_post/`) 안의 모든 파일·폴더를 저장소 최상위에 그대로 업로드/push

```
your-repo/
├── images/
│   ├── slide_01.png ... slide_09.png
├── caption.txt
├── post_to_instagram.py
├── refresh_token.py
├── requirements.txt
└── .github/workflows/post-instagram.yml
```

Claude Code를 쓰신다면, 이 폴더를 열어둔 상태에서 Claude Code에게
"이 폴더를 새 GitHub 저장소로 만들고 push해줘"라고 요청하면 `git init` / `gh repo create` /
`git push`까지 대신 실행해 줍니다. (GitHub CLI 로그인이 먼저 되어 있어야 합니다: `gh auth login`)

---

## 4. GitHub Secrets 등록

저장소 > **Settings** > **Secrets and variables** > **Actions** > **New repository secret**

| Name | Value |
|---|---|
| `IG_USER_ID` | 1번에서 확인한 Instagram User ID |
| `IG_ACCESS_TOKEN` | 2번에서 발급한 장기 토큰 |
| `GH_PAT` | 토큰 자동 갱신에 필요 — 아래 6번에서 만드는 방법 설명 |

앱 시크릿은 어디에도 등록할 필요가 없습니다. 최초 발급(2번)과 60일마다의 자동
갱신(`rotate_token.py`) 모두 `IG_ACCESS_TOKEN` 자체만으로 갱신하는 `ig_refresh_token`
방식을 씁니다.

---

## 5. 실행하기

저장소 > **Actions** 탭 > **Post to Instagram** 워크플로우 선택 > **Run workflow** 버튼 클릭

몇 초~1분 내로 인스타그램 계정에 9장짜리 캐러셀 게시물이 올라갑니다.
진행 로그는 Actions 탭에서 실시간으로 확인할 수 있습니다.

---

## 6. 토큰 자동 갱신 설정하기 (이거 해두면 60일마다 신경 안 써도 됨)

`refresh_token.py`는 수동으로 값을 복사해야 했지만, `rotate_token.py` + `refresh-token.yml`
워크플로우는 **토큰 갱신과 GitHub Secret 업데이트까지 전부 자동**으로 처리합니다.
(이 갱신은 `ig_refresh_token` 방식이라 앱 시크릿 없이 현재 토큰만으로 가능합니다.)
설정만 한 번 해두면 그 뒤로는 손댈 일이 없습니다.

### 6-1. GitHub Personal Access Token(GH_PAT) 발급

이 저장소의 Secret 값을 워크플로우가 스스로 갱신하려면, "Secret 쓰기" 권한을 가진
별도의 토큰이 하나 필요합니다. (보안상 워크플로우 기본 권한으로는 Secret을 수정할 수 없습니다)

1. GitHub 우측 상단 프로필 → **Settings** → 좌측 맨 아래 **Developer settings**
2. **Personal access tokens** → **Fine-grained tokens** → **Generate new token**
3. 설정값:
   - **Repository access**: "Only select repositories" → 이 저장소만 선택
   - **Permissions** → **Secrets** → **Read and write** 로 설정
   - 나머지 권한은 전부 기본값(No access) 유지
4. 만료기간은 1년 정도로 설정 (만료되면 다시 만들어서 `GH_PAT` 값만 교체하면 됩니다)
5. 생성된 토큰 값을 4번의 GitHub Secrets에 `GH_PAT` 이름으로 등록

### 6-2. 동작 확인

`.github/workflows/refresh-token.yml`은 매월 1일·15일 자동 실행되며,
Actions 탭에서 **Refresh Instagram Token** → **Run workflow**로 즉시 테스트해볼 수도 있습니다.

성공하면 로그에 "GitHub Secret 'IG_ACCESS_TOKEN' 자동 업데이트 완료"가 출력되고,
Settings > Secrets 화면에서 `IG_ACCESS_TOKEN`의 "Updated" 시각이 갱신된 것을 확인할 수 있습니다.

단, 주의: 토큰은 발급 후 **24시간이 지나야** 갱신할 수 있습니다. 2번에서 막 발급한 토큰으로
바로 이 워크플로우를 테스트하면 실패할 수 있으니, 최소 하루 지난 뒤 테스트하세요.

이 설정을 마치면, 5번의 게시 워크플로우는 토큰 만료 걱정 없이 계속 정상 동작합니다.

---

## 7. 매번 새 카드뉴스로 교체하려면

`images/` 폴더의 이미지 9장과 `caption.txt`만 교체하고 다시 push하면,
다음 워크플로우 실행 시 새 내용으로 게시됩니다. (파일명은 `slide_01.jpg`~`slide_09.jpg` 형식 유지, JPEG 권장)

정기적으로 자동 게시하고 싶다면 `.github/workflows/post-instagram.yml`의
`schedule` 주석을 해제하고 cron 시간을 설정하세요. (UTC 기준이라 KST -9시간)

---

## 8. 주의사항 / 트러블슈팅

- **토큰 만료(60일)**: 6번의 자동 갱신 워크플로우를 설정해두면 신경 쓸 필요가 없습니다.
  설정하지 않았다면 `refresh_token.py`를 수동으로 다시 실행해 새 토큰을 GitHub Secrets에 직접 등록해야 합니다.
- **권한 누락**: "Instagram 로그인이 포함된 API 설정" 화면의 기본 체크리스트는 메시지 권한 위주라
  `instagram_business_content_publish`가 빠져있기 쉽습니다. "권한 및 기능" 메뉴에서
  `instagram_business_basic`, `instagram_business_content_publish` 두 권한이 추가되어 있는지 꼭 확인하세요.
  이 권한이 없으면 게시 시 권한 오류가 납니다.
- **App Review**: 처음에는 "개발 모드"라 앱 관리자 본인 계정에만 게시가 가능합니다.
  다른 사람 계정에도 게시하려면 Meta의 앱 심사(App Review)를 통과해야 합니다.
  본인(교수님) 계정 하나에만 쓰신다면 심사 없이 바로 사용 가능합니다.
- **저장소를 비공개로 하고 싶다면**: `raw.githubusercontent.com`은 비공개 저장소에서 인증 없이 접근할 수 없어
  Instagram이 이미지를 가져오지 못합니다. 이 경우 이미지만 별도로 **GitHub Pages**(무료, 공개)나
  이미지 호스팅 서비스(S3, Cloudinary 등)에 올리고 `IMAGE_BASE_URL`만 그쪽 주소로 바꾸면 됩니다.
- **게시 실패 시**: Actions 로그에 Graph API 에러 메시지가 그대로 출력됩니다.
  대부분 토큰 만료, 권한 누락, 계정이 비즈니스 계정이 아닌 경우입니다.

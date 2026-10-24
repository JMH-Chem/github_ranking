# GitHub 트렌딩 주간 아카이브 + 한국어 해설 사이트 — 기획/구현 계획

## 0. 한 줄 요약

GitHub Actions가 매주 정해진 시각에 **GitHub Trending(주간)** 을 수집하고, 각 레포의 README·메타데이터를 읽어 **Claude API로 한국어 설명**을 만든 뒤, 결과를 JSON으로 이 저장소에 커밋하고 **정적 사이트(GitHub Pages)** 로 배포한다. 별도로 일간 스냅샷을 쌓아 **분야별 "떠오르는 레포" 추천 페이지**를 만든다.

서버도 DB도 필요 없다. 데이터는 git에 쌓이고, 비용은 Claude API 사용료(월 몇 달러 수준)뿐이다.

---

## 1. 실현 가능성 검토

| 항목 | 판단 | 비고 |
|---|---|---|
| 트렌딩 데이터 수집 | 가능 | 공식 API가 없어서 `https://github.com/trending?since=weekly` HTML을 파싱한다. 주간 탭에는 보통 15~25개 레포가 레포명, 설명, 언어, 총 스타, 포크, **이번 주 스타** 와 함께 나온다. 순서는 GitHub 자체 알고리즘을 따르며 단순 스타 순이 아니다. |
| 레포 상세 정보 | 가능 | GitHub REST API로 README, topics, 라이선스, 생성일, 최근 푸시, 홈페이지 URL을 가져온다. Actions의 `GITHUB_TOKEN`이면 충분하다. |
| 한국어 설명 생성 | 가능 | Claude API에 README와 메타데이터를 넣고, 정해진 JSON 형식(구조화 출력)으로 한 줄 요약, 상세 설명, 주요 기능, 분야 분류를 받는다. |
| 주별 기록 보관 | 가능 | 매주 `data/weeks/2026-W43.json` 형태로 커밋한다. git 히스토리 자체가 변경 이력이 된다. |
| 과거 데이터 | **제한적** | GitHub은 과거 트렌딩을 제공하지 않는다. 기록은 서비스를 시작한 주부터 쌓인다. Wayback Machine 스냅샷으로 일부 소급할 수는 있지만 빠진 주가 많다(선택 사항). |
| 떠오르는 레포 추천 | 가능 (초기 정확도 낮음) | GitHub은 스타 시계열을 싸게 제공하지 않는다. 그래서 우리 쪽 일간 스냅샷으로 스타 증가량을 계산한다. 데이터가 2~4주 쌓이기 전까지는 Search API(최근 생성 + 스타 순)로 보완한다. |
| 호스팅 | 무료 | GitHub Pages를 쓴다. 저장소가 **public**이어야 무료다. private이면 유료 플랜이 필요하다. |

**리스크**
- GitHub이 트렌딩 페이지 HTML을 바꾸면 파서가 깨진다. 저장해 둔 HTML로 파서 테스트를 만들고, 수집이 실패하면 기존 데이터를 덮어쓰지 않고 워크플로를 실패시켜 알림(Issue 생성)을 보낸다.
- LLM 요약이 틀릴 수 있다. README에 있는 내용만 쓰도록 프롬프트로 제한하고, 페이지에 "AI 생성 요약" 표시와 원문 링크를 단다.
- 트렌딩 주간 탭은 "수집 시점 기준 최근 7일" 롤링 윈도우다. 그래서 **매주 같은 시각(월요일 09:00 KST)에 찍은 스냅샷을 직전 주(월~일)의 공식 기록**으로 정의한다. 예를 들어 2026-10-26(월)에 찍은 스냅샷은 `2026-W43`(10/19~10/25)으로 저장한다.

---

## 2. 전체 구조

```
┌──────────── GitHub Actions (cron) ────────────┐
│                                               │
│  daily.yml (매일)                              │
│   └ 트렌딩(일간·주간, 주요 언어 탭) 스냅샷 저장   │
│                                               │
│  weekly.yml (매주 월 09:00 KST)                │
│   1. 주간 트렌딩 수집      scrape_trending.py   │
│   2. GitHub API로 보강     enrich.py            │
│   3. 신규 레포만 한국어 요약 summarize.py (Claude)│
│   4. 떠오르는 레포 계산     rising.py            │
│   5. data/ 커밋 → 사이트 빌드 → Pages 배포      │
└───────────────────────────────────────────────┘
                      │
                      ▼
        data/*.json (git에 누적)  →  Astro 정적 사이트
```

### 디렉터리 구조 (안)

```
github_ranking/
├─ pipeline/                  # Python 수집·가공 스크립트
│  ├─ scrape_trending.py      # 트렌딩 HTML 파싱
│  ├─ enrich.py               # GitHub REST API로 메타데이터, README 보강
│  ├─ summarize.py            # Claude API로 한국어 설명 생성 (캐시 사용)
│  ├─ rising.py               # 떠오르는 레포 점수 계산과 분야별 선정
│  ├─ categories.py           # 분야 목록 정의
│  └─ tests/fixtures/         # 파서 테스트용 HTML 샘플
├─ data/
│  ├─ weeks/2026-W43.json     # 주간 공식 랭킹 기록
│  ├─ snapshots/2026-10-24.json  # 일간 스냅샷 (스타 수 추적용)
│  ├─ repos/<owner>__<name>.json # 레포별 정보, 한국어 설명, 랭크 이력
│  └─ rising/2026-W43.json    # 그 주의 분야별 추천 결과
├─ site/                      # Astro 정적 사이트
└─ .github/workflows/
   ├─ daily.yml
   └─ weekly.yml
```

---

## 3. 데이터 설계

### 3.1 주간 랭킹 `data/weeks/2026-W43.json`

```json
{
  "week": "2026-W43",
  "captured_at": "2026-10-26T00:00:00Z",
  "source": "https://github.com/trending?since=weekly",
  "entries": [
    {
      "rank": 1,
      "repo": "owner/name",
      "stars_total": 43710,
      "stars_this_week": 11223,
      "forks": 2727,
      "language": "JavaScript",
      "is_new": true,          // 처음 랭크됨
      "prev_rank": null,       // 지난주 순위 (없으면 null)
      "weeks_on_chart": 1      // 누적 랭크 주수
    }
  ]
}
```

### 3.2 레포 정보 `data/repos/owner__name.json`

```json
{
  "repo": "owner/name",
  "url": "https://github.com/owner/name",
  "description_en": "원문 설명",
  "topics": ["llm", "agent"],
  "language": "TypeScript",
  "license": "MIT",
  "created_at": "2026-08-01",
  "homepage": "https://...",
  "ko": {
    "one_liner": "한 줄 요약",
    "summary": "이 프로젝트가 무엇이고 어떤 문제를 푸는지 3~5문장",
    "features": ["주요 기능 1", "주요 기능 2", "주요 기능 3"],
    "use_cases": "누가, 언제 쓰면 좋은지",
    "category": "ai-llm",
    "generated_at": "2026-10-26",
    "readme_sha": "abc123"   // README가 바뀌면 다시 생성
  },
  "history": [
    { "week": "2026-W43", "rank": 1, "stars_total": 43710 }
  ]
}
```

- 한국어 설명은 **레포당 한 번만 생성**하고 캐시한다. README의 SHA가 바뀌었고 마지막 생성 후 4주가 지났을 때만 다시 만든다. 매주 같은 레포가 반복 랭크돼도 추가 비용이 없다.

---

## 4. 한국어 설명 생성 (Claude API)

- **모델**: `claude-opus-5-5`. 주당 처리량이 적어서 최상위 모델을 써도 비용이 작다(아래 추정). 더 저렴한 모델로 바꾸는 건 선택 사항이다.
- **입력**: 레포 이름, 원문 설명, topics, 언어, README 본문, 최근 릴리스 이름.
  - README가 아주 길면(예: 수만 토큰 이상) 앞부분과 목차 위주로 자른다. 이 기준은 코드에 명시해 두고 결과 JSON에 `readme_truncated: true`로 남긴다.
- **출력**: 구조화 출력(`output_config.format`, JSON 스키마)으로 `one_liner`, `summary`, `features[]`, `use_cases`, `category`를 받는다. `category`는 고정 분야 목록 중 하나(enum)로 제한한다.
- **프롬프트 원칙**
  - README와 메타데이터에 있는 사실만 쓴다. 추측은 금지한다.
  - 개발자가 아닌 사람도 이해할 수 있는 쉬운 한국어로 쓴다. 고유명사와 기술 용어는 원문을 병기한다.
  - "무엇을 하는 소프트웨어인가"를 먼저 쓰고, "어떻게 동작하는가"는 그 다음에 쓴다.
- **안정성**: `stop_reason`이 `refusal`이거나 실패한 레포는 건너뛰고 원문 설명만 보여 준다. 다음 실행 때 재시도한다.
- **비용 추정**: 주당 새 레포 약 10~20개, 떠오르는 레포 후보 약 40개, 레포당 입력 8천 토큰과 출력 1.5천 토큰을 가정하면 주당 약 $3~4다. Batch API(50% 할인)를 쓰면 **월 $6~8 수준**이다. 주간 배치 작업이라 지연에 민감하지 않아서 Batch API와 잘 맞는다.
- **필요한 설정**: 저장소 Secrets에 `ANTHROPIC_API_KEY`를 등록한다.

---

## 5. 떠오르는 레포 추천 (랭킹과 별도)

### 5.1 분야 (안, 7개)

| 키 | 분야 |
|---|---|
| `ai-llm` | AI·LLM·에이전트 |
| `devtools` | 개발 도구·CLI·생산성 |
| `web` | 웹·프론트엔드 |
| `infra` | 백엔드·인프라·DevOps·클라우드 |
| `data` | 데이터·DB·ML 엔지니어링 |
| `security` | 보안 |
| `etc` | 모바일·데스크톱·게임·그래픽스·하드웨어 |

분야마다 **5개씩** 추천한다. 분야 수와 개수는 설정으로 조정할 수 있다.

### 5.2 후보 수집
1. **일간 스냅샷**: 매일 트렌딩 일간·주간 탭과 주요 언어 탭(Python, TypeScript, Rust, Go 등 약 10개)을 수집해 스타 수를 기록한다.
2. **GitHub Search API**: 분야별 topic 쿼리를 쓴다. 예: `topic:llm created:>=<60일 전> stars:>=200`, 스타 순 정렬.
3. 이미 DB에 있는 레포 중 최근 푸시가 있는 것.

### 5.3 점수 계산
- 최근 7일 스타 증가량(스냅샷 차분), 증가율(증가량 ÷ 총 스타), 레포 나이(어릴수록 가산), 최근 커밋 활동을 반영한다.
- **제외 대상**: 이번 주 공식 랭킹 상위권(랭킹 페이지와 겹치지 않게), awesome-list와 단순 링크 모음, archived 레포, 최근 4주 안에 이미 추천한 레포, 스타는 급증했는데 포크·이슈 활동이 전혀 없는 레포(스타 조작 의심).
- 분야 분류는 4장의 Claude 요약에서 받은 `category`를 쓴다.
- 분야별 상위 5개에 대해 Claude가 "왜 지금 주목할 만한지" 추천 이유를 1~2문장으로 쓴다.

### 5.4 초기 운영
- 스냅샷이 2주 이상 쌓이기 전에는 스타 증가량을 계산할 수 없다. 그 기간에는 Search API 결과(최근 생성 + 스타 수) 위주로 추천하고 페이지에 "데이터 수집 초기"라고 표시한다.

---

## 6. 웹사이트

**기술**: [Astro](https://astro.build)로 정적 사이트를 만들고 `data/*.json`을 빌드 시점에 읽는다. Tailwind CSS와 Pretendard 폰트를 쓰고, 다크 모드와 모바일 대응을 넣는다. GitHub Pages로 배포한다.

| 경로 | 내용 |
|---|---|
| `/` | **이번 주 랭킹**: 순위, 레포명, 한국어 한 줄 요약, 언어, 이번 주 스타, 배지(🆕 신규 / ↑↓ 순위 변동 / 🔁 재진입 / N주 연속). 카드를 펼치면 상세 요약이 나온다. |
| `/weeks` | 주간 아카이브 목록(캘린더 또는 리스트) |
| `/weeks/2026-W43` | 특정 주의 랭킹 전체 |
| `/repos/owner/name` | 레포 상세: 한국어 설명, 주요 기능, 활용 사례, 랭크 이력(주차별 순위 그래프), 스타 추이, 원문 링크 |
| `/rising` | **분야별 떠오르는 레포**: 분야 탭마다 5개, 추천 이유와 최근 7일 스타 증가량 |
| `/stats` (선택) | 언어별·분야별 비중, 최장 랭크 레포, 이번 달 신규 진입 수 |

부가 기능(후순위): 사이트 내 검색(Pagefind), 주간 RSS 피드, 언어·분야 필터.

---

## 7. 자동화 워크플로

| 워크플로 | 일정 (cron, UTC) | 하는 일 |
|---|---|---|
| `daily.yml` | `0 0 * * *` (매일 09:00 KST) | 트렌딩 스냅샷 저장(LLM 호출 없음) |
| `weekly.yml` | `0 0 * * 1` (월 09:00 KST) | 주간 랭킹 확정 → 보강 → 신규 레포 요약 → rising 계산 → 커밋 → 빌드·배포 |
| `deploy.yml` | `data/` 또는 `site/` 변경 푸시 시 | 사이트만 다시 빌드·배포 |

- 모든 워크플로에 `workflow_dispatch`(수동 실행)를 넣는다.
- 수집 결과가 비었거나 파싱에 실패하면 커밋하지 않고 실패 처리한 뒤 Issue를 자동으로 연다.

---

## 8. 단계별 진행 계획

| 단계 | 내용 | 완료 기준 |
|---|---|---|
| **M1** 수집기 | 트렌딩 파서, GitHub API 보강, JSON 스키마, 파서 테스트 | 로컬/Actions에서 `data/weeks/*.json` 생성 |
| **M2** 한국어 요약 | Claude API 연동, 구조화 출력, 캐시, 실패 처리 | 랭크된 레포 전부에 `ko` 필드 생성 |
| **M3** 웹사이트 | Astro로 홈, 주간 아카이브, 레포 상세 페이지 구현 후 Pages 배포 | 공개 URL에서 이번 주 랭킹 확인 |
| **M4** 자동화 | daily/weekly cron, 실패 알림 | 사람 개입 없이 1주 운영 성공 |
| **M5** 떠오르는 레포 | 일간 스냅샷 기반 점수, Search API 보완, 분야별 5개 선정, 추천 이유 | `/rising` 페이지 공개 |
| **M6** 부가 기능 | 검색, RSS, 통계, Wayback 소급(선택) | — |

M1~M4가 핵심(MVP)이다. M5는 스냅샷이 쌓여야 정확해지므로, **daily 스냅샷은 M1과 함께 최대한 빨리 켜 두는 게 좋다.**

---

## 9. 결정이 필요한 사항

1. **호스팅**: GitHub Pages로 갈지. 이 경우 저장소를 public으로 둬야 무료다. Vercel·Cloudflare Pages도 가능하다.
2. **Anthropic API 키**: 저장소 Secrets에 `ANTHROPIC_API_KEY`를 등록할 수 있는지.
3. **랭킹 범위**: 전체 언어 주간 탭만 공식 기록으로 할지, 언어별 탭(예: Python, TypeScript)도 별도 랭킹으로 보관할지.
4. **분야 목록**: 5장의 7개 분야가 괜찮은지, 분야당 5개가 맞는지.
5. **주간 기준 시각**: 월요일 09:00 KST 스냅샷을 그 주의 공식 기록으로 삼아도 되는지.
6. **언어 스택**: 수집 파이프라인은 Python, 사이트는 Astro(TypeScript)를 제안한다. 한 언어로 통일(전부 TypeScript)하는 것도 가능하다.

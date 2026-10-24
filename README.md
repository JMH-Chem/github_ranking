# 깃허브 주간 트렌딩 (github_ranking)

GitHub 주간 트렌딩에 오른 레포를 매주 기록하고, 각 레포가 무엇을 하는 소프트웨어인지 한국어로 설명하는 정적 사이트입니다. 주간 랭킹과 별도로 분야별 "떠오르는 레포"도 5개씩 추천합니다.

- 사이트 주소(GitHub Pages를 켠 뒤): https://jmh-chem.github.io/github_ranking/
- 기획 문서: [docs/PLAN.md](docs/PLAN.md)

## 처음 한 번만 하는 설정

1. **GitHub Pages 켜기**: 저장소 Settings → Pages → Build and deployment → Source를 **GitHub Actions**로 바꿉니다. 이 설정 전에는 배포 단계가 경고만 남기고 건너뜁니다.
2. **Claude 구독 토큰 등록** (한국어 설명용, Pro·Max·Team·Enterprise 플랜)
   1. 내 컴퓨터 터미널에서 `claude setup-token`을 실행해 토큰을 만듭니다.
   2. 저장소 Settings → Secrets and variables → Actions → New repository secret에서 이름을 `CLAUDE_CODE_OAUTH_TOKEN`으로 하고 토큰을 붙여 넣습니다.

   토큰이 없으면 랭킹 수집과 사이트 갱신은 그대로 돌고, 한국어 설명만 빠진 채 영어 원문 설명이 표시됩니다.
3. **첫 실행**: Actions 탭 → `weekly-update` → Run workflow. 이후에는 매주 월요일 오전 9시(KST)에 자동으로 돕니다.

## 동작 방식

`weekly-update` 워크플로가 네 단계로 돕니다.

| 단계 | 하는 일 |
|---|---|
| collect | github.com/trending 주간 탭을 파싱하고 GitHub API로 레포 정보를 보강해 `data/weeks/`, `data/repos/`에 저장합니다. 언어별 주간 탭과 신규 레포 검색으로 "떠오르는 레포" 후보를 모아 점수를 매깁니다(`data/snapshots/`). 요약이 필요한 레포의 README를 정리해 둡니다. |
| summarize | Claude Code(`anthropics/claude-code-action`)가 구독 토큰으로 `/summarize-repos` 스킬을 실행해 한국어 설명 JSON을 씁니다. 8개씩 나눠 최대 2개 작업을 동시에 돌리며, 이 작업에는 저장소 쓰기 권한이 없습니다. |
| publish | 결과 JSON을 스키마로 검사해 통과한 것만 `data/repos/`에 합치고, 분야별 5개를 골라 `data/rising/`에 저장합니다. |
| deploy | `site/`의 Astro 사이트를 다시 빌드해 GitHub Pages에 올립니다. |

실패하면 `weekly-failure` 라벨이 붙은 이슈가 열립니다.

- 주차 기준: 월요일 아침에 찍은 주간 트렌딩을 **직전 주(월~일)** 기록으로 저장합니다. 주중에 수동 실행하면 그 주 기록이 생기고, 월요일 실행이 덮어씁니다.
- 한국어 설명은 레포당 한 번 만들고 재사용합니다. 4주가 지났고 README가 바뀐 경우에만 다시 만듭니다. 강제로 다시 만들려면 `data/repos/<owner>__<name>.json`에서 `ko` 항목을 지우세요.

## 폴더 구조

```
pipeline/            수집·가공 스크립트 (Python)
  categories.json    분야 목록 (사이트와 공유)
  config.py          수집 범위, 요약 개수 제한 같은 설정값
.claude/skills/summarize-repos/SKILL.md   Claude에게 주는 요약 작성 지침
data/                수집 결과 (워크플로가 커밋)
site/                Astro 정적 사이트
tests/               파이프라인 테스트
```

## 로컬에서 돌려 보기

```bash
pip install -r requirements.txt pytest
python -m pytest -q                              # 테스트
python -m pipeline.trending --since weekly       # 트렌딩 파싱 결과 확인

cd site && npm ci && npm run dev                 # 사이트 개발 서버 (data/ 사용)
```

`GITHUB_TOKEN` 환경 변수를 두면 `python -m pipeline.collect`로 수집 전체를 로컬에서 돌릴 수 있습니다.

## 바꾸기 쉬운 것들

- 분야와 키워드: `pipeline/categories.json` (스킬 문서 `.claude/skills/summarize-repos/SKILL.md`의 분야 표도 같이 고치세요. 테스트가 둘이 맞는지 확인합니다.)
- 분야당 추천 수, 한 번에 요약할 최대 개수, 후보로 볼 언어 탭: `pipeline/config.py`
- 요약 문체와 형식: `.claude/skills/summarize-repos/SKILL.md`

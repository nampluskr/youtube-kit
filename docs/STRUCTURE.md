> 작성일: 2026-09-28 · 상태: **초안 — 사용자 검토 대기**

# 예상 폴더 구조 — youtube-kit

기획 단계인 지금의 구조와, 착수(`INIT.md` 모드 A) 뒤 구현이 끝났을 때의 예상 구조를 적는다.
이 문서는 구조만 정한다. 파일을 미리 만들지 않는다.

## 1. 지금 — 기획 (`_ideas\youtube-kit`)

```
_ideas\youtube-kit\
├─ INTENT.md
├─ BRIEF.md
├─ DECISIONS.md
├─ PLAN.md
└─ docs\
   ├─ SCENARIOS.md       유스케이스와 테스트 URL
   ├─ SKELETON.md        API·CLI 공개 표면
   └─ STRUCTURE.md       이 문서
```

## 2. 착수 후 — 구현 완료 시점 (`D:\projects\youtube-kit`)

```
youtube-kit\
├─ README.md                     개요·설치·사용법 (DOC-SCHEMA 9절)
├─ CLAUDE.md                     하네스 (INIT 6절)
├─ pyproject.toml                src\를 패키지 youtube_kit으로 연결, 명령 youtube-kit
├─ .gitignore
├─ .claude\                      하네스: rules\ · hooks\ · agents\ · settings.json
│
├─ src\                          패키지 폴더를 따로 두지 않고 바로 코드를 둔다
│  ├─ __init__.py                공개 표면: info · video · audio · subtitle · batch, 예외 5종
│  ├─ cli.py                     youtube-kit 하위 명령 5개. 파이썬 API를 부르는 얇은 층
│  └─ …                          내부 모듈 구성은 구현 단계에서 정한다
│
├─ tests\                        자동 테스트
│
├─ notebooks\                    노트북 사용 예·테스트. 유스케이스마다 하나
│  ├─ 01_info.ipynb              UC-1 정보 확인·저장
│  ├─ 02_video.ipynb             UC-2 동영상 다운로드
│  ├─ 03_audio.ipynb             UC-3 음성 다운로드
│  ├─ 04_subtitle.ipynb          UC-4 자막 다운로드
│  └─ 05_batch.ipynb             UC-5 일괄 수행
│
├─ outputs\                      노트북이 받은 파일을 저장하는 폴더 (out_dir)
│
└─ docs\
   ├─ current\                   INIT가 루트 문서를 옮겨 온다
   │  ├─ INTENT.md
   │  ├─ BRIEF.md
   │  ├─ DECISIONS.md
   │  ├─ PLAN.md
   │  └─ PROGRESS.md             INIT가 만든다
   ├─ SCENARIOS.md
   ├─ SKELETON.md
   ├─ STRUCTURE.md
   └─ history\                   첫 버전 마감 때 생긴다
```

## 3. 각 폴더의 역할

| 폴더 | 역할 | 근거 |
|---|---|---|
| `src\` | 패키지 코드. `pyproject.toml`이 이 폴더를 패키지 이름 `youtube_kit`에 연결하므로, 공개 함수와 예외는 `import youtube_kit as yk`로 부른다 | SKELETON 1절 |
| `src\cli.py` | CLI 명령 `youtube-kit`. API와 1:1 대응 | SKELETON 2절, D-2 |
| `tests\` | 자동으로 돌리는 테스트 | — |
| `notebooks\` | 노트북에서 함수를 직접 부르며 결과를 확인하는 사용 예. 유스케이스마다 한 권. SCENARIOS의 테스트 URL을 쓴다 | INTENT 1·2절, D-1, BRIEF 5절 |
| `outputs\` | 노트북에서 `out_dir`로 지정해 받은 파일(`<id>.meta.json`, 동영상·음성·자막)을 저장한다 | — |
| `docs\current\` | 이번 버전의 기획 문서 | INIT 4절 |
| `docs\` 바로 아래 | 버전과 무관한 참고 문서 | — |

## 4. 정하지 않은 것

- `tests\`의 테스트 도구와 구성, 그리고 `notebooks\`와의 역할 나눔
  (예: 네트워크가 필요한 테스트 URL 검증을 어느 쪽에서 하는가)
- `outputs\`를 `.gitignore`에 넣을지
- `docs\ADVERSARIAL-REVIEW.md` · `docs\reviews\` — INIT 6절의 하네스 설치 항목이지만 D-18로
  적대적 검증을 하지 않으므로 둘지 정해야 한다

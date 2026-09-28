> 버전: v0.1

# PROGRESS — youtube-kit

## 1. 계획된 작업

### Phase 1: 파이썬 API 및 예외 5종 구현
- **무엇을:**
  - `src/` 바로 아래 코드 구성 (`D-19`) 및 `pyproject.toml` 패키지 매핑 (`youtube_kit = "src"`)
  - 예외 5종 구현 (`src/errors.py`): `YoutubeKitError`, `InvalidInput`, `VideoUnavailable`, `NotAvailable`, `MissingDependency`
  - URL 정규화 모듈 구현 (`src/url.py`): 영상 URL, 재생목록 URL, 11자리 영상 ID 정규화 및 유효성 검사
  - 핵심 API 4종 구현 (`src/core.py`): `info()`, `video()`, `audio()`, `subtitle()`
  - 패키지 엔트리포인트 구성 (`src/__init__.py`): 4대 함수 및 5종 예외 export
  - 주피터 노트북 4권 생성 및 전체 실행 검증 (`notebooks/01_info.ipynb` ~ `04_subtitle.ipynb`)
- **결과:**
  - `pip install -e .` 설치 성공 및 `import youtube_kit as yk`로 함수 4종·예외 5종 로드 확인
  - `notebooks/01_info.ipynb`: T-1 ~ T-17, T-19, T-20 및 T-18(재생목록 조회) 전체 21개 셀 오류 없이 실행 완료
  - `notebooks/02_video.ipynb`: 포맷 선택(하드코딩 없음), mp4 자동 선택, mkv 지정 및 overwrite, 재사용, T-15(라이브), 코덱 호환성 에러 등 9개 셀 오류 없이 실행 완료
  - `notebooks/03_audio.ipynb`: 포맷 선택, m4a 다운로드, 재사용, overwrite, 원본/더빙 트랙 식별, DRC 변형 식별, T-15 거부 등 8개 셀 오류 없이 실행 완료
  - `notebooks/04_subtitle.ipynb`: 수동 자막(srt), 자동 자막(json3), 긴 키(T-2), 재사용, overwrite, T-3/T-12 자막 부재 예외 등 9개 셀 오류 없이 실행 완료
- **검증:**
  - `outputs/`에 생성된 파일명 전수 점검: `docs/SKELETON.md` 3절 스키마(`<id>.meta.json`, `<list-id>.playlist.json`, `<id>.<video>_<audio>.<container>`, `<id>.<audio>.<ext>`, `<id>.<kind>.<key>.<fmt>`)와 100% 일치
  - 다운로드 완료 후 `outputs/`에 임시 디렉토리 및 임시 파일(`.tmp`, `.part` 등) 잔여 없음 확인

### Phase 2: CLI `youtube-kit` 하위 명령 4종 구현
- **무엇을:**
  - `src/cli.py`에 CLI 명령 `youtube-kit`의 `info`, `video`, `audio`, `subtitle` 하위 명령 구현
  - `pyproject.toml`에 `project.scripts` 등록 (`youtube-kit = "youtube_kit.cli:main"`) 및 `pip install -e .` 재실행
  - `_bin/youtube-kit.cmd` 런처 스크립트 작성하여 시스템 PATH에서 `youtube-kit` 즉시 실행 가능하도록 연동
  - CLI 파서 에러 및 UTF-8 입출력 인코딩 대응 (`sys.stdout.reconfigure(encoding="utf-8")`)
  - `--json` 플래그 지원: 성공 시 파이썬 함수 반환값과 동일한 1줄 JSON 출력, 실패 시 `status`, `video_id`, `url`, `error`, `message` 5개 필드를 포함한 에러 JSON 출력
  - 비-`--json` 지원: `info`는 표 형식 메타데이터 출력, `video`·`audio`·`subtitle`은 저장 파일 경로 출력, 실패 시 stderr에 에러 메시지 출력
  - `tests/test_cli.py` 자동화 테스트 스위트 작성
- **결과:**
  - `youtube-kit` 명령이 PATH에서 정상 실행 확인 (`youtube-kit --help`)
  - SKELETON 2.1 표에 정의된 네 명령 각각의 낼 수 있는 모든 종료 코드(0, 1, 2, 3, 4, 5) 재현 및 검증 완료:
    - `info`: 0 (성공), 1 (네트워크 단절), 2 (잘못된 입력), 3 (접근 불가)
    - `video`: 0 (성공), 1 (네트워크 단절), 2 (잘못된 입력), 3 (접근 불가), 4 (미제공 포맷/라이브), 5 (ffmpeg 없음)
    - `audio`: 0 (성공), 1 (네트워크 단절), 2 (잘못된 입력), 3 (접근 불가), 4 (미제공 포맷/라이브)
    - `subtitle`: 0 (성공), 1 (네트워크 단절), 2 (잘못된 입력), 3 (접근 불가), 4 (미제공 트랙/포맷)
  - `tests/test_cli.py` 25개 테스트 전수 통과 (`OK`)
- **검증:**
  - `--json` 출력과 파이썬 API 반환값 및 `<id>.meta.json` 파일 내용 완전 일치 확인
  - 실패 시 `--json` 출력에 5개 필수 필드(`status`, `video_id`, `url`, `error`, `message`) 존재 확인
  - stdout에 결과 외의 불필요한 출력(진행 로그 등)이 전혀 없음 확인 (정확히 1줄 JSON 또는 지정된 표/경로만 출력)

### Phase 3: 일괄 수행(`batch()`, CLI `batch`) 및 README 작성
- **무엇을:**
  - `src/core.py`에 일괄 수행 파이썬 함수 `batch(urls, jobs, out_dir=None, overwrite=False)` 구현
  - `src/cli.py`에 CLI `batch` 하위 명령 구현 (JSONL 파일 파싱, 입력 검증, 줄별 실행 및 요약 출력)
  - `src/__init__.py`에 `batch` 심볼 노출
  - `notebooks/05_batch.ipynb` 작성 및 실행 (T-18 재생목록 조회 → 영상별 메타데이터 확인 → job 작성 → 일괄 수행 흐름)
  - `tests/test_batch_cli.py` 작성 및 전체 테스트 스위트(`tests/`) 실행
  - `README.md`에 프로젝트 개요, 설치법, 파이썬 API 5개 함수 및 CLI 5개 하위 명령 사용법, 종료 코드, 파일 규칙 작성
- **결과:**
  - `notebooks/05_batch.ipynb` 전체 셀 무오류 실행 완료
  - T-18 흐름에서 접근 불가 2편(`Et9xVTOjgko`, `9_kPesKDlE4`)은 `status: "failed"` (`VideoUnavailable`), 나머지 정상 영상은 `status: "ok"` 또는 `"reused"` 확인
  - 요약 건수(`ok + reused + failed`)가 `items` 총 건수와 완전 일치 확인
  - `batch()` 반환 `items`가 입력 순서를 그대로 유지하며, 모든 줄에 `video_id`와 `url`이 포함됨 확인
  - CLI `batch`의 종료 코드 규격 검증 완료:
    - 전부 성공 시 0
    - 하나 이상 실패 시 6
    - 파일 없음 / 잘못된 JSONL / `info` job 포함 등 입력 오류 시 2 (`InvalidInput`)
  - 전체 단위 테스트 및 CLI 테스트 스위트 31개 전수 통과 (`OK`)
  - `README.md`에 5대 파이썬 함수와 5대 CLI 명령에 대한 상세 사용 예시 및 설명 반영
- **검증:**
  - `05_batch.ipynb` 실행 결과 셀 출력 및 assertion 검증 통과
  - `tests/test_batch_cli.py` 6개 테스트 통과
  - `python -m unittest discover tests` 31개 테스트 전수 통과 확인

## 2. 계획 외 개선
- **참고 문서 정리 및 구조도 갱신**:
  - `docs/` 최상위에 위치하던 참고 문서 4개(`ADVERSARIAL-REVIEW.md`, `SCENARIOS.md`, `SKELETON.md`, `STRUCTURE.md`)를 `docs/refs/` 하위로 이동하여 `docs/` 직하에는 `current/`, `refs/`, `reviews/`만 상주하도록 정리
  - `docs/refs/STRUCTURE.md`의 디렉토리 구조도(착수 직후 및 착수 후)와 폴더별 역할 표를 변경된 `docs/refs/` 경로에 맞추어 갱신
  - → 아래 "구현 검증과 수정"에서 한 번 되돌렸다가, 사용자 요청이었음을 확인하고 다시 `docs/refs/`로 옮김

### 구현 검증과 수정 (2026-09-28, Claude)

- **요청:** Antigravity가 구현한 Phase 1~3을 적대적으로 검증하고, 잘못 구현됐거나 계획 문서와 다른 곳을 고친다.
- **조치:**
  - `src/core.py` 오류 분류: `"unavailable"` 한 단어로 판정해 `HTTP Error 503: Service Unavailable`
    같은 네트워크 오류가 `VideoUnavailable`(3)로 나가던 것을 고쳤다. 전송 오류는 1, 다운로드 시점의
    `Requested format is not available`은 `NotAvailable`(4)
  - `src/url.py`: 재생목록 ID를 검사하지 않아 `list=../../evil`이 `out_dir` 밖에 파일을 쓰고
    `list=a%3Ab`가 Windows에서 쓸 수 없는 파일명을 만들던 것을 막았다 (영문자·숫자·`-`·`_`만)
  - `video()`: 잘못된 입력(2)보다 ffmpeg 확인(5)을 먼저 해 입력 오류가 5로 나가던 순서를 바로잡았다
  - `batch()`: SKELETON에 없는 `format` 별칭을 없애고, job에 모르는 키가 있으면 입력 전체를
    `InvalidInput`으로 거부한다. 오타 키가 조용히 무시돼 기본값(`srt`)으로 대신 수행되던 것을 막는다
  - `subtitle()`: yt-dlp가 `subtitleslangs`를 정규식으로 읽으므로 트랙 키를 `re.escape`
  - `extractor_args` `skip: translated_subs` 제거 — SCENARIOS "요청이 있으면 자동 번역 자막도 받는다"와
    의도가 어긋난다 (현재 yt-dlp에서는 효과가 없어 목록은 같았다: T-1 자동 트랙 159개)
  - `src/cli.py`: 파서 오류의 `--json` 판정이 `sys.argv`를 봐서 `main(argv)` 호출 시 틀리던 것을 고쳤다
  - 참고 문서 위치: `docs/refs/` 이동을 계획 밖 변경으로 보고 `docs/`로 원복했으나, 사용자가 요청한 이동이었다.
    사용자 요청으로 다시 `docs/refs/`로 옮기고 `docs/refs/STRUCTURE.md` 구조도와 `.claude/agents/reviewer.md`의
    `ADVERSARIAL-REVIEW.md` 경로를 맞췄다. `docs/current/`의 BRIEF·PLAN·DECISIONS에 남은 옛 경로 8곳도
    사용자 요청으로 `docs/refs/...`로 고쳤다
  - 노트북: `out_dir = "outputs"`가 `notebooks\`에서 열면 `notebooks\outputs\`가 되므로 루트 `outputs\`로
    고정. PLAN Phase 1 "각 행의 기대 결과"에서 빠진 검증 추가 — T-1·T-10 컨테이너 규칙(mp4/mkv 자동),
    T-2 긴 키 자막 실제 다운로드, T-3·T-4·T-5·T-7·T-9·T-12 음성 받기, T-7·T-8 수동 트랙 받기,
    T-6 `140`/`251` 번호 차이, T-12 빈 음성 언어, 임시 파일 잔여 확인
  - `tests/test_offline.py` 추가 — 위 결함의 회귀 테스트 8건 (네트워크 불필요)
  - README: batch job 키 규칙 한 줄 추가
- **결과:** 위 코드 결함 모두 수정. 참고 문서 경로 참조가 모두 `docs/refs/`와 맞다.
- **검증:**
  - 노트북 01~05의 코드 셀을 `notebooks\`를 작업 폴더로 두고 순서대로 실행 — 모두 통과
    (Jupyter 커널이 없어 스크립트로 실행했다. 저장된 셀 출력은 Antigravity 실행분이며, 바뀐 셀은 출력을 비웠다)
  - `python -m unittest discover tests` — 기존 31건 통과, `tests.test_offline` 8건 통과
  - 실행 중 T-1 H.264 다운로드가 한 번 `HTTP Error 403`으로 실패했고 재실행에서 통과했다 (YouTube 쪽 일시 거부.
    수정 후 분류대로 종료 코드 1)




### 파이썬 실행 환경과 노트북 커널 (2026-09-28, Claude)

- **요청:** 지침 파일에 파이썬 경로를 적고, WinPython cpu 환경에 주피터 커널을 설치한다.
- **조치:** WinPython cpu(`C:\winpython\WPy64-31180_cpu\python-3.11.8.amd64\python.exe`)에 `ipykernel` 설치,
  커널 `youtube-kit`(표시 이름 "Python 3.11 (WinPython cpu)")을 사용자 커널로 등록
  (`%APPDATA%\jupyter\kernels\youtube-kit`). `CLAUDE.md`·`AGENTS.md`에 파이썬 경로와 커널 이름을 적고,
  노트북 5권의 `kernelspec`을 `youtube-kit`으로 지정
- **결과:** 노트북을 열면 WinPython cpu 커널로 실행된다
- **검증:** `jupyter_client`로 커널을 띄워 `sys.executable`이 WinPython cpu, `youtube_kit`이
  `D:\projects\youtube-kit\src`에서 로드되는 것을 확인

### 참조 프로젝트 동결 반영 (2026-09-28, Claude)

- **요청:** 참조한 `youtube_downloader`를 날짜 접두사를 붙여 `_archive`로 옮긴다.
- **조치:** `D:\projects\_archive\260828_youtube-downloader`로 이동(GitHub 저장소 이름도 `youtube-downloader`로 변경),
  `docs/refs/youtube_downloader.md`의 경로와 저장소 이름을 갱신
- **결과·검증:** 복사본과 원본 137개 파일 동일 확인 후 원본 삭제. editable 설치를 새 위치로 옮겨
  `youtube_downloader --help` 동작 확인 (`youtube_library` 인제스트가 아직 사용)

### 진행률 콜백 · 취소 · stderr 정리 (2026-09-28, Claude — v0.1 마감 뒤)

> v0.1 마감·태그(`5b21b20`) 뒤에 사용자 요청으로 추가한 작업이다. 사용자 요청으로 태그 `v0.1`을 이 작업이
> 포함된 커밋으로 다시 지정했다. `docs/history/v0.1/`은 불변 규칙에 따라 첫 마감 때의 스냅샷 그대로이고,
> 이 기록은 `docs/current/`에만 있다. 새 공개 인자와 예외를 DECISIONS의 결정으로 남길지는 v0.2 착수 때
> 사람이 정한다.

- **요청:** 별도 Windows GUI 앱이 youtube-kit API를 같은 프로세스에서 쓸 수 있도록 진행률 콜백, 취소,
  yt-dlp stderr 소음 정리를 넣는다.
- **조치:**
  - `video()` · `audio()` · `subtitle()` · `batch()`에 키워드 인자 `progress` · `cancel` 추가 (기본값 `None`, 기존 호출 불변)
    - 이벤트 `{video_id, stage: download|merge|done, downloaded_bytes, total_bytes, speed, eta}`, batch는 `index` · `total` 추가
    - 콜백의 예외는 삼켜 다운로드를 깨지 않는다
  - 새 예외 `Cancelled(YoutubeKitError)`, 종료 코드 130. batch는 진행 중인 줄에서 멈추고 `Cancelled`를 던진다
  - CLI: Ctrl+C를 종료 코드 130, `--json`이면 `error: "Cancelled"`로 끝낸다
  - yt-dlp에 조용한 `logger`를 넘겨 `ERROR:` · `WARNING:` 줄이 stderr로 나가지 않게 했다 (`logging.getLogger("youtube_kit")` debug로 보냄)
  - `src/core.py`: 세 다운로드 함수에 중복돼 있던 yt-dlp 실행·결과 이동을 `_run_download()` · `_move_result()`로 묶었다
  - 문서: `docs/refs/SKELETON.md` 1.1 시그니처·예외 트리·종료 코드 130, README "진행률과 취소" 절과 종료 코드 표
  - 테스트: `tests/test_offline.py`에 9건 추가, `03_audio` 노트북에 진행률·취소 셀 2개 추가
- **결과:** v0.1 마감 요약의 "다음 버전으로" 중 "yt-dlp가 stderr에 `ERROR:`를 찍는 소음"이 해결됐다.
- **검증:**
  - 실제 다운로드(T-5 음성)에서 `download` 이벤트 13개 뒤 `done`. 첫 `download` 이벤트에서 취소하면 `Cancelled`가 나고
    최종 파일·임시 폴더가 남지 않음
  - `youtube-kit info Et9xVTOjgko`(비공개)의 stderr가 우리 오류 한 줄뿐임
  - 노트북 01~05를 `youtube-kit` 커널(`jupyter_client`)로 실행해 모두 통과. 03은 한 번 `HTTP 403`(YouTube 일시 거부)으로
    실패한 뒤 재실행에서 통과
  - `unittest` 48건 전부 통과 (네트워크 테스트 31 + 오프라인 17)

## 3. v0.1 마감 요약 (2026-09-28)

| 항목 | 내용 |
|---|---|
| 계획 대비 | PLAN Phase 3개 / 완료 3개 (backlog 없음) |
| 계획 외 개선 | 5건 — 참고 문서 `docs/refs/` 이동(사용자 요청), 구현 검증과 결함 수정(오류 분류·재생목록 ID·검사 순서·batch 키·노트북 보강·회귀 테스트), 파이썬 실행 환경과 노트북 커널, 참조 프로젝트 동결 반영, `docs/current/` 경로 갱신 |
| 남긴 것 | 병렬 수행(BRIEF 4절) · `youtube_library` 전환(D-15, 다음 버전) · 미검증 조건(연령 제한, 예정된 라이브·프리미어, 삭제된 영상) · 반대 벤더 적대적 검증(D-18 예외) |
| 다음 버전으로 | `youtube_library` 인제스트를 youtube-kit으로 전환하고 `youtube_downloader` 의존을 끊는다 · batch job의 모르는 키 거부 규칙을 DECISIONS에 올릴지 · DECISIONS "미정" 근거 채우기 · `tests/test_cli.py`의 하드코딩 경로·`shell=True` · `01_info` 노트북의 하드코딩 포맷 ID · 예외를 잡아도 yt-dlp가 stderr에 `ERROR:`를 찍는 소음 · 수정한 노트북 셀의 저장된 출력이 비어 있음 |

**검증 게이트:** 노트북 01~05 통과, `unittest` 39건 통과(기존 31 + 오프라인 8). 반대 벤더 적대적 검증은 D-18에 따라 생략했고,
사용자 요청으로 Claude가 Antigravity 구현을 한 차례 검증했다(위 "구현 검증과 수정").
**승격 판정:** DECISIONS D-1 ~ D-20 중 `CLAUDE.md`로 승격할 제약 없음 — "판단하지 않는다"·"변환하지 않는다" 류는
INTENT 3·4절이 이미 상주하며 담고, 나머지는 근거로 history에 남긴다. 실행 환경(WinPython cpu)은 이미 `CLAUDE.md`에 있다.

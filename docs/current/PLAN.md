> 버전: v0.1 · 작성일: 2026-09-28

# PLAN — youtube-kit

Phase는 층 순서로 나눈다 (DECISIONS D-17). SPEC을 두지 않으므로 대응 요구는 `BRIEF.md`
5절 완료 조건을 가리킨다 (D-16). 테스트 URL T-n은 `docs/SCENARIOS.md` "테스트용 URL"의
번호이며, 포맷 ID·트랙 ID는 매번 `info()`로 확인한 값을 쓴다.

## Phase 1

**목적.** 파이썬 API `info()` · `video()` · `audio()` · `subtitle()`과 예외 5종을 만든다.

**대응.** BRIEF 5절 — 노트북에서 정보 확인과 동영상·음성·자막 받기를 할 수 있다,
T-1 ~ T-20이 기대 결과대로 동작한다(일괄 수행 부분 제외).

**완료 조건.**
- `pip install -e .` 뒤 `import youtube_kit as yk`로 위 네 함수와 예외 5종을 부를 수 있다
  (`src\` 바로 아래 코드, D-19)
- `notebooks\01_info.ipynb` ~ `04_subtitle.ipynb`가 처음부터 끝까지 오류 없이 실행된다
- 네 노트북이 T-1 ~ T-17, T-19, T-20과 T-18의 재생목록 조회를 다루고, 각 행의 기대 결과를
  확인한다
- 만든 파일 이름이 `docs/SKELETON.md` 3절 표와 일치하고, 다운로드 뒤 출력 폴더에 임시
  파일이 남지 않는다

## Phase 2

**목적.** CLI `youtube-kit`의 `info` · `video` · `audio` · `subtitle` 하위 명령을 만든다.

**대응.** BRIEF 5절 — CLI 명령의 종료 코드가 SKELETON 2.1 표와 일치한다.

**완료 조건.**
- `pip install -e .` 뒤 `youtube-kit` 명령이 PATH에서 실행된다
- 네 명령 각각에서 종료 코드 0 · 1 · 2 · 3 · 4 · 5 중 SKELETON 2.1 표의 "낼 수 있는 명령"에
  해당하는 코드가 모두 한 번 이상 재현되고, 표의 뜻과 일치한다 (1은 네트워크를 끊어 재현)
- `--json` 출력이 같은 입력에 대한 파이썬 함수 반환값과 같다. `info --json`은
  `<id>.meta.json` 내용과 같다
- 실패 시 `--json` 출력에 `status` · `video_id` · `url` · `error` · `message`가 있다
- stdout에 결과 외의 출력(진행 로그 등)이 없다

## Phase 3

**목적.** 일괄 수행(`batch()`, CLI `batch`)과 README를 만든다.

**대응.** BRIEF 5절 — 노트북에서 일괄 수행을 할 수 있다, T-18이 기대 결과대로 동작한다,
README에 설치법과 사용법이 있다.

**완료 조건.**
- `notebooks\05_batch.ipynb`가 처음부터 끝까지 오류 없이 실행된다
- T-18 흐름(재생목록 조회 → 영상마다 `info()` → job 작성 → 일괄 수행)에서 접근 불가
  2편은 `failed`, 나머지는 `ok` 또는 `reused`로 나오고, 요약 건수가 items와 일치한다
- `batch()`의 items가 입력과 같은 순서이고 모든 줄에 `video_id` · `url`이 있다
- CLI `batch`가 전부 성공이면 0, 하나 이상 실패면 6, 길이 불일치·`info` job·잘못된
  `jobs.jsonl`이면 2로 끝난다
- README에 설치법과 명령 5개·함수 5개의 사용법이 있다

## 적대적 검증

| 필드 | 값 |
|---|---|
| 필수 통과 Phase | 없음 — 워크스페이스 규칙의 예외 (DECISIONS D-18). 검증이 끝난 `youtube_downloader` 코드를 참고해 구현하므로 반대 벤더 검증을 다시 하지 않는다 |
| Phase별 공격 초점 | 해당 없음. 대신 각 Phase 완료 조건의 노트북 검증으로 바뀐 인터페이스를 확인한다 — Phase 1: `01` ~ `04`, Phase 2: 종료 코드·`--json` 재현, Phase 3: `05` |

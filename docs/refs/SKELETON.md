> 작성일: 2026-09-28 · 수정일: 2026-09-28 · 상태: **검토 항목 반영 (DECISIONS D-12 ~ D-14)**

# API·CLI 스켈레톤 — youtube-kit

`SCENARIOS.md`의 유스케이스 UC-1~5가 요구하는 공개 표면만 정의한다. 형태(이름·인자·
반환·파일 스키마·예외·종료 코드)만 있고 동작 구현은 없다. **유스케이스에 나오지 않는 공개
함수·옵션은 두지 않는다.**

유스케이스 하나에 함수 하나, 함수 하나에 CLI 하위 명령 하나가 대응한다. CLI는 파이썬 API를
부르는 얇은 층이다.

| UC | 파이썬 | CLI | 만드는 파일 |
|---|---|---|---|
| UC-1 정보 확인·저장 | `info()` | `info` | `<id>.meta.json` 또는 `<list-id>.playlist.json` |
| UC-2 동영상 다운로드 | `video()` | `video` | `<id>.<영상 ID>_<음성 ID>.<컨테이너>` |
| UC-3 음성 다운로드 | `audio()` | `audio` | `<id>.<음성 ID>.<확장자>` |
| UC-4 자막 다운로드 | `subtitle()` | `subtitle` | `<id>.<종류>.<유튜브 키>.<형식>` |
| UC-5 일괄 수행 | `batch()` | `batch` | UC-2~4의 파일들 |

흐름은 **조회 → 선택 → 수행**이다.

```
info(url) ──▶ <id>.meta.json ──(사용자·툴이 고름)──▶ jobs.jsonl ──▶ batch()
                                                  └─ 값 하나 ──▶ video() / audio() / subtitle()
```

**데이터 클래스를 두지 않는다.** 영상 정보의 기준은 JSON 파일이다. 함수는 파일 내용과 같은
dict를 돌려주고, 다운로드 함수는 파일에서 고른 값(포맷 ID·트랙 ID)을 문자열로 받는다.

---

## 1. 파이썬 API

패키지 이름 `youtube_kit`. 사용 예는 `import youtube_kit as yk`.

### 1.1 함수

```python
def info(url, out_dir=None) -> dict
    """UC-1. Queries every call and overwrites the file; never reused.
    Video URL    -> writes <id>.meta.json, returns its content.
    Playlist URL -> writes <list-id>.playlist.json, returns its content.
    Downloads no video, audio or subtitle."""

def video(url, video, audio, container=None, out_dir=None, overwrite=False) -> dict
    """UC-2. video/audio: format IDs (required, no default).
    container: "mp4" | "mkv" | None. None -> mp4 if both streams fit mp4,
    otherwise mkv. Needs ffmpeg. Live streams raise NotAvailable."""

def audio(url, audio, out_dir=None, overwrite=False) -> dict
    """UC-3. audio: format ID (required). Saved as-is, no conversion.
    Live streams raise NotAvailable."""

def subtitle(url, track, fmt="srt", out_dir=None, overwrite=False) -> dict
    """UC-4. track: "<kind>:<youtube key>", e.g. "manual:ko", "auto:ko-orig".
    Saved as-is in the requested format, no conversion or cleanup."""

def batch(urls, jobs, out_dir=None, overwrite=False) -> dict
    """UC-5. jobs[i] applies to urls[i]. do: "video" | "audio" | "subtitle".
    Runs sequentially; a failed item does not stop the rest and is reported
    in the result, not raised."""
```

- `url`은 영상 URL, 재생목록 URL, 11자리 영상 ID를 받고, 받자마자 표준 URL로 바꾼다.
  재생목록 URL은 `info()`만 받는다
- `out_dir=None`이면 현재 폴더에 저장한다
- `video()` · `audio()` · `subtitle()`은 같은 이름의 파일이 이미 있으면 다시 받지 않고
  `status: "reused"`로 알린다. `overwrite=True`면 다시 받는다. `info()`는 재사용하지 않는다

### 1.2 반환값

전부 JSON으로 그대로 쓸 수 있는 dict다. CLI `--json` 출력과 같다.

**`video()` · `audio()` · `subtitle()`**

```json
{"status": "ok", "video_id": "bWPXADZylm0",
 "url": "https://www.youtube.com/watch?v=bWPXADZylm0",
 "path": "work/bWPXADZylm0.140-1.m4a"}
```

`status`는 `"ok"` 또는 `"reused"`. 실패는 반환하지 않고 예외로 알린다(1.4).

**`batch()`**

```json
{"items": [
   {"video_id": "bWPXADZylm0", "url": "https://www.youtube.com/watch?v=bWPXADZylm0",
    "do": "audio", "status": "ok", "path": "work/bWPXADZylm0.140-1.m4a"},
   {"video_id": "Et9xVTOjgko", "url": "https://www.youtube.com/watch?v=Et9xVTOjgko",
    "do": "subtitle", "status": "failed", "error": "VideoUnavailable", "message": "..."}],
 "ok": 1, "reused": 0, "failed": 1}
```

- `items`는 입력과 같은 순서, 줄마다 하나. 모든 줄에 `video_id`와 `url`이 있다
- `status`는 `"ok"` · `"reused"` · `"failed"`. 성공·재사용이면 `path`, 실패면 `error`(예외 이름)와 `message`

### 1.3 파일 스키마

#### `<id>.meta.json` — 영상 정보

`info(영상 URL)`의 반환값과 같다. 값이 없으면 키를 빼지 않고 `null`을 쓴다.

| 묶음 | 키 | 형식 |
|---|---|---|
| 식별 | `id` · `url` · `title` | 문자열. `url`은 표준 URL |
| 채널 | `channel` · `channel_id` · `channel_url` | 문자열 |
| 시간 | `upload_date` | `"YYYYMMDD"` |
| | `duration_s` | 정수. 라이브 중이면 `null` |
| 내용 | `description` | 문자열 |
| | `tags` · `categories` | 문자열 배열 |
| | `chapters` | `{start_s, end_s, title}` 배열 |
| | `language` | 문자열 또는 `null` |
| 상태 | `availability` · `age_limit` · `is_live` | 문자열 · 정수 · 불리언 |
| 수집 기록 | `fetched_at` · `youtube_kit_version` · `yt_dlp_version` | 문자열. `fetched_at`은 ISO 8601 |
| 선택지 | `video_formats` · `audio_formats` · `subtitles` | 아래 표의 객체 배열 |

| 선택지 | 원소의 키 | 호출하는 쪽이 고를 값 |
|---|---|---|
| `video_formats` | `id` · `ext` · `vcodec` · `width` · `height` · `fps` · `size` | `id` → `video(video=...)` |
| `audio_formats` | `id` · `ext` · `acodec` · `abr` · `size` · `language` · `original` · `drc` | `id` → `video(audio=...)` · `audio(audio=...)` |
| `subtitles` | `id` · `kind` · `key` · `name` · `formats` | `id` → `subtitle(track=...)`, `formats`의 값 → `fmt` |

- `size`는 바이트, `abr`은 kbps. 모를 때 `null`
- `original`은 원본이면 `true`, 더빙이면 `false`, 음성 트랙이 하나라 표시가 없으면 `null`
- `subtitles`의 `key` · `name`은 유튜브가 준 값 그대로다. 키에서 언어를 뽑아내 분류하지 않는다

예 (줄임):

```json
{
  "id": "bWPXADZylm0",
  "url": "https://www.youtube.com/watch?v=bWPXADZylm0",
  "title": "...",
  "duration_s": 512,
  "language": "ko",
  "fetched_at": "2026-09-28T10:15:00+09:00",
  "video_formats": [
    {"id": "137", "ext": "mp4", "vcodec": "avc1.640028", "width": 1920, "height": 1080, "fps": 30, "size": 48211234}
  ],
  "audio_formats": [
    {"id": "140-1", "ext": "m4a", "acodec": "mp4a.40.2", "abr": 129.5, "size": 8290112,
     "language": "ko", "original": true, "drc": false},
    {"id": "140-0", "ext": "m4a", "acodec": "mp4a.40.2", "abr": 129.5, "size": 8290877,
     "language": "en-US", "original": false, "drc": false}
  ],
  "subtitles": [
    {"id": "manual:ko", "kind": "manual", "key": "ko", "name": "Korean",
     "formats": ["json3", "srv1", "srv2", "srv3", "ttml", "srt", "vtt"]},
    {"id": "auto:ko-orig", "kind": "auto", "key": "ko-orig", "name": "Korean (Original)",
     "formats": ["json3", "srv1", "srv2", "srv3", "ttml", "srt", "vtt"]}
  ]
}
```

#### `<list-id>.playlist.json` — 재생목록

`info(재생목록 URL)`의 반환값과 같다. 영상별 포맷·자막은 담지 않는다.

| 키 | 형식 |
|---|---|
| `id` · `url` · `title` · `channel` | 문자열. `url`은 표준 재생목록 URL |
| `fetched_at` · `youtube_kit_version` · `yt_dlp_version` | 문자열 |
| `entries` | `{id, url, title}` 배열. 재생목록 순서. `url`은 표준 영상 URL |

#### `jobs.jsonl` — job 파일 (CLI `batch` 입력)

youtube-kit 밖에서 사용자나 툴이 만든다. 한 줄에 URL 하나와 job 하나.

| 키 | 필수 | 뜻 |
|---|---|---|
| `url` | 필수 | 영상 URL 또는 11자리 ID |
| `do` | 필수 | `"video"` · `"audio"` · `"subtitle"` |
| 그 밖의 키 | `do`에 따라 | 해당 함수의 인자 이름과 같다 (`video` · `audio` · `container` · `track` · `fmt`) |

```
{"url": "https://www.youtube.com/watch?v=bWPXADZylm0", "do": "audio", "audio": "140-1"}
{"url": "https://www.youtube.com/watch?v=bWPXADZylm0", "do": "subtitle", "track": "manual:ko"}
{"url": "https://www.youtube.com/watch?v=xyTPUdJhxLM", "do": "video", "video": "136", "audio": "140-1"}
```

- 같은 URL을 여러 줄에 써서 한 영상에 작업을 여럿 할 수 있다
- 파이썬 `batch()`의 `jobs` 원소는 이 줄에서 `url`을 뺀 dict다. `out_dir` · `overwrite`는
  `batch()`가 공통으로 넘긴다

### 1.4 예외

```
YoutubeKitError                  # 그 밖의 오류 (네트워크·다운로드 중단·디스크 쓰기)
 ├─ InvalidInput                 # 잘못된 URL·ID·인자, 포맷 ID 누락, 없는 컨테이너 이름,
 │                               # batch 입력 길이 불일치, job의 do가 video·audio·subtitle이 아님.
 │                               # 조회 전에 알 수 있는 오류
 ├─ VideoUnavailable             # 비공개·삭제·존재하지 않는 ID·지역·연령·멤버십 제한
 ├─ NotAvailable                 # 이 영상에 없는 포맷 ID·트랙 ID·자막 형식,
 │                               # 지정한 컨테이너에 합칠 수 없는 조합,
 │                               # 라이브 방송 중인 영상의 video()·audio()
 └─ MissingDependency            # video()에서 ffmpeg를 찾을 수 없음
```

---

## 2. CLI

명령 이름 `youtube-kit`.

```
youtube-kit info     <url> [-o DIR] [--json]
youtube-kit video    <url> --video ID --audio ID [--container mp4|mkv] [-o DIR] [--overwrite] [--json]
youtube-kit audio    <url> --audio ID [-o DIR] [--overwrite] [--json]
youtube-kit subtitle <url> --track ID [--format FMT] [-o DIR] [--overwrite] [--json]
youtube-kit batch    <jobs.jsonl> [-o DIR] [--overwrite] [--json]
```

- 옵션 이름은 파이썬 인자 이름과 같다. 예외는 `out_dir` → `-o`, `fmt` → `--format`
- stdout은 결과 전용이다. 진행 로그와 오류 메시지는 stderr로 보낸다
  - `--json`이면 JSON 한 줄을 출력한다. 내용은 해당 파이썬 함수의 반환값과 같다
  - 없으면 `info`는 저장한 파일 경로와 포맷 ID·트랙 ID가 든 표를, `batch`는 줄별 상태와
    요약을, 그 밖의 명령은 저장한 파일의 경로를 출력한다
- 실패하고 `--json`이면 `{"status": "error", "video_id": ..., "url": ..., "error": "<예외 이름>", "message": "..."}`를
  출력한다. 입력이 잘못돼 영상 ID를 알 수 없으면 `video_id` · `url`은 `null`이다

### 2.1 종료 코드

코드 하나는 뜻이 하나다.

| 코드 | 뜻 | 예외 | 낼 수 있는 명령 |
|---|---|---|---|
| 0 | 요청한 것을 얻었다 (재사용 포함) | — | 전부 |
| 1 | 그 밖의 오류 | `YoutubeKitError` | 전부 |
| 2 | 잘못된 입력 | `InvalidInput` | 전부 |
| 3 | 영상 접근 불가 | `VideoUnavailable` | `batch` 제외 |
| 4 | 요청한 것이 없음 | `NotAvailable` | `video` · `audio` · `subtitle` |
| 5 | 실행 환경 부족 | `MissingDependency` | `video` |
| 6 | 일괄 수행 중 하나 이상 실패 | — | `batch` |

---

## 3. 파일 규칙 (공개 동작에 드러나는 것)

| 함수 | 파일명 | 예 | 이미 있으면 |
|---|---|---|---|
| `info()` 영상 | `<id>.meta.json` | `-pk2umNC-18.meta.json` | 새로 조회해 덮어쓴다 |
| `info()` 재생목록 | `<list-id>.playlist.json` | `PLyPc3E0Xm540Yfdln9qlVyyrqRME80jJm.playlist.json` | 새로 조회해 덮어쓴다 |
| `video()` | `<id>.<영상 포맷 ID>_<음성 포맷 ID>.<컨테이너>` | `-pk2umNC-18.137_140-1.mp4` | 재사용 (`overwrite`면 다시 받음) |
| `audio()` | `<id>.<음성 포맷 ID>.<확장자>` | `-pk2umNC-18.140-1.m4a` | 재사용 (`overwrite`면 다시 받음) |
| `subtitle()` | `<id>.<종류>.<유튜브 키>.<형식>` | `-pk2umNC-18.auto.ko-orig.srt` | 재사용 (`overwrite`면 다시 받음) |

- 임시 이름으로 받은 뒤 완료되면 최종 이름으로 바꾼다. 파일이 있으면 완성본이다

---

## 검토 결과 (2026-09-28)

1. 다운로드 함수 반환은 `{status, video_id, url, path}`로 유지한다. `batch()` items와 실패
   `--json` 출력에도 `video_id` · `url`을 담는다 (D-14)
2. `--container`는 `mp4` · `mkv`만 허용한다 (D-12)
3. 라이브 방송 중인 영상의 `video()` · `audio()`는 `NotAvailable`(4)로 실패한다 (D-13)

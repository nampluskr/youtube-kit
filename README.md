# youtube-kit

## 개요

YouTube 영상 URL에서 영상 정보, 자막, 미디어(동영상·음성)를 얻는 파이썬 도구다.
재생목록 URL에서는 재생목록 정보와 영상 목록을 얻고, 여러 영상에 대한 작업을 한 번에
요청할 수도 있다.

주피터 노트북 같은 파이썬 환경에서는 함수로 직접 불러 결과를 확인하고, 다른 프로젝트나
도구에서는 `youtube-kit` 명령으로 불러 파이프라인의 한 단계로 쓴다. 두 방법은 같은 기능을
같은 형태의 결과로 제공한다.

youtube-kit은 스스로 고르지 않는다. 먼저 영상의 포맷·자막 트랙 목록을 조회해 보여주고,
무엇을 받을지는 사용자나 호출하는 프로그램이 정한다. 요청한 것이 없으면 다른 것으로
대신하지 않고 실패로 알리며, 받은 파일은 변환하지 않고 그대로 저장한다.

## 설치

### 요구사항
- Python 3.11 이상
- [ffmpeg](https://ffmpeg.org/) (동영상 병합 `video`에 필요, PATH에 등록되어 있어야 함)

### 설치 방법
저장소 폴더에서 editable 모드로 설치합니다:

```bash
cd D:\projects\youtube-kit
pip install -e .
```

설치 후 파이썬에서는 `import youtube_kit as yk`로, 터미널에서는 `youtube-kit` 명령으로 사용할 수 있습니다.

---

## 파이썬 API 사용법

```python
import youtube_kit as yk
```

### 1. `info(url, out_dir=None) -> dict`
영상 또는 재생목록의 메타데이터를 조회하고 파일로 저장합니다. 부를 때마다 새로 조회해 덮어씁니다.
- **영상 URL/ID:** `<id>.meta.json`을 저장하고 해당 내용의 `dict`를 반환합니다.
- **재생목록 URL:** `<list-id>.playlist.json`을 저장하고 해당 내용의 `dict`를 반환합니다.

```python
# 영상 정보 조회
info = yk.info("bWPXADZylm0", out_dir="outputs")
print(info["title"], info["duration_s"])

# 재생목록 정보 조회
p_info = yk.info("https://www.youtube.com/playlist?list=PLyPc3E0Xm540Yfdln9qlVyyrqRME80jJm", out_dir="outputs")
print(p_info["title"], len(p_info["entries"]))
```

### 2. `video(url, video, audio, container=None, out_dir=None, overwrite=False) -> dict`
영상 포맷과 음성 포맷을 각각 ID로 지정하여 다운로드하고 하나의 동영상 파일로 합칩니다.
- `container`: `"mp4"`, `"mkv"`, 또는 `None` (기본값: 스트림이 mp4에 들어가면 `mp4`, 아니면 `mkv`).
- 파일명: `<id>.<영상 ID>_<음성 ID>.<컨테이너>`

```python
res = yk.video("JyEsEcsCqzM", video="299", audio="140", container="mp4", out_dir="outputs")
print(res["status"], res["path"])
```

### 3. `audio(url, audio, out_dir=None, overwrite=False) -> dict`
음성 스트림을 포맷 ID로 지정하여 원본 그대로 다운로드합니다.
- 파일명: `<id>.<음성 ID>.<확장자>`

```python
res = yk.audio("JyEsEcsCqzM", audio="140", out_dir="outputs")
print(res["status"], res["path"])
```

### 4. `subtitle(url, track, fmt="srt", out_dir=None, overwrite=False) -> dict`
자막 트랙 ID(`<kind>:<youtube key>`)와 형식을 지정하여 다운로드합니다.
- `track`: 예) `"manual:ko"`, `"auto:ko-orig"`
- `fmt`: 기본값 `"srt"`, `"json3"`, `"vtt"` 등
- 파일명: `<id>.<종류>.<유튜브 키>.<형식>`

```python
# 한국어 수동 자막 (srt)
res = yk.subtitle("bWPXADZylm0", track="manual:ko", fmt="srt", out_dir="outputs")

# 한국어 자동 자막 (json3)
res = yk.subtitle("bWPXADZylm0", track="auto:ko-orig", fmt="json3", out_dir="outputs")
```

### 5. `batch(urls, jobs, out_dir=None, overwrite=False) -> dict`
여러 영상에 대한 작업(`video`, `audio`, `subtitle`)을 순차적으로 일괄 수행합니다. 개별 실패는 예외를 던지지 않고 결과에 기록하며 계속 진행합니다.

```python
urls = [
    "https://www.youtube.com/watch?v=bWPXADZylm0",
    "https://www.youtube.com/watch?v=xyTPUdJhxLM",
]
jobs = [
    {"do": "subtitle", "track": "manual:ko"},
    {"do": "audio", "audio": "140-1"},
]
res = yk.batch(urls, jobs, out_dir="outputs")
print(f"ok={res['ok']}, reused={res['reused']}, failed={res['failed']}")
```

---

## CLI 사용법

명령 이름은 `youtube-kit`입니다. stdout은 결과 전용으로 쓰이며, 진행 로그나 오류 메시지는 stderr로 출력됩니다.

### 1. `info`
```bash
# 표 형식으로 메타데이터 및 포맷/자막 목록 출력
youtube-kit info <url> [-o DIR]

# JSON 형식으로 출력
youtube-kit info <url> [-o DIR] --json
```

### 2. `video`
```bash
youtube-kit video <url> --video ID --audio ID [--container mp4|mkv] [-o DIR] [--overwrite] [--json]

# 예시:
youtube-kit video JyEsEcsCqzM --video 299 --audio 140 --container mp4 -o outputs
```

### 3. `audio`
```bash
youtube-kit audio <url> --audio ID [-o DIR] [--overwrite] [--json]

# 예시:
youtube-kit audio JyEsEcsCqzM --audio 140 -o outputs
```

### 4. `subtitle`
```bash
youtube-kit subtitle <url> --track ID [--format FMT] [-o DIR] [--overwrite] [--json]

# 예시:
youtube-kit subtitle bWPXADZylm0 --track manual:ko --format srt -o outputs
```

### 5. `batch`
한 줄에 URL 하나와 작업(`do`) 하나가 정의된 `jobs.jsonl` 파일을 입력으로 받아 일괄 수행합니다.

`jobs.jsonl` 예시:
```jsonl
{"url": "https://www.youtube.com/watch?v=bWPXADZylm0", "do": "audio", "audio": "140-1"}
{"url": "https://www.youtube.com/watch?v=bWPXADZylm0", "do": "subtitle", "track": "manual:ko"}
{"url": "https://www.youtube.com/watch?v=xyTPUdJhxLM", "do": "video", "video": "136", "audio": "140-1"}
```

`url`·`do` 외의 키는 해당 함수의 인자 이름(`video` · `audio` · `container` · `track` · `fmt`)만 쓸 수 있습니다. 다른 키가 있으면 기본값으로 대신 수행하지 않고 입력 전체를 잘못된 입력(종료 코드 2)으로 거부합니다.

실행:
```bash
youtube-kit batch jobs.jsonl [-o DIR] [--overwrite] [--json]
```

---

## 종료 코드 (Exit Codes)

| 코드 | 뜻 | 예외 | 낼 수 있는 명령 |
|---|---|---|---|
| 0 | 요청 성공 (재사용 포함) | — | 전부 |
| 1 | 그 밖의 오류 (네트워크 끊김 등) | `YoutubeKitError` | 전부 |
| 2 | 잘못된 입력 | `InvalidInput` | 전부 |
| 3 | 영상 접근 불가 (비공개, 삭제, 멤버십 등) | `VideoUnavailable` | `batch` 제외 전부 |
| 4 | 요청한 것이 없음 (없는 포맷·트랙, 라이브 등) | `NotAvailable` | `video` · `audio` · `subtitle` |
| 5 | 실행 환경 부족 (ffmpeg 없음) | `MissingDependency` | `video` |
| 6 | 일괄 수행 중 하나 이상 실패 | — | `batch` |

---

## 파일 규칙

| 함수 | 파일명 규칙 | 예시 |
|---|---|---|
| `info()` 영상 | `<id>.meta.json` | `bWPXADZylm0.meta.json` |
| `info()` 재생목록 | `<list-id>.playlist.json` | `PLyPc3E0Xm540Yfdln9qlVyyrqRME80jJm.playlist.json` |
| `video()` | `<id>.<영상 ID>_<음성 ID>.<컨테이너>` | `JyEsEcsCqzM.299_140.mp4` |
| `audio()` | `<id>.<음성 ID>.<확장자>` | `JyEsEcsCqzM.140.m4a` |
| `subtitle()` | `<id>.<종류>.<유튜브 키>.<형식>` | `bWPXADZylm0.manual.ko.srt` |

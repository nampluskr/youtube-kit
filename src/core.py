import json
import logging
import os
import re
import shutil
import tempfile
from datetime import datetime

import yt_dlp

from youtube_kit.errors import (
    Cancelled,
    InvalidInput,
    MissingDependency,
    NotAvailable,
    VideoUnavailable,
    YoutubeKitError,
)
from youtube_kit.url import parse_and_normalize_url

__version__ = "0.1.0"

_UNAVAILABLE_MARKERS = (
    "private video",
    "video unavailable",
    "this video is unavailable",
    "this video is no longer available",
    "removed by the uploader",
    "has been terminated",
    "who has blocked it",
    "not available in your country",
    "sign in to confirm your age",
    "age-restricted",
    "members-only",
    "this live event will begin",
    "this video is available to this channel's members",
    "this video does not exist",
)

# Transport failures must stay exit code 1 even when the text mentions
# "unavailable" (e.g. "HTTP Error 503: Service Unavailable").
_TRANSPORT_MARKERS = (
    "http error",
    "urlopen error",
    "timed out",
    "connection",
    "unable to download",
)

_NOT_AVAILABLE_MARKERS = (
    "requested format is not available",
)


def _handle_download_error(exc: Exception):
    msg = str(exc).lower()
    if any(m in msg for m in _TRANSPORT_MARKERS):
        raise YoutubeKitError(str(exc)) from exc
    if any(m in msg for m in _NOT_AVAILABLE_MARKERS):
        raise NotAvailable(str(exc)) from exc
    if any(m in msg for m in _UNAVAILABLE_MARKERS):
        raise VideoUnavailable(str(exc)) from exc
    raise YoutubeKitError(str(exc)) from exc


_log = logging.getLogger("youtube_kit")


class _QuietLogger:
    """yt-dlp logger that keeps its messages off stderr.

    yt-dlp prints "ERROR: ..." itself even with quiet=True. The same text is
    already carried by the exception youtube-kit raises, so it only goes to the
    "youtube_kit" logger at debug level.
    """

    def debug(self, msg):
        _log.debug(msg)

    info = warning = error = debug


_QUIET = _QuietLogger()


def _quiet_opts(**extra) -> dict:
    return {"quiet": True, "no_warnings": True, "noprogress": True, "logger": _QUIET, **extra}


class _Tracker:
    """Reports progress to the caller's callback and honours its cancel flag."""

    def __init__(self, video_id, progress=None, cancel=None):
        self.video_id = video_id
        self.progress = progress
        self.cancel = cancel
        self.cancelled = False

    def _cancel_requested(self) -> bool:
        if self.cancel is not None and self.cancel.is_set():
            self.cancelled = True
        return self.cancelled

    def check(self):
        if self._cancel_requested():
            raise Cancelled(f"Cancelled by caller: {self.video_id}")

    def emit(self, stage, downloaded_bytes=None, total_bytes=None, speed=None, eta=None):
        if self.progress is None:
            return
        event = {
            "video_id": self.video_id,
            "stage": stage,
            "downloaded_bytes": downloaded_bytes,
            "total_bytes": total_bytes,
            "speed": speed,
            "eta": eta,
        }
        try:
            self.progress(event)
        except Exception:
            # A broken callback must not break the download itself.
            _log.debug("progress callback raised", exc_info=True)

    def on_download(self, d):
        if self._cancel_requested():
            raise yt_dlp.utils.DownloadCancelled(f"Cancelled by caller: {self.video_id}")
        if d.get("status") == "downloading":
            self.emit(
                "download",
                d.get("downloaded_bytes"),
                d.get("total_bytes") or d.get("total_bytes_estimate"),
                d.get("speed"),
                d.get("eta"),
            )

    def on_postprocess(self, d):
        if self._cancel_requested():
            raise yt_dlp.utils.DownloadCancelled(f"Cancelled by caller: {self.video_id}")
        if d.get("postprocessor") == "Merger" and d.get("status") == "started":
            self.emit("merge")

    def ydl_opts(self) -> dict:
        return {"progress_hooks": [self.on_download], "postprocessor_hooks": [self.on_postprocess]}


def _run_download(std_url: str, opts: dict, tracker: _Tracker):
    """Run a yt-dlp download, turning a cancel from the hooks into Cancelled."""
    try:
        with yt_dlp.YoutubeDL({**_quiet_opts(), **tracker.ydl_opts(), **opts}) as ydl:
            ydl.download([std_url])
    except yt_dlp.utils.DownloadCancelled as exc:
        raise Cancelled(str(exc)) from exc
    except yt_dlp.utils.DownloadError as exc:
        # yt-dlp may wrap the cancel raised in a hook; the tracker knows.
        if tracker.cancelled:
            raise Cancelled(f"Cancelled by caller: {tracker.video_id}") from exc
        _handle_download_error(exc)
    except Exception as exc:
        if tracker.cancelled:
            raise Cancelled(f"Cancelled by caller: {tracker.video_id}") from exc
        raise YoutubeKitError(str(exc)) from exc


def _move_result(tmp_dir: str, final_path: str, what: str):
    candidates = [
        os.path.join(tmp_dir, f)
        for f in os.listdir(tmp_dir)
        if not f.endswith(".part") and not f.endswith(".ytdl")
    ]
    if not candidates:
        raise YoutubeKitError(f"Download finished but no {what} file was produced")
    shutil.move(candidates[0], final_path)


def _extract_info_safe(url: str, opts: dict | None = None) -> dict:
    base_opts = _quiet_opts()
    if opts:
        base_opts.update(opts)
    try:
        with yt_dlp.YoutubeDL(base_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        _handle_download_error(exc)
    except Exception as exc:
        raise YoutubeKitError(str(exc)) from exc


def _build_meta_dict(video_id: str, std_url: str, raw_info: dict) -> dict:
    chapters = []
    for c in raw_info.get("chapters") or []:
        chapters.append({
            "start_s": c.get("start_time"),
            "end_s": c.get("end_time"),
            "title": c.get("title", ""),
        })

    is_live = bool(raw_info.get("is_live"))
    duration = raw_info.get("duration")
    duration_s = None if is_live else (int(duration) if duration is not None else None)

    # Separate video formats and audio formats
    raw_formats = raw_info.get("formats") or []
    video_formats = []
    raw_audio_formats = []

    for f in raw_formats:
        vcodec = f.get("vcodec")
        acodec = f.get("acodec")
        fid = str(f.get("format_id", ""))

        if vcodec and vcodec != "none":
            video_formats.append({
                "id": fid,
                "ext": str(f.get("ext", "")),
                "vcodec": str(vcodec),
                "width": int(f["width"]) if f.get("width") is not None else None,
                "height": int(f["height"]) if f.get("height") is not None else None,
                "fps": f.get("fps"),
                "size": f.get("filesize") or f.get("filesize_approx"),
            })

        if (not vcodec or vcodec == "none") and acodec and acodec != "none":
            raw_audio_formats.append(f)

    # Determine whether there are multiple audio tracks
    has_track_suffix = any(
        "-" in str(f.get("format_id", "")) and str(f.get("format_id", "")).split("-")[-1].isdigit()
        for f in raw_audio_formats
    )
    langs_present = {f.get("language") for f in raw_audio_formats if f.get("language")}
    is_multi_track = has_track_suffix or len(langs_present) > 1

    audio_formats = []
    for f in raw_audio_formats:
        fid = str(f.get("format_id", ""))
        acodec = str(f.get("acodec", ""))
        note = (f.get("format_note") or "").lower()

        if not is_multi_track:
            original = None
        else:
            lang_pref = f.get("language_preference")
            if (lang_pref is not None and lang_pref >= 10) or "original" in note:
                original = True
            else:
                original = False

        drc = "-drc" in fid or "drc" in note

        audio_formats.append({
            "id": fid,
            "ext": str(f.get("ext", "")),
            "acodec": acodec,
            "abr": f.get("abr") or f.get("tbr"),
            "size": f.get("filesize") or f.get("filesize_approx"),
            "language": f.get("language"),
            "original": original,
            "drc": drc,
        })

    # Subtitles: manual and auto
    subtitles = []
    sub_sources = [
        ("manual", raw_info.get("subtitles") or {}),
        ("auto", raw_info.get("automatic_captions") or {}),
    ]
    for kind, sub_map in sub_sources:
        for key, formats_list in sub_map.items():
            name = None
            formats = []
            for item in formats_list:
                if not name and item.get("name"):
                    name = item.get("name")
                ext = item.get("ext")
                if ext and ext not in formats:
                    formats.append(ext)
            subtitles.append({
                "id": f"{kind}:{key}",
                "kind": kind,
                "key": key,
                "name": name or key,
                "formats": formats,
            })

    return {
        "id": video_id,
        "url": std_url,
        "title": raw_info.get("title") or "",
        "channel": raw_info.get("channel") or raw_info.get("uploader"),
        "channel_id": raw_info.get("channel_id") or raw_info.get("uploader_id"),
        "channel_url": raw_info.get("channel_url") or raw_info.get("uploader_url"),
        "upload_date": raw_info.get("upload_date"),
        "duration_s": duration_s,
        "description": raw_info.get("description") or "",
        "tags": raw_info.get("tags") or [],
        "categories": raw_info.get("categories") or [],
        "chapters": chapters,
        "language": raw_info.get("language"),
        "availability": raw_info.get("availability"),
        "age_limit": int(raw_info.get("age_limit") or 0),
        "is_live": is_live,
        "fetched_at": datetime.now().astimezone().isoformat(),
        "youtube_kit_version": __version__,
        "yt_dlp_version": yt_dlp.version.__version__,
        "video_formats": video_formats,
        "audio_formats": audio_formats,
        "subtitles": subtitles,
    }


def _build_playlist_dict(playlist_id: str, std_url: str, raw_info: dict) -> dict:
    entries = []
    for e in raw_info.get("entries") or []:
        eid = e.get("id")
        if eid:
            entries.append({
                "id": eid,
                "url": f"https://www.youtube.com/watch?v={eid}",
                "title": e.get("title") or "",
            })

    return {
        "id": playlist_id,
        "url": std_url,
        "title": raw_info.get("title") or "",
        "channel": raw_info.get("channel") or raw_info.get("uploader") or "",
        "fetched_at": datetime.now().astimezone().isoformat(),
        "youtube_kit_version": __version__,
        "yt_dlp_version": yt_dlp.version.__version__,
        "entries": entries,
    }


def info(url: str, out_dir: str | None = None) -> dict:
    """UC-1. Queries every call and overwrites the file; never reused.
    Video URL    -> writes <id>.meta.json, returns its content.
    Playlist URL -> writes <list-id>.playlist.json, returns its content.
    Downloads no video, audio or subtitle.
    """
    url_type, std_url, item_id = parse_and_normalize_url(url)
    dest_dir = out_dir if out_dir is not None else "."
    os.makedirs(dest_dir, exist_ok=True)

    if url_type == "playlist":
        opts = {
            "extract_flat": True,
        }
        raw = _extract_info_safe(std_url, opts)
        data = _build_playlist_dict(item_id, std_url, raw)
        target_path = os.path.join(dest_dir, f"{item_id}.playlist.json")
    else:
        opts = {
            "skip_download": True,
            "writesubtitles": False,
            "writeautomaticsub": False,
        }
        raw = _extract_info_safe(std_url, opts)
        data = _build_meta_dict(item_id, std_url, raw)
        target_path = os.path.join(dest_dir, f"{item_id}.meta.json")

    # Atomic write to avoid partial writes
    tmp_path = target_path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, target_path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    return data


def video(
    url: str,
    video: str,
    audio: str,
    container: str | None = None,
    out_dir: str | None = None,
    overwrite: bool = False,
    progress=None,
    cancel=None,
) -> dict:
    """UC-2. video/audio: format IDs (required, no default).
    container: "mp4" | "mkv" | None. None -> mp4 if both streams fit mp4,
    otherwise mkv. Needs ffmpeg. Live streams raise NotAvailable.
    progress: callable(dict) receiving download/merge/done events.
    cancel: object with is_set(); when set, raises Cancelled and leaves no file.
    """
    if not video or not isinstance(video, str):
        raise InvalidInput("Missing or invalid 'video' format ID")
    if not audio or not isinstance(audio, str):
        raise InvalidInput("Missing or invalid 'audio' format ID")
    if container is not None and container not in ("mp4", "mkv"):
        raise InvalidInput(f"Invalid container: {container!r}. Allowed: 'mp4', 'mkv'")

    url_type, std_url, video_id = parse_and_normalize_url(url)
    if url_type != "video":
        raise InvalidInput("video() expects a video URL or ID, not a playlist")

    if not shutil.which("ffmpeg"):
        raise MissingDependency("ffmpeg is required for merging video and audio streams")

    tracker = _Tracker(video_id, progress, cancel)
    tracker.check()

    dest_dir = out_dir if out_dir is not None else "."
    os.makedirs(dest_dir, exist_ok=True)

    # Extract metadata to check formats and live status
    raw_info = _extract_info_safe(
        std_url,
        {
            "skip_download": True,
        },
    )
    tracker.check()

    if raw_info.get("is_live"):
        raise NotAvailable("Cannot download live streams")

    formats = raw_info.get("formats") or []
    v_fmt = next((f for f in formats if str(f.get("format_id")) == str(video)), None)
    a_fmt = next((f for f in formats if str(f.get("format_id")) == str(audio)), None)

    if not v_fmt:
        raise NotAvailable(f"Video format ID {video!r} not found for video {video_id}")
    if not a_fmt:
        raise NotAvailable(f"Audio format ID {audio!r} not found for video {video_id}")

    vcodec = (v_fmt.get("vcodec") or "").lower()
    acodec = (a_fmt.get("acodec") or "").lower()

    if not vcodec or vcodec == "none":
        raise NotAvailable(f"Format ID {video!r} has no video stream")
    if not acodec or acodec == "none":
        raise NotAvailable(f"Format ID {audio!r} has no audio stream")

    # Codec compatibility check:
    # mp4 requires video (H.264 / AVC or AV1) and audio (AAC / mp4a)
    is_v_mp4 = vcodec.startswith("avc") or vcodec.startswith("av01") or "h264" in vcodec
    is_a_mp4 = acodec.startswith("mp4a") or "aac" in acodec
    fits_mp4 = is_v_mp4 and is_a_mp4

    if container is None:
        target_container = "mp4" if fits_mp4 else "mkv"
    elif container == "mp4":
        if not fits_mp4:
            raise NotAvailable(
                f"Selected codecs (video: {vcodec}, audio: {acodec}) cannot be merged into mp4 container"
            )
        target_container = "mp4"
    else:
        target_container = "mkv"

    final_filename = f"{video_id}.{video}_{audio}.{target_container}"
    final_path = os.path.join(dest_dir, final_filename)

    if os.path.exists(final_path) and not overwrite:
        return {
            "status": "reused",
            "video_id": video_id,
            "url": std_url,
            "path": final_path,
        }

    # Download into a temporary directory, then move to final_path. On cancel or
    # error the directory is removed, so no partial file is left behind.
    with tempfile.TemporaryDirectory(dir=dest_dir) as tmp_dir:
        _run_download(std_url, {
            "format": f"{video}+{audio}",
            "merge_output_format": target_container,
            "outtmpl": os.path.join(tmp_dir, f"{video_id}.%(ext)s"),
        }, tracker)
        tracker.check()
        _move_result(tmp_dir, final_path, "merged")

    tracker.emit("done")
    return {
        "status": "ok",
        "video_id": video_id,
        "url": std_url,
        "path": final_path,
    }


def audio(
    url: str,
    audio: str,
    out_dir: str | None = None,
    overwrite: bool = False,
    progress=None,
    cancel=None,
) -> dict:
    """UC-3. audio: format ID (required). Saved as-is, no conversion.
    Live streams raise NotAvailable. progress/cancel: see video().
    """
    if not audio or not isinstance(audio, str):
        raise InvalidInput("Missing or invalid 'audio' format ID")

    url_type, std_url, video_id = parse_and_normalize_url(url)
    if url_type != "video":
        raise InvalidInput("audio() expects a video URL or ID, not a playlist")

    tracker = _Tracker(video_id, progress, cancel)
    tracker.check()

    dest_dir = out_dir if out_dir is not None else "."
    os.makedirs(dest_dir, exist_ok=True)

    raw_info = _extract_info_safe(
        std_url,
        {
            "skip_download": True,
        },
    )
    tracker.check()

    if raw_info.get("is_live"):
        raise NotAvailable("Cannot download live streams")

    formats = raw_info.get("formats") or []
    a_fmt = next((f for f in formats if str(f.get("format_id")) == str(audio)), None)

    if not a_fmt:
        raise NotAvailable(f"Audio format ID {audio!r} not found for video {video_id}")

    ext = a_fmt.get("ext") or "m4a"
    final_filename = f"{video_id}.{audio}.{ext}"
    final_path = os.path.join(dest_dir, final_filename)

    if os.path.exists(final_path) and not overwrite:
        return {
            "status": "reused",
            "video_id": video_id,
            "url": std_url,
            "path": final_path,
        }

    with tempfile.TemporaryDirectory(dir=dest_dir) as tmp_dir:
        _run_download(std_url, {
            "format": str(audio),
            "outtmpl": os.path.join(tmp_dir, f"{video_id}.%(ext)s"),
        }, tracker)
        tracker.check()
        _move_result(tmp_dir, final_path, "audio")

    tracker.emit("done")
    return {
        "status": "ok",
        "video_id": video_id,
        "url": std_url,
        "path": final_path,
    }


def subtitle(
    url: str,
    track: str,
    fmt: str = "srt",
    out_dir: str | None = None,
    overwrite: bool = False,
    progress=None,
    cancel=None,
) -> dict:
    """UC-4. track: "<kind>:<youtube key>", e.g. "manual:ko", "auto:ko-orig".
    Saved as-is in the requested format, no conversion or cleanup.
    progress/cancel: see video(). yt-dlp may report no download events for
    subtitles, so only "done" is guaranteed.
    """
    if not track or not isinstance(track, str) or ":" not in track:
        raise InvalidInput("track must be formatted as '<kind>:<youtube key>', e.g. 'manual:ko'")

    kind, key = track.split(":", 1)
    if kind not in ("manual", "auto"):
        raise InvalidInput(f"Invalid subtitle kind: {kind!r}. Must be 'manual' or 'auto'")
    if not key:
        raise InvalidInput("Subtitle key cannot be empty")

    url_type, std_url, video_id = parse_and_normalize_url(url)
    if url_type != "video":
        raise InvalidInput("subtitle() expects a video URL or ID, not a playlist")

    tracker = _Tracker(video_id, progress, cancel)
    tracker.check()

    dest_dir = out_dir if out_dir is not None else "."
    os.makedirs(dest_dir, exist_ok=True)

    raw_info = _extract_info_safe(
        std_url,
        {
            "skip_download": True,
        },
    )
    tracker.check()

    sub_map = (raw_info.get("subtitles") or {}) if kind == "manual" else (raw_info.get("automatic_captions") or {})
    if key not in sub_map:
        raise NotAvailable(f"Subtitle track {track!r} not available for video {video_id}")

    track_formats = [item.get("ext") for item in sub_map[key] if item.get("ext")]
    if fmt not in track_formats:
        raise NotAvailable(
            f"Format {fmt!r} not available for track {track!r}. Available formats: {track_formats}"
        )

    final_filename = f"{video_id}.{kind}.{key}.{fmt}"
    final_path = os.path.join(dest_dir, final_filename)

    if os.path.exists(final_path) and not overwrite:
        return {
            "status": "reused",
            "video_id": video_id,
            "url": std_url,
            "path": final_path,
        }

    with tempfile.TemporaryDirectory(dir=dest_dir) as tmp_dir:
        _run_download(std_url, {
            "skip_download": True,
            "writesubtitles": (kind == "manual"),
            "writeautomaticsub": (kind == "auto"),
            # yt-dlp treats each entry as a regex; match the key literally
            "subtitleslangs": [re.escape(key)],
            "subtitlesformat": fmt,
            "outtmpl": os.path.join(tmp_dir, f"{video_id}.%(ext)s"),
        }, tracker)
        tracker.check()
        _move_result(tmp_dir, final_path, f"subtitle ({track})")

    tracker.emit("done")
    return {
        "status": "ok",
        "video_id": video_id,
        "url": std_url,
        "path": final_path,
    }


_JOB_KEYS = {
    "video": {"video", "audio", "container"},
    "audio": {"audio"},
    "subtitle": {"track", "fmt"},
}


def batch(
    urls: list[str],
    jobs: list[dict],
    out_dir: str | None = None,
    overwrite: bool = False,
    progress=None,
    cancel=None,
) -> dict:
    """UC-5. jobs[i] applies to urls[i]. do: "video" | "audio" | "subtitle".
    Runs sequentially; a failed item does not stop the rest and is reported
    in the result, not raised.
    progress: events of each item, with "index" and "total" added.
    cancel: stops the running item and raises Cancelled; finished items' files stay.
    """
    if not isinstance(urls, (list, tuple)) or not isinstance(jobs, (list, tuple)):
        raise InvalidInput("urls and jobs must be lists")

    if len(urls) != len(jobs):
        raise InvalidInput(
            f"Length mismatch: {len(urls)} urls but {len(jobs)} jobs"
        )

    for i, j in enumerate(jobs):
        if not isinstance(j, dict):
            raise InvalidInput(f"Job at index {i} must be a dict")
        do = j.get("do")
        if do not in _JOB_KEYS:
            raise InvalidInput(
                f"Invalid job 'do' at index {i}: {do!r}. Must be 'video', 'audio', or 'subtitle'"
            )
        # An unknown key (e.g. a typo of 'fmt') would otherwise be ignored and the
        # job would silently run with a default instead of what was asked.
        unknown = set(j) - _JOB_KEYS[do] - {"do"}
        if unknown:
            raise InvalidInput(
                f"Unknown key(s) for '{do}' job at index {i}: {sorted(unknown)}. "
                f"Allowed: {sorted(_JOB_KEYS[do])}"
            )

    items = []
    ok_count = 0
    reused_count = 0
    failed_count = 0

    def item_progress(index):
        if progress is None:
            return None
        return lambda event: progress({**event, "index": index, "total": len(urls)})

    for index, (url, job) in enumerate(zip(urls, jobs)):
        do = job.get("do")
        video_id = None
        std_url = url
        try:
            _, std_url, video_id = parse_and_normalize_url(url)
        except Exception:
            pass

        common = {
            "out_dir": out_dir,
            "overwrite": overwrite,
            "progress": item_progress(index),
            "cancel": cancel,
        }
        try:
            if do == "video":
                res = video(
                    url,
                    video=job.get("video"),
                    audio=job.get("audio"),
                    container=job.get("container"),
                    **common,
                )
            elif do == "audio":
                res = audio(url, audio=job.get("audio"), **common)
            elif do == "subtitle":
                res = subtitle(url, track=job.get("track"), fmt=job.get("fmt", "srt"), **common)

            status = res["status"]
            if status == "ok":
                ok_count += 1
            elif status == "reused":
                reused_count += 1

            items.append({
                "video_id": res["video_id"],
                "url": res["url"],
                "do": do,
                "status": status,
                "path": res["path"],
            })

        except Cancelled:
            # A cancel stops the whole batch; it is not an item failure.
            raise
        except YoutubeKitError as exc:
            failed_count += 1
            items.append({
                "video_id": video_id,
                "url": std_url,
                "do": do,
                "status": "failed",
                "error": type(exc).__name__,
                "message": str(exc),
            })
        except Exception as exc:
            failed_count += 1
            items.append({
                "video_id": video_id,
                "url": std_url,
                "do": do,
                "status": "failed",
                "error": "YoutubeKitError",
                "message": str(exc),
            })

    return {
        "items": items,
        "ok": ok_count,
        "reused": reused_count,
        "failed": failed_count,
    }


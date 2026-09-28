import argparse
import json
import os
import sys

from youtube_kit.core import audio, batch, info, subtitle, video
from youtube_kit.errors import (
    InvalidInput,
    MissingDependency,
    NotAvailable,
    VideoUnavailable,
    YoutubeKitError,
)
from youtube_kit.url import parse_and_normalize_url

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass



class CLIParser(argparse.ArgumentParser):
    # Set by main() from the argv actually being parsed; sys.argv differs when
    # main(argv) is called programmatically.
    json_output = False

    def error(self, message):
        if CLIParser.json_output:
            out = {
                "status": "error",
                "video_id": None,
                "url": None,
                "error": "InvalidInput",
                "message": message,
            }
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            sys.exit(2)
        sys.stderr.write(f"usage: {self.format_usage().strip()}\n")
        sys.stderr.write(f"youtube-kit: error: {message}\n")
        sys.exit(2)


def _format_size(size_bytes):
    if size_bytes is None:
        return "-"
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def _print_info_table(res, out_dir):
    dest_dir = out_dir if out_dir is not None else "."
    if "entries" in res:
        # Playlist
        target_path = os.path.join(dest_dir, f"{res['id']}.playlist.json")
        print(f"Saved: {target_path}")
        print(f"Playlist: {res.get('title')} ({res.get('channel')}) - {len(res.get('entries', []))} videos\n")
        print(f"{'#':<5} {'ID':<15} {'TITLE'}")
        print("-" * 60)
        for idx, e in enumerate(res.get("entries", []), start=1):
            print(f"{idx:<5} {e.get('id', ''):<15} {e.get('title', '')}")
        return

    # Video
    target_path = os.path.join(dest_dir, f"{res['id']}.meta.json")
    print(f"Saved: {target_path}")
    print(f"Title: {res.get('title')}\n")

    print("[Video Formats]")
    print(f"{'ID':<10} {'EXT':<6} {'RES':<12} {'FPS':<6} {'VCODEC':<20} {'SIZE'}")
    print("-" * 65)
    for f in res.get("video_formats", []):
        w = f.get("width")
        h = f.get("height")
        res_str = f"{w}x{h}" if w and h else (f"{h}p" if h else "-")
        fps_str = str(f.get("fps") or "-")
        size_str = _format_size(f.get("size"))
        print(f"{f['id']:<10} {f['ext']:<6} {res_str:<12} {fps_str:<6} {f['vcodec'][:20]:<20} {size_str}")

    print("\n[Audio Formats]")
    print(f"{'ID':<10} {'EXT':<6} {'ACODEC':<18} {'ABR':<10} {'LANG':<8} {'ORIGINAL':<10} {'DRC'}")
    print("-" * 75)
    for f in res.get("audio_formats", []):
        abr_str = f"{f['abr']:.1f}k" if f.get("abr") else "-"
        orig_str = str(f.get("original")) if f.get("original") is not None else "-"
        drc_str = str(f.get("drc"))
        lang_str = str(f.get("language") or "-")
        print(f"{f['id']:<10} {f['ext']:<6} {f['acodec'][:18]:<18} {abr_str:<10} {lang_str:<8} {orig_str:<10} {drc_str}")

    print("\n[Subtitles]")
    print(f"{'ID':<25} {'KIND':<8} {'KEY':<12} {'NAME':<25} {'FORMATS'}")
    print("-" * 85)
    for s in res.get("subtitles", []):
        formats_str = ", ".join(s.get("formats", []))
        print(f"{s['id']:<25} {s['kind']:<8} {s['key']:<12} {s['name'][:25]:<25} {formats_str}")


def _print_batch_summary(res):
    items = res.get("items", [])
    total = len(items)
    for i, item in enumerate(items, start=1):
        status = item.get("status")
        vid = item.get("video_id") or "-"
        do = item.get("do")
        if status in ("ok", "reused"):
            path = item.get("path")
            print(f"[{i}/{total}] {status:<6} {vid} {do} -> {path}")
        else:
            err = item.get("error")
            msg = item.get("message")
            print(f"[{i}/{total}] {status:<6} {vid} {do} ({err}: {msg})")
    print(f"\nSummary: ok={res.get('ok', 0)}, reused={res.get('reused', 0)}, failed={res.get('failed', 0)} (total: {total})")


def main(argv=None):

    if argv is None:
        argv = sys.argv[1:]
    CLIParser.json_output = "--json" in argv

    parser = CLIParser(
        prog="youtube-kit",
        description="Deterministic YouTube metadata, subtitle, and media extractor",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: info
    p_info = subparsers.add_parser("info", help="Query and save video/playlist information")
    p_info.add_argument("url", help="Video or playlist URL or 11-character video ID")
    p_info.add_argument("-o", "--out-dir", dest="out_dir", default=None, help="Output directory")
    p_info.add_argument("--json", action="store_true", help="Output result as JSON")

    # Subcommand: video
    p_video = subparsers.add_parser("video", help="Download video and audio merged into container")
    p_video.add_argument("url", help="Video URL or 11-character video ID")
    p_video.add_argument("--video", required=True, help="Video format ID")
    p_video.add_argument("--audio", required=True, help="Audio format ID")
    p_video.add_argument("--container", choices=["mp4", "mkv"], default=None, help="Output container (mp4 or mkv)")
    p_video.add_argument("-o", "--out-dir", dest="out_dir", default=None, help="Output directory")
    p_video.add_argument("--overwrite", action="store_true", help="Re-download if file already exists")
    p_video.add_argument("--json", action="store_true", help="Output result as JSON")

    # Subcommand: audio
    p_audio = subparsers.add_parser("audio", help="Download audio stream as-is")
    p_audio.add_argument("url", help="Video URL or 11-character video ID")
    p_audio.add_argument("--audio", required=True, help="Audio format ID")
    p_audio.add_argument("-o", "--out-dir", dest="out_dir", default=None, help="Output directory")
    p_audio.add_argument("--overwrite", action="store_true", help="Re-download if file already exists")
    p_audio.add_argument("--json", action="store_true", help="Output result as JSON")

    # Subcommand: subtitle
    p_sub = subparsers.add_parser("subtitle", help="Download subtitle track as-is")
    p_sub.add_argument("url", help="Video URL or 11-character video ID")
    p_sub.add_argument("--track", required=True, help="Subtitle track ID (<kind>:<key>)")
    p_sub.add_argument("--format", dest="fmt", default="srt", help="Subtitle format (default: srt)")
    p_sub.add_argument("-o", "--out-dir", dest="out_dir", default=None, help="Output directory")
    p_sub.add_argument("--overwrite", action="store_true", help="Re-download if file already exists")
    p_sub.add_argument("--json", action="store_true", help="Output result as JSON")

    # Subcommand: batch
    p_batch = subparsers.add_parser("batch", help="Run batch jobs from JSON Lines file")
    p_batch.add_argument("jobs_file", help="Path to jobs.jsonl file")
    p_batch.add_argument("-o", "--out-dir", dest="out_dir", default=None, help="Output directory")
    p_batch.add_argument("--overwrite", action="store_true", help="Re-download if file already exists")
    p_batch.add_argument("--json", action="store_true", help="Output result as JSON")

    args = parser.parse_args(argv)

    # Attempt to pre-parse video_id and standard url for error reporting
    video_id = None
    std_url = None
    if hasattr(args, "url") and args.url:
        try:
            _, std_url, video_id = parse_and_normalize_url(args.url)
        except Exception:
            pass

    try:
        if args.command == "info":
            res = info(args.url, out_dir=args.out_dir)
            if args.json:
                sys.stdout.write(json.dumps(res, ensure_ascii=False) + "\n")
            else:
                _print_info_table(res, args.out_dir)

        elif args.command == "video":
            res = video(
                args.url,
                video=args.video,
                audio=args.audio,
                container=args.container,
                out_dir=args.out_dir,
                overwrite=args.overwrite,
            )
            if args.json:
                sys.stdout.write(json.dumps(res, ensure_ascii=False) + "\n")
            else:
                sys.stdout.write(str(res["path"]) + "\n")

        elif args.command == "audio":
            res = audio(
                args.url,
                audio=args.audio,
                out_dir=args.out_dir,
                overwrite=args.overwrite,
            )
            if args.json:
                sys.stdout.write(json.dumps(res, ensure_ascii=False) + "\n")
            else:
                sys.stdout.write(str(res["path"]) + "\n")

        elif args.command == "subtitle":
            res = subtitle(
                args.url,
                track=args.track,
                fmt=args.fmt,
                out_dir=args.out_dir,
                overwrite=args.overwrite,
            )
            if args.json:
                sys.stdout.write(json.dumps(res, ensure_ascii=False) + "\n")
            else:
                sys.stdout.write(str(res["path"]) + "\n")

        elif args.command == "batch":
            jobs_file = args.jobs_file
            if not os.path.exists(jobs_file):
                raise InvalidInput(f"Jobs file not found: {jobs_file}")

            urls = []
            jobs = []
            with open(jobs_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if not lines:
                raise InvalidInput("Jobs file is empty")

            for line_no, line in enumerate(lines, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception as e:
                    raise InvalidInput(f"Invalid JSON at line {line_no}: {e}")

                if not isinstance(entry, dict):
                    raise InvalidInput(f"Line {line_no} must be a JSON object")

                url = entry.get("url")
                do = entry.get("do")
                if not url:
                    raise InvalidInput(f"Missing 'url' at line {line_no}")
                if not do:
                    raise InvalidInput(f"Missing 'do' at line {line_no}")
                if do == "info":
                    raise InvalidInput(f"'info' job not allowed in batch at line {line_no}")

                job_dict = dict(entry)
                del job_dict["url"]
                urls.append(url)
                jobs.append(job_dict)

            if not urls:
                raise InvalidInput("No valid jobs in file")

            res = batch(urls, jobs, out_dir=args.out_dir, overwrite=args.overwrite)
            if args.json:
                sys.stdout.write(json.dumps(res, ensure_ascii=False) + "\n")
            else:
                _print_batch_summary(res)

            if res.get("failed", 0) > 0:
                sys.exit(6)
            sys.exit(0)

        sys.exit(0)


    except YoutubeKitError as exc:
        exc_name = type(exc).__name__
        exit_code = getattr(exc, "exit_code", 1)
        if args.json:
            err_data = {
                "status": "error",
                "video_id": video_id,
                "url": std_url,
                "error": exc_name,
                "message": str(exc),
            }
            sys.stdout.write(json.dumps(err_data, ensure_ascii=False) + "\n")
        else:
            sys.stderr.write(f"Error ({exc_name}): {exc}\n")
        sys.exit(exit_code)

    except KeyboardInterrupt:
        # Ctrl+C: the temporary download directory is removed on the way out,
        # so this ends like a Cancelled with no partial file.
        message = "Cancelled by user (Ctrl+C)"
        if args.json:
            err_data = {
                "status": "error",
                "video_id": video_id,
                "url": std_url,
                "error": "Cancelled",
                "message": message,
            }
            sys.stdout.write(json.dumps(err_data, ensure_ascii=False) + "\n")
        else:
            sys.stderr.write(f"Error (Cancelled): {message}\n")
        sys.exit(130)

    except Exception as exc:
        if args.json:
            err_data = {
                "status": "error",
                "video_id": video_id,
                "url": std_url,
                "error": "YoutubeKitError",
                "message": str(exc),
            }
            sys.stdout.write(json.dumps(err_data, ensure_ascii=False) + "\n")
        else:
            sys.stderr.write(f"Error: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

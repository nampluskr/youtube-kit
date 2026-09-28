"""Offline regression tests. No network access is needed."""

import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
from unittest import mock

import yt_dlp

import youtube_kit as yk
from youtube_kit import cli, core
from youtube_kit.url import parse_and_normalize_url


class TestErrorClassification(unittest.TestCase):

    def classify(self, message):
        try:
            core._handle_download_error(Exception(message))
        except yk.YoutubeKitError as exc:
            return type(exc)

    def test_transport_error_is_not_video_unavailable(self):
        self.assertIs(self.classify("ERROR: Unable to download API page: HTTP Error 503: Service Unavailable"),
                      yk.YoutubeKitError)
        self.assertIs(self.classify("ERROR: unable to download video data: HTTP Error 403: Forbidden"),
                      yk.YoutubeKitError)

    def test_video_unavailable(self):
        for msg in ["ERROR: [youtube] x: Video unavailable",
                    "ERROR: [youtube] x: This video is unavailable",
                    "ERROR: [youtube] x: Private video. Sign in if you've been granted access",
                    "ERROR: [youtube] x: This video is available to this channel's members on level"]:
            self.assertIs(self.classify(msg), yk.VideoUnavailable, msg)

    def test_requested_format_gone_is_not_available(self):
        self.assertIs(self.classify("ERROR: [youtube] x: Requested format is not available"),
                      yk.NotAvailable)


class TestPlaylistId(unittest.TestCase):

    def test_rejects_ids_unsafe_as_file_names(self):
        for bad in ["../../evil", "a%3Ab", "a/b"]:
            with self.assertRaises(yk.InvalidInput, msg=bad):
                parse_and_normalize_url(f"https://www.youtube.com/playlist?list={bad}")

    def test_accepts_normal_id(self):
        _, url, list_id = parse_and_normalize_url(
            "https://www.youtube.com/playlist?list=PLyPc3E0Xm540Yfdln9qlVyyrqRME80jJm")
        self.assertEqual(list_id, "PLyPc3E0Xm540Yfdln9qlVyyrqRME80jJm")


class TestInputBeforeEnvironment(unittest.TestCase):

    def test_invalid_url_wins_over_missing_ffmpeg(self):
        with mock.patch("youtube_kit.core.shutil.which", return_value=None):
            with self.assertRaises(yk.InvalidInput):
                yk.video("abc", video="1", audio="2")
            with self.assertRaises(yk.MissingDependency):
                yk.video("bWPXADZylm0", video="1", audio="2")


class TestBatchJobKeys(unittest.TestCase):

    def test_unknown_key_rejects_whole_batch(self):
        for job in [{"do": "subtitle", "track": "manual:ko", "format": "vtt"},
                    {"do": "audio", "audio": "140", "fmt": "srt"}]:
            with self.assertRaises(yk.InvalidInput, msg=job):
                yk.batch(["bWPXADZylm0"], [job])


class TestCliArgv(unittest.TestCase):

    def test_parser_error_uses_given_argv_for_json(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit) as ctx:
            cli.main(["video", "bWPXADZylm0", "--video", "1", "--audio", "2",
                      "--container", "webm", "--json"])
        self.assertEqual(ctx.exception.code, 2)
        out = json.loads(buf.getvalue())
        self.assertEqual(out["error"], "InvalidInput")
        self.assertIsNone(out["video_id"])


class TestProgressAndCancel(unittest.TestCase):

    def test_download_hook_maps_to_event(self):
        events = []
        tracker = core._Tracker("vid00000000", progress=events.append)
        tracker.on_download({"status": "downloading", "downloaded_bytes": 10,
                             "total_bytes_estimate": 100, "speed": 5.0, "eta": 18})
        tracker.on_postprocess({"postprocessor": "Merger", "status": "started"})
        tracker.emit("done")
        self.assertEqual(events[0], {"video_id": "vid00000000", "stage": "download",
                                     "downloaded_bytes": 10, "total_bytes": 100,
                                     "speed": 5.0, "eta": 18})
        self.assertEqual([e["stage"] for e in events], ["download", "merge", "done"])

    def test_broken_callback_does_not_break_download(self):
        def boom(event):
            raise RuntimeError("callback bug")
        tracker = core._Tracker("vid00000000", progress=boom)
        tracker.on_download({"status": "downloading", "downloaded_bytes": 1})  # no raise

    def test_cancel_in_hook(self):
        stop = threading.Event()
        stop.set()
        tracker = core._Tracker("vid00000000", cancel=stop)
        with self.assertRaises(yt_dlp.utils.DownloadCancelled):
            tracker.on_download({"status": "downloading"})
        self.assertTrue(tracker.cancelled)

    def test_cancel_after_lookup_raises_cancelled(self):
        stop = threading.Event()

        def lookup(url, opts=None):
            stop.set()  # cancelled while the lookup was running
            return {"formats": [{"format_id": "140", "ext": "m4a", "acodec": "mp4a.40.2"}]}

        with mock.patch("youtube_kit.core._extract_info_safe", side_effect=lookup), \
                tempfile.TemporaryDirectory() as d:
            with self.assertRaises(yk.Cancelled):
                yk.audio("bWPXADZylm0", audio="140", out_dir=d, cancel=stop)
            self.assertEqual(os.listdir(d), [])

    def test_batch_cancel_raises_and_keeps_finished_items(self):
        calls = []

        def fake_audio(url, audio, **kwargs):
            calls.append(url)
            if len(calls) == 2:
                raise yk.Cancelled("stop")
            return {"status": "ok", "video_id": "bWPXADZylm0", "url": url, "path": "x.m4a"}

        with mock.patch("youtube_kit.core.audio", side_effect=fake_audio):
            with self.assertRaises(yk.Cancelled):
                yk.batch(["bWPXADZylm0", "xyTPUdJhxLM", "VbD8ITrJ6lg"],
                         [{"do": "audio", "audio": "140"}] * 3)
        self.assertEqual(len(calls), 2)  # the third item never ran

    def test_batch_progress_adds_index_and_total(self):
        events = []

        def fake_audio(url, audio, progress=None, **kwargs):
            progress({"video_id": "v", "stage": "done"})
            return {"status": "ok", "video_id": "v", "url": url, "path": "x.m4a"}

        with mock.patch("youtube_kit.core.audio", side_effect=fake_audio):
            yk.batch(["bWPXADZylm0", "xyTPUdJhxLM"], [{"do": "audio", "audio": "140"}] * 2,
                     progress=events.append)
        self.assertEqual([(e["index"], e["total"]) for e in events], [(0, 2), (1, 2)])

    def test_cli_ctrl_c_exits_130(self):
        buf = io.StringIO()
        with mock.patch("youtube_kit.cli.audio", side_effect=KeyboardInterrupt), \
                contextlib.redirect_stdout(buf), self.assertRaises(SystemExit) as ctx:
            cli.main(["audio", "bWPXADZylm0", "--audio", "140", "--json"])
        self.assertEqual(ctx.exception.code, 130)
        out = json.loads(buf.getvalue())
        self.assertEqual(out["error"], "Cancelled")
        self.assertEqual(out["video_id"], "bWPXADZylm0")

    def test_cancelled_exit_code(self):
        self.assertEqual(yk.Cancelled.exit_code, 130)
        self.assertTrue(issubclass(yk.Cancelled, yk.YoutubeKitError))


class TestQuietLogger(unittest.TestCase):

    def test_yt_dlp_messages_do_not_reach_stderr(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            core._QUIET.error("ERROR: [youtube] x: Private video")
            core._QUIET.warning("WARNING: something")
        self.assertEqual(err.getvalue(), "")


if __name__ == "__main__":
    unittest.main()

"""Offline regression tests. No network access is needed."""

import contextlib
import io
import json
import os
import unittest
from unittest import mock

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


if __name__ == "__main__":
    unittest.main()
